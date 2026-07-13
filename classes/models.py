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

    class EducationStage(models.TextChoices):
        EARLY_CHILDHOOD = "EARLY_CHILDHOOD", "Educação Infantil"
        ELEMENTARY_I = "ELEMENTARY_I", "Ensino Fundamental — Anos Iniciais"
        ELEMENTARY_II = "ELEMENTARY_II", "Ensino Fundamental — Anos Finais"
        HIGH_SCHOOL = "HIGH_SCHOOL", "Ensino Médio"
        OTHER = "OTHER", "Outra"

    class Grade(models.TextChoices):
        EARLY_NURSERY_1 = "EARLY_NURSERY_1", "Berçário I"
        EARLY_NURSERY_2 = "EARLY_NURSERY_2", "Berçário II"
        EARLY_MATERNAL_1 = "EARLY_MATERNAL_1", "Maternal I"
        EARLY_MATERNAL_2 = "EARLY_MATERNAL_2", "Maternal II"
        EARLY_PRE_1 = "EARLY_PRE_1", "Pré I"
        EARLY_PRE_2 = "EARLY_PRE_2", "Pré II"
        ELEMENTARY_1 = "ELEMENTARY_1", "1º Ano"
        ELEMENTARY_2 = "ELEMENTARY_2", "2º Ano"
        ELEMENTARY_3 = "ELEMENTARY_3", "3º Ano"
        ELEMENTARY_4 = "ELEMENTARY_4", "4º Ano"
        ELEMENTARY_5 = "ELEMENTARY_5", "5º Ano"
        ELEMENTARY_6 = "ELEMENTARY_6", "6º Ano"
        ELEMENTARY_7 = "ELEMENTARY_7", "7º Ano"
        ELEMENTARY_8 = "ELEMENTARY_8", "8º Ano"
        ELEMENTARY_9 = "ELEMENTARY_9", "9º Ano"
        HIGH_SCHOOL_1 = "HIGH_SCHOOL_1", "1ª Série"
        HIGH_SCHOOL_2 = "HIGH_SCHOOL_2", "2ª Série"
        HIGH_SCHOOL_3 = "HIGH_SCHOOL_3", "3ª Série"
        OTHER = "OTHER", "Outra"

    name = models.CharField(max_length=100, verbose_name="Nome")
    grade = models.CharField(max_length=30, choices=Grade.choices, verbose_name="Série")
    education_stage = models.CharField(
        max_length=20,
        choices=EducationStage.choices,
        default=EducationStage.OTHER,
        verbose_name="Etapa de Ensino",
    )
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
        return f"{self.name} · {self.get_grade_display()} · {self.academic_year}"

    @property
    def enrollment_count(self) -> int:
        """Retorna o número de matrículas ativas na turma."""
        return self.enrollments.filter(status=Enrollment.Status.ACTIVE).count()

    @property
    def has_open_seats(self) -> bool:
        """Indica se ainda há vagas disponíveis."""
        return self.enrollment_count < self.max_students


GRADES_BY_EDUCATION_STAGE = {
    Class.EducationStage.EARLY_CHILDHOOD: (
        Class.Grade.EARLY_NURSERY_1,
        Class.Grade.EARLY_NURSERY_2,
        Class.Grade.EARLY_MATERNAL_1,
        Class.Grade.EARLY_MATERNAL_2,
        Class.Grade.EARLY_PRE_1,
        Class.Grade.EARLY_PRE_2,
    ),
    Class.EducationStage.ELEMENTARY_I: (
        Class.Grade.ELEMENTARY_1,
        Class.Grade.ELEMENTARY_2,
        Class.Grade.ELEMENTARY_3,
        Class.Grade.ELEMENTARY_4,
        Class.Grade.ELEMENTARY_5,
    ),
    Class.EducationStage.ELEMENTARY_II: (
        Class.Grade.ELEMENTARY_6,
        Class.Grade.ELEMENTARY_7,
        Class.Grade.ELEMENTARY_8,
        Class.Grade.ELEMENTARY_9,
    ),
    Class.EducationStage.HIGH_SCHOOL: (
        Class.Grade.HIGH_SCHOOL_1,
        Class.Grade.HIGH_SCHOOL_2,
        Class.Grade.HIGH_SCHOOL_3,
    ),
    Class.EducationStage.OTHER: (Class.Grade.OTHER,),
}

GRADE_PEDAGOGICAL_ORDER = tuple(
    grade for stage_grades in GRADES_BY_EDUCATION_STAGE.values() for grade in stage_grades
)


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
