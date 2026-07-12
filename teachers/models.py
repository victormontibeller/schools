"""Modelos do módulo de professores."""

from django.conf import settings
from django.db import models

from base.models import BaseModel


class Subject(BaseModel):
    """Disciplina ministrada na escola."""

    name = models.CharField(max_length=100, verbose_name="Nome")
    code = models.CharField(max_length=20, unique=True, verbose_name="Código")
    workload = models.PositiveSmallIntegerField(default=0, verbose_name="Carga Horária (h/ano)")

    class Meta:
        ordering = ["name"]
        verbose_name = "Disciplina"
        verbose_name_plural = "Disciplinas"

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class Teacher(BaseModel):
    """Professor vinculado a um usuário do sistema."""

    class Gender(models.TextChoices):
        MALE = "M", "Masculino"
        FEMALE = "F", "Feminino"
        NON_BINARY = "NB", "Não Binário"
        NOT_INFORMED = "NI", "Prefiro não informar"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_profile",
        verbose_name="Usuário",
    )
    registration_number = models.CharField(max_length=30, unique=True, verbose_name="Matrícula")
    hire_date = models.DateField(null=True, blank=True, verbose_name="Data de Admissão")
    subjects = models.ManyToManyField(
        Subject, blank=True, related_name="teachers", verbose_name="Disciplinas"
    )
    birth_date = models.DateField(null=True, blank=True, verbose_name="Data de Nascimento")
    gender = models.CharField(
        max_length=2, choices=Gender.choices, default=Gender.NOT_INFORMED, verbose_name="Gênero"
    )
    nationality = models.CharField(
        max_length=100, blank=True, default="Brasileiro(a)", verbose_name="Nacionalidade"
    )
    cpf = models.CharField(
        max_length=14, blank=True, null=True, unique=True, default=None, verbose_name="CPF"
    )
    rg_number = models.CharField(max_length=20, blank=True, default="", verbose_name="RG — Número")
    rg_issuer = models.CharField(
        max_length=50, blank=True, default="", verbose_name="RG — Órgão Emissor"
    )
    rg_state = models.CharField(max_length=2, blank=True, default="", verbose_name="RG — UF")
    phone_mobile = models.CharField(max_length=20, blank=True, default="", verbose_name="Celular")
    accepts_email_notifications = models.BooleanField(
        default=False, verbose_name="Aceita notificações por e-mail"
    )
    accepts_whatsapp_notifications = models.BooleanField(
        default=False, verbose_name="Aceita notificações por WhatsApp"
    )

    class Meta:
        ordering = ["user__first_name", "user__last_name"]
        verbose_name = "Professor"
        verbose_name_plural = "Professores"

    def __str__(self) -> str:
        return str(self.user)

    @property
    def full_name(self) -> str:
        return self.user.get_full_name()

    @property
    def email(self) -> str:
        return self.user.email
