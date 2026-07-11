"""Testes para AddressSelector."""

import pytest


@pytest.fixture()
def selector():
    from addresses.selectors import AddressSelector

    return AddressSelector()


@pytest.fixture()
def school_with_address(user):
    from addresses.models import Address, SchoolAddress
    from tenancy.models import School

    school = School.objects.create(
        schema_name="testschool2",
        name="Escola Enderecada",
        created_by=user,
        updated_by=user,
    )
    address = Address.objects.create(
        street="Av Principal",
        number="1000",
        district="Centro",
        postal_code="01001000",
        city="Sao Paulo",
        state="SP",
        created_by=user,
        updated_by=user,
    )
    SchoolAddress.objects.create(
        school=school,
        address=address,
        is_primary=True,
        created_by=user,
        updated_by=user,
    )
    return school, address


@pytest.mark.django_db
def test_get_by_entity_returns_addresses(selector, school_with_address):
    school, address = school_with_address
    result = selector.get_by_entity("school", school.pk)
    assert len(result) == 1
    assert result[0].street == "Av Principal"


@pytest.mark.django_db
def test_get_primary_address(selector, school_with_address):
    school, address = school_with_address
    result = selector.get_primary_address("school", school.pk)
    assert result is not None
    assert result.street == "Av Principal"


@pytest.mark.django_db
def test_get_by_entity_unknown_type_returns_empty(selector):
    result = selector.get_by_entity("unknown", "some-id")
    assert result == []


@pytest.mark.django_db
def test_get_by_entity_no_data_returns_empty(selector):
    import uuid

    result = selector.get_by_entity("school", uuid.uuid4())
    assert result == []


@pytest.mark.django_db
def test_list_by_city(selector, school_with_address):
    result = selector.list_by_city("Sao Paulo")
    assert result.total >= 1
    assert any(a.city == "Sao Paulo" for a in result.items)
