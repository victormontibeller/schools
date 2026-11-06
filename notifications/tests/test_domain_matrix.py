"""Matriz de avisos com famílias, publicação e revogação no worker."""

from unittest.mock import patch

import pytest
from django.utils import timezone

from academic_calendar.services import CalendarService
from core.models import RoleModuleAccess
from enrollments.models import EnrollmentApplication, StudentDocument
from enrollments.services import EnrollmentReminderService
from financeiro.models import BillingEntry, CollectionReminder
from financeiro.services import FinanceService, PaymentService
from notifications.channels import ChannelResult
from notifications.models import MessageLog, Notification
from notifications.outbox_services import OutboxService
from notifications.tests.test_announcement_workflow import family

pytestmark = pytest.mark.django_db


def test_public_calendar_targets_family_once_and_revalidates_school(user, school):
    account, _, cls, _ = family(user, children=2)
    event = CalendarService(user=user).create_event(
        {
            "title": "Conteúdo privado",
            "start_date": timezone.localdate(),
            "end_date": timezone.localdate(),
            "type": "MEETING",
            "audience": "CLASS",
            "class_obj_id": cls.pk,
            "is_public": True,
        }
    )
    logs = MessageLog.objects.filter(source_type="calendar_event", source_id=str(event.pk))
    assert logs.filter(channel="EMAIL").count() == 1
    assert Notification.objects.filter(recipient=account).count() == 1
    school.is_active = False
    school.save()
    with patch("notifications.channels.email.EmailChannel.send") as send:
        OutboxService().dispatch(logs.get(channel="EMAIL").pk)
    send.assert_not_called()


def test_private_calendar_does_not_notify_family_and_publication_has_one_intent(user, school):
    account, _, cls, _ = family(user)
    service = CalendarService(user=user)
    event = service.create_event(
        {
            "title": "Privado",
            "start_date": timezone.localdate(),
            "end_date": timezone.localdate(),
            "type": "MEETING",
            "audience": "CLASS",
            "class_obj_id": cls.pk,
            "is_public": False,
        }
    )
    assert not MessageLog.objects.filter(recipient=account).exists()
    event = service.update_event(event.pk, {"is_public": True})
    assert MessageLog.objects.filter(recipient=account, channel="EMAIL").count() == 1
    service.update_event(event.pk, {"description": "Ajuste interno"})
    assert MessageLog.objects.filter(recipient=account, channel="EMAIL").count() == 1


def billing_for_family(user):
    account, guardian, _, links = family(user)
    access = RoleModuleAccess.objects.get(role=account.role, module_key="finance_billings")
    access.can_view = True
    access.save()
    billing = BillingEntry.objects.create(
        student=links[0].student,
        description="Privado",
        principal_value=100,
        due_date=timezone.localdate(),
        competency=timezone.localdate().replace(day=1),
    )
    return billing, account, guardian, links[0]


def test_financial_reminder_projects_outbox_result_and_revokes_custody(user, school):
    billing, account, _, link = billing_for_family(user)
    service = FinanceService(user=user)
    assert service.send_manual_reminder(billing.pk, channels=["EMAIL"]) == 1
    assert service.send_manual_reminder(billing.pk, channels=["EMAIL"]) == 0
    reminder = CollectionReminder.objects.get()
    link.has_custody = False
    link.save()
    with patch("notifications.channels.email.EmailChannel.send") as send:
        OutboxService().dispatch(reminder.message_log_id)
    send.assert_not_called()
    reminder.refresh_from_db()
    assert reminder.status == "SKIPPED"


def test_payment_only_notifies_on_confirmation_and_reversal(user, school):
    billing, account, _, _ = billing_for_family(user)
    service = PaymentService(user=user)
    payment = service.create_payment(
        allocations=[{"billing_id": billing.pk, "amount": 100}], paid_date=timezone.localdate()
    )
    assert not MessageLog.objects.filter(source_type="payment").exists()
    service.confirm_payment(payment.pk)
    assert (
        MessageLog.objects.filter(source_type="payment", recipient=account, channel="EMAIL").count()
        == 1
    )
    service.reverse_payment(payment.pk, reason="Correção", adjustment_due_date=timezone.localdate())
    assert (
        MessageLog.objects.filter(source_type="payment", recipient=account, channel="EMAIL").count()
        == 2
    )


def test_document_reminder_uses_primary_guardian_without_child_login_or_opt_in_for_inbox(
    user, school
):
    account, guardian, cls, links = family(user)
    link = links[0]
    link.is_primary = True
    link.save()
    guardian.accepts_email_notifications = False
    guardian.save()
    application = EnrollmentApplication.objects.create(
        student=link.student, target_class=cls, academic_year=2026, application_number="MAT-TEST"
    )
    StudentDocument.objects.create(
        application=application,
        requirement_code="doc",
        requirement_label="Documento",
        is_required=True,
    )
    service = EnrollmentReminderService(user=user)
    reminders = service.send_reminders(application.pk, expected_version=application.version)
    assert len(reminders) == 1
    assert Notification.objects.filter(recipient=account).exists()
    OutboxService().dispatch(reminders[0].message_log_id)
    reminders[0].refresh_from_db()
    assert reminders[0].status == "SKIPPED"
    guardian.accepts_email_notifications = True
    guardian.save()
    successor = service.send_reminders(application.pk, expected_version=application.version)[0]
    with patch(
        "notifications.channels.email.EmailChannel.send",
        return_value=ChannelResult(
            success=True, channel="EMAIL", recipient_address="", provider_message_id="provider"
        ),
    ):
        OutboxService().dispatch(successor.message_log_id)
    successor.refresh_from_db()
    assert successor.status == "SENT"
    assert service.send_reminders(application.pk, expected_version=application.version) == []


