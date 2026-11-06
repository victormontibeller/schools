"""Pessoas e escola fictícias do atendimento privado."""

import datetime as dt
from unittest.mock import patch

import pytest

from core.models import CustomUser, Role
from notifications.tests.test_announcement_workflow import family
from service_requests.configuration_services import ServiceConfigurationService
from tenancy.models import Domain, School


@pytest.fixture
def setup_requests(user):
    school = School.objects.create(schema_name="test_school", name="Escola fictícia")
    Domain.objects.create(tenant=school, domain="school.example.test", is_primary=True)
    account, guardian, cls, links = family(user)
    staff = CustomUser.objects.create_user(
        email="secretary@example.test",
        password="Violeta824",
        role=Role.objects.get(name="SECRETARY"),
    )
    service = ServiceConfigurationService(user=user)
    calendar = service.update_calendar(
        {
            "version": 0,
            "weekdays": [0, 1, 2, 3, 4],
            "opens_at": dt.time(8),
            "closes_at": dt.time(18),
            "closed_dates": [],
            "immediate_contact": "Contato fictício: 0000-0000",
        }
    )
    department = service.update_department(
        "SECRETARY", enabled=True, user_ids=[str(staff.pk)], version=0
    )
    with patch("notifications.outbox_services.publish_task_after_commit"):
        yield {
            "school": school,
            "family": account,
            "guardian": guardian,
            "student": links[0].student,
            "link": links[0],
            "staff": staff,
            "department": department,
            "calendar": calendar,
            "class": cls,
        }
