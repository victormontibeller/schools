"""Cobertura HTTP dos fluxos financeiros."""

import datetime as dt
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.urls import resolve, reverse

from classes.models import Class
from core.models import CustomUser, Role, RoleModuleAccess
from core.permissions import resolve_view_access
from financeiro.models import (
    BillingEntry,
    FinancialPlanTemplate,
    PaymentRecord,
    StudentFinancialContract,
)
from financeiro.services import FinanceService, PaymentService
from students.models import Student


def _create_single_payment(service, billing_id, *, amount, **kwargs):
    return service.create_payment(
        allocations=[{"billing_id": billing_id, "amount": amount}],
        **kwargs,
    )


def _finance_actor(email, permissions):
    role = Role.objects.get(name=Role.Name.SECRETARY)
    RoleModuleAccess.objects.filter(role=role, module_key__startswith="finance_").update(
        can_view=False,
        can_create=False,
        can_edit=False,
        can_deactivate=False,
    )
    for module_key, actions in permissions.items():
        RoleModuleAccess.objects.filter(role=role, module_key=module_key).update(
            can_view="view" in actions,
            can_create="create" in actions,
            can_edit="edit" in actions,
        )
    return CustomUser.objects.create_user(email=email, password="Senha123", role=role)


@pytest.mark.parametrize(
    ("route_name", "args", "module_key", "action"),
    [
        ("finance_dashboard", (), "finance_overview", "view"),
        ("financial_template_list", (), "finance_templates", "view"),
        ("financial_template_create", (), "finance_templates", "create"),
        ("financial_template_edit", (uuid.uuid4(),), "finance_templates", "edit"),
        ("contract_list", (), "finance_contracts", "view"),
        ("contract_create", (), "finance_contracts", "create"),
        ("contract_amendment_create", (uuid.uuid4(),), "finance_contracts", "edit"),
        ("contract_materialize_billings", (uuid.uuid4(),), "finance_billings", "create"),
        ("billing_list", (), "finance_billings", "view"),
        ("billing_create", (), "finance_billings", "create"),
        ("billing_cancel", (uuid.uuid4(),), "finance_billings", "edit"),
        ("billing_register_payment", (uuid.uuid4(),), "finance_payments", "create"),
        ("payment_queue", (), "finance_payments", "view"),
        ("payment_confirm", (uuid.uuid4(),), "finance_payments", "edit"),
        ("payment_reverse", (uuid.uuid4(),), "finance_payments", "edit"),
        ("reminder_history", (), "finance_reminders", "view"),
        ("reminder_settings", (), "finance_reminders", "edit"),
        ("billing_send_reminder", (uuid.uuid4(),), "finance_reminders", "edit"),
        ("finance_revenue_report", (), "finance_revenue_reports", "view"),
        ("finance_overdue_report", (), "finance_overdue_reports", "view"),
        ("student_financial_statement", (uuid.uuid4(),), "finance_billings", "view"),
        ("student_financial_statement_pdf", (uuid.uuid4(),), "finance_billings", "view"),
        ("payment_receipt_pdf", (uuid.uuid4(),), "finance_billings", "view"),
    ],
)
def test_finance_routes_declare_granular_access(route_name, args, module_key, action):
    match = resolve(reverse(route_name, args=args))

    assert resolve_view_access(match.func, match.url_name or "", "GET") == (module_key, action)


