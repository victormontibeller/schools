"""Invariantes de ciclo de vida das identidades escolares."""

from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.db.models import Q

from base.exceptions import BusinessRuleViolationError


def lock_administrator_role() -> None:
    """Serializa alterações de administradores antes de consultar a contagem."""
    from core.contracts import Role

    Role.objects.select_for_update().get(name=Role.Name.ADMIN)


def validate_user_change(user, updates: dict) -> None:
    """Preserva o último administrador e a identidade dos perfis de pessoa."""
    from core.contracts import CustomUser
    from service_requests.selectors import ServiceStaffSelector

    ServiceStaffSelector.validate_departments_staffed(user, updates)
    current_role = getattr(user.role, "name", "")
    next_role = getattr(updates.get("role", user.role), "name", "")
    if "role" in updates and next_role != current_role:
        if hasattr(user, "teacher_profile") or hasattr(user, "guardian_profile"):
            raise BusinessRuleViolationError(
                "O papel de um perfil docente ou familiar não pode ser alterado."
            )
    if updates.get("is_active") and not user.has_usable_password():
        raise BusinessRuleViolationError(
            "A pessoa deve ativar o acesso pelo convite antes de ficar ativa."
        )
    remains_admin = updates.get("is_active", user.is_active) and (
        user.is_superuser or next_role == "ADMIN"
    )
    if user.is_active and (user.is_superuser or current_role == "ADMIN") and not remains_admin:
        others = (
            CustomUser.objects.filter(Q(role__name="ADMIN") | Q(is_superuser=True), is_active=True)
            .exclude(pk=user.pk)
            .exclude(password__startswith=UNUSABLE_PASSWORD_PREFIX)
        )
        if not others.exists():
            raise BusinessRuleViolationError("Mantenha ao menos um administrador ativo na escola.")


def lock_and_refresh_administrator(service):
    """Revalida o ator depois da barreira compartilhada com alterações de papel."""
    from base.exceptions import PermissionDeniedError
    from core.contracts import CustomUser
    from core.permissions import can_access

    lock_administrator_role()
    actor = (
        CustomUser.objects.select_related("role")
        .filter(pk=getattr(service.user, "pk", None))
        .first()
    )
    if not actor or not can_access(actor, "__admin__", "edit"):
        raise PermissionDeniedError("A administração escolar exige uma autorização vigente.")
    service.user = actor
