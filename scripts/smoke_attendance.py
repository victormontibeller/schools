"""Smoke test do módulo de frequência."""
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

import re

from django.test import Client
from django.urls import reverse

c = Client(raise_request_exception=False)
H = {"HTTP_HOST": "localhost"}


def err(resp):
    m = re.findall(r"Exception Value:.*?</", resp.content.decode("utf-8", "ignore"), re.S)
    return (m[0][:300] if m else resp.content[:300].decode("utf-8", "ignore"))


def show(label, resp):
    extra = f" | {err(resp)}" if resp.status_code >= 400 else ""
    print(f"{label}: {resp.status_code}{extra}")


c.post(reverse("login"), {"email": "admin@demo.com", "password": "Senha123", "remember_me": True}, **H)

from attendance.models import AttendanceEntry, AttendanceRecord, AttendanceJustification
from classes.models import Class
from students.models import Student

show("records_list", c.get(reverse("attendance_records_list"), **H))
show("record_create GET", c.get(reverse("attendance_record_create"), **H))

rec = AttendanceRecord.objects.first()
show("record_fill GET", c.get(reverse("attendance_record_fill", kwargs={"record_id": rec.pk}), **H))

# Bulk POST via HTMX-friendly data: um presente, um ausente.
stu_ids = list(AttendanceEntry.objects.filter(record=rec).values_list("student_id", flat=True))
data = {f"status_{s}": "PRESENT" for s in stu_ids}
if len(stu_ids) >= 2:
    data[f"status_{stu_ids[1]}"] = "ABSENT"
show("record_fill POST", c.post(reverse("attendance_record_fill", kwargs={"record_id": rec.pk}), data, **H))

cls = Class.objects.first()
show("class_summary", c.get(reverse("class_attendance_summary", kwargs={"class_id": cls.pk}), **H))
stu = Student.objects.first()
show("student_attendance", c.get(reverse("student_attendance", kwargs={"student_id": stu.pk}), **H))
show("at_risk", c.get(reverse("students_at_risk"), **H))
show("at_risk (turma)", c.get(reverse("students_at_risk") + f"?class_obj={cls.pk}", **H))
show("justifications_list", c.get(reverse("justifications_list"), **H))
show("justification_create GET", c.get(reverse("justification_create"), **H))

j = AttendanceJustification.objects.first()
show("justification_approve", c.post(reverse("justification_approve", kwargs={"pk": j.pk}), **H))