"""Cobertura HTTP dos fluxos financeiros."""

import datetime as dt
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.urls import reverse

from classes.models import Class
from financeiro.models import BillingEntry, FinancialPlan, PaymentRecord
from financeiro.services import FinanceService, PaymentService
from students.models import Student


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
    plan = FinanceService(user=user).create_plan(
        {
            "student_id": student.pk,
            "class_obj_id": class_obj.pk,
            "academic_year": 2026,
            "name": "Plano Views",
            "billing_frequency": FinancialPlan.BillingFrequency.MONTHLY,
            "installment_count": 2,
            "installment_value": Decimal("100.00"),
            "due_day": 10,
        }
    )
    FinanceService(user=user).activate_plan(plan.pk)
    FinanceService(user=user).generate_billings(plan.pk)
    billing = BillingEntry.objects.filter(plan=plan).first()
    return SimpleNamespace(student=student, class_obj=class_obj, plan=plan, billing=billing)


@pytest.mark.django_db
def test_finance_get_views_render_full_and_htmx(client, user, finance_records):
    client.force_login(user)
    urls = [
        reverse("finance_dashboard"),
        reverse("plan_list"),
        reverse("plan_create"),
        reverse("plan_detail", args=[finance_records.plan.pk]),
        reverse("billing_list"),
        reverse("billing_detail", args=[finance_records.billing.pk]),
        reverse("billing_register_payment", args=[finance_records.billing.pk]),
        reverse("billing_cancel", args=[finance_records.billing.pk]),
        reverse("billing_renegotiate", args=[finance_records.billing.pk]),
        reverse("bulk_generate_billings"),
        reverse("finance_revenue_report"),
        reverse("finance_overdue_report"),
    ]
    for url in urls:
        assert client.get(url).status_code == 200

    assert client.get(reverse("plan_list"), HTTP_HX_REQUEST="true").status_code == 200
    assert client.get(reverse("billing_list"), HTTP_HX_REQUEST="true").status_code == 200


@pytest.mark.django_db
def test_finance_command_views_orchestrate_services(client, user, finance_records):
    client.force_login(user)
    plan_result = SimpleNamespace(pk=finance_records.plan.pk)
    with patch("financeiro.views.FinanceService.create_plan", return_value=plan_result) as create:
        response = client.post(
            reverse("plan_create"),
            {
                "student": finance_records.student.pk,
                "class_obj": finance_records.class_obj.pk,
                "academic_year": 2027,
                "name": "Novo plano",
                "billing_frequency": FinancialPlan.BillingFrequency.MONTHLY,
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
        ("plan_activate", [finance_records.plan.pk], "FinanceService.activate_plan"),
        ("plan_suspend", [finance_records.plan.pk], "FinanceService.cancel_plan"),
        (
            "plan_generate_billings",
            [finance_records.plan.pk],
            "FinanceService.generate_billings",
        ),
        (
            "billing_apply_late_fees",
            [finance_records.billing.pk],
            "FinanceService.apply_late_fees",
        ),
    ]
    for url_name, args, method in action_cases:
        with patch(f"financeiro.views.{method}", return_value=1) as command:
            assert (
                client.post(reverse(url_name, args=args), {"reason": "Solicitado"}).status_code
                == 302
            )
            assert command.called

    with patch("financeiro.views.PaymentService.register_payment") as register:
        response = client.post(
            reverse("billing_register_payment", args=[finance_records.billing.pk]),
            {
                "amount": "10.00",
                "paid_date": dt.date.today().isoformat(),
                "payment_method": PaymentRecord.PaymentMethod.PIX,
                "notes": "",
            },
        )
    assert response.status_code == 302
    assert register.called

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

    payment = PaymentService(user=user).register_payment(
        finance_records.billing.pk,
        amount=Decimal("10.00"),
        paid_date=dt.date.today(),
    )
    for action, confirmed in (("confirmar", True), ("estornar", False)):
        with patch("financeiro.views.PaymentService.reconcile") as reconcile:
            response = client.post(
                reverse(
                    "billing_reconcile_payment",
                    args=[finance_records.billing.pk, payment.pk, action],
                )
            )
        assert response.status_code == 302
        reconcile.assert_called_once_with(payment.pk, confirmed=confirmed)


@pytest.mark.django_db
def test_finance_bulk_and_invalid_actions(client, user, finance_records):
    client.force_login(user)
    with patch("financeiro.views.FinanceService.generate_billings_by_class", return_value=3):
        response = client.post(
            reverse("bulk_generate_billings"),
            {
                "class_obj": finance_records.class_obj.pk,
                "academic_year": 2026,
                "month": "7",
            },
        )
    assert response.status_code == 302

    payment = PaymentRecord.objects.create(
        billing=finance_records.billing,
        amount=Decimal("1.00"),
        paid_date=dt.date.today(),
        created_by=user,
        updated_by=user,
    )
    invalid = reverse(
        "billing_reconcile_payment",
        args=[finance_records.billing.pk, payment.pk, "invalida"],
    )
    assert client.get(invalid).status_code == 302
    assert client.post(invalid).status_code == 302
