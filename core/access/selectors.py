"""Consultas da matriz central de acessos."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db.models import Q, QuerySet

from base.exceptions import ObjectNotFoundError
from core.access_catalog import (
    ACTION_FIELDS,
    ACTIONS,
    ADMIN,
    CONFIGURABLE_ROLES,
    MODULES,
    MODULES_BY_KEY,
    ROLE_LABELS,
)

if TYPE_CHECKING:
    from core.models import CustomUser


@dataclass(frozen=True, slots=True)
class AccessMatrixRole:
    """Cabeçalho de grupo e versão usados pelo formulário completo."""

    name: str
    label: str
    version: int


@dataclass(frozen=True, slots=True)
class FullAccessMatrix:
    """Estado completo dos grupos configuráveis em uma única leitura."""

    roles: tuple[AccessMatrixRole, ...]
    values: dict[str, dict[str, dict[str, bool]]]


class AccessConfigurationSelector:
    """Lê políticas sem alterar o estado do tenant."""

    @staticmethod
    def users_with_permission(module_key: str, action: str) -> QuerySet[CustomUser]:
        """Lista usuários que possuem uma capacidade na matriz central."""
        from core.models import CustomUser

        module = MODULES_BY_KEY.get(module_key)
        if module is None or action not in module.supported_actions:
            return CustomUser.objects.none()
        configured_access = {
            "role__name__in": module.eligible_roles,
            "role__module_accesses__module_key": module_key,
            f"role__module_accesses__{ACTION_FIELDS[action]}": True,
        }
        return CustomUser.objects.filter(
            Q(is_superuser=True) | Q(role__name=ADMIN) | Q(**configured_access)
        ).distinct()

    def get_full_matrix(self) -> FullAccessMatrix:
        """Carrega os cinco grupos e suas capacidades sem consultas por célula."""
        from core.models import Role

        roles = {
            role.name: role
            for role in Role.objects.filter(name__in=CONFIGURABLE_ROLES).prefetch_related(
                "module_accesses"
            )
        }
        missing_roles = [role_name for role_name in CONFIGURABLE_ROLES if role_name not in roles]
        if missing_roles:
            raise ObjectNotFoundError("Role", missing_roles[0])

        values = {}
        columns = []
        for role_name in CONFIGURABLE_ROLES:
            role = roles[role_name]
            accesses = {access.module_key: access for access in role.module_accesses.all()}
            role_values = {}
            for module in MODULES:
                if role_name not in module.eligible_roles:
                    continue
                access = accesses.get(module.key)
                role_values[module.key] = {
                    action: bool(access and getattr(access, ACTION_FIELDS[action]))
                    for action in ACTIONS
                }
            values[role_name] = role_values
            columns.append(
                AccessMatrixRole(
                    name=role_name,
                    label=ROLE_LABELS[role_name],
                    version=role.version,
                )
            )
        return FullAccessMatrix(roles=tuple(columns), values=values)

    @staticmethod
    def permissions_for_role(role_id) -> dict[str, frozenset[str]]:
        """Carrega todas as capacidades do papel em uma única consulta."""
        from core.models import RoleModuleAccess

        result = {}
        for access in RoleModuleAccess.objects.filter(role_id=role_id):
            result[access.module_key] = frozenset(
                action for action, field in ACTION_FIELDS.items() if getattr(access, field)
            )
        return result
