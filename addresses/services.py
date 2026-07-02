"""AddressService: regras de negocio para enderecos."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from addresses.models import Address

from base.exceptions import ObjectNotFoundError, ValidationError
from base.repositories import BaseRepository
from base.services import BaseService

logger = logging.getLogger(__name__)


class _AddressRepo(BaseRepository):
    """Repositorio de acesso a dados de Address."""

    @property
    def model_class(self):
        from addresses.models import Address

        return Address


class AddressService(BaseService):
    """Servico de regras de negocio para enderecos."""

    def _validate_address_data(self, data: dict) -> dict:
        """Valida e normaliza dados de endereco."""
        from base.validators import validate_cep, validate_uf

        self.validate_required(
            data, ["street", "number", "district", "postal_code", "city", "state"]
        )

        cleaned = {
            "recipient": data.get("recipient", ""),
            "street": data["street"],
            "number": data["number"],
            "complement": data.get("complement", ""),
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

        return cleaned

    def _create_address(self, data: dict):
        """Cria um registro de Address e retorna a instancia."""
        from addresses.models import Address

        cleaned = self._validate_address_data(data)

        if not cleaned["recipient"]:
            cleaned["recipient"] = cleaned["street"] + ", " + cleaned["number"]

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
