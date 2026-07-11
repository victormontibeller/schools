"""Testes das views de secretaria."""

import pytest
from django.urls import reverse


@pytest.fixture()
def student(db, user):
    from students.services import StudentService

    return StudentService(user=user).create_student(
        {
            "first_name": "Ana",
            "last_name": "Lima",
            "birth_date": "2010-05-15",
            "enrollment_number": "VW-TEST-001",
            "gender": "F",
            "blood_type": "O+",
            "nationality": "Brasileira",
            "cpf": "390.533.447-05",
            "rg_number": "1234567",
            "rg_issuer": "SSP",
            "rg_state": "SP",
            "phone_mobile": "11999990000",
            "email": "ana.lima@example.com",
        }
    )


@pytest.fixture()
def class_obj(db, user):
    from classes.services import ClassService

    return ClassService(user=user).create_class(
        {
            "name": "Turma View Test",
            "grade": "3o Ano",
            "academic_year": 2025,
            "shift": "MORNING",
            "max_students": 30,
        }
    )


@pytest.mark.django_db
class TestSecretaryDashboard:
    def test_dashboard_returns_200(self, client, user):
        client.force_login(user)
        url = reverse("secretary_dashboard")
        response = client.get(url)
        assert response.status_code == 200

    def test_dashboard_requires_login(self, client):
        url = reverse("secretary_dashboard")
        response = client.get(url)
        assert response.status_code == 302

    def test_dashboard_tabs_have_content(self, client, user, student, class_obj):
        from enrollments.services import EnrollmentApplicationService

        svc = EnrollmentApplicationService(user=user)
        svc.create_application(
            {
                "student_id": student.pk,
                "class_obj_id": class_obj.pk,
                "academic_year": 2025,
            }
        )

        client.force_login(user)
        url = reverse("secretary_dashboard") + "?tab=pre-matricula"
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert student.first_name in content


@pytest.mark.django_db
class TestApplicationCreate:
    def test_create_form_returns_200(self, client, user):
        client.force_login(user)
        url = reverse("application_create")
        response = client.get(url)
        assert response.status_code == 200

    def test_create_application_post(self, client, user, student, class_obj):
        client.force_login(user)
        url = reverse("application_create")
        response = client.post(
            url,
            {
                "student": student.pk,
                "class_obj": class_obj.pk,
                "academic_year": 2025,
                "application_type": "NEW",
                "priority": 0,
            },
        )
        assert response.status_code == 302
        assert response.url == reverse("secretary_dashboard")


@pytest.mark.django_db
class TestApplicationDetail:
    def test_detail_returns_200(self, client, user, student, class_obj):
        from enrollments.services import EnrollmentApplicationService

        svc = EnrollmentApplicationService(user=user)
        app = svc.create_application(
            {
                "student_id": student.pk,
                "class_obj_id": class_obj.pk,
                "academic_year": 2025,
            }
        )

        client.force_login(user)
        url = reverse("application_detail", kwargs={"pk": app.pk})
        response = client.get(url)
        assert response.status_code == 200
        assert app.application_number in response.content.decode()


@pytest.mark.django_db
class TestApplicationReview:
    def test_approve_action(self, client, user, student, class_obj):
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

        client.force_login(user)
        url = reverse("application_review", kwargs={"pk": app.pk})
        response = client.post(url, {"action": "approve", "reason": ""})
        assert response.status_code == 302

        app.refresh_from_db()
        assert app.status == EnrollmentApplication.Status.APPROVED

    def test_reject_action(self, client, user, student, class_obj):
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

        client.force_login(user)
        url = reverse("application_review", kwargs={"pk": app.pk})
        response = client.post(url, {"action": "reject", "reason": "Falta documentacao"})
        assert response.status_code == 302

        app.refresh_from_db()
        assert app.status == EnrollmentApplication.Status.REJECTED


