"""Consultas read-only de propriedade usadas pelas políticas de acesso."""

from django.db.models import Q


class ObjectAccessSelector:
    """Verifica vínculos entre o usuário e objetos do domínio."""

    @staticmethod
    def guardian_can_access_student(user_id, student_id) -> bool:
        """Confirma vínculo ativo entre responsável e aluno."""
        from guardians.contracts import StudentGuardian

        return StudentGuardian.objects.filter(
            guardian__user_id=user_id,
            guardian__is_active=True,
            student_id=student_id,
            has_custody=True,
        ).exists()

    @staticmethod
    def guardian_can_access_activity(user_id, activity_id) -> bool:
        """Confirma que a atividade pertence a turma de aluno vinculado."""
        from activities.contracts import Activity

        return Activity.objects.filter(
            pk=activity_id,
            class_obj__enrollments__student__guardians__guardian__user_id=user_id,
        ).exists()

    @staticmethod
    def teacher_can_access_class(user_id, class_id) -> bool:
        """Confirma responsabilidade ou horário do professor na turma."""
        from classes.contracts import Class

        return (
            Class.objects.filter(pk=class_id)
            .filter(Q(class_teacher__user_id=user_id) | Q(schedules__teacher__user_id=user_id))
            .exists()
        )

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
        """Confirma que a disciplina está atribuída ao professor."""
        from teachers.contracts import Subject

        return Subject.objects.filter(pk=subject_id, teachers__user_id=user_id).exists()

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

        return Enrollment.objects.filter(
            Q(class_obj__class_teacher__user_id=user_id)
            | Q(class_obj__schedules__teacher__user_id=user_id),
            student_id=student_id,
        ).exists()
