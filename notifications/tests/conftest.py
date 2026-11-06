"""Fixtures explícitas da central de comunicação."""

import pytest

from tenancy.models import Domain, School


@pytest.fixture
def school(user):
    school = School.objects.create(schema_name="test_school", name="Escola fictícia")
    Domain.objects.create(tenant=school, domain="school.example.test", is_primary=True)
    return school
