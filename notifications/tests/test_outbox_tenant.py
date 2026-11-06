"""Concorrência real de claims e webhooks em PostgreSQL isolado por schema."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest
from django.db import connection, connections
from django.utils import timezone

from base import context
from base.context import tenant_schema_context

pytestmark = [
    pytest.mark.tenant,
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(os.environ.get("DJANGO_ENV") != "test_pg", reason="Requer PostgreSQL"),
]


@pytest.fixture
def outbox_tenant():
    from core.models import CustomUser, Role
    from notifications.announcement_services import AnnouncementService
    from notifications.models import MessageLog
    from tenancy.models import Domain, School

    connection.set_schema_to_public()
    school = School(schema_name=f"outbox_{uuid.uuid4().hex[:12]}", name="Escola fictícia")
    school.save(verbosity=0)
    try:
        hostname = school.schema_name.replace("_", "-")
        Domain.objects.create(
            tenant=school,
            domain=f"{hostname}.example.test",
            is_primary=True,
        )
        with tenant_schema_context(school.schema_name):
            role, _ = Role.objects.get_or_create(name="ADMIN")
            user = CustomUser.objects.create_user(
                email="admin@example.test", password="Violeta824", role=role
            )
            with patch("notifications.outbox_services.publish_task_after_commit"):
                service = AnnouncementService(user=user)
                draft = service.create_announcement(
                    {"title": "Teste", "body": "Privado", "audience": "STAFF", "send_email": True}
                )
                service.publish_announcement(draft.pk, version=draft.version)
            yield school, MessageLog.objects.get(channel="EMAIL")
    finally:
        connection.set_schema_to_public()
        school.delete(force_drop=True)


def race(school, operation):
    barrier = Barrier(2)

    def run(index):
        conn = connections["default"]
        conn.set_tenant(school)
        token = context.current_tenant.set(school.schema_name)
        try:
            barrier.wait(timeout=10)
            return operation(index)
        finally:
            context.current_tenant.reset(token)
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        return list(executor.map(run, range(2)))


def test_outbox_claim_locks_only_log_with_nullable_joins(outbox_tenant):
    from notifications.outbox_services import OutboxService

    _, delivery = outbox_tenant
    claimed = OutboxService().claim_delivery(delivery.pk)
    assert claimed.lease_token
    assert OutboxService().claim_delivery(delivery.pk) is None


def test_two_workers_cannot_claim_same_delivery(outbox_tenant):
    from notifications.outbox_services import OutboxService

    school, delivery = outbox_tenant
    claims = race(school, lambda _: bool(OutboxService().claim_delivery(delivery.pk)))
    assert sorted(claims) == [False, True]
    delivery.refresh_from_db()
    assert delivery.attempts == 1


def test_duplicate_webhook_race_records_one_receipt_without_error(outbox_tenant):
    from notifications.delivery_services import MessageDeliveryService
    from notifications.models import WebhookEventReceipt

    school, delivery = outbox_tenant
    occurred = timezone.now()

    def process(_):
        return MessageDeliveryService().process_resend_event(
            external_event_id="repeated-event",
            event_type="email.delivered",
            provider_message_id="provider-message",
            message_log_id=str(delivery.pk),
            occurred_at=occurred,
        )

    assert sorted(race(school, process)) == [False, True]
    assert WebhookEventReceipt.objects.filter(external_event_id="repeated-event").count() == 1
    delivery.refresh_from_db()
    assert delivery.status == "DELIVERED"
