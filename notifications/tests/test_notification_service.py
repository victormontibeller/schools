"""Testes dos servicos de notificacao."""

import pytest

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
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
        result = NotificationService(user=user).mark_as_read(notif.pk)
        assert result.read_at is not None

    def test_already_read(self, user):
        recipient = _make_user("already@test.com")
        notif = NotificationService(user=user).create_notification(
            {"recipient_id": recipient.pk, "title": "Teste", "message": "Corpo"}
        )
        NotificationService(user=user).mark_as_read(notif.pk)
        with pytest.raises(BusinessRuleViolationError):
            NotificationService(user=user).mark_as_read(notif.pk)

    def test_not_found(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            NotificationService(user=user).mark_as_read(uuid.uuid4())


@pytest.mark.django_db
class TestMarkAllAsRead:
    def test_success(self, user):
        recipient = _make_user("markall@test.com")
        NotificationService(user=user).create_notification(
            {"recipient_id": recipient.pk, "title": "N1", "message": "M1"}
        )
        NotificationService(user=user).create_notification(
            {"recipient_id": recipient.pk, "title": "N2", "message": "M2"}
        )
        count = NotificationService(user=user).mark_all_as_read(recipient.pk)
        assert count == 2
        unread = NotificationService(user=user).get_unread_count(recipient.pk)
        assert unread == 0

    def test_no_unread(self, user):
        recipient = _make_user("noread@test.com")
        count = NotificationService(user=user).mark_all_as_read(recipient.pk)
        assert count == 0


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
