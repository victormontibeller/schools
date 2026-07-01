"""Smoke test de demo via Django test client (host=localhost → tenant demo)."""

# Workaround Django 5.1 + Python 3.14 (mesmo patch do conftest.py).
from django.template.context import BaseContext


def _patched_bctx_copy(self):
    cls = type(self)
    new = object.__new__(cls)
    for slot in getattr(cls, "__slots__", ()) or ():
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

from django.test import Client

c = Client(raise_request_exception=False)
HOST = {"HTTP_HOST": "localhost"}


def show(label, resp):
    loc = resp.get("Location", "")
    extra = ""
    if resp.status_code >= 400:
        import re

        m = re.findall(r"Exception Value:.*?</", resp.content.decode("utf-8", "ignore"), re.S)
        extra = " | " + (m[0][:300] if m else resp.content[:300].decode("utf-8", "ignore"))
    print(f"{label}: {resp.status_code} {('-> ' + loc) if loc else ''}{extra}")


# 1. Dashboard sem login -> deve redirecionar para login.
show("GET / (anon)", c.get("/", **HOST))

# 2. Login.
from django.urls import reverse

login_url = reverse("login")
show(
    "POST login",
    c.post(
        login_url, {"email": "admin@demo.com", "password": "Senha123", "remember_me": True}, **HOST
    ),
)

# 3. Dashboard após login.
show("GET / (auth)", c.get("/", **HOST))

# 4. Listas dos módulos.
for name in [
    "teachers_list",
    "students_list",
    "guardians_list",
    "classes_list",
    "rooms_list",
    "activities_list",
    "time_slots_list",
]:
    url = reverse(name)
    show(f"GET {url}", c.get(url, **HOST))

# 5. Detalhe da turma + grade + atividade.
from activities.models import Activity
from classes.models import Class

cls = Class.objects.first()
show(f"GET class_detail {cls.pk}", c.get(reverse("class_detail", kwargs={"pk": cls.pk}), **HOST))
show("GET schedule_weekly", c.get(reverse("schedule_weekly", kwargs={"class_id": cls.pk}), **HOST))
show(
    "GET schedule_create (GET)",
    c.get(reverse("schedule_create", kwargs={"class_id": cls.pk}), **HOST),
)
act = Activity.objects.first()
show(
    f"GET activity_detail {act.pk}",
    c.get(reverse("activity_detail", kwargs={"pk": act.pk}), **HOST),
)
show("GET activity_create (GET)", c.get(reverse("activity_create"), **HOST))
show("GET class_create (GET)", c.get(reverse("class_create"), **HOST))
show("GET room_create (GET)", c.get(reverse("room_create"), **HOST))
