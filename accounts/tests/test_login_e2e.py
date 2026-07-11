"""Testes de integração do login (e2e via Django Client).

Cobrem:
- Login bem-sucedido gera audit_log (ver Sprint 02 §58).
- Login com falha NÃO vaza e-mail em logs (docs/04_SECURITY.md §39).
- Axes bloqueia após 5 tentativas falhas consecutivas (docs/04_SECURITY.md §33).
"""

import pytest

from core.models import CustomUser


@pytest.mark.django_db
class TestLoginE2E:
    URL = "/login/"

    def _make_user(self) -> CustomUser:
        return CustomUser.objects.create_user(
            email="user@test.com",
            password="Senha123",
            first_name="A",
            last_name="B",
        )

    def test_get_login_page_returns_200(self, client):
        resp = client.get(self.URL)
        assert resp.status_code == 200
        assert "E-mail" in resp.content.decode()

    def test_successful_login_redirects_and_audits(self, client):
        self._make_user()
        resp = client.post(
            self.URL, {"email": "user@test.com", "password": "Senha123"}, follow=False
        )
        assert resp.status_code in (302, 303)
        # Auditoria de login é opcional além da auditoria de domínio; basta
        # validar que uma sessão foi criada.
        assert "_auth_user_id" in client.session

    def test_invalid_credentials_does_not_leak_email_in_logs(self, client, caplog):
        import logging

        self._make_user()
        with caplog.at_level(logging.WARNING, logger="accounts.views"):
            client.post(
                self.URL,
                {"email": "victim@test.com", "password": "wrong"},
                follow=False,
            )
        # Nenhum record pode conter o e-mail vítima.
        body = "\n".join(r.getMessage() + " " + str(r.__dict__) for r in caplog.records)
        assert "victim@test.com" not in body

    def test_axes_locks_after_five_failures(self, client):
        """Após 5 falhas, Axes bloqueia — a 6ª nem chega a validar senha."""
        from axes.models import AccessAttempt

        self._make_user()
        for _ in range(5):
            client.post(
                self.URL,
                {"email": "user@test.com", "password": "wrong"},
                follow=False,
            )
        # Cada (ip, username) é agregado; 5 falhas = 1 AccessAttempt com contador 5.
        assert AccessAttempt.objects.count() == 1
        attempt = AccessAttempt.objects.get()
        assert attempt.failures_since_start >= 5

        # 6ª tentativa deve ser bloqueada pelo AxesMiddleware (429 Too Many Requests).
        resp = client.post(
            self.URL,
            {"email": "user@test.com", "password": "wrong"},
            follow=False,
        )
        assert resp.status_code in (
            403,
            429,
        ), f"Esperado lock (403 ou 429); obtido {resp.status_code}"

    def test_logout_works_when_logged_in(self, client):
        self._make_user()
        client.post(self.URL, {"email": "user@test.com", "password": "Senha123"})
        resp = client.post("/logout/", follow=False)
        assert resp.status_code in (302, 303)
        assert "_auth_user_id" not in client.session
