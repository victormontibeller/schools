"""Formularios do modulo de enderecos."""

from django import forms
from django.urls import reverse

from addresses.models import Address


class AddressForm(forms.ModelForm):
    """Formulario de criacao/edicao de endereco."""

    state = forms.ChoiceField(
        label="Estado",
        choices=(),
        widget=forms.Select(
            attrs={"class": "form-select form-select-sm", "data_grid": "col-6 col-lg-6"}
        ),
    )
    city = forms.ChoiceField(
        label="Municipio",
        choices=(),
        widget=forms.Select(
            attrs={"class": "form-select form-select-sm", "data_grid": "col-6 col-lg-6"}
        ),
    )

    def __init__(self, *args, **kwargs):
        """Torna todos os campos do endereco obrigatorios na interface."""
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True

        from locations.selectors import CitySelector, StateSelector

        is_instance_edit = not self.is_bound and not self.instance._state.adding
        raw_selected_state = self._get_selected_state()
        raw_selected_city = self._get_selected_city()
        state_choices = StateSelector().list_choices()
        valid_state_codes = {code for code, _label in state_choices}
        selected_state = raw_selected_state
        if selected_state not in valid_state_codes:
            selected_state = ""

        self.fields["state"].choices = [("", "Selecione uma UF")] + state_choices
        self.fields["state"].widget.attrs.update(
            {
                "hx-get": reverse("addresses:city_options"),
                "hx-target": "#city-field-container",
                "hx-swap": "outerHTML",
                "hx-trigger": "change",
                "hx-include": "#id_city",
            }
        )

        city_choices = [("", "Selecione um municipio")] + [
            (city.name, city.name) for city in CitySelector().list_by_state_code(selected_state)
        ]
        valid_city_names = {choice[0] for choice in city_choices if choice[0]}
        selected_city = raw_selected_city
        if selected_city not in valid_city_names:
            selected_city = ""
            if is_instance_edit and raw_selected_city:
                selected_state = ""
                city_choices = [("", "Selecione um municipio")]

        if is_instance_edit and selected_state and not selected_city:
            selected_state = ""
            city_choices = [("", "Selecione um municipio")]

        self.fields["city"].choices = city_choices
        if selected_state:
            self.fields["city"].widget.attrs.pop("disabled", None)
        else:
            self.fields["city"].widget.attrs["disabled"] = True
        self.fields["state"].initial = selected_state
        self.fields["city"].initial = selected_city

    def _get_selected_state(self) -> str:
        """Descobre a UF atual priorizando dados submetidos."""
        if self.is_bound:
            return (self.data.get("state") or "").strip().upper()
        if self.initial.get("state"):
            return str(self.initial["state"]).strip().upper()
        if getattr(self.instance, "state", ""):
            return str(self.instance.state).strip().upper()
        return ""

    def _get_selected_city(self) -> str:
        """Descobre o municipio atual priorizando dados submetidos."""
        if self.is_bound:
            return (self.data.get("city") or "").strip()
        if self.initial.get("city"):
            return str(self.initial["city"]).strip()
        if getattr(self.instance, "city", ""):
            return str(self.instance.city).strip()
        return ""

    class Meta:
        model = Address
        fields = [
            "recipient",
            "street",
            "number",
            "postal_code",
            "complement",
            "district",
            "state",
            "city",
        ]
        widgets = {
            "recipient": forms.TextInput(
                attrs={"class": "form-control form-control-sm", "data_grid": "col-12 col-lg-3"}
            ),
            "street": forms.TextInput(
                attrs={"class": "form-control form-control-sm", "data_grid": "col-12 col-lg-7"}
            ),
            "number": forms.TextInput(
                attrs={"class": "form-control form-control-sm", "data_grid": "col-6 col-lg-2"}
            ),
            "complement": forms.TextInput(
                attrs={"class": "form-control form-control-sm", "data_grid": "col-6 col-lg-5"}
            ),
            "district": forms.TextInput(
                attrs={"class": "form-control form-control-sm", "data_grid": "col-6 col-lg-5"}
            ),
            "postal_code": forms.TextInput(
                attrs={
                    "class": "form-control form-control-sm",
                    "maxlength": "9",
                    "data_grid": "col-6 col-lg-2",
                }
            ),
        }
        labels = {
            "recipient": "Destinatario",
            "street": "Logradouro",
            "number": "Numero",
            "complement": "Complemento",
            "district": "Bairro",
            "postal_code": "CEP",
            "city": "Municipio",
            "state": "Estado",
        }
