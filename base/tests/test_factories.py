"""Smoke tests das factories e do helper `with_tenant`.

Cobrem pendências listadas em `docs/15_SPRINT_01.md` §88 (factories) e
`docs/15_SPRINT_01.md` §89 (helper `with_tenant`).
"""

import pytest

from base.tests.factories import CustomUserFactory, RoomFactory, StudentFactory, SubjectFactory


@pytest.mark.django_db
class TestFactories:
    def test_custom_user_factory_creates_unique_email(self):
        u1 = CustomUserFactory()
        u2 = CustomUserFactory()
        assert u1.email != u2.email
        assert u1.check_password("Senha123")
        assert u1.is_active

    def test_subject_factory_code_is_unique(self):
        s1 = SubjectFactory()
        s2 = SubjectFactory()
        assert s1.code != s2.code

    def test_room_factory_defaults(self):
        r = RoomFactory()
        assert r.capacity == 30
        assert r.type == "CLASSROOM"
        assert r.code.startswith("R-")

    def test_student_factory_creates_enrollment(self):
        st = StudentFactory()
        assert st.enrollment_number.startswith("STU-")
        assert st.gender == "NI"


@pytest.mark.django_db
class TestWithTenant:
    def test_with_tenant_noop_in_sqlite_tests(self, db):
        """Em testes SQLite (sem django_tenants), o helper é no-op seguro."""
        from conftest import with_tenant

        # Sem schema configurado — deve apenas executar o bloco sem erro.
        with with_tenant("public"):
            from core.models import CustomUser

            assert CustomUser.objects.exists() is False
