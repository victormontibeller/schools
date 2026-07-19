from django.db import migrations


def enable_create_for_previous_defaults(apps, schema_editor):
    """Libera cadastro apenas nas políticas que ainda correspondem ao padrão anterior."""
    RoleModuleAccess = apps.get_model("core", "RoleModuleAccess")
    RoleModuleAccess.objects.filter(
        module_key="diary_configuration",
        role__name__in=["SECRETARY", "COORDINATOR"],
        can_view=True,
        can_create=False,
        can_edit=True,
        can_deactivate=False,
    ).update(can_create=True)


class Migration(migrations.Migration):
    dependencies = [("core", "0003_secretaria_rooms_diary_configuration_access")]

    operations = [
        migrations.RunPython(enable_create_for_previous_defaults, migrations.RunPython.noop),
    ]
