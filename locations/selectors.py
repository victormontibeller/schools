"""Selectors read-only para catalogos de localizacao."""

from base.selectors import BaseSelector
from locations.models import City, State


class StateSelector(BaseSelector):
    """Consultas read-only para estados do catalogo global."""

    model_class = State

    def list_all(self) -> list[State]:
        """Retorna todos os estados ordenados por nome."""
        return list(State.objects.order_by("name"))

    def list_choices(self, *, include_blank: bool = False) -> list[tuple[str, str]]:
        """Retorna choices de UF para formularios."""
        choices = [(state.code, f"{state.name} ({state.code})") for state in self.list_all()]
        if include_blank:
            return [("", "---------")] + choices
        return choices


class CitySelector(BaseSelector):
    """Consultas read-only para municipios do catalogo global."""

    model_class = City

    def list_by_state_code(self, state_code: str) -> list[City]:
        """Retorna os municipios ativos da UF informada."""
        if not state_code:
            return []
        return list(
            City.objects.select_related("state")
            .filter(state__code__iexact=state_code)
            .order_by("name")
        )
