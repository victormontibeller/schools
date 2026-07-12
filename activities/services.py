"""ActivityService: regras para atividades e lançamento de notas."""

import logging
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from base.exceptions import (
    ObjectNotFoundError,
    ValidationError,
)
from base.repositories import BaseRepository
from base.services import BaseService

logger = logging.getLogger(__name__)


class _ActivityRepo(BaseRepository):
    @property
    def model_class(self):
        from activities.models import Activity

        return Activity


class _SubmissionRepo(BaseRepository):
    @property
    def model_class(self):
        from activities.models import ActivitySubmission

        return ActivitySubmission


class ActivityService(BaseService):
    """Serviço de aplicação para o domínio de atividades."""

    def create_activity(self, data: dict):
        """Cria uma atividade. Dispara evento para notificações futuras."""
        from activities.models import Activity

        self.validate_required(
            data,
            ["class_obj_id", "subject_id", "teacher_id", "title", "due_date", "max_score"],
        )

        from classes.models import Class
        from teachers.models import Subject, Teacher

        try:
            class_obj = Class.objects.get(pk=data["class_obj_id"])
        except Class.DoesNotExist:
            raise ObjectNotFoundError("Class", str(data["class_obj_id"])) from None

        try:
            subject = Subject.objects.get(pk=data["subject_id"])
        except Subject.DoesNotExist:
            raise ObjectNotFoundError("Subject", str(data["subject_id"])) from None

        try:
            teacher = Teacher.objects.get(pk=data["teacher_id"])
        except Teacher.DoesNotExist:
            raise ObjectNotFoundError("Teacher", str(data["teacher_id"])) from None

        self._validate_activity_relations({"teacher": teacher, "subject": subject})

        max_score = Decimal(str(data["max_score"]))
        if max_score <= 0:
            raise ValidationError(errors={"max_score": ["Nota máxima deve ser positiva."]})

        from activities.models import ActivitySubmission
        from classes.models import Enrollment

        with transaction.atomic():
            activity = Activity.objects.create(
                class_obj=class_obj,
                subject=subject,
                teacher=teacher,
                title=data["title"].strip(),
                description=(data.get("description") or "").strip(),
                type=data.get("type", Activity.Type.HOMEWORK),
                due_date=data["due_date"],
                max_score=max_score,
                weight=Decimal(str(data.get("weight", 1.00))),
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", activity)
            submissions = [
                ActivitySubmission(
                    activity=activity,
                    student_id=student_id,
                    created_by=self.user,
                    updated_by=self.user,
                )
                for student_id in Enrollment.objects.filter(
                    class_obj=class_obj, status=Enrollment.Status.ACTIVE
                ).values_list("student_id", flat=True)
            ]
            ActivitySubmission.objects.bulk_create(submissions)
            for submission in submissions:
                self._record_audit("INSERT", submission)
        self._log("Atividade criada", activity_id=str(activity.pk))
        return activity

    def update_activity(self, activity_id, data: dict):
        """Atualiza campos permitidos de uma atividade existente."""
        repo = _ActivityRepo()
        activity = repo.get_by_id(activity_id)
        old = {"title": activity.title, "due_date": str(activity.due_date)}

        self._validate_activity_relations(data)
        allowed = {
            "title",
            "description",
            "type",
            "due_date",
            "max_score",
            "weight",
            "class_obj",
            "subject",
            "teacher",
        }
        updates = {k: v for k, v in data.items() if k in allowed}
        updates["updated_by"] = self.user
        activity = repo.update(activity, **updates)
        if "class_obj" in updates:
            self._sync_activity_submissions(activity)
        self._record_audit("UPDATE", activity, old_values=old)
        self._log("Atividade atualizada", activity_id=str(activity.pk))
        return activity

    def _sync_activity_submissions(self, activity) -> None:
        """Sincroniza entregas pré-carregadas quando a turma da atividade muda."""
        from activities.models import ActivitySubmission
        from classes.models import Enrollment

        active_student_ids = set(
            Enrollment.objects.filter(
                class_obj=activity.class_obj, status=Enrollment.Status.ACTIVE
            ).values_list("student_id", flat=True)
        )
        existing = {item.student_id: item for item in activity.submissions.all()}
        for student_id in active_student_ids - set(existing):
            submission = ActivitySubmission.objects.create(
                activity=activity,
                student_id=student_id,
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", submission)
        for student_id in set(existing) - active_student_ids:
            submission = existing[student_id]
            if submission.score is None and not submission.feedback:
                submission.soft_delete(user=self.user)
                self._record_audit("DELETE", submission)

    def _validate_activity_relations(self, data: dict) -> None:
        """Valida se professor ministra a disciplina selecionada."""
        teacher = data.get("teacher")
        subject = data.get("subject")
        if teacher and subject and not teacher.subjects.filter(pk=subject.pk).exists():
            raise ValidationError(
                errors={"subject": ["A disciplina não está vinculada ao professor selecionado."]}
            )

    def record_score(self, activity_id, student_id, score, feedback: str = ""):
        """Lança/atualiza a nota de um aluno numa atividade."""
        from activities.models import ActivitySubmission
        from students.models import Student

        activity = _ActivityRepo().get_by_id(activity_id)
        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            raise ObjectNotFoundError("Student", str(student_id)) from None
        if not ActivitySubmission.objects.filter(activity=activity, student=student).exists():
            raise ValidationError(
                errors={"student": ["Aluno não pertence à turma desta atividade."]}
            )

        try:
            score_decimal = Decimal(str(score))
        except (ValueError, TypeError, ArithmeticError) as exc:
            raise ValidationError(errors={"score": ["Nota invalida."]}) from exc

        if score_decimal < 0 or score_decimal > activity.max_score:
            raise ValidationError(
                errors={"score": [f"Nota deve estar entre 0 e {activity.max_score}."]}
            )

        submission, created = ActivitySubmission.objects.update_or_create(
            activity=activity,
            student=student,
            defaults={
                "score": score_decimal,
                "feedback": (feedback or "").strip(),
                "updated_by": self.user,
            },
        )
        # Marca a primeira nota, inclusive para entregas pré-carregadas.
        if submission.submitted_at is None:
            from django.utils import timezone

            submission.submitted_at = timezone.now()
            submission.save(update_fields=["submitted_at"])

        self._record_audit("UPDATE" if not created else "INSERT", submission)
        self._log(
            "Nota lançada",
            activity_id=str(activity.pk),
            student_id=str(student.pk),
            submission_id=str(submission.pk),
        )
        return submission

    @transaction.atomic
    def batch_record_scores(self, activity_id, scores_data, recorded_by=None):
        """Lança notas em lote para vários alunos numa chamada atômica."""
        submissions: list = []
        errors: list[dict] = []
        for entry in scores_data:
            if entry.get("score") in (None, "") and not entry.get("feedback", "").strip():
                continue
            if entry.get("score") in (None, ""):
                raise ValidationError(errors={"score": ["Informe a nota quando houver feedback."]})
            try:
                sub = self.record_score(
                    activity_id,
                    entry["student_id"],
                    entry["score"],
                    entry.get("feedback", ""),
                )
                submissions.append(sub)
            except (ValidationError, ObjectNotFoundError, DjangoValidationError) as exc:
                errors.append({"student_id": str(entry.get("student_id")), "message": str(exc)})

        self._log(
            "Notas em lote",
            activity_id=str(activity_id),
            ok_count=len(submissions),
            error_count=len(errors),
        )
        return {"created": len(submissions), "errors": errors}
