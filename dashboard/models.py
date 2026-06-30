"""Modelos do modulo de dashboards."""

from __future__ import annotations

from django.db import models

from base.models import BaseModel


class DashboardWidget(BaseModel):
    """Configuracao de widget por escola — posicao, tipo, refresh."""

    class WidgetType(models.TextChoices):
        KPI = "KPI", "Indicador (card)"
        CHART = "CHART", "Grafico"
        TABLE = "TABLE", "Tabela"
        LIST = "LIST", "Lista"

    name: str = models.CharField(max_length=100, verbose_name="Nome")
    widget_type: str = models.CharField(
        max_length=20,
        choices=WidgetType.choices,
        default=WidgetType.KPI,
        verbose_name="Tipo",
    )
    datasource: str = models.CharField(
        max_length=100,
        verbose_name="Fonte de dados",
        help_text="Metodo do DashboardSelector que alimenta o widget.",
    )
    refresh_interval: int = models.PositiveIntegerField(
        default=60,
        verbose_name="Intervalo de atualizacao (s)",
    )
    position: int = models.PositiveIntegerField(default=0, verbose_name="Posicao no grid")
    size: str = models.CharField(
        max_length=10,
        default="medium",
        verbose_name="Tamanho",
        help_text="small, medium, large, full",
    )
    is_visible: bool = models.BooleanField(default=True, verbose_name="Visivel")
    config: dict = models.JSONField(default=dict, blank=True, verbose_name="Configuracao extra")

    class Meta:
        ordering = ["position"]
        verbose_name = "Widget"
        verbose_name_plural = "Widgets"

    def __str__(self) -> str:
        return f"{self.name} ({self.get_widget_type_display()})"
