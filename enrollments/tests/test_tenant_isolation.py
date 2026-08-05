"""Concorrência e isolamento do workflow em PostgreSQL com django-tenants."""

import datetime as dt
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

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


def _records(email: str, suffix: str, *, capacity: int = 2):
    from classes.models import Class
    from classes.services import ClassService
    from core.models import Role
    from students.models import Student

    role, _ = Role.objects.get_or_create(name=Role.Name.ADMIN)
    actor = CustomUser.objects.create_user(
        email=email,
        password="Senha123",
        role=role,
        is_superuser=True,
    )
    class_obj = ClassService(user=actor).create_class(
        {
            "name": f"5A {suffix}",
            "grade": Class.Grade.ELEMENTARY_5,
            "education_stage": Class.EducationStage.ELEMENTARY_I,
            "academic_year": 2026,
            "max_students": capacity,
        }
    )
    students = [
        Student.objects.create(
            first_name="Aluno",
            last_name=str(index),
            birth_date=dt.date(2014, 1, index),
            enrollment_number=f"ALU-{suffix}-{index}",
            created_by=actor,
            updated_by=actor,
        )
        for index in (1, 2)
    ]
    return actor, class_obj, students


def _create_submitted(actor, class_obj, student):
    from enrollments.models import EnrollmentApplication
    from enrollments.services import EnrollmentApplicationService

    service = EnrollmentApplicationService(user=actor)
    application = service.create_application(
        {
            "student_id": student.pk,
            "target_class_id": class_obj.pk,
            "application_type": EnrollmentApplication.ApplicationType.NEW,
        }
    )
    return service.submit_application(application.pk, expected_version=application.version)


