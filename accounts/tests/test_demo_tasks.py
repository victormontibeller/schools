"""Testes das tasks de confirmação e expiração do DEMO."""

from unittest.mock import patch

import pytest

from accounts.tasks import (
    expire_demo_users_task,
    send_demo_verification_task,
    send_teacher_invitation_task,
)


@pytest.mark.django_db
def test_demo_verification_task_ignores_missing_user():
    assert (
        send_demo_verification_task.run("demo", "00000000-0000-0000-0000-000000000000", "url")
        is None
    )


@pytest.mark.django_db
def test_demo_verification_task_uses_notification_transport(user):
    with patch("notifications.transport.MessageTransport.send_individual", return_value=1) as send:
        send_demo_verification_task.run("demo", str(user.pk), "https://demo/verify")
    send.assert_called_once()


@pytest.mark.django_db
def test_demo_verification_task_retries_when_transport_does_not_send(user):
    with (
        patch("notifications.transport.MessageTransport.send_individual", return_value=0),
        patch.object(send_demo_verification_task, "retry", side_effect=RuntimeError("retry")),
        pytest.raises(RuntimeError, match="retry"),
    ):
        send_demo_verification_task.run("demo", str(user.pk), "https://demo/verify")


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
    with patch("notifications.transport.MessageTransport.send_individual", return_value=1) as send:
        send_teacher_invitation_task.run("demo", str(user.pk), "https://demo/invite")
    send.assert_called_once()

    with (
        patch("notifications.transport.MessageTransport.send_individual", return_value=0),
        patch.object(send_teacher_invitation_task, "retry", side_effect=RuntimeError("retry")),
        pytest.raises(RuntimeError, match="retry"),
    ):
        send_teacher_invitation_task.run("demo", str(user.pk), "https://demo/invite")
