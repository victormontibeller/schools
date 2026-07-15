"""Services de provisionamento do catálogo público de escolas."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection

from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from base.services import BaseService


class PlatformSchoolService(BaseService):
    """Provisiona e mantém escolas no catálogo público."""

    def create_platform_school(self, data: dict):
        """Cria tenant e domínio primário com auditoria."""
        from tenancy.models import Domain, School

        self._validate_platform_operator()
        self.validate_required(data, ["name", "schema_name", "domain"])
        name = data["name"].strip()
        schema_name = data["schema_name"].strip().lower()
        from tenancy.domain_validation import normalize_domain

        try:
            domain_name = normalize_domain(data["domain"], tenant_schema=schema_name)
        except DjangoValidationError as exc:
            raise ValidationError(errors={"domain": list(exc.messages)}) from None
        if schema_name == "public":
            raise BusinessRuleViolationError("O schema public é reservado para a plataforma.")
        if School.all_objects.filter(schema_name=schema_name).exists():
            raise ValidationError(errors={"schema_name": ["Este schema já está cadastrado."]})
        if School.all_objects.filter(name__iexact=name).exists():
            raise ValidationError(errors={"name": ["Já existe uma escola com este nome."]})
        if Domain.objects.filter(domain=domain_name).exists():
            raise ValidationError(errors={"domain": ["Este domínio já está cadastrado."]})

        school = School.objects.create(
            schema_name=schema_name,
            name=name,
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            created_by=self.user,
            updated_by=self.user,
        )
        domain = Domain.objects.create(domain=domain_name, tenant=school, is_primary=True)
        self._record_audit("INSERT", school)
        self._record_audit("INSERT", domain)
        self._log("platform_school_created", school_id=str(school.pk))
        return school

    def update_platform_school(self, school_id, data: dict):
        """Atualiza catálogo e domínio primário sem renomear o schema."""
        from tenancy.models import Domain, School

        self._validate_platform_operator()
        try:
            school = School.all_objects.exclude(schema_name="public").get(pk=school_id)
        except School.DoesNotExist:
            raise ObjectNotFoundError("School", str(school_id)) from None

        name = data.get("name", school.name).strip()
        duplicate_name = School.all_objects.filter(name__iexact=name).exclude(pk=school.pk)
        if duplicate_name.exists():
            raise ValidationError(errors={"name": ["Já existe uma escola com este nome."]})

        domain = school.domains.filter(is_primary=True).first()
        from tenancy.domain_validation import normalize_domain

        try:
            domain_name = normalize_domain(
                data.get("domain", getattr(domain, "domain", "")),
                tenant_schema=school.schema_name,
            )
        except DjangoValidationError as exc:
            raise ValidationError(errors={"domain": list(exc.messages)}) from None
        if not domain_name:
            raise ValidationError(errors={"domain": ["Informe o domínio principal."]})
        if Domain.objects.filter(domain=domain_name).exclude(tenant=school).exists():
            raise ValidationError(errors={"domain": ["Este domínio já está cadastrado."]})

        old_school = self._snapshot(school, ["name", "is_active"])
        school.name = name
        school.email = data.get("email", school.email)
        school.phone = data.get("phone", school.phone)
        school.is_active = bool(data.get("is_active", school.is_active))
        school.updated_by = self.user
        school.save()
        self._record_audit("UPDATE", school, old_values=old_school)

        if domain is None:
            domain = Domain.objects.create(domain=domain_name, tenant=school, is_primary=True)
            self._record_audit("INSERT", domain)
        elif domain.domain != domain_name:
            old_domain = {"domain": domain.domain}
            domain.domain = domain_name
            domain.save(update_fields=["domain"])
            self._record_audit("UPDATE", domain, old_values=old_domain)
        self._log("platform_school_updated", school_id=str(school.pk))
        return school

    def _validate_platform_operator(self) -> None:
        """Restringe provisionamento a superusuários do schema público."""
        if self.user is None or not self.user.is_superuser:
            raise PermissionDeniedError("Somente superusuários podem administrar escolas.")
        if not settings.TESTING and getattr(connection, "schema_name", "public") != "public":
            raise BusinessRuleViolationError("Escolas só podem ser administradas no schema public.")
