"""Workflow de revisão, publicação e visualização da Agenda escolar."""

from __future__ import annotations

from django.conf import settings
from django.db import connection, transaction
from django.urls import reverse
from django.utils import timezone

from base.exceptions import BusinessRuleViolationError, PermissionDeniedError, ValidationError
from base.services import BaseService


class DiaryWorkflowService(BaseService):
    """Publica a agenda de forma unidirecional, sem respostas da família."""

    @transaction.atomic
    def submit_sheet(self, sheet_id, *, base_url: str = ""):
        """Envia uma folha completa para revisão da coordenação."""
        from classes.contracts import Enrollment
        from student_diary.models import DailyDiary, DiarySheet
        from student_diary.services import StudentDiaryService

        self._assert_feature_enabled()
        sheet = self._locked_sheet(sheet_id)
        StudentDiaryService(user=self.user)._get_authorized_teacher(sheet.class_obj)
        if sheet.status not in {DiarySheet.Status.DRAFT, DiarySheet.Status.CHANGES_REQUESTED}:
            raise BusinessRuleViolationError(
                "Somente rascunhos ou agendas devolvidas podem ser enviados."
            )
        active_ids = set(
            Enrollment.objects.filter(
                class_obj=sheet.class_obj, status=Enrollment.Status.ACTIVE
            ).values_list("student_id", flat=True)
        )
        saved_ids = set(
            DailyDiary.objects.filter(class_obj=sheet.class_obj, date=sheet.date).values_list(
                "student_id", flat=True
            )
        )
        if not active_ids or active_ids != saved_ids:
            raise BusinessRuleViolationError("Salve a agenda completa da turma antes de enviar.")
        old = self._snapshot(sheet, ["status", "review_feedback", "submitted_at"])
        sheet.status = DiarySheet.Status.PENDING_REVIEW
        sheet.review_feedback = ""
        sheet.submitted_at = timezone.now()
        sheet.submitted_by = self.user
        sheet.updated_by = self.user
        sheet.save()
        self._record_audit("UPDATE", sheet, old_values=old)
        self._notify_reviewers(sheet, base_url)
        self._log("agenda_enviada_revisao", sheet_id=str(sheet.pk))
        return sheet

    @transaction.atomic
    def request_changes(self, sheet_id, feedback: str, *, base_url: str = ""):
        """Devolve uma folha em revisão com motivo obrigatório."""
        from student_diary.models import DiarySheet

        self._assert_feature_enabled()
        self._assert_reviewer()
        sheet = self._locked_sheet(sheet_id)
        feedback = (feedback or "").strip()
        if sheet.status != DiarySheet.Status.PENDING_REVIEW:
            raise BusinessRuleViolationError("Somente agendas em revisão podem ser devolvidas.")
        if not feedback:
            raise ValidationError(errors={"feedback": ["Informe o motivo da devolução."]})
        old = self._snapshot(sheet, ["status", "review_feedback"])
        sheet.status = DiarySheet.Status.CHANGES_REQUESTED
        sheet.review_feedback = feedback
        sheet.reviewed_at = timezone.now()
        sheet.reviewed_by = self.user
        sheet.updated_by = self.user
        sheet.save()
        self._record_audit("UPDATE", sheet, old_values=old)
        self._notify_submitter_changes(sheet, base_url)
        self._log("agenda_devolvida", sheet_id=str(sheet.pk))
        return sheet

    @transaction.atomic
    def open_sheet_for_correction(self, sheet_id):
        """Reabre uma agenda publicada sem alterar suas revisões anteriores."""
        from student_diary.models import DiarySheet

        self._assert_feature_enabled()
        self._assert_reviewer()
        sheet = self._locked_sheet(sheet_id)
        if sheet.status != DiarySheet.Status.PUBLISHED:
            raise BusinessRuleViolationError("Somente agendas publicadas podem ser reabertas.")
        old = self._snapshot(sheet, ["status", "review_feedback"])
        sheet.status = DiarySheet.Status.DRAFT
        sheet.review_feedback = ""
        sheet.updated_by = self.user
        sheet.save()
        self._record_audit("UPDATE", sheet, old_values=old)
        self._log("agenda_reaberta", sheet_id=str(sheet.pk))
        return sheet

    @transaction.atomic
    def approve_sheet(self, sheet_id, *, base_url: str = ""):
        """Publica snapshots imutáveis e notifica responsáveis com guarda."""
        from notifications.services import NotificationService
        from student_diary.models import (
            DiaryPublication,
            DiarySheet,
            DiaryViewReceipt,
        )
        from student_diary.selectors import StudentDiarySelector

        self._assert_feature_enabled()
        self._assert_reviewer()
        sheet = self._locked_sheet(sheet_id)
        if sheet.status != DiarySheet.Status.PENDING_REVIEW:
            raise BusinessRuleViolationError("Somente agendas em revisão podem ser publicadas.")
        selector = StudentDiarySelector()
        payloads = selector.build_publication_payloads(sheet)
        if not payloads:
            raise BusinessRuleViolationError("Não há registros para publicar.")
        latest = (
            sheet.publications.order_by("-revision_number")
            .values_list("revision_number", flat=True)
            .first()
        )
        number = (latest or 0) + 1
        now = timezone.now()
        publication = DiaryPublication.objects.create(
            sheet=sheet,
            revision_number=number,
            published_at=now,
            published_by=self.user,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", publication)
        entries = self._create_entries(publication, payloads)
        notification_service = NotificationService(user=self.user)
        for link in selector.list_custodial_guardians(entries):
            entry = entries[link.student_id]
            action_url = reverse("diary_publication_detail", args=[entry.pk])
            notification = notification_service.create_notification(
                {
                    "recipient_id": link.guardian.user_id,
                    "title": "Agenda escolar disponível",
                    "message": "A escola publicou uma atualização da agenda.",
                    "source": "student_diary",
                    "action_url": action_url,
                }
            )
            receipt = DiaryViewReceipt.objects.create(
                entry=entry,
                guardian=link.guardian,
                notification_id=notification.pk,
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", receipt)
            absolute_url = f"{base_url.rstrip('/')}{action_url}" if base_url else action_url
            self._schedule_family_delivery(link.guardian.user_id, absolute_url, publication.pk)
        old = self._snapshot(sheet, ["status", "reviewed_at", "reviewed_by_id"])
        sheet.status = DiarySheet.Status.PUBLISHED
        sheet.reviewed_at = now
        sheet.reviewed_by = self.user
        sheet.updated_by = self.user
        sheet.save()
        self._record_audit("UPDATE", sheet, old_values=old)
        self._log("agenda_publicada", sheet_id=str(sheet.pk), revision=number)
        return publication

    @transaction.atomic
    def mark_entry_viewed(self, entry_id):
        """Registra abertura idempotente sem criar resposta da família."""
        from notifications.services import NotificationService
        from student_diary.models import DiaryViewReceipt
        from student_diary.selectors import StudentDiarySelector

        self._assert_feature_enabled()
        entry = StudentDiarySelector().get_published_entry_for_guardian(entry_id, self.user.pk)
        receipt = DiaryViewReceipt.objects.select_for_update().get(
            entry=entry, guardian__user_id=self.user.pk
        )
        old = self._snapshot(receipt, ["first_viewed_at", "last_viewed_at", "view_count"])
        now = timezone.now()
        receipt.first_viewed_at = receipt.first_viewed_at or now
        receipt.last_viewed_at = now
        receipt.view_count += 1
        receipt.updated_by = self.user
        receipt.save()
        self._record_audit("UPDATE", receipt, old_values=old)
        if receipt.notification_id:
            NotificationService(user=self.user).mark_as_read_for_user(
                receipt.notification_id, self.user.pk
            )
        self._log("agenda_visualizada", entry_id=str(entry.pk))
        return receipt

    def _create_entries(self, publication, payloads: list[dict]) -> dict:
        """Cria e audita os snapshots individuais da revisão."""
        from student_diary.models import DiaryPublishedEntry

        entries = {}
        for payload in payloads:
            student_id = payload.pop("student_id")
            entry = DiaryPublishedEntry.objects.create(
                publication=publication,
                student_id=student_id,
                **payload,
                created_by=self.user,
                updated_by=self.user,
            )
            entries[student_id] = entry
            self._record_audit("INSERT", entry)
        return entries

    def _locked_sheet(self, sheet_id):
        """Obtém a folha bloqueada para impedir transições concorrentes."""
        from base.exceptions import ObjectNotFoundError
        from student_diary.models import DiarySheet

        try:
            return (
                DiarySheet.objects.select_for_update().select_related("class_obj").get(pk=sheet_id)
            )
        except DiarySheet.DoesNotExist:
            raise ObjectNotFoundError("DiarySheet", str(sheet_id)) from None

    def _assert_reviewer(self) -> None:
        """Restringe revisão a coordenação/administração com edição da Agenda."""
        from core.permissions import can_access, role_name

        eligible_reviewer = getattr(self.user, "is_active", False) and (
            getattr(self.user, "is_superuser", False)
            or role_name(self.user) in {"ADMIN", "COORDINATOR"}
        )
        if not eligible_reviewer or not can_access(self.user, "student_diary", "edit"):
            raise PermissionDeniedError("Somente a coordenação pode revisar a Agenda.")

    def _notify_reviewers(self, sheet, base_url: str) -> None:
        """Notifica revisores ativos com link direto para a folha autenticada."""
        from notifications.services import NotificationService
        from student_diary.selectors import StudentDiarySelector

        action_url = self._sheet_action_url(sheet)
        absolute_url = f"{base_url.rstrip('/')}{action_url}" if base_url else action_url
        notification_service = NotificationService(user=self.user)
        for reviewer in StudentDiarySelector().list_active_reviewers():
            notification_service.create_notification(
                {
                    "recipient_id": reviewer.pk,
                    "title": "Agenda aguardando revisão",
                    "message": "Uma agenda foi enviada para revisão.",
                    "source": "student_diary",
                    "action_url": action_url,
                }
            )
            self._schedule_staff_delivery(reviewer.pk, absolute_url, "review_requested")

    def _notify_submitter_changes(self, sheet, base_url: str) -> None:
        """Avisa o autor da submissão sem colocar o motivo no canal externo."""
        if not sheet.submitted_by_id or not sheet.submitted_by.is_active:
            return
        from notifications.services import NotificationService

        action_url = self._sheet_action_url(sheet)
        absolute_url = f"{base_url.rstrip('/')}{action_url}" if base_url else action_url
        NotificationService(user=self.user).create_notification(
            {
                "recipient_id": sheet.submitted_by_id,
                "title": "Correção solicitada na Agenda",
                "message": "Uma agenda foi devolvida para correção.",
                "source": "student_diary",
                "action_url": action_url,
            }
        )
        self._schedule_staff_delivery(sheet.submitted_by_id, absolute_url, "changes_requested")

    @staticmethod
    def _sheet_action_url(sheet) -> str:
        """Monta o link interno sem incluir conteúdo da Agenda."""
        return (
            f"{reverse('diary_daily')}?class_id={sheet.class_obj_id}"
            f"&date={sheet.date.isoformat()}"
        )

    @staticmethod
    def _assert_feature_enabled() -> None:
        """Aplica a ativação gradual configurada por escola."""
        if settings.TESTING:
            return
        from tenancy.selectors import SchoolSelector

        school = SchoolSelector().get_current_school()
        enabled = bool(
            (school.settings if school else {})
            .get("student_diary", {})
            .get("interactive_enabled", False)
        )
        if not enabled:
            raise BusinessRuleViolationError("Publicação da Agenda ainda não está habilitada.")

    @staticmethod
    def _schedule_family_delivery(user_id, action_url: str, publication_id) -> None:
        """Agenda e-mail somente depois do commit da publicação."""
        from notifications.tasks import send_diary_email_task

        schema_name = getattr(connection, "schema_name", "public")
        transaction.on_commit(
            lambda: send_diary_email_task.delay(
                schema_name,
                str(user_id),
                "publication",
                action_url,
                str(publication_id),
            )
        )

    @staticmethod
    def _schedule_staff_delivery(user_id, action_url: str, event: str) -> None:
        """Agenda e-mail de workflow somente após a transação confirmar."""
        from notifications.tasks import send_diary_email_task

        schema_name = getattr(connection, "schema_name", "public")
        transaction.on_commit(
            lambda: send_diary_email_task.delay(
                schema_name,
                str(user_id),
                event,
                action_url,
            )
        )
