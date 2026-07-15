"""
Modelos tenant-specific: BusinessUnit, Role e CustomUser.

AUTH_USER_MODEL     = "core.CustomUser"
School e Domain vivem no app compartilhado `tenancy`.
"""

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from base.media import (
    business_unit_logo_path,
    get_private_storage,
    get_public_storage,
    user_avatar_path,
)
from base.models import BaseModel
from base.upload_validators import validate_image_upload
from core.managers import UserManager


class BusinessUnit(BaseModel):
    """Unidade de negocio pertencente ao tenant ativo."""

    name = models.CharField(max_length=200, verbose_name="Nome da Empresa")
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
    logo = models.ImageField(
        upload_to=business_unit_logo_path,
        storage=get_public_storage,
        null=True,
        blank=True,
        validators=[validate_image_upload],
    )
    academic_year_start = models.DateField(null=True, blank=True)
    academic_year_end = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["cnpj"]),
        ]

    def __str__(self) -> str:
        """Representação legível da unidade."""
        return self.name


class RegistrationSequence(BaseModel):
    """Contador anual, isolado pelo schema do tenant, para matrículas legíveis."""

    scope = models.CharField(max_length=20, verbose_name="Tipo")
    year = models.PositiveSmallIntegerField(verbose_name="Ano")
    current_value = models.PositiveIntegerField(default=0, verbose_name="Valor Atual")

    class Meta:
        verbose_name = "Sequência de Matrícula"
        verbose_name_plural = "Sequências de Matrícula"
        constraints = [
            models.UniqueConstraint(fields=["scope", "year"], name="uniq_reg_sequence_scope_year")
        ]
        indexes = [models.Index(fields=["scope", "year"])]

    def __str__(self) -> str:
        return f"{self.scope}-{self.year}: {self.current_value}"


# ── Acesso ─────────────────────────────────────────────────────────────────────


class Role(BaseModel):
    """Perfil de acesso da plataforma."""

    class Name(models.TextChoices):
        ADMIN = "ADMIN", "Administrador"
        SECRETARY = "SECRETARY", "Secretaria"
        COORDINATOR = "COORDINATOR", "Coordenador"
        TEACHER = "TEACHER", "Professor"
        FINANCE = "FINANCE", "Financeiro"
        GUARDIAN = "GUARDIAN", "Responsável"

    name = models.CharField(max_length=20, choices=Name.choices, unique=True)

    class Meta:
        verbose_name = "Perfil de Acesso"
        verbose_name_plural = "Perfis de Acesso"
        ordering = ["name"]

    def __str__(self) -> str:
        """Representação legível do perfil de acesso."""
        return self.get_name_display()


class RoleModuleAccess(BaseModel):
    """Permissões de um papel para um módulo funcional do tenant."""

    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,  # Papéis fixos não podem perder sua política por cascata.
        related_name="module_accesses",
    )
    module_key = models.CharField(max_length=50)
    can_view = models.BooleanField(default=False)
    can_create = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_deactivate = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Acesso de Módulo"
        verbose_name_plural = "Acessos de Módulo"
        ordering = ["role__name", "module_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["role", "module_key"],
                name="uniq_role_module_access",
            )
        ]
        indexes = [models.Index(fields=["role", "module_key"])]

    def __str__(self) -> str:
        """Representa o vínculo sem expor dados pessoais."""
        return f"{self.role.name}:{self.module_key}"


# ── Usuário ────────────────────────────────────────────────────────────────────


class CustomUser(AbstractBaseUser, PermissionsMixin, BaseModel):
    """Usuário da plataforma — e-mail como identificador único."""

    class AccessMode(models.TextChoices):
        STANDARD = "STANDARD", "Padrão"
        DEMO = "DEMO", "Demonstração"

    email = models.EmailField(unique=True, verbose_name="E-mail")
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True, default="")
    avatar = models.ImageField(
        upload_to=user_avatar_path,
        storage=get_private_storage,
        null=True,
        blank=True,
        validators=[validate_image_upload],
    )
    role = models.ForeignKey(
        Role,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
    )
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    access_mode = models.CharField(
        max_length=20,
        choices=AccessMode.choices,
        default=AccessMode.STANDARD,
        db_index=True,
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

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

    @property
    def is_expired(self) -> bool:
        """Indica se a conta temporária já expirou."""
        return bool(self.expires_at and self.expires_at <= timezone.now())
