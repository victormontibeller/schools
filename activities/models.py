"""Modelos do módulo de atividades e avaliações."""

from django.db import models

from base.models import BaseModel


class Activity(BaseModel):
    """Atividade/avaliação atribuída a uma turma por um professor."""

    class Type(models.TextChoices):
        HOMEWORK = "HOMEWORK", "Tarefa"
        EXAM = "EXAM", "Prova"
        PROJECT = "PROJECT", "Trabalho"
        PARTICIPATION = "PARTICIPATION", "Participação"

    class_obj = models.ForeignKey(
        "classes.Class",
        on_delete=models.CASCADE,
        related_name="activities",
        verbose_name="Turma",
    )
    subject = models.ForeignKey(
        "teachers.Subject",
        on_delete=models.PROTECT,
        related_name="activities",
        verbose_name="Disciplina",
    )
    teacher = models.ForeignKey(
        "teachers.Teacher",
        on_delete=models.PROTECT,
        related_name="activities",
        verbose_name="Professor",
    )
    title = models.CharField(max_length=200, verbose_name="Título")
    description = models.TextField(blank=True, default="", verbose_name="Descrição")
    type = models.CharField(
        max_length=20, choices=Type.choices, default=Type.HOMEWORK, verbose_name="Tipo"
    )
    due_date = models.DateField(verbose_name="Data de Entrega")
    max_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=10.00, verbose_name="Nota Máxima"
    )
    weight = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.00, verbose_name="Peso na Média"
    )

    class Meta:
        ordering = ["-due_date", "title"]
        verbose_name = "Atividade"
        verbose_name_plural = "Atividades"

    def __str__(self) -> str:
        """Retorna a identificação curta da atividade."""
        return f"{self.title} · {self.class_obj} · {self.get_type_display()}"


class ActivitySubmission(BaseModel):
    """Entrega/nota de um aluno a uma atividade."""

    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="Atividade",
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="Aluno",
    )
    score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Nota"
    )
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name="Entregue em")
    feedback = models.TextField(blank=True, default="", verbose_name="Feedback")

    class Meta:
        verbose_name = "Entrega"
        verbose_name_plural = "Entregas"
        ordering = ["-submitted_at"]
        unique_together = [("activity", "student")]

    def __str__(self) -> str:
        """Retorna a identificação curta da entrega."""
        return f"{self.student} — {self.activity.title} ({self.score})"
