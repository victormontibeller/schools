"""Testes para SchoolService."""

import pytest

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError


@pytest.fixture()
def service(user):
    from core.services import SchoolService

    return SchoolService(user=user)


@pytest.fixture()
def school(user):
    from core.models import School

    return School.objects.create(
        schema_name="testschool06",
        name="Escola Teste 06",
        created_by=user,
        updated_by=user,
    )


VALID_SCHOOL_DATA = {
    "name": "Escola Nova",
    "cnpj": "11222333000181",
    "legal_name": "Escola Nova Ltda",
    "trade_name": "Escola Nova",
    "phone": "1133334444",
    "email": "contato@escola.com",
    "contact_full_name": "Diretor Teste",
    "contact_role": "Diretor",
    "contact_phone": "11988887777",
    "contact_email": "diretor@escola.com",
}


@pytest.mark.django_db
class TestCreateSchool:
    def test_create_succeeds(self, service):
        result = service.create_school({"name": "Minha Escola"})
        assert result.pk is not None
        assert result.name == "Minha Escola"

    def test_create_fails_when_name_missing(self, service):
        with pytest.raises(ValidationError):
            service.create_school({})

    def test_create_fails_when_duplicate_name(self, service):
        service.create_school({"name": "Escola Duplicada"})
        with pytest.raises(ValidationError):
            service.create_school({"name": "Escola Duplicada"})

    def test_create_with_valid_cnpj(self, service):
        result = service.create_school({"name": "Escola CNPJ", "cnpj": "11222333000181"})
        assert result.cnpj == "11222333000181"

    def test_create_fails_with_invalid_cnpj(self, service):
        with pytest.raises(ValidationError):
            service.create_school({"name": "CNPJ Ruim", "cnpj": "12345678901234"})

    def test_create_with_contact_data(self, service):
        result = service.create_school(VALID_SCHOOL_DATA)
        assert result.contact_full_name == "Diretor Teste"
        assert result.contact_email == "diretor@escola.com"


@pytest.mark.django_db
class TestUpdateSchool:
    def test_update_succeeds(self, service, school):
        result = service.update_school(school.pk, {"legal_name": "Nova Razao"})
        assert result.legal_name == "Nova Razao"

    def test_update_fails_when_school_not_found(self, service):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            service.update_school(uuid.uuid4(), {"name": "X"})

    def test_update_contact_data(self, service, school):
        result = service.update_school(
            school.pk, {"contact_full_name": "Nova Diretora", "contact_role": "Diretora"}
        )
        assert result.contact_full_name == "Nova Diretora"
        assert result.contact_role == "Diretora"

    def test_update_institutional_data(self, service, school):
        result = service.update_school(
            school.pk,
            {
                "trade_name": "Nome Fantasia X",
                "state_registration": "123456",
                "municipal_registration": "78901",
            },
        )
        assert result.trade_name == "Nome Fantasia X"
        assert result.state_registration == "123456"

    def test_update_duplicate_name(self, service, user, school):
        from core.models import School

        School.objects.create(
            schema_name="other06",
            name="Outra Escola",
            created_by=user,
            updated_by=user,
        )
        with pytest.raises(ValidationError):
            service.update_school(school.pk, {"name": "Outra Escola"})

    def test_update_duplicate_cnpj(self, service, user, school):
        from core.models import School

        School.objects.create(
            schema_name="cnpj06",
            name="Escola CNPJ",
            cnpj="11222333000181",
            created_by=user,
            updated_by=user,
        )
        with pytest.raises(ValidationError):
            service.update_school(school.pk, {"cnpj": "11222333000181"})


@pytest.mark.django_db
class TestDeactivateSchool:
    def test_success(self, service, school):
        result = service.deactivate_school(school.pk)
        assert result.is_deleted is True

    def test_already_deactivated(self, service, school):
        service.deactivate_school(school.pk)
        with pytest.raises(BusinessRuleViolationError):
            service.deactivate_school(school.pk)
