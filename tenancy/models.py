"""Modelos compartilhados: School, Domain e SupportAccessGrant."""

import sys
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from base.models import BaseModel
from base.upload_validators import validate_image_upload

_IN_PYTEST = "pytest" in sys.modules
_TEST_PG = _IN_PYTEST and __import__("os").environ.get("DJANGO_ENV") == "test_pg"
_TESTING = _IN_PYTEST and not _TEST_PG

if _TESTING:

    class TenantMixin(models.Model):
        """Substituto SQLite do mixin de tenant."""

        schema_name = models.CharField(max_length=63, unique=True, default="public")

        class Meta:
            abstract = True

    class DomainMixin(models.Model):
        """Substituto SQLite do mixin de domínio."""

        domain = models.CharField(max_length=253, unique=True, db_index=True)
        tenant = models.ForeignKey(
            "tenancy.School",
            on_delete=models.CASCADE,
            related_name="domains",
        )
        is_primary = models.BooleanField(default=False)

        class Meta:
            abstract = True

else:
    from django_tenants.models import DomainMixin, TenantMixin  # type: ignore[assignment]


class School(TenantMixin, BaseModel):
    """Tenant raiz — uma escola por schema PostgreSQL."""

    name = models.CharField(max_length=200, verbose_name="Nome da Escola")
    cnpj = models.CharField(max_length=18, unique=True, null=True, blank=True)
    legal_name = models.CharField(
        max_length=255, blank=True, default="", verbose_name="Razao Social"
    )
    trade_name = models.CharField(
        max_length=255, blank=True, default="", verbose_name="Nome Fantasia"
    )
    state_registration = models.CharField(
        max_length=20, blank=True, default="", verbose_name="Inscricao Estadual"
    )
    municipal_registration = models.CharField(
        max_length=20, blank=True, default="", verbose_name="Inscricao Municipal"
    )
    phone = models.CharField(max_length=20, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    contact_full_name = models.CharField(
        max_length=255, blank=True, default="", verbose_name="Nome do Responsavel"
    )
    contact_role = models.CharField(
        max_length=150, blank=True, default="", verbose_name="Cargo do Responsavel"
    )
    contact_phone = models.CharField(
        max_length=20, blank=True, default="", verbose_name="Telefone do Responsavel"
    )
    contact_email = models.EmailField(blank=True, default="", verbose_name="E-mail do Responsavel")
    address = models.JSONField(default=dict, blank=True)
    logo = models.ImageField(
        upload_to="schools/logos/",
        null=True,
        blank=True,
        validators=[validate_image_upload],
    )
    settings = models.JSONField(default=dict, blank=True)
    academic_year_start = models.DateField(null=True, blank=True)
    academic_year_end = models.DateField(null=True, blank=True)

    auto_create_schema = True

    class Meta:
        verbose_name = "Escola"
        verbose_name_plural = "Escolas"
        ordering = ["name"]

    def __str__(self) -> str:
        """Retorna o nome da escola ou do schema."""
        return self.name or self.schema_name


class Domain(DomainMixin):
    """Domínio HTTP associado a uma escola.

    DomainMixin é a exceção técnica à BaseModel: django-tenants exige sua PK e
    contrato próprios para resolver o tenant antes de qualquer autenticação.
    """

    class Meta:
        verbose_name = "Domínio"
        verbose_name_plural = "Domínios"


def default_support_expiry():
    """Retorna a expiração padrão de uma concessão de suporte."""
    return timezone.now() + timedelta(minutes=30)


class SupportAccessGrant(BaseModel):
    """Concessão pública, temporária e de uso único para acessar um tenant."""

    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,  # preserva autoria da concessão
        related_name="support_access_grants",
    )
    tenant = models.ForeignKey(
        School,
        on_delete=models.PROTECT,  # histórico não pode perder o tenant
        related_name="support_access_grants",
    )
    reason = models.CharField(max_length=500)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    expires_at = models.DateTimeField(default=default_support_expiry, db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Concessão de Acesso"
        verbose_name_plural = "Concessões de Acesso"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "expires_at"])]
        permissions = [("access_tenant", "Pode acessar tenant para suporte")]

    def __str__(self) -> str:
        """Retorna uma identificação não sensível da concessão."""
        return f"SupportAccessGrant({self.pk}, {self.tenant.schema_name})"
