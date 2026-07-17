"""Testes dos helpers compartilhados de retry Celery."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from notifications.channels import ChannelResult
from notifications.task_helpers import retry_email_if_needed


def _transport(*, retryable: bool):
    return SimpleNamespace(
        last_result=ChannelResult(
            success=False,
            channel="EMAIL",
            recipient_address="",
            retryable=retryable,
        ),
        last_log_id="stable-message-log",
    )


def _task(*, retries: int = 0):
    return SimpleNamespace(
        request=SimpleNamespace(retries=retries, kwargs={"event": "invite"}),
        max_retries=3,
        retry=MagicMock(side_effect=RuntimeError("retry")),
    )


def test_retry_email_preserves_message_log_for_transient_failure():
    task = _task()

    with pytest.raises(RuntimeError, match="retry"):
        retry_email_if_needed(task, _transport(retryable=True), 0)

    assert task.retry.call_args.kwargs["kwargs"] == {
        "event": "invite",
        "message_log_id": "stable-message-log",
    }


@pytest.mark.parametrize(
    ("result", "retryable"),
    [(1, True), (0, False)],
)
def test_retry_email_ignores_success_and_permanent_failure(result, retryable):
    task = _task()

    retry_email_if_needed(task, _transport(retryable=retryable), result)

    task.retry.assert_not_called()


def test_retry_email_marks_same_log_when_attempts_are_exhausted():
    task = _task(retries=3)
    with patch(
        "notifications.delivery_services.MessageDeliveryService.record_channel_result"
    ) as record:
        retry_email_if_needed(task, _transport(retryable=True), 0)

    task.retry.assert_not_called()
    message_log_id, result = record.call_args.args
    assert message_log_id == "stable-message-log"
    assert result.error_message == "retry_exhausted"
    assert result.retryable is False
