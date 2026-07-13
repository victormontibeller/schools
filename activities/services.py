"""ActivityService: regras para atividades e lançamento de notas."""

import logging
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
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

        self._validate_activity_relations(
            {"teacher": teacher, "subject": subject, "class_obj": class_obj}
        )

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
                modality=data.get("modality", Activity.Modality.INDIVIDUAL),
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
            "modality",
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
        if activity.modality == activity.Modality.INDIVIDUAL:
            self._deactivate_activity_groups(activity)
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
        for membership in activity.group_memberships.exclude(student_id__in=active_student_ids):
            membership.soft_delete(user=self.user)
            self._record_audit("DELETE", membership)

    def _validate_activity_relations(self, data: dict) -> None:
        """Valida autoria e vínculos entre professor, disciplina e turma."""
        teacher = data.get("teacher")
        subject = data.get("subject")
        class_obj = data.get("class_obj")
        if teacher and subject and not teacher.subjects.filter(pk=subject.pk).exists():
            raise ValidationError(
                errors={"subject": ["A disciplina não está vinculada ao professor selecionado."]}
            )
        if teacher and class_obj:
            linked = (
                class_obj.class_teacher_id == teacher.pk
                or class_obj.schedules.filter(teacher=teacher).exists()
            )
            if not linked:
                raise ValidationError(
                    errors={"class_obj": ["O professor não está vinculado a esta turma."]}
                )
        if teacher:
            from core.permissions import role_name

            if role_name(self.user) == "TEACHER" and teacher.user_id != self.user.pk:
                raise PermissionDeniedError("Professor não autorizado para esta atividade.")

    def _assert_activity_actor(self, activity) -> None:
        """Impede que um professor altere atividade de outro docente."""
        from core.permissions import role_name

        if role_name(self.user) == "TEACHER" and activity.teacher.user_id != self.user.pk:
            raise PermissionDeniedError("Atividade fora do escopo do professor.")

    def record_score(self, activity_id, student_id, score, feedback: str = ""):
        """Lança/atualiza a nota de um aluno numa atividade."""
        from activities.models import ActivitySubmission
        from students.models import Student

        activity = _ActivityRepo().get_by_id(activity_id)
        self._assert_activity_actor(activity)
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
    def save_group(self, activity_id, data: dict, group_id=None):
        """Cria ou edita um grupo e substitui sua composição de integrantes."""
        from activities.models import ActivityGroup, ActivityGroupMember
        from classes.models import Enrollment

        activity = _ActivityRepo().get_by_id(activity_id)
        self._assert_activity_actor(activity)
        if activity.modality != activity.Modality.GROUP:
            raise BusinessRuleViolationError("A atividade não está configurada como grupo.")
        self.validate_required(data, ["name", "student_ids"])
        student_ids = {str(student_id) for student_id in data["student_ids"]}
        active_ids = {
            str(student_id)
            for student_id in Enrollment.objects.filter(
                class_obj=activity.class_obj, status=Enrollment.Status.ACTIVE
            ).values_list("student_id", flat=True)
        }
        if not student_ids or not student_ids.issubset(active_ids):
            raise ValidationError(errors={"students": ["Selecione apenas alunos ativos da turma."]})
        duplicate = ActivityGroupMember.objects.filter(
            activity=activity, student_id__in=student_ids
        )
        if group_id:
            duplicate = duplicate.exclude(group_id=group_id)
        if duplicate.exists():
            raise BusinessRuleViolationError(
                "Um ou mais alunos já pertencem a outro grupo desta atividade."
            )
        name = data["name"].strip()
        same_name = ActivityGroup.objects.filter(activity=activity, name__iexact=name)
        if group_id:
            same_name = same_name.exclude(pk=group_id)
        if same_name.exists():
            raise ValidationError(errors={"name": ["Já existe um grupo com este nome."]})

        if group_id:
            try:
                group = ActivityGroup.objects.get(pk=group_id, activity=activity)
            except ActivityGroup.DoesNotExist:
                raise ObjectNotFoundError("ActivityGroup", str(group_id)) from None
            old = self._snapshot(group, ["name"])
            group.name = name
            group.updated_by = self.user
            group.save(update_fields=["name", "updated_by", "updated_at"])
            self._record_audit("UPDATE", group, old_values=old)
            for membership in group.memberships.all():
                membership.soft_delete(user=self.user)
                self._record_audit("DELETE", membership)
        else:
            group = ActivityGroup.objects.create(
                activity=activity,
                name=name,
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", group)

        for student_id in student_ids:
            membership = ActivityGroupMember.objects.create(
                activity=activity,
                group=group,
                student_id=student_id,
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", membership)
        self._log(
            "grupo_atividade_salvo",
            activity_id=str(activity.pk),
            group_id=str(group.pk),
            member_count=len(student_ids),
        )
        return group

    @transaction.atomic
    def apply_group_result(self, activity_id, group_id, score, feedback: str = ""):
        """Salva o resultado coletivo e o reaplica explicitamente aos integrantes."""
        from activities.models import ActivityGroup

        activity = _ActivityRepo().get_by_id(activity_id)
        self._assert_activity_actor(activity)
        try:
            group = ActivityGroup.objects.get(pk=group_id, activity=activity)
        except ActivityGroup.DoesNotExist:
            raise ObjectNotFoundError("ActivityGroup", str(group_id)) from None
        try:
            score_decimal = Decimal(str(score))
        except (ValueError, TypeError, ArithmeticError) as exc:
            raise ValidationError(errors={"score": ["Nota inválida."]}) from exc
        if score_decimal < 0 or score_decimal > activity.max_score:
            raise ValidationError(
                errors={"score": [f"Nota deve estar entre 0 e {activity.max_score}."]}
            )
        old = self._snapshot(group, ["score", "feedback"])
        group.score = score_decimal
        group.feedback = (feedback or "").strip()
        group.updated_by = self.user
        group.save(update_fields=["score", "feedback", "updated_by", "updated_at"])
        self._record_audit("UPDATE", group, old_values=old)
        for student_id in group.memberships.values_list("student_id", flat=True):
            self.record_score(activity.pk, student_id, score_decimal, group.feedback)
        self._log(
            "resultado_grupo_aplicado",
            activity_id=str(activity.pk),
            group_id=str(group.pk),
            member_count=group.memberships.count(),
        )
        return group

    def deactivate_group(self, activity_id, group_id):
        """Desativa um grupo e suas associações sem apagar notas individuais."""
        from activities.models import ActivityGroup

        activity = _ActivityRepo().get_by_id(activity_id)
        self._assert_activity_actor(activity)
        try:
            group = ActivityGroup.objects.get(pk=group_id, activity=activity)
        except ActivityGroup.DoesNotExist:
            raise ObjectNotFoundError("ActivityGroup", str(group_id)) from None
        for membership in group.memberships.all():
            membership.soft_delete(user=self.user)
            self._record_audit("DELETE", membership)
        group.soft_delete(user=self.user)
        self._record_audit("DELETE", group)
        self._log(
            "grupo_atividade_desativado",
            activity_id=str(activity.pk),
            group_id=str(group.pk),
        )
        return group

    def _deactivate_activity_groups(self, activity) -> None:
        """Desativa grupos quando a atividade volta a ser individual."""
        for group in activity.groups.all():
            self.deactivate_group(activity.pk, group.pk)

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
