"""AttendanceSelector: consultas somente-leitura de frequência."""

from base.selectors import BaseSelector


class AttendanceSelector(BaseSelector):
    """Selector para registros de chamada e resumos de frequência."""

    @property
    def model_class(self):
        from attendance.models import AttendanceRecord

        return AttendanceRecord

    def list_records(self, class_id=None, teacher_id=None, date_from=None, date_to=None):
        """Lista registros de chamada com filtros opcionais."""
        from attendance.models import AttendanceRecord

        qs = AttendanceRecord.objects.select_related("class_obj", "subject", "teacher")
        if class_id:
            qs = qs.filter(class_obj_id=class_id)
        if teacher_id:
            qs = qs.filter(teacher_id=teacher_id)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        return qs.order_by("-date", "-lesson_number")

    def get_class_attendance_summary(self, class_id):
        """Resumo por aluno da turma: presenças, ausências, justificadas, %."""
        from attendance.models import AttendanceEntry
        from classes.models import Enrollment

        active = Enrollment.objects.filter(
            class_obj_id=class_id, status=Enrollment.Status.ACTIVE
        ).select_related("student")

        summary: list[dict] = []
        at_risk: list[dict] = []
        for enr in active:
            entries = AttendanceEntry.objects.filter(
                record__class_obj_id=class_id, student=enr.student
            )
            total = entries.count()
            if total == 0:
                summary.append(
                    {
                        "student": enr.student,
                        "present": 0,
                        "absent": 0,
                        "justified": 0,
                        "rate": None,
                    }
                )
                continue
            present = entries.filter(status=AttendanceEntry.Status.PRESENT).count()
            absent = entries.filter(status=AttendanceEntry.Status.ABSENT).count()
            justified = entries.filter(status=AttendanceEntry.Status.JUSTIFIED).count()
            rate = round(((present + justified) / total) * 100, 2)
            item = {
                "student": enr.student,
                "present": present,
                "absent": absent,
                "justified": justified,
                "rate": rate,
            }
            summary.append(item)
            if rate is not None and rate < 75:
                at_risk.append(item)
        at_risk.sort(key=lambda x: (x["rate"] is None, x["rate"]))
        return {"summary": summary, "at_risk": at_risk}

    def get_student_attendance(self, student_id, class_id=None):
        """Histórico de presença de um aluno (opcionalmente filtrado por turma)."""
        from attendance.models import AttendanceEntry

        qs = AttendanceEntry.objects.filter(student_id=student_id).select_related(
            "record__class_obj", "record__subject", "record__teacher"
        )
        if class_id:
            qs = qs.filter(record__class_obj_id=class_id)
        return qs.order_by("-record__date", "-record__lesson_number")

    def get_students_at_risk(self, class_id, threshold: float = 75.0):
        """Lista alunos com frequência abaixo do limite (default 75%)."""
        summary = self.get_class_attendance_summary(class_id)
        return [
            item
            for item in summary["summary"]
            if item["rate"] is not None and item["rate"] < threshold
        ]

    def get_teacher_attendance_history(self, teacher_id, date_from=None, date_to=None):
        """Chamadas lançadas por um professor em determinado intervalo."""
        return self.list_records(teacher_id=teacher_id, date_from=date_from, date_to=date_to)

    def get_record_with_entries(self, record_id):
        """Retorna registro de chamada com entradas de alunos ordenadas."""
        from attendance.models import AttendanceEntry, AttendanceRecord

        record = (
            AttendanceRecord.objects.select_related("class_obj", "subject")
            .filter(pk=record_id)
            .first()
        )
        if record is None:
            return None, None
        entries = (
            AttendanceEntry.objects.filter(record=record)
            .select_related("student")
            .order_by("student__first_name")
        )
        return record, entries

    def get_student_attendance_rate(self, student_id, class_id):
        """Retorna percentual de frequencia (0-100) ou None se sem dados."""
        from attendance.models import AttendanceEntry

        entries = AttendanceEntry.objects.filter(
            student_id=student_id, record__class_obj_id=class_id
        )
        total = entries.count()
        if total == 0:
            return None
        presences = entries.filter(
            status__in=[AttendanceEntry.Status.PRESENT, AttendanceEntry.Status.JUSTIFIED]
        ).count()
        return round((presences / total) * 100, 2)


class JustificationSelector(BaseSelector):
    """Selector para justificativas de ausência."""

    @property
    def model_class(self):
        from attendance.models import AttendanceJustification

        return AttendanceJustification

    def list_justifications(self, status=None):
        """Lista justificativas; opcionalmente filtra por situação."""
        from attendance.models import AttendanceJustification

        qs = AttendanceJustification.objects.select_related("student", "approved_by")
        if status:
            qs = qs.filter(status=status)
        return qs.order_by("-start_date")
