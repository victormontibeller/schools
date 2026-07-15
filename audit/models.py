"""AuditLog: registro imutável de todas as mutações de domínio.

NÃO estende BaseModel — evita recursão infinita no sistema de auditoria.
"""

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    class Operation(models.TextChoices):
        INSERT = "INSERT", "Inserção"
        UPDATE = "UPDATE", "Atualização"
        DELETE = "DELETE", "Exclusão"
        RESTORE = "RESTORE", "Restauração"

    tenant_schema = models.CharField(max_length=63, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    model_name = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=100, db_index=True)
    operation = models.CharField(max_length=10, choices=Operation.choices, db_index=True)
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    correlation_id = models.CharField(max_length=36, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Registro de Auditoria"
        verbose_name_plural = "Registros de Auditoria"
        indexes = [
            models.Index(fields=["model_name", "object_id"]),
            models.Index(fields=["tenant_schema", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"[{self.operation}] {self.model_name}#{self.object_id}"
