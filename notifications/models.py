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
        DELIVERED = "DELIVERED", "Entregue"
        DELAYED = "DELAYED", "Entrega atrasada"
        BOUNCED = "BOUNCED", "Devolvido"
        SUPPRESSED = "SUPPRESSED", "Suprimido"
        COMPLAINED = "COMPLAINED", "Marcado como spam"
        FAILED = "FAILED", "Falhou"

    announcement: models.ForeignKey | None = models.ForeignKey(
        Announcement,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="logs",
        verbose_name="Comunicado",
    )
    diary_publication = models.ForeignKey(
        "student_diary.DiaryPublication",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,  # A entrega pode permanecer sem a publicação ativa.
        related_name="message_logs",
        verbose_name="Publicação da Agenda",
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
    provider: str = models.CharField(max_length=30, blank=True, default="", verbose_name="Provedor")
    provider_message_id: str | None = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        unique=True,
        verbose_name="ID da mensagem no provedor",
    )
    last_event: str = models.CharField(
        max_length=40, blank=True, default="", verbose_name="Último evento"
    )
    event_occurred_at: models.DateTimeField | None = models.DateTimeField(
        null=True, blank=True, verbose_name="Evento ocorrido em"
    )
    sent_at: models.DateTimeField | None = models.DateTimeField(
        null=True, blank=True, verbose_name="Enviado em"
    )
    delivered_at: models.DateTimeField | None = models.DateTimeField(
        null=True, blank=True, verbose_name="Entregue em"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Log de Envio"
        verbose_name_plural = "Logs de Envio"
        indexes = [
            models.Index(fields=["channel", "status"]),
            models.Index(fields=["announcement"]),
            models.Index(fields=["diary_publication", "channel", "status"]),
        ]

    def __str__(self) -> str:
        disp = self.get_channel_display()
        return f"{disp} → {self.recipient_address} ({self.get_status_display()})"


class WebhookEventReceipt(BaseModel):
    """Evento de webhook processado sem persistir o payload com dados pessoais."""

    provider = models.CharField(max_length=30, verbose_name="Provedor")
    external_event_id = models.CharField(
        max_length=100, unique=True, verbose_name="ID externo do evento"
    )
    event_type = models.CharField(max_length=40, verbose_name="Tipo do evento")
    provider_message_id = models.CharField(max_length=100, verbose_name="ID da mensagem")
    occurred_at = models.DateTimeField(verbose_name="Ocorrido em")

    class Meta:
        ordering = ["-occurred_at"]
        verbose_name = "Evento de Webhook"
        verbose_name_plural = "Eventos de Webhook"
        indexes = [models.Index(fields=["provider", "provider_message_id"])]

    def __str__(self) -> str:
        """Representa o evento somente por identificadores opacos."""
        return f"WebhookEventReceipt({self.pk})"
