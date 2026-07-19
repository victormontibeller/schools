from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("student_diary", "0003_diarypublication_diarypublishedentry_diarysheet_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="diarycategory",
            name="code",
            field=models.CharField(
                blank=True,
                choices=[
                    ("MOOD", "Humor"),
                    ("REST", "Descanso"),
                    ("BOWEL_MOVEMENT", "Evacuação"),
                    ("PARTICIPATION", "Participação"),
                ],
                default=None,
                max_length=20,
                null=True,
                unique=True,
                verbose_name="Aspecto estruturado",
            ),
        ),
        migrations.AlterField(
            model_name="diarycategory",
            name="is_required",
            field=models.BooleanField(default=True, verbose_name="Resposta obrigatória"),
        ),
        migrations.AlterField(
            model_name="diaryoption",
            name="code",
            field=models.CharField(
                blank=True,
                choices=[
                    ("MOOD_HAPPY", "Alegre"),
                    ("MOOD_CALM", "Tranquilo"),
                    ("MOOD_AGITATED", "Agitado"),
                    ("MOOD_IRRITATED", "Irritado"),
                    ("MOOD_TEARFUL", "Choroso"),
                    ("MOOD_SLEEPY", "Sonolento"),
                    ("REST_SLEPT_WELL", "Dormiu bem"),
                    ("REST_RESTLESS", "Sono agitado"),
                    ("REST_ONLY_RESTED", "Apenas descansou"),
                    ("REST_NO_SLEEP", "Não dormiu"),
                    ("BOWEL_NONE", "Não evacuou"),
                    ("BOWEL_NORMAL", "Normal"),
                    ("BOWEL_SOFT", "Pastosa"),
                    ("BOWEL_LIQUID", "Líquida"),
                    ("PARTICIPATED_WELL", "Participou bem"),
                    ("PARTICIPATED_PART", "Participou parcialmente"),
                    ("DID_NOT_PARTICIPATE", "Não quis participar"),
                ],
                default=None,
                max_length=24,
                null=True,
                verbose_name="Opção estruturada",
            ),
        ),
        migrations.AddField(
            model_name="diaryoption",
            name="is_enabled",
            field=models.BooleanField(default=True, verbose_name="Disponível na rotina"),
        ),
    ]
