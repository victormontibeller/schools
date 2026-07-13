"""Configuração do Django Admin para frequência."""

from django.contrib import admin

from attendance.models import AttendanceEntry, AttendanceJustification, AttendanceRecord


class AttendanceEntryInline(admin.TabularInline):
    """Inline de presenças dentro do registro de chamada."""

    model = AttendanceEntry
    extra = 0
    readonly_fields = ["created_at", "updated_at"]


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    """Admin para registros de chamada."""

    list_display = ["class_obj", "subject", "teacher", "date", "lesson_number"]
    list_filter = ["date", "class_obj", "subject"]
    search_fields = ["class_obj__name", "lesson_content", "notes"]
    date_hierarchy = "date"
    inlines = [AttendanceEntryInline]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(AttendanceEntry)
class AttendanceEntryAdmin(admin.ModelAdmin):
    """Admin para presenças individuais."""

    list_display = ["student", "record", "status"]
    list_filter = ["status", "record__class_obj"]
    search_fields = ["student__first_name", "student__last_name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(AttendanceJustification)
class AttendanceJustificationAdmin(admin.ModelAdmin):
    """Admin para justificativas de ausência."""

    list_display = ["student", "start_date", "end_date", "status", "approved_by", "approved_at"]
    list_filter = ["status", "start_date"]
    search_fields = ["student__first_name", "student__last_name", "reason"]
    readonly_fields = ["created_at", "updated_at", "approved_at"]
