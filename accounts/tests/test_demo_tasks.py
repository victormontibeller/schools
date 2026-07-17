"""Testes das tasks de confirmação e convites de contas."""

from unittest.mock import MagicMock, patch

import pytest

from accounts.tasks import (
    expire_demo_users_task,
    send_demo_verification_task,
    send_teacher_invitation_task,
)
from notifications.channels import ChannelResult


def _email_transport(*, success: bool, retryable: bool = False):
    transport = MagicMock()
    transport.send_individual.return_value = int(success)
    transport.last_result = ChannelResult(
        success=success,
        channel="EMAIL",
        recipient_address="",
        retryable=retryable,
    )
    transport.last_log_id = "opaque-message-log"
    return transport


@pytest.mark.django_db
def test_demo_verification_task_ignores_missing_user():
    assert (
        send_demo_verification_task.run("demo", "00000000-0000-0000-0000-000000000000", "url")
        is None
    )


@pytest.mark.django_db
def test_demo_verification_task_uses_notification_transport(user):
    transport = _email_transport(success=True)
    with patch("accounts.tasks.get_transport", return_value=transport):
        send_demo_verification_task.run("demo", str(user.pk), "https://demo/verify")
    transport.send_individual.assert_called_once()


@pytest.mark.django_db
def test_demo_verification_task_retries_when_transport_does_not_send(user):
    transport = _email_transport(success=False, retryable=True)
    with (
        patch("accounts.tasks.get_transport", return_value=transport),
        patch.object(
            send_demo_verification_task, "retry", side_effect=RuntimeError("retry")
        ) as retry,
        pytest.raises(RuntimeError, match="retry"),
    ):
        send_demo_verification_task.run("demo", str(user.pk), "https://demo/verify")
    assert retry.call_args.kwargs["kwargs"]["message_log_id"] == "opaque-message-log"


def test_expire_demo_task_delegates_inside_schema():
    with patch("accounts.services.AccountService.expire_demo_users", return_value=2) as expire:
        assert expire_demo_users_task.run("demo") == 2
    expire.assert_called_once_with()


@pytest.mark.django_db
def test_teacher_invitation_task_ignores_missing_user():
    assert (
        send_teacher_invitation_task.run("demo", "00000000-0000-0000-0000-000000000000", "url")
        is None
    )


@pytest.mark.django_db
def test_teacher_invitation_task_sends_and_retries(user):
    transport = _email_transport(success=True)
    with patch("accounts.tasks.get_transport", return_value=transport):
        send_teacher_invitation_task.run("demo", str(user.pk), "https://demo/invite")
    transport.send_individual.assert_called_once()

    transport = _email_transport(success=False, retryable=True)
    with (
        patch("accounts.tasks.get_transport", return_value=transport),
        patch.object(
            send_teacher_invitation_task, "retry", side_effect=RuntimeError("retry")
        ) as retry,
        pytest.raises(RuntimeError, match="retry"),
    ):
        send_teacher_invitation_task.run("demo", str(user.pk), "https://demo/invite")
    assert retry.call_args.kwargs["kwargs"]["message_log_id"] == "opaque-message-log"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("task", "url"),
    [
        (send_demo_verification_task, "https://demo/verify"),
        (send_teacher_invitation_task, "https://demo/invite"),
    ],
)
def test_account_email_tasks_do_not_retry_permanent_failure(user, task, url):
    transport = _email_transport(success=False, retryable=False)
    with (
        patch("accounts.tasks.get_transport", return_value=transport),
        patch.object(task, "retry") as retry,
    ):
        task.run("demo", str(user.pk), url)
    retry.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("task", "url"),
    [
        (send_demo_verification_task, "https://demo/verify"),
        (send_teacher_invitation_task, "https://demo/invite"),
    ],
)
def test_account_email_tasks_forward_message_log_on_retry(user, task, url):
    transport = _email_transport(success=True)
    with patch("accounts.tasks.get_transport", return_value=transport):
        task.run("demo", str(user.pk), url, "existing-message-log")
    assert transport.send_individual.call_args.kwargs["message_log_id"] == "existing-message-log"
