"""Modelos compartilhados do catálogo público de escolas."""

import sys

from django.db import models

from base.media import get_public_storage, school_logo_path
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
        upload_to=school_logo_path,
        storage=get_public_storage,
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

    def clean(self) -> None:
        """Normaliza e valida o host conforme o ambiente e o tenant."""
        from tenancy.domain_validation import normalize_domain

        self.domain = normalize_domain(
            self.domain,
            tenant_schema=getattr(self.tenant, "schema_name", None),
        )

    def save(self, *args, **kwargs):
        """Garante que nenhum caminho de escrita contorne a política de host."""
        self.clean()
        return super().save(*args, **kwargs)
