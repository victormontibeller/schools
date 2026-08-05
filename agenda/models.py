"""Modelos do módulo de grade horária."""

from django.db import models

from base.models import BaseModel


class TimeSlot(BaseModel):
    """Período de um turno reutilizável pelas turmas compatíveis da escola."""

    class Shift(models.TextChoices):
        MORNING = "MORNING", "Matutino"
        AFTERNOON = "AFTERNOON", "Vespertino"
        NIGHT = "NIGHT", "Noturno"

    start_time = models.TimeField(verbose_name="Início")
    end_time = models.TimeField(verbose_name="Fim")
    slot_number = models.PositiveSmallIntegerField(default=1, verbose_name="Número do Horário")
    shift = models.CharField(max_length=9, choices=Shift.choices, verbose_name="Turno")

    class Meta:
        ordering = ["start_time", "end_time", "slot_number"]
        verbose_name = "Período"
        verbose_name_plural = "Períodos"
        indexes = [models.Index(fields=["shift", "start_time"], name="agenda_ts_shift_start_idx")]
        constraints = [
            models.UniqueConstraint(
                fields=["start_time", "end_time"], name="agenda_unique_time_slot_interval"
            ),
            models.CheckConstraint(
                condition=models.Q(shift__in=["MORNING", "AFTERNOON", "NIGHT"]),
                name="agenda_time_slot_valid_shift",
            ),
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F("start_time")),
                name="agenda_time_slot_valid_interval",
            ),
        ]

    def __str__(self) -> str:
        """Retorna a identificação curta do período."""
        return f"{self.get_shift_display()} · {self.start_time}–{self.end_time}"


class Schedule(BaseModel):
    """Item da grade horária — combina turma, professor, disciplina, sala e horário."""

    class_obj = models.ForeignKey(
        "classes.Class",
        on_delete=models.CASCADE,
        related_name="schedules",
        verbose_name="Turma",
    )
    teacher = models.ForeignKey(
        "teachers.Teacher",
        on_delete=models.PROTECT,
        related_name="schedules",
        verbose_name="Professor",
    )
    subject = models.ForeignKey(
        "teachers.Subject",
        on_delete=models.PROTECT,
        related_name="schedules",
        verbose_name="Disciplina",
    )
    room = models.ForeignKey(
        "rooms.Room",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="schedules",
        verbose_name="Sala",
    )
    time_slot = models.ForeignKey(
        TimeSlot,
        on_delete=models.PROTECT,
        related_name="schedules",
        verbose_name="Horário",
    )

    class Day(models.TextChoices):
        MON = "MON", "Segunda"
        TUE = "TUE", "Terça"
        WED = "WED", "Quarta"
        THU = "THU", "Quinta"
        FRI = "FRI", "Sexta"

    day_of_week = models.CharField(max_length=3, choices=Day.choices, verbose_name="Dia da Semana")
    valid_from = models.DateField(verbose_name="Válido a partir de")
    valid_until = models.DateField(null=True, blank=True, verbose_name="Válido até")

    class Meta:
        ordering = ["-valid_from", "class_obj", "day_of_week", "time_slot__start_time"]
        verbose_name = "Grade Horária"
        verbose_name_plural = "Grade Horária"
        indexes = [
            models.Index(fields=["class_obj", "day_of_week", "time_slot"]),
            models.Index(fields=["teacher", "day_of_week", "time_slot"]),
            models.Index(fields=["room", "day_of_week", "time_slot"]),
            models.Index(fields=["valid_from", "valid_until"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valid_until__isnull=True)
                | models.Q(valid_until__gte=models.F("valid_from")),
                name="agenda_schedule_valid_interval",
            )
        ]

    def __str__(self) -> str:
        """Retorna a identificação curta da entrada da grade."""
        return (
            f"{self.class_obj} · {self.get_day_of_week_display()} · {self.time_slot} "
            f"· {self.teacher} · {self.subject}"
        )
