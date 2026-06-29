"""Modelos do módulo de turmas e matrículas."""

from django.db import models

from base.models import BaseModel


class Class(BaseModel):
    """Turma de uma escola — agrupa alunos num ano letivo."""

    class Shift(models.TextChoices):
        MORNING = "MORNING", "Matutino"
        AFTERNOON = "AFTERNOON", "Vespertino"
        NIGHT = "NIGHT", "Noturno"
        FULL = "FULL", "Integral"

    name = models.CharField(max_length=100, verbose_name="Nome")
    grade = models.CharField(max_length=30, verbose_name="Série")
    shift = models.CharField(
        max_length=10, choices=Shift.choices, default=Shift.MORNING, verbose_name="Turno"
    )
    academic_year = models.PositiveIntegerField(verbose_name="Ano Letivo")
    max_students = models.PositiveIntegerField(default=30, verbose_name="Vagas")
    class_teacher = models.ForeignKey(
        "teachers.Teacher",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="classes",
        verbose_name="Professor Responsável",
    )

    class Meta:
        ordering = ["-academic_year", "name"]
        verbose_name = "Turma"
        verbose_name_plural = "Turmas"
        unique_together = [("name", "academic_year")]

    def __str__(self) -> str:
        """Retorna a identificação curta da turma."""
        return f"{self.name} · {self.grade} · {self.academic_year}"

    @property
    def enrollment_count(self) -> int:
        """Retorna o número de matrículas ativas na turma."""
        return self.enrollments.filter(status=Enrollment.Status.ACTIVE).count()

    @property
    def has_open_seats(self) -> bool:
        """Indica se ainda há vagas disponíveis."""
        return self.enrollment_count < self.max_students


class Enrollment(BaseModel):
    """Matrícula de um aluno em uma turma."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Ativa"
        TRANSFERRED = "TRANSFERRED", "Transferida"
        CANCELLED = "CANCELLED", "Cancelada"

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name="Aluno",
    )
    class_obj = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name="Turma",
    )
    enrollment_date = models.DateField(verbose_name="Data de Matrícula")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE, verbose_name="Situação"
    )
    cancel_reason = models.CharField(
        max_length=200, blank=True, default="", verbose_name="Motivo de Cancelamento"
    )

    class Meta:
        verbose_name = "Matrícula"
        verbose_name_plural = "Matrículas"
        ordering = ["-enrollment_date"]
        unique_together = [("student", "class_obj")]

    def __str__(self) -> str:
        """Retorna a identificação curta da matrícula."""
        return f"{self.student} → {self.class_obj} ({self.get_status_display()})"
