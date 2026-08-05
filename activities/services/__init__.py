"""Serviço público do domínio de atividades."""

from activities.services.activity import ActivityCoreService
from activities.services.groups import ActivityGroupMixin
from activities.services.scores import ActivityScoreMixin


class ActivityService(ActivityScoreMixin, ActivityGroupMixin, ActivityCoreService):
    """Coordena atividades individuais e em grupo."""


__all__ = ["ActivityService"]
