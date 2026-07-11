"""Testes do EnrollmentApplicationService."""

import pytest

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError


@pytest.fixture()
def student(db, user):
    from students.services import StudentService

    return StudentService(user=user).create_student(
        {
            "first_name": "Lucas",
            "last_name": "Silva",
            "birth_date": "2010-03-10",
            "enrollment_number": "ENR-TEST-001",
            "gender": "M",
            "blood_type": "O+",
            "nationality": "Brasileira",
            "cpf": "390.533.447-05",
            "rg_number": "1234567",
            "rg_issuer": "SSP",
            "rg_state": "SP",
            "phone_mobile": "11999990000",
            "email": "lucas@example.com",
        }
    )


@pytest.fixture()
def class_obj(db, user):
    from classes.services import ClassService

    return ClassService(user=user).create_class(
        {
            "name": "Turma A",
            "grade": "5o Ano",
            "academic_year": 2025,
            "shift": "MORNING",
            "max_students": 5,
        }
    )


@pytest.fixture()
def class_obj_full(db, user):
    from classes.services import ClassService

    return ClassService(user=user).create_class(
        {
            "name": "Turma Cheia",
            "grade": "5o Ano",
            "academic_year": 2025,
            "shift": "AFTERNOON",
            "max_students": 1,
        }
    )


@pytest.mark.django_db
class TestCreateApplication:
    def test_success(self, user, student, class_obj):
        from enrollments.services import EnrollmentApplicationService

        svc = EnrollmentApplicationService(user=user)
        app = svc.create_application(
            {
                "student_id": student.pk,
                "class_obj_id": class_obj.pk,
                "academic_year": 2025,
            }
        )
        assert app.pk is not None
        assert app.status == "PRE_ENROLLMENT"
        assert app.application_number.startswith("MAT-")

    def test_missing_required_fields(self, user):
        from enrollments.services import EnrollmentApplicationService

        svc = EnrollmentApplicationService(user=user)
        with pytest.raises(ValidationError):
            svc.create_application({"student_id": "some-id"})

    def test_student_not_found(self, user, class_obj):
        from enrollments.services import EnrollmentApplicationService

        svc = EnrollmentApplicationService(user=user)
        with pytest.raises(ObjectNotFoundError):
            svc.create_application(
                {
                    "student_id": "00000000-0000-0000-0000-000000000000",
                    "class_obj_id": class_obj.pk,
                    "academic_year": 2025,
                }
            )

    def test_class_not_found(self, user, student):
        from enrollments.services import EnrollmentApplicationService

        svc = EnrollmentApplicationService(user=user)
        with pytest.raises(ObjectNotFoundError):
            svc.create_application(
                {
                    "student_id": student.pk,
                    "class_obj_id": "00000000-0000-0000-0000-000000000000",
                    "academic_year": 2025,
                }
            )

    def test_duplicate_active_application(self, user, student, class_obj):
        from enrollments.services import EnrollmentApplicationService

        svc = EnrollmentApplicationService(user=user)
        svc.create_application(
            {
                "student_id": student.pk,
                "class_obj_id": class_obj.pk,
                "academic_year": 2025,
            }
        )
        with pytest.raises(BusinessRuleViolationError):
            svc.create_application(
                {
                    "student_id": student.pk,
                    "class_obj_id": class_obj.pk,
                    "academic_year": 2025,
                }
            )

    def test_no_vacancies(self, user, student, class_obj_full):
        from enrollments.services import EnrollmentApplicationService

        svc = EnrollmentApplicationService(user=user)
        svc.create_application(
            {
                "student_id": student.pk,
                "class_obj_id": class_obj_full.pk,
                "academic_year": 2025,
            }
        )
        svc2 = EnrollmentApplicationService(user=user)
        with pytest.raises(BusinessRuleViolationError):
            student2 = _create_student(user, "ENR-TEST-FULL", "Joao", "Teste")
            svc2.create_application(
                {
                    "student_id": student2.pk,
                    "class_obj_id": class_obj_full.pk,
                    "academic_year": 2025,
                }
            )


