"""Admin de suporte ao workflow de matrículas."""

from django.contrib import admin

from enrollments.models import (
    DocumentRequirement,
    EnrollmentApplication,
    EnrollmentReminder,
    EnrollmentTransition,
    StudentDocument,
)


class ReadOnlyWorkflowAdmin(admin.ModelAdmin):
    """Impede que o admin contorne os comandos auditados do workflow."""

    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EnrollmentApplication)
class EnrollmentApplicationAdmin(ReadOnlyWorkflowAdmin):
    list_display = [
        "application_number",
        "student",
        "target_class",
        "academic_year",
        "application_type",
        "status",
    ]
    list_filter = ["status", "application_type", "academic_year"]
    search_fields = ["application_number", "student__enrollment_number"]
    raw_id_fields = [
        "student",
        "target_class",
        "source_enrollment",
        "result_enrollment",
        "reviewed_by",
    ]


@admin.register(DocumentRequirement)
class DocumentRequirementAdmin(ReadOnlyWorkflowAdmin):
    list_display = ["label", "application_type", "is_required", "allows_physical"]
    list_filter = ["application_type", "is_required", "allows_physical"]


@admin.register(StudentDocument)
class StudentDocumentAdmin(ReadOnlyWorkflowAdmin):
    list_display = ["requirement_label", "application", "status", "verified_at"]
    list_filter = ["status", "is_required"]
    raw_id_fields = ["application", "requirement", "verified_by"]


@admin.register(EnrollmentTransition)
class EnrollmentTransitionAdmin(ReadOnlyWorkflowAdmin):
    """Expõe o histórico somente para leitura, preservando seu caráter imutável."""

    list_display = ["application", "from_status", "to_status", "actor", "created_at"]
    readonly_fields = [
        "application",
        "from_status",
        "to_status",
        "actor",
        "reason",
        "created_at",
        "updated_at",
    ]


@admin.register(EnrollmentReminder)
class EnrollmentReminderAdmin(ReadOnlyWorkflowAdmin):
    list_display = ["application", "recipient", "status", "sent_at"]
