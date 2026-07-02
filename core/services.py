"""SchoolService: regras de negocio para escolas."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import School

from base.exceptions import ObjectNotFoundError, ValidationError
from base.services import BaseService

logger = logging.getLogger(__name__)


class SchoolService(BaseService):
    """Servico de regras de negocio para gestao de escolas."""

    def create_school(self, data: dict) -> School:
        """Cria uma escola validando CNPJ, nome e registrando auditoria."""
        from core.models import School

        self.validate_required(data, ["name"])

        name = data["name"].strip()
        if School.objects.filter(name__iexact=name).exists():
            raise ValidationError(errors={"name": ["Ja existe uma escola com este nome."]})

        cnpj_cleaned = self._validate_cnpj(data)

        school = School.objects.create(
            name=name,
            cnpj=cnpj_cleaned,
            legal_name=data.get("legal_name", ""),
            trade_name=data.get("trade_name", ""),
            state_registration=data.get("state_registration", ""),
            municipal_registration=data.get("municipal_registration", ""),
            phone=data.get("phone", ""),
            email=data.get("email", ""),
            contact_full_name=data.get("contact_full_name", ""),
            contact_role=data.get("contact_role", ""),
            contact_phone=data.get("contact_phone", ""),
            contact_email=data.get("contact_email", ""),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", school)
        self._log("Escola criada", school_id=str(school.pk))
        return school

    def update_school(self, school_id, data: dict) -> School:
        """Atualiza dados institucionais e de contato da escola."""
        from core.models import School

        try:
            school = School.objects.get(pk=school_id)
        except School.DoesNotExist:
            raise ObjectNotFoundError("School", str(school_id)) from None

        old = {
            "name": school.name,
            "cnpj": school.cnpj,
        }

        allowed = {
            "name",
            "legal_name",
            "trade_name",
            "state_registration",
            "municipal_registration",
            "phone",
            "email",
            "contact_full_name",
            "contact_role",
            "contact_phone",
            "contact_email",
            "academic_year_start",
            "academic_year_end",
        }
        updates = {k: v for k, v in data.items() if k in allowed}

        if "cnpj" in data:
            cnpj_cleaned = self._validate_cnpj(data, exclude_id=school_id)
            updates["cnpj"] = cnpj_cleaned

        if "name" in data and data["name"].strip() != school.name:
            new_name = data["name"].strip()
            if School.objects.filter(name__iexact=new_name).exists():
                raise ValidationError(errors={"name": ["Ja existe uma escola com este nome."]})
            updates["name"] = new_name

        for field, value in updates.items():
            setattr(school, field, value)
        school.updated_by = self.user
        school.save()

        self._record_audit("UPDATE", school, old_values=old)
        self._log("Escola atualizada", school_id=str(school.pk))
        return school

    def update_logo(self, school_id, logo_file) -> School:
        """Atualiza o logotipo da escola."""
        from core.models import School

        try:
            school = School.objects.get(pk=school_id)
        except School.DoesNotExist:
            raise ObjectNotFoundError("School", str(school_id)) from None

        school.logo = logo_file
        school.updated_by = self.user
        school.save(update_fields=["logo", "updated_by", "updated_at"])

        self._record_audit("UPDATE", school)
        self._log("Logo da escola atualizado", school_id=str(school.pk))
        return school

    def deactivate_school(self, school_id) -> School:
        """Aplica exclusao logica na escola."""
        from core.models import School

        return self._deactivate(School, school_id, "School")

    def _validate_cnpj(self, data: dict, exclude_id=None) -> str | None:
        """Valida CNPJ: formato e unicidade. Retorna CNPJ limpo ou None."""
        from base.validators import validate_cnpj
        from core.models import School

        cnpj = data.get("cnpj", "")
        if not cnpj:
            return None
        try:
            cnpj_clean = validate_cnpj(cnpj)
        except Exception as e:
            raise ValidationError(errors={"cnpj": [str(e)]}) from e

        qs = School.objects.filter(cnpj=cnpj_clean)
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
        if qs.exists():
            raise ValidationError(errors={"cnpj": ["CNPJ ja cadastrado para outra escola."]})
        return cnpj_clean
