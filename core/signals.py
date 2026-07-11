"""Seeds idempotentes de papéis e permissões por schema."""

from django.apps import apps
from django.db.models.signals import post_migrate
from django.dispatch import receiver

ROLE_APP_PERMISSIONS = {
    "ADMIN": {"*"},
    "SECRETARY": {"students", "guardians", "classes", "enrollments", "addresses", "rooms"},
    "COORDINATOR": {
        "teachers",
        "students",
        "guardians",
        "classes",
        "rooms",
        "agenda",
        "activities",
        "academic_calendar",
        "attendance",
        "notifications",
        "dashboard",
    },
    "TEACHER": {
        "classes",
        "agenda",
        "activities",
        "attendance",
        "academic_calendar",
        "notifications",
    },
    "FINANCE": {"financeiro", "students", "classes"},
    "GUARDIAN": {"students", "activities", "attendance", "academic_calendar", "notifications"},
}


@receiver(post_migrate, dispatch_uid="core.seed_fixed_roles")
def seed_fixed_roles(sender, **kwargs) -> None:
    """Cria os seis papéis e associa permissões do schema atual."""
    if sender.name != "core":
        return
    Role = apps.get_model("core", "Role")
    Permission = apps.get_model("auth", "Permission")
    for role_name, app_labels in ROLE_APP_PERMISSIONS.items():
        role, _ = Role.objects.get_or_create(name=role_name)
        permissions = Permission.objects.all()
        if "*" not in app_labels:
            permissions = permissions.filter(content_type__app_label__in=app_labels)
        role.permissions.set(permissions)