def test_payment_confirmation_rolls_back_when_required_outbox_fails(user, school):
    billing, _, _, _ = billing_for_family(user)
    service = PaymentService(user=user)
    payment = service.create_payment(
        allocations=[{"billing_id": billing.pk, "amount": 100}], paid_date=timezone.localdate()
    )
    with patch(
        "notifications.outbox_services.OutboxService._record_audit",
        side_effect=RuntimeError("audit"),
    ):
        with pytest.raises(RuntimeError):
            service.confirm_payment(payment.pk)
    payment.refresh_from_db()
    billing.refresh_from_db()
    assert payment.status == "PENDING"
    assert billing.paid_value == 0
    assert not MessageLog.objects.filter(source_type="payment").exists()


def test_calendar_worker_requires_same_child_for_custody_and_class(user, school):
    from classes.models import Enrollment

    account, _, cls, links = family(user, children=2)
    event = CalendarService(user=user).create_event(
        {
            "title": "Turma",
            "start_date": timezone.localdate(),
            "end_date": timezone.localdate(),
            "type": "MEETING",
            "audience": "CLASS",
            "class_obj_id": cls.pk,
            "is_public": True,
        }
    )
    links[0].has_custody = False
    links[0].save()
    Enrollment.objects.filter(student=links[1].student).update(status="TRANSFERRED")
    log = MessageLog.objects.get(source_id=str(event.pk), recipient=account, channel="EMAIL")
    with patch("notifications.channels.email.EmailChannel.send") as send:
        OutboxService().dispatch(log.pk)
    send.assert_not_called()
    log.refresh_from_db()
    assert log.dispatch_state == "REVOKED"


def test_calendar_update_rejects_class_audience_without_class(user, school):
    from base.exceptions import ValidationError

    service = CalendarService(user=user)
    event = service.create_event(
        {
            "title": "Escola",
            "start_date": timezone.localdate(),
            "end_date": timezone.localdate(),
            "type": "MEETING",
            "audience": "ALL",
            "is_public": False,
        }
    )
    with pytest.raises(ValidationError):
        service.update_event(event.pk, {"audience": "CLASS", "is_public": True})
    event.refresh_from_db()
    assert not event.is_public


def test_finance_can_reprocess_failed_reminder_without_announcement_edit(user, school, client):
    from django.urls import reverse

    from core.models import CustomUser, Role
    from core.permissions import can_access

    billing, _, _, _ = billing_for_family(user)
    staff = CustomUser.objects.create_user(
        email="finance@example.test", password="Violeta824", role=Role.objects.get(name="FINANCE")
    )
    assert not can_access(staff, "notifications", "edit")
    FinanceService(user=user).send_manual_reminder(billing.pk, channels=["EMAIL"])
    reminder = CollectionReminder.objects.get()
    with patch(
        "notifications.channels.email.EmailChannel.send",
        return_value=ChannelResult(
            success=False,
            channel="EMAIL",
            recipient_address="",
            error_message="provider_error",
            retryable=False,
        ),
    ):
        OutboxService().dispatch(reminder.message_log_id)
    previous = reminder.message_log_id
    client.force_login(staff)
    assert client.get(reverse("communication_delivery_list")).status_code == 200
    response = client.post(reverse("communication_delivery_retry", args=[previous]))
    assert response.status_code == 302
    reminder.refresh_from_db()
    assert reminder.status == "PENDING" and reminder.message_log_id != previous
    assert MessageLog.objects.get(pk=reminder.message_log_id).previous_delivery_id == previous


def test_payment_worker_revokes_financial_capability(user, school):
    billing, account, _, _ = billing_for_family(user)
    service = PaymentService(user=user)
    payment = service.create_payment(
        allocations=[{"billing_id": billing.pk, "amount": 100}], paid_date=timezone.localdate()
    )
    service.confirm_payment(payment.pk)
    RoleModuleAccess.objects.filter(role=account.role, module_key="finance_billings").update(
        can_view=False
    )
    delivery = MessageLog.objects.get(source_type="payment", recipient=account, channel="EMAIL")
    with patch("notifications.channels.email.EmailChannel.send") as send:
        OutboxService().dispatch(delivery.pk)
    send.assert_not_called()
    delivery.refresh_from_db()
    assert delivery.dispatch_state == "REVOKED"


@pytest.mark.parametrize("via_update", [False, True])
def test_global_calendar_clears_class_and_family_destination_is_accessible(
    user, school, client, via_update
):
    from django.urls import reverse

    account, _, cls, _ = family(user)
    service = CalendarService(user=user)
    event = service.create_event(
        {
            "title": "Aviso",
            "start_date": timezone.localdate(),
            "end_date": timezone.localdate(),
            "type": "MEETING",
            "audience": "CLASS" if via_update else "ALL",
            "class_obj_id": cls.pk,
            "is_public": True,
        }
    )
    if via_update:
        event = service.update_event(event.pk, {"audience": "ALL"})
    assert event.class_obj_id is None
    client.force_login(account)
    assert client.get(reverse("event_detail", args=[event.pk]), follow=True).status_code == 200


def test_payment_destination_requires_only_billings_capability(user, school, client):
    from django.urls import reverse

    billing, account, _, _ = billing_for_family(user)
    RoleModuleAccess.objects.filter(role=account.role, module_key="finance_overview").update(
        can_view=False
    )
    service = PaymentService(user=user)
    payment = service.create_payment(
        allocations=[{"billing_id": billing.pk, "amount": 100}], paid_date=timezone.localdate()
    )
    service.confirm_payment(payment.pk)
    notice = Notification.objects.filter(recipient=account).latest("created_at")
    assert notice.action_url == reverse("billing_list")
    client.force_login(account)
    assert client.get(notice.action_url).status_code == 200
