"""Comandos atômicos para o lançamento de notas por aluno."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.utils import timezone

from activities.services.activity import _ActivityRepo
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.repositories import BaseRepository
from base.services import service_command


class _SubmissionRepo(BaseRepository):
    """Repositório com compare-and-swap das entregas de atividade."""

    @property
    def model_class(self):
        from activities.models import ActivitySubmission

        return ActivitySubmission


class ActivityScoreMixin:
    """Lançamento em grade com pré-validação e concorrência por linha."""

    def batch_record_scores(self, activity_id, scores_data: list[dict]) -> dict[str, int]:
        """Persiste todas as notas válidas ou nenhuma, usando a versão de cada linha."""
        from activities.models import ActivitySubmission
        from classes.contracts import Enrollment

        activity = self._get_locked_activity(activity_id)
        self._assert_activity_actor(activity)
        self._assert_scores_editable(activity)
        normalized_rows, errors = self._normalize_rows(activity, scores_data)
        if errors:
            raise ValidationError(errors=errors)

        student_ids = [row["student_id"] for row in normalized_rows]
        locked_submissions = list(
            ActivitySubmission.objects.select_for_update()
            .filter(activity=activity, student_id__in=student_ids)
            .select_related("student")
            .order_by(
                "student__first_name",
                "student__last_name",
                "student__enrollment_number",
                "pk",
            )
        )
        submissions_by_student = {
            str(submission.student_id): submission for submission in locked_submissions
        }
        active_student_ids = {
            str(student_id)
            for student_id in Enrollment.objects.filter(
                class_obj=activity.class_obj,
                status=Enrollment.Status.ACTIVE,
                student_id__in=student_ids,
            ).values_list("student_id", flat=True)
        }
        for row in normalized_rows:
            student_id = row["student_id"]
            submission = submissions_by_student.get(student_id)
            if submission is None or student_id not in active_student_ids:
                errors.setdefault(student_id, {}).setdefault("score", []).append(
                    "Aluno não pertence à turma desta atividade."
                )
                continue
            if submission.version != row["version"]:
                errors.setdefault(student_id, {}).setdefault("version", []).append(
                    "Esta linha foi alterada por outra pessoa. "
                    "Recarregue os dados e tente novamente."
                )
        if errors:
            raise ValidationError(errors=errors)

        saved = 0
        repository = _SubmissionRepo()
        for row in normalized_rows:
            submission = submissions_by_student[row["student_id"]]
            submitted_at = (
                submission.submitted_at or timezone.now() if row["score"] is not None else None
            )
            if (
                submission.score == row["score"]
                and submission.feedback == row["feedback"]
                and (submission.submitted_at is None) == (submitted_at is None)
            ):
                continue
            old_values = self._snapshot(submission, ["score", "feedback", "submitted_at"])
            submission = repository.update(
                submission,
                expected_version=row["version"],
                score=row["score"],
                feedback=row["feedback"],
                submitted_at=submitted_at,
                updated_by=self.user,
            )
            self._record_audit("UPDATE", submission, old_values=old_values)
            saved += 1
        if saved:
            self._log("activity_scores_recorded", activity_id=str(activity.pk), saved_count=saved)
        return {"saved": saved}

    @service_command
    def launch_scores(self, activity_id, version: int):
        """Torna oficiais as notas atuais de uma atividade."""
        activity = self._get_locked_activity(activity_id)
        self._assert_activity_actor(activity)
        self._assert_scores_editable(activity)
        expected_version = self._validate_activity_version(version)
        self._assert_all_active_students_have_valid_scores(activity)
        old_values = self._snapshot(activity, ["score_status", "scores_launched_at"])
        activity = _ActivityRepo().update(
            activity,
            expected_version=expected_version,
            score_status=activity.ScoreStatus.LAUNCHED,
            scores_launched_at=timezone.now(),
            updated_by=self.user,
        )
        self._record_audit("UPDATE", activity, old_values=old_values)
        self._log("activity_scores_launched", activity_id=str(activity.pk))
        return activity

    @service_command
    def reopen_scores(self, activity_id, version: int, reason: str):
        """Reabre notas oficiais mediante motivo informado pelo usuário."""
        reason = (reason or "").strip()
        if not reason:
            raise ValidationError(errors={"reason": ["Informe o motivo da reabertura."]})

        activity = self._get_locked_activity(activity_id)
        self._assert_activity_actor(activity)
        if activity.score_status != activity.ScoreStatus.LAUNCHED:
            raise BusinessRuleViolationError("As notas desta atividade já estão em rascunho.")
        expected_version = self._validate_activity_version(version)
        old_values = self._snapshot(activity, ["score_status", "scores_launched_at"])
        activity = _ActivityRepo().update(
            activity,
            expected_version=expected_version,
            score_status=activity.ScoreStatus.DRAFT,
            scores_launched_at=None,
            updated_by=self.user,
        )
        self._record_audit(
            "UPDATE",
            activity,
            old_values=old_values,
            new_values={
                "score_status": activity.score_status,
                "scores_launched_at": activity.scores_launched_at,
                "reason": reason,
            },
        )
        self._log("activity_scores_reopened", activity_id=str(activity.pk))
        return activity

    @staticmethod
    def _assert_scores_editable(activity) -> None:
        """Impede mutações na grade depois do lançamento oficial."""
        if activity.score_status != activity.ScoreStatus.DRAFT:
            raise BusinessRuleViolationError(
                "As notas estão lançadas oficialmente. Reabra-as para editar."
            )

    @staticmethod
    def _assert_all_active_students_have_valid_scores(activity) -> None:
        """Exige uma nota finita e válida para cada matrícula ativa antes do lançamento."""
        from activities.models import ActivitySubmission
        from classes.contracts import Enrollment

        active_student_ids = list(
            Enrollment.objects.select_for_update()
            .filter(class_obj=activity.class_obj, status=Enrollment.Status.ACTIVE)
            .values_list("student_id", flat=True)
        )
        if not active_student_ids:
            raise BusinessRuleViolationError(
                "A atividade precisa ter matrículas ativas com notas válidas antes do lançamento."
            )
        submissions_by_student = {
            submission.student_id: submission
            for submission in ActivitySubmission.objects.select_for_update().filter(
                activity=activity,
                student_id__in=active_student_ids,
            )
        }
        for student_id in active_student_ids:
            submission = submissions_by_student.get(student_id)
            score = submission.score if submission is not None else None
            if score is None or not score.is_finite() or score < 0 or score > activity.max_score:
                raise BusinessRuleViolationError(
                    "Todas as matrículas ativas precisam ter notas válidas antes do lançamento."
                )

    @staticmethod
    def _get_locked_activity(activity_id):
        """Obtém a atividade ativa sob lock para serializar o workflow de notas."""
        from activities.models import Activity

        try:
            return (
                Activity.objects.select_for_update()
                .select_related("teacher__user")
                .get(pk=activity_id)
            )
        except Activity.DoesNotExist:
            raise ObjectNotFoundError("Activity", str(activity_id)) from None

    @staticmethod
    def _validate_activity_version(version: int) -> int:
        """Normaliza a versão recebida sem vazar exceções de infraestrutura."""
        try:
            normalized_version = int(version)
        except (TypeError, ValueError):
            raise ValidationError(errors={"version": ["Versão da atividade inválida."]}) from None
        if normalized_version < 0:
            raise ValidationError(errors={"version": ["Versão da atividade inválida."]})
        return normalized_version

    @staticmethod
    def _normalize_rows(activity, scores_data: list[dict]) -> tuple[list[dict], dict]:
        """Valida todos os valores de entrada sem escrever no banco."""
        if not isinstance(scores_data, list):
            raise ValidationError(errors={"__all__": ["Dados de notas inválidos."]})

        normalized_rows: list[dict] = []
        errors: dict = {}
        seen_student_ids: set[str] = set()
        for index, entry in enumerate(scores_data):
            if not isinstance(entry, dict):
                errors.setdefault("__all__", []).append("Dados de notas inválidos.")
                continue
            student_id = str(entry.get("student_id") or "")
            row_errors: dict[str, list[str]] = {}
            if not student_id:
                row_errors["student_id"] = ["Aluno obrigatório."]
            else:
                try:
                    UUID(student_id)
                except (TypeError, ValueError, AttributeError):
                    row_errors["student_id"] = ["Aluno inválido."]
            if student_id and student_id in seen_student_ids:
                row_errors["student_id"] = ["Aluno informado mais de uma vez."]
            seen_student_ids.add(student_id)

            feedback = str(entry.get("feedback") or "").strip()
            score_value = entry.get("score")
            score = None
            if score_value not in (None, ""):
                try:
                    score = Decimal(str(score_value))
                except (InvalidOperation, TypeError, ValueError):
                    row_errors["score"] = ["Nota inválida."]
                else:
                    if not score.is_finite() or score < 0 or score > activity.max_score:
                        row_errors["score"] = [f"Nota deve estar entre 0 e {activity.max_score}."]
            elif feedback:
                row_errors["score"] = ["Informe a nota quando houver feedback."]

            try:
                version = int(entry["version"])
                if version < 0:
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                row_errors["version"] = ["Versão da linha inválida."]
                version = -1

            if row_errors:
                errors[student_id or f"row-{index}"] = row_errors
                continue
            normalized_rows.append(
                {
                    "student_id": student_id,
                    "score": score,
                    "feedback": feedback,
                    "version": version,
                }
            )
        return normalized_rows, errors
