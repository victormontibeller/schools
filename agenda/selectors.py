"""ScheduleSelector: consultas de grade horária."""

from base.selectors import BaseSelector


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

    def list_time_slots(self, filters=None, page=1, page_size=50):
        """Lista horários paginados, com filtros opcionais."""
        return self.list(filters=filters, page=page, page_size=page_size)
