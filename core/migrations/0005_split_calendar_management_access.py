from django.db import migrations


ELIGIBLE_ROLES = ("SECRETARY", "COORDINATOR", "FINANCE")
TARGET_MODULES = ("holidays", "academic_years")


def copy_calendar_management_access(apps, schema_editor):
    """Cria capacidades separadas sem sobrescrever configurações já existentes."""
    Role = apps.get_model("core", "Role")
    RoleModuleAccess = apps.get_model("core", "RoleModuleAccess")

    for role in Role.objects.filter(name__in=ELIGIBLE_ROLES):
        source = RoleModuleAccess.objects.filter(
            role=role,
            module_key="academic_calendar",
        ).first()
        if source is None:
            continue
        defaults = {
            "can_view": source.can_view,
            "can_create": source.can_create,
            "can_edit": source.can_edit,
            "can_deactivate": False,
            "created_by_id": source.created_by_id,
            "updated_by_id": source.updated_by_id,
        }
        for module_key in TARGET_MODULES:
            RoleModuleAccess.objects.get_or_create(
                role=role,
                module_key=module_key,
                defaults=defaults,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_diary_configuration_create_access"),
    ]

    operations = [
        migrations.RunPython(copy_calendar_management_access, migrations.RunPython.noop),
    ]
