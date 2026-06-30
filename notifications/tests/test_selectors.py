"""Testes dos selectors do modulo de notificacoes."""

import pytest

from core.models import CustomUser
from notifications.models import Announcement, Notification
from notifications.selectors import AnnouncementSelector, NotificationSelector, TemplateSelector


def _make_notification(recipient, user, **kwargs):
    return Notification.objects.create(
        recipient=recipient,
        type=kwargs.get("type", Notification.Type.INFO),
        title=kwargs.get("title", "Teste"),
        message=kwargs.get("message", "Corpo"),
        created_by=user,
        updated_by=user,
    )


def _make_announcement(user, audience=Announcement.Audience.ALL, sent=False):
    author = CustomUser.objects.create_user(
        email=f"author-{audience}@test.com",
        password="Senha123",
        first_name="Author",
        last_name="Test",
    )
    from django.utils import timezone

    return Announcement.objects.create(
        title="Aviso",
        body="Corpo",
        audience=audience,
        author=author,
        sent_at=timezone.now() if sent else None,
        created_by=user,
        updated_by=user,
    )


@pytest.mark.django_db
class TestNotificationSelector:
    def test_get_unread(self, user):
        recipient = CustomUser.objects.create_user(
            email="sel@test.com", password="Senha123", first_name="S", last_name="T"
        )
        _make_notification(recipient, user)
        n2 = _make_notification(recipient, user, title="Lida")
        from django.utils import timezone

        n2.read_at = timezone.now()
        n2.save()
        unread = NotificationSelector().get_unread_for_user(recipient.pk)
        assert unread.count() == 1

    def test_get_all(self, user):
        recipient = CustomUser.objects.create_user(
            email="sel2@test.com", password="Senha123", first_name="S", last_name="T"
        )
        _make_notification(recipient, user)
        all_n = NotificationSelector().get_all_for_user(recipient.pk)
        assert all_n.count() == 1

    def test_get_by_type(self, user):
        recipient = CustomUser.objects.create_user(
            email="sel3@test.com", password="Senha123", first_name="S", last_name="T"
        )
        Notification.objects.create(
            recipient=recipient,
            type=Notification.Type.ALERT,
            title="Alerta",
            message="Corpo",
            created_by=user,
            updated_by=user,
        )
        _make_notification(recipient, user)
        alerts = NotificationSelector().get_by_type(recipient.pk, Notification.Type.ALERT)
        assert alerts.count() == 1

    def test_get_by_source(self, user):
        recipient = CustomUser.objects.create_user(
            email="sel4@test.com", password="Senha123", first_name="S", last_name="T"
        )
        Notification.objects.create(
            recipient=recipient,
            type=Notification.Type.INFO,
            title="T",
            message="M",
            source="attendance",
            created_by=user,
            updated_by=user,
        )
        result = NotificationSelector().get_by_source(recipient.pk, "attendance")
        assert result.count() == 1


@pytest.mark.django_db
class TestAnnouncementSelector:
    def test_get_sent(self, user):
        _make_announcement(user, Announcement.Audience.ALL, sent=True)
        _make_announcement(user, Announcement.Audience.TEACHERS, sent=False)
        sent = AnnouncementSelector().get_sent()
        assert sent.count() == 1

    def test_get_scheduled(self, user):
        from django.utils import timezone

        author = CustomUser.objects.create_user(
            email="sched-auth@test.com", password="Senha123", first_name="A", last_name="T"
        )
        Announcement.objects.create(
            title="Agendado",
            body="Corpo",
            audience=Announcement.Audience.ALL,
            author=author,
            scheduled_at=timezone.now() + timezone.timedelta(days=1),
            created_by=user,
            updated_by=user,
        )
        scheduled = AnnouncementSelector().get_scheduled()
        assert scheduled.count() == 1

    def test_get_by_audience(self, user):
        _make_announcement(user, Announcement.Audience.ALL)
        _make_announcement(user, Announcement.Audience.TEACHERS)
        all_ann = AnnouncementSelector().get_by_audience(Announcement.Audience.ALL)
        assert all_ann.count() == 1

    def test_get_for_class(self, user):
        from classes.models import Class

        cls = Class.objects.create(
            name="1A-SEL",
            grade="1o Ano",
            academic_year=2025,
            shift=Class.Shift.MORNING,
            created_by=user,
            updated_by=user,
        )
        author = CustomUser.objects.create_user(
            email="auth-sel@test.com", password="Senha123", first_name="A", last_name="T"
        )
        Announcement.objects.create(
            title="Aviso Turma",
            body="Corpo",
            audience=Announcement.Audience.CLASS,
            author=author,
            class_obj=cls,
            created_by=user,
            updated_by=user,
        )
        for_class = AnnouncementSelector().get_for_class(cls.pk)
        assert for_class.count() == 1


@pytest.mark.django_db
class TestTemplateSelector:
    def test_get_by_channel(self, user):
        from notifications.models import MessageTemplate

        MessageTemplate.objects.create(
            name="Email 1",
            channel=MessageTemplate.Channel.EMAIL,
            body="X",
            created_by=user,
            updated_by=user,
        )
        MessageTemplate.objects.create(
            name="WhatsApp 1",
            channel=MessageTemplate.Channel.WHATSAPP,
            body="Y",
            created_by=user,
            updated_by=user,
        )
        email_templates = TemplateSelector().get_by_channel(MessageTemplate.Channel.EMAIL)
        assert email_templates.count() == 1

    def test_get_by_type(self, user):
        from notifications.models import MessageTemplate

        MessageTemplate.objects.create(
            name="Welcome",
            channel=MessageTemplate.Channel.EMAIL,
            type=MessageTemplate.Type.WELCOME,
            body="Ola!",
            created_by=user,
            updated_by=user,
        )
        result = TemplateSelector().get_by_type(MessageTemplate.Type.WELCOME)
        assert result.count() == 1
