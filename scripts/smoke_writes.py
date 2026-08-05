"""Smoke test de escrita: POSTs de criação via Django test client."""

import datetime as dt
import re

from django.conf import settings
from django.test import Client
from django.urls import reverse

c = Client(raise_request_exception=False)
HOST = {"HTTP_HOST": "localhost"}


def err(resp):
    m = re.findall(r"Exception Value:.*?</", resp.content.decode("utf-8", "ignore"), re.S)
    return m[0][:300] if m else resp.content[:300].decode("utf-8", "ignore")


def show(label, resp):
    loc = resp.get("Location", "")
    extra = f" | {err(resp)}" if resp.status_code >= 400 else ""
    print(f"{label}: {resp.status_code} {('-> ' + loc) if loc else ''}{extra}")


c.post(
    reverse("login"),
    {
        "email": "admin@demo.com",
        "password": settings.DEV_DEMO_ADMIN_PASSWORD,
        "remember_me": True,
    },
    **HOST,
)

from activities.models import Activity, ActivitySubmission
from agenda.models import TimeSlot
from classes.models import Class
from enrollments.models import EnrollmentApplication
from enrollments.services import EnrollmentApplicationService
from students.models import Student
from teachers.models import Subject, Teacher

cls = Class.objects.get(name="6º A", academic_year=2026)
teacher = Teacher.objects.get()
subject = Subject.objects.get(code="MAT")
stu2, _ = Student.objects.get_or_create(
    enrollment_number="SMOKE-MATRICULA",
    defaults={
        "first_name": "Aluno",
        "last_name": "Smoke",
        "birth_date": dt.date(2014, 1, 1),
    },
)

# 1. Criar nova turma (ModelForm com dropdown de professor)
show(
    "POST class_create",
    c.post(
        reverse("class_create"),
        {
            "name": "6º B",
            "grade": Class.Grade.ELEMENTARY_6,
            "education_stage": Class.EducationStage.ELEMENTARY_II,
            "shift": Class.Shift.AFTERNOON,
            "academic_year": 2026,
            "max_students": 28,
            "class_teacher": str(teacher.pk),
        },
        **HOST,
    ),
)
print("Turmas agora:", Class.objects.count())

# 2. Criar horário
show(
    "POST time_slot_create",
    c.post(
        reverse("time_slot_create"),
        {
            "slot_number": 2,
            "shift": TimeSlot.Shift.MORNING,
            "start_time": "09:10",
            "end_time": "10:00",
        },
        **HOST,
    ),
)

# 3. Abrir solicitação (todo vínculo nasce pelo workflow da Secretaria)
show(
    "POST enrollment_application_create",
    c.post(
        reverse("enrollment_application_create"),
        {
            "student_id": str(stu2.pk),
            "target_class_id": str(cls.pk),
            "application_type": "NEW",
            "priority": 0,
            "notes": "",
        },
        **HOST,
    ),
)
application = EnrollmentApplication.objects.get(
    student=stu2,
    target_class=cls,
    status=EnrollmentApplication.Status.PRE_ENROLLMENT,
)
enrollment_service = EnrollmentApplicationService(user=application.created_by)
application = enrollment_service.submit_application(
    application.pk, expected_version=application.version
)
application = enrollment_service.approve_application(
    application.pk, expected_version=application.version
)
enrollment_service.finalize_application(application.pk, expected_version=application.version)

# 4. Criar atividade
show(
    "POST activity_create",
    c.post(
        reverse("activity_create"),
        {
            "class_obj": str(cls.pk),
            "subject": str(subject.pk),
            "teacher": str(teacher.pk),
            "title": "Trabalho de Conjuntos",
            "description": "Listas 1 e 2.",
            "type": Activity.Type.PROJECT,
            "due_date": (dt.date.today() + dt.timedelta(days=5)).isoformat(),
            "max_score": "10.00",
            "weight": "1.00",
        },
        **HOST,
    ),
)
print("Atividades agora:", Activity.objects.count())

# 5. Lançar nota
act = Activity.objects.order_by("-created_at").first()
submission = ActivitySubmission.objects.get(activity=act, student=stu2)
score_prefix = f"submission-{submission.pk}"
show(
    "POST activity_record_score",
    c.post(
        reverse("activity_record_score", kwargs={"pk": act.pk}),
        {
            f"{score_prefix}-score": "8.50",
            f"{score_prefix}-feedback": "Bom.",
            f"{score_prefix}-submission_id": str(submission.pk),
            f"{score_prefix}-version": str(submission.version),
        },
        **HOST,
    ),
)
