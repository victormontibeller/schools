"""Modelos do módulo de calendário acadêmico."""

from django.db import models

from base.models import BaseModel


class AcademicYear(BaseModel):
    """Ano letivo de uma escola — janela temporal que contém eventos."""

    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planejado"
        IN_PROGRESS = "IN_PROGRESS", "Em Andamento"
        CLOSED = "CLOSED", "Encerrado"

    name = models.CharField(max_length=50, verbose_name="Nome")
    start_date = models.DateField(verbose_name="Início")
    end_date = models.DateField(verbose_name="Término")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
        verbose_name="Situação",
    )

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "Ano Letivo"
        verbose_name_plural = "Anos Letivos"
        unique_together = [("name", "start_date")]

    def __str__(self) -> str:
        """Retorna a identificação curta do ano letivo."""
        return f"{self.name} · {self.start_date} → {self.end_date}"


class Holiday(BaseModel):
    """Feriado ou dia não letivo — descontado do cálculo de dias letivos."""

    class Type(models.TextChoices):
        NATIONAL = "NATIONAL", "Nacional"
        STATE = "STATE", "Estadual"
        MUNICIPAL = "MUNICIPAL", "Municipal"
        SCHOOL = "SCHOOL", "Escolar"

    name = models.CharField(max_length=120, verbose_name="Nome")
    date = models.DateField(verbose_name="Data")
    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.NATIONAL,
        verbose_name="Tipo",
    )
    is_recurring = models.BooleanField(
        default=False,
        verbose_name="Repete todo ano",
        help_text="Quando ativo, o feriado é considerado em qualquer ano.",
    )

    class Meta:
        ordering = ["date"]
        verbose_name = "Feriado"
        verbose_name_plural = "Feriados"
        unique_together = [("name", "date")]

    def __str__(self) -> str:
        """Retorna a identificação curta do feriado."""
        return f"{self.date} · {self.name}"


class CalendarEvent(BaseModel):
    """Evento do calendário acadêmico — pode ser único ou recorrente."""

    class Type(models.TextChoices):
        HOLIDAY = "HOLIDAY", "Feriado/Dia não letivo"
        MEETING = "MEETING", "Reunião"
        SCHOOL_EVENT = "SCHOOL_EVENT", "Evento Escolar"
        NON_SCHOOL_DAY = "NON_SCHOOL_DAY", "Dia não letivo"
        ASSESSMENT = "ASSESSMENT", "Avaliação"
        OTHER = "OTHER", "Outro"

    class Audience(models.TextChoices):
        ALL = "ALL", "Todos"
        TEACHERS = "TEACHERS", "Professores"
        STUDENTS = "STUDENTS", "Alunos"
        GUARDIANS = "GUARDIANS", "Responsáveis"
        CLASS = "CLASS", "Turma específica"

    title = models.CharField(max_length=200, verbose_name="Título")
    description = models.TextField(blank=True, default="", verbose_name="Descrição")
    start_date = models.DateField(verbose_name="Início")
    end_date = models.DateField(verbose_name="Término")
    start_time = models.TimeField(null=True, blank=True, verbose_name="Hora de início")
    end_time = models.TimeField(null=True, blank=True, verbose_name="Hora de término")
    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.SCHOOL_EVENT,
        verbose_name="Tipo",
    )
    recurrence = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Recorrência",
        help_text="Regra de recorrência (ex.: {'freq':'WEEKLY','interval':1}).",
    )
    audience = models.CharField(
        max_length=20,
        choices=Audience.choices,
        default=Audience.ALL,
        verbose_name="Público-alvo",
    )
    class_obj = models.ForeignKey(
        "classes.Class",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="calendar_events",
        verbose_name="Turma",
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
        verbose_name="Ano Letivo",
    )
    is_public = models.BooleanField(
        default=False,
        verbose_name="Público para responsáveis/alunos",
    )
    is_cancelled = models.BooleanField(default=False, verbose_name="Cancelado")
    cancel_reason = models.CharField(
        max_length=200, blank=True, default="", verbose_name="Motivo de cancelamento"
    )

    class Meta:
        ordering = ["start_date", "start_time"]
        verbose_name = "Evento"
        verbose_name_plural = "Eventos"

    def __str__(self) -> str:
        """Retorna a identificação curta do evento."""
        return f"{self.start_date} · {self.title} ({self.get_type_display()})"
