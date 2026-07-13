"""Testes de integração para os dados realistas do tenant DEMO."""

import pytest


@pytest.mark.django_db
def test_populate_demo_seed_creates_complete_and_idempotent_dataset():
    """O seed cria o conjunto completo de 2026 sem duplicá-lo na reexecução."""
    from academic_calendar.models import CalendarEvent, Holiday
    from activities.models import Activity, ActivitySubmission
    from addresses.models import StudentAddress, TeacherAddress
    from attendance.models import AttendanceEntry, AttendanceRecord
    from classes.models import Class, Enrollment
    from core.demo_seed import DemoSeedService
    from core.models import CustomUser, Role
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

    service.populate_core(school)
    service.populate_calendar()
    service.populate_attendance()
    service.populate_core(school)
    service.populate_calendar()
    service.populate_attendance()

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
    assert Activity.objects.count() == 6
    assert ActivitySubmission.objects.count() == 20
    assert Holiday.objects.count() == 13
    assert CalendarEvent.objects.count() == 6
    assert AttendanceRecord.objects.count() == 20
    assert AttendanceEntry.objects.count() > 20
