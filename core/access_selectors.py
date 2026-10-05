"""Consultas read-only de propriedade usadas pelas políticas de acesso."""

from datetime import date

from django.db.models import Q, QuerySet
from django.utils import timezone


class ObjectAccessSelector:
    """Verifica vínculos entre o usuário e objetos do domínio."""

    @staticmethod
    def student_id_for_route(view_module: str, view_kwargs: dict) -> object | None:
        """Resolve o aluno também nas rotas genéricas de endereço."""
        student_id = view_kwargs.get("student_id")
        if view_module == "students.views":
            return view_kwargs.get("pk", student_id)
        if view_module == "addresses.views":
            entity_type, entity_id = view_kwargs.get("entity_type"), view_kwargs.get("entity_id")
            if view_kwargs.get("address_id"):
                from addresses.selectors import AddressSelector

                selector = AddressSelector()
                entity_type, entity_id = selector.get_entity_context(
                    selector.get_by_id(view_kwargs["address_id"])
                )
            if entity_type == "student":
                return entity_id
        return student_id

    @staticmethod
    def require_student_access(user, student_id) -> None:
        """Repete o escopo obrigatório antes de mutações do aluno e seus dados."""
        from base.exceptions import PermissionDeniedError
        from core.permissions import role_name

        role = role_name(user)
        if role == "TEACHER" and not ObjectAccessSelector.teacher_can_access_student(
            user.pk, student_id
        ):
            raise PermissionDeniedError("Aluno fora do escopo do professor.")
        if role == "GUARDIAN" and not ObjectAccessSelector.guardian_can_access_student(
            user.pk, student_id
        ):
            raise PermissionDeniedError("Aluno fora do escopo do responsável.")

    @staticmethod
    def guardian_can_access_student(user_id, student_id) -> bool:
        """Confirma vínculo ativo entre responsável e aluno."""
        from guardians.selectors import GuardianSelector

        return GuardianSelector().user_can_access_student(user_id, student_id)

    @staticmethod
    def guardian_can_access_activity(user_id, activity_id) -> bool:
        """Confirma que a atividade pertence a turma de aluno vinculado."""
        from activities.selectors import ActivitySelector

        return ActivitySelector().guardian_can_access_activity(user_id, activity_id)

    @staticmethod
    def teacher_classes(user_id, on_date: date | None = None) -> QuerySet:
        """Turmas ativas atribuídas a uma conta e perfil docentes válidos."""
        from classes.contracts import Class
        from teachers.contracts import Teacher

        reference = on_date or timezone.localdate()
        teachers = Teacher.objects.filter(
            user_id=user_id,
            is_active=True,
            user__is_active=True,
            user__deleted_at__isnull=True,
        ).values("pk")
        owner = Q(class_teacher_id__in=teachers)
        schedule = Q(
            schedules__teacher_id__in=teachers,
            schedules__is_active=True,
            schedules__deleted_at__isnull=True,
            schedules__valid_from__lte=reference,
        ) & (Q(schedules__valid_until__isnull=True) | Q(schedules__valid_until__gte=reference))
        return Class.objects.filter(owner | schedule, is_active=True).distinct()

    @staticmethod
    def teacher_enrollments(user_id) -> QuerySet:
        """Matrículas e alunos vigentes nas turmas atualmente acessíveis."""
        from classes.contracts import Enrollment

        return Enrollment.objects.filter(
            class_obj_id__in=ObjectAccessSelector.teacher_classes(user_id).values("pk"),
            status=Enrollment.Status.ACTIVE,
            is_active=True,
            enrollment_date__lte=timezone.localdate(),
            student__is_active=True,
            student__deleted_at__isnull=True,
        )

    @staticmethod
    def teacher_can_access_class(user_id, class_id, on_date=None) -> bool:
        """Confirma a atribuição válida, com referência histórica apenas na grade."""
        return ObjectAccessSelector.teacher_classes(user_id, on_date).filter(pk=class_id).exists()

    @staticmethod
    def teacher_can_access_teacher(user_id, teacher_id) -> bool:
        """Confirma que o perfil consultado pertence ao usuário professor."""
        from teachers.contracts import Teacher

        return Teacher.objects.filter(pk=teacher_id, user_id=user_id).exists()

    @staticmethod
    def teacher_has_current_class_subject(teacher_id, class_id, subject_id, on_date) -> bool:
        """Confirma a combinação exata e vigente na grade horária."""
        from agenda.contracts import Schedule

        return (
            Schedule.objects.filter(
                teacher_id=teacher_id,
                class_obj_id=class_id,
                subject_id=subject_id,
                is_active=True,
                deleted_at__isnull=True,
                valid_from__lte=on_date,
            )
            .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=on_date))
            .exists()
        )

    @staticmethod
    def teacher_can_access_activity(user_id, activity_id) -> bool:
        """Confirma autoria da atividade pelo professor."""
        from activities.contracts import Activity

        return Activity.objects.filter(pk=activity_id, teacher__user_id=user_id).exists()

    @staticmethod
    def teacher_can_access_subject(user_id, subject_id) -> bool:
        """Confirma que a disciplina não excluída está atribuída ao professor."""
        from teachers.contracts import Subject

        return Subject.all_objects.filter(
            pk=subject_id,
            deleted_at__isnull=True,
            teachers__user_id=user_id,
        ).exists()

    @staticmethod
    def teacher_can_access_attendance(user_id, record_id) -> bool:
        """Confirma que a chamada pertence ao professor."""
        from attendance.contracts import AttendanceRecord

        return AttendanceRecord.objects.filter(pk=record_id, teacher__user_id=user_id).exists()

    @staticmethod
    def teacher_can_access_student(user_id, student_id) -> bool:
        """Confirma matrícula vigente do aluno no escopo docente canônico."""
        return (
            ObjectAccessSelector.teacher_enrollments(user_id).filter(student_id=student_id).exists()
        )
