"""
Modelos centrais: School (tenant), Domain, Role, CustomUser.

AUTH_USER_MODEL     = "core.CustomUser"
TENANT_MODEL        = "core.School"
TENANT_DOMAIN_MODEL = "core.Domain"
"""

import sys

from django.contrib.auth.models import AbstractBaseUser, Permission, PermissionsMixin
from django.db import models

from base.models import BaseModel
from core.managers import UserManager

# ── Mixins condicionais para django-tenants ───────────────────────────────────
# Em perfil TESTING (SQLite, sem django_tenants — ADR-0001) usamos mixins vazios.
# Em TEST_PG/dev/prod importamos os mixins reais do django_tenants.
_IN_PYTEST = "pytest" in sys.modules
_TEST_PG = _IN_PYTEST and __import__("os").environ.get("DJANGO_ENV") == "test_pg"
_TESTING = _IN_PYTEST and not _TEST_PG
if _TESTING:

    class TenantMixin(models.Model):
        schema_name = models.CharField(max_length=63, unique=True, default="public")

        class Meta:
            abstract = True

    class DomainMixin(models.Model):
        domain = models.CharField(max_length=253)
        is_primary = models.BooleanField(default=False)

        class Meta:
            abstract = True

else:
    from django_tenants.models import DomainMixin, TenantMixin  # type: ignore[assignment]


# ── Tenant ─────────────────────────────────────────────────────────────────────


class School(TenantMixin, BaseModel):
    """Tenant raiz — uma escola por schema PostgreSQL."""

    name = models.CharField(max_length=200, verbose_name="Nome da Escola")
    cnpj = models.CharField(max_length=18, unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    address = models.JSONField(default=dict, blank=True)
    logo = models.ImageField(upload_to="schools/logos/", null=True, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    academic_year_start = models.DateField(null=True, blank=True)
    academic_year_end = models.DateField(null=True, blank=True)

    auto_create_schema = True

    class Meta:
        verbose_name = "Escola"
        verbose_name_plural = "Escolas"
        ordering = ["name"]

    def __str__(self) -> str:
        """Representação legível da escola."""
        return self.name or self.schema_name


class Domain(DomainMixin):
    """Domínio HTTP associado a uma escola."""

    class Meta:
        verbose_name = "Domínio"
        verbose_name_plural = "Domínios"


# ── Acesso ─────────────────────────────────────────────────────────────────────


class Role(BaseModel):
    """Perfil de acesso da plataforma."""

    class Name(models.TextChoices):
        ADMIN = "ADMIN", "Administrador"
        COORDINATOR = "COORDINATOR", "Coordenador"
        TEACHER = "TEACHER", "Professor"
        GUARDIAN = "GUARDIAN", "Responsável"

    name = models.CharField(max_length=20, choices=Name.choices, unique=True)
    permissions = models.ManyToManyField(Permission, blank=True)

    class Meta:
        verbose_name = "Perfil de Acesso"
        verbose_name_plural = "Perfis de Acesso"
        ordering = ["name"]

    def __str__(self) -> str:
        """Representação legível do perfil de acesso."""
        return self.get_name_display()


# ── Usuário ────────────────────────────────────────────────────────────────────


class CustomUser(AbstractBaseUser, PermissionsMixin, BaseModel):
    """Usuário da plataforma — e-mail como identificador único."""

    email = models.EmailField(unique=True, verbose_name="E-mail")
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True, default="")
    avatar = models.ImageField(upload_to="accounts/avatars/", null=True, blank=True)
    role = models.ForeignKey(
        Role,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
    )
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"
        ordering = ["first_name", "last_name"]

    def __str__(self) -> str:
        """Representação legível do usuário com nome e e-mail."""
        return f"{self.get_full_name()} <{self.email}>"

    def get_full_name(self) -> str:
        """Retorna nome e sobrenome concatenados."""
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self) -> str:
        """Retorna apenas o primeiro nome do usuário."""
        return self.first_name
