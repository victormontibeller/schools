"""ScheduleSelector: consultas de grade horária."""

from django.db.models import Q

from base.selectors import BaseSelector, PageResult


class ScheduleSelector(BaseSelector):
    """Selector para a entidade Schedule — grade semanal e por professor."""

    @property
    def model_class(self):
        from agenda.models import Schedule

        return Schedule

    def get_weekly_schedule(self, class_id):
        """Retorna todos os itens ativos da grade de uma turma, ordenados por dia/hora."""
        from agenda.models import Schedule

        return (
            Schedule.objects.filter(class_obj_id=class_id, is_active=True)
            .select_related("teacher", "subject", "room", "time_slot")
            .order_by("time_slot__day_of_week", "time_slot__start_time")
        )

    @staticmethod
    def group_by_day_of_week(schedules) -> dict[str, list]:
        """Agrupa itens de grade por dia da semana (MON..SUN)."""
        from agenda.models import TimeSlot

        days = [d[0] for d in TimeSlot.Day.choices]
        by_day: dict[str, list] = {d: [] for d in days}
        for s in schedules:
            by_day[s.time_slot.day_of_week].append(s)
        return by_day

    def get_teacher_schedule(self, teacher_id):
        """Retorna itens ativos da grade atribuídos a um professor."""
        from agenda.models import Schedule

        return (
            Schedule.objects.filter(teacher_id=teacher_id, is_active=True)
            .select_related("class_obj", "subject", "room", "time_slot")
            .order_by("time_slot__day_of_week", "time_slot__start_time")
        )


class TimeSlotSelector(BaseSelector):
    """Selector para a entidade TimeSlot."""

    @property
    def model_class(self):
        from agenda.models import TimeSlot

        return TimeSlot

    def list_time_slots(self, search="", order_by="day_of_week", page=1, page_size=20):
        """Lista horários com busca, ordenação e paginação."""
        from agenda.models import TimeSlot

        queryset = TimeSlot.objects.all()
        if search:
            queryset = queryset.filter(
                Q(day_of_week__icontains=search)
                | Q(slot_number__icontains=search)
                | Q(start_time__icontains=search)
                | Q(end_time__icontains=search)
            )
        total = queryset.count()
        page = max(1, page)
        offset = (page - 1) * page_size
        return PageResult(
            items=list(queryset.order_by(order_by)[offset : offset + page_size]),
            total=total,
            page=page,
            page_size=page_size,
        )
