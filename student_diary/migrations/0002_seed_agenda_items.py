"""Cria o catálogo inicial configurável da Agenda em cada tenant."""

from django.db import migrations


AGENDA_ITEMS = (
    (
        "Humor",
        "ROUTINE",
        1,
        (True, True, True),
        ("Alegre", "Tranquilo", "Agitado", "Irritado", "Choroso", "Sonolento"),
    ),
    (
        "Descanso",
        "ROUTINE",
        2,
        (True, True, True),
        ("Dormiu bem", "Sono agitado", "Apenas descansou", "Não dormiu"),
    ),
    (
        "Evacuação",
        "ROUTINE",
        3,
        (True, True, True),
        ("Não evacuou", "Normal", "Pastosa", "Líquida"),
    ),
    (
        "Participação",
        "ROUTINE",
        4,
        (True, True, True),
        ("Participou bem", "Participou parcialmente", "Não quis participar"),
    ),
    (
        "Café da manhã",
        "MEAL",
        1,
        (True, False, True),
        ("Comeu bem", "Comeu parcialmente", "Não comeu", "Não estava presente"),
    ),
    (
        "Almoço",
        "MEAL",
        2,
        (True, True, True),
        ("Comeu bem", "Comeu parcialmente", "Não comeu", "Não estava presente"),
    ),
    (
        "Café da tarde",
        "MEAL",
        3,
        (False, True, True),
        ("Comeu bem", "Comeu parcialmente", "Não comeu", "Não estava presente"),
    ),
)


def seed_agenda_items(apps, schema_editor):
    """Insere os sete itens iniciais no schema em criação."""
    Category = apps.get_model("student_diary", "DiaryCategory")
    Option = apps.get_model("student_diary", "DiaryOption")

    for name, section, order, shifts, option_labels in AGENDA_ITEMS:
        category = Category._base_manager.create(
            name=name,
            section=section,
            display_order=order,
            is_required=True,
            is_enabled=True,
            applies_morning=shifts[0],
            applies_afternoon=shifts[1],
            applies_full=shifts[2],
        )
        for option_order, label in enumerate(option_labels, start=1):
            Option._base_manager.create(
                category_id=category.pk,
                label=label,
                display_order=option_order,
                is_enabled=True,
            )


class Migration(migrations.Migration):
    dependencies = [("student_diary", "0001_initial")]
    operations = [migrations.RunPython(seed_agenda_items, migrations.RunPython.noop)]
