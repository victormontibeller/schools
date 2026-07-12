"""Modelos do módulo de frequência (controle de presença)."""

from django.db import models

from base.models import BaseModel
from base.upload_validators import validate_document_upload


class AttendanceRecord(BaseModel):
    """Registro de uma chamada feita pelo professor numa aula."""

    class_obj = models.ForeignKey(
        "classes.Class",
        on_delete=models.CASCADE,
        related_name="attendance_records",
        verbose_name="Turma",
    )
    subject = models.ForeignKey(
        "teachers.Subject",
        on_delete=models.PROTECT,
        related_name="attendance_records",
        verbose_name="Disciplina",
    )
    teacher = models.ForeignKey(
        "teachers.Teacher",
        on_delete=models.PROTECT,
        related_name="attendance_records",
        verbose_name="Professor",
    )
    date = models.DateField(verbose_name="Data")
    lesson_number = models.PositiveSmallIntegerField(
        default=1, verbose_name="Aula nº", help_text="Número da aula no dia."
    )
    notes = models.TextField(blank=True, default="", verbose_name="Observações")

    class Meta:
        ordering = ["-date", "-lesson_number"]
        verbose_name = "Registro de Chamada"
        verbose_name_plural = "Registros de Chamada"
        unique_together = [("class_obj", "date", "lesson_number")]

    def __str__(self) -> str:
        """Retorna a identificação curta do registro."""
        return f"{self.class_obj} · {self.subject} · {self.date} (aula {self.lesson_number})"


class AttendanceEntry(BaseModel):
    """Presença individual de um aluno numa chamada."""

    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Presente"
        ABSENT = "ABSENT", "Ausente"
        JUSTIFIED = "JUSTIFIED", "Justificado"

    record = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.CASCADE,
        related_name="entries",
        verbose_name="Registro",
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="attendance_entries",
        verbose_name="Aluno",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PRESENT,
        verbose_name="Situação",
    )
    justification = models.CharField(
        max_length=200, blank=True, default="", verbose_name="Justificativa"
    )
    note = models.CharField(
        max_length=250, blank=True, default="", verbose_name="Observação/recado"
    )

    class Meta:
        verbose_name = "Presença"
        verbose_name_plural = "Presenças"
        unique_together = [("record", "student")]
        ordering = ["record__date", "record__lesson_number", "student__first_name"]

    def __str__(self) -> str:
        """Retorna a identificação curta da presença."""
        return f"{self.student} — {self.record.date} ({self.get_status_display()})"


class AttendanceJustification(BaseModel):
    """Justificativa de ausência submetida por aluno/responsável."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        APPROVED = "APPROVED", "Aprovada"
        REJECTED = "REJECTED", "Rejeitada"

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="justifications",
        verbose_name="Aluno",
    )
    start_date = models.DateField(verbose_name="Início")
    end_date = models.DateField(verbose_name="Término")
    reason = models.CharField(max_length=200, verbose_name="Motivo")
    document = models.FileField(
        upload_to="attendance/justifications/",
        null=True,
        blank=True,
        verbose_name="Documento",
        validators=[validate_document_upload],
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Situação",
    )
    approved_by = models.ForeignKey(
        "core.CustomUser",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_justifications",
        verbose_name="Aprovado por",
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="Aprovado em")
    rejection_reason = models.CharField(
        max_length=200, blank=True, default="", verbose_name="Motivo da rejeição"
    )

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "Justificativa de Ausência"
        verbose_name_plural = "Justificativas de Ausência"

    def __str__(self) -> str:
        """Retorna a identificação curta da justificativa."""
        return f"{self.student} · {self.start_date} → {self.end_date} ({self.get_status_display()})"
