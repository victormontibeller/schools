from django.contrib import admin

from audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "operation", "model_name", "object_id", "user", "tenant_schema"]
    list_filter = ["operation", "model_name"]
    search_fields = ["model_name", "object_id", "correlation_id"]
    readonly_fields = [f.name for f in AuditLog._meta.get_fields() if hasattr(f, "name")]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
