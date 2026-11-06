"""ActivityService: regras para atividades e lançamento de notas."""

from decimal import Decimal

from django.db import transaction

from base.context import require_tenant_schema
from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from base.repositories import BaseRepository
from base.services import BaseService, system_command


class _ActivityRepo(BaseRepository):
    @property
    def model_class(self):
        from activities.models import Activity

        return Activity


class ActivityCoreService(BaseService):
    """Serviço de aplicação para o domínio de atividades."""

    def create_activity(self, data: dict):
        """Cria uma atividade. Dispara evento para notificações futuras."""
        from activities.models import Activity

        self.validate_required(
            data,
            ["class_obj_id", "subject_id", "teacher_id", "title", "due_date", "max_score"],
        )

        from classes.contracts import Class
        from teachers.contracts import Subject, Teacher

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
            {"teacher": teacher, "subject": subject, "class_obj": class_obj},
            on_date=data["due_date"],
        )

        max_score = Decimal(str(data["max_score"]))
        if max_score <= 0:
            raise ValidationError(errors={"max_score": ["Nota máxima deve ser positiva."]})

        from activities.models import ActivitySubmission
        from classes.contracts import Enrollment
        from students.contracts import ImportUsageService

        ImportUsageService(user=self.user).seal_for_use(
            student_ids=Enrollment.objects.filter(class_obj=class_obj, status="ACTIVE").values_list(
                "student_id", flat=True
            )
        )

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
        activity = self._get_locked_activity(activity_id)
        self._assert_activity_actor(activity)
        if activity.score_status == activity.ScoreStatus.LAUNCHED:
            raise BusinessRuleViolationError(
                "As notas estão lançadas oficialmente. Reabra-as para editar a atividade."
            )
        old = {"title": activity.title, "due_date": str(activity.due_date)}
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
        effective_relations = {
            "class_obj": updates.get("class_obj", activity.class_obj),
            "subject": updates.get("subject", activity.subject),
            "teacher": updates.get("teacher", activity.teacher),
        }
        self._validate_activity_relations(
            effective_relations,
            on_date=updates.get("due_date", activity.due_date),
        )
        class_changed = "class_obj" in updates and updates["class_obj"].pk != activity.class_obj_id
        if class_changed:
            self._assert_class_change_allowed(activity)
        updates["updated_by"] = self.user
        activity = repo.update(
            activity,
            expected_version=data.get("version", activity.version),
            **updates,
        )
        if class_changed:
            self._deactivate_activity_groups(activity)
            self._sync_activity_submissions(activity)
        if activity.modality == activity.Modality.INDIVIDUAL:
            self._deactivate_activity_groups(activity)
        self._record_audit("UPDATE", activity, old_values=old)
        self._log("Atividade atualizada", activity_id=str(activity.pk))
        return activity

    @system_command
    def sync_class_submissions(self, class_id, tenant_schema: str) -> dict[str, int]:
        """Sincroniza entregas das atividades em rascunho após mudanças de matrícula."""
        require_tenant_schema(tenant_schema)
        from activities.models import Activity

        activities = list(
            Activity.objects.select_for_update()
            .filter(class_obj_id=class_id, score_status=Activity.ScoreStatus.DRAFT)
            .order_by("pk")
        )
        totals = {"inserted": 0, "restored": 0, "deactivated": 0}
        for activity in activities:
            changes = self._sync_activity_submissions(activity)
            for key, value in changes.items():
                totals[key] += value
        self._log(
            "activity_class_submissions_synced",
            class_id=str(class_id),
            activity_count=len(activities),
            **totals,
        )
        return totals

    def _sync_activity_submissions(self, activity) -> dict[str, int]:
        """Sincroniza entregas pré-carregadas quando a turma da atividade muda."""
        from activities.models import ActivitySubmission
        from classes.contracts import Enrollment

        active_student_ids = set(
            Enrollment.objects.filter(
                class_obj=activity.class_obj, status=Enrollment.Status.ACTIVE
            ).values_list("student_id", flat=True)
        )
        existing = {}
        changes = {"inserted": 0, "restored": 0, "deactivated": 0}
        for item in (
            ActivitySubmission.all_objects.select_for_update()
            .filter(activity=activity)
            .order_by("-is_active", "-updated_at")
        ):
            existing.setdefault(item.student_id, item)
        for student_id in active_student_ids:
            submission = existing.get(student_id)
            if submission is None:
                submission = ActivitySubmission.objects.create(
                    activity=activity,
                    student_id=student_id,
                    created_by=self.user,
                    updated_by=self.user,
                )
                self._record_audit("INSERT", submission)
                changes["inserted"] += 1
            elif submission.is_deleted or not submission.is_active:
                submission.restore(user=self.user)
                self._record_audit("RESTORE", submission)
                changes["restored"] += 1
        for student_id, submission in existing.items():
            if student_id not in active_student_ids and submission.is_active:
                submission.soft_delete(user=self.user)
                self._record_audit("DELETE", submission)
                changes["deactivated"] += 1
        return changes

    @staticmethod
    def _activity_has_results(activity) -> bool:
        """Indica se há qualquer resultado individual ou coletivo lançado."""
        from django.db.models import Q

        return (
            activity.submissions.filter(
                Q(score__isnull=False) | ~Q(feedback="") | Q(submitted_at__isnull=False)
            ).exists()
            or activity.groups.filter(Q(score__isnull=False) | ~Q(feedback="")).exists()
        )

    def _assert_class_change_allowed(self, activity) -> None:
        """Impede a troca de turma depois do primeiro resultado lançado."""
        if self._activity_has_results(activity):
            raise BusinessRuleViolationError(
                "A turma não pode ser alterada depois do lançamento de resultados."
            )

    def _validate_activity_relations(self, data: dict, *, on_date) -> None:
        """Valida autoria e vínculos entre professor, disciplina e turma."""
        teacher = data.get("teacher")
        subject = data.get("subject")
        class_obj = data.get("class_obj")
        if teacher and subject and not teacher.subjects.filter(pk=subject.pk).exists():
            raise ValidationError(
                errors={"subject": ["A disciplina não está vinculada ao professor selecionado."]}
            )
        if teacher and subject and class_obj:
            from core.access_selectors import ObjectAccessSelector

            if not ObjectAccessSelector.teacher_has_current_class_subject(
                teacher.pk,
                class_obj.pk,
                subject.pk,
                on_date,
            ):
                raise ValidationError(
                    errors={
                        "class_obj": [
                            "Professor, turma e disciplina não possuem vínculo vigente na grade."
                        ]
                    }
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
