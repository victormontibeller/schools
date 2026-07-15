"""Modelos da agenda diária da Educação Infantil."""

from django.db import models

from base.models import BaseModel


class DiaryCategory(BaseModel):
    """Categoria configurável de acompanhamento diário."""

    class Aspect(models.TextChoices):
        MOOD = "MOOD", "Humor"
        REST = "REST", "Descanso"
        BOWEL_MOVEMENT = "BOWEL_MOVEMENT", "Evacuação"
        PARTICIPATION = "PARTICIPATION", "Participação"

    name = models.CharField(max_length=100, verbose_name="Nome")
    code = models.CharField(
        max_length=20,
        choices=Aspect.choices,
        unique=True,
        verbose_name="Aspecto estruturado",
    )
    display_order = models.PositiveSmallIntegerField(default=0, verbose_name="Ordem")
    is_required = models.BooleanField(default=False, verbose_name="Obrigatória")
    is_enabled = models.BooleanField(default=True, verbose_name="Ativo na rotina")

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "Categoria da Agenda"
        verbose_name_plural = "Categorias da Agenda"
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(is_active=True, deleted_at__isnull=True),
                name="unique_active_diary_category_name",
            ),
        ]
        indexes = [models.Index(fields=["display_order", "is_active"])]

    def __str__(self) -> str:
        """Retorna o nome da categoria."""
        return self.name


class DiaryOption(BaseModel):
    """Opção de resposta única de uma categoria."""

    class FixedCode(models.TextChoices):
        MOOD_HAPPY = "MOOD_HAPPY", "Alegre"
        MOOD_CALM = "MOOD_CALM", "Tranquilo"
        MOOD_AGITATED = "MOOD_AGITATED", "Agitado"
        MOOD_IRRITATED = "MOOD_IRRITATED", "Irritado"
        MOOD_TEARFUL = "MOOD_TEARFUL", "Choroso"
        MOOD_SLEEPY = "MOOD_SLEEPY", "Sonolento"
        REST_SLEPT_WELL = "REST_SLEPT_WELL", "Dormiu bem"
        REST_RESTLESS_SLEEP = "REST_RESTLESS", "Sono agitado"
        REST_ONLY_RESTED = "REST_ONLY_RESTED", "Apenas descansou"
        REST_DID_NOT_SLEEP = "REST_NO_SLEEP", "Não dormiu"
        BOWEL_NONE = "BOWEL_NONE", "Não evacuou"
        BOWEL_NORMAL = "BOWEL_NORMAL", "Normal"
        BOWEL_SOFT = "BOWEL_SOFT", "Pastosa"
        BOWEL_LIQUID = "BOWEL_LIQUID", "Líquida"
        PARTICIPATED_WELL = "PARTICIPATED_WELL", "Participou bem"
        PARTICIPATED_PARTIALLY = "PARTICIPATED_PART", "Participou parcialmente"
        DID_NOT_WANT_TO_PARTICIPATE = "DID_NOT_PARTICIPATE", "Não quis participar"

    category = models.ForeignKey(
        DiaryCategory,
        on_delete=models.CASCADE,
        related_name="options",
        verbose_name="Categoria",
    )
    label = models.CharField(max_length=100, verbose_name="Opção")
    code = models.CharField(
        max_length=24,
        choices=FixedCode.choices,
        verbose_name="Opção estruturada",
    )
    display_order = models.PositiveSmallIntegerField(default=0, verbose_name="Ordem")

    class Meta:
        ordering = ["display_order", "label"]
        verbose_name = "Opção da Agenda"
        verbose_name_plural = "Opções da Agenda"
        constraints = [
            models.UniqueConstraint(
                fields=["category", "label"],
                condition=models.Q(is_active=True, deleted_at__isnull=True),
                name="unique_active_diary_category_option",
            ),
            models.UniqueConstraint(
                fields=["category", "code"],
                condition=models.Q(is_active=True, deleted_at__isnull=True),
                name="unique_active_diary_option_code",
            ),
        ]
        indexes = [models.Index(fields=["category", "display_order"])]

    def __str__(self) -> str:
        """Retorna categoria e rótulo da opção."""
        return f"{self.category} · {self.label}"


