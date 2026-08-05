"""Coordenação pública dos seeds DEMO por domínio."""

from academic_calendar.demo_seed import CalendarDemoSeedMixin
from activities.demo_seed import ActivityDemoSeedMixin
from agenda.demo_seed import AgendaDemoSeedMixin
from attendance.demo_seed import AttendanceDemoSeedMixin
from base.services import BaseService
from core.demo_seed.core_data import CoreDemoSeedMixin
from financeiro.demo_seed import FinanceDemoSeedMixin
from rooms.demo_seed import RoomDemoSeedMixin


class DemoSeedService(
    CoreDemoSeedMixin,
    RoomDemoSeedMixin,
    AgendaDemoSeedMixin,
    ActivityDemoSeedMixin,
    CalendarDemoSeedMixin,
    AttendanceDemoSeedMixin,
    FinanceDemoSeedMixin,
    BaseService,
):
    """Coordena os seeds idempotentes sem concentrar regras dos domínios."""

    def populate_core(self, school) -> dict[str, int]:
        """Popula a base acadêmica e, então, a matriz semanal da grade."""
        result = super().populate_core(school)
        self.populate_schedule()
        return result


def get_demo_seed_service() -> DemoSeedService:
    """Retorna o service de seed com ator de sistema."""
    return DemoSeedService(user=None)


__all__ = ["DemoSeedService", "get_demo_seed_service"]
