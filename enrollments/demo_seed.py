"""Seed DEMO do workflow canônico de matrículas."""

from base.exceptions import PermissionDeniedError
from classes.contracts import Enrollment
from enrollments.models import EnrollmentApplication
from enrollments.services import EnrollmentApplicationService


def ensure_demo_enrollment(user, student, class_obj):
    """Garante um vínculo DEMO passando por solicitação, aprovação e efetivação."""
    if user is None:
        raise PermissionDeniedError("O seed de matrícula exige um ator administrativo.")
    existing = Enrollment.objects.filter(
        student=student,
        academic_year=class_obj.academic_year,
        status=Enrollment.Status.ACTIVE,
    ).first()
    if existing:
        return existing

    service = EnrollmentApplicationService(user=user)
    application = service.create_application(
        {
            "student_id": student.pk,
            "target_class_id": class_obj.pk,
            "application_type": EnrollmentApplication.ApplicationType.NEW,
        }
    )
    application = service.submit_application(application.pk, expected_version=application.version)
    application = service.approve_application(application.pk, expected_version=application.version)
    application = service.finalize_application(application.pk, expected_version=application.version)
    return application.result_enrollment
