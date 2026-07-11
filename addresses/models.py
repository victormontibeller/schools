"""Modelos do modulo de enderecos."""

from django.db import models

from base.models import BaseModel


class Address(BaseModel):
    """Endereco reutilizavel para School, Teacher, Student e Guardian."""

    recipient = models.CharField(
        max_length=255, blank=True, default="", verbose_name="Destinatario"
    )
    street = models.CharField(max_length=255, verbose_name="Logradouro")
    number = models.CharField(max_length=20, verbose_name="Numero")
    complement = models.CharField(
        max_length=255, blank=True, default="", verbose_name="Complemento"
    )
    district = models.CharField(max_length=150, verbose_name="Bairro")
    postal_code = models.CharField(max_length=9, verbose_name="CEP")
    city = models.CharField(max_length=150, verbose_name="Municipio")
    state = models.CharField(max_length=2, verbose_name="Estado")

    class Meta:
        verbose_name = "Endereco"
        verbose_name_plural = "Enderecos"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["city"]),
            models.Index(fields=["state"]),
            models.Index(fields=["postal_code"]),
        ]

    def __str__(self) -> str:
        return f"{self.street}, {self.number} — {self.city}/{self.state}"


class SchoolAddress(BaseModel):
    """Vinculo entre School e Address."""

    school = models.ForeignKey(
        "tenancy.School",
        # DO_NOTHING: o schema do tenant e removido integralmente antes do registro publico.
        on_delete=models.DO_NOTHING,
        related_name="+",
        verbose_name="Escola",
    )
    address = models.ForeignKey(
        Address,
        on_delete=models.CASCADE,
        related_name="school_links",
        verbose_name="Endereco",
    )
    is_primary = models.BooleanField(default=True, verbose_name="Principal")

    class Meta:
        verbose_name = "Endereco da Escola"
        verbose_name_plural = "Enderecos da Escola"
        unique_together = [("school", "address")]

    def __str__(self) -> str:
        return f"{self.school} — {self.address}"


class BusinessUnitAddress(BaseModel):
    """Vinculo entre BusinessUnit e Address."""

    business_unit = models.ForeignKey(
        "core.BusinessUnit",
        on_delete=models.CASCADE,
        related_name="address_links",
        verbose_name="Empresa",
    )
    address = models.ForeignKey(
        Address,
        on_delete=models.CASCADE,
        related_name="business_unit_links",
        verbose_name="Endereco",
    )
    is_primary = models.BooleanField(default=True, verbose_name="Principal")

    class Meta:
        verbose_name = "Endereco da Empresa"
        verbose_name_plural = "Enderecos da Empresa"
        unique_together = [("business_unit", "address")]

    def __str__(self) -> str:
        return f"{self.business_unit} — {self.address}"


class TeacherAddress(BaseModel):
    """Vinculo entre Teacher e Address."""

    teacher = models.ForeignKey(
        "teachers.Teacher",
        on_delete=models.CASCADE,
        related_name="address_links",
        verbose_name="Professor",
    )
    address = models.ForeignKey(
        Address,
        on_delete=models.CASCADE,
        related_name="teacher_links",
        verbose_name="Endereco",
    )
    is_primary = models.BooleanField(default=True, verbose_name="Principal")

    class Meta:
        verbose_name = "Endereco do Professor"
        verbose_name_plural = "Enderecos do Professor"
        unique_together = [("teacher", "address")]

    def __str__(self) -> str:
        return f"{self.teacher} — {self.address}"


class StudentAddress(BaseModel):
    """Vinculo entre Student e Address."""

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="address_links",
        verbose_name="Aluno",
    )
    address = models.ForeignKey(
        Address,
        on_delete=models.CASCADE,
        related_name="student_links",
        verbose_name="Endereco",
    )
    is_primary = models.BooleanField(default=True, verbose_name="Principal")

    class Meta:
        verbose_name = "Endereco do Aluno"
        verbose_name_plural = "Enderecos do Aluno"
        unique_together = [("student", "address")]

    def __str__(self) -> str:
        return f"{self.student} — {self.address}"


class GuardianAddress(BaseModel):
    """Vinculo entre Guardian e Address."""

    guardian = models.ForeignKey(
        "guardians.Guardian",
        on_delete=models.CASCADE,
        related_name="address_links",
        verbose_name="Responsavel",
    )
    address = models.ForeignKey(
        Address,
        on_delete=models.CASCADE,
        related_name="guardian_links",
        verbose_name="Endereco",
    )
    is_primary = models.BooleanField(default=True, verbose_name="Principal")

    class Meta:
        verbose_name = "Endereco do Responsavel"
        verbose_name_plural = "Enderecos do Responsavel"
        unique_together = [("guardian", "address")]

    def __str__(self) -> str:
        return f"{self.guardian} — {self.address}"
