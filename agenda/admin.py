"""Configuração do Django Admin para grade horária."""

from django.contrib import admin

from agenda.models import Schedule, TimeSlot


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    """Admin para horários — listagem por dia e slot_number."""

    list_display = ["day_of_week", "slot_number", "start_time", "end_time"]
    list_filter = ["day_of_week"]
    ordering = ["day_of_week", "slot_number"]


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    """Admin para itens da grade — filtros por turma/professor/disciplina."""

    list_display = [
        "class_obj",
        "teacher",
        "subject",
        "room",
        "time_slot",
        "valid_from",
        "valid_until",
    ]
    list_filter = ["valid_from", "class_obj", "teacher"]
    search_fields = ["class_obj__name", "teacher__user__first_name"]
