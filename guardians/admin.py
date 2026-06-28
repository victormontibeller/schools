from django.contrib import admin

from guardians.models import Guardian, StudentGuardian


@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display = ["full_name", "relationship_type", "phone", "phone_whatsapp", "created_at"]
    list_filter = ["relationship_type"]
    search_fields = ["user__first_name", "user__last_name", "cpf", "phone"]
    readonly_fields = ["created_at", "updated_at", "deleted_at"]


@admin.register(StudentGuardian)
class StudentGuardianAdmin(admin.ModelAdmin):
    list_display = ["guardian", "student", "is_primary", "has_custody", "can_pickup"]
    list_filter = ["is_primary", "has_custody", "can_pickup"]
    readonly_fields = ["created_at", "updated_at"]
