---
applyTo: "**/forms.py"
---

# Forms — Padrões Obrigatórios

Forms são responsáveis **apenas por validação de campo** (required, tipo, choices, formato).
Nenhuma regra de negócio aqui — isso vai em `services.py`.

## Padrão de ModelForm

```python
"""Formulários do módulo my_app."""

from django import forms

from my_app.models import MyModel


class MyModelForm(forms.ModelForm):
    """Formulário de criação/edição de MyModel."""

    class Meta:
        model = MyModel
        fields = ["name", "description", "status", "due_date", "is_active"]
        widgets = {
            # TextInput / EmailInput / NumberInput / URLInput
            "name":        forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            # Select / ChoiceField
            "status":      forms.Select(attrs={"class": "form-select"}),
            # DateInput — obrigatório type="date" para o browser renderizar date picker
            "due_date":    forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            # CheckboxInput — NÃO usa form-control (usa form-check-input)
            "is_active":   forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "name":        "Nome",
            "description": "Descrição",
            "status":      "Status",
            "due_date":    "Data de Entrega",
            "is_active":   "Ativo",
        }
```

## Padrão de Form (não-ModelForm)

Usado quando o form não mapeia diretamente para um model (ex: criação com FK manual):

```python
class TeacherForm(forms.Form):
    """Formulário de criação de professor a partir de usuário existente."""

    user_id = forms.ChoiceField(
        label="Usuário",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    registration_number = forms.CharField(
        label="Matrícula",
        max_length=20,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    hire_date = forms.DateField(
        label="Data de Contratação",
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Choices avaliados lazy — nunca no topo do módulo
        from core.models import CustomUser
        self.fields["user_id"].choices = [
            (u.pk, u.get_full_name() or u.email)
            for u in CustomUser.objects.filter(is_active=True).order_by("first_name")
        ]
```

## Widgets por Tipo de Campo

| Tipo de campo | Widget | Classe CSS |
|---|---|---|
| Texto curto | `forms.TextInput` | `class="form-control"` |
| Texto longo | `forms.Textarea` | `class="form-control" rows=3` |
| E-mail | `forms.EmailInput` | `class="form-control"` |
| Número | `forms.NumberInput` | `class="form-control" min=0` |
| Data | `forms.DateInput` | `class="form-control" type="date"` |
| Data+Hora | `forms.DateTimeInput` | `class="form-control" type="datetime-local"` |
| Select único | `forms.Select` | `class="form-select"` |
| Select múltiplo | `forms.SelectMultiple` | `class="form-select"` |
| Checkbox | `forms.CheckboxInput` | `class="form-check-input"` |
| Upload de arquivo | `forms.ClearableFileInput` | `class="form-control"` |
| Senha | `forms.PasswordInput` | `class="form-control"` |
| Oculto | `forms.HiddenInput` | — |

## Validação no Form (apenas campo, não negócio)

```python
def clean_registration_number(self):
    """Validação de formato — nunca regra de negócio (unicidade vai no service)."""
    value = self.cleaned_data.get("registration_number", "").strip()
    if not value:
        raise forms.ValidationError("Matrícula é obrigatória.")
    if len(value) > 20:
        raise forms.ValidationError("Matrícula deve ter no máximo 20 caracteres.")
    return value.upper()
```

## Regras

- **Nunca** lógica de negócio em form — usar `services.py`
- **Nunca** unicidade checada em form — isso é regra de negócio, vai no service
- **Sempre** `class="form-control"` nos widgets de texto/número/data
- **Sempre** `class="form-select"` nos widgets Select
- **Sempre** `type="date"` em `DateInput` para ativar o date picker do browser
- **Sempre** `rows=3` em Textarea (evita campo gigante)
- Choices de FK: carregar no `__init__` (lazy), nunca no topo do módulo
- Labels em português no `Meta.labels` ou no campo
