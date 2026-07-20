"""Admin da Agenda escolar."""

from django.contrib import admin

from student_diary.models import DailyDiary, DiaryAnswer, DiaryCategory, DiaryOption


@admin.register(DiaryCategory)
class DiaryCategoryAdmin(admin.ModelAdmin):
    """Administra categorias da agenda."""

    list_display = ["name", "section", "display_order", "is_enabled", "is_active"]


@admin.register(DiaryOption)
class DiaryOptionAdmin(admin.ModelAdmin):
    """Administra opções de categoria."""

    list_display = ["label", "category", "display_order", "is_active"]


@admin.register(DailyDiary)
class DailyDiaryAdmin(admin.ModelAdmin):
    """Consulta registros diários infantis."""

    list_display = ["student", "class_obj", "date", "teacher"]
    list_filter = ["date", "class_obj"]


admin.site.register(DiaryAnswer)
