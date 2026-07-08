from django.contrib import admin

from enrollments.models import EnrollmentApplication, StudentDocument


@admin.register(EnrollmentApplication)
class EnrollmentApplicationAdmin(admin.ModelAdmin):
    list_display = [
        "application_number",
        "student",
        "class_obj",
        "academic_year",
        "application_type",
        "status",
        "created_at",
    ]
    list_filter = ["status", "application_type", "academic_year"]
    search_fields = [
        "application_number",
        "student__first_name",
        "student__last_name",
        "student__enrollment_number",
    ]
    raw_id_fields = ["student", "class_obj", "enrollment", "reviewed_by"]


@admin.register(StudentDocument)
class StudentDocumentAdmin(admin.ModelAdmin):
    list_display = ["student", "document_type", "status", "verified_at"]
    list_filter = ["status", "document_type"]
    search_fields = ["student__first_name", "student__last_name", "description"]
    raw_id_fields = ["student", "application", "verified_by"]