@pytest.mark.django_db
class TestApplicationLifecycle:
    def test_submit_for_review(self, user, student, class_obj):
        from enrollments.models import EnrollmentApplication
        from enrollments.services import EnrollmentApplicationService

        svc = EnrollmentApplicationService(user=user)
        app = svc.create_application(
            {
                "student_id": student.pk,
                "class_obj_id": class_obj.pk,
                "academic_year": 2025,
            }
        )
        app = svc.submit_for_review(app.pk)
        assert app.status == EnrollmentApplication.Status.UNDER_REVIEW

    def test_submit_wrong_status(self, user, student, class_obj):
        from enrollments.services import EnrollmentApplicationService

        svc = EnrollmentApplicationService(user=user)
        app = svc.create_application(
            {
                "student_id": student.pk,
                "class_obj_id": class_obj.pk,
                "academic_year": 2025,
            }
        )
        svc.submit_for_review(app.pk)
        with pytest.raises(BusinessRuleViolationError):
            svc.submit_for_review(app.pk)

    def test_approve_application(self, user, student, class_obj):
        from enrollments.models import EnrollmentApplication
        from enrollments.services import EnrollmentApplicationService

        svc = EnrollmentApplicationService(user=user)
        app = svc.create_application(
            {
                "student_id": student.pk,
                "class_obj_id": class_obj.pk,
                "academic_year": 2025,
            }
        )
        svc.submit_for_review(app.pk)
        app = svc.approve_application(app.pk)
        assert app.status == EnrollmentApplication.Status.APPROVED
        assert app.reviewed_by == user
        assert app.reviewed_at is not None

    def test_reject_application(self, user, student, class_obj):
        from enrollments.models import EnrollmentApplication
        from enrollments.services import EnrollmentApplicationService

        svc = EnrollmentApplicationService(user=user)
        app = svc.create_application(
            {
                "student_id": student.pk,
                "class_obj_id": class_obj.pk,
                "academic_year": 2025,
            }
        )
        app = svc.reject_application(app.pk, reason="Documentacao incompleta")
        assert app.status == EnrollmentApplication.Status.REJECTED
        assert app.rejection_reason == "Documentacao incompleta"

    def test_complete_enrollment(self, user, student, class_obj):
        from enrollments.models import EnrollmentApplication
        from enrollments.services import EnrollmentApplicationService

        svc = EnrollmentApplicationService(user=user)
        app = svc.create_application(
            {
                "student_id": student.pk,
                "class_obj_id": class_obj.pk,
                "academic_year": 2025,
            }
        )
        svc.submit_for_review(app.pk)
        svc.approve_application(app.pk)
        app = svc.complete_enrollment(app.pk)
        assert app.status == EnrollmentApplication.Status.ENROLLED
        assert app.enrollment is not None
        assert app.enrollment.status == "ACTIVE"

    def test_complete_enrollment_wrong_status(self, user, student, class_obj):
        from enrollments.services import EnrollmentApplicationService

        svc = EnrollmentApplicationService(user=user)
        app = svc.create_application(
            {
                "student_id": student.pk,
                "class_obj_id": class_obj.pk,
                "academic_year": 2025,
            }
        )
        with pytest.raises(BusinessRuleViolationError):
            svc.complete_enrollment(app.pk)

    def test_request_correction(self, user, student, class_obj):
        from enrollments.models import EnrollmentApplication
        from enrollments.services import EnrollmentApplicationService

        svc = EnrollmentApplicationService(user=user)
        app = svc.create_application(
            {
                "student_id": student.pk,
                "class_obj_id": class_obj.pk,
                "academic_year": 2025,
            }
        )
        svc.submit_for_review(app.pk)
        app = svc.request_correction(app.pk, notes="CPF ilegivel")
        assert app.status == EnrollmentApplication.Status.PRE_ENROLLMENT
        assert app.correction_notes == "CPF ilegivel"

    def test_cancel_application(self, user, student, class_obj):
        from enrollments.models import EnrollmentApplication
        from enrollments.services import EnrollmentApplicationService

        svc = EnrollmentApplicationService(user=user)
        app = svc.create_application(
            {
                "student_id": student.pk,
                "class_obj_id": class_obj.pk,
                "academic_year": 2025,
            }
        )
        app = svc.cancel_application(app.pk, reason="Desistencia")
        assert app.status == EnrollmentApplication.Status.CANCELLED
        assert app.cancellation_reason == "Desistencia"
        assert app.rejection_reason == ""


@pytest.mark.django_db
class TestBulkReenroll:
    def test_success(self, user, student, class_obj):
        from classes.services import ClassService
        from enrollments.models import EnrollmentApplication
        from enrollments.services import EnrollmentApplicationService

        svc_class = ClassService(user=user)
        svc_class.enroll_student(class_obj.pk, student.pk)

        svc = EnrollmentApplicationService(user=user)
        count = svc.bulk_reenroll(from_class_id=class_obj.pk, to_academic_year=2026)
        assert count == 1
        assert (
            EnrollmentApplication.objects.filter(
                academic_year=2026,
                application_type=EnrollmentApplication.ApplicationType.REENROLL,
            ).count()
            == 1
        )


@pytest.mark.django_db
class TestStudentDocumentService:
    def test_add_document(self, user, student):
        from enrollments.models import StudentDocument
        from enrollments.services import StudentDocumentService

        svc = StudentDocumentService(user=user)
        doc = svc.add_document(
            {
                "student_id": student.pk,
                "document_type": StudentDocument.DocumentType.BIRTH_CERTIFICATE,
                "description": "Certidao original",
            }
        )
        assert doc.pk is not None
        assert doc.status == StudentDocument.Status.PENDING

    def test_verify_document(self, user, student):
        from enrollments.models import StudentDocument
        from enrollments.services import StudentDocumentService

        svc = StudentDocumentService(user=user)
        doc = svc.add_document(
            {
                "student_id": student.pk,
                "document_type": StudentDocument.DocumentType.ID,
            }
        )
        doc = svc.verify_document(doc.pk)
        assert doc.status == StudentDocument.Status.VERIFIED
        assert doc.verified_by == user

    def test_reject_document(self, user, student):
        from enrollments.models import StudentDocument
        from enrollments.services import StudentDocumentService

        svc = StudentDocumentService(user=user)
        doc = svc.add_document(
            {
                "student_id": student.pk,
                "document_type": StudentDocument.DocumentType.CPF,
            }
        )
        doc = svc.reject_document(doc.pk, reason="Documento ilegivel")
        assert doc.status == StudentDocument.Status.REJECTED


def _create_student(user, enrollment, first_name, last_name):
    from students.services import StudentService

    return StudentService(user=user).create_student(
        {
            "first_name": first_name,
            "last_name": last_name,
            "birth_date": "2010-01-01",
            "enrollment_number": enrollment,
            "gender": "M",
            "blood_type": "A+",
            "nationality": "Brasileira",
            "cpf": "529.982.247-25",
            "rg_number": "7654321",
            "rg_issuer": "SSP",
            "rg_state": "SP",
            "phone_mobile": "11999990001",
            "email": f"{enrollment.lower()}@example.com",
        }
    )
