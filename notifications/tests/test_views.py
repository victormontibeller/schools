"""Testes das views do modulo de notificacoes."""

import pytest
from django.urls import reverse

from core.models import CustomUser
from notifications.models import Notification


def _notification(recipient, author, title="Aviso"):
    return Notification.objects.create(
        recipient=recipient,
        type=Notification.Type.INFO,
        title=title,
        message="Corpo",
        created_by=author,
        updated_by=author,
    )


@pytest.mark.django_db
class TestNotificationViews:
    def test_list_empty(self, client, user):
        client.force_login(user)
        response = client.get(reverse("notification_list"))
        assert response.status_code == 200
        assert "Nenhuma notificacao" in response.content.decode()

    def test_list_with_items(self, client, user):
        Notification.objects.create(
            recipient=user,
            type=Notification.Type.INFO,
            title="Teste",
            message="Mensagem de teste",
            created_by=user,
            updated_by=user,
        )
        client.force_login(user)
        response = client.get(reverse("notification_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Teste" in content

    def test_mark_read_get_is_method_not_allowed_without_mutation(self, client, user):
        notif = _notification(user, user, "Permanece não lida")
        client.force_login(user)

        response = client.get(reverse("notification_mark_read", args=[notif.pk]))

        assert response.status_code == 405
        notif.refresh_from_db()
        assert notif.read_at is None

    def test_mark_all_read_get_is_method_not_allowed_without_mutation(self, client, user):
        notification = _notification(user, user)
        client.force_login(user)

        response = client.get(reverse("notification_mark_all_read"))

        assert response.status_code == 405
        notification.refresh_from_db()
        assert notification.read_at is None

    @pytest.mark.parametrize("htmx", [False, True])
    def test_mark_read_post_only_mutates_notification_owned_by_actor(self, client, user, htmx):
        other = CustomUser.objects.create_user(
            email=f"other-{htmx}@notifications.test", password="Senha123"
        )
        own = _notification(user, user, "Própria")
        foreign = _notification(other, user, "Alheia")
        client.force_login(user)
        headers = {"HTTP_HX_REQUEST": "true"} if htmx else {}

        response = client.post(reverse("notification_mark_read", args=[own.pk]), **headers)
        denied = client.post(reverse("notification_mark_read", args=[foreign.pk]), **headers)

        own.refresh_from_db()
        foreign.refresh_from_db()
        assert response.status_code in {200, 302}
        assert denied.status_code in {200, 302}
        assert own.read_at is not None
        assert foreign.read_at is None

    @pytest.mark.parametrize("htmx", [False, True])
    def test_mark_all_read_post_only_mutates_actor_notifications(self, client, user, htmx):
        other = CustomUser.objects.create_user(
            email=f"other-all-{htmx}@notifications.test", password="Senha123"
        )
        own = _notification(user, user, "Própria")
        foreign = _notification(other, user, "Alheia")
        client.force_login(user)
        headers = {"HTTP_HX_REQUEST": "true"} if htmx else {}

        response = client.post(reverse("notification_mark_all_read"), **headers)

        own.refresh_from_db()
        foreign.refresh_from_db()
        assert response.status_code in {200, 302}
        assert own.read_at is not None
        assert foreign.read_at is None

    def test_unread_count(self, client, user):
        Notification.objects.create(
            recipient=user,
            type=Notification.Type.INFO,
            title="N1",
            message="M1",
            created_by=user,
            updated_by=user,
        )
        client.force_login(user)
        response = client.get(reverse("unread_count"))
        assert response.status_code == 200
        assert response.content.decode() == "1"

    def test_unread_count_is_empty_when_zero(self, client, user):
        client.force_login(user)
        response = client.get(reverse("unread_count"))
        assert response.status_code == 200
        assert response.content == b""

    def test_list_returns_header_partial_for_htmx(self, client, user):
        Notification.objects.create(
            recipient=user,
            type=Notification.Type.INFO,
            title="Cabeçalho",
            message="Mensagem do popup",
            created_by=user,
            updated_by=user,
        )
        client.force_login(user)

        response = client.get(
            reverse("notification_list"),
            {"context": "header"},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Notificações" in content
        assert "Mensagem do popup" in content


@pytest.mark.django_db
class TestAnnouncementViews:
    def test_list_empty(self, client, user):
        client.force_login(user)
        response = client.get(reverse("announcement_list"))
        assert response.status_code == 200
        assert "Nenhum comunicado" in response.content.decode()
