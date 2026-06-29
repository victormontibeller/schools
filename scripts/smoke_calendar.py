"""Smoke test do calendário."""
# Workaround Django 5.1 + Python 3.14 (mesmo patch do conftest.py).
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
H = {"HTTP_HOST": "localhost"}


def err(resp):
    m = re.findall(r"Exception Value:.*?</", resp.content.decode("utf-8", "ignore"), re.S)
    return (m[0][:300] if m else resp.content[:300].decode("utf-8", "ignore"))


def show(label, resp):
    extra = f" | {err(resp)}" if resp.status_code >= 400 else ""
    print(f"{label}: {resp.status_code}{extra}")


c.post(reverse("login"), {"email": "admin@demo.com", "password": "Senha123", "remember_me": True}, **H)

for name in [
    "calendar_month",
    "events_list",
    "event_create",
    "holidays_list",
    "academic_years_list",
]:
    show(f"{name}", c.get(reverse(name), **H))

from academic_calendar.models import CalendarEvent

ev = CalendarEvent.objects.first()
show("event_detail", c.get(reverse("event_detail", kwargs={"pk": ev.pk}), **H))
show("monthly 06/2026", c.get(reverse("calendar_month_specific", kwargs={"year": 2026, "month": 6}), **H))

ev_junina = CalendarEvent.objects.get(title__contains="Festa Junina")
print("Festa Junina:", ev_junina.start_date, ev_junina.type)

# GET do dashboard com widget de próximos eventos
show("dashboard /app/", c.get("/app/", **H))

svc = __import__("academic_calendar.services", fromlist=["CalendarService"]).CalendarService()
print("is_working_day(2026-05-01 feriado):", svc.is_working_day(dt.date(2026, 5, 1)))
print("is_working_day(2026-05-04 seg):", svc.is_working_day(dt.date(2026, 5, 4)))