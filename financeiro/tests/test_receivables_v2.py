"""Cobertura das invariantes introduzidas pelo contas a receber 2.0."""

import datetime as dt
import uuid
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pypdf import PdfReader

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from core.access_catalog import GUARDIAN, MODULES_BY_KEY, allowed_actions
from core.models import CustomUser, Role, RoleModuleAccess
from financeiro.models import (
    BillingEntry,
    CollectionReminder,
    CollectionReminderPolicy,
    FinancialPlanTemplate,
    PaymentRecord,
)
from financeiro.pdf_documents import render_payment_receipt, render_student_statement
from financeiro.selectors import (
    BillingSelector,
    FinancialContractSelector,
    FinancialTemplateSelector,
    PaymentSelector,
    ReminderSelector,
)
from financeiro.services import FinanceService, PaymentService
from financeiro.tasks import deliver_collection_reminder_task, process_collection_reminders_task
from guardians.models import Guardian, StudentGuardian
from notifications.models import Notification
from students.models import Student


def _create_single_payment(service, billing_id, *, amount, **kwargs):
    return service.create_payment(
        allocations=[{"billing_id": billing_id, "amount": amount}],
        **kwargs,
    )


def _student(user, suffix="V2"):
    return Student.objects.create(
        first_name="Aluno",
        last_name=suffix,
        birth_date=dt.date(2012, 1, 1),
        enrollment_number=f"FIN-{suffix}",
        created_by=user,
        updated_by=user,
    )


def _contract(user, student, **overrides):
    data = {
        "student_id": student.pk,
        "academic_year": 2026,
        "name": "Contrato anual",
        "billing_frequency": "MONTHLY",
        "installment_count": 12,
        "installment_value": Decimal("100.00"),
        "due_day": 10,
        "start_competency": dt.date(2026, 1, 1),
        "late_fee_percent": Decimal("2.00"),
        "daily_interest_percent": Decimal("0.1000"),
    }
    data.update(overrides)
    contract = FinanceService(user=user).create_contract(data)
    return FinanceService(user=user).activate_contract(contract.pk)


@pytest.mark.django_db
def test_template_is_snapshot_for_future_contracts_only(user):
    service = FinanceService(user=user)
    template = service.create_financial_template(
        {
            "name": "Anuidade 2026",
            "academic_year": 2026,
            "billing_frequency": "MONTHLY",
            "installment_count": 2,
            "installment_value": Decimal("150.00"),
            "due_day": 8,
            "discount_value": Decimal("10.00"),
        }
    )
    contract = service.create_contract(
        {"template_id": template.pk, "student_id": _student(user, "TPL").pk}
    )

    service.update_financial_template(
        template.pk,
        {
            "version": template.version,
            "name": template.name,
            "academic_year": template.academic_year,
            "billing_frequency": template.billing_frequency,
            "installment_count": 2,
            "installment_value": Decimal("200.00"),
            "due_day": 8,
            "discount_value": Decimal("10.00"),
            "late_fee_percent": 0,
            "daily_interest_percent": 0,
            "description": "",
        },
    )

    contract.refresh_from_db()
    assert contract.template_id == template.pk
    assert contract.installment_value == Decimal("150.00")
    assert contract.discount_value == Decimal("10.00")


@pytest.mark.django_db
def test_activation_materializes_exact_calendar_and_is_idempotent(user):
    contract = _contract(
        user,
        _student(user, "CAL"),
        installment_count=3,
        start_competency=dt.date(2026, 1, 31),
        due_day=28,
    )

    billings = list(BillingEntry.objects.filter(contract=contract).order_by("installment_number"))
    assert [item.competency for item in billings] == [
        dt.date(2026, 1, 1),
        dt.date(2026, 2, 1),
        dt.date(2026, 3, 1),
    ]
    assert [item.due_date for item in billings] == [
        dt.date(2026, 1, 28),
        dt.date(2026, 2, 28),
        dt.date(2026, 3, 28),
    ]
    assert FinanceService(user=user).materialize_contract_billings(contract.pk) == 0


