"""Consultas read-only de propriedade usadas pelas políticas de acesso."""

from django.db.models import Q
from django.utils import timezone


class ObjectAccessSelector:
    """Verifica vínculos entre o usuário e objetos do domínio."""

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
    def teacher_can_access_class(user_id, class_id, on_date=None) -> bool:
        """Confirma responsabilidade ou horário do professor na turma."""
        from classes.contracts import Class

        reference_date = on_date or timezone.localdate()
        schedule_scope = Q(
            schedules__teacher__user_id=user_id,
            schedules__is_active=True,
            schedules__deleted_at__isnull=True,
            schedules__valid_from__lte=reference_date,
        ) & (Q(schedules__valid_until__isnull=True) | Q(schedules__valid_until__gte=reference_date))
        return Class.objects.filter(
            Q(class_teacher__user_id=user_id) | schedule_scope,
            pk=class_id,
        ).exists()

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
        """Confirma matrícula do aluno em turma do professor."""
        from django.db.models import Q

        from classes.contracts import Enrollment

        today = timezone.localdate()
        schedule_scope = Q(
            class_obj__schedules__teacher__user_id=user_id,
            class_obj__schedules__is_active=True,
            class_obj__schedules__deleted_at__isnull=True,
            class_obj__schedules__valid_from__lte=today,
        ) & (
            Q(class_obj__schedules__valid_until__isnull=True)
            | Q(class_obj__schedules__valid_until__gte=today)
        )
        return Enrollment.objects.filter(
            Q(class_obj__class_teacher__user_id=user_id) | schedule_scope,
            student_id=student_id,
            status=Enrollment.Status.ACTIVE,
        ).exists()
