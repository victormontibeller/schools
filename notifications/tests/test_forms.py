"""Testes dos formularios do modulo de notificacoes."""

import pytest

from notifications.forms import AnnouncementForm, MessageTemplateForm


@pytest.mark.django_db
class TestMessageTemplateForm:
    def test_valid(self):
        form = MessageTemplateForm(
            data={
                "name": "Boas-vindas",
                "channel": "EMAIL",
                "type": "WELCOME",
                "body": "Ola {{nome}}!",
            }
        )
        assert form.is_valid()

    def test_blank_name(self):
        form = MessageTemplateForm(data={"name": "", "channel": "EMAIL", "body": "X"})
        assert not form.is_valid()
        assert "name" in form.errors


@pytest.mark.django_db
class TestAnnouncementForm:
    def test_valid(self):
        form = AnnouncementForm(
            data={
                "title": "Aviso",
                "body": "Conteudo do aviso.",
                "audience": "ALL",
            }
        )
        assert form.is_valid()

    def test_blank_title(self):
        form = AnnouncementForm(data={"title": "", "body": "Corpo", "audience": "ALL"})
        assert not form.is_valid()
        assert "title" in form.errors
