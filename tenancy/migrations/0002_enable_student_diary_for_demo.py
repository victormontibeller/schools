"""Ativa o workflow da Agenda apenas no tenant de demonstração configurado."""

from django.conf import settings
from django.db import migrations


def enable_demo_student_diary(apps, schema_editor):
    """Mescla o flag sem apagar outras configurações da escola demo."""
    School = apps.get_model("tenancy", "School")
    schema_name = getattr(settings, "DEMO_SCHEMA_NAME", "demo")
    school = School.objects.filter(schema_name=schema_name).first()
    if school is None:
        return
    school_settings = dict(school.settings or {})
    diary_settings = dict(school_settings.get("student_diary", {}))
    diary_settings["interactive_enabled"] = True
    school_settings["student_diary"] = diary_settings
    if school.settings != school_settings:
        school.settings = school_settings
        school.save(update_fields=["settings"])


class Migration(migrations.Migration):
    """Aplica reconciliação segura do flag de rollout."""

    dependencies = [("tenancy", "0001_initial")]

    operations = [migrations.RunPython(enable_demo_student_diary, migrations.RunPython.noop)]
