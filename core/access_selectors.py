"""Consultas read-only de propriedade usadas pelas políticas de acesso."""

from django.db.models import Q


class ObjectAccessSelector:
    """Verifica vínculos entre o usuário e objetos do domínio."""

    @staticmethod
    def guardian_can_access_student(user_id, student_id) -> bool:
        """Confirma vínculo ativo entre responsável e aluno."""
        from guardians.models import StudentGuardian

        return StudentGuardian.objects.filter(
            guardian__user_id=user_id,
            student_id=student_id,
        ).exists()

    @staticmethod
    def guardian_can_access_activity(user_id, activity_id) -> bool:
        """Confirma que a atividade pertence a turma de aluno vinculado."""
        from activities.models import Activity

        return Activity.objects.filter(
            pk=activity_id,
            class_obj__enrollments__student__guardians__guardian__user_id=user_id,
        ).exists()

    @staticmethod
    def teacher_can_access_class(user_id, class_id) -> bool:
        """Confirma responsabilidade ou horário do professor na turma."""
        from classes.models import Class

        return (
            Class.objects.filter(pk=class_id)
            .filter(Q(class_teacher__user_id=user_id) | Q(schedules__teacher__user_id=user_id))
            .exists()
        )

    @staticmethod
    def teacher_can_access_activity(user_id, activity_id) -> bool:
        """Confirma autoria da atividade pelo professor."""
        from activities.models import Activity

        return Activity.objects.filter(pk=activity_id, teacher__user_id=user_id).exists()

    @staticmethod
    def teacher_can_access_attendance(user_id, record_id) -> bool:
        """Confirma que a chamada pertence ao professor."""
        from attendance.models import AttendanceRecord

        return AttendanceRecord.objects.filter(pk=record_id, teacher__user_id=user_id).exists()

    @staticmethod
    def teacher_can_access_student(user_id, student_id) -> bool:
        """Confirma matrícula do aluno em turma do professor."""
        from django.db.models import Q

        from classes.models import Enrollment

        return Enrollment.objects.filter(
            Q(class_obj__class_teacher__user_id=user_id)
            | Q(class_obj__schedules__teacher__user_id=user_id),
            student_id=student_id,
        ).exists()
