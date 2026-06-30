"""Testes dos formularios do modulo accounts."""

from accounts.forms import ChangePasswordForm, LoginForm


class TestLoginForm:
    def test_valid(self):
        form = LoginForm(data={"email": "user@test.com", "password": "Senha123"})
        assert form.is_valid()

    def test_blank_fields(self):
        form = LoginForm(data={"email": "", "password": ""})
        assert not form.is_valid()
        assert "email" in form.errors


class TestChangePasswordForm:
    def test_valid(self):
        form = ChangePasswordForm(
            data={
                "current_password": "oldpass",
                "new_password": "NewPass123",
                "confirm_password": "NewPass123",
            }
        )
        assert form.is_valid()

    def test_passwords_dont_match(self):
        form = ChangePasswordForm(
            data={
                "current_password": "oldpass",
                "new_password": "NewPass123",
                "confirm_password": "DifferentPass",
            }
        )
        assert not form.is_valid()
        assert "confirm_password" in form.errors

    def test_blank_fields(self):
        form = ChangePasswordForm(data={})
        assert not form.is_valid()
        assert "current_password" in form.errors
