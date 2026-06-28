"""Modelos do módulo de alunos."""

from django.conf import settings
from django.db import models

from base.models import BaseModel


class Student(BaseModel):
    """Aluno da escola — pode ou não ter acesso ao sistema."""

    class Gender(models.TextChoices):
        MALE = "M", "Masculino"
        FEMALE = "F", "Feminino"
        NON_BINARY = "NB", "Não Binário"
        NOT_INFORMED = "NI", "Prefiro não informar"

    class BloodType(models.TextChoices):
        A_POS = "A+", "A+"
        A_NEG = "A-", "A-"
        B_POS = "B+", "B+"
        B_NEG = "B-", "B-"
        AB_POS = "AB+", "AB+"
        AB_NEG = "AB-", "AB-"
        O_POS = "O+", "O+"
        O_NEG = "O-", "O-"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="student_profile",
        verbose_name="Usuário do Sistema",
    )
    enrollment_number = models.CharField(max_length=30, unique=True, verbose_name="Matrícula")
    first_name = models.CharField(max_length=150, verbose_name="Nome")
    last_name = models.CharField(max_length=150, verbose_name="Sobrenome")
    birth_date = models.DateField(verbose_name="Data de Nascimento")
    gender = models.CharField(
        max_length=2, choices=Gender.choices, default=Gender.NOT_INFORMED, verbose_name="Gênero"
    )
    blood_type = models.CharField(
        max_length=3,
        choices=BloodType.choices,
        blank=True,
        default="",
        verbose_name="Tipo Sanguíneo",
    )
    special_needs = models.JSONField(
        default=dict, blank=True, verbose_name="Necessidades Especiais"
    )
    photo = models.ImageField(
        upload_to="students/photos/", null=True, blank=True, verbose_name="Foto"
    )

    class Meta:
        ordering = ["first_name", "last_name"]
        verbose_name = "Aluno"
        verbose_name_plural = "Alunos"

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} ({self.enrollment_number})"

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()
