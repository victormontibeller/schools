"""Tarefas Celery periodicas para atualizacao de cache de dashboards."""

from __future__ import annotations

import logging

from celery import shared_task
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@shared_task
def update_school_dashboard_cache(tenant_schema: str) -> None:
    """Atualiza cache do dashboard escolar para um tenant especifico."""
    with schema_context(tenant_schema):
        from dashboard.services import DashboardService

        DashboardService().get_school_dashboard_data()
        logger.info(
            "Cache do dashboard escolar atualizado.", extra={"tenant_schema": tenant_schema}
        )


@shared_task
def refresh_all_school_dashboards() -> None:
    """Dispatcher periodico: enfileira atualizacao de cache por tenant ativo.

    Esta e a task que o Celery Beat deve chamar a cada 5 minutos.
    Ela itera todos os tenants ativos e dispara `update_school_dashboard_cache`
    individualmente, garantindo isolamento de schema.
    """
    from core.models import School

    for tenant in School.objects.filter(is_active=True):
        update_school_dashboard_cache.delay(tenant.schema_name)


@shared_task
def update_executive_dashboard_cache() -> None:
    """Atualiza cache do dashboard executivo (dados agregados do schema public).

    Nao requer schema_context — opera no schema public para agregar dados
    de todos os tenants (total_tenants, platform_users, platform_growth).
    """
    from dashboard.services import DashboardService

    DashboardService().get_executive_dashboard_data()
    logger.info("Cache do dashboard executivo atualizado.")
