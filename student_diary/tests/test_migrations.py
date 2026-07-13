"""Testes da migração do catálogo fixo da Agenda."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_fixed_aspects_migration_preserves_legacy_category():
    executor = MigrationExecutor(connection)
    final_targets = executor.loader.graph.leaf_nodes()
    executor.migrate([("student_diary", "0001_initial")])
    try:
        old_apps = executor.loader.project_state([("student_diary", "0001_initial")]).apps
        old_category_model = old_apps.get_model("student_diary", "DiaryCategory")
        old_category_model.objects.all().delete()
        old_category_model.objects.create(name="Humor", display_order=99, is_required=False)

        executor = MigrationExecutor(connection)
        executor.migrate([("student_diary", "0002_fixed_routine_aspects")])
        new_apps = executor.loader.project_state(
            [("student_diary", "0002_fixed_routine_aspects")]
        ).apps
        category_model = new_apps.get_model("student_diary", "DiaryCategory")
        option_model = new_apps.get_model("student_diary", "DiaryOption")

        assert category_model.objects.filter(code__isnull=False).count() == 4
        assert option_model.objects.filter(code__isnull=False).count() == 17
        assert category_model.objects.filter(name__startswith="Humor (legado", code=None).exists()
    finally:
        MigrationExecutor(connection).migrate(final_targets)
