"""Modelos do módulo de salas físicas."""

from django.db import models

from base.models import BaseModel


class Room(BaseModel):
    """Sala física da escola — sala de aula, laboratório, quadra, etc."""

    class Type(models.TextChoices):
        CLASSROOM = "CLASSROOM", "Sala de Aula"
        LAB = "LAB", "Laboratório"
        GYM = "GYM", "Quadra"
        LIBRARY = "LIBRARY", "Biblioteca"
        AUDITORIUM = "AUDITORIUM", "Auditório"
        OTHER = "OTHER", "Outro"

    name = models.CharField(max_length=100, verbose_name="Nome")
    code = models.CharField(max_length=20, unique=True, verbose_name="Código")
    capacity = models.PositiveIntegerField(default=0, verbose_name="Capacidade")
    type = models.CharField(
        max_length=20, choices=Type.choices, default=Type.CLASSROOM, verbose_name="Tipo"
    )
    resources = models.JSONField(default=dict, blank=True, verbose_name="Recursos")
    observations = models.TextField(blank=True, default="", verbose_name="Observações")
    floor = models.CharField(max_length=20, blank=True, default="", verbose_name="Andar")
    building = models.CharField(max_length=50, blank=True, default="", verbose_name="Prédio")

    class Meta:
        ordering = ["building", "floor", "name"]
        verbose_name = "Sala"
        verbose_name_plural = "Salas"

    def __str__(self) -> str:
        """Retorna a representação textual curta da sala."""
        return f"{self.code} — {self.name}".strip(" —")
