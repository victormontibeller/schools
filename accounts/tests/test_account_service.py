"""Testes do AccountService (nova estrutura)."""

import uuid

import pytest

from accounts.services import AccountService
from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from core.models import CustomUser


@pytest.mark.django_db
class TestCreateUser:
    def test_success(self, user):
        data = {
            "email": "novo@test.com",
            "password": "Violeta824",
            "first_name": "Novo",
            "last_name": "User",
        }
        new_user = AccountService(user=user).create_user(data)
        assert new_user.pk is not None
        assert new_user.email == "novo@test.com"

    def test_duplicate_email(self, user):
        data = {"email": user.email, "password": "Violeta824"}
        with pytest.raises(ValidationError):
            AccountService(user=user).create_user(data)

    def test_weak_password(self, user):
        data = {"email": "fraco@test.com", "password": "curta"}
        with pytest.raises(ValidationError):
            AccountService(user=user).create_user(data)

    @pytest.mark.parametrize("password", ["password", "12345678"])
    def test_rejects_common_or_numeric_password(self, user, password):
        data = {"email": "politica@test.com", "password": password}
        with pytest.raises(ValidationError):
            AccountService(user=user).create_user(data)

    def test_accepts_eight_letters_without_composition_requirement(self, user):
        created = AccountService(user=user).create_user(
            {"email": "oito@test.com", "password": "xqzvbnml"}
        )
        assert created.check_password("xqzvbnml")

    def test_rejects_password_similar_to_user(self, user):
        data = {
            "email": "marcelino@example.com",
            "first_name": "Marcelino",
            "password": "marcelino",
        }
        with pytest.raises(ValidationError):
            AccountService(user=user).create_user(data)

    def test_rejects_unknown_role(self, user):
        with pytest.raises(ObjectNotFoundError):
            AccountService(user=user).create_user(
                {
                    "email": "unknown-role@test.com",
                    "password": "Violeta824",
                    "role_id": uuid.uuid4(),
                }
            )


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

    def test_missing_user(self, user):
        with pytest.raises(ObjectNotFoundError):
            AccountService(user=user).change_password(uuid.uuid4(), "old", "Violeta824")


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

    def test_rejects_unknown_role_and_accepts_role_clear(self, user):
        with pytest.raises(ObjectNotFoundError):
            AccountService(user=user).update_user(user.pk, {"role_id": uuid.uuid4()})

        updated = AccountService(user=user).update_user(user.pk, {"role_id": None})
        assert updated.role is None


@pytest.mark.django_db
class TestAccountServiceEdges:
    def test_platform_management_rejects_common_operator_and_missing_user(self, user):
        common = CustomUser.objects.create_user(
            email="common-platform@test.com", password="Senha123", is_superuser=False
        )
        with pytest.raises(PermissionDeniedError):
            AccountService(user=common).create_platform_user(
                {
                    "first_name": "Sem",
                    "last_name": "Permissão",
                    "email": "denied@test.com",
                    "password": "Violeta824",
                }
            )
        with pytest.raises(ObjectNotFoundError):
            AccountService(user=user).update_platform_user(uuid.uuid4(), {})

    def test_platform_user_rejects_duplicate_email(self, user):
        with pytest.raises(ValidationError):
            AccountService(user=user).create_platform_user(
                {
                    "first_name": "Duplicado",
                    "last_name": "Operador",
                    "email": user.email,
                    "password": "Violeta824",
                }
            )

    def test_restore_missing_user(self, user):
        with pytest.raises(ObjectNotFoundError):
            AccountService(user=user).restore_user(uuid.uuid4())
