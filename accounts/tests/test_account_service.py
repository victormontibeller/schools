"""Testes do AccountService (nova estrutura)."""

import pytest

from accounts.services import AccountService
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from core.models import CustomUser


@pytest.mark.django_db
class TestCreateUser:
    def test_success(self, user):
        data = {
            "email": "novo@test.com",
            "password": "Senha123",
            "first_name": "Novo",
            "last_name": "User",
        }
        new_user = AccountService(user=user).create_user(data)
        assert new_user.pk is not None
        assert new_user.email == "novo@test.com"

    def test_duplicate_email(self, user):
        data = {"email": user.email, "password": "Senha123"}
        with pytest.raises(ValidationError):
            AccountService(user=user).create_user(data)

    def test_weak_password(self, user):
        data = {"email": "fraco@test.com", "password": "curta"}
        with pytest.raises(ValidationError):
            AccountService(user=user).create_user(data)


@pytest.mark.django_db
class TestDeactivateUser:
    def test_success(self, user):
        target = CustomUser.objects.create_user(email="target@test.com", password="Senha123")
        AccountService(user=user).deactivate_user(target.pk)
        target.refresh_from_db()
        assert target.deleted_at is not None

    def test_already_deactivated(self, user):
        target = CustomUser.objects.create_user(email="target2@test.com", password="Senha123")
        AccountService(user=user).deactivate_user(target.pk)
        with pytest.raises(BusinessRuleViolationError):
            AccountService(user=user).deactivate_user(target.pk)

    def test_not_found(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            AccountService(user=user).deactivate_user(uuid.uuid4())


@pytest.mark.django_db
class TestRestoreUser:
    def test_success(self, user):
        target = CustomUser.objects.create_user(email="restore@test.com", password="Senha123")
        AccountService(user=user).deactivate_user(target.pk)
        AccountService(user=user).restore_user(target.pk)
        target.refresh_from_db()
        assert target.deleted_at is None

    def test_not_deleted(self, user):
        target = CustomUser.objects.create_user(email="nodelet@test.com", password="Senha123")
        with pytest.raises(BusinessRuleViolationError):
            AccountService(user=user).restore_user(target.pk)


@pytest.mark.django_db
class TestChangePassword:
    def test_success(self, user):
        AccountService(user=user).change_password(user.pk, "Senha123", "NovaSenha456")
        user.refresh_from_db()
        assert user.check_password("NovaSenha456")

    def test_weak_password(self, user):
        with pytest.raises(ValidationError):
            AccountService(user=user).change_password(user.pk, "Senha123", "fraca")

    def test_wrong_current_password(self, user):
        with pytest.raises(ValidationError):
            AccountService(user=user).change_password(user.pk, "SenhaErrada", "NovaSenha456")


@pytest.mark.django_db
class TestUpdateUser:
    def test_updates_and_normalizes_email(self, user):
        updated = AccountService(user=user).update_user(
            user.pk,
            {"email": "  NOVO@EXAMPLE.COM  "},
        )

        assert updated.email == "novo@example.com"

    def test_rejects_email_used_by_inactive_user(self, user):
        CustomUser.objects.create_user(
            email="existente@example.com",
            password="Senha123",
            is_active=False,
        )

        with pytest.raises(ValidationError) as exc_info:
            AccountService(user=user).update_user(user.pk, {"email": "EXISTENTE@example.com"})

        assert "email" in exc_info.value.errors
