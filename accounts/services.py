"""AccountService: ciclo de vida dos usuários."""

import logging
import re

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.repositories import BaseRepository
from base.services import BaseService

logger = logging.getLogger(__name__)
_PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")


class AccountService(BaseService):

    def create_user(self, data: dict):
        """Cria um usuário validando senha, e-mail único e papel, e registra auditoria."""
        from core.models import CustomUser, Role

        self._validate_password(data.get("password", ""))

        if CustomUser.objects.filter(email=data["email"]).exists():
            raise ValidationError(errors={"email": ["Este e-mail já está em uso."]})

        role = None
        if role_id := data.get("role_id"):
            try:
                role = Role.objects.get(pk=role_id)
            except Role.DoesNotExist:
                raise ObjectNotFoundError("Role", str(role_id)) from None

        user = CustomUser.objects.create_user(
            email=data["email"],
            password=data["password"],
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            phone=data.get("phone", ""),
            role=role,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", user)
        self._log("Usuário criado", user_id=str(user.pk))
        return user

    def update_user(self, user_id, data: dict):
        """Atualiza campos permitidos do usuário e registra auditoria."""
        from core.models import CustomUser, Role

        class UserRepo(BaseRepository):
            model_class = CustomUser

        user = UserRepo().get_by_id(user_id)
        old = {"email": user.email, "first_name": user.first_name}
        allowed = {"first_name", "last_name", "phone", "is_active"}
        updates = {k: v for k, v in data.items() if k in allowed}
        if "role_id" in data:
            role_id = data["role_id"]
            if role_id:
                try:
                    updates["role"] = Role.objects.get(pk=role_id)
                except Role.DoesNotExist:
                    raise ObjectNotFoundError("Role", str(role_id)) from None
            else:
                updates["role"] = None
        updates["updated_by"] = self.user
        user = UserRepo().update(user, **updates)
        self._record_audit("UPDATE", user, old_values=old)
        self._log("Usuário atualizado", user_id=str(user.pk))
        return user

    def deactivate_user(self, user_id):
        """Aplica exclusão lógica no usuário e registra auditoria."""
        from core.models import CustomUser

        return self._deactivate(CustomUser, user_id, "CustomUser")

    def restore_user(self, user_id):
        """Reverte a exclusão lógica do usuário e registra auditoria."""
        from core.models import CustomUser

        try:
            user = CustomUser.all_objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            raise ObjectNotFoundError("CustomUser", str(user_id)) from None

        if not user.is_deleted:
            raise BusinessRuleViolationError("Usuário não está desativado.")
        user.restore(user=self.user)
        self._record_audit("RESTORE", user)
        return user

    def change_password(self, user_id, current_password: str, new_password: str):
        """Altera a senha do usuario, validando senha atual e nova senha.

        Raises:
            ValidationError: se a senha atual estiver incorreta ou a nova for fraca.
        """
        from core.models import CustomUser

        try:
            user = CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            raise ObjectNotFoundError("CustomUser", str(user_id)) from None

        if not user.check_password(current_password):
            raise ValidationError(errors={"current_password": ["Senha atual incorreta."]})

        self._validate_password(new_password)
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        self._record_audit(
            "UPDATE", user, old_values={"password": "***"}, new_values={"password": "***"}
        )

    @staticmethod
    def _validate_password(password: str) -> None:
        if not _PASSWORD_RE.match(password or ""):
            raise ValidationError(
                errors={
                    "password": [
                        "A senha deve ter no mínimo 8 caracteres, contendo letras e números."
                    ]
                }
            )
