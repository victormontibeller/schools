"""Testes de integração para os dados realistas do tenant DEMO."""

import datetime as dt

import pytest
from django.db.models import Count


@pytest.mark.django_db
def test_populate_demo_seed_creates_complete_and_idempotent_dataset():
    """O seed cria o conjunto completo de 2026 sem duplicá-lo na reexecução."""
    from academic_calendar.models import CalendarEvent, Holiday
    from activities.models import Activity, ActivitySubmission
    from addresses.models import StudentAddress, TeacherAddress
    from agenda.models import Schedule, TimeSlot
    from attendance.models import AttendanceEntry, AttendanceRecord
    from base.context import tenant_schema_context
    from classes.models import Class, Enrollment
    from core.demo_seed import DemoSeedService
    from core.models import CustomUser, Role
    from financeiro.models import (
        BillingEntry,
        CollectionReminder,
        CollectionReminderPolicy,
        FinancialContractAmendment,
        FinancialPlanTemplate,
        PaymentAllocation,
        PaymentRecord,
        StudentFinancialContract,
    )
    from financeiro.selectors import BillingSelector
    from guardians.models import Guardian, StudentGuardian
    from rooms.models import Room
    from students.models import Student
    from teachers.models import Subject, Teacher
    from tenancy.models import School

    role, _ = Role.objects.get_or_create(name=Role.Name.ADMIN)
    admin = CustomUser.objects.create_user(
        email="admin@demo.com",
        password="DemoTest123",
        first_name="Admin",
        last_name="Demo",
        role=role,
    )
    school = School.objects.create(schema_name="demo", name="Escola Demonstração")
    service = DemoSeedService(user=admin)

    with tenant_schema_context("demo"):
        service.populate_core(school)
        service.populate_calendar()
        service.populate_attendance()
        service.populate_finance()
    first_payment_ids = set(PaymentRecord.objects.values_list("pk", flat=True))
    first_schedule_ids = set(Schedule.objects.values_list("pk", flat=True))
    first_billing_count = BillingEntry.objects.count()
    with tenant_schema_context("demo"):
        service.populate_core(school)
        service.populate_calendar()
        service.populate_attendance()
        service.populate_finance()

    assert Subject.objects.count() == 10
    assert Teacher.objects.count() == 10
    assert Student.objects.count() == 13
    assert Guardian.objects.count() == 26
    assert StudentGuardian.objects.count() == 26
    assert StudentGuardian.objects.filter(is_primary=True).count() == 13
    assert StudentAddress.objects.count() == 13
    assert TeacherAddress.objects.count() == 10
    assert Class.objects.count() == 4
    assert Class.objects.filter(education_stage=Class.EducationStage.EARLY_CHILDHOOD).count() == 1
    assert Enrollment.objects.filter(status=Enrollment.Status.ACTIVE).count() == 13
    assert Room.objects.count() == 5
    assert TimeSlot.objects.count() == 10
    assert TimeSlot.objects.filter(shift=TimeSlot.Shift.MORNING).count() == 5
    assert TimeSlot.objects.filter(shift=TimeSlot.Shift.AFTERNOON).count() == 5
    assert TimeSlot.objects.filter(shift=TimeSlot.Shift.NIGHT).count() == 0
    assert Schedule.objects.count() == 75
    assert set(Schedule.objects.values_list("pk", flat=True)) == first_schedule_ids
    assert (
        Schedule.objects.filter(valid_from=dt.date(2026, 2, 2), valid_until__isnull=True).count()
        == 75
    )
    assert dict(
        Schedule.objects.values_list("class_obj__name")
        .annotate(count=Count("id"))
        .order_by("class_obj__name")
    ) == {"6º A": 25, "6º B": 25, "7º A": 25}
    assert set(Schedule.objects.values_list("day_of_week", flat=True)) == set(Schedule.Day.values)
    assert all(
        schedule.subject in schedule.teacher.subjects.all()
        for schedule in Schedule.objects.select_related("teacher", "subject")
    )
    assert Activity.objects.count() == 6
    assert ActivitySubmission.objects.count() == 20
    assert Holiday.objects.count() == 13
    assert CalendarEvent.objects.count() == 6
    assert AttendanceRecord.objects.count() == 20
    assert AttendanceEntry.objects.count() > 20
    assert FinancialPlanTemplate.objects.count() == 3
    assert StudentFinancialContract.objects.count() == 6
    assert (
        StudentFinancialContract.objects.filter(
            status=StudentFinancialContract.Status.ACTIVE
        ).count()
        == 3
    )
    assert (
        StudentFinancialContract.objects.filter(
            status=StudentFinancialContract.Status.DRAFT
        ).count()
        == 1
    )
    assert (
        StudentFinancialContract.objects.filter(
            status=StudentFinancialContract.Status.SUSPENDED
        ).count()
        == 1
    )
    assert (
        StudentFinancialContract.objects.filter(
            status=StudentFinancialContract.Status.CANCELLED
        ).count()
        == 1
    )
    assert StudentFinancialContract.objects.filter(class_obj__isnull=False).count() == 6
    assert FinancialContractAmendment.objects.count() == 1
    assert FinancialContractAmendment.objects.get().effective_competency > dt.date.today().replace(
        day=1
    )
    assert BillingEntry.objects.filter(contract__isnull=True).count() == 1
    assert BillingEntry.objects.count() == first_billing_count
    assert set(PaymentRecord.objects.values_list("pk", flat=True)) == first_payment_ids
    assert PaymentRecord.objects.filter(status=PaymentRecord.Status.CONFIRMED).count() == 1
    assert PaymentRecord.objects.filter(status=PaymentRecord.Status.PENDING).count() == 1
    assert PaymentRecord.objects.filter(status=PaymentRecord.Status.REVERSED).count() == 1
    confirmed_payment = PaymentRecord.objects.get(status=PaymentRecord.Status.CONFIRMED)
    assert confirmed_payment.receipt_number.startswith(f"REC-{dt.date.today().year}-")
    allocation = PaymentAllocation.objects.get(payment=confirmed_payment)
    assert allocation.amount == confirmed_payment.amount
    assert allocation.principal_amount == confirmed_payment.amount
    assert CollectionReminder.objects.count() == 0
    overdue_bands = {
        item["faixa"]: item["quantidade"]
        for item in BillingSelector(user=admin).inadimplencia_por_faixa(
            reference_date=dt.date.today()
        )
    }
    assert overdue_bands["1-30 dias"] > 0
    assert overdue_bands["31-60 dias"] > 0
    assert overdue_bands["60+ dias"] > 0
    policy = CollectionReminderPolicy.objects.get(name="Régua DEMO desabilitada")
    assert policy.enabled is False
    assert policy.offset_days == [-5, 0, 5]
    assert policy.channels == ["IN_APP"]
