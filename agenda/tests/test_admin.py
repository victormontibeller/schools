"""Testes do acesso somente leitura aos modelos auditáveis no Django Admin."""

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from agenda.admin import ScheduleAdmin, TimeSlotAdmin
from agenda.models import Schedule, TimeSlot
from classes.admin import ClassAdmin
from classes.models import Class


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("admin_class", "model_class"),
    ((ClassAdmin, Class), (TimeSlotAdmin, TimeSlot), (ScheduleAdmin, Schedule)),
)
def test_domain_admins_are_read_only(user, admin_class, model_class):
    request = RequestFactory().get("/admin/")
    request.user = user
    model_admin = admin_class(model_class, AdminSite())

    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request) is False
    assert model_admin.has_delete_permission(request) is False
