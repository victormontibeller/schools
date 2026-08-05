"""Configuração do Django Admin para turmas."""

from django.contrib import admin

from classes.models import Class, Enrollment


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    """Admin para turmas — listagem e filtros por ano/turno."""

    list_display = [
        "name",
        "grade",
        "education_stage",
        "shift",
        "academic_year",
        "max_students",
        "class_teacher",
    ]
    list_filter = ["academic_year", "education_stage", "shift"]
    search_fields = ["name", "grade"]
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    """Admin para matrículas — estado por situação."""

    list_display = ["student", "class_obj", "academic_year", "enrollment_date", "status"]
    list_filter = ["status", "academic_year", "enrollment_date"]
    search_fields = ["student__first_name", "student__last_name"]
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
