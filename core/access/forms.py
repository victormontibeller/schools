"""Validação de campo da central de acessos."""

from __future__ import annotations

from django import forms

from core.access_catalog import (
    ACTION_LABELS,
    ACTION_SHORT_LABELS,
    ACTIONS,
    CONFIGURABLE_ROLES,
    MODULES,
    ROLE_LABELS,
    VIEW,
)


class AccessConfigurationForm(forms.Form):
    """Valida todos os grupos configuráveis em uma única matriz."""

    def __init__(self, *args, initial_access=None, versions=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        initial_access = initial_access or {}
        versions = versions or {}
        for role_name in CONFIGURABLE_ROLES:
            self.fields[self.version_field_name(role_name)] = forms.IntegerField(
                min_value=0,
                initial=versions.get(role_name),
                widget=forms.HiddenInput(),
            )
        for module in MODULES:
            for role_name in CONFIGURABLE_ROLES:
                if role_name not in module.eligible_roles:
                    continue
                field_name = self.field_name(module.key, role_name)
                current = initial_access.get(role_name, {}).get(module.key, {})
                self.fields[field_name] = forms.MultipleChoiceField(
                    required=False,
                    label=f"Permissões de {ROLE_LABELS[role_name]} em {module.label}",
                    choices=tuple(
                        (action, ACTION_LABELS[action])
                        for action in ACTIONS
                        if action in module.supported_actions
                    ),
                    initial=tuple(
                        action
                        for action in ACTIONS
                        if action in module.supported_actions and current.get(action, False)
                    ),
                    widget=forms.CheckboxSelectMultiple(
                        attrs={
                            "class": "form-check-input sm-access-action-input",
                            "data-module": module.key,
                            "data-role": role_name,
                        }
                    ),
                )

    @staticmethod
    def field_name(module_key: str, role_name: str) -> str:
        """Produz o nome estável do array de ações de uma célula."""
        return f"access__{module_key}__{role_name}"

    @staticmethod
    def version_field_name(role_name: str) -> str:
        """Produz o nome estável da versão de um grupo."""
        return f"version__{role_name}"

    def clean(self) -> dict:
        """Normaliza dependências e entrega somente combinações elegíveis."""
        cleaned = super().clean()
        submitted_access_fields = {
            field_name
            for field_name in self.data
            if field_name.startswith(("access__", "version__"))
        }
        unknown_fields = submitted_access_fields - self.fields.keys()
        if unknown_fields:
            raise forms.ValidationError("A matriz contém grupos ou módulos inválidos.")

        matrix: dict[str, dict[str, frozenset[str]]] = {
            role_name: {} for role_name in CONFIGURABLE_ROLES
        }
        versions_map = {}
        for role_name in CONFIGURABLE_ROLES:
            versions_map[role_name] = cleaned.get(self.version_field_name(role_name))
            for module in MODULES:
                if role_name not in module.eligible_roles:
                    continue
                selected = set(cleaned.get(self.field_name(module.key, role_name), ()))
                if selected - {VIEW}:
                    selected.add(VIEW)
                if VIEW not in selected:
                    selected.clear()
                matrix[role_name][module.key] = frozenset(selected)
        cleaned["access_matrix"] = matrix
        cleaned["expected_versions"] = versions_map
        return cleaned

    @property
    def role_columns(self) -> tuple[dict, ...]:
        """Entrega os cabeçalhos dos cinco grupos na ordem canônica."""
        return tuple(
            {"name": role_name, "label": ROLE_LABELS[role_name]} for role_name in CONFIGURABLE_ROLES
        )

    @property
    def version_fields(self) -> tuple:
        """Entrega os campos ocultos de concorrência otimista."""
        return tuple(self[self.version_field_name(role_name)] for role_name in CONFIGURABLE_ROLES)

    @property
    def matrix_rows(self) -> tuple[dict, ...]:
        """Entrega uma linha por módulo e uma célula por grupo."""
        rows = []
        for module in MODULES:
            cells = []
            for role_name in CONFIGURABLE_ROLES:
                if role_name not in module.eligible_roles:
                    cells.append(
                        {
                            "role_name": role_name,
                            "available": False,
                            "field": None,
                            "options": (),
                            "selected_actions": (),
                        }
                    )
                    continue
                field = self[self.field_name(module.key, role_name)]
                selected = set(field.value() or ())
                selected_actions = tuple(
                    {
                        "key": action,
                        "label": ACTION_LABELS[action],
                        "short_label": ACTION_SHORT_LABELS[action],
                    }
                    for action in ACTIONS
                    if action in selected
                )
                cells.append(
                    {
                        "role_name": role_name,
                        "available": True,
                        "field": field,
                        "options": tuple(field),
                        "selected_actions": selected_actions,
                    }
                )
            rows.append({"module": module, "cells": tuple(cells)})
        return tuple(rows)
