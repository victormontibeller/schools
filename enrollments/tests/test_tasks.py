"""Garantias de segurança e idempotência da task de lembrete documental."""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from enrollments.tasks import (
    dispatch_stale_document_reminder_recovery,
    reconcile_stale_document_reminders,
    send_enrollment_document_reminder,
)


def test_task_refuses_public_schema():
    with patch("enrollments.services.EnrollmentReminderService.claim_for_delivery") as get:
        send_enrollment_document_reminder.run("public", "opaque-id")
    get.assert_not_called()


def test_reconciler_task_refuses_public_schema():
    with patch("enrollments.services.EnrollmentReminderService.reconcile_stale_claims") as recover:
        assert reconcile_stale_document_reminders.run("public") == 0
    recover.assert_not_called()


def test_reconciler_task_activates_tenant_context():
    from base import context

    def recover(_service, *, tenant_schema):
        assert context.current_tenant.get() == "tenant_a"
        assert tenant_schema == "tenant_a"
        return 2

    with patch(
        "enrollments.services.EnrollmentReminderService.reconcile_stale_claims",
        autospec=True,
        side_effect=recover,
    ):
        assert reconcile_stale_document_reminders.run("tenant_a") == 2


@pytest.mark.django_db
def test_recovery_dispatcher_publishes_one_task_per_active_tenant():
    from tenancy.contracts import School

    School.objects.create(schema_name="tenant_a", name="Escola A")
    School.objects.create(schema_name="tenant_b", name="Escola B")
    School.objects.create(schema_name="tenant_inactive", name="Escola Inativa", is_active=False)
    with patch.object(reconcile_stale_document_reminders, "delay") as delay:
        count = dispatch_stale_document_reminder_recovery.run()

    assert count == 2
    assert {call.args[0] for call in delay.call_args_list} == {"tenant_a", "tenant_b"}


def test_task_records_real_transport_success_and_reuses_message_log():
    reminder = SimpleNamespace(
        pk=uuid.uuid4(),
        status="FAILED",
        recipient=object(),
        message_log_id=uuid.uuid4(),
    )
    transport = MagicMock()
    transport.send_individual.return_value = 1
    transport.last_log_id = reminder.message_log_id
    with (
        patch(
            "enrollments.services.EnrollmentReminderService.claim_for_delivery",
            return_value=reminder,
        ),
        patch("notifications.task_helpers.get_transport", return_value=transport),
        patch("notifications.task_helpers.retry_email_if_needed"),
        patch("enrollments.services.EnrollmentReminderService.record_delivery_result") as record,
    ):
        send_enrollment_document_reminder.run("tenant_a", str(reminder.pk))

    assert transport.send_individual.call_args.kwargs["message_log_id"] == reminder.message_log_id
    record.assert_called_once_with(
        reminder.pk,
        tenant_schema="tenant_a",
        success=True,
        message_log_id=reminder.message_log_id,
    )


def test_task_records_real_transport_failure():
    reminder = SimpleNamespace(
        pk=uuid.uuid4(),
        status="PENDING",
        recipient=object(),
        message_log_id=None,
    )
    transport = MagicMock()
    transport.send_individual.return_value = 0
    transport.last_log_id = uuid.uuid4()
    with (
        patch(
            "enrollments.services.EnrollmentReminderService.claim_for_delivery",
            return_value=reminder,
        ),
        patch("notifications.task_helpers.get_transport", return_value=transport),
        patch("notifications.task_helpers.retry_email_if_needed"),
        patch("enrollments.services.EnrollmentReminderService.record_delivery_result") as record,
    ):
        send_enrollment_document_reminder.run("tenant_a", str(reminder.pk))

    record.assert_called_once_with(
        reminder.pk,
        tenant_schema="tenant_a",
        success=False,
        message_log_id=transport.last_log_id,
    )


def test_task_keeps_reminder_sending_while_retry_is_scheduled():
    class RetryScheduledError(Exception):
        pass

    reminder = SimpleNamespace(
        pk=uuid.uuid4(),
        recipient=object(),
        message_log_id=uuid.uuid4(),
    )
    transport = MagicMock()
    transport.send_individual.return_value = 0
    transport.last_log_id = reminder.message_log_id
    transport.last_result = SimpleNamespace(retryable=True)
    with (
        patch(
            "enrollments.services.EnrollmentReminderService.claim_for_delivery",
            return_value=reminder,
        ),
        patch("notifications.task_helpers.get_transport", return_value=transport),
        patch(
            "notifications.task_helpers.retry_email_if_needed",
            side_effect=RetryScheduledError,
        ),
        patch("enrollments.services.EnrollmentReminderService.record_delivery_result") as record,
        pytest.raises(RetryScheduledError),
    ):
        send_enrollment_document_reminder.run("tenant_a", str(reminder.pk))

    record.assert_not_called()


