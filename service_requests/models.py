"""Atendimento privado, calendário administrativo e história imutável."""

import datetime as dt

from django.conf import settings
from django.db import models

from base.media import TenantMediaPath, get_private_storage
from base.models import BaseModel
from base.upload_validators import validate_document_upload


def default_weekdays():
    return [0, 1, 2, 3, 4]


class AdministrativeCalendar(BaseModel):
    key = models.CharField(max_length=20, unique=True, default="school")
    weekdays = models.JSONField(default=default_weekdays)
    opens_at = models.TimeField(default=dt.time(8))
    closes_at = models.TimeField(default=dt.time(18))
    closed_dates = models.JSONField(default=list, blank=True)
    immediate_contact = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "Calendário administrativo"
        verbose_name_plural = "Calendários administrativos"


class ServiceDepartment(BaseModel):
    class Code(models.TextChoices):
        SECRETARY = "SECRETARY", "Secretaria"
        COORDINATOR = "COORDINATOR", "Coordenação"
        FINANCE = "FINANCE", "Financeiro"

    code = models.CharField(max_length=20, choices=Code.choices, unique=True)
    enabled = models.BooleanField(default=False)

    def __str__(self):
        return self.get_code_display()

    class Meta:
        verbose_name = "Setor de atendimento"
        verbose_name_plural = "Setores de atendimento"


class DepartmentMembership(BaseModel):
    department = models.ForeignKey(
        ServiceDepartment, on_delete=models.PROTECT, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="service_memberships"
    )

    class Meta:
        verbose_name = "Vínculo de atendente"
        verbose_name_plural = "Vínculos de atendentes"
        constraints = [
            models.UniqueConstraint(
                fields=["department", "user"], name="service_department_user_unique"
            )
        ]


class RequestSequence(BaseModel):
    year = models.PositiveIntegerField(unique=True)
    next_number = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Sequência de protocolo"
        verbose_name_plural = "Sequências de protocolo"


class ServiceRequest(BaseModel):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberta"
        IN_PROGRESS = "IN_PROGRESS", "Em atendimento"
        WAITING_FAMILY = "WAITING_FAMILY", "Aguardando família"
        RESOLVED = "RESOLVED", "Resolvida"
        CANCELLED = "CANCELLED", "Cancelada"

    protocol = models.CharField(max_length=30, unique=True)
    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="service_requests"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authored_service_requests"
    )
    department = models.ForeignKey(
        ServiceDepartment, on_delete=models.PROTECT, related_name="requests"
    )
    attendant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assigned_service_requests",
    )
    subject = models.CharField(max_length=180)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.OPEN)
    cycle = models.PositiveIntegerField(default=1)
    cycle_opened_at = models.DateTimeField()
    response_due_at = models.DateTimeField(db_index=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    overdue_notified_cycle = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Solicitação privada"
        verbose_name_plural = "Solicitações privadas"
        indexes = [models.Index(fields=["department", "status", "response_due_at"])]


class RequestMessage(BaseModel):
    request = models.ForeignKey(ServiceRequest, on_delete=models.PROTECT, related_name="messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField()
    is_staff_response = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Mensagem de atendimento"
        verbose_name_plural = "Mensagens de atendimento"
        ordering = ["created_at", "pk"]


class RequestAttachment(BaseModel):
    message = models.ForeignKey(
        RequestMessage, on_delete=models.PROTECT, related_name="attachments"
    )
    file = models.FileField(
        upload_to=TenantMediaPath("documents/service_requests"),
        storage=get_private_storage,
        validators=[validate_document_upload],
    )

    class Meta:
        verbose_name = "Anexo de atendimento"
        verbose_name_plural = "Anexos de atendimento"


class RequestTransition(BaseModel):
    request = models.ForeignKey(
        ServiceRequest, on_delete=models.PROTECT, related_name="transitions"
    )
    event = models.CharField(
        max_length=30,
        choices=[
            ("opened", "Solicitação aberta"),
            ("response", "Mensagem enviada"),
            ("status", "Estado atualizado"),
            ("reopened", "Solicitação reaberta"),
            ("transferred", "Setor alterado"),
            ("assigned", "Atendente atribuído"),
        ],
    )
    from_status = models.CharField(max_length=24, blank=True)
    to_status = models.CharField(max_length=24, choices=ServiceRequest.Status.choices)
    from_department = models.CharField(max_length=20, blank=True)
    to_department = models.CharField(max_length=20)
    cycle = models.PositiveIntegerField()

    class Meta:
        verbose_name = "Histórico de atendimento"
        verbose_name_plural = "Históricos de atendimento"
        ordering = ["created_at", "pk"]
