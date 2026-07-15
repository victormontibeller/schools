"""Testes do AuditService."""

import datetime as dt
from decimal import Decimal

import pytest

from audit.models import AuditLog
from audit.services import AuditService
from base import context


@pytest.mark.django_db
class TestAuditService:
    def _fake(self, pk="abc-123"):
        class Fake:
            _meta = type("Meta", (), {"get_fields": lambda s: []})()

            def __init__(self, pk):
                self.pk = pk

        return Fake(pk)

    def test_record_insert(self, user):
        log = AuditService(user=user).record_insert(self._fake())
        assert log.operation == AuditLog.Operation.INSERT
        assert log.user == user

    def test_record_update(self, user):
        log = AuditService(user=user).record_update(self._fake(), {"name": "Before"})
        assert log.operation == AuditLog.Operation.UPDATE
        assert log.old_values == {"name": "Before"}

    def test_record_delete(self, user):
        log = AuditService(user=user).record_delete(self._fake())
        assert log.operation == AuditLog.Operation.DELETE
        assert log.new_values is None

    def test_record_restore(self, user):
        log = AuditService(user=user).record_restore(self._fake())
        assert log.operation == AuditLog.Operation.RESTORE

    def test_correlation_id(self, user):
        t = context.correlation_id.set("cid-test")
        try:
            log = AuditService(user=user).record_insert(self._fake())
            assert log.correlation_id == "cid-test"
        finally:
            context.correlation_id.reset(t)

    def test_ip_captured(self, user):
        t = context.request_ip.set("10.0.0.1")
        try:
            log = AuditService(user=user).record_insert(self._fake())
            assert log.ip_address == "10.0.0.1"
        finally:
            context.request_ip.reset(t)

    def test_excludes_sensitive_fields(self, user):
        result = AuditService._serialize(self._fake())
        assert "password" not in result

    def test_serialize_redacts_pii_and_normalizes_field_values(self):
        class Field:
            def __init__(self, attname=None):
                if attname is not None:
                    self.attname = attname

        class Fake:
            pk = "audit-object"
            email = "sensitive@example.com"
            created_at = dt.datetime(2026, 7, 13, 12, 0)
            amount = Decimal("10.25")
            active = True
            _meta = type(
                "Meta",
                (),
                {
                    "get_fields": lambda self: [
                        Field(),
                        Field("email"),
                        Field("created_at"),
                        Field("amount"),
                        Field("active"),
                    ]
                },
            )()

        result = AuditService._serialize(Fake())

        assert result == {
            "email": "[REDACTED]",
            "created_at": "2026-07-13T12:00:00",
            "amount": "10.25",
            "active": True,
        }

    def test_redact_handles_none_and_sensitive_snapshot_keys(self):
        assert AuditService._redact(None) is None
        assert AuditService._redact({"phone_mobile": "secret", "status": "ACTIVE"}) == {
            "phone_mobile": "[REDACTED]",
            "status": "ACTIVE",
        }