def test_task_resumes_only_the_message_log_carried_by_retry():
    reminder_id = str(uuid.uuid4())
    message_log_id = str(uuid.uuid4())
    with patch(
        "enrollments.services.EnrollmentReminderService.claim_for_delivery",
        return_value=None,
    ) as claim:
        send_enrollment_document_reminder.run("tenant_a", reminder_id, message_log_id)

    claim.assert_called_once_with(
        reminder_id,
        tenant_schema="tenant_a",
        message_log_id=message_log_id,
    )


def test_task_retries_unexpected_transport_failure_with_same_message_log():
    class RetryScheduledError(Exception):
        pass

    reminder = SimpleNamespace(
        pk=uuid.uuid4(),
        recipient=object(),
        message_log_id=uuid.uuid4(),
    )
    with (
        patch(
            "enrollments.services.EnrollmentReminderService.claim_for_delivery",
            return_value=reminder,
        ),
        patch(
            "notifications.task_helpers.get_transport",
            side_effect=RuntimeError("provider response with sensitive detail"),
        ),
        patch.object(
            send_enrollment_document_reminder,
            "retry",
            side_effect=RetryScheduledError,
        ) as retry,
        patch("enrollments.services.EnrollmentReminderService.record_delivery_result") as record,
        pytest.raises(RetryScheduledError),
    ):
        send_enrollment_document_reminder.run("tenant_a", str(reminder.pk))

    assert retry.call_args.kwargs["kwargs"] == {
        "tenant_schema": "tenant_a",
        "reminder_id": str(reminder.pk),
        "message_log_id": str(reminder.message_log_id),
    }
    assert str(retry.call_args.kwargs["exc"]) == "enrollment_reminder_transport_failed"
    record.assert_not_called()


def test_task_records_generic_failure_when_recipient_becomes_ineligible_in_transport():
    reminder = SimpleNamespace(
        pk=uuid.uuid4(),
        recipient=object(),
        message_log_id=uuid.uuid4(),
    )
    transport = MagicMock()
    transport.send_individual.return_value = 0
    transport.last_log_id = reminder.message_log_id
    transport.last_result = None
    with (
        patch(
            "enrollments.services.EnrollmentReminderService.claim_for_delivery",
            return_value=reminder,
        ),
        patch("notifications.task_helpers.get_transport", return_value=transport),
        patch("notifications.task_helpers.retry_email_if_needed"),
        patch(
            "notifications.delivery_services.MessageDeliveryService.record_channel_result"
        ) as record_channel,
        patch("enrollments.services.EnrollmentReminderService.record_delivery_result") as record,
    ):
        send_enrollment_document_reminder.run("tenant_a", str(reminder.pk))

    assert record_channel.call_args.args[0] == reminder.message_log_id
    assert record_channel.call_args.args[1].error_message == "recipient_not_eligible"
    record.assert_called_once_with(
        reminder.pk,
        tenant_schema="tenant_a",
        success=False,
        message_log_id=reminder.message_log_id,
    )


def test_task_closes_same_log_after_unexpected_retry_exhaustion():
    reminder = SimpleNamespace(
        pk=uuid.uuid4(),
        recipient=object(),
        message_log_id=uuid.uuid4(),
    )
    with (
        patch(
            "enrollments.services.EnrollmentReminderService.claim_for_delivery",
            return_value=reminder,
        ),
        patch(
            "notifications.task_helpers.get_transport",
            side_effect=RuntimeError("provider detail must not persist"),
        ),
        patch.object(send_enrollment_document_reminder, "max_retries", 0),
        patch(
            "notifications.delivery_services.MessageDeliveryService.record_channel_result"
        ) as record_channel,
        patch("enrollments.services.EnrollmentReminderService.record_delivery_result") as record,
    ):
        send_enrollment_document_reminder.run("tenant_a", str(reminder.pk))

    assert record_channel.call_args.args[0] == reminder.message_log_id
    assert record_channel.call_args.args[1].error_message == "unexpected_delivery_failure"
    record.assert_called_once_with(
        reminder.pk,
        tenant_schema="tenant_a",
        success=False,
        message_log_id=reminder.message_log_id,
    )
