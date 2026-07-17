"""Testes da task de convite de responsáveis."""

from unittest.mock import MagicMock, patch

import pytest

from guardians.tasks import send_guardian_invitation_task
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
    transport.last_log_id = "guardian-message-log"
    return transport


@pytest.mark.django_db
def test_guardian_invitation_task_retries_transient_failure(user):
    transport = _email_transport(success=False, retryable=True)
    with (
        patch("guardians.tasks.get_transport", return_value=transport),
        patch.object(
            send_guardian_invitation_task, "retry", side_effect=RuntimeError("retry")
        ) as retry,
        pytest.raises(RuntimeError, match="retry"),
    ):
        send_guardian_invitation_task.run("demo", str(user.pk), "https://demo/invite")
    assert retry.call_args.kwargs["kwargs"]["message_log_id"] == "guardian-message-log"


@pytest.mark.django_db
def test_guardian_invitation_task_does_not_retry_permanent_failure(user):
    transport = _email_transport(success=False, retryable=False)
    with (
        patch("guardians.tasks.get_transport", return_value=transport),
        patch.object(send_guardian_invitation_task, "retry") as retry,
    ):
        send_guardian_invitation_task.run("demo", str(user.pk), "https://demo/invite")
    retry.assert_not_called()


@pytest.mark.django_db
def test_guardian_invitation_task_forwards_message_log_on_retry(user):
    transport = _email_transport(success=True)
    with patch("guardians.tasks.get_transport", return_value=transport):
        send_guardian_invitation_task.run(
            "demo", str(user.pk), "https://demo/invite", "existing-message-log"
        )
    call = transport.send_individual.call_args
    assert call.kwargs["force"] is True
    assert call.kwargs["message_log_id"] == "existing-message-log"
