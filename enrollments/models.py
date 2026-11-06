"""Persistência do workflow canônico de matrículas da Secretaria."""

from django.conf import settings
from django.db import models
from django.db.models import Q

from base.media import get_private_storage, student_document_path
from base.models import BaseModel
from base.upload_validators import validate_document_upload


class EnrollmentApplication(BaseModel):
    """Solicitação que governa a criação ou o encerramento de vínculo acadêmico."""

    class Status(models.TextChoices):
        PRE_ENROLLMENT = "PRE_ENROLLMENT", "Pré-matrícula"
        CORRECTION_REQUIRED = "CORRECTION_REQUIRED", "Correção necessária"
        UNDER_REVIEW = "UNDER_REVIEW", "Em análise"
        WAITLISTED = "WAITLISTED", "Lista de espera"
        APPROVED = "APPROVED", "Aprovada"
        ENROLLED = "ENROLLED", "Matriculada"
        TRANSFERRED = "TRANSFERRED", "Transferida"
        REJECTED = "REJECTED", "Recusada"
        CANCELLED = "CANCELLED", "Cancelada"

    class ApplicationType(models.TextChoices):
        NEW = "NEW", "Nova matrícula"
        REENROLLMENT = "REENROLLMENT", "Rematrícula"
        INTERNAL_TRANSFER = "INTERNAL_TRANSFER", "Transferência interna"
        INBOUND_TRANSFER = "INBOUND_TRANSFER", "Transferência recebida"
        OUTBOUND_TRANSFER = "OUTBOUND_TRANSFER", "Transferência de saída"

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        related_name="enrollment_applications",
        verbose_name="Aluno",
    )
    target_class = models.ForeignKey(
        "classes.Class",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="enrollment_applications",
        verbose_name="Turma de destino",
    )
    source_enrollment = models.ForeignKey(
        "classes.Enrollment",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="source_applications",
        verbose_name="Matrícula de origem",
    )
    result_enrollment = models.OneToOneField(
        "classes.Enrollment",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="result_application",
        verbose_name="Matrícula resultante",
    )
    academic_year = models.PositiveIntegerField(verbose_name="Ano letivo")
    application_number = models.CharField(max_length=20, unique=True, verbose_name="Protocolo")
    application_type = models.CharField(
        max_length=30,
        choices=ApplicationType.choices,
        default=ApplicationType.NEW,
        verbose_name="Tipo de solicitação",
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PRE_ENROLLMENT,
        verbose_name="Situação",
    )
    priority = models.PositiveSmallIntegerField(default=0, verbose_name="Prioridade")
    notes = models.TextField(blank=True, default="", verbose_name="Observações")
    origin_school = models.CharField(
        max_length=200, blank=True, default="", verbose_name="Escola de origem"
    )
    destination_school = models.CharField(
        max_length=200, blank=True, default="", verbose_name="Escola de destino"
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_enrollment_applications",
        verbose_name="Revisado por",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Revisado em")
    waitlisted_at = models.DateTimeField(null=True, blank=True, verbose_name="Entrada na espera")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Solicitação de matrícula"
        verbose_name_plural = "Solicitações de matrícula"
        indexes = [
            models.Index(fields=["status", "-priority", "created_at"]),
            models.Index(fields=["application_number"]),
            models.Index(fields=["student", "academic_year"]),
            models.Index(fields=["target_class", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "academic_year"],
                condition=Q(
                    is_active=True,
                    status__in=[
                        "PRE_ENROLLMENT",
                        "CORRECTION_REQUIRED",
                        "UNDER_REVIEW",
                        "WAITLISTED",
                        "APPROVED",
                    ],
                ),
                name="uniq_open_enrollment_application_student_year",
            )
        ]

    def __str__(self) -> str:
        return f"{self.application_number} ({self.get_status_display()})"


class EnrollmentTransition(BaseModel):
    """Registro imutável, append-only, de cada mudança de estado."""

    application = models.ForeignKey(
        EnrollmentApplication,
        on_delete=models.PROTECT,
        related_name="transitions",
        verbose_name="Solicitação",
    )
    from_status = models.CharField(max_length=30, blank=True, default="", verbose_name="De")
    to_status = models.CharField(
        max_length=30, choices=EnrollmentApplication.Status.choices, verbose_name="Para"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="enrollment_transitions",
        verbose_name="Ator",
    )
    reason = models.TextField(blank=True, default="", verbose_name="Motivo")

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Transição de matrícula"
        verbose_name_plural = "Transições de matrícula"
        indexes = [models.Index(fields=["application", "created_at"])]

    def __str__(self) -> str:
        return f"{self.application_id}: {self.from_status or '—'} → {self.to_status}"


class DocumentRequirement(BaseModel):
    """Requisito documental configurável por tipo de solicitação."""

    application_type = models.CharField(
        max_length=30,
        choices=EnrollmentApplication.ApplicationType.choices,
        verbose_name="Tipo de solicitação",
    )
    code = models.SlugField(max_length=50, verbose_name="Código")
    label = models.CharField(max_length=120, verbose_name="Documento")
    is_required = models.BooleanField(default=True, verbose_name="Obrigatório")
    allows_physical = models.BooleanField(default=False, verbose_name="Aceita conferência física")
    display_order = models.PositiveSmallIntegerField(default=0, verbose_name="Ordem")

    class Meta:
        ordering = ["application_type", "display_order", "label"]
        verbose_name = "Requisito documental"
        verbose_name_plural = "Requisitos documentais"
        constraints = [
            models.UniqueConstraint(
                fields=["application_type", "code"],
                condition=Q(is_active=True),
                name="uniq_active_document_requirement_type_code",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_application_type_display()} · {self.label}"


class StudentDocument(BaseModel):
    """Item materializado do checklist documental de uma solicitação."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        SUBMITTED = "SUBMITTED", "Entregue"
        VERIFIED = "VERIFIED", "Verificado"
        REJECTED = "REJECTED", "Recusado"
        WAIVED = "WAIVED", "Dispensado"

    class DeliveryMethod(models.TextChoices):
        DIGITAL = "DIGITAL", "Digital"
        PHYSICAL = "PHYSICAL", "Físico"

    application = models.ForeignKey(
        EnrollmentApplication,
        on_delete=models.PROTECT,
        related_name="documents",
        verbose_name="Solicitação",
    )
    requirement = models.ForeignKey(
        DocumentRequirement,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="snapshots",
        verbose_name="Requisito de origem",
    )
    requirement_code = models.SlugField(max_length=50, verbose_name="Código do requisito")
    requirement_label = models.CharField(max_length=120, verbose_name="Documento")
    is_required = models.BooleanField(default=True, verbose_name="Obrigatório")
    allows_physical = models.BooleanField(default=False, verbose_name="Aceita conferência física")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name="Situação"
    )
    delivery_method = models.CharField(
        max_length=10,
        choices=DeliveryMethod.choices,
        blank=True,
        default="",
        verbose_name="Forma de entrega",
    )
    file = models.FileField(
        upload_to=student_document_path,
        storage=get_private_storage,
        null=True,
        blank=True,
        validators=[validate_document_upload],
        verbose_name="Arquivo",
    )
    decision_reason = models.TextField(blank=True, default="", verbose_name="Motivo")
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_enrollment_documents",
        verbose_name="Verificado por",
    )
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name="Verificado em")

    class Meta:
        ordering = ["requirement_label"]
        verbose_name = "Documento de matrícula"
        verbose_name_plural = "Documentos de matrícula"
        constraints = [
            models.UniqueConstraint(
                fields=["application", "requirement_code"],
                condition=Q(is_active=True),
                name="uniq_active_application_document_code",
            )
        ]
        indexes = [
            models.Index(fields=["application", "status"]),
            models.Index(fields=["application", "is_required"]),
        ]

    def __str__(self) -> str:
        return f"{self.application.application_number} · {self.requirement_label}"


class EnrollmentReminder(BaseModel):
    """Deduplicação e rastreabilidade de lembrete documental por destinatário."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        SKIPPED = "SKIPPED", "Não enviado"
        SENT = "SENT", "Enviado"
        FAILED = "FAILED", "Falhou"

    application = models.ForeignKey(
        EnrollmentApplication,
        on_delete=models.PROTECT,
        related_name="reminders",
        verbose_name="Solicitação",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="enrollment_reminders",
        verbose_name="Destinatário",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, verbose_name="Situação"
    )
    message_log_id = models.UUIDField(null=True, blank=True, verbose_name="Log de mensagem")
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Enviado em")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Lembrete documental"
        verbose_name_plural = "Lembretes documentais"
        constraints = [
            models.UniqueConstraint(
                fields=["application", "recipient"],
                condition=Q(is_active=True),
                name="uniq_active_enrollment_reminder_recipient",
            )
        ]

    def __str__(self) -> str:
        return f"{self.application_id} · {self.status}"
