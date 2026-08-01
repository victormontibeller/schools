"""Testes dos servicos de notificacao."""

import uuid
from unittest.mock import patch

import pytest

from audit.models import AuditLog
from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from core.models import CustomUser
from notifications.models import Announcement, MessageTemplate, Notification
from notifications.services import AnnouncementService, NotificationService


def _make_user(email="notif@test.com"):
    return CustomUser.objects.create_user(
        email=email, password="Senha123", first_name="Test", last_name="Notif"
    )


# ── NotificationService ──────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCreateNotification:
    def test_success(self, user):
        recipient = _make_user("recipient@test.com")
        notif = NotificationService(user=user).create_notification(
            {
                "recipient_id": recipient.pk,
                "title": "Bem-vindo",
                "message": "Seja bem-vindo a plataforma!",
                "type": Notification.Type.INFO,
                "source": "system",
            }
        )
        assert notif.pk is not None
        assert notif.title == "Bem-vindo"
        assert notif.message == "Seja bem-vindo a plataforma!"
        assert notif.read_at is None

    def test_missing_required(self, user):
        with pytest.raises(ValidationError):
            NotificationService(user=user).create_notification({})

    def test_recipient_not_found(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            NotificationService(user=user).create_notification(
                {"recipient_id": uuid.uuid4(), "title": "X", "message": "Y"}
            )


@pytest.mark.django_db
class TestMarkAsRead:
    def test_success(self, user):
        recipient = _make_user("markread@test.com")
        notif = NotificationService(user=user).create_notification(
            {"recipient_id": recipient.pk, "title": "Teste", "message": "Corpo"}
        )
        initial_version = notif.version
        initial_updated_at = notif.updated_at
        service = NotificationService(user=recipient)
        with patch.object(service, "_log") as log:
            result = service.mark_as_read(notif.pk)

        assert result.read_at is not None
        assert result.updated_by == recipient
        assert result.version == initial_version + 1
        assert result.updated_at > initial_updated_at
        log.assert_called_once_with("notification_marked_as_read", notification_id=str(notif.pk))
        audit = AuditLog.objects.filter(
            model_name="Notification", object_id=str(notif.pk), operation="UPDATE"
        ).get()
        assert audit.old_values["version"] == initial_version
        assert audit.old_values["read_at"] is None

    def test_already_read_is_idempotent(self, user):
        recipient = _make_user("already@test.com")
        notif = NotificationService(user=user).create_notification(
            {"recipient_id": recipient.pk, "title": "Teste", "message": "Corpo"}
        )
        service = NotificationService(user=recipient)
        with patch.object(service, "_log") as log:
            first = service.mark_as_read(notif.pk)
            audit_count = AuditLog.objects.count()
            second = service.mark_as_read(notif.pk)

        assert second.read_at == first.read_at
        assert second.version == first.version
        assert AuditLog.objects.count() == audit_count
        log.assert_called_once()

    def test_not_found(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            NotificationService(user=user).mark_as_read(uuid.uuid4())


@pytest.mark.django_db
class TestMarkAllAsRead:
    def test_success(self, user):
        recipient = _make_user("markall@test.com")
        first = NotificationService(user=user).create_notification(
            {"recipient_id": recipient.pk, "title": "N1", "message": "M1"}
        )
        second = NotificationService(user=user).create_notification(
            {"recipient_id": recipient.pk, "title": "N2", "message": "M2"}
        )
        service = NotificationService(user=recipient)
        initial_updated_at = {item.pk: item.updated_at for item in (first, second)}
        with patch.object(service, "_log") as log:
            count = service.mark_all_as_read()

        assert count == 2
        unread = NotificationService(user=user).get_unread_count(recipient.pk)
        assert unread == 0
        for notification in (first, second):
            notification.refresh_from_db()
            assert notification.updated_by == recipient
            assert notification.version == 1
            assert notification.updated_at > initial_updated_at[notification.pk]
        assert AuditLog.objects.filter(model_name="Notification", operation="UPDATE").count() == 2
        log.assert_called_once_with("notifications_marked_as_read", count=2)

    def test_no_unread(self, user):
        recipient = _make_user("noread@test.com")
        count = NotificationService(user=recipient).mark_all_as_read()
        assert count == 0

    def test_only_actor_notifications_are_marked(self, user):
        other = _make_user("markall-other@test.com")
        own = NotificationService(user=user).create_notification(
            {"recipient_id": user.pk, "title": "Própria", "message": "M1"}
        )
        foreign = NotificationService(user=user).create_notification(
            {"recipient_id": other.pk, "title": "Alheia", "message": "M2"}
        )

        assert NotificationService(user=user).mark_all_as_read() == 1

        own.refresh_from_db()
        foreign.refresh_from_db()
        assert own.read_at is not None
        assert foreign.read_at is None


@pytest.mark.django_db
class TestMarkActorScope:
    def test_mark_as_read_rejects_foreign_notification(self, user):
        other = _make_user("foreign-mark@test.com")
        notification = NotificationService(user=user).create_notification(
            {"recipient_id": other.pk, "title": "Alheia", "message": "Corpo"}
        )

        with pytest.raises(ObjectNotFoundError):
            NotificationService(user=user).mark_as_read(notification.pk)

        notification.refresh_from_db()
        assert notification.read_at is None

    def test_mark_single_requires_actor(self):
        with pytest.raises(PermissionDeniedError):
            NotificationService(user=None).mark_as_read(uuid.uuid4())

    def test_mark_all_requires_actor(self):
        with pytest.raises(PermissionDeniedError):
            NotificationService(user=None).mark_all_as_read()


# ── AnnouncementService ──────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCreateAnnouncement:
    def test_success(self, user):
        author = _make_user("author@test.com")
        announcement = AnnouncementService(user=user).create_announcement(
            {
                "title": "Reuniao de Pais",
                "body": "Reuniao sera dia 15/03.",
                "author_id": author.pk,
            }
        )
        assert announcement.pk is not None
        assert announcement.title == "Reuniao de Pais"
        assert announcement.sent_at is None

    def test_whatsapp_is_preserved_but_not_enabled(self, user):
        author = _make_user("whatsapp-author@test.com")
        announcement = AnnouncementService(user=user).create_announcement(
            {
                "title": "Aviso",
                "body": "Corpo",
                "author_id": author.pk,
                "send_whatsapp": True,
            }
        )
        assert announcement.send_whatsapp is False

    def test_missing_required(self, user):
        with pytest.raises(ValidationError):
            AnnouncementService(user=user).create_announcement({})

    def test_author_not_found(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            AnnouncementService(user=user).create_announcement(
                {"title": "X", "body": "Y", "author_id": uuid.uuid4()}
            )

    def test_class_audience_without_class(self, user):
        author = _make_user("author2@test.com")
        with pytest.raises(ValidationError):
            AnnouncementService(user=user).create_announcement(
                {
                    "title": "Aviso Turma",
                    "body": "Conteudo",
                    "author_id": author.pk,
                    "audience": Announcement.Audience.CLASS,
                }
            )

    def test_class_audience_with_class(self, user):
        from classes.models import Class

        cls = Class.objects.create(
            name="1A-ANN",
            grade=Class.Grade.ELEMENTARY_1,
            education_stage=Class.EducationStage.ELEMENTARY_I,
            academic_year=2025,
            shift=Class.Shift.MORNING,
            created_by=user,
            updated_by=user,
        )
        author = _make_user("author3@test.com")
        announcement = AnnouncementService(user=user).create_announcement(
            {
                "title": "Aviso Turma 1A",
                "body": "Conteudo",
                "author_id": author.pk,
                "audience": Announcement.Audience.CLASS,
                "class_obj_id": cls.pk,
            }
        )
        assert announcement.class_obj == cls

    def test_class_audience_class_not_found(self, user):
        import uuid

        author = _make_user("author-cnf@test.com")
        with pytest.raises(ObjectNotFoundError):
            AnnouncementService(user=user).create_announcement(
                {
                    "title": "Aviso",
                    "body": "Conteudo",
                    "author_id": author.pk,
                    "audience": Announcement.Audience.CLASS,
                    "class_obj_id": uuid.uuid4(),
                }
            )


@pytest.mark.django_db
class TestSendAnnouncement:
    def test_success(self, user):
        author = _make_user("send-auth@test.com")
        announcement = AnnouncementService(user=user).create_announcement(
            {"title": "Aviso", "body": "Corpo", "author_id": author.pk}
        )
        result = AnnouncementService(user=user).send_announcement(announcement.pk)
        assert result.sent_at is not None

    def test_already_sent(self, user):
        author = _make_user("sent-auth@test.com")
        announcement = AnnouncementService(user=user).create_announcement(
            {"title": "Aviso", "body": "Corpo", "author_id": author.pk}
        )
        AnnouncementService(user=user).send_announcement(announcement.pk)
        with pytest.raises(BusinessRuleViolationError):
            AnnouncementService(user=user).send_announcement(announcement.pk)

    def test_not_found(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            AnnouncementService(user=user).send_announcement(uuid.uuid4())


@pytest.mark.django_db
class TestGetAudienceUsers:
    def test_all(self, user):
        users = AnnouncementService(user=user).get_audience_users("ALL")
        assert users.filter(pk=user.pk).exists()

    def test_class_audience(self, user):
        from classes.models import Class, Enrollment
        from students.models import Student

        cls = Class.objects.create(
            name="1A-AUD",
            grade=Class.Grade.ELEMENTARY_1,
            education_stage=Class.EducationStage.ELEMENTARY_I,
            academic_year=2025,
            shift=Class.Shift.MORNING,
            created_by=user,
            updated_by=user,
        )
        student_user = _make_user("student-aud@test.com")
        student = Student.objects.create(
            user=student_user,
            first_name="Aluno",
            last_name="Audience",
            birth_date="2010-01-01",
            enrollment_number="AUD001",
            created_by=user,
            updated_by=user,
        )
        Enrollment.objects.create(
            student=student,
            class_obj=cls,
            enrollment_date="2025-01-01",
            status=Enrollment.Status.ACTIVE,
            created_by=user,
            updated_by=user,
        )
        audience = AnnouncementService(user=user).get_audience_users("CLASS", cls.pk)
        assert audience.filter(pk=student_user.pk).exists()


@pytest.mark.django_db
class TestCreateTemplate:
    def test_success(self, user):
        template = AnnouncementService(user=user).create_template(
            {
                "name": "Boas-vindas",
                "channel": MessageTemplate.Channel.EMAIL,
                "body": "Ola {{nome}}, bem-vindo!",
                "subject": "Bem-vindo ao Schools",
            }
        )
        assert template.pk is not None
        assert template.name == "Boas-vindas"

    def test_duplicate(self, user):
        data = {
            "name": "Duplicado",
            "channel": MessageTemplate.Channel.EMAIL,
            "body": "Template duplicado",
        }
        AnnouncementService(user=user).create_template(data)
        with pytest.raises(ValidationError):
            AnnouncementService(user=user).create_template(data)

    def test_missing_required(self, user):
        with pytest.raises(ValidationError):
            AnnouncementService(user=user).create_template({"name": "Sem corpo"})
