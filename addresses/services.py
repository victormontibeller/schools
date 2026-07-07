"""AddressService: regras de negocio para enderecos."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

if TYPE_CHECKING:
    from addresses.models import Address

from base.exceptions import ObjectNotFoundError, ValidationError
from base.repositories import BaseRepository
from base.services import BaseService


class _AddressRepo(BaseRepository):
    """Repositorio de acesso a dados de Address."""

    @property
    def model_class(self):
        from addresses.models import Address

        return Address


class AddressService(BaseService):
    """Servico de regras de negocio para enderecos."""

    def lookup_postal_code(self, postal_code: str) -> dict[str, str]:
        """Consulta um CEP em provedor externo e normaliza o retorno."""
        from base.validators import validate_cep
        from locations.models import City

        try:
            cleaned_postal_code = validate_cep(postal_code)
        except Exception as exc:
            raise ValidationError(errors={"postal_code": [str(exc)]}) from exc

        endpoint = f"https://viacep.com.br/ws/{cleaned_postal_code}/json/"

        try:
            with urlopen(endpoint, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise ValidationError(
                errors={"postal_code": ["Nao foi possivel consultar o CEP no momento."]}
            ) from exc

        if payload.get("erro"):
            raise ValidationError(errors={"postal_code": ["CEP nao encontrado."]})

        state = str(payload.get("uf", "")).strip().upper()
        city = str(payload.get("localidade", "")).strip()
        if not state or not city:
            raise ValidationError(
                errors={"postal_code": ["CEP sem dados suficientes para preencher."]}
            )

        if not City.objects.filter(state__code=state, name=city).exists():
            raise ValidationError(
                errors={"postal_code": ["CEP retornou um municipio nao cadastrado no sistema."]}
            )

        return {
            "postal_code": self._format_postal_code(cleaned_postal_code),
            "street": str(payload.get("logradouro", "")).strip(),
            "district": str(payload.get("bairro", "")).strip(),
            "complement": str(payload.get("complemento", "")).strip(),
            "state": state,
            "city": city,
        }

    @staticmethod
    def _format_postal_code(postal_code: str) -> str:
        """Formata CEP com hifen para exibicao."""
        return f"{postal_code[:5]}-{postal_code[5:]}"

    def _validate_address_data(self, data: dict) -> dict:
        """Valida e normaliza dados de endereco."""
        from base.validators import validate_cep, validate_uf
        from locations.models import City

        self.validate_required(
            data,
            [
                "recipient",
                "street",
                "number",
                "complement",
                "district",
                "postal_code",
                "city",
                "state",
            ],
        )

        cleaned = {
            "recipient": data["recipient"],
            "street": data["street"],
            "number": data["number"],
            "complement": data["complement"],
            "district": data["district"],
            "city": data["city"],
            "state": data["state"],
        }

        postal_code = data["postal_code"]
        try:
            cleaned["postal_code"] = validate_cep(postal_code)
        except Exception as e:
            raise ValidationError(errors={"postal_code": [str(e)]}) from e

        try:
            cleaned["state"] = validate_uf(data["state"])
        except Exception as e:
            raise ValidationError(errors={"state": [str(e)]}) from e

        city_name = str(data["city"]).strip()
        if not City.objects.filter(state__code=cleaned["state"], name=city_name).exists():
            raise ValidationError(errors={"city": ["Municipio invalido para a UF informada."]})
        cleaned["city"] = city_name

        return cleaned

    def _create_address(self, data: dict):
        """Cria um registro de Address e retorna a instancia."""
        from addresses.models import Address

        cleaned = self._validate_address_data(data)

        address = Address.objects.create(
            created_by=self.user,
            updated_by=self.user,
            **cleaned,
        )
        self._record_audit("INSERT", address)
        self._log("Endereco criado", address_id=str(address.pk))
        return address

    def _link_address(
        self, link_model, entity_field: str, entity_obj, address, is_primary: bool = True
    ):
        """Cria o vinculo entre entidade e endereco."""
        filters = {entity_field: entity_obj, "address": address}
        if link_model.objects.filter(**filters).exists():
            return None

        link = link_model.objects.create(
            **{entity_field: entity_obj},
            address=address,
            is_primary=is_primary,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", link)
        self._log("Vinculo de endereco criado", link_id=str(link.pk))
        return link

    def create_address_for_school(self, school_id, data: dict) -> Address:
        """Cria endereco e vincula a uma escola."""
        from addresses.models import SchoolAddress
        from core.models import School

        try:
            school = School.objects.get(pk=school_id)
        except School.DoesNotExist:
            raise ObjectNotFoundError("School", str(school_id)) from None

        address = self._create_address(data)
        self._link_address(SchoolAddress, "school", school, address)
        return address

    def create_address_for_business_unit(self, business_unit_id, data: dict) -> Address:
        """Cria endereco e vincula a uma empresa."""
        from addresses.models import BusinessUnitAddress
        from core.models import BusinessUnit

        try:
            business_unit = BusinessUnit.objects.get(pk=business_unit_id)
        except BusinessUnit.DoesNotExist:
            raise ObjectNotFoundError("BusinessUnit", str(business_unit_id)) from None

        address = self._create_address(data)
        self._link_address(BusinessUnitAddress, "business_unit", business_unit, address)
        return address

    def create_address_for_teacher(self, teacher_id, data: dict) -> Address:
        """Cria endereco e vincula a um professor."""
        from addresses.models import TeacherAddress
        from teachers.models import Teacher

        try:
            teacher = Teacher.objects.get(pk=teacher_id)
        except Teacher.DoesNotExist:
            raise ObjectNotFoundError("Teacher", str(teacher_id)) from None

        address = self._create_address(data)
        self._link_address(TeacherAddress, "teacher", teacher, address)
        return address

    def create_address_for_student(self, student_id, data: dict) -> Address:
        """Cria endereco e vincula a um aluno."""
        from addresses.models import StudentAddress
        from students.models import Student

        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            raise ObjectNotFoundError("Student", str(student_id)) from None

        address = self._create_address(data)
        self._link_address(StudentAddress, "student", student, address)
        return address

    def create_address_for_guardian(self, guardian_id, data: dict) -> Address:
        """Cria endereco e vincula a um responsavel."""
        from addresses.models import GuardianAddress
        from guardians.models import Guardian

        try:
            guardian = Guardian.objects.get(pk=guardian_id)
        except Guardian.DoesNotExist:
            raise ObjectNotFoundError("Guardian", str(guardian_id)) from None

        address = self._create_address(data)
        self._link_address(GuardianAddress, "guardian", guardian, address)
        return address

    def update_address(self, address_id, data: dict) -> Address:
        """Atualiza dados do endereco e registra auditoria."""
        from addresses.models import Address

        try:
            address = Address.objects.get(pk=address_id)
        except Address.DoesNotExist:
            raise ObjectNotFoundError("Address", str(address_id)) from None

        old = {
            "street": address.street,
            "number": address.number,
            "district": address.district,
            "city": address.city,
            "state": address.state,
        }

        cleaned = self._validate_address_data(data)
        for field, value in cleaned.items():
            setattr(address, field, value)
        address.updated_by = self.user
        address.save()

        self._record_audit("UPDATE", address, old_values=old)
        self._log("Endereco atualizado", address_id=str(address.pk))
        return address

    def deactivate_address(self, address_id) -> Address:
        """Aplica exclusao logica no endereco e registra auditoria."""
        from addresses.models import Address

        return self._deactivate(Address, address_id, "Address")
