"""Popula o catálogo compartilhado de estados e municípios brasileiros."""

import json
from pathlib import Path

from django.db import migrations


def seed_locations(apps, schema_editor):
    """Carrega o catálogo IBGE no schema compartilhado."""
    State = apps.get_model("locations", "State")
    City = apps.get_model("locations", "City")
    state_manager = State._base_manager
    city_manager = City._base_manager

    data_path = Path(__file__).resolve().parents[1] / "data" / "brazil_locations.json"
    with data_path.open(encoding="utf-8") as fixture:
        payload = json.load(fixture)

    state_map = {}
    for item in payload["states"]:
        state, _ = state_manager.update_or_create(
            code=item["code"],
            defaults={
                "name": item["name"],
                "is_active": True,
                "deleted_at": None,
                "deleted_by": None,
            },
        )
        state_map[item["code"]] = state

    for state_code, cities in payload["cities"].items():
        state = state_map[state_code]
        for item in cities:
            city_manager.update_or_create(
                ibge_code=item["ibge_code"],
                defaults={
                    "state": state,
                    "name": item["name"],
                    "is_active": True,
                    "deleted_at": None,
                    "deleted_by": None,
                },
            )


def unseed_locations(apps, schema_editor):
    """Remove o catálogo ao reverter o baseline local."""
    City = apps.get_model("locations", "City")
    State = apps.get_model("locations", "State")

    City._base_manager.all().delete()
    State._base_manager.all().delete()


class Migration(migrations.Migration):
    dependencies = [("locations", "0001_initial")]

    operations = [migrations.RunPython(seed_locations, unseed_locations)]
