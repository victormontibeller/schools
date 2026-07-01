"""Formulários de comunicados e templates de mensagens."""

from django import forms

from notifications.models import Announcement, MessageTemplate


class AnnouncementForm(forms.ModelForm):
    """Formulário de criação/edição de comunicado institucional."""

    class Meta:
        model = Announcement
        fields = [
            "title",
            "body",
            "audience",
            "class_obj",
            "send_email",
            "send_whatsapp",
            "scheduled_at",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "body": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "audience": forms.Select(attrs={"class": "form-select"}),
            "class_obj": forms.Select(attrs={"class": "form-select"}),
            "send_email": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "send_whatsapp": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "scheduled_at": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
        }
        labels = {
            "title": "Título",
            "body": "Mensagem",
            "audience": "Público-alvo",
            "class_obj": "Turma (quando aplicável)",
            "send_email": "Enviar por E-mail",
            "send_whatsapp": "Enviar por WhatsApp",
            "scheduled_at": "Agendado para (opcional)",
        }


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
