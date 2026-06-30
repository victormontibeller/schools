"""Testes das views do modulo de notificacoes."""

import pytest
from django.urls import reverse

from notifications.models import Notification


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

    def test_mark_read(self, client, user):
        notif = Notification.objects.create(
            recipient=user,
            type=Notification.Type.INFO,
            title="Para ler",
            message="Corpo",
            created_by=user,
            updated_by=user,
        )
        client.force_login(user)
        response = client.get(reverse("notification_mark_read", args=[notif.pk]))
        assert response.status_code == 302
        notif.refresh_from_db()
        assert notif.read_at is not None

    def test_mark_all_read(self, client, user):
        Notification.objects.create(
            recipient=user,
            type=Notification.Type.INFO,
            title="N1",
            message="M1",
            created_by=user,
            updated_by=user,
        )
        client.force_login(user)
        response = client.post(reverse("notification_mark_all_read"))
        assert response.status_code == 302
        assert Notification.objects.filter(recipient=user, read_at__isnull=True).count() == 0

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


@pytest.mark.django_db
class TestAnnouncementViews:
    def test_list_empty(self, client, user):
        client.force_login(user)
        response = client.get(reverse("announcement_list"))
        assert response.status_code == 200
        assert "Nenhum comunicado" in response.content.decode()
