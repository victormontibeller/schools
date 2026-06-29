"""Configuração do Django Admin para atividades."""

from django.contrib import admin

from activities.models import Activity, ActivitySubmission


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    """Admin para atividades — filtros por turma/tipo/professor."""

    list_display = ["title", "class_obj", "subject", "teacher", "type", "due_date", "max_score"]
    list_filter = ["type", "due_date", "class_obj"]
    search_fields = ["title", "class_obj__name", "teacher__user__first_name"]


@admin.register(ActivitySubmission)
class ActivitySubmissionAdmin(admin.ModelAdmin):
    """Admin para entregas — por aluno e nota."""

    list_display = ["activity", "student", "score", "submitted_at"]
    list_filter = ["activity__class_obj"]
    search_fields = ["student__first_name", "student__last_name"]
