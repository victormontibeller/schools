"""Testes do `BaseModel` (UUID, soft delete, is_active, deleted_by, restore).

Usa `Student` (herda `BaseModel`) como modelo concreto representativo para
evitar acoplar a suites específicas de domínio.
"""

import pytest

from students.models import Student


@pytest.mark.django_db
class TestBaseModelSoftDelete:
    def _make(self, user) -> Student:
        return Student.objects.create(
            first_name="Ana",
            last_name="Lima",
            birth_date="2010-01-01",
            enrollment_number="BASE-001",
            created_by=user,
            updated_by=user,
        )

    def test_soft_delete_sets_is_active_false_deleted_at_and_deleted_by(self, user):
        s = self._make(user)
        assert s.is_active is True
        assert s.deleted_at is None
        assert s.deleted_by is None

        s.soft_delete(user=user)
        s.refresh_from_db()

        assert s.is_active is False
        assert s.deleted_at is not None
        assert s.deleted_by == user
        assert s.is_deleted is True
        assert s.version == 1

    def test_restore_clears_deletion_and_reactivates(self, user):
        s = self._make(user)
        s.soft_delete(user=user)

        s.restore(user=user)
        s.refresh_from_db()

        assert s.is_active is True
        assert s.deleted_at is None
        assert s.deleted_by is None  # restaurar limpa o "deleter"
        assert s.version == 2

    def test_stale_save_is_rejected_without_overwriting(self, user):
        from base.exceptions import BusinessRuleViolationError

        first = self._make(user)
        stale = Student.all_objects.get(pk=first.pk)
        first.first_name = "Atualizado"
        first.save(update_fields=["first_name"])

        stale.last_name = "Sobrescrito"
        with pytest.raises(BusinessRuleViolationError):
            stale.save(update_fields=["last_name"])

        persisted = Student.all_objects.get(pk=first.pk)
        assert persisted.first_name == "Atualizado"
        assert persisted.last_name == "Lima"

    def test_stale_soft_delete_is_rejected(self, user):
        from base.exceptions import BusinessRuleViolationError

        current = self._make(user)
        stale = Student.all_objects.get(pk=current.pk)
        current.last_name = "Atualizado"
        current.save(update_fields=["last_name"])

        with pytest.raises(BusinessRuleViolationError):
            stale.soft_delete(user=user)

    def test_two_repository_updates_with_same_version_yield_one_conflict(self, user):
        from base.exceptions import BusinessRuleViolationError
        from base.repositories import BaseRepository

        class StudentRepository(BaseRepository):
            model_class = Student

        first = self._make(user)
        second = Student.all_objects.get(pk=first.pk)
        repository = StudentRepository()

        repository.update(first, expected_version=0, first_name="Primeiro")
        with pytest.raises(BusinessRuleViolationError):
            repository.update(second, expected_version=0, first_name="Segundo")

        persisted = Student.all_objects.get(pk=first.pk)
        assert persisted.first_name == "Primeiro"
        assert persisted.version == 1

    def test_active_manager_hides_deleted(self, user):
        s = self._make(user)
        s.soft_delete(user=user)
        # ActiveManager (objects) exclui:
        assert not Student.objects.filter(pk=s.pk).exists()
        # all_objects ainda enxerga:
        assert Student.all_objects.filter(pk=s.pk).exists()

    def test_active_manager_excludes_inactive_even_without_deleted_at(self, user):
        """`is_active=False` é suficiente para filtrar pelo ActiveManager."""
        s = self._make(user)
        Student.all_objects.filter(pk=s.pk).update(is_active=False)
        assert not Student.objects.filter(pk=s.pk).exists()
        assert Student.all_objects.filter(pk=s.pk).exists()


@pytest.mark.django_db
class TestBaseServiceAuditViaEvent:
    """Regressão:Service dispara DomainEvent → handler audit → AuditLog."""

    def test_create_user_persists_audit_log(self, user):
        from accounts.services import AccountService
        from audit.models import AuditLog

        before = AuditLog.objects.count()
        AccountService(user=user).create_user(
            {
                "email": "audit-via-event@test.com",
                "password": "Violeta824",
                "first_name": "A",
                "last_name": "B",
            }
        )
        after = AuditLog.objects.count()
        assert after == before + 1
        log = AuditLog.objects.latest("created_at")
        assert log.operation == AuditLog.Operation.INSERT
        assert log.model_name == "CustomUser"
        assert log.user == user
