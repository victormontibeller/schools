from django.contrib import admin

from students.models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = [
        "enrollment_number",
        "first_name",
        "last_name",
        "birth_date",
        "gender",
        "created_at",
    ]
    list_filter = ["gender", "blood_type"]
    search_fields = ["first_name", "last_name", "enrollment_number"]
    readonly_fields = ["created_at", "updated_at", "deleted_at"]
    ordering = ["first_name", "last_name"]
