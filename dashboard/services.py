"""DashboardService: agregacao de KPIs com cache Redis."""

from __future__ import annotations

import logging

from django.core.cache import cache

from base.services import BaseService

logger = logging.getLogger(__name__)

# TTL por tipo de dado (segundos).
CACHE_TTL = {
    "total_students": 3600,  # 1h
    "total_teachers": 3600,
    "total_classes": 3600,
    "total_guardians": 3600,
    "today_attendance": 300,  # 5 min
    "weekly_attendance": 600,  # 10 min
    "students_at_risk": 600,
    "pending_activities": 300,
    "upcoming_events": 600,
    "recent_announcements": 300,
    "total_tenants": 3600,
    "platform_users": 3600,
    "platform_growth": 3600,
    "school_dashboard": 60,  # cache composto — 1 min
    "executive_dashboard": 900,  # 15 min
}


class DashboardService(BaseService):
    """Servico de aplicacao para agregacao de dashboards."""

    @staticmethod
    def _cache_key(prefix: str, identifier: str = "") -> str:
        return f"dashboard:{prefix}:{identifier}".rstrip(":")

    def get_school_dashboard_data(self) -> dict:
        """Retorna todos os KPIs do dashboard escolar com cache.

        Se Redis estiver indisponivel, consulta o banco diretamente.
        """
        cache_key = self._cache_key("school_dashboard")
        data = self._safe_cache_get(cache_key)
        if data is not None:
            return data

        from dashboard.selectors import DashboardSelector

        selector = DashboardSelector()
        data = {
            "total_students": self._cached("total_students", selector.get_total_students),
            "total_teachers": self._cached("total_teachers", selector.get_total_teachers),
            "total_classes": self._cached("total_classes", selector.get_total_classes),
            "total_guardians": self._cached("total_guardians", selector.get_total_guardians),
            "today_attendance": self._cached(
                "today_attendance", selector.get_today_attendance_rate
            ),
            "weekly_attendance": self._cached("weekly_attendance", selector.get_weekly_attendance),
            "students_at_risk": self._cached(
                "students_at_risk", selector.get_students_at_risk_count
            ),
            "pending_activities": self._cached(
                "pending_activities", selector.get_pending_activities
            ),
            "upcoming_events": self._cached("upcoming_events", selector.get_upcoming_events),
            "recent_announcements": self._cached(
                "recent_announcements", selector.get_recent_announcements
            ),
        }
        self._safe_cache_set(cache_key, data, CACHE_TTL["school_dashboard"])
        return data

    def get_executive_dashboard_data(self) -> dict:
        """Retorna KPIs agregados de todos os tenants com cache."""
        cache_key = self._cache_key("executive_dashboard")
        data = self._safe_cache_get(cache_key)
        if data is not None:
            return data

        from dashboard.selectors import DashboardSelector

        selector = DashboardSelector()
        data = {
            "total_tenants": self._cached("total_tenants", selector.get_total_tenants),
            "platform_users": self._cached("platform_users", selector.get_platform_users),
            "platform_growth": self._cached("platform_growth", selector.get_platform_growth),
        }
        self._safe_cache_set(cache_key, data, CACHE_TTL["executive_dashboard"])
        return data

    def invalidate_cache(self, key: str = "") -> None:
        """Invalida cache por chave especifica ou todo o dashboard."""
        try:
            if key:
                cache.delete(self._cache_key(key))
            else:
                for prefix in CACHE_TTL:
                    cache.delete(self._cache_key(prefix))
        except Exception:
            pass
        self._log("Cache de dashboard invalidado", key=key or "all")

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _safe_cache_get(key: str):
        """cache.get com fallback silencioso se Redis indisponivel."""
        try:
            return cache.get(key)
        except Exception:
            return None

    @staticmethod
    def _safe_cache_set(key: str, value, timeout: int) -> None:
        """cache.set com fallback silencioso se Redis indisponivel."""
        try:
            cache.set(key, value, timeout=timeout)
        except Exception:
            pass

    def _cached(self, key: str, fn, *args, **kwargs):
        """Executa funcao com cache Redis individual."""
        cache_key = self._cache_key(key)
        value = self._safe_cache_get(cache_key)
        if value is not None:
            return value
        result = fn(*args, **kwargs) if callable(fn) else fn
        self._safe_cache_set(cache_key, result, CACHE_TTL.get(key, 300))
        return result
