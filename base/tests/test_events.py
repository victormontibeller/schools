"""Testes do sistema de eventos in-process (não requerem Django).

Cobrem o `EventDispatcher` e a integracão `BaseService._record_audit → DomainEvent →
handler de auditoria`, mantendo `base/` testável sem infraestrutura.
"""

import logging

import pytest

from base.events import DomainEvent, Event, EventDispatcher
from base.services import BaseService


class TestEventDispatcher:
    def test_register_and_dispatch_same_event_type(self):
        seen: list[Event] = []
        d = EventDispatcher()
        d.register(DomainEvent, lambda e: seen.append(e))

        e = DomainEvent(operation="INSERT", instance=None)
        d.dispatch(e)

        assert seen == [e]

    def test_dispatch_only_handlers_for_event_type(self):
        seen: list[str] = []
        d = EventDispatcher()
        d.register(DomainEvent, lambda e: seen.append("domain"))
        d.register(Event, lambda e: seen.append("base"))  # base nunca dispara p/ DomainEvent

        d.dispatch(DomainEvent(operation="DELETE", instance=None))

        assert seen == ["domain"]

    def test_failed_handler_does_not_break_dispatch(self, caplog):
        called: list[str] = []
        d = EventDispatcher()

        def boom(_):
            raise RuntimeError("boom")

        d.register(DomainEvent, boom)
        d.register(DomainEvent, lambda e: called.append("after"))
        d.dispatch(DomainEvent(operation="UPDATE", instance=None))
        assert called == ["after"]

    def test_dispatch_unknown_event_is_noop(self):
        d = EventDispatcher()
        d.dispatch(DomainEvent(operation="INSERT", instance=None))  # sem handlers


class TestDomainEvent:
    def test_defaults_are_neutral(self):
        e = DomainEvent()
        assert e.operation == ""
        assert e.instance is None
        assert e.correlation_id == ""
        assert isinstance(e, Event)

    def test_is_frozen_shape(self):
        e = DomainEvent(operation="INSERT", instance="x", user="u1", correlation_id="c1")
        assert e.operation == "INSERT"
        assert e.user == "u1"
        assert e.correlation_id == "c1"


class TestBaseServiceDispatchesDomainEvent:
    """`BaseService._record_audit` deve disparar `DomainEvent` no dispatcher global."""

    def test_dispatched_event_carries_operation_instance_user(self, monkeypatch):
        recorded: list[DomainEvent] = []
        from base import events

        monkeypatch.setattr(events, "dispatcher", events.EventDispatcher())
        events.dispatcher.register(DomainEvent, lambda e: recorded.append(e))

        class FakeInstance:
            pk = "obj-1"

        svc = BaseService(user="user-fixture-12")
        svc._record_audit("INSERT", FakeInstance())

        assert len(recorded) == 1
        evt = recorded[0]
        assert evt.operation == "INSERT"
        assert evt.instance.pk == "obj-1"
        assert evt.user == "user-fixture-12"

    def test_dispatch_failure_is_swallowed_with_log(self, caplog, monkeypatch):
        """Bugs em handler (audit, etc.) nunca derrubam o service."""
        from base import events

        monkeypatch.setattr(events, "dispatcher", events.EventDispatcher())

        def boom(_):
            raise RuntimeError("audit down")

        events.dispatcher.register(DomainEvent, boom)

        svc = BaseService()
        # Não deve levantar — serviço continua funcionando.
        svc._record_audit("DELETE", object())


class TestBaseServiceLogGuardPII:
    """`BaseService._log` должен rejeitar PII em `extra` (docs/04_SECURITY.md §39)."""

    def test_rejects_email_in_debug_mode(self, settings):
        settings.DEBUG = True
        import logging

        logging.disable(logging.INFO)  # evita ruído no stdout
        try:
            svc = BaseService()
            with pytest.raises(RuntimeError, match="PII"):
                svc._log("anything", email="victim@test.com")
        finally:
            logging.disable(logging.NOTSET)

    def test_rejects_password_in_debug_mode(self, settings):
        settings.DEBUG = True
        import logging

        logging.disable(logging.INFO)
        try:
            svc = BaseService()
            with pytest.raises(RuntimeError, match="PII"):
                svc._log("anything", password="Senha123")
        finally:
            logging.disable(logging.NOTSET)

    def test_prod_drops_key_and_logs_warning_instead_of_raising(self, settings, caplog):
        settings.DEBUG = False
        svc = BaseService()
        # Não levanta — apenas loga warning e remove a chave.
        with caplog.at_level(logging.WARNING, logger="base.services"):
            svc._log("ok", email="victim@test.com")

        # A mensagem escrita pelo log é "PII descartado de log".
        assert any("PII descartado" in r.getMessage() for r in caplog.records)

    def test_non_pii_keys_pass_through(self, settings):
        settings.DEBUG = True
        svc = BaseService()
        # Estes são aceitos: IDs, contagens, modelo, etc.
        svc._log("ok", user_id="123", model_name="Student", count=5)
