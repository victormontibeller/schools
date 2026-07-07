"""Modelos compartilhados de estados e municipios."""

from django.db import models

from base.models import BaseModel


class State(BaseModel):
    """Catalogo global de unidades federativas brasileiras."""

    code = models.CharField(max_length=2, unique=True, verbose_name="UF")
    name = models.CharField(max_length=100, verbose_name="Nome")

    class Meta:
        verbose_name = "Estado"
        verbose_name_plural = "Estados"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class City(BaseModel):
    """Catalogo global de municipios brasileiros por UF."""

    state = models.ForeignKey(
        State,
        on_delete=models.CASCADE,  # CASCADE: sem UF, o municipio perde o contexto geografico.
        related_name="cities",
        verbose_name="Estado",
    )
    name = models.CharField(max_length=150, verbose_name="Municipio")
    ibge_code = models.CharField(max_length=7, unique=True, verbose_name="Codigo IBGE")

    class Meta:
        verbose_name = "Municipio"
        verbose_name_plural = "Municipios"
        ordering = ["state__code", "name"]
        indexes = [
            models.Index(fields=["state"]),
            models.Index(fields=["name"]),
            models.Index(fields=["ibge_code"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["state", "name"],
                name="uniq_locations_city_state_name",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name}/{self.state.code}"
