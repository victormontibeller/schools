"""Testes dos contratos de leitura do catálogo público."""

import uuid

import pytest

from base.exceptions import ObjectNotFoundError


@pytest.mark.django_db
def test_school_selector_exposes_current_listing_and_platform_overview(monkeypatch):
    from django.db import connection

    from tenancy.models import Domain, School
    from tenancy.selectors import SchoolSelector

    public = School.objects.create(schema_name="public", name="Plataforma")
    school = School.objects.create(schema_name="selector_school", name="Escola Selector")
    Domain.objects.create(domain="selector.localhost", tenant=school, is_primary=True)
    selector = SchoolSelector()

    monkeypatch.setattr(connection, "schema_name", school.schema_name, raising=False)

    assert selector.model_class is School
    assert selector.list_active().total == 2
    assert selector.get_current_school() == school
    assert selector.get_platform_overview() == {
        "total_tenants": 1,
        "active_tenants": 1,
        "total_domains": 1,
    }
    assert selector.list_platform_tenants(search="Selector").items == [school]
    assert selector.get_platform_school(school.pk) == school
    with pytest.raises(ObjectNotFoundError):
        selector.get_platform_school(public.pk)


@pytest.mark.django_db
def test_school_selector_rejects_unknown_platform_school():
    from tenancy.selectors import SchoolSelector

    with pytest.raises(ObjectNotFoundError):
        SchoolSelector().get_platform_school(uuid.uuid4())
