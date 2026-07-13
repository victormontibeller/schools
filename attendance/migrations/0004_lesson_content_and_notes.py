"""Preserva observações antigas como conteúdo ministrado."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Renomeia o campo legado e cria observações opcionais separadas."""

    dependencies = [("attendance", "0003_attendanceentry_note")]

    operations = [
        migrations.RenameField(
            model_name="attendancerecord",
            old_name="notes",
            new_name="lesson_content",
        ),
        migrations.AlterField(
            model_name="attendancerecord",
            name="lesson_content",
            field=models.TextField(verbose_name="Conteúdo Ministrado"),
        ),
        migrations.AddField(
            model_name="attendancerecord",
            name="notes",
            field=models.TextField(blank=True, default="", verbose_name="Observações"),
        ),
    ]
