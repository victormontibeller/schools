"""BaseModel: classe base abstrata para todos os modelos de domínio."""

import uuid

from django.conf import settings
from django.db import models, router, transaction
from django.db.models import F
from django.utils import timezone


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

    def save(self, *args, **kwargs):
        """Incrementa a versão e recusa saves feitos sobre uma cópia obsoleta."""
        if self._state.adding:
            return super().save(*args, **kwargs)

        from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError

        expected_version = self.version
        database = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=database):
            try:
                current_version = (
                    type(self)
                    .all_objects.using(database)
                    .select_for_update()
                    .values_list("version", flat=True)
                    .get(pk=self.pk)
                )
            except type(self).DoesNotExist:
                raise ObjectNotFoundError(type(self).__name__, str(self.pk)) from None
            if current_version != expected_version:
                raise BusinessRuleViolationError(
                    "Este registro foi alterado por outra pessoa. "
                    "Recarregue os dados e tente novamente."
                )
            self.version = expected_version + 1
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {
                    "version",
                    "updated_at",
                }
            return super().save(*args, **kwargs)

    def soft_delete(self, user=None) -> None:
        """Aplica exclusão lógica registrando timestamp e executor."""
        from base.exceptions import BusinessRuleViolationError

        expected_version = self.version
        updates = {
            "deleted_at": timezone.now(),
            "is_active": False,
            "version": F("version") + 1,
            "updated_at": timezone.now(),
        }
        if user is not None:
            updates.update(updated_by=user, deleted_by=user)
        affected = (
            type(self)
            .all_objects.filter(
                pk=self.pk,
                version=expected_version,
            )
            .update(**updates)
        )
        if affected != 1:
            raise BusinessRuleViolationError(
                "Este registro foi alterado por outra pessoa. "
                "Recarregue os dados e tente novamente."
            )
        self.refresh_from_db()

    def restore(self, user=None) -> None:
        """Reverte a exclusão lógica reativando o registro."""
        from base.exceptions import BusinessRuleViolationError

        expected_version = self.version
        updates = {
            "deleted_at": None,
            "deleted_by": None,
            "is_active": True,
            "version": F("version") + 1,
            "updated_at": timezone.now(),
        }
        if user is not None:
            updates["updated_by"] = user
        affected = (
            type(self)
            .all_objects.filter(
                pk=self.pk,
                version=expected_version,
            )
            .update(**updates)
        )
        if affected != 1:
            raise BusinessRuleViolationError(
                "Este registro foi alterado por outra pessoa. "
                "Recarregue os dados e tente novamente."
            )
        self.refresh_from_db()
