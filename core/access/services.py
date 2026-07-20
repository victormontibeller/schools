"""Regras de negócio da matriz central de acessos."""

from __future__ import annotations

from collections.abc import Collection, Mapping

from django.db import transaction

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.services import BaseService
from core.access_catalog import (
    ACTION_FIELDS,
    ACTIONS,
    ADMIN,
    CONFIGURABLE_ROLES,
    MODULES,
    MODULES_BY_KEY,
    VIEW,
    allowed_actions,
    default_actions,
)


class AccessConfigurationService(BaseService):
    """Cria defaults e atualiza capacidades de grupos com concorrência segura."""

    @transaction.atomic
    def create_missing_access_defaults(self) -> int:
        """Cria papéis e acessos ausentes sem sobrescrever escolhas existentes."""
        from core.models import Role, RoleModuleAccess

        created_count = 0
        roles = {}
        for role_name in (ADMIN, *CONFIGURABLE_ROLES):
            role, created = Role.objects.get_or_create(
                name=role_name,
                defaults={"created_by": self.user, "updated_by": self.user},
            )
            roles[role_name] = role
            if created:
                created_count += 1
                self._record_audit("INSERT", role)

        for module in MODULES:
            for role_name in module.eligible_roles:
                actions = default_actions(module.key, role_name)
                defaults = {ACTION_FIELDS[action]: action in actions for action in ACTIONS}
                defaults.update(created_by=self.user, updated_by=self.user)
                access, created = RoleModuleAccess.objects.get_or_create(
                    role=roles[role_name],
                    module_key=module.key,
                    defaults=defaults,
                )
                if created:
                    created_count += 1
                    self._record_audit("INSERT", access)
        if created_count:
            self._log("access_defaults_created", created_count=created_count)
        return created_count

    @transaction.atomic
    def update_access_matrix(
        self,
        access_matrix: Mapping[str, Mapping[str, Collection[str]]],
        expected_versions: Mapping[str, int],
    ) -> tuple:
        """Atualiza a matriz completa; conflito em um grupo desfaz toda a operação."""
        from core.models import Role

        expected_roles = set(CONFIGURABLE_ROLES)
        if set(access_matrix) != expected_roles or set(expected_versions) != expected_roles:
            raise ValidationError(errors={"access": ["Matriz de grupos incompleta ou inválida."]})

        normalized = {
            role_name: self._validate_role_matrix(role_name, access_matrix[role_name])
            for role_name in CONFIGURABLE_ROLES
        }
        locked_roles = {
            role.name: role
            for role in Role.objects.select_for_update().filter(name__in=CONFIGURABLE_ROLES)
        }
        missing_roles = [
            role_name for role_name in CONFIGURABLE_ROLES if role_name not in locked_roles
        ]
        if missing_roles:
            raise ObjectNotFoundError("Role", missing_roles[0])

        for role_name in CONFIGURABLE_ROLES:
            self._validate_version(locked_roles[role_name], expected_versions[role_name])

        changed_roles = 0
        for role_name in CONFIGURABLE_ROLES:
            role = locked_roles[role_name]
            changed_modules = self._apply_role_access(role, normalized[role_name])
            if changed_modules:
                changed_roles += 1
            self._finish_role_update(role, changed_modules)
        if changed_roles:
            self._log("access_matrix_updated", changed_role_count=changed_roles)
        return tuple(locked_roles[role_name] for role_name in CONFIGURABLE_ROLES)

    @staticmethod
    def _validate_version(role, expected_version: int) -> None:
        if role.version != expected_version:
            raise BusinessRuleViolationError(
                "Os acessos foram alterados por outra pessoa. "
                "Recarregue a tela e tente novamente."
            )

    @staticmethod
    def _validate_role_matrix(
        role_name: str,
        access_matrix: Mapping[str, Collection[str]],
    ) -> dict[str, frozenset[str]]:
        expected_modules = {module.key for module in MODULES if role_name in module.eligible_roles}
        if set(access_matrix) != expected_modules:
            raise ValidationError(errors={"access": ["Matriz de módulos incompleta ou inválida."]})

        normalized = {}
        for module_key, submitted in access_matrix.items():
            module = MODULES_BY_KEY[module_key]
            selected = set(submitted)
            if selected - allowed_actions(module, role_name):
                raise ValidationError(errors={"access": ["Ação não suportada pelo módulo."]})
            if selected - {VIEW}:
                selected.add(VIEW)
            if VIEW not in selected:
                selected.clear()
            normalized[module_key] = frozenset(selected)
        return normalized

    def _apply_role_access(self, role, access_matrix: Mapping[str, Collection[str]]) -> list[str]:
        from core.models import RoleModuleAccess

        changed_modules = []
        for module_key, selected in access_matrix.items():
            access, created = RoleModuleAccess.objects.get_or_create(
                role=role,
                module_key=module_key,
                defaults={"created_by": self.user, "updated_by": self.user},
            )
            old = {action: getattr(access, ACTION_FIELDS[action]) for action in ACTIONS}
            new = {action: action in selected for action in ACTIONS}
            if old == new:
                if created:
                    self._record_audit("INSERT", access)
                    changed_modules.append(module_key)
                continue
            for action in ACTIONS:
                setattr(access, ACTION_FIELDS[action], new[action])
            access.updated_by = self.user
            access.save()
            self._record_audit("INSERT" if created else "UPDATE", access, old_values=old)
            changed_modules.append(module_key)
        return changed_modules

    def _finish_role_update(self, role, changed_modules: Collection[str]) -> None:
        if not changed_modules:
            return
        old_role_version = role.version
        role.updated_by = self.user
        role.save(update_fields=["updated_by", "updated_at"])
        self._record_audit(
            "UPDATE",
            role,
            old_values={"version": old_role_version},
            new_values={"changed_modules": sorted(changed_modules)},
        )
        self._log(
            "role_access_updated",
            role_name=role.name,
            changed_count=len(changed_modules),
        )
