"""Configuração do Django Admin para calendário acadêmico."""

from django.contrib import admin

from academic_calendar.models import AcademicYear, CalendarEvent, Holiday


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    """Admin para anos letivos — listagem por início."""

    list_display = ["name", "start_date", "end_date", "status"]
    list_filter = ["status"]
    search_fields = ["name"]
    ordering = ["-start_date"]


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    """Admin para feriados — filtros por tipo e recorrência."""

    list_display = ["name", "date", "type", "is_recurring"]
    list_filter = ["type", "is_recurring"]
    search_fields = ["name"]
    ordering = ["date"]


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    """Admin para eventos — filtros por tipo, público e ano letivo."""

    list_display = [
        "title",
        "start_date",
        "end_date",
        "type",
        "audience",
        "is_public",
        "is_cancelled",
    ]
    list_filter = ["type", "audience", "is_public", "is_cancelled", "academic_year"]
    search_fields = ["title", "description"]
    date_hierarchy = "start_date"
