"""Smoke test de escrita: POSTs de criação via Django test client."""
from django.template.context import BaseContext


def _patched_bctx_copy(self):
    cls = type(self)
    new = object.__new__(cls)
    for slot in (getattr(cls, "__slots__", ()) or ()):
        if hasattr(self, slot):
            try:
                setattr(new, slot, getattr(self, slot))
            except AttributeError:
                pass
    try:
        for k, v in vars(self).items():
            try:
                setattr(new, k, v)
            except AttributeError:
                pass
    except TypeError:
        pass
    return new


BaseContext.__copy__ = _patched_bctx_copy

import datetime as dt
import re

from django.test import Client
from django.urls import reverse

c = Client(raise_request_exception=False)
HOST = {"HTTP_HOST": "localhost"}


def err(resp):
    m = re.findall(r"Exception Value:.*?</", resp.content.decode("utf-8", "ignore"), re.S)
    return (m[0][:300] if m else resp.content[:300].decode("utf-8", "ignore"))


def show(label, resp):
    loc = resp.get("Location", "")
    extra = f" | {err(resp)}" if resp.status_code >= 400 else ""
    print(f"{label}: {resp.status_code} {('-> ' + loc) if loc else ''}{extra}")


c.post(reverse("login"), {"email": "admin@demo.com", "password": "Senha123", "remember_me": True}, **HOST)

from activities.models import Activity
from classes.models import Class
from students.models import Student
from teachers.models import Subject, Teacher

cls = Class.objects.get(name="6º A", academic_year=2026)
teacher = Teacher.objects.get()
subject = Subject.objects.get(code="MAT")
stu2 = Student.objects.get(enrollment_number="2026002")
act = Activity.objects.first()

# 1. Criar nova turma (ModelForm com dropdown de professor)
show(
    "POST class_create",
    c.post(
        reverse("class_create"),
        {
            "name": "6º B",
            "grade": "6º ano",
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
        {"day_of_week": "TUE", "slot_number": 2, "start_time": "09:10", "end_time": "10:00"},
        **HOST,
    ),
)

# 3. Matricular 2º aluno na turma
show("POST class_enroll", c.post(reverse("class_enroll", kwargs={"class_id": cls.pk}), {"student_id": str(stu2.pk)}, **HOST))

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
show(
    "POST activity_record_score",
    c.post(
        reverse("activity_record_score", kwargs={"pk": act.pk}),
        {"student": str(stu2.pk), "score": "8.50", "feedback": "Bom."},
        **HOST,
    ),
)