@pytest.mark.django_db
class TestCompleteEnrollment:
    def test_complete_enrollment_post(self, client, user, student, class_obj):
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

        client.force_login(user)
        url = reverse("application_complete_enrollment", kwargs={"pk": app.pk})
        response = client.post(url)
        assert response.status_code == 302

        app.refresh_from_db()
        assert app.status == EnrollmentApplication.Status.ENROLLED


@pytest.mark.django_db
class TestBulkReenrollView:
    def test_bulk_reenroll_form_returns_200(self, client, user):
        client.force_login(user)
        url = reverse("bulk_reenroll")
        response = client.get(url)
        assert response.status_code == 200

    def test_bulk_reenroll_post(self, client, user, student, class_obj):
        from classes.services import ClassService

        ClassService(user=user).enroll_student(class_obj.pk, student.pk)

        client.force_login(user)
        url = reverse("bulk_reenroll")
        response = client.post(url, {"from_class": str(class_obj.pk), "to_academic_year": 2026})
        assert response.status_code == 302


@pytest.mark.django_db
class TestDocumentViews:
    def test_document_add_for_application(self, client, user, student, class_obj):
        from enrollments.services import EnrollmentApplicationService

        svc = EnrollmentApplicationService(user=user)
        app = svc.create_application(
            {
                "student_id": student.pk,
                "class_obj_id": class_obj.pk,
                "academic_year": 2025,
            }
        )

        client.force_login(user)
        url = reverse("document_add_for_application", kwargs={"application_id": app.pk})
        response = client.post(
            url,
            {
                "student": student.pk,
                "application": app.pk,
                "document_type": "BIRTH_CERT",
                "description": "Certidao original",
            },
        )
        assert response.status_code == 302

    def test_document_verify_post(self, client, user, student):
        from enrollments.models import StudentDocument
        from enrollments.services import StudentDocumentService

        svc = StudentDocumentService(user=user)
        doc = svc.add_document(
            {
                "student_id": student.pk,
                "document_type": StudentDocument.DocumentType.ID,
            }
        )

        client.force_login(user)
        url = reverse("document_verify", kwargs={"pk": doc.pk})
        response = client.post(url)
        assert response.status_code in (204, 302)

        doc.refresh_from_db()
        assert doc.status == StudentDocument.Status.VERIFIED

    def test_document_reject_post(self, client, user, student):
        from enrollments.models import StudentDocument
        from enrollments.services import StudentDocumentService

        svc = StudentDocumentService(user=user)
        doc = svc.add_document(
            {
                "student_id": student.pk,
                "document_type": StudentDocument.DocumentType.CPF,
            }
        )

        client.force_login(user)
        url = reverse("document_reject", kwargs={"pk": doc.pk})
        response = client.post(url, {"reason": "Documento ilegivel"})
        assert response.status_code in (204, 302)

        doc.refresh_from_db()
        assert doc.status == StudentDocument.Status.REJECTED

    def test_document_get_redirects(self, client, user, student):
        from enrollments.models import StudentDocument
        from enrollments.services import StudentDocumentService

        svc = StudentDocumentService(user=user)
        doc = svc.add_document(
            {
                "student_id": student.pk,
                "document_type": StudentDocument.DocumentType.PHOTO,
            }
        )

        client.force_login(user)
        url = reverse("document_verify", kwargs={"pk": doc.pk})
        response = client.get(url)
        assert response.status_code in (204, 302)


@pytest.mark.django_db
class TestApplicationCancel:
    def test_cancel_application_post(self, client, user, student, class_obj):
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

        client.force_login(user)
        url = reverse("application_cancel", kwargs={"pk": app.pk})
        response = client.post(url, {"reason": "Desistencia do aluno"})
        assert response.status_code == 302

        app.refresh_from_db()
        assert app.status == EnrollmentApplication.Status.CANCELLED
        assert app.cancellation_reason == "Desistencia do aluno"
        assert app.rejection_reason == ""