@pytest.mark.django_db
def test_future_amendment_replaces_only_future_unpaid_billings(user):
    contract = _contract(user, _student(user, "AMD"))
    previous = BillingEntry.objects.get(contract=contract, installment_number=8)
    future = BillingEntry.objects.get(contract=contract, installment_number=9)

    amendment = FinanceService(user=user).create_amendment(
        contract.pk,
        {
            "effective_competency": dt.date(2026, 9, 1),
            "reason": "Revisão anual",
            "installment_value": Decimal("120.00"),
            "installment_count": 10,
        },
    )

    previous.refresh_from_db()
    future.refresh_from_db()
    replacement = BillingEntry.objects.get(
        contract=contract, installment_number=9, schedule_revision=amendment.revision
    )
    assert previous.status == BillingEntry.Status.ACTIVE
    assert previous.schedule_revision == 1
    assert future.status == BillingEntry.Status.CANCELLED
    assert replacement.amendment_id == amendment.pk
    assert replacement.principal_value == Decimal("120.00")
    assert not BillingEntry.objects.filter(
        contract=contract,
        installment_number__gt=10,
        schedule_revision=amendment.revision,
    ).exists()


@pytest.mark.django_db
def test_payment_multi_allocation_confirmation_receipt_and_reversal(user):
    contract = _contract(
        user,
        _student(user, "PAY"),
        installment_count=2,
        start_competency=dt.date(2026, 11, 1),
    )
    billings = list(BillingEntry.objects.filter(contract=contract).order_by("due_date"))
    service = PaymentService(user=user)
    payment = service.create_payment(
        allocations=[
            {"billing_id": billings[0].pk, "amount": Decimal("40.00")},
            {"billing_id": billings[1].pk, "amount": Decimal("60.00")},
        ],
        paid_date=dt.date(2026, 7, 19),
        payment_method="PIX",
    )
    assert payment.status == PaymentRecord.Status.PENDING
    assert all(item.paid_value == 0 for item in billings)

    confirmed = service.confirm_payment(payment.pk)
    assert confirmed.receipt_number == "REC-2026-000001"
    assert list(
        confirmed.allocations.order_by("amount").values_list("principal_amount", flat=True)
    ) == [Decimal("40.00"), Decimal("60.00")]

    reversed_payment = service.reverse_payment(payment.pk, reason="Baixa duplicada")
    assert reversed_payment.status == PaymentRecord.Status.REVERSED
    assert reversed_payment.deleted_at is None
    assert all(
        value == Decimal("0.00")
        for value in BillingEntry.objects.filter(contract=contract).values_list(
            "paid_value", flat=True
        )
    )


@pytest.mark.django_db
def test_payment_idempotency_key_does_not_duplicate_allocations(user):
    contract = _contract(user, _student(user, "IDEMP"), installment_count=1)
    billing = BillingEntry.objects.get(contract=contract)
    key = uuid.uuid4()
    service = PaymentService(user=user)

    first = _create_single_payment(
        service,
        billing.pk,
        amount=Decimal("25.00"),
        paid_date=dt.date(2026, 7, 19),
        idempotency_key=key,
    )
    second = _create_single_payment(
        service,
        billing.pk,
        amount=Decimal("25.00"),
        paid_date=dt.date(2026, 7, 19),
        idempotency_key=key,
    )

    assert second.pk == first.pk
    assert first.allocations.count() == 1


@pytest.mark.django_db
def test_competence_and_cash_use_different_dates(user):
    contract = _contract(
        user,
        _student(user, "REPORT"),
        installment_count=1,
        start_competency=dt.date(2026, 1, 1),
    )
    billing = BillingEntry.objects.get(contract=contract)
    payment = _create_single_payment(
        PaymentService(user=user),
        billing.pk,
        amount=Decimal("100.00"),
        paid_date=dt.date(2026, 7, 19),
    )
    PaymentService(user=user).confirm_payment(payment.pk)
    selector = BillingSelector(user=user)

    assert selector.competence_report(year=2026, month=1)["received"] == Decimal("100.00")
    assert selector.cash_report(year=2026, month=1)["net"] == Decimal("0.00")
    assert selector.cash_report(year=2026, month=7)["net"] == Decimal("100.00")


