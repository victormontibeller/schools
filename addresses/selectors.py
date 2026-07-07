"""AddressSelector: consultas somente-leitura de enderecos."""

from addresses.models import (
    Address,
    BusinessUnitAddress,
    GuardianAddress,
    SchoolAddress,
    StudentAddress,
    TeacherAddress,
)
from base.selectors import BaseSelector, PageResult


class AddressSelector(BaseSelector):
    """Consultas read-only para enderecos."""

    model_class = Address

    def get_by_entity(self, entity_type: str, entity_id) -> list[Address]:
        """Retorna lista de enderecos vinculados a uma entidade.

        Args:
            entity_type: 'school', 'business_unit', 'teacher', 'student' ou 'guardian'.
            entity_id: PK da entidade.
        """
        link_models = {
            "school": (SchoolAddress, "school"),
            "business_unit": (BusinessUnitAddress, "business_unit"),
            "teacher": (TeacherAddress, "teacher"),
            "student": (StudentAddress, "student"),
            "guardian": (GuardianAddress, "guardian"),
        }

        entry = link_models.get(entity_type)
        if not entry:
            return []

        link_model, field = entry
        filters = {field: entity_id}
        link_ids = link_model.objects.filter(**filters).values_list("address_id", flat=True)
        return list(Address.objects.filter(pk__in=link_ids).order_by("-created_at"))

    def get_primary_address(self, entity_type: str, entity_id) -> Address | None:
        """Retorna o endereco principal da entidade."""
        addresses = self.get_by_entity(entity_type, entity_id)
        return addresses[0] if addresses else None

    def get_entity_context(self, address: Address) -> tuple[str, str]:
        """Retorna o tipo e o ID da entidade dona do endereco."""
        link_checks = [
            ("school", SchoolAddress, "school_id"),
            ("business_unit", BusinessUnitAddress, "business_unit_id"),
            ("teacher", TeacherAddress, "teacher_id"),
            ("student", StudentAddress, "student_id"),
            ("guardian", GuardianAddress, "guardian_id"),
        ]
        for entity_type, link_model, field_name in link_checks:
            link = link_model.objects.filter(address=address).values(field_name).first()
            if link:
                return entity_type, str(link[field_name])
        return "school", ""

    def list_by_city(self, city: str, page: int = 1) -> PageResult[Address]:
        """Lista enderecos filtrados por municipio."""
        return self.list(filters={"city__icontains": city}, order_by="city", page=page)

    def list_by_state(self, state: str, page: int = 1) -> PageResult[Address]:
        """Lista enderecos filtrados por estado."""
        return self.list(filters={"state__iexact": state}, order_by="city", page=page)
