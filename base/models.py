"""BaseModel: classe base abstrata para todos os modelos de domínio."""

import uuid

from django.conf import settings
from django.db import models


class ActiveManager(models.Manager):
    """Retorna apenas registros ativos e não deletados por padrão."""

    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().filter(is_active=True, deleted_at__isnull=True)


class BaseModel(models.Model):
    """
    Classe base abstrata que TODOS os modelos de domínio devem herdar.

    Provê: UUID PK, timestamps, soft-delete com `deleted_by`, flag `is_active`,
    restore e versionamento otimista.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_updated",
    )

    is_active = models.BooleanField(default=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_deleted",
    )
    version = models.PositiveIntegerField(default=0)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    @property
    def is_deleted(self) -> bool:
        """Indica se o registro sofreu exclusão lógica."""
        return self.deleted_at is not None

    def soft_delete(self, user=None) -> None:
        """Aplica exclusão lógica registrando timestamp e executor."""
        from django.utils import timezone

        self.deleted_at = timezone.now()
        self.is_active = False
        if user is not None:
            self.updated_by = user
            self.deleted_by = user
        self.save(
            update_fields=["deleted_at", "is_active", "updated_by", "deleted_by", "updated_at"]
        )

    def restore(self, user=None) -> None:
        """Reverte a exclusão lógica reativando o registro."""
        self.deleted_at = None
        self.deleted_by = None
        self.is_active = True
        if user is not None:
            self.updated_by = user
        self.save(
            update_fields=["deleted_at", "is_active", "updated_by", "deleted_by", "updated_at"]
        )
