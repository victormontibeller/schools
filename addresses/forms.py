"""Formularios do modulo de enderecos."""

from django import forms

from addresses.models import Address


class AddressForm(forms.ModelForm):
    """Formulario de criacao/edicao de endereco."""

    class Meta:
        model = Address
        fields = [
            "recipient",
            "street",
            "number",
            "complement",
            "district",
            "postal_code",
            "city",
            "state",
        ]
        widgets = {
            "recipient": forms.TextInput(attrs={"class": "form-control"}),
            "street": forms.TextInput(attrs={"class": "form-control"}),
            "number": forms.TextInput(attrs={"class": "form-control"}),
            "complement": forms.TextInput(attrs={"class": "form-control"}),
            "district": forms.TextInput(attrs={"class": "form-control"}),
            "postal_code": forms.TextInput(attrs={"class": "form-control", "maxlength": "9"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "state": forms.Select(attrs={"class": "form-select"}),
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
