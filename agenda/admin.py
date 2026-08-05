"""Configuração do Django Admin para grade horária."""

from django.contrib import admin

from agenda.models import Schedule, TimeSlot


class _ReadOnlyDomainAdmin(admin.ModelAdmin):
    """Mantém consulta no Admin sem contornar os services auditáveis."""

    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TimeSlot)
class TimeSlotAdmin(_ReadOnlyDomainAdmin):
    """Admin para períodos por turno — listagem cronológica."""

    list_display = ["slot_number", "shift", "start_time", "end_time"]
    ordering = ["start_time", "end_time", "slot_number"]


@admin.register(Schedule)
class ScheduleAdmin(_ReadOnlyDomainAdmin):
    """Admin para itens da grade — filtros por turma/professor/disciplina."""

    list_display = [
        "class_obj",
        "teacher",
        "subject",
        "room",
        "time_slot",
        "day_of_week",
        "valid_from",
        "valid_until",
    ]
    list_filter = ["valid_from", "class_obj", "teacher"]
    search_fields = ["class_obj__name", "teacher__user__first_name"]
