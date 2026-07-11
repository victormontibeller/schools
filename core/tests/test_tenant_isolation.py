"""Testes de isolamento por Schema PostgreSQL (multi-tenant).

Estes testes **não** rodam no perfil SQLite (TESTING); requerem PostgreSQL +
django-tenants — execute com `DJANGO_ENV=test_pg pytest -m tenant`.

Usam `django_tenants.test.cases.TenantTestCase`: cria um schema de teste por
classe, бескрeturn connection to schema público ao final. entre cada método, o
TestCase faz flush apenas das tabelas do schema de teste.

Ver ADR-0001.
"""

import os

import pytest
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from base import context
from core.models import CustomUser
from tenancy.models import Domain, School

pytestmark = [pytest.mark.tenant]

_requires_pg = pytest.mark.skipif(
    os.environ.get("DJANGO_ENV") != "test_pg",
    reason="Requer perfil DJANGO_ENV=test_pg (PostgreSQL + django_tenants)",
)


@_requires_pg
class TestTenantSchemaIsolation(TenantTestCase):
    """Prova que dados inseridos num schema NÃO vazam para outro."""

    # TenantTestCase cria um schema "test" automaticamente; usamos o dele +
    # criamos um segundo para provar isolamento cruzado.

    @classmethod
    def get_test_schema_name(cls) -> str:
        return "escola_a"

    @classmethod
    def get_test_tenant_domain(cls) -> str:
        return "escola_a.test.local"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()  # cria cls.tenant (schema escola_a) e ativa o schema dele
        # Para criar o segundo tenant é obrigatório estar no schema public.
        connection.set_schema_to_public()
        second = School(schema_name="escola_b", name="Escola B")
        cls.setup_tenant(second)
        second.save(verbosity=0)
        cls.tenant_b = second
        Domain.objects.create(domain="escola_b.test.local", tenant=second, is_primary=True)
        # Volta a apontar para o primeiro (default do TenantTestCase).
        connection.set_tenant(cls.tenant)

    @classmethod
    def tearDownClass(cls):
        connection.set_schema_to_public()
        cls.tenant_b.delete(force_drop=True)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        # Cada teste começa explicitamente no tenant A; o método anterior pode
        # ter terminado após validar o tenant B.
        connection.set_tenant(self.tenant)
        # Ajusta `current_tenant` (em produção é reponsabilidade do middleware)
        self._ctx_token = context.current_tenant.set(connection.schema_name)

    def tearDown(self):
        context.current_tenant.reset(self._ctx_token)
        super().tearDown()

    def _make_student(self, enrollment: str, first_name: str = "Ana"):
        from students.models import Student

        return Student.objects.create(
            first_name=first_name,
            last_name="Silva",
            birth_date="2010-01-01",
            enrollment_number=enrollment,
        )

    def test_each_tenant_sees_only_its_own_students(self):
        from students.models import Student

        # Schema A (atual via TenantTestCase)
        a1 = self._make_student("A-001", "Ana")
        assert Student.objects.count() == 1

        # Troca para Escola B e cria lá outro aluno
        connection.set_tenant(self.tenant_b)
        context.current_tenant.set("escola_b")
        self._make_student("B-001", "Bruno")
        assert Student.objects.count() == 1
        assert Student.objects.get().enrollment_number == "B-001"
        assert not Student.objects.filter(enrollment_number="A-001").exists()

        # Volta para Escola A
        connection.set_tenant(self.tenant)
        context.current_tenant.set("escola_a")
        assert Student.objects.count() == 1
        assert Student.objects.get().enrollment_number == "A-001"
        assert not Student.objects.filter(enrollment_number="B-001").exists()

        # PKs são distintos entre schemas
        a_after = Student.objects.get()
        connection.set_tenant(self.tenant_b)
        b_after = Student.objects.get()
        assert a_after.pk == a1.pk
        assert a_after.pk != b_after.pk

    def test_same_email_is_isolated_between_tenant_schemas(self):
        """Cada schema possui sua própria tabela de autenticação."""
        user_a = CustomUser.objects.create_user(
            email="admin@school.test",
            password="SenhaA123",
            first_name="Admin",
            last_name="A",
        )
        connection.set_tenant(self.tenant_b)
        user_b = CustomUser.objects.create_user(
            email="admin@school.test",
            password="SenhaB123",
            first_name="Admin",
            last_name="B",
        )
        assert user_b.pk != user_a.pk
        assert user_b.check_password("SenhaB123")
        assert not user_b.check_password("SenhaA123")

        connection.set_tenant(self.tenant)
        isolated_a = CustomUser.objects.get(email="admin@school.test")
        assert isolated_a.pk == user_a.pk
        assert isolated_a.check_password("SenhaA123")
        assert not isolated_a.check_password("SenhaB123")

    def test_audit_logs_record_tenant_schema(self):
        from audit.models import AuditLog
        from students.services import StudentService

        actor = CustomUser.objects.create_user(
            email="audit@escola_a.test",
            password="Senha123",
            first_name="A",
            last_name="B",
            is_superuser=True,
        )
        StudentService(user=actor).create_student(
            {
                "first_name": "X",
                "last_name": "Y",
                "birth_date": "2010-01-01",
                "enrollment_number": "AUD-001",
                "gender": "M",
                "blood_type": "O+",
                "nationality": "Brasileira",
                "cpf": "390.533.447-05",
                "rg_number": "1234567",
                "rg_issuer": "SSP",
                "rg_state": "SP",
                "phone_mobile": "11999990000",
                "email": "x@example.com",
            }
        )

        log = AuditLog.objects.get(operation=AuditLog.Operation.INSERT)
        assert log.tenant_schema == "escola_a"
        assert log.model_name == "Student"
