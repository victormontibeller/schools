"""Modelos do modulo de notificacoes e comunicacao."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from base.models import BaseModel


class MessageTemplate(BaseModel):
    """Template de mensagem reutilizavel com variaveis dinamicas {{ variavel }}."""

    class Channel(models.TextChoices):
        EMAIL = "EMAIL", "E-mail"
        WHATSAPP = "WHATSAPP", "WhatsApp"

    class Type(models.TextChoices):
        WELCOME = "WELCOME", "Boas-vindas"
        ATTENDANCE_ALERT = "ATTENDANCE_ALERT", "Alerta de Frequencia"
        NEW_ACTIVITY = "NEW_ACTIVITY", "Nova Atividade"
        EVENT_REMINDER = "EVENT_REMINDER", "Lembrete de Evento"
        CUSTOM = "CUSTOM", "Personalizado"

    name: str = models.CharField(max_length=100, verbose_name="Nome")
    channel: str = models.CharField(
        max_length=20, choices=Channel.choices, default=Channel.EMAIL, verbose_name="Canal"
    )
    type: str = models.CharField(
        max_length=30, choices=Type.choices, default=Type.CUSTOM, verbose_name="Tipo"
    )
    subject: str = models.CharField(max_length=200, blank=True, default="", verbose_name="Assunto")
    body: str = models.TextField(verbose_name="Corpo")
    variables: dict = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Variaveis disponiveis",
        help_text="Ex: {'nome': 'Nome do destinatario', 'escola': 'Nome da escola'}",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Template de Mensagem"
        verbose_name_plural = "Templates de Mensagem"
        unique_together = [("name", "channel")]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_channel_display()})"


class Announcement(BaseModel):
    """Comunicado institucional enviado a um grupo de destinatarios."""

    class Audience(models.TextChoices):
        ALL = "ALL", "Todos"
        TEACHERS = "TEACHERS", "Professores"
        STUDENTS = "STUDENTS", "Alunos"
        GUARDIANS = "GUARDIANS", "Responsaveis"
        CLASS = "CLASS", "Turma especifica"

    title: str = models.CharField(max_length=200, verbose_name="Titulo")
    body: str = models.TextField(verbose_name="Mensagem")
    audience: str = models.CharField(
        max_length=20, choices=Audience.choices, default=Audience.ALL, verbose_name="Publico-alvo"
    )
    class_obj: models.ForeignKey | None = models.ForeignKey(
        "classes.Class",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="announcements",
        verbose_name="Turma",
    )
    author: models.ForeignKey = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="announcements",
        verbose_name="Autor",
    )
    send_email: bool = models.BooleanField(default=False, verbose_name="Enviar por E-mail")
    send_whatsapp: bool = models.BooleanField(default=False, verbose_name="Enviar por WhatsApp")
    scheduled_at: models.DateTimeField | None = models.DateTimeField(
        null=True, blank=True, verbose_name="Agendado para"
    )
    sent_at: models.DateTimeField | None = models.DateTimeField(
        null=True, blank=True, verbose_name="Enviado em"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Comunicado"
        verbose_name_plural = "Comunicados"

    def __str__(self) -> str:
        return f"{self.title} ({self.get_audience_display()})"

    @property
    def is_sent(self) -> bool:
        return self.sent_at is not None


class Notification(BaseModel):
    """Notificacao individual enviada a um usuario especifico."""

    class Type(models.TextChoices):
        INFO = "INFO", "Informativa"
        ALERT = "ALERT", "Alerta"
        CRITICAL = "CRITICAL", "Critico"
        SUCCESS = "SUCCESS", "Sucesso"

    recipient: models.ForeignKey = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Destinatario",
    )
    type: str = models.CharField(
        max_length=20, choices=Type.choices, default=Type.INFO, verbose_name="Tipo"
    )
    title: str = models.CharField(max_length=200, verbose_name="Titulo")
    message: str = models.TextField(verbose_name="Mensagem")
    source: str = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="Origem",
        help_text="Modulo que gerou a notificacao (attendance, activities, calendar, etc.)",
    )
    action_url: str = models.CharField(
        max_length=500, blank=True, default="", verbose_name="Link de acao"
    )
    read_at: models.DateTimeField | None = models.DateTimeField(
        null=True, blank=True, verbose_name="Lida em"
    )
    correlation_id: str = models.CharField(
        max_length=64, blank=True, default="", verbose_name="ID de correlacao"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Notificacao"
        verbose_name_plural = "Notificacoes"
        indexes = [
            models.Index(fields=["recipient", "read_at"]),
            models.Index(fields=["recipient", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"[{self.get_type_display()}] {self.title}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


class MessageLog(BaseModel):
    """Log de envio de mensagem — rastreabilidade de cada disparo."""

    class Channel(models.TextChoices):
        EMAIL = "EMAIL", "E-mail"
        WHATSAPP = "WHATSAPP", "WhatsApp"
        IN_APP = "IN_APP", "Notificacao In-App"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        SENT = "SENT", "Enviado"
        FAILED = "FAILED", "Falhou"

    announcement: models.ForeignKey | None = models.ForeignKey(
        Announcement,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="logs",
        verbose_name="Comunicado",
    )
    recipient: models.ForeignKey | None = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="message_logs",
        verbose_name="Destinatario",
    )
    channel: str = models.CharField(max_length=20, choices=Channel.choices, verbose_name="Canal")
    recipient_address: str = models.CharField(
        max_length=200,
        verbose_name="Destino",
        help_text="E-mail ou telefone do destinatario",
    )
    status: str = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name="Status"
    )
    error_message: str = models.TextField(blank=True, default="", verbose_name="Mensagem de erro")
    sent_at: models.DateTimeField | None = models.DateTimeField(
        null=True, blank=True, verbose_name="Enviado em"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Log de Envio"
        verbose_name_plural = "Logs de Envio"
        indexes = [
            models.Index(fields=["channel", "status"]),
            models.Index(fields=["announcement"]),
        ]

    def __str__(self) -> str:
        disp = self.get_channel_display()
        return f"{disp} → {self.recipient_address} ({self.get_status_display()})"