ROUTINE_ASPECT_DEFINITIONS = (
    (
        DiaryCategory.Aspect.MOOD,
        1,
        (
            DiaryOption.FixedCode.MOOD_HAPPY,
            DiaryOption.FixedCode.MOOD_CALM,
            DiaryOption.FixedCode.MOOD_AGITATED,
            DiaryOption.FixedCode.MOOD_IRRITATED,
            DiaryOption.FixedCode.MOOD_TEARFUL,
            DiaryOption.FixedCode.MOOD_SLEEPY,
        ),
    ),
    (
        DiaryCategory.Aspect.REST,
        2,
        (
            DiaryOption.FixedCode.REST_SLEPT_WELL,
            DiaryOption.FixedCode.REST_RESTLESS_SLEEP,
            DiaryOption.FixedCode.REST_ONLY_RESTED,
            DiaryOption.FixedCode.REST_DID_NOT_SLEEP,
        ),
    ),
    (
        DiaryCategory.Aspect.BOWEL_MOVEMENT,
        3,
        (
            DiaryOption.FixedCode.BOWEL_NONE,
            DiaryOption.FixedCode.BOWEL_NORMAL,
            DiaryOption.FixedCode.BOWEL_SOFT,
            DiaryOption.FixedCode.BOWEL_LIQUID,
        ),
    ),
    (
        DiaryCategory.Aspect.PARTICIPATION,
        4,
        (
            DiaryOption.FixedCode.PARTICIPATED_WELL,
            DiaryOption.FixedCode.PARTICIPATED_PARTIALLY,
            DiaryOption.FixedCode.DID_NOT_WANT_TO_PARTICIPATE,
        ),
    ),
)


class DailyDiary(BaseModel):
    """Registro diário individual de uma criança."""

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="daily_diaries",
        verbose_name="Aluno",
    )
    class_obj = models.ForeignKey(
        "classes.Class",
        on_delete=models.CASCADE,
        related_name="daily_diaries",
        verbose_name="Turma",
    )
    teacher = models.ForeignKey(
        "teachers.Teacher",
        on_delete=models.PROTECT,
        related_name="daily_diaries",
        verbose_name="Professor",
        null=True,
        blank=True,
    )
    date = models.DateField(verbose_name="Data")
    notes = models.TextField(blank=True, default="", verbose_name="Observações")

    class Meta:
        ordering = ["-date", "student__first_name"]
        verbose_name = "Agenda Diária"
        verbose_name_plural = "Agendas Diárias"
        constraints = [
            models.UniqueConstraint(
                fields=["student", "class_obj", "date"],
                condition=models.Q(is_active=True, deleted_at__isnull=True),
                name="unique_active_student_daily_diary",
            )
        ]
        indexes = [
            models.Index(fields=["class_obj", "date"]),
            models.Index(fields=["student", "date"]),
        ]

    def __str__(self) -> str:
        """Retorna aluno, turma e data da agenda."""
        return f"{self.student} · {self.class_obj} · {self.date}"


class DiaryAnswer(BaseModel):
    """Resposta selecionada para uma categoria da agenda."""

    diary = models.ForeignKey(
        DailyDiary,
        on_delete=models.CASCADE,
        related_name="answers",
        verbose_name="Agenda",
    )
    category = models.ForeignKey(
        DiaryCategory,
        on_delete=models.PROTECT,
        related_name="answers",
        verbose_name="Categoria",
    )
    option = models.ForeignKey(
        DiaryOption,
        on_delete=models.PROTECT,
        related_name="answers",
        verbose_name="Opção",
    )

    class Meta:
        ordering = ["category__display_order"]
        verbose_name = "Resposta da Agenda"
        verbose_name_plural = "Respostas da Agenda"
        constraints = [
            models.UniqueConstraint(
                fields=["diary", "category"],
                condition=models.Q(is_active=True, deleted_at__isnull=True),
                name="unique_active_diary_category_answer",
            )
        ]
        indexes = [models.Index(fields=["diary", "category"])]

    def __str__(self) -> str:
        """Retorna a resposta selecionada."""
        return f"{self.diary} · {self.option}"


class DiaryMeal(BaseModel):
    """Resultado de uma refeição prevista para o turno."""

    class MealType(models.TextChoices):
        MORNING_SNACK = "MORNING_SNACK", "Café da manhã"
        LUNCH = "LUNCH", "Almoço"
        AFTERNOON_SNACK = "AFTERNOON_SNACK", "Café da tarde"

    class Status(models.TextChoices):
        ATE_WELL = "ATE_WELL", "Comeu bem"
        ATE_PARTIALLY = "ATE_PARTIALLY", "Comeu parcialmente"
        DID_NOT_EAT = "DID_NOT_EAT", "Não comeu"
        NOT_PRESENT = "NOT_PRESENT", "Não estava presente"

    diary = models.ForeignKey(
        DailyDiary,
        on_delete=models.CASCADE,
        related_name="meals",
        verbose_name="Agenda",
    )
    meal_type = models.CharField(max_length=20, choices=MealType.choices, verbose_name="Refeição")
    status = models.CharField(max_length=20, choices=Status.choices, verbose_name="Situação")

    class Meta:
        ordering = ["meal_type"]
        verbose_name = "Alimentação da Agenda"
        verbose_name_plural = "Alimentações da Agenda"
        constraints = [
            models.UniqueConstraint(
                fields=["diary", "meal_type"],
                condition=models.Q(is_active=True, deleted_at__isnull=True),
                name="unique_active_diary_meal",
            )
        ]
        indexes = [models.Index(fields=["diary", "meal_type"])]

    def __str__(self) -> str:
        """Retorna refeição e resultado."""
        return f"{self.diary} · {self.get_meal_type_display()}"
