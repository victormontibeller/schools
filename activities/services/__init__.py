"""Serviço público do domínio de atividades."""

from activities.services.activity import ActivityCoreService
from activities.services.groups import ActivityGroupMixin


class ActivityService(ActivityGroupMixin, ActivityCoreService):
    """Coordena atividades individuais e em grupo."""


__all__ = ["ActivityService"]
