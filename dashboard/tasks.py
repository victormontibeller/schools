"""Tarefas Celery periodicas para atualizacao de cache de dashboards."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def update_school_dashboard_cache() -> None:
    """Atualiza cache do dashboard escolar. Executada a cada 5 min."""
    from dashboard.services import DashboardService

    DashboardService().get_school_dashboard_data()
    logger.info("Cache do dashboard escolar atualizado.")


@shared_task
def update_executive_dashboard_cache() -> None:
    """Atualiza cache do dashboard executivo. Executada a cada 15 min."""
    from dashboard.services import DashboardService

    DashboardService().get_executive_dashboard_data()
    logger.info("Cache do dashboard executivo atualizado.")
