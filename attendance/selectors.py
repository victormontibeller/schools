"""AttendanceSelector: consultas somente-leitura de frequência."""

from django.db.models import Count, Q

from base.selectors import BaseSelector, PageResult


class AttendanceSelector(BaseSelector):
    """Selector para registros de chamada e resumos de frequência."""

    @property
    def model_class(self):
        from attendance.models import AttendanceRecord

        return AttendanceRecord

    def list_records(
        self,
        class_id=None,
        teacher_id=None,
        date_from=None,
        date_to=None,
        search="",
        order_by="-date",
        page=1,
        page_size=20,
    ):
        """Lista chamadas com filtros, busca, ordenação e paginação."""
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
        if search:
            qs = qs.filter(
                Q(class_obj__name__icontains=search)
                | Q(subject__name__icontains=search)
                | Q(teacher__user__first_name__icontains=search)
                | Q(teacher__user__last_name__icontains=search)
            )
        total = qs.count()
        page = max(1, page)
        offset = (page - 1) * page_size
        return PageResult(
            items=list(qs.order_by(order_by)[offset : offset + page_size]),
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_class_attendance_summary(self, class_id, *, student_ids=None):
        """Resumo por aluno da turma: presenças, ausências, justificadas, %."""
        return self.get_classes_attendance_summary([class_id], student_ids=student_ids).get(
            class_id, {"summary": [], "at_risk": []}
        )

    def get_classes_attendance_summary(self, class_ids, *, student_ids=None) -> dict:
        """Agrega todas as turmas em duas consultas, independentemente dos alunos."""
        from attendance.models import AttendanceEntry
        from classes.contracts import Enrollment

        active = Enrollment.objects.filter(
            class_obj_id__in=class_ids,
            status=Enrollment.Status.ACTIVE,
            is_active=True,
        ).select_related("student")
        entries = AttendanceEntry.objects.filter(record__class_obj_id__in=class_ids)
        if student_ids is not None:
            active = active.filter(student_id__in=student_ids)
            entries = entries.filter(student_id__in=student_ids)
        counts = {
            (row["record__class_obj_id"], row["student_id"]): row
            for row in entries.order_by()
            .values("record__class_obj_id", "student_id")
            .annotate(
                total=Count("pk"),
                present=Count("pk", filter=Q(status=AttendanceEntry.Status.PRESENT)),
                absent=Count("pk", filter=Q(status=AttendanceEntry.Status.ABSENT)),
                justified=Count("pk", filter=Q(status=AttendanceEntry.Status.JUSTIFIED)),
            )
        }
        result = {}
        for enrollment in active:
            count = counts.get((enrollment.class_obj_id, enrollment.student_id), {})
            total = count.get("total", 0)
            present, absent, justified = (
                count.get(key, 0) for key in ("present", "absent", "justified")
            )
            rate = round((present + justified) * 100 / total, 2) if total else None
            item = {
                "student": enrollment.student,
                "present": present,
                "absent": absent,
                "justified": justified,
                "rate": rate,
            }
            group = result.setdefault(enrollment.class_obj_id, {"summary": [], "at_risk": []})
            group["summary"].append(item)
            if rate is not None and rate < 75:
                group["at_risk"].append(item)
        for group in result.values():
            group["at_risk"].sort(key=lambda item: item["rate"])
        return result

    def get_student_attendance(self, student_id, class_id=None):
        """Histórico de presença de um aluno (opcionalmente filtrado por turma)."""
        from attendance.models import AttendanceEntry

        qs = AttendanceEntry.objects.filter(student_id=student_id).select_related(
            "record__class_obj", "record__subject", "record__teacher"
        )
        if class_id:
            qs = qs.filter(record__class_obj_id=class_id)
        return qs.order_by("-record__date", "-record__lesson_number")

    def get_students_at_risk(self, class_id, threshold: float = 75.0, *, student_ids=None):
        """Lista alunos com frequência abaixo do limite (default 75%)."""
        summary = self.get_class_attendance_summary(class_id, student_ids=student_ids)
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

    def list_justifications(
        self,
        status=None,
        search="",
        order_by="-start_date",
        page=1,
        page_size=20,
    ):
        """Lista justificativas com filtro de situação, busca e paginação."""
        from attendance.models import AttendanceJustification

        qs = AttendanceJustification.objects.select_related("student", "approved_by")
        if status:
            qs = qs.filter(status=status)
        if search:
            qs = qs.filter(
                Q(student__first_name__icontains=search)
                | Q(student__last_name__icontains=search)
                | Q(reason__icontains=search)
            )
        total = qs.count()
        page = max(1, page)
        offset = (page - 1) * page_size
        return PageResult(
            items=list(qs.order_by(order_by)[offset : offset + page_size]),
            total=total,
            page=page,
            page_size=page_size,
        )
