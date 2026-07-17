"""Testes de funcoes utilitarias e tasks."""

import logging

import pytest

from notifications.transport import render_template


class TestRenderTemplate:
    def test_simple_substitution(self):
        result = render_template("Ola {{nome}}!", {"nome": "Joao"})
        assert result == "Ola Joao!"

    def test_multiple_variables(self):
        result = render_template(
            "{{saudacao}}, {{nome}}. Bem-vindo a {{escola}}.",
            {"saudacao": "Ola", "nome": "Maria", "escola": "Escola ABC"},
        )
        assert result == "Ola, Maria. Bem-vindo a Escola ABC."

    def test_missing_variable_keeps_placeholder(self):
        result = render_template("Ola {{nome}}!", {})
        assert result == "Ola {{nome}}!"

    def test_empty_template(self):
        result = render_template("", {"nome": "X"})
        assert result == ""


@pytest.mark.django_db
class TestEventHandlers:
    def test_register_handlers_idempotent(self):
        from notifications.handlers import register_event_handlers

        register_event_handlers()
        register_event_handlers()

    def test_domain_event_none_instance(self):
        from base.events import DomainEvent
        from notifications.handlers import _on_domain_event

        _on_domain_event(DomainEvent(operation="INSERT", instance=None))

    def test_student_created_notifies_guardian(self, user):
        from base.events import DomainEvent
        from core.models import CustomUser
        from guardians.models import Guardian, StudentGuardian
        from notifications.handlers import _handle_student_created
        from students.models import Student

        guardian_user = CustomUser.objects.create_user(
            email="guardian-ev@test.com",
            password="Senha123",
            first_name="Resp",
            last_name="Event",
        )
        guardian = Guardian.objects.create(
            user=guardian_user,
            created_by=user,
            updated_by=user,
        )
        student = Student.objects.create(
            first_name="Aluno",
            last_name="Evento",
            birth_date="2010-01-01",
            enrollment_number="EVT001",
            created_by=user,
            updated_by=user,
        )
        StudentGuardian.objects.create(
            student=student,
            guardian=guardian,
            is_primary=True,
            created_by=user,
            updated_by=user,
        )

        from notifications.models import Notification

        count_before = Notification.objects.count()
        _handle_student_created(DomainEvent(operation="INSERT", instance=student, user=user))
        assert Notification.objects.count() == count_before + 1

    def test_attendance_alert_creates_notification(self, user):
        from base.events import DomainEvent
        from core.models import CustomUser
        from guardians.models import Guardian, StudentGuardian
        from notifications.handlers import _handle_attendance_threshold
        from students.models import Student

        guardian_user = CustomUser.objects.create_user(
            email="guardian-att@test.com",
            password="Senha123",
            first_name="Resp",
            last_name="Att",
        )
        guardian = Guardian.objects.create(
            user=guardian_user,
            created_by=user,
            updated_by=user,
        )
        student = Student.objects.create(
            first_name="Aluno",
            last_name="Att",
            birth_date="2010-01-01",
            enrollment_number="ATT001",
            created_by=user,
            updated_by=user,
        )
        StudentGuardian.objects.create(
            student=student,
            guardian=guardian,
            is_primary=True,
            created_by=user,
            updated_by=user,
        )

        from notifications.models import Notification

        count_before = Notification.objects.count()
        _handle_attendance_threshold(DomainEvent(operation="ALERT", instance=student, user=user))
        assert Notification.objects.count() == count_before + 1


@pytest.mark.django_db
class TestTransport:
    def test_email_channel_success(self, user):
        from unittest.mock import patch

        from django.test import override_settings

        from notifications.channels.email import EmailChannel

        channel = EmailChannel()
        with (
            override_settings(RESEND_API_KEY="re_test"),
            patch(
                "core.tenant_email.get_tenant_resend_config",
                return_value={
                    "verified": True,
                    "from_email": "agenda@mail.example.com",
                    "domain": "mail.example.com",
                    "school_name": "Escola",
                },
            ),
            patch("resend.Emails.send", return_value={"id": "email-provider-id"}),
        ):
            result = channel.send(
                recipient_address="test@example.com",
                subject="Teste",
                body="Corpo de teste",
                tenant_schema="demo",
                message_log_id="opaque-id",
                idempotency_key="message-log/opaque-id",
            )
        assert result.success is True
        assert result.channel == "EMAIL"
        assert result.provider_message_id == "email-provider-id"

    def test_whatsapp_channel_stub(self, user):
        from notifications.channels.whatsapp import WhatsAppChannel

        channel = WhatsAppChannel()
        result = channel.send(
            recipient_address="+5511999999999",
            subject="",
            body="Teste",
        )
        assert result.success is False
        assert "stub" in result.error_message

    def test_whatsapp_channel_no_phone(self, user):
        from notifications.channels.whatsapp import WhatsAppChannel

        channel = WhatsAppChannel()
        result = channel.send(recipient_address="", subject="", body="Teste")
        assert result.success is False

    def test_transport_send_individual(self, user):
        from unittest.mock import patch

        from django.test import override_settings

        from core.models import CustomUser
        from notifications.channels.email import EmailChannel
        from notifications.models import MessageTemplate
        from notifications.transport import MessageTransport

        recipient = CustomUser.objects.create_user(
            email="transport@test.com",
            password="Senha123",
            first_name="T",
            last_name="User",
        )
        template = MessageTemplate.objects.create(
            name="Welcome",
            channel=MessageTemplate.Channel.EMAIL,
            body="Ola {{nome}}!",
            created_by=user,
            updated_by=user,
        )
        transport = MessageTransport(EmailChannel())
        with (
            override_settings(RESEND_API_KEY="re_test"),
            patch(
                "core.tenant_email.get_tenant_resend_config",
                return_value={
                    "verified": True,
                    "from_email": "agenda@mail.example.com",
                    "domain": "mail.example.com",
                    "school_name": "Escola",
                },
            ),
            patch("resend.Emails.send", return_value={"id": "transport-provider-id"}),
        ):
            result = transport.send_individual(recipient, template, {"nome": "Joao"})
        assert result == 1

    def test_transport_logs_do_not_expose_recipient_address(self, user, caplog):
        from core.models import CustomUser
        from notifications.channels.email import EmailChannel
        from notifications.models import MessageTemplate
        from notifications.transport import MessageTransport

        address = "private-recipient@example.com"
        recipient = CustomUser.objects.create_user(
            email=address,
            password="Senha123",
            first_name="Private",
            last_name="Recipient",
        )
        template = MessageTemplate.objects.create(
            name="Private",
            channel=MessageTemplate.Channel.EMAIL,
            body="Mensagem",
            created_by=user,
            updated_by=user,
        )

        with caplog.at_level(logging.DEBUG):
            MessageTransport(EmailChannel()).send_individual(recipient, template)

        assert address not in caplog.text
