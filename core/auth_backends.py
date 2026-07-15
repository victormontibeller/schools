"""Backend tenant-specific de autenticação sem permissões individuais legadas."""

from django.contrib.auth.backends import ModelBackend


class TenantAuthenticationBackend(ModelBackend):
    """Autentica no schema corrente; autorização pertence à matriz de papéis."""

    def user_can_authenticate(self, user) -> bool:
        """Recusa contas expiradas e contas DEMO ainda não verificadas."""
        if not super().user_can_authenticate(user) or getattr(user, "is_expired", False):
            return False
        access_mode = getattr(user, "access_mode", "STANDARD")
        return access_mode != "DEMO" or user.email_verified_at is not None

    def get_user_permissions(self, user_obj, obj=None) -> set[str]:
        """Impede que permissões individuais ampliem acessos do produto."""
        return set()

    def get_group_permissions(self, user_obj, obj=None) -> set[str]:
        """Impede que grupos Django concorram com os cinco papéis fixos."""
        return set()

    def has_perm(self, user_obj, perm, obj=None) -> bool:
        """Mantém somente o bypass nativo de superusuário para o Django Admin."""
        return bool(
            getattr(user_obj, "is_active", False) and getattr(user_obj, "is_superuser", False)
        )
