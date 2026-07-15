"""Coordenação pública dos seeds DEMO por domínio."""

from academic_calendar.demo_seed import CalendarDemoSeedMixin
from activities.demo_seed import ActivityDemoSeedMixin
from attendance.demo_seed import AttendanceDemoSeedMixin
from base.services import BaseService
from core.demo_seed.core_data import CoreDemoSeedMixin
from rooms.demo_seed import RoomDemoSeedMixin


class DemoSeedService(
    CoreDemoSeedMixin,
    RoomDemoSeedMixin,
    ActivityDemoSeedMixin,
    CalendarDemoSeedMixin,
    AttendanceDemoSeedMixin,
    BaseService,
):
    """Coordena os seeds idempotentes sem concentrar regras dos domínios."""


def get_demo_seed_service() -> DemoSeedService:
    """Retorna o service de seed com ator de sistema."""
    return DemoSeedService(user=None)


__all__ = ["DemoSeedService", "get_demo_seed_service"]
