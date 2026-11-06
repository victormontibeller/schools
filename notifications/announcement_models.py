"""Rascunhos e snapshots imutáveis de comunicados institucionais."""

from django.conf import settings
from django.db import models
from django.db.models import Q

from base.media import TenantMediaPath, get_private_storage
from base.models import BaseModel
from base.upload_validators import validate_document_upload


class Announcement(BaseModel):
    class Audience(models.TextChoices):
        FAMILIES = "FAMILIES", "Famílias da escola"
        CLASSES = "CLASSES", "Famílias de turmas"
        STAFF = "STAFF", "Equipe interna"
        INDIVIDUAL = "INDIVIDUAL", "Pessoas selecionadas"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        SCHEDULED = "SCHEDULED", "Agendado"
        PUBLISHED = "PUBLISHED", "Publicado"

    title = models.CharField(max_length=200, verbose_name="Título")
    body = models.TextField(verbose_name="Mensagem")
    audience = models.CharField(max_length=20, choices=Audience.choices, default=Audience.FAMILIES)
    attachment_ids = models.JSONField(default=list)
    class_ids = models.JSONField(default=list)
    user_ids = models.JSONField(default=list)
    student = models.ForeignKey(
        "students.Student",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="individual_announcements",
    )  # Preserva contexto.
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="announcements"
    )  # Preserva autoria.
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    send_email = models.BooleanField(default=True)
    requires_acknowledgement = models.BooleanField(default=False)
    acknowledgement_due_at = models.DateTimeField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Comunicado"
        verbose_name_plural = "Comunicados"
        indexes = [models.Index(fields=["status", "scheduled_at"])]

    def __str__(self):
        return self.title


class AnnouncementRevision(BaseModel):
    announcement = models.ForeignKey(
        Announcement, on_delete=models.PROTECT, related_name="revisions"
    )  # Publicações permanecem no histórico.
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    body = models.TextField()
    audience = models.CharField(max_length=20, choices=Announcement.Audience.choices)
    audience_snapshot = models.JSONField(default=dict)
    requires_acknowledgement = models.BooleanField(default=False)
    acknowledgement_due_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField()
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="announcement_publications"
    )  # Preserva autoria.

    class Meta:
        ordering = ["-number"]
        verbose_name = "Revisão publicada"
        verbose_name_plural = "Revisões publicadas"
        constraints = [
            models.UniqueConstraint(
                fields=["announcement", "number"], name="announcement_revision_unique"
            )
        ]


class AnnouncementRecipient(BaseModel):
    revision = models.ForeignKey(
        AnnouncementRevision, on_delete=models.PROTECT, related_name="recipients"
    )  # Ciência e audiência são históricas.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="announcement_receipts",
    )
    guardian = models.ForeignKey(
        "guardians.Guardian",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="announcement_receipts",
    )
    student_ids = models.JSONField(default=list)
    first_viewed_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Destinatário de comunicado"
        verbose_name_plural = "Destinatários de comunicado"
        constraints = [
            models.UniqueConstraint(
                fields=["revision", "guardian"],
                condition=Q(guardian__isnull=False),
                name="announcement_guardian_unique",
            ),
            models.UniqueConstraint(
                fields=["revision", "user"],
                condition=Q(user__isnull=False),
                name="announcement_user_unique",
            ),
        ]


class AnnouncementAttachment(BaseModel):
    announcement = models.ForeignKey(
        Announcement, on_delete=models.PROTECT, related_name="attachments"
    )
    revisions = models.ManyToManyField(AnnouncementRevision, related_name="attachments", blank=True)
    file = models.FileField(
        storage=get_private_storage,
        upload_to=TenantMediaPath("documents/announcements"),
        validators=[validate_document_upload],
        max_length=250,
    )
    label = models.CharField(max_length=150, default="Anexo")

    class Meta:
        verbose_name = "Anexo de comunicado"
        verbose_name_plural = "Anexos de comunicado"
