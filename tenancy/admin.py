"""Administração do catálogo público de tenants."""

from django.contrib import admin

from tenancy.models import Domain, School


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    """Administração de escolas."""

    list_display = ["name", "schema_name", "email", "created_at"]
    search_fields = ["name", "schema_name", "cnpj"]
    readonly_fields = ["schema_name", "created_at", "updated_at"]


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    """Administração de domínios de tenant."""

    list_display = ["domain", "tenant", "is_primary"]
