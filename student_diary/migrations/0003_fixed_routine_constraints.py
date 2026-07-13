from django.db import migrations, models


class Migration(migrations.Migration):
    """Cria índices após a carga, evitando triggers pendentes no PostgreSQL."""

    dependencies = [("student_diary", "0002_fixed_routine_aspects")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'CREATE UNIQUE INDEX IF NOT EXISTS '
                        '"unique_active_diary_category_code" '
                        'ON "student_diary_diarycategory" ("code") '
                        'WHERE "code" IS NOT NULL AND "deleted_at" IS NULL '
                        'AND "is_active"'
                    ),
                    reverse_sql=(
                        'DROP INDEX IF EXISTS "unique_active_diary_category_code"'
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        'CREATE UNIQUE INDEX IF NOT EXISTS '
                        '"unique_active_diary_option_code" '
                        'ON "student_diary_diaryoption" ("category_id", "code") '
                        'WHERE "code" IS NOT NULL AND "deleted_at" IS NULL '
                        'AND "is_active"'
                    ),
                    reverse_sql=(
                        'DROP INDEX IF EXISTS "unique_active_diary_option_code"'
                    ),
                ),
            ],
            state_operations=[
                migrations.AddConstraint(
                    model_name="diarycategory",
                    constraint=models.UniqueConstraint(
                        condition=models.Q(
                            code__isnull=False,
                            deleted_at__isnull=True,
                            is_active=True,
                        ),
                        fields=("code",),
                        name="unique_active_diary_category_code",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="diaryoption",
                    constraint=models.UniqueConstraint(
                        condition=models.Q(
                            code__isnull=False,
                            deleted_at__isnull=True,
                            is_active=True,
                        ),
                        fields=("category", "code"),
                        name="unique_active_diary_option_code",
                    ),
                ),
            ],
        )
    ]
