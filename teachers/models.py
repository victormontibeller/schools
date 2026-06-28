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