@pytest.mark.django_db
def test_pending_concurrent_payment_is_revalidated_on_confirmation(user):
    contract = _contract(
        user,
        _student(user, "RACE"),
        installment_count=1,
        start_competency=dt.date(2026, 12, 1),
    )
    billing = BillingEntry.objects.get(contract=contract)
    service = PaymentService(user=user)
    first = _create_single_payment(
        service, billing.pk, amount=Decimal("100.00"), paid_date=dt.date(2026, 7, 19)
    )
    second = _create_single_payment(
        service, billing.pk, amount=Decimal("100.00"), paid_date=dt.date(2026, 7, 19)
    )

    service.confirm_payment(first.pk)
    with pytest.raises(BusinessRuleViolationError):
        service.confirm_payment(second.pk)
    second.refresh_from_db()
    assert second.status == PaymentRecord.Status.PENDING


@pytest.mark.django_db
def test_confirmation_amortizes_charges_before_principal(user):
    contract = _contract(user, _student(user, "FEE"), installment_count=1)
    billing = BillingEntry.objects.get(contract=contract)
    payment = _create_single_payment(
        PaymentService(user=user),
        billing.pk,
        amount=Decimal("50.00"),
        paid_date=dt.date(2026, 1, 20),
    )

    PaymentService(user=user).confirm_payment(payment.pk)
    allocation = payment.allocations.get()
    assert allocation.late_fee_amount == Decimal("2.00")
    assert allocation.interest_amount == Decimal("1.00")
    assert allocation.principal_amount == Decimal("47.00")


@pytest.mark.django_db
def test_ad_hoc_billing_does_not_require_contract(user):
    billing = FinanceService(user=user).create_ad_hoc_billing(
        {
            "student_id": _student(user, "ADHOC").pk,
            "description": "Material didático",
            "category": "MATERIAL",
            "amount": Decimal("80.00"),
            "due_date": dt.date(2026, 8, 10),
        }
    )
    assert billing.contract_id is None
    assert billing.category == BillingEntry.Category.MATERIAL


def _guardian_access(user, student):
    role, _ = Role.objects.get_or_create(name=GUARDIAN)
    guardian_user = CustomUser.objects.create_user(
        email="guardian-finance@test.com", password="Senha123", role=role
    )
    for module_key in ("finance_overview", "finance_billings"):
        RoleModuleAccess.objects.update_or_create(
            role=role,
            module_key=module_key,
            defaults={
                "can_view": True,
                "can_create": False,
                "can_edit": False,
                "can_deactivate": False,
                "created_by": user,
                "updated_by": user,
            },
        )
    guardian = Guardian.objects.create(
        user=guardian_user,
        first_name="Responsável",
        accepts_email_notifications=True,
        created_by=user,
        updated_by=user,
    )
    StudentGuardian.objects.create(
        student=student,
        guardian=guardian,
        has_custody=True,
        created_by=user,
        updated_by=user,
    )
    return guardian_user, guardian


@pytest.mark.django_db(transaction=True)
def test_reminders_require_policy_rules_dedupe_and_use_on_commit(user):
    student = _student(user, "REM")
    contract = _contract(user, student, installment_count=1)
    billing = BillingEntry.objects.get(contract=contract)
    _guardian_access(user, student)
    service = FinanceService(user=user)
    with pytest.raises(BusinessRuleViolationError):
        service.configure_reminder_policy(
            {"name": "Régua", "enabled": True, "offset_days": [], "channels": []}
        )
    service.configure_reminder_policy(
        {"name": "Régua", "enabled": True, "offset_days": [0], "channels": ["IN_APP"]}
    )

    with patch("financeiro.tasks.deliver_collection_reminder_task.delay") as delay:
        assert service.send_manual_reminder(billing.pk) == 1
        assert service.send_manual_reminder(billing.pk) == 0
    assert CollectionReminder.objects.count() == 1
    delay.assert_called_once()


