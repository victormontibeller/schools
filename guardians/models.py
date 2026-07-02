"""Modelos do módulo de responsáveis."""

from django.conf import settings
from django.db import models

from base.models import BaseModel
from base.validators import UF_CHOICES


class Guardian(BaseModel):
    """Responsável legal pelo aluno."""

    class Gender(models.TextChoices):
        MALE = "M", "Masculino"
        FEMALE = "F", "Feminino"
        NON_BINARY = "NB", "Não Binário"
        NOT_INFORMED = "NI", "Prefiro não informar"

    class Relationship(models.TextChoices):
        MOTHER = "MAE", "Mãe"
        FATHER = "PAI", "Pai"
        GRANDMOTHER = "AVO_F", "Avó"
        GRANDFATHER = "AVO_M", "Avô"
        AUNT = "TIA", "Tia"
        UNCLE = "TIO", "Tio"
        SISTER = "IRMA", "Irmã"
        BROTHER = "IRMAO", "Irmão"
        LEGAL = "LEGAL", "Responsável Legal"
        OTHER = "OUTRO", "Outro"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="guardian_profile",
        verbose_name="Usuário",
    )
    relationship_type = models.CharField(
        max_length=10, choices=Relationship.choices, verbose_name="Parentesco"
    )
    birth_date = models.DateField(null=True, blank=True, verbose_name="Data de Nascimento")
    gender = models.CharField(
        max_length=2, choices=Gender.choices, default=Gender.NOT_INFORMED, verbose_name="Gênero"
    )
    nationality = models.CharField(
        max_length=100, blank=True, default="Brasileiro(a)", verbose_name="Nacionalidade"
    )
    cpf = models.CharField(max_length=14, blank=True, default="", verbose_name="CPF")
    rg_number = models.CharField(max_length=20, blank=True, default="", verbose_name="RG — Número")
    rg_issuer = models.CharField(
        max_length=50, blank=True, default="", verbose_name="RG — Órgão Emissor"
    )
    rg_state = models.CharField(
        max_length=2, choices=UF_CHOICES, blank=True, default="", verbose_name="RG — UF"
    )
    phone = models.CharField(max_length=20, blank=True, default="", verbose_name="Telefone")
    phone_whatsapp = models.CharField(
        max_length=20, blank=True, default="", verbose_name="WhatsApp"
    )
    phone_mobile = models.CharField(max_length=20, blank=True, default="", verbose_name="Celular")

    class Meta:
        ordering = ["user__first_name", "user__last_name"]
        verbose_name = "Responsável"
        verbose_name_plural = "Responsáveis"
        indexes = [
            models.Index(fields=["cpf"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.get_full_name()} ({self.get_relationship_type_display()})"

    @property
    def full_name(self) -> str:
        return self.user.get_full_name()


class StudentGuardian(BaseModel):
    """Vínculo entre aluno e responsável."""

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="guardians",
        verbose_name="Aluno",
    )
    guardian = models.ForeignKey(
        Guardian,
        on_delete=models.CASCADE,
        related_name="students",
        verbose_name="Responsável",
    )
    is_primary = models.BooleanField(default=False, verbose_name="Responsável Principal")
    has_custody = models.BooleanField(default=True, verbose_name="Possui Guarda Legal")
    can_pickup = models.BooleanField(default=True, verbose_name="Autorizado a Buscar")

    class Meta:
        unique_together = [("student", "guardian")]
        verbose_name = "Vínculo Aluno-Responsável"
        verbose_name_plural = "Vínculos Aluno-Responsável"
        ordering = ["-is_primary", "guardian__user__first_name"]

    def __str__(self) -> str:
        return f"{self.guardian} → {self.student}"
