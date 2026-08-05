"""Concorrência dos comandos de atividades em PostgreSQL com django-tenants."""

import datetime as dt
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import connection, connections
from django.test import TransactionTestCase

from base import context
from core.models import CustomUser
from tenancy.models import Domain, School

pytestmark = [pytest.mark.tenant]

_requires_pg = pytest.mark.skipif(
    os.environ.get("DJANGO_ENV") != "test_pg",
    reason="Requer perfil DJANGO_ENV=test_pg (PostgreSQL + django_tenants)",
)


@_requires_pg
class TestActivityConcurrency(TransactionTestCase):
    """Exercita o lock comum entre edição da atividade e lançamento de notas."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        connection.set_schema_to_public()
        cls.tenant = School(
            schema_name="activities_concurrency",
            name="Atividades Concorrentes",
        )
        cls.tenant.save(verbosity=0)
        cls.domain = Domain.objects.create(
            domain="activities-concurrency.test.local",
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

    def test_update_and_score_launch_are_serialized(self):
        from activities.models import Activity
        from activities.services import ActivityService
        from agenda.models import Schedule, TimeSlot
        from base.exceptions import BusinessRuleViolationError
        from classes.models import Class, Enrollment
        from students.models import Student
        from teachers.models import Subject, Teacher

        actor = CustomUser.objects.create_user(
            email="activity-lock@tenant.test",
            password="Senha123",
            is_superuser=True,
        )
        class_obj = Class.objects.create(
            name="Turma lock de atividade",
            grade=Class.Grade.ELEMENTARY_1,
            education_stage=Class.EducationStage.ELEMENTARY_I,
            academic_year=2026,
            shift=Class.Shift.MORNING,
            created_by=actor,
            updated_by=actor,
        )
        teacher_user = CustomUser.objects.create_user(
            email="activity-lock-teacher@tenant.test",
            password="Senha123",
        )
        teacher = Teacher.objects.create(
            user=teacher_user,
            registration_number="ACTIVITY-LOCK",
            created_by=actor,
            updated_by=actor,
        )
        subject = Subject.objects.create(
            name="Disciplina concorrente",
            code="ACTL",
            created_by=actor,
            updated_by=actor,
        )
        teacher.subjects.add(subject)
        slot = TimeSlot.objects.create(
            slot_number=1,
            shift=TimeSlot.Shift.MORNING,
            start_time=dt.time(8),
            end_time=dt.time(9),
            created_by=actor,
            updated_by=actor,
        )
        Schedule.objects.create(
            class_obj=class_obj,
            teacher=teacher,
            subject=subject,
            time_slot=slot,
            day_of_week=Schedule.Day.MON,
            valid_from=dt.date(2026, 1, 1),
            created_by=actor,
            updated_by=actor,
        )
        student = Student.objects.create(
            first_name="Aluno",
            last_name="Concorrente",
            birth_date=dt.date(2015, 1, 1),
            enrollment_number="ACTIVITY-LOCK-STUDENT",
            created_by=actor,
            updated_by=actor,
        )
        Enrollment.objects.create(
            student=student,
            class_obj=class_obj,
            academic_year=class_obj.academic_year,
            enrollment_date=dt.date(2026, 1, 5),
            status=Enrollment.Status.ACTIVE,
            created_by=actor,
            updated_by=actor,
        )
        service = ActivityService(user=actor)
        activity = service.create_activity(
            {
                "class_obj_id": class_obj.pk,
                "subject_id": subject.pk,
                "teacher_id": teacher.pk,
                "title": "Atividade concorrente",
                "due_date": dt.date(2026, 2, 2),
                "max_score": 10,
            }
        )
        submission = activity.submissions.get(student=student)
        service.batch_record_scores(
            activity.pk,
            [
                {
                    "student_id": student.pk,
                    "score": 7,
                    "feedback": "",
                    "version": submission.version,
                }
            ],
        )
        activity.refresh_from_db()
        initial_version = activity.version
        barrier = Barrier(2)

        def run_in_connection(command):
            thread_connection = connections["default"]
            thread_connection.set_tenant(self.tenant)
            token = context.current_tenant.set(self.tenant.schema_name)
            try:
                thread_actor = CustomUser.objects.get(pk=actor.pk)
                thread_service = ActivityService(user=thread_actor)
                barrier.wait()
                try:
                    if command == "update":
                        thread_service.update_activity(
                            activity.pk,
                            {"title": "Atividade editada", "version": initial_version},
                        )
                    else:
                        thread_service.launch_scores(activity.pk, initial_version)
                    return f"{command}_completed"
                except BusinessRuleViolationError:
                    return f"{command}_blocked"
            finally:
                context.current_tenant.reset(token)
                thread_connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(run_in_connection, ("update", "launch")))

        activity.refresh_from_db()
        assert sorted(result.rsplit("_", 1)[1] for result in results) == [
            "blocked",
            "completed",
        ]
        if activity.score_status == Activity.ScoreStatus.LAUNCHED:
            assert activity.title == "Atividade concorrente"
        else:
            assert activity.score_status == Activity.ScoreStatus.DRAFT
            assert activity.title == "Atividade editada"