@pytest.mark.django_db(transaction=True)
def test_manual_reminder_ignores_ineligible_recipient_and_closed_billing(user):
    student = _student(user, "REM-SKIP")
    contract = _contract(user, student, installment_count=1)
    billing = BillingEntry.objects.get(contract=contract)
    guardian_user, _guardian = _guardian_access(user, student)
    RoleModuleAccess.objects.filter(role=guardian_user.role, module_key="finance_billings").update(
        can_view=False
    )
    service = FinanceService(user=user)

    with patch("financeiro.tasks.deliver_collection_reminder_task.delay") as delay:
        assert service.send_manual_reminder(billing.pk) == 0
        billing.status = BillingEntry.Status.CANCELLED
        billing.save(update_fields=["status"])
        assert service.send_manual_reminder(billing.pk) == 0

    assert CollectionReminder.objects.count() == 0
    delay.assert_not_called()


@pytest.mark.django_db
def test_in_app_reminder_delivery_revalidates_access_and_uses_generic_message(user):
    student = _student(user, "DELIVERY")
    contract = _contract(user, student, installment_count=1)
    billing = BillingEntry.objects.get(contract=contract)
    guardian_user, guardian = _guardian_access(user, student)
    reminder = CollectionReminder.objects.create(
        billing=billing,
        guardian=guardian,
        recipient=guardian_user,
        channel="IN_APP",
        rule_offset_days=0,
        scheduled_for=dt.date.today(),
        created_by=user,
        updated_by=user,
    )

    deliver_collection_reminder_task.run("public", str(reminder.pk))

    reminder.refresh_from_db()
    notification = Notification.objects.get(recipient=guardian_user)
    assert reminder.status == CollectionReminder.Status.SENT
    assert student.first_name not in notification.message
    assert str(billing.outstanding_value) not in notification.message
    assert notification.action_url.endswith(f"/cobrancas/{billing.pk}/")


@pytest.mark.django_db(transaction=True)
def test_scheduled_reminders_and_policy_validation_branches(user):
    student = _student(user, "SCHEDULED")
    contract = _contract(user, student, installment_count=1)
    billing = BillingEntry.objects.get(contract=contract)
    _guardian_access(user, student)
    service = FinanceService(user=user)

    with pytest.raises(ValidationError):
        service.configure_reminder_policy(
            {"name": "Inválida", "enabled": False, "offset_days": [0], "channels": ["WHATSAPP"]}
        )
    with pytest.raises(ValidationError):
        service.configure_reminder_policy(
            {"name": "Inválida", "enabled": False, "offset_days": [366], "channels": []}
        )
    service.configure_reminder_policy(
        {"name": "Agendada", "enabled": True, "offset_days": [0], "channels": ["EMAIL"]}
    )
    updated = service.configure_reminder_policy(
        {"name": "Agendada 2", "enabled": True, "offset_days": [0], "channels": ["EMAIL"]}
    )
    assert updated.name == "Agendada 2"

    with patch("financeiro.tasks.deliver_collection_reminder_task.delay") as delay:
        assert service.run_scheduled_reminders(reference_date=billing.due_date) == 1
    delay.assert_called_once()
    assert process_collection_reminders_task.run("public", "2026-07-19") == 0


