"""Bootstrap idempotente dos papéis e acessos de cada schema."""

from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate, dispatch_uid="core.seed_fixed_roles_and_accesses")
def seed_fixed_roles(sender, **kwargs) -> None:
    """Cria somente registros ausentes, preservando toda personalização."""
    if sender.name != "core":
        return
    from core.access.services import AccessConfigurationService

    AccessConfigurationService().create_missing_access_defaults()
