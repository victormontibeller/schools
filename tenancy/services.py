"""Services de provisionamento e acesso temporário entre schemas."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.db import connection
from django.utils import timezone

from base import context as audit_context
from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from base.services import BaseService

SUPPORT_TOKEN_SALT = "schools.support-access.v1"  # noqa: S105 -- signing salt, não senha
SUPPORT_TOKEN_TTL_SECONDS = 30 * 60
SUPPORT_USER_EMAIL = "platform-support@internal.invalid"


class PlatformSchoolService(BaseService):
    """Provisiona e mantém escolas no catálogo público."""

    def create_platform_school(self, data: dict):
        """Cria tenant e domínio primário com auditoria."""
        from tenancy.models import Domain, School

        self._validate_platform_operator()
        self.validate_required(data, ["name", "schema_name", "domain"])
        name = data["name"].strip()
        schema_name = data["schema_name"].strip().lower()
        domain_name = data["domain"].strip().lower()
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
        domain_name = data.get("domain", getattr(domain, "domain", "")).strip().lower()
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


class SupportAccessService(BaseService):
    """Cria, consome e encerra acessos temporários de operadores públicos."""

    def create_grant(self, tenant_id, reason: str, source_ip: str = ""):
        """Cria concessão no public e retorna token assinado de uso único."""
        from tenancy.models import School, SupportAccessGrant

        if self.user is None or not (
            self.user.is_superuser or self.user.has_perm("tenancy.access_tenant")
        ):
            raise PermissionDeniedError("Sem permissão para acessar tenants.")
        if getattr(connection, "schema_name", "public") != "public":
            raise BusinessRuleViolationError("Concessões devem ser iniciadas no painel público.")
        reason = (reason or "").strip()
        if len(reason) < 10:
            raise BusinessRuleViolationError("Informe um motivo com pelo menos 10 caracteres.")
        try:
            tenant = School.objects.get(pk=tenant_id)
        except School.DoesNotExist:
            raise ObjectNotFoundError("School", str(tenant_id)) from None
        if tenant.schema_name == "public":
            raise BusinessRuleViolationError("O schema public não requer concessão.")
        grant = SupportAccessGrant.objects.create(
            operator=self.user,
            tenant=tenant,
            reason=reason,
            source_ip=source_ip or None,
            expires_at=timezone.now() + timedelta(seconds=SUPPORT_TOKEN_TTL_SECONDS),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", grant)
        self._log("support_access_created", grant_id=str(grant.pk), tenant=tenant.schema_name)
        token = signing.dumps({"grant_id": str(grant.pk)}, salt=SUPPORT_TOKEN_SALT, compress=True)
        return grant, token

    def consume_grant(self, token: str, tenant_schema: str):
        """Valida token, marca concessão como usada e retorna a conta técnica."""
        from core.models import CustomUser, Role
        from tenancy.models import SupportAccessGrant

        try:
            payload = signing.loads(
                token,
                salt=SUPPORT_TOKEN_SALT,
                max_age=SUPPORT_TOKEN_TTL_SECONDS,
            )
        except signing.BadSignature as exc:
            raise BusinessRuleViolationError("Acesso de suporte inválido ou expirado.") from exc
        try:
            grant = SupportAccessGrant.objects.select_related("tenant", "operator").get(
                pk=payload.get("grant_id")
            )
        except SupportAccessGrant.DoesNotExist:
            raise ObjectNotFoundError("SupportAccessGrant", str(payload.get("grant_id"))) from None
        if grant.tenant.schema_name != tenant_schema:
            raise PermissionDeniedError("A concessão não pertence a este tenant.")
        if grant.used_at or grant.ended_at or grant.expires_at <= timezone.now():
            raise BusinessRuleViolationError("A concessão já foi usada ou expirou.")

        role, _ = Role.objects.get_or_create(
            name=Role.Name.ADMIN,
            defaults={"created_by": None, "updated_by": None},
        )
        support_user, created = CustomUser.all_objects.get_or_create(
            email=SUPPORT_USER_EMAIL,
            defaults={
                "first_name": "Suporte",
                "last_name": "da Plataforma",
                "role": role,
                "access_mode": CustomUser.AccessMode.SUPPORT,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        support_user.role = role
        support_user.access_mode = CustomUser.AccessMode.SUPPORT
        support_user.is_staff = True
        support_user.is_superuser = True
        support_user.is_active = True
        support_user.set_unusable_password()
        support_user.save()

        grant.used_at = timezone.now()
        grant.updated_by = grant.operator
        grant.save(update_fields=["used_at", "updated_by", "updated_at"])
        actor_token = audit_context.platform_actor_id.set(grant.operator_id)
        grant_token = audit_context.support_grant_id.set(grant.pk)
        try:
            self._record_audit("INSERT" if created else "UPDATE", support_user)
            self._record_audit("UPDATE", grant, old_values={"used_at": None})
        finally:
            audit_context.support_grant_id.reset(grant_token)
            audit_context.platform_actor_id.reset(actor_token)
        return grant, support_user

    def end_grant(self, grant_id) -> None:
        """Encerra explicitamente uma sessão de suporte ativa."""
        from tenancy.models import SupportAccessGrant

        try:
            grant = SupportAccessGrant.objects.get(pk=grant_id)
        except SupportAccessGrant.DoesNotExist:
            raise ObjectNotFoundError("SupportAccessGrant", str(grant_id)) from None
        if grant.ended_at is None:
            grant.ended_at = timezone.now()
            grant.save(update_fields=["ended_at", "updated_at"])
            self._record_audit("UPDATE", grant, old_values={"ended_at": None})


def support_target_url(grant, token: str) -> str:
    """Monta URL absoluta do callback no domínio primário do tenant."""
    domain = grant.tenant.domains.filter(is_primary=True).first()
    if domain is None:
        raise BusinessRuleViolationError("Tenant sem domínio primário configurado.")
    scheme = "http" if settings.DEBUG else "https"
    return f"{scheme}://{domain.domain}/support/consume/?token={token}"
