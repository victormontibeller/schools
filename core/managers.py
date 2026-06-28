"""UserManager: manager para CustomUser com autenticação por e-mail."""

from django.contrib.auth.models import BaseUserManager


class UserManager(BaseUserManager):
    """Manager do `CustomUser` com autenticação por e-mail e soft-delete."""

    def get_queryset(self):
        """Filtra usuários não excluídos logicamente."""
        return super().get_queryset().filter(deleted_at__isnull=True)

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        """Cria um usuário comum normalizando o e-mail e aplicando a senha."""
        if not email:
            raise ValueError("O campo e-mail é obrigatório.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        """Cria um superusuário garantindo flags de staff e superuser."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email, password, **extra_fields)
