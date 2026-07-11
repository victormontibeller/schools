"""Admin tenant-specific: BusinessUnit, Role e CustomUser."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from core.models import BusinessUnit, CustomUser, Role


@admin.register(BusinessUnit)
class BusinessUnitAdmin(admin.ModelAdmin):
    list_display = ["name", "cnpj", "email", "created_at"]
    search_fields = ["name", "cnpj", "trade_name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    filter_horizontal = ["permissions"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ["email", "first_name", "last_name", "role", "is_active", "is_staff"]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = ["email", "first_name", "last_name"]
    ordering = ["email"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Dados Pessoais", {"fields": ("first_name", "last_name", "phone", "avatar")}),
        (
            "Acesso",
            {"fields": ("role", "access_mode", "is_active", "is_staff", "is_superuser")},
        ),
        ("Permissões", {"fields": ("groups", "user_permissions")}),
        (
            "Datas",
            {
                "fields": (
                    "last_login",
                    "email_verified_at",
                    "expires_at",
                    "created_at",
                    "updated_at",
                    "deleted_at",
                )
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "password1", "password2"),
            },
        ),
    )
    readonly_fields = ["created_at", "updated_at", "deleted_at"]