@pytest.mark.django_db
def test_finance_dashboard_renders_only_authorized_process_shortcuts(client):
    role = Role.objects.get(name=Role.Name.SECRETARY)
    actor = CustomUser.objects.create_user(
        email="finance-dashboard-granular@test.com",
        password="Senha123",
        role=role,
    )
    RoleModuleAccess.objects.filter(role=role, module_key="finance_overview").update(can_view=True)
    RoleModuleAccess.objects.filter(role=role, module_key="finance_contracts").update(
        can_view=True,
        can_create=True,
    )
    client.force_login(actor)

    response = client.get(reverse("finance_dashboard"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "NOVO CONTRATO" in content
    assert "NOVA BAIXA" not in content
    assert reverse("contract_list") in content
    assert reverse("financial_template_list") not in content
    assert "Caixa do mês" not in content
    assert "Conciliações pendentes" not in content
    assert "Lembretes com falha" not in content


@pytest.fixture()
def finance_records(user):
    student = Student.objects.create(
        first_name="Aluno",
        last_name="Financeiro",
        birth_date=dt.date(2012, 1, 1),
        enrollment_number="VIEW-FIN-1",
        created_by=user,
        updated_by=user,
    )
    class_obj = Class.objects.create(
        name="Financeiro Views",
        grade=Class.Grade.ELEMENTARY_1,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        academic_year=2026,
        max_students=30,
        created_by=user,
        updated_by=user,
    )
    contract = FinanceService(user=user).create_contract(
        {
            "student_id": student.pk,
            "class_obj_id": class_obj.pk,
            "academic_year": 2026,
            "name": "Plano Views",
            "billing_frequency": StudentFinancialContract.BillingFrequency.MONTHLY,
            "installment_count": 2,
            "installment_value": Decimal("100.00"),
            "due_day": 10,
        }
    )
    FinanceService(user=user).activate_contract(contract.pk)
    FinanceService(user=user).materialize_contract_billings(contract.pk)
    billing = BillingEntry.objects.filter(contract=contract).first()
    return SimpleNamespace(student=student, class_obj=class_obj, contract=contract, billing=billing)


@pytest.mark.django_db
def test_finance_get_views_render_full_and_htmx(client, user, finance_records):
    client.force_login(user)
    urls = [
        reverse("finance_dashboard"),
        reverse("contract_list"),
        reverse("contract_create"),
        reverse("contract_detail", args=[finance_records.contract.pk]),
        reverse("billing_list"),
        reverse("billing_detail", args=[finance_records.billing.pk]),
        reverse("billing_register_payment", args=[finance_records.billing.pk]),
        reverse("billing_cancel", args=[finance_records.billing.pk]),
        reverse("billing_renegotiate", args=[finance_records.billing.pk]),
        reverse("bulk_materialize_billings"),
        reverse("finance_revenue_report"),
        reverse("finance_overdue_report"),
    ]
    for url in urls:
        assert client.get(url).status_code == 200

    assert client.get(reverse("contract_list"), HTTP_HX_REQUEST="true").status_code == 200
    assert client.get(reverse("billing_list"), HTTP_HX_REQUEST="true").status_code == 200


@pytest.mark.django_db
def test_contract_detail_does_not_query_or_render_billings_without_access(client, finance_records):
    actor = _finance_actor("contracts-only@test.com", {"finance_contracts": {"view"}})
    client.force_login(actor)

    with patch("financeiro.views.BillingSelector.get_billings_for_contract") as query:
        response = client.get(reverse("contract_detail", args=[finance_records.contract.pk]))

    assert response.status_code == 200
    assert "Cobranças materializadas" not in response.content.decode()
    query.assert_not_called()


@pytest.mark.django_db
def test_billing_detail_does_not_query_or_render_payments_without_access(client, finance_records):
    actor = _finance_actor("billings-only@test.com", {"finance_billings": {"view"}})
    client.force_login(actor)

    with patch("financeiro.views.BillingSelector.get_payments") as query:
        response = client.get(reverse("billing_detail", args=[finance_records.billing.pk]))

    assert response.status_code == 200
    assert "Pagamentos e conciliação" not in response.content.decode()
    query.assert_not_called()


@pytest.mark.django_db
def test_payment_forms_do_not_link_to_billings_without_access(client, finance_records):
    actor = _finance_actor("payments-only@test.com", {"finance_payments": {"create"}})
    client.force_login(actor)
    billing_url = reverse("billing_detail", args=[finance_records.billing.pk])

    single = client.get(reverse("billing_register_payment", args=[finance_records.billing.pk]))
    batch = client.get(reverse("payment_create"), {"student_id": finance_records.student.pk})

    assert single.status_code == batch.status_code == 200
    assert billing_url not in single.content.decode()
    assert billing_url not in batch.content.decode()
    assert reverse("payment_queue") in single.content.decode()


@pytest.mark.django_db
def test_finance_command_views_orchestrate_services(client, user, finance_records):
    client.force_login(user)
    contract_result = SimpleNamespace(pk=finance_records.contract.pk)
    with patch(
        "financeiro.views.FinanceService.create_contract", return_value=contract_result
    ) as create:
        response = client.post(
            reverse("contract_create"),
            {
                "student": finance_records.student.pk,
                "class_obj": finance_records.class_obj.pk,
                "academic_year": 2027,
                "name": "Novo contrato",
                "billing_frequency": StudentFinancialContract.BillingFrequency.MONTHLY,
                "installment_count": 2,
                "installment_value": "120.00",
                "due_day": 10,
                "discount_value": "0",
                "late_fee_percent": "0",
                "daily_interest_percent": "0",
                "notes": "",
            },
        )
    assert response.status_code == 302
    assert create.called

    action_cases = [
        ("contract_activate", [finance_records.contract.pk], "FinanceService.activate_contract"),
        ("contract_suspend", [finance_records.contract.pk], "FinanceService.suspend_contract"),
        (
            "contract_materialize_billings",
            [finance_records.contract.pk],
            "FinanceService.materialize_contract_billings",
        ),
        (
            "billing_assess_late_charges",
            [finance_records.billing.pk],
            "FinanceService.assess_late_charges",
        ),
    ]
    for url_name, args, method in action_cases:
        with patch(f"financeiro.views.{method}", return_value=1) as command:
            assert (
                client.post(reverse(url_name, args=args), {"reason": "Solicitado"}).status_code
                == 302
            )
            assert command.called

    with patch("financeiro.views.PaymentService.create_payment") as create_payment:
        response = client.post(
            reverse("billing_register_payment", args=[finance_records.billing.pk]),
            {
                "amount": "10.00",
                "paid_date": dt.date.today().isoformat(),
                "payment_method": PaymentRecord.PaymentMethod.PIX,
                "idempotency_key": str(uuid.uuid4()),
                "notes": "",
            },
        )
    assert response.status_code == 302
    assert create_payment.called

    with patch("financeiro.views.FinanceService.cancel_billing") as cancel:
        response = client.post(
            reverse("billing_cancel", args=[finance_records.billing.pk]),
            {"reason": "Solicitado pela família"},
        )
    assert response.status_code == 302
    assert cancel.called

    with patch("financeiro.views.FinanceService.renegotiate_billing") as renegotiate:
        response = client.post(
            reverse("billing_renegotiate", args=[finance_records.billing.pk]),
            {
                "new_due_date": (dt.date.today() + dt.timedelta(days=30)).isoformat(),
                "new_value": "90.00",
                "installment_count": 2,
            },
        )
    assert response.status_code == 302
    assert renegotiate.called


@pytest.mark.django_db
def test_finance_bulk_materialization(client, user, finance_records):
    client.force_login(user)
    with patch("financeiro.views.FinanceService.materialize_billings_by_class", return_value=3):
        response = client.post(
            reverse("bulk_materialize_billings"),
            {
                "class_obj": finance_records.class_obj.pk,
                "academic_year": 2026,
                "month": "7",
            },
        )
    assert response.status_code == 302


@pytest.mark.django_db
def test_finance_v2_pages_and_pdf_documents_render(client, user, finance_records):
    client.force_login(user)
    template = FinancialPlanTemplate.objects.create(
        name="Modelo HTTP",
        academic_year=2026,
        installment_count=2,
        installment_value=Decimal("100.00"),
        due_day=10,
        created_by=user,
        updated_by=user,
    )
    urls = [
        reverse("financial_template_list"),
        reverse("financial_template_create"),
        reverse("financial_template_detail", args=[template.pk]),
        reverse("financial_template_edit", args=[template.pk]),
        reverse("contract_edit", args=[finance_records.contract.pk]),
        reverse("contract_amendment_create", args=[finance_records.contract.pk]),
        reverse("billing_create"),
        reverse("payment_create"),
        reverse("payment_queue"),
        reverse("reminder_settings"),
        reverse("reminder_history"),
        reverse("student_financial_statement", args=[finance_records.student.pk]),
    ]
    for url in urls:
        assert client.get(url).status_code == 200

    payment = _create_single_payment(
        PaymentService(user=user),
        finance_records.billing.pk,
        amount=Decimal("10.00"),
        paid_date=dt.date.today(),
    )
    PaymentService(user=user).confirm_payment(payment.pk)
    assert client.get(reverse("payment_detail", args=[payment.pk])).status_code == 200
    receipt = client.get(reverse("payment_receipt_pdf", args=[payment.pk]))
    statement = client.get(
        reverse("student_financial_statement_pdf", args=[finance_records.student.pk])
    )
    assert receipt.status_code == 200
    assert receipt["Content-Type"] == "application/pdf"
    assert statement.status_code == 200
    assert statement.content.startswith(b"%PDF")
    csv_response = client.get(reverse("finance_overdue_report"), {"format": "csv"})
    assert csv_response.status_code == 200
    assert csv_response["Content-Type"].startswith("text/csv")


@pytest.mark.django_db
def test_finance_v2_operational_posts_and_htmx_cards(client, user, finance_records):
    client.force_login(user)
    template_payload = {
        "name": "Modelo operacional",
        "academic_year": 2028,
        "billing_frequency": "MONTHLY",
        "installment_count": 2,
        "installment_value": "150.00",
        "due_day": 8,
        "discount_value": "0.00",
        "late_fee_percent": "2.00",
        "daily_interest_percent": "0.1000",
        "description": "Modelo para novos contratos",
    }
    response = client.post(reverse("financial_template_create"), template_payload)
    assert response.status_code == 302
    template = FinancialPlanTemplate.objects.get(name="Modelo operacional")
    response = client.post(
        reverse("financial_template_edit", args=[template.pk]),
        {**template_payload, "description": "Termos atualizados"},
    )
    assert response.status_code == 302
    assert client.get(reverse("financial_template_list"), HTTP_HX_REQUEST="true").status_code == 200

    draft = FinanceService(user=user).create_contract(
        {
            "student_id": finance_records.student.pk,
            "academic_year": 2027,
            "name": "Contrato editável",
            "billing_frequency": "MONTHLY",
            "installment_count": 2,
            "installment_value": Decimal("100.00"),
            "due_day": 10,
        }
    )
    contract_payload = {
        "template": "",
        "student": finance_records.student.pk,
        "class_obj": finance_records.class_obj.pk,
        "academic_year": 2027,
        "name": "Contrato editado",
        "billing_frequency": "MONTHLY",
        "installment_count": 2,
        "installment_value": "110.00",
        "due_day": 11,
        "start_competency": "2027-01-01",
        "discount_value": "0.00",
        "late_fee_percent": "2.00",
        "daily_interest_percent": "0.1000",
        "notes": "",
    }
    edit_url = reverse("contract_edit", args=[draft.pk])
    assert client.get(edit_url, HTTP_HX_REQUEST="true").status_code == 200
    response = client.post(edit_url, contract_payload, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    assert b"contract-information-card" in response.content

    amendment_response = client.post(
        reverse("contract_amendment_create", args=[finance_records.contract.pk]),
        {
            "effective_competency": "2027-01-01",
            "reason": "Condição futura",
            "due_day": 12,
        },
    )
    assert amendment_response.status_code == 302

    ad_hoc_response = client.post(
        reverse("billing_create"),
        {
            "student": finance_records.student.pk,
            "category": "MATERIAL",
            "description": "Material operacional",
            "principal_value": "50.00",
            "discount_value": "0.00",
            "competency": "2026-07-01",
            "due_date": "2026-07-28",
        },
    )
    assert ad_hoc_response.status_code == 302

    payment_response = client.post(
        reverse("payment_create"),
        {
            "student_id": finance_records.student.pk,
            "paid_date": dt.date.today().isoformat(),
            "payment_method": "PIX",
            "reference": "REF-INTERNA",
            "idempotency_key": str(uuid.uuid4()),
            f"allocation_{finance_records.billing.pk}": "10.00",
        },
    )
    assert payment_response.status_code == 302
    payment = PaymentRecord.objects.filter(status="PENDING").latest("created_at")
    assert client.get(reverse("payment_queue"), HTTP_HX_REQUEST="true").status_code == 200
    assert client.post(reverse("payment_confirm", args=[payment.pk])).status_code == 302
    assert client.get(reverse("payment_reverse", args=[payment.pk])).status_code == 200
    assert (
        client.post(
            reverse("payment_reverse", args=[payment.pk]), {"reason": "Correção operacional"}
        ).status_code
        == 302
    )

    assert (
        client.post(
            reverse("reminder_settings"),
            {
                "name": "Régua operacional",
                "enabled": True,
                "channels": ["IN_APP"],
                "offset_days_text": "-3, 0, 5",
            },
        ).status_code
        == 302
    )
    assert client.get(reverse("reminder_history"), HTTP_HX_REQUEST="true").status_code == 200
    assert (
        client.post(reverse("billing_send_reminder", args=[finance_records.billing.pk])).status_code
        == 302
    )
