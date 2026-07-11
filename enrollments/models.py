"""Modelos do modulo de matriculas e secretaria."""

from django.conf import settings
from django.db import models

from base.models import BaseModel
from base.upload_validators import validate_document_upload


class EnrollmentApplication(BaseModel):
    """Processo completo de matricula — da pre-matricula ao deferimento."""

    class Status(models.TextChoices):
        PRE_ENROLLMENT = "PRE_ENROLLMENT", "Pre-Matricula"
        UNDER_REVIEW = "UNDER_REVIEW", "Em Analise"
        APPROVED = "APPROVED", "Aprovado"
        ENROLLED = "ENROLLED", "Matriculado"
        REJECTED = "REJECTED", "Recusado"
        CANCELLED = "CANCELLED", "Cancelado"

    class ApplicationType(models.TextChoices):
        NEW = "NEW", "Nova Matricula"
        REENROLL = "REENROLL", "Rematricula"
        TRANSFER_INTERNAL = "TRANSFER_INTERNAL", "Transferencia Interna"
        TRANSFER_EXTERNAL = "TRANSFER_EXTERNAL", "Transferencia Externa"

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="enrollment_applications",
        verbose_name="Aluno",
    )
    class_obj = models.ForeignKey(
        "classes.Class",
        on_delete=models.CASCADE,
        related_name="enrollment_applications",
        verbose_name="Turma",
    )
    academic_year = models.PositiveIntegerField(verbose_name="Ano Letivo")
    application_number = models.CharField(max_length=30, unique=True, verbose_name="Protocolo")
    application_type = models.CharField(
        max_length=30,
        choices=ApplicationType.choices,
        default=ApplicationType.NEW,
        verbose_name="Tipo de Solicitacao",
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PRE_ENROLLMENT,
        verbose_name="Situacao",
    )
    priority = models.PositiveSmallIntegerField(default=0, verbose_name="Prioridade")
    notes = models.TextField(blank=True, default="", verbose_name="Observacoes")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_applications",
        verbose_name="Revisado por",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Data de Revisao")
    rejection_reason = models.TextField(blank=True, default="", verbose_name="Motivo de Recusa")
    correction_notes = models.TextField(
        blank=True, default="", verbose_name="Solicitacao de Correcao"
    )
    cancellation_reason = models.TextField(
        blank=True, default="", verbose_name="Motivo de Cancelamento"
    )
    enrollment = models.ForeignKey(
        "classes.Enrollment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="application",
        verbose_name="Matricula Efetivada",
    )
    previous_class = models.ForeignKey(
        "classes.Class",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transfer_from_applications",
        verbose_name="Turma de Origem",
    )
    previous_school = models.CharField(
        max_length=200, blank=True, default="", verbose_name="Escola de Origem"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Solicitacao de Matricula"
        verbose_name_plural = "Solicitacoes de Matricula"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["application_number"]),
            models.Index(fields=["student", "academic_year"]),
        ]

    def __str__(self) -> str:
        return f"{self.application_number} — {self.student} ({self.get_status_display()})"


class StudentDocument(BaseModel):
    """Documento apresentado ou pendente para um aluno."""

    class DocumentType(models.TextChoices):
        BIRTH_CERTIFICATE = "BIRTH_CERT", "Certidao de Nascimento"
        ID = "ID", "Documento de Identidade"
        CPF = "CPF", "CPF"
        PROOF_OF_ADDRESS = "ADDRESS", "Comprovante de Endereco"
        SCHOOL_TRANSCRIPT = "TRANSCRIPT", "Historico Escolar"
        MEDICAL_CERTIFICATE = "MEDICAL", "Atestado Medico"
        PHOTO = "PHOTO", "Foto 3x4"
        VACCINATION = "VACCINE", "Carteira de Vacinacao"
        CUSTODY = "CUSTODY", "Termo de Guarda"
        TRANSFER_LETTER = "TRANSFER_LETTER", "Carta de Transferencia"
        OTHER = "OTHER", "Outro"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        SUBMITTED = "SUBMITTED", "Entregue"
        VERIFIED = "VERIFIED", "Verificado"
        REJECTED = "REJECTED", "Recusado"

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name="Aluno",
    )
    application = models.ForeignKey(
        EnrollmentApplication,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documents",
        verbose_name="Solicitacao",
    )
    document_type = models.CharField(
        max_length=30, choices=DocumentType.choices, verbose_name="Tipo de Documento"
    )
    description = models.CharField(max_length=200, blank=True, default="", verbose_name="Descricao")
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Situacao",
    )
    file = models.FileField(
        upload_to="documents/students/",
        null=True,
        blank=True,
        verbose_name="Arquivo",
        validators=[validate_document_upload],
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_documents",
        verbose_name="Verificado por",
    )
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name="Data de Verificacao")

    class Meta:
        ordering = ["document_type"]
        verbose_name = "Documento do Aluno"
        verbose_name_plural = "Documentos dos Alunos"
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["application", "document_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.student} — {self.get_document_type_display()} ({self.get_status_display()})"
