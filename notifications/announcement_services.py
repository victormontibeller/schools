"""Comandos de autoria, publicação e ciência de comunicados."""

from django.utils import timezone

from base.context import active_tenant_schema
from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from base.services import BaseService, service_command
from notifications.announcement_selectors import (
    AnnouncementAudienceSelector,
    AnnouncementSelector,
    can_manage_announcements,
)
from notifications.models import (
    Announcement,
    AnnouncementAttachment,
    AnnouncementRecipient,
    AnnouncementRevision,
)


class AnnouncementService(BaseService):
    def _assert_manager(self, action="edit"):
        active_tenant_schema()
        if not can_manage_announcements(self.user, action):
            raise PermissionDeniedError(
                "Somente Administração e Coordenação gerenciam comunicados."
            )

    def _locked(self, pk, version):
        self._assert_manager()
        try:
            announcement = Announcement.objects.select_for_update().get(pk=pk)
        except Announcement.DoesNotExist:
            raise ObjectNotFoundError("Announcement", str(pk)) from None
        try:
            expected = int(version)
        except (TypeError, ValueError):
            raise ValidationError(
                errors={"version": ["Recarregue o comunicado antes de continuar."]}
            ) from None
        if announcement.version != expected:
            raise BusinessRuleViolationError("O comunicado mudou. Recarregue antes de continuar.")
        return announcement

    def _validated(self, data):
        from accounts.selectors import AccountSelector
        from classes.selectors import ClassSelector
        from students.selectors import StudentSelector

        self.validate_required(data, ["title", "body", "audience"])
        if data["audience"] not in Announcement.Audience.values:
            raise ValidationError(errors={"audience": ["Público inválido."]})
        values = {key: data.get(key) for key in ("title", "body", "audience")}
        values.update(
            class_ids=[str(value) for value in data.get("class_ids", [])],
            user_ids=[str(value) for value in data.get("user_ids", [])],
            student_id=data.get("student_id") or None,
            send_email=bool(data.get("send_email")),
            requires_acknowledgement=bool(data.get("requires_acknowledgement")),
            acknowledgement_due_at=data.get("acknowledgement_due_at"),
        )
        if len(values["title"]) > 200 or len(values["body"]) > 50000:
            raise ValidationError(
                errors={"body": ["Título até 200 e mensagem até 50000 caracteres."]}
            )
        if values["audience"] == "CLASSES" and not values["class_ids"]:
            raise ValidationError(errors={"class_ids": ["Selecione ao menos uma turma."]})
        if values["audience"] == "INDIVIDUAL" and not values["user_ids"]:
            raise ValidationError(errors={"user_ids": ["Selecione ao menos uma pessoa."]})
        for pk in values["class_ids"]:
            ClassSelector().get_by_id(pk)
        for pk in values["user_ids"]:
            AccountSelector().get_by_id(pk)
        if values["student_id"]:
            from students.contracts import ImportUsageService

            ImportUsageService(user=self.user).seal_for_use(student_ids=[values["student_id"]])
            StudentSelector().get_by_id(values["student_id"])
        due = values["acknowledgement_due_at"]
        if due and (not values["requires_acknowledgement"] or due <= timezone.now()):
            raise ValidationError(
                errors={"acknowledgement_due_at": ["Informe um prazo futuro para a ciência."]}
            )
        return values

    def create_announcement(self, data):
        self._assert_manager("create")
        announcement = Announcement.objects.create(
            **self._validated(data), author=self.user, created_by=self.user, updated_by=self.user
        )
        self._record_audit("INSERT", announcement)
        self._log("announcement_draft_created", announcement_id=str(announcement.pk))
        return announcement

    def update_announcement(self, pk, data):
        announcement = self._locked(pk, data.get("version"))
        if announcement.status != Announcement.Status.DRAFT:
            raise BusinessRuleViolationError(
                "Cancele o agendamento ou abra uma correção antes de editar."
            )
        old = self._snapshot(announcement)
        for key, value in self._validated(data).items():
            setattr(announcement, key, value)
        announcement.updated_by = self.user
        announcement.save()
        self._record_audit("UPDATE", announcement, old_values=old)
        self._log("announcement_draft_updated", announcement_id=str(pk))
        return announcement

    def open_announcement_correction(self, pk, *, version):
        announcement = self._locked(pk, version)
        if announcement.status != Announcement.Status.PUBLISHED:
            raise BusinessRuleViolationError("Somente comunicados publicados podem ser corrigidos.")
        announcement.status = Announcement.Status.DRAFT
        announcement.scheduled_at = None
        announcement.save()
        self._record_audit("UPDATE", announcement, old_values={"status": "PUBLISHED"})
        self._log("announcement_correction_opened", announcement_id=str(pk))
        return announcement

    @service_command
    def schedule_announcement(self, pk, *, version, scheduled_at):
        announcement = self._locked(pk, version)
        if announcement.status != "DRAFT" or not scheduled_at or scheduled_at <= timezone.now():
            raise BusinessRuleViolationError("Agende um rascunho para uma data futura.")
        if (
            announcement.acknowledgement_due_at
            and announcement.acknowledgement_due_at <= scheduled_at
        ):
            raise BusinessRuleViolationError(
                "O prazo de ciência deve ocorrer depois da publicação."
            )
        announcement.status = Announcement.Status.SCHEDULED
        announcement.scheduled_at = scheduled_at
        announcement.save()
        self._record_audit("UPDATE", announcement, old_values={"status": "DRAFT"})
        self._log("announcement_scheduled", announcement_id=str(pk))
        return announcement

    def cancel_announcement_schedule(self, pk, *, version):
        announcement = self._locked(pk, version)
        if announcement.status != "SCHEDULED":
            raise BusinessRuleViolationError("Este comunicado não está agendado.")
        announcement.status = Announcement.Status.DRAFT
        announcement.scheduled_at = None
        announcement.save()
        self._record_audit("UPDATE", announcement, old_values={"status": "SCHEDULED"})
        self._log("announcement_schedule_cancelled", announcement_id=str(pk))
        return announcement

    @service_command
    def publish_announcement(self, pk, *, version):
        from django.urls import reverse

        from notifications.outbox_services import OutboxService

        announcement = self._locked(pk, version)
        if announcement.status == "PUBLISHED":
            raise BusinessRuleViolationError("Abra uma correção para publicar nova revisão.")
        if announcement.status == "SCHEDULED" and announcement.scheduled_at > timezone.now():
            raise BusinessRuleViolationError("O horário programado ainda não chegou.")
        rows = AnnouncementAudienceSelector.resolve(announcement)
        if not rows:
            raise BusinessRuleViolationError("Nenhum destinatário elegível. Revise a audiência.")
        from students.contracts import ImportUsageService

        ImportUsageService(user=self.user).seal_for_use(
            guardian_ids=[row["guardian"].pk for row in rows if row.get("guardian")]
        )
        latest = announcement.revisions.order_by("-number").first()
        revision = AnnouncementRevision.objects.create(
            announcement=announcement,
            number=latest.number + 1 if latest else 1,
            title=announcement.title,
            body=announcement.body,
            audience=announcement.audience,
            audience_snapshot={
                "class_ids": announcement.class_ids,
                "user_ids": announcement.user_ids,
                "student_id": str(announcement.student_id or ""),
            },
            requires_acknowledgement=announcement.requires_acknowledgement,
            acknowledgement_due_at=announcement.acknowledgement_due_at,
            published_at=timezone.now(),
            published_by=self.user,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", revision)
        revision.attachments.set(
            announcement.attachments.filter(pk__in=announcement.attachment_ids)
        )
        for row in rows:
            receipt = AnnouncementRecipient.objects.create(
                revision=revision, **row, created_by=self.user, updated_by=self.user
            )
            self._record_audit("INSERT", receipt)
            OutboxService(user=self.user).create_event_deliveries(
                source_type="announcement",
                source_id=str(receipt.pk),
                recipient=row["user"],
                announcement_recipient=receipt,
                action_url=reverse("announcement_detail", args=[announcement.pk])
                + f"?revision={revision.pk}",
                event="announcement",
                send_email=announcement.send_email,
            )
        announcement.status = Announcement.Status.PUBLISHED
        announcement.published_at = revision.published_at
        announcement.scheduled_at = None
        announcement.save()
        self._record_audit("UPDATE", announcement, old_values={"status": "DRAFT"})
        self._log(
            "announcement_published",
            announcement_id=str(pk),
            revision=revision.number,
            count=len(rows),
        )
        return revision

    def add_announcement_attachment(self, pk, upload, *, version):
        from django.core.exceptions import ValidationError as DjangoValidationError

        from base.upload_validators import validate_document_upload

        announcement = self._locked(pk, version)
        if announcement.status != "DRAFT":
            raise BusinessRuleViolationError("Anexos só podem ser alterados em rascunho.")
        try:
            validate_document_upload(upload)
        except DjangoValidationError as exc:
            raise ValidationError(errors={"file": exc.messages}) from None
        attachment = AnnouncementAttachment(
            announcement=announcement, created_by=self.user, updated_by=self.user
        )
        try:
            attachment.file.save(upload.name, upload, save=False)
            attachment.save()
            self._record_audit("INSERT", attachment)
            announcement.attachment_ids = [*announcement.attachment_ids, str(attachment.pk)]
            announcement.save()
            self._record_audit("UPDATE", announcement)
        except Exception:
            if attachment.file.name:
                attachment.file.storage.delete(attachment.file.name)
            raise
        self._log(
            "announcement_attachment_added",
            announcement_id=str(pk),
            attachment_id=str(attachment.pk),
        )
        return attachment

    def remove_announcement_attachment(self, pk, attachment_id, *, version):
        announcement = self._locked(pk, version)
        if announcement.status != "DRAFT":
            raise BusinessRuleViolationError("Anexos só podem ser alterados em rascunho.")
        if str(attachment_id) not in announcement.attachment_ids:
            raise PermissionDeniedError("Anexo não pertence a este rascunho.")
        announcement.attachment_ids = [
            value for value in announcement.attachment_ids if value != str(attachment_id)
        ]
        announcement.save()
        self._record_audit("UPDATE", announcement)
        self._log(
            "announcement_attachment_removed",
            announcement_id=str(pk),
            attachment_id=str(attachment_id),
        )

    def mark_announcement_viewed(self, revision_id):
        return self._receipt_action(revision_id, acknowledge=False)

    @service_command
    def acknowledge_announcement(self, revision_id):
        return self._receipt_action(revision_id, acknowledge=True)

    def _receipt_action(self, revision_id, *, acknowledge):
        active_tenant_schema()
        try:
            revision = AnnouncementRevision.objects.get(pk=revision_id)
        except AnnouncementRevision.DoesNotExist:
            raise ObjectNotFoundError("AnnouncementRevision", str(revision_id)) from None
        receipt = AnnouncementSelector().receipt_for(revision, self.user)
        receipt = AnnouncementRecipient.objects.select_for_update().get(pk=receipt.pk)
        if not AnnouncementAudienceSelector.is_eligible(receipt, self.user):
            raise PermissionDeniedError("Acesso revogado.")
        field = "acknowledged_at" if acknowledge else "first_viewed_at"
        if acknowledge and not revision.requires_acknowledgement:
            raise BusinessRuleViolationError("Esta revisão não solicita ciência.")
        if not getattr(receipt, field):
            setattr(receipt, field, timezone.now())
            receipt.updated_by = self.user
            receipt.save()
            self._record_audit("UPDATE", receipt, old_values={field: None})
            self._log("announcement_receipt_recorded", receipt_id=str(receipt.pk), action=field)
        return receipt
