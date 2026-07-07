"""Testes para o modulo de enderecos."""

import pytest

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError


@pytest.fixture()
def service(user):
    from addresses.services import AddressService

    return AddressService(user=user)


@pytest.fixture()
def school(user):
    from core.models import School

    return School.objects.create(
        schema_name="testschool",
        name="Escola Teste",
        created_by=user,
        updated_by=user,
    )


@pytest.fixture()
def teacher(db, user):
    from teachers.models import Teacher

    return Teacher.objects.create(
        user=user,
        registration_number="T001",
        created_by=user,
        updated_by=user,
    )


@pytest.fixture()
def business_unit(user):
    from core.models import BusinessUnit

    return BusinessUnit.objects.create(
        name="Unidade Leste",
        created_by=user,
        updated_by=user,
    )


@pytest.fixture()
def student(user):
    from students.models import Student

    return Student.objects.create(
        first_name="Aluno",
        last_name="Teste",
        enrollment_number="STU001",
        birth_date="2010-01-01",
        created_by=user,
        updated_by=user,
    )


@pytest.fixture()
def guardian(user):
    from guardians.models import Guardian

    return Guardian.objects.create(
        user=user,
        relationship_type="MAE",
        created_by=user,
        updated_by=user,
    )


VALID_ADDRESS_DATA = {
    "recipient": "Fulano de Tal",
    "street": "Rua Exemplo",
    "number": "123",
    "complement": "Apto 45",
    "district": "Centro",
    "postal_code": "01001999",
    "city": "São Paulo",
    "state": "SP",
}


class _DummyViaCepResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def read(self) -> bytes:
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.mark.django_db
def test_create_address_for_school_succeeds(service, school):
    result = service.create_address_for_school(school.pk, VALID_ADDRESS_DATA)
    assert result.pk is not None
    assert result.street == "Rua Exemplo"
    assert result.state == "SP"


@pytest.mark.django_db
def test_lookup_postal_code_succeeds(service, monkeypatch):
    payload = (
        b'{"cep":"01001-000","logradouro":"Praca da Se","complemento":"lado impar",'
        b'"bairro":"Se","localidade":"S\\u00e3o Paulo","uf":"SP"}'
    )

    monkeypatch.setattr(
        "addresses.services.urlopen",
        lambda *_args, **_kwargs: _DummyViaCepResponse(payload),
    )

    result = service.lookup_postal_code("01001000")

    assert result["postal_code"] == "01001-000"
    assert result["street"] == "Praca da Se"
    assert result["district"] == "Se"
    assert result["state"] == "SP"
    assert result["city"] == "S\u00e3o Paulo"


@pytest.mark.django_db
def test_lookup_postal_code_fails_when_not_found(service, monkeypatch):
    monkeypatch.setattr(
        "addresses.services.urlopen",
        lambda *_args, **_kwargs: _DummyViaCepResponse(b'{"erro": true}'),
    )

    with pytest.raises(ValidationError) as exc_info:
        service.lookup_postal_code("99999999")

    assert "postal_code" in exc_info.value.errors


@pytest.mark.django_db
def test_create_address_for_school_fails_when_school_not_found(service):
    import uuid

    with pytest.raises(ObjectNotFoundError):
        service.create_address_for_school(uuid.uuid4(), VALID_ADDRESS_DATA)


@pytest.mark.django_db
def test_create_address_fails_when_required_fields_missing(service, school):
    with pytest.raises(ValidationError) as exc_info:
        service.create_address_for_school(school.pk, {"street": "Rua"})
    assert "number" in exc_info.value.errors


@pytest.mark.django_db
def test_create_address_fails_when_invalid_cep(service, school):
    data = {**VALID_ADDRESS_DATA, "postal_code": "123"}
    with pytest.raises(ValidationError) as exc_info:
        service.create_address_for_school(school.pk, data)
    assert "postal_code" in exc_info.value.errors


@pytest.mark.django_db
def test_create_address_fails_when_invalid_uf(service, school):
    data = {**VALID_ADDRESS_DATA, "state": "XX"}
    with pytest.raises(ValidationError) as exc_info:
        service.create_address_for_school(school.pk, data)
    assert "state" in exc_info.value.errors


@pytest.mark.django_db
def test_create_address_fails_when_city_does_not_belong_to_state(service, school):
    data = {**VALID_ADDRESS_DATA, "city": "Niterói", "state": "SP"}
    with pytest.raises(ValidationError) as exc_info:
        service.create_address_for_school(school.pk, data)
    assert "city" in exc_info.value.errors


@pytest.mark.django_db
def test_create_address_for_teacher_succeeds(service, teacher):
    result = service.create_address_for_teacher(teacher.pk, VALID_ADDRESS_DATA)
    assert result.pk is not None


@pytest.mark.django_db
def test_create_address_for_business_unit_succeeds(service, business_unit):
    result = service.create_address_for_business_unit(business_unit.pk, VALID_ADDRESS_DATA)
    assert result.pk is not None


@pytest.mark.django_db
def test_create_address_for_teacher_fails_when_teacher_not_found(service):
    import uuid

    with pytest.raises(ObjectNotFoundError):
        service.create_address_for_teacher(uuid.uuid4(), VALID_ADDRESS_DATA)


@pytest.mark.django_db
def test_create_address_for_student_succeeds(service, student):
    result = service.create_address_for_student(student.pk, VALID_ADDRESS_DATA)
    assert result.pk is not None


@pytest.mark.django_db
def test_create_address_for_guardian_succeeds(service, guardian):
    result = service.create_address_for_guardian(guardian.pk, VALID_ADDRESS_DATA)
    assert result.pk is not None


@pytest.mark.django_db
def test_update_address_succeeds(service, school):
    addr = service.create_address_for_school(school.pk, VALID_ADDRESS_DATA)
    result = service.update_address(addr.pk, {**VALID_ADDRESS_DATA, "number": "456"})
    assert result.number == "456"


@pytest.mark.django_db
def test_update_address_fails_when_address_not_found(service):
    import uuid

    with pytest.raises(ObjectNotFoundError):
        service.update_address(uuid.uuid4(), VALID_ADDRESS_DATA)


@pytest.mark.django_db
def test_deactivate_address_succeeds(service, school):
    addr = service.create_address_for_school(school.pk, VALID_ADDRESS_DATA)
    result = service.deactivate_address(addr.pk)
    assert result.is_deleted is True
    assert result.is_active is False


@pytest.mark.django_db
def test_deactivate_address_fails_when_already_inactive(service, school):
    addr = service.create_address_for_school(school.pk, VALID_ADDRESS_DATA)
    service.deactivate_address(addr.pk)
    with pytest.raises(BusinessRuleViolationError):
        service.deactivate_address(addr.pk)
