from django.db import migrations


def reconcile_secretary_access(apps, schema_editor):
    """Concede os novos padrões sem revogar permissões existentes de Salas."""
    Role = apps.get_model("core", "Role")
    RoleModuleAccess = apps.get_model("core", "RoleModuleAccess")

    secretary = Role.objects.filter(name="SECRETARY").first()
    if secretary:
        rooms_access, _ = RoleModuleAccess.objects.get_or_create(
            role=secretary,
            module_key="rooms",
        )
        rooms_access.can_view = True
        rooms_access.can_create = True
        rooms_access.can_edit = True
        rooms_access.save(update_fields=["can_view", "can_create", "can_edit", "updated_at"])

        diary_access, _ = RoleModuleAccess.objects.get_or_create(
            role=secretary,
            module_key="diary_configuration",
        )
        diary_access.can_view = True
        diary_access.can_create = False
        diary_access.can_edit = True
        diary_access.can_deactivate = False
        diary_access.save(
            update_fields=[
                "can_view",
                "can_create",
                "can_edit",
                "can_deactivate",
                "updated_at",
            ]
        )

    coordinator = Role.objects.filter(name="COORDINATOR").first()
    if coordinator:
        diary_access, _ = RoleModuleAccess.objects.get_or_create(
            role=coordinator,
            module_key="diary_configuration",
        )
        diary_access.can_view = True
        diary_access.can_create = False
        diary_access.can_edit = True
        diary_access.can_deactivate = False
        diary_access.save(
            update_fields=[
                "can_view",
                "can_create",
                "can_edit",
                "can_deactivate",
                "updated_at",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_remove_role_permissions_rolemoduleaccess"),
    ]

    operations = [
        migrations.RunPython(reconcile_secretary_access, migrations.RunPython.noop),
    ]