@_requires_pg
class TestEnrollmentConcurrency(TransactionTestCase):
    """Exercita locks reais usando conexões PostgreSQL independentes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        connection.set_schema_to_public()
        cls.tenant = School(
            schema_name="enrollments_concurrency",
            name="Matrículas Concorrentes",
        )
        cls.tenant.save(verbosity=0)
        cls.domain = Domain.objects.create(
            domain="enrollments-concurrency.test.local",
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

    def test_last_seat_is_reserved_once(self):
        from enrollments.models import EnrollmentApplication
        from enrollments.services import EnrollmentApplicationService

        actor, class_obj, students = _records("concurrency@enrollments.test", "CONC", capacity=1)
        applications = [_create_submitted(actor, class_obj, student) for student in students]

        def approve(application):
            thread_connection = connections["default"]
            thread_connection.set_tenant(self.tenant)
            token = context.current_tenant.set(self.tenant.schema_name)
            try:
                thread_actor = CustomUser.objects.get(pk=actor.pk)
                result = EnrollmentApplicationService(user=thread_actor).approve_application(
                    application.pk, expected_version=application.version
                )
                return result.status
            finally:
                context.current_tenant.reset(token)
                thread_connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(approve, applications))

        assert sorted(statuses) == sorted(
            [EnrollmentApplication.Status.APPROVED, EnrollmentApplication.Status.WAITLISTED]
        )

    def test_concurrent_document_requirement_duplicate_is_translated(self):
        from base.exceptions import ValidationError
        from enrollments.models import DocumentRequirement, EnrollmentApplication
        from enrollments.services import StudentDocumentService

        actor, _class_obj, _students = _records("requirements@enrollments.test", "REQUIREMENTS")
        data = {
            "application_type": EnrollmentApplication.ApplicationType.NEW,
            "code": "concurrent-proof",
            "label": "Comprovante concorrente",
        }

        def create_in_connection():
            thread_connection = connections["default"]
            thread_connection.set_tenant(self.tenant)
            token = context.current_tenant.set(self.tenant.schema_name)
            try:
                thread_actor = CustomUser.objects.get(pk=actor.pk)
                try:
                    StudentDocumentService(user=thread_actor).create_requirement(data)
                    return "created"
                except ValidationError:
                    return "duplicate"
            finally:
                context.current_tenant.reset(token)
                thread_connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _index: create_in_connection(), range(2)))

        assert sorted(results) == ["created", "duplicate"]
        assert DocumentRequirement.objects.filter(code="concurrent-proof").count() == 1

    def test_concurrent_finalization_creates_one_academic_enrollment(self):
        from base.exceptions import BusinessRuleViolationError
        from classes.models import Enrollment
        from enrollments.models import EnrollmentApplication
        from enrollments.services import EnrollmentApplicationService

        actor, class_obj, students = _records("finalize@enrollments.test", "FINALIZE", capacity=2)
        application = _create_submitted(actor, class_obj, students[0])
        application = EnrollmentApplicationService(user=actor).approve_application(
            application.pk, expected_version=application.version
        )

        def finalize_in_connection():
            thread_connection = connections["default"]
            thread_connection.set_tenant(self.tenant)
            token = context.current_tenant.set(self.tenant.schema_name)
            try:
                thread_actor = CustomUser.objects.get(pk=actor.pk)
                try:
                    EnrollmentApplicationService(user=thread_actor).finalize_application(
                        application.pk,
                        expected_version=application.version,
                    )
                    return "enrolled"
                except BusinessRuleViolationError:
                    return "conflict"
            finally:
                context.current_tenant.reset(token)
                thread_connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _index: finalize_in_connection(), range(2)))

        application.refresh_from_db()
        assert sorted(results) == ["conflict", "enrolled"]
        assert application.status == EnrollmentApplication.Status.ENROLLED
        assert (
            Enrollment.objects.filter(student=students[0], status=Enrollment.Status.ACTIVE).count()
            == 1
        )

    def test_duplicate_reenrollment_batch_is_rejected_without_partial_write(self):
        from base.exceptions import ValidationError
        from classes.models import Class
        from classes.services import ClassService
        from enrollments.models import EnrollmentApplication
        from enrollments.services import EnrollmentApplicationService, ReenrollmentService

        actor, class_obj, students = _records("batch@enrollments.test", "BATCH")
        original = _create_submitted(actor, class_obj, students[0])
        original = EnrollmentApplicationService(user=actor).approve_application(
            original.pk, expected_version=original.version
        )
        original = EnrollmentApplicationService(user=actor).finalize_application(
            original.pk, expected_version=original.version
        )
        target = ClassService(user=actor).create_class(
            {
                "name": "6A BATCH",
                "grade": Class.Grade.ELEMENTARY_6,
                "education_stage": Class.EducationStage.ELEMENTARY_II,
                "academic_year": 2027,
            }
        )
        mapping = {
            "source_enrollment_id": original.result_enrollment_id,
            "target_class_id": target.pk,
            "expected_version": original.result_enrollment.version,
        }

        with pytest.raises(ValidationError):
            ReenrollmentService(user=actor).confirm_batch([mapping, mapping])

        assert not EnrollmentApplication.objects.filter(
            application_type=EnrollmentApplication.ApplicationType.REENROLLMENT
        ).exists()

    def test_channel_result_and_webhook_keep_delivery_status_monotonic(self):
        from django.utils import timezone

        from notifications.channels import ChannelResult
        from notifications.delivery_services import MessageDeliveryService
        from notifications.models import MessageLog

        actor, _class_obj, _students = _records("message-race@enrollments.test", "MESSAGE-RACE")
        message_log = MessageDeliveryService(user=None).create_pending(
            recipient=actor,
            channel=MessageLog.Channel.EMAIL,
            recipient_address=actor.email,
        )
        provider_message_id = "provider-message-race"
        occurred_at = timezone.now()
        barrier = Barrier(2)

        def record_transport_failure():
            thread_connection = connections["default"]
            thread_connection.set_tenant(self.tenant)
            token = context.current_tenant.set(self.tenant.schema_name)
            try:
                barrier.wait()
                MessageDeliveryService(user=None).record_channel_result(
                    message_log.pk,
                    ChannelResult(
                        success=False,
                        channel=MessageLog.Channel.EMAIL,
                        recipient_address="",
                        provider_message_id=provider_message_id,
                        error_message="transport_failed",
                        retryable=False,
                    ),
                )
            finally:
                context.current_tenant.reset(token)
                thread_connection.close()

        def record_delivery_webhook():
            thread_connection = connections["default"]
            thread_connection.set_tenant(self.tenant)
            token = context.current_tenant.set(self.tenant.schema_name)
            try:
                barrier.wait()
                MessageDeliveryService(user=None).process_resend_event(
                    external_event_id="evt-message-race",
                    event_type="email.delivered",
                    provider_message_id=provider_message_id,
                    message_log_id=str(message_log.pk),
                    occurred_at=occurred_at,
                )
            finally:
                context.current_tenant.reset(token)
                thread_connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(record_transport_failure),
                executor.submit(record_delivery_webhook),
            ]
            for future in futures:
                future.result()

        message_log.refresh_from_db()
        assert message_log.status == MessageLog.Status.DELIVERED
        assert message_log.delivered_at == occurred_at
        assert message_log.last_event == "email.delivered"


@_requires_pg
class TestEnrollmentTenantIsolation(TenantTestCase):
    """Prova reserva serializada e sequência anual independente por schema."""

    @classmethod
    def get_test_schema_name(cls) -> str:
        return "enrollments_a"

    @classmethod
    def get_test_tenant_domain(cls) -> str:
        return "enrollments-a.test.local"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        connection.set_schema_to_public()
        second = School(schema_name="enrollments_b", name="Escola Matrículas B")
        cls.setup_tenant(second)
        second.save(verbosity=0)
        cls.tenant_b = second
        Domain.objects.create(domain="enrollments-b.test.local", tenant=second, is_primary=True)
        connection.set_tenant(cls.tenant)

    @classmethod
    def tearDownClass(cls):
        connection.set_schema_to_public()
        cls.tenant_b.delete(force_drop=True)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self._ctx_token = context.current_tenant.set(self.tenant.schema_name)

    def tearDown(self):
        context.current_tenant.reset(self._ctx_token)
        super().tearDown()

    def test_protocol_and_records_are_tenant_scoped(self):
        actor_a, class_a, students_a = _records("sequence-a@enrollments.test", "SEQ-A")
        application_a = _create_submitted(actor_a, class_a, students_a[0])

        connection.set_tenant(self.tenant_b)
        token = context.current_tenant.set(self.tenant_b.schema_name)
        try:
            actor_b, class_b, students_b = _records("sequence-b@enrollments.test", "SEQ-B")
            application_b = _create_submitted(actor_b, class_b, students_b[0])
            from enrollments.models import EnrollmentApplication

            assert EnrollmentApplication.objects.count() == 1
        finally:
            context.current_tenant.reset(token)
            connection.set_tenant(self.tenant)

        assert application_a.application_number == "MAT-2026-000001"
        assert application_b.application_number == "MAT-2026-000001"
        from enrollments.models import EnrollmentApplication

        assert EnrollmentApplication.objects.count() == 1
