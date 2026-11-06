"""Formulários de comunicados e templates de mensagens."""

from django import forms

from notifications.models import MessageTemplate


class MessageTemplateForm(forms.ModelForm):
    """Formulário de criação/edição de template de mensagem reutilizável."""

    class Meta:
        model = MessageTemplate
        fields = ["name", "channel", "type", "subject", "body", "variables"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "channel": forms.Select(attrs={"class": "form-select"}),
            "type": forms.Select(attrs={"class": "form-select"}),
            "subject": forms.TextInput(attrs={"class": "form-control"}),
            "body": forms.Textarea(attrs={"class": "form-control", "rows": 8}),
            "variables": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": '{"nome": "..." }'}
            ),
        }
        labels = {
            "name": "Nome",
            "channel": "Canal",
            "type": "Tipo",
            "subject": "Assunto",
            "body": "Corpo",
            "variables": "Variáveis disponíveis (JSON)",
        }
