"""Formulário nativo com transporte SMTP que não expõe exceções pessoais."""

from django.contrib.auth.forms import PasswordResetForm

from notifications.contracts import send_recovery_email


class SchoolPasswordResetForm(PasswordResetForm):
    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        return send_recovery_email(
            subject_template_name,
            email_template_name,
            context,
            from_email,
            to_email,
            html_email_template_name,
        )
