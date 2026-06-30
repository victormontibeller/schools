from django import forms

from notifications.models import Announcement, MessageTemplate


class AnnouncementForm(forms.ModelForm):
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
            "body": forms.Textarea(attrs={"rows": 5}),
            "scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class MessageTemplateForm(forms.ModelForm):
    class Meta:
        model = MessageTemplate
        fields = ["name", "channel", "type", "subject", "body", "variables"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 8}),
        }
