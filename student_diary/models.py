"""Modelos da agenda diária da Educação Infantil."""

from django.conf import settings
from django.db import models

from base.models import BaseModel


class DiaryCategory(BaseModel):
    """Categoria configurável de acompanhamento diário."""

    class Section(models.TextChoices):
        ROUTINE = "ROUTINE", "Como foi o dia"
        MEAL = "MEAL", "Alimentação"

    name = models.CharField(max_length=100, verbose_name="Nome")
    section = models.CharField(
        max_length=12,
        choices=Section.choices,
        default=Section.ROUTINE,
        verbose_name="Seção",
    )
    display_order = models.PositiveSmallIntegerField(default=0, verbose_name="Ordem")
    is_required = models.BooleanField(default=True, verbose_name="Resposta obrigatória")
    is_enabled = models.BooleanField(default=True, verbose_name="Ativo na Agenda")
    applies_morning = models.BooleanField(default=True, verbose_name="Manhã")
    applies_afternoon = models.BooleanField(default=True, verbose_name="Tarde")
    applies_full = models.BooleanField(default=True, verbose_name="Integral")

    class Meta:
        ordering = ["section", "display_order", "name"]
        verbose_name = "Categoria da Agenda"
        verbose_name_plural = "Categorias da Agenda"
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(is_active=True, deleted_at__isnull=True),
                name="unique_active_diary_category_name",
            ),
        ]
        indexes = [models.Index(fields=["section", "display_order", "is_active"])]

    def __str__(self) -> str:
        """Retorna o nome da categoria."""
        return self.name


class DiaryOption(BaseModel):
    """Opção de resposta única de uma categoria."""

    category = models.ForeignKey(
        DiaryCategory,
        on_delete=models.CASCADE,
        related_name="options",
        verbose_name="Categoria",
    )
    label = models.CharField(max_length=100, verbose_name="Opção")
    display_order = models.PositiveSmallIntegerField(default=0, verbose_name="Ordem")
    is_enabled = models.BooleanField(default=True, verbose_name="Disponível na Agenda")

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
        ]
        indexes = [models.Index(fields=["category", "display_order"])]

    def __str__(self) -> str:
        """Retorna categoria e rótulo da opção."""
        return f"{self.category} · {self.label}"


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


class DiarySheet(BaseModel):
    """Controla o workflow da agenda de uma turma em uma data."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        PENDING_REVIEW = "PENDING_REVIEW", "Em revisão"
        CHANGES_REQUESTED = "CHANGES_REQUESTED", "Devolvido para correção"
        PUBLISHED = "PUBLISHED", "Publicado"

    class_obj = models.ForeignKey(
        "classes.Class",
        on_delete=models.PROTECT,  # A revisão publicada preserva a turma de origem.
        related_name="diary_sheets",
        verbose_name="Turma",
    )
    date = models.DateField(verbose_name="Data")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    review_feedback = models.TextField(blank=True, default="", verbose_name="Motivo da devolução")
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name="Enviado em")
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submitted_diary_sheets",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Revisado em")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_diary_sheets",
    )

    class Meta:
        ordering = ["-date", "class_obj__name"]
        verbose_name = "Folha da Agenda"
        verbose_name_plural = "Folhas da Agenda"
        constraints = [
            models.UniqueConstraint(
                fields=["class_obj", "date"],
                condition=models.Q(is_active=True, deleted_at__isnull=True),
                name="unique_active_diary_sheet",
            )
        ]
        indexes = [models.Index(fields=["status", "date"]), models.Index(fields=["class_obj"])]

    def __str__(self) -> str:
        """Representa a folha sem expor dados pessoais."""
        return f"{self.class_obj_id} · {self.date} · {self.status}"


class DiaryPublication(BaseModel):
    """Revisão imutável publicada de uma folha diária."""

    sheet = models.ForeignKey(
        DiarySheet,
        on_delete=models.PROTECT,  # Publicações não podem desaparecer com o rascunho.
        related_name="publications",
    )
    revision_number = models.PositiveSmallIntegerField(verbose_name="Revisão")
    published_at = models.DateTimeField(verbose_name="Publicado em")
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="published_diary_revisions",
    )

    class Meta:
        ordering = ["-revision_number"]
        verbose_name = "Publicação da Agenda"
        verbose_name_plural = "Publicações da Agenda"
        constraints = [
            models.UniqueConstraint(
                fields=["sheet", "revision_number"], name="unique_diary_publication_revision"
            )
        ]
        indexes = [models.Index(fields=["sheet", "-revision_number"])]

    def __str__(self) -> str:
        """Representa a revisão publicada."""
        return f"{self.sheet_id} · revisão {self.revision_number}"


class DiaryPublishedEntry(BaseModel):
    """Snapshot imutável da agenda publicada para uma criança."""

    publication = models.ForeignKey(
        DiaryPublication,
        on_delete=models.PROTECT,  # O snapshot compõe o histórico publicado.
        related_name="entries",
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,  # O histórico permanece mesmo após a matrícula.
        related_name="published_diary_entries",
    )
    answers_snapshot = models.JSONField(default=list, verbose_name="Respostas publicadas")
    notes = models.TextField(blank=True, default="", verbose_name="Observações")

    class Meta:
        ordering = ["-publication__published_at"]
        verbose_name = "Agenda Publicada do Aluno"
        verbose_name_plural = "Agendas Publicadas dos Alunos"
        constraints = [
            models.UniqueConstraint(
                fields=["publication", "student"], name="unique_diary_publication_student"
            )
        ]
        indexes = [models.Index(fields=["student", "publication"])]

    def __str__(self) -> str:
        """Representa o snapshot sem conteúdo pessoal."""
        return f"{self.publication_id} · {self.student_id}"


class DiaryViewReceipt(BaseModel):
    """Destinatário e visualização de uma agenda; não representa resposta."""

    entry = models.ForeignKey(
        DiaryPublishedEntry,
        on_delete=models.PROTECT,  # Evidência de entrega acompanha a publicação.
        related_name="view_receipts",
    )
    guardian = models.ForeignKey(
        "guardians.Guardian",
        on_delete=models.PROTECT,  # Preserva a evidência histórica de destinatário.
        related_name="diary_view_receipts",
    )
    notification_id = models.UUIDField(null=True, blank=True, verbose_name="Notificação interna")
    first_viewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Primeira abertura")
    last_viewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Última abertura")
    view_count = models.PositiveIntegerField(default=0, verbose_name="Visualizações")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Visualização da Agenda"
        verbose_name_plural = "Visualizações da Agenda"
        constraints = [
            models.UniqueConstraint(
                fields=["entry", "guardian"],
                condition=models.Q(is_active=True, deleted_at__isnull=True),
                name="unique_active_diary_entry_guardian",
            )
        ]
        indexes = [
            models.Index(fields=["guardian", "first_viewed_at"]),
            models.Index(fields=["entry"]),
        ]

    def __str__(self) -> str:
        """Representa o recibo por identificadores opacos."""
        return f"{self.entry_id} · {self.guardian_id}"


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
        ordering = ["category__section", "category__display_order", "category__name"]
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
