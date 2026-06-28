from django.contrib import admin

from teachers.models import Subject, Teacher


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "workload"]
    search_fields = ["name", "code"]
    ordering = ["code"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ["full_name", "email", "registration_number", "hire_date", "created_at"]
    search_fields = ["user__first_name", "user__last_name", "user__email", "registration_number"]
    filter_horizontal = ["subjects"]
    readonly_fields = ["created_at", "updated_at", "deleted_at"]
