"""Cria somente os aspectos estruturados da agenda diária."""

from django.db import migrations

ASPECTS = (
    ("MOOD", ("MOOD_HAPPY", "MOOD_CALM", "MOOD_AGITATED", "MOOD_IRRITATED", "MOOD_TEARFUL", "MOOD_SLEEPY")),
    ("REST", ("REST_SLEPT_WELL", "REST_RESTLESS", "REST_ONLY_RESTED", "REST_NO_SLEEP")),
    ("BOWEL_MOVEMENT", ("BOWEL_NONE", "BOWEL_NORMAL", "BOWEL_SOFT", "BOWEL_LIQUID")),
    ("PARTICIPATION", ("PARTICIPATED_WELL", "PARTICIPATED_PART", "DID_NOT_PARTICIPATE")),
)


def seed_fixed_aspects(apps, schema_editor):
    Category = apps.get_model("student_diary", "DiaryCategory")
    Option = apps.get_model("student_diary", "DiaryOption")
    category_labels = dict(Category._meta.get_field("code").choices)
    option_labels = dict(Option._meta.get_field("code").choices)
    for order, (code, options) in enumerate(ASPECTS, start=1):
        category, _ = Category._base_manager.update_or_create(
            code=code,
            defaults={"name": category_labels[code], "display_order": order, "is_required": True, "is_enabled": True, "is_active": True},
        )
        for option_order, option_code in enumerate(options, start=1):
            Option._base_manager.update_or_create(
                category=category,
                code=option_code,
                defaults={"label": option_labels[option_code], "display_order": option_order, "is_active": True},
            )


class Migration(migrations.Migration):
    dependencies = [("student_diary", "0001_initial")]
    operations = [migrations.RunPython(seed_fixed_aspects, migrations.RunPython.noop)]
