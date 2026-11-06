"""Formulários da central de comunicados com fallback HTML nativo."""

from django import forms

from base.forms import VersionedModelForm
from notifications.models import Announcement


class AnnouncementForm(VersionedModelForm):
    class_ids = forms.MultipleChoiceField(
        required=False, label="Turmas", widget=forms.SelectMultiple(attrs={"class": "form-select"})
    )
    user_ids = forms.MultipleChoiceField(
        required=False, label="Pessoas", widget=forms.SelectMultiple(attrs={"class": "form-select"})
    )
    student_id = forms.ChoiceField(
        required=False,
        label="Contexto individual da criança",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Announcement
        fields = [
            "title",
            "body",
            "audience",
            "class_ids",
            "user_ids",
            "student_id",
            "send_email",
            "requires_acknowledgement",
            "acknowledgement_due_at",
        ]
        labels = {
            "title": "Título",
            "body": "Mensagem",
            "audience": "Destinatários",
            "send_email": "Avisar por e-mail",
            "requires_acknowledgement": "Solicitar ciência explícita",
            "acknowledgement_due_at": "Prazo de ciência (opcional)",
        }
        widgets = {
            "body": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "acknowledgement_due_at": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
        }

    def __init__(self, *args, choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        for key in ("class_ids", "user_ids", "student_id"):
            self.fields[key].choices = (choices or {}).get(key, [])
        if self.instance and self.instance.pk:
            self.fields["student_id"].initial = self.instance.student_id or ""
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                (
                    "form-check-input"
                    if isinstance(field.widget, forms.CheckboxInput)
                    else "form-select" if isinstance(field.widget, forms.Select) else "form-control"
                ),
            )


class AnnouncementScheduleForm(forms.Form):
    version = forms.IntegerField(widget=forms.HiddenInput())
    scheduled_at = forms.DateTimeField(
        label="Publicar em",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
    )


class AnnouncementAttachmentForm(forms.Form):
    version = forms.IntegerField(widget=forms.HiddenInput())
    file = forms.FileField(
        label="PDF ou imagem",
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdf,.jpg,.jpeg,.png,.webp"}
        ),
    )