@pytest.mark.django_db
def test_reminder_delivery_skip_email_failure_retry_and_service_idempotence(user):
    student = _student(user, "CHANNELS")
    contract = _contract(user, student, installment_count=1)
    billing = BillingEntry.objects.get(contract=contract)
    guardian_user, guardian = _guardian_access(user, student)

    deliver_collection_reminder_task.run("public", str(uuid.uuid4()))

    def reminder(channel, offset):
        return CollectionReminder.objects.create(
            billing=billing,
            guardian=guardian,
            recipient=guardian_user,
            channel=channel,
            rule_offset_days=offset,
            scheduled_for=dt.date.today(),
            created_by=user,
            updated_by=user,
        )

    skipped = reminder("WHATSAPP", 1)
    deliver_collection_reminder_task.run("public", str(skipped.pk))
    skipped.refresh_from_db()
    assert skipped.status == CollectionReminder.Status.SKIPPED

    successful = reminder("EMAIL", 2)
    successful_transport = SimpleNamespace(
        send_individual=lambda *args, **kwargs: True,
        last_log_id=uuid.uuid4(),
        last_result=None,
    )
    with patch("notifications.task_helpers.get_transport", return_value=successful_transport):
        deliver_collection_reminder_task.run("public", str(successful.pk))
    successful.refresh_from_db()
    assert successful.status == CollectionReminder.Status.SENT

    failed = reminder("EMAIL", 3)
    failed_transport = SimpleNamespace(
        send_individual=lambda *args, **kwargs: False,
        last_log_id=uuid.uuid4(),
        last_result=SimpleNamespace(retryable=False),
    )
    with patch("notifications.task_helpers.get_transport", return_value=failed_transport):
        deliver_collection_reminder_task.run("public", str(failed.pk))
    failed.refresh_from_db()
    assert failed.status == CollectionReminder.Status.FAILED

    retrying = reminder("EMAIL", 4)
    retry_transport = SimpleNamespace(
        send_individual=lambda *args, **kwargs: False,
        last_log_id=uuid.uuid4(),
        last_result=SimpleNamespace(retryable=True),
    )
    with (
        patch("notifications.task_helpers.get_transport", return_value=retry_transport),
        patch("notifications.task_helpers.retry_email_if_needed") as retry,
    ):
        deliver_collection_reminder_task.run("public", str(retrying.pk))
    retry.assert_called_once()
    retrying.refresh_from_db()
    assert retrying.message_log_id == retry_transport.last_log_id

    service = FinanceService(user=None)
    service.attach_reminder_message_log(retrying.pk, uuid.uuid4())
    same = service.complete_reminder_delivery(
        successful.pk, status=CollectionReminder.Status.FAILED
    )
    assert same.status == CollectionReminder.Status.SENT
    with pytest.raises(ObjectNotFoundError):
        service.attach_reminder_message_log(uuid.uuid4(), uuid.uuid4())
    with pytest.raises(ObjectNotFoundError):
        service.complete_reminder_delivery(uuid.uuid4(), status=CollectionReminder.Status.FAILED)


@pytest.mark.django_db
def test_financial_selectors_filters_and_not_found_branches(user):
    student = _student(user, "SELECT")
    contract = _contract(user, student, installment_count=1)
    billing = BillingEntry.objects.get(contract=contract)
    template = FinancialPlanTemplate.objects.create(
        name="Seletor",
        academic_year=2026,
        installment_count=1,
        installment_value=Decimal("100.00"),
        due_day=10,
        created_by=user,
        updated_by=user,
    )
    assert FinancialTemplateSelector().list_templates(search="Seletor", year=2026).total == 1
    assert FinancialContractSelector().list_contracts(search="Contrato", status="ACTIVE").total == 1
    selector = BillingSelector(user=user)
    assert selector.list_billings(search="Parcela", contract_id=contract.pk).total == 1
    assert (
        selector.list_billings(
            class_id=contract.class_obj_id,
            date_from=billing.due_date,
            date_to=billing.due_date,
        ).total
        == 1
    )
    for status in ("CANCELLED", "PAID", "OVERDUE", "PARTIAL", "OPEN"):
        selector.list_billings(status=status)
    payment = _create_single_payment(
        PaymentService(user=user),
        billing.pk,
        amount=Decimal("1.00"),
        paid_date=dt.date(2026, 7, 19),
    )
    assert PaymentSelector().list_payments(status="").total == 1
    CollectionReminderPolicy.objects.create(name="Filtro", created_by=user, updated_by=user)
    assert ReminderSelector().get_policy().name == "Filtro"
    assert ReminderSelector().list_reminders(status="FAILED").total == 0

    assert FinancialTemplateSelector().get_template(template.pk) == template
    for callback in (
        lambda: FinancialTemplateSelector().get_template(uuid.uuid4()),
        lambda: FinancialContractSelector().get_contract(uuid.uuid4()),
        lambda: selector.get_billing_by_id(uuid.uuid4()),
        lambda: PaymentSelector().get_payment(uuid.uuid4()),
    ):
        with pytest.raises(ObjectNotFoundError):
            callback()
    assert payment.status == PaymentRecord.Status.PENDING


