"""Tokens Django vinculados à escola, mantendo o formato nativo dos links."""

from django.contrib.auth.tokens import PasswordResetTokenGenerator

from base.context import current_tenant


class SchoolPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return super()._make_hash_value(user, timestamp) + "|" + current_tenant.get()


recovery_token_generator = SchoolPasswordResetTokenGenerator()
