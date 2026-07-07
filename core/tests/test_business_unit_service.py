"""Testes para BusinessUnitService."""

import pytest

from base.exceptions import ObjectNotFoundError, ValidationError


@pytest.fixture()
def service(user):
    from core.services import BusinessUnitService

    return BusinessUnitService(user=user)


@pytest.fixture()
def business_unit(user):
    from core.models import BusinessUnit

    return BusinessUnit.objects.create(
        name="Unidade Centro",
        cnpj="11222333000181",
        created_by=user,
        updated_by=user,
    )


VALID_BUSINESS_UNIT_DATA = {
    "name": "Unidade Norte",
    "cnpj": "22333444000181",
    "legal_name": "Unidade Norte Ltda",
    "trade_name": "Norte",
    "phone": "1133334444",
    "email": "norte@demo.com",
    "contact_full_name": "Ana Gestora",
    "contact_role": "Diretora",
    "contact_phone": "11999998888",
    "contact_email": "ana@demo.com",
}


@pytest.mark.django_db
def test_create_business_unit_succeeds(service):
    result = service.create_business_unit(VALID_BUSINESS_UNIT_DATA)

    assert result.pk is not None
    assert result.name == "Unidade Norte"
    assert result.cnpj == "22333444000181"


@pytest.mark.django_db
def test_create_business_unit_fails_when_name_missing(service):
    with pytest.raises(ValidationError):
        service.create_business_unit({})


@pytest.mark.django_db
def test_create_business_unit_fails_when_name_is_duplicated(service, business_unit):
    with pytest.raises(ValidationError):
        service.create_business_unit({"name": business_unit.name})


@pytest.mark.django_db
def test_update_business_unit_succeeds(service, business_unit):
    result = service.update_business_unit(
        business_unit.pk, {"trade_name": "Centro Atualizado", "phone": "1144445555"}
    )

    assert result.trade_name == "Centro Atualizado"
    assert result.phone == "1144445555"


@pytest.mark.django_db
def test_update_business_unit_fails_when_not_found(service):
    import uuid

    with pytest.raises(ObjectNotFoundError):
        service.update_business_unit(uuid.uuid4(), {"name": "X"})