@pytest.mark.django_db
def test_guardian_action_ceiling_and_scoped_selector(user):
    student = _student(user, "SCOPE")
    other = _student(user, "OTHER")
    contract = _contract(user, student, installment_count=1)
    other_contract = _contract(user, other, installment_count=1)
    guardian_user, _guardian = _guardian_access(user, student)

    assert allowed_actions(MODULES_BY_KEY["finance_overview"], GUARDIAN) == frozenset({"view"})
    assert allowed_actions(MODULES_BY_KEY["finance_billings"], GUARDIAN) == frozenset({"view"})
    result = BillingSelector(user=guardian_user).list_billings(status="")
    assert [item.student_id for item in result.items] == [student.pk]
    assert BillingEntry.objects.filter(contract=contract).exists()
    other_billing = BillingEntry.objects.get(contract=other_contract)
    _create_single_payment(
        PaymentService(user=user),
        other_billing.pk,
        amount=Decimal("1.00"),
        paid_date=dt.date.today(),
        payment_method="CASH",
        idempotency_key=str(uuid.uuid4()),
    )
    with pytest.raises(ObjectNotFoundError):
        BillingSelector(user=guardian_user).get_payments(other_billing.pk)


@pytest.mark.django_db
def test_guardian_cannot_open_payment_with_allocation_for_another_student(user):
    student = _student(user, "PAYMENT-SCOPE")
    other = _student(user, "PAYMENT-OTHER")
    first_billing = BillingEntry.objects.get(contract=_contract(user, student, installment_count=1))
    other_billing = BillingEntry.objects.get(contract=_contract(user, other, installment_count=1))
    guardian_user, _guardian = _guardian_access(user, student)
    payment = PaymentService(user=user).create_payment(
        allocations=[
            {"billing_id": first_billing.pk, "amount": Decimal("10.00")},
            {"billing_id": other_billing.pk, "amount": Decimal("10.00")},
        ],
        paid_date=dt.date.today(),
        payment_method="CASH",
        idempotency_key=str(uuid.uuid4()),
    )

    with pytest.raises(ObjectNotFoundError):
        PaymentSelector(user=guardian_user).get_payment(payment.pk)


@pytest.mark.django_db
def test_receipt_and_statement_are_valid_pdfs_and_keep_reversed_document(user):
    student = _student(user, "PDF")
    contract = _contract(
        user,
        student,
        installment_count=1,
        start_competency=dt.date(2026, 12, 1),
    )
    billing = BillingEntry.objects.get(contract=contract)
    service = PaymentService(user=user)
    payment = _create_single_payment(
        service, billing.pk, amount=Decimal("100.00"), paid_date=dt.date(2026, 7, 19)
    )
    service.confirm_payment(payment.pk)
    service.reverse_payment(payment.pk, reason="Teste de estorno")
    payment.refresh_from_db()

    receipt = render_payment_receipt(payment, school_name="Escola Teste")
    statement = render_student_statement(
        student, BillingSelector().student_statement(student.pk), school_name="Escola Teste"
    )
    assert len(PdfReader(BytesIO(receipt)).pages) == 1
    assert "PAGAMENTO ESTORNADO" in PdfReader(BytesIO(receipt)).pages[0].extract_text()
    assert len(PdfReader(BytesIO(statement)).pages) == 1
