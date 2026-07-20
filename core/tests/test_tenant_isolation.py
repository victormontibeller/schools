"""Testes de isolamento por Schema PostgreSQL (multi-tenant).

Estes testes **não** rodam no perfil SQLite (TESTING); requerem PostgreSQL +
django-tenants — execute com `DJANGO_ENV=test_pg pytest -m tenant`.

Usam `django_tenants.test.cases.TenantTestCase`: cria um schema de teste por
classe, бескрeturn connection to schema público ao final. entre cada método, o
TestCase faz flush apenas das tabelas do schema de teste.

Ver ADR-0001.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from django.db import connection, connections
from django.test import TransactionTestCase
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
        return "escola-a.test.local"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()  # cria cls.tenant (schema escola_a) e ativa o schema dele
        # Para criar o segundo tenant é obrigatório estar no schema public.
        connection.set_schema_to_public()
        second = School(schema_name="escola_b", name="Escola B")
        cls.setup_tenant(second)
        second.save(verbosity=0)
        cls.tenant_b = second
        Domain.objects.create(domain="escola-b.test.local", tenant=second, is_primary=True)
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

    def test_student_diary_configuration_is_isolated_between_tenants(self):
        """A configuração dos itens da Agenda nunca atravessa schemas escolares."""
        from student_diary.models import DiaryCategory

        assert DiaryCategory.objects.count() == 7
        mood_a = DiaryCategory.objects.get(name="Humor")
        mood_a.is_enabled = False
        mood_a.save(update_fields=["is_enabled"])
        lunch_a = DiaryCategory.objects.get(name="Almoço")
        lunch_a.applies_afternoon = False
        lunch_a.save(update_fields=["applies_afternoon"])

        connection.set_tenant(self.tenant_b)
        context.current_tenant.set("escola_b")
        assert DiaryCategory.objects.count() == 7
        assert DiaryCategory.objects.get(name="Humor").is_enabled is True
        assert DiaryCategory.objects.get(name="Almoço").applies_afternoon is True

        connection.set_tenant(self.tenant)
        context.current_tenant.set("escola_a")
        assert DiaryCategory.objects.get(name="Humor").is_enabled is False
        assert DiaryCategory.objects.get(name="Almoço").applies_afternoon is False

    def test_role_access_configuration_is_isolated_between_tenants(self):
        """Cada escola mantém sua própria matriz de módulos e ações."""
        from core.access.selectors import AccessConfigurationSelector
        from core.access.services import AccessConfigurationService
        from core.models import Role, RoleModuleAccess

        admin_role = Role.objects.get(name="ADMIN")
        actor = CustomUser.objects.create_user(
            email="access-admin@escola-a.test",
            password="Senha123",
            first_name="Access",
            last_name="Admin",
            role=admin_role,
        )
        current = AccessConfigurationSelector().get_full_matrix()
        access_matrix = {
            role_name: {
                module_key: {action for action, enabled in values.items() if enabled}
                for module_key, values in role_values.items()
            }
            for role_name, role_values in current.values.items()
        }
        versions = {role.name: role.version for role in current.roles}
        access_matrix["SECRETARY"]["finance_contracts"].add("view")
        AccessConfigurationService(user=actor).update_access_matrix(access_matrix, versions)

        connection.set_tenant(self.tenant_b)
        context.current_tenant.set("escola_b")
        access_b = RoleModuleAccess.objects.get(
            role__name="SECRETARY",
            module_key="finance_contracts",
        )
        assert access_b.can_view is False

        connection.set_tenant(self.tenant)
        context.current_tenant.set("escola_a")
        access_a = RoleModuleAccess.objects.get(
            role__name="SECRETARY",
            module_key="finance_contracts",
        )
        assert access_a.can_view is True

    def test_financial_contracts_and_receipt_sequences_are_tenant_scoped(self):
        """Contratos, títulos, alocações e REC anual nunca atravessam schemas."""
        import datetime as dt
        from decimal import Decimal

        from financeiro.models import BillingEntry, StudentFinancialContract
        from financeiro.services import FinanceService, PaymentService

        def create_and_confirm(suffix):
            actor = CustomUser.objects.create_user(
                email=f"finance-{suffix}@tenant.test",
                password="Senha123",
                is_superuser=True,
            )
            student = self._make_student(f"FIN-{suffix}", f"Aluno {suffix}")
            contract = FinanceService(user=actor).create_contract(
                {
                    "student_id": student.pk,
                    "academic_year": 2026,
                    "name": f"Contrato {suffix}",
                    "installment_count": 1,
                    "installment_value": Decimal("100.00"),
                    "due_day": 10,
                }
            )
            FinanceService(user=actor).activate_contract(contract.pk)
            billing = BillingEntry.objects.get(contract=contract)
            payment = PaymentService(user=actor).create_payment(
                allocations=[{"billing_id": billing.pk, "amount": Decimal("100.00")}],
                paid_date=dt.date(2026, 7, 19),
            )
            return contract, PaymentService(user=actor).confirm_payment(payment.pk)

        contract_a, payment_a = create_and_confirm("A")
        assert payment_a.receipt_number == "REC-2026-000001"

        connection.set_tenant(self.tenant_b)
        context.current_tenant.set("escola_b")
        assert StudentFinancialContract.objects.count() == 0
        contract_b, payment_b = create_and_confirm("B")
        assert payment_b.receipt_number == "REC-2026-000001"
        assert not StudentFinancialContract.objects.filter(pk=contract_a.pk).exists()

        connection.set_tenant(self.tenant)
        context.current_tenant.set("escola_a")
        assert StudentFinancialContract.objects.get().pk == contract_a.pk
        assert not StudentFinancialContract.objects.filter(pk=contract_b.pk).exists()

    def test_demo_seed_is_idempotent_on_postgresql_tenant(self):
        """O seed canônico pode ser repetido no schema sem duplicar dados."""
        from core.demo_seed import DemoSeedService
        from core.models import Role
        from students.models import Student

        role, _ = Role.objects.get_or_create(name=Role.Name.ADMIN)
        actor = CustomUser.objects.create_user(
            email="seed-admin@tenant.test",
            password="Senha123",
            first_name="Seed",
            last_name="Admin",
            role=role,
        )
        service = DemoSeedService(user=actor)

        for _ in range(2):
            service.populate_core(self.tenant)
            service.populate_calendar()
            service.populate_attendance()

        assert Student.objects.count() == 13

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

        log = AuditLog.objects.get(
            operation=AuditLog.Operation.INSERT,
            model_name="Student",
        )
        assert log.tenant_schema == "escola_a"
        assert log.model_name == "Student"


@_requires_pg
class TestDiaryApprovalConcurrency(TransactionTestCase):
    """Valida lock real em conexões PostgreSQL independentes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        connection.set_schema_to_public()
        cls.tenant = School(
            schema_name="agenda_concorrente",
            name="Agenda Concorrente",
            settings={"student_diary": {"interactive_enabled": True}},
        )
        cls.tenant.save(verbosity=0)
        cls.domain = Domain.objects.create(
            domain="agenda-concorrente.test.local",
            tenant=cls.tenant,
            is_primary=True,
        )
        connection.set_tenant(cls.tenant)

    @classmethod
    def tearDownClass(cls):
        connection.set_schema_to_public()
        cls.domain.delete()
        cls.tenant.delete(force_drop=True)
        super().tearDownClass()

    def setUp(self):
        connection.set_tenant(self.tenant)
        self._ctx_token = context.current_tenant.set(self.tenant.schema_name)

    def tearDown(self):
        context.current_tenant.reset(self._ctx_token)

    def test_concurrent_diary_approval_creates_single_revision(self):
        """O lock pessimista impede duas publicações para a mesma revisão."""
        from base.exceptions import BusinessRuleViolationError
        from core.models import Role
        from student_diary.tests.test_workflow import _saved_sheet
        from student_diary.workflow_services import DiaryWorkflowService

        role = Role.objects.get(name=Role.Name.ADMIN)
        actor = CustomUser.objects.create_user(
            email="diary-reviewer@tenant.test",
            password="Senha123",
            role=role,
            is_superuser=True,
        )
        sheet, _student = _saved_sheet(actor, actor)
        with patch.object(DiaryWorkflowService, "_schedule_staff_delivery"):
            DiaryWorkflowService(user=actor).submit_sheet(sheet.pk)

        def approve_in_connection():
            thread_connection = connections["default"]
            thread_connection.set_tenant(self.tenant)
            token = context.current_tenant.set(self.tenant.schema_name)
            try:
                thread_actor = CustomUser.objects.get(pk=actor.pk)
                try:
                    publication = DiaryWorkflowService(user=thread_actor).approve_sheet(sheet.pk)
                    return "published", publication.pk
                except BusinessRuleViolationError:
                    return "blocked", None
            finally:
                context.current_tenant.reset(token)
                thread_connection.close()

        with (
            patch.object(DiaryWorkflowService, "_schedule_family_delivery"),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            results = list(executor.map(lambda _index: approve_in_connection(), range(2)))

        sheet.refresh_from_db()
        assert sorted(result[0] for result in results) == ["blocked", "published"]
        assert sheet.publications.count() == 1
