"""Modelos do módulo de grade horária."""

from django.db import models

from base.models import BaseModel


class TimeSlot(BaseModel):
    """Faixa de horário recorrente (por dia da semana) da grade escolar."""

    class Day(models.TextChoices):
        MON = "MON", "Segunda"
        TUE = "TUE", "Terça"
        WED = "WED", "Quarta"
        THU = "THU", "Quinta"
        FRI = "FRI", "Sexta"
        SAT = "SAT", "Sábado"
        SUN = "SUN", "Domingo"

    day_of_week = models.CharField(max_length=3, choices=Day.choices, verbose_name="Dia da Semana")
    start_time = models.TimeField(verbose_name="Início")
    end_time = models.TimeField(verbose_name="Fim")
    slot_number = models.PositiveSmallIntegerField(default=1, verbose_name="Número do Horário")

    class Meta:
        ordering = ["day_of_week", "slot_number"]
        verbose_name = "Horário"
        verbose_name_plural = "Horários"
        unique_together = [("day_of_week", "start_time", "end_time")]

    def __str__(self) -> str:
        """Retorna a identificação do horário (dia + faixa)."""
        return f"{self.get_day_of_week_display()} {self.start_time}–{self.end_time}"


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
    valid_from = models.DateField(verbose_name="Válido a partir de")
    valid_until = models.DateField(null=True, blank=True, verbose_name="Válido até")

    class Meta:
        ordering = ["-valid_from", "class_obj", "time_slot__day_of_week", "time_slot__start_time"]
        verbose_name = "Grade Horária"
        verbose_name_plural = "Grade Horária"

    def __str__(self) -> str:
        """Retorna a identificação curta da entrada da grade."""
        return f"{self.class_obj} · {self.teacher} · {self.subject} · {self.time_slot}"
