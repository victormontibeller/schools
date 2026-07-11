from django.contrib import admin

from guardians.models import Guardian, StudentGuardian


@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display = ["full_name", "phone", "phone_whatsapp", "created_at"]
    search_fields = ["first_name", "last_name", "email", "cpf", "phone"]
    readonly_fields = ["created_at", "updated_at", "deleted_at"]


@admin.register(StudentGuardian)
class StudentGuardianAdmin(admin.ModelAdmin):
    list_display = ["guardian", "student", "is_primary", "has_custody", "can_pickup"]
    list_filter = ["is_primary", "has_custody", "can_pickup"]
    readonly_fields = ["created_at", "updated_at"]
