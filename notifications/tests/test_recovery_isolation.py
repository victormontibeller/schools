"""Falhas de coordenação não impedem recuperar outras escolas ou intenções."""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, call, patch
from uuid import uuid4

import pytest

from base.context import current_tenant, tenant_schema_context
from base.exceptions import BusinessRuleViolationError, PermissionDeniedError
from notifications import outbox_tasks

PRIVATE_ERROR = "private-recipient@example.test conteúdo reservado da comunicação"


@pytest.fixture(autouse=True)
def capture_recovery_logs(caplog):
    """Habilita os eventos sob teste apesar do nível CRITICAL do perfil de testes."""
    caplog.set_level("WARNING", logger=outbox_tasks.__name__)


def assert_private_error_is_absent(caplog):
    records = [record for record in caplog.records if record.name == outbox_tasks.__name__]
    assert records
    for record in records:
        assert PRIVATE_ERROR not in str(record.__dict__)
        assert record.exc_info is None
        assert record.exc_text is None
    return records


@pytest.mark.parametrize("failure_stage", ["activation", "recovery"])
def test_recover_continues_with_next_tenant_after_failure(monkeypatch, caplog, failure_stage):
    visited = []

    @contextmanager
    def activate(schema):
        with tenant_schema_context(schema):
            if schema == "failed_school" and failure_stage == "activation":
                raise RuntimeError(PRIVATE_ERROR)
            yield

    def recover(schema):
        assert current_tenant.get() == schema
        if schema == "failed_school":
            raise RuntimeError(PRIVATE_ERROR)
        visited.append(schema)

    monkeypatch.setattr(outbox_tasks, "tenant_schema_context", activate)
    monkeypatch.setattr(outbox_tasks, "recover_tenant_communications", recover)
    with patch(
        "tenancy.selectors.SchoolSelector.list_active_schemas",
        return_value=["failed_school", "healthy_school"],
    ):
        outbox_tasks.recover_communications_task()

    assert visited == ["healthy_school"]
    assert current_tenant.get() == "public"
    record = assert_private_error_is_absent(caplog)[0]
    assert record.getMessage() == "communications_recovery_failed"
    assert record.tenant_schema == "failed_school"
    assert record.exception_type == "RuntimeError"


@pytest.fixture
def recovery_dependencies():
    """Isola somente as portas chamadas pelo coordenador, sem simular regras dos services."""
    with (
        patch("notifications.models.Announcement.objects.filter") as scheduled,
        patch("notifications.announcement_services.AnnouncementService") as announcement_service,
        patch(
            "notifications.outbox_selectors.OutboxSelector.pending_ids", return_value=[]
        ) as pending,
        patch("notifications.outbox_services.OutboxService") as outbox_service,
        patch(
            "service_requests.selectors.ServiceRequestSelector.overdue_ids", return_value=[]
        ) as overdue,
        patch("service_requests.event_services.RequestEventService") as request_service,
    ):
        scheduled.return_value.select_related.return_value.__getitem__.return_value = []
        yield SimpleNamespace(
            scheduled=scheduled,
            publish=announcement_service.return_value.publish_announcement,
            pending=pending,
            dispatch=outbox_service.return_value.dispatch,
            overdue=overdue,
            notify=request_service.return_value.notify_overdue_request,
        )


@pytest.mark.parametrize(
    "error_type", [BusinessRuleViolationError, PermissionDeniedError, RuntimeError]
)
def test_recover_continues_after_scheduled_announcement_failure(
    recovery_dependencies, caplog, error_type
):
    dependencies = recovery_dependencies
    announcements = [SimpleNamespace(pk=uuid4(), author=Mock(), version=1) for _ in range(2)]
    dependencies.scheduled.return_value.select_related.return_value.__getitem__.return_value = (
        announcements
    )
    dependencies.publish.side_effect = [error_type(PRIVATE_ERROR), None]
    delivery_id = uuid4()
    dependencies.pending.return_value = [delivery_id]

    outbox_tasks.recover_tenant_communications("test_school")

    assert dependencies.publish.call_args_list == [
        call(item.pk, version=1) for item in announcements
    ]
    dependencies.dispatch.assert_called_once_with(delivery_id)
    record = assert_private_error_is_absent(caplog)[0]
    assert record.tenant_schema == "test_school"
    assert record.announcement_id == str(announcements[0].pk)
    if error_type is RuntimeError:
        assert record.getMessage() == "announcement_recovery_failed"
        assert record.exception_type == "RuntimeError"
    else:
        assert record.getMessage() == "announcement_schedule_blocked"


def test_recover_continues_with_deliveries_and_sla_after_dispatch_failure(
    recovery_dependencies, caplog
):
    dependencies = recovery_dependencies
    delivery_ids = [uuid4(), uuid4()]
    request_id = uuid4()
    dependencies.pending.return_value = delivery_ids
    dependencies.dispatch.side_effect = [RuntimeError(PRIVATE_ERROR), None]
    dependencies.overdue.return_value = [request_id]

    outbox_tasks.recover_tenant_communications("test_school")

    assert dependencies.dispatch.call_args_list == [call(item) for item in delivery_ids]
    dependencies.notify.assert_called_once_with(request_id)
    record = assert_private_error_is_absent(caplog)[0]
    assert record.getMessage() == "outbox_recovery_failed"
    assert record.tenant_schema == "test_school"
    assert record.delivery_id == str(delivery_ids[0])
    assert record.exception_type == "RuntimeError"


def test_recover_continues_with_next_overdue_request_after_failure(recovery_dependencies, caplog):
    dependencies = recovery_dependencies
    request_ids = [uuid4(), uuid4()]
    dependencies.overdue.return_value = request_ids
    dependencies.notify.side_effect = [RuntimeError(PRIVATE_ERROR), None]

    outbox_tasks.recover_tenant_communications("test_school")

    assert dependencies.notify.call_args_list == [call(item) for item in request_ids]
    record = assert_private_error_is_absent(caplog)[0]
    assert record.getMessage() == "request_recovery_failed"
    assert record.tenant_schema == "test_school"
    assert record.request_id == str(request_ids[0])
    assert record.exception_type == "RuntimeError"
