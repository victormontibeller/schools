"""Administração do catálogo público de tenants."""

from django.contrib import admin

from tenancy.models import Domain, School, SupportAccessGrant


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


@admin.register(SupportAccessGrant)
class SupportAccessGrantAdmin(admin.ModelAdmin):
    """Consulta imutável das concessões de suporte."""

    list_display = ["id", "tenant", "operator", "expires_at", "used_at", "ended_at"]
    list_filter = ["tenant", "expires_at"]
    readonly_fields = [field.name for field in SupportAccessGrant._meta.fields]

    def has_add_permission(self, request):
        """Concessões são criadas somente pelo service."""
        return False

    def has_change_permission(self, request, obj=None):
        """Concessões são imutáveis pelo admin."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Concessões nunca são removidas fisicamente."""
        return False
