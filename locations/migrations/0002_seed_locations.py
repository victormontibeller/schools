"""Carrega o catálogo estrutural atual de estados e municípios."""

import json
from pathlib import Path

from django.db import migrations


def seed_locations(apps, schema_editor):
    State = apps.get_model("locations", "State")
    City = apps.get_model("locations", "City")
    data_path = Path(__file__).resolve().parents[1] / "data" / "brazil_locations.json"
    with data_path.open(encoding="utf-8") as fixture:
        payload = json.load(fixture)
    states = {}
    for item in payload["states"]:
        state, _ = State._base_manager.update_or_create(
            code=item["code"], defaults={"name": item["name"], "is_active": True}
        )
        states[item["code"]] = state
    for state_code, cities in payload["cities"].items():
        for item in cities:
            City._base_manager.update_or_create(
                ibge_code=item["ibge_code"],
                defaults={"state": states[state_code], "name": item["name"], "is_active": True},
            )


class Migration(migrations.Migration):
    dependencies = [("locations", "0001_initial")]
    operations = [migrations.RunPython(seed_locations, migrations.RunPython.noop)]
