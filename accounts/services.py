"""AccountService: ciclo de vida dos usuários."""

import logging
import re
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.db import connection, transaction
from django.utils import timezone

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.repositories import BaseRepository
from base.services import BaseService

logger = logging.getLogger(__name__)
_PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")
DEMO_VERIFY_SALT = "schools.demo-signup.v1"
DEMO_VERIFY_TTL_SECONDS = 30 * 60


class AccountService(BaseService):

    def create_platform_user(self, data: dict):
        """Cria operador persistente no schema público."""
        from core.models import CustomUser

        self._validate_platform_operator()
        self.validate_required(data, ["first_name", "last_name", "email", "password"])
        self._validate_password(data["password"])
        email = data["email"].strip().lower()
        if CustomUser.all_objects.filter(email=email, deleted_at__isnull=True).exists():
            raise ValidationError(errors={"email": ["Este e-mail já está em uso."]})
        user = CustomUser.objects.create_user(
            email=email,
            password=data["password"],
            first_name=data["first_name"].strip(),
            last_name=data["last_name"].strip(),
            is_staff=True,
            is_superuser=bool(data.get("is_superuser")),
            access_mode=CustomUser.AccessMode.STANDARD,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", user)
        self._log("platform_user_created", user_id=str(user.pk))
        return user

    def update_platform_user(self, user_id, data: dict):
        """Atualiza status e nível de acesso de um operador público."""
        from core.models import CustomUser

        self._validate_platform_operator()
        try:
            user = CustomUser.all_objects.get(
                pk=user_id,
                access_mode=CustomUser.AccessMode.STANDARD,
                deleted_at__isnull=True,
            )
        except CustomUser.DoesNotExist:
            raise ObjectNotFoundError("CustomUser", str(user_id)) from None
        if user.pk == self.user.pk and (
            not data.get("is_active", user.is_active)
            or not data.get("is_superuser", user.is_superuser)
        ):
            raise BusinessRuleViolationError(
                "Você não pode remover seu próprio acesso administrativo."
            )
        old = self._snapshot(user, ["is_active", "is_superuser"])
        user.first_name = data.get("first_name", user.first_name).strip()
        user.last_name = data.get("last_name", user.last_name).strip()
        user.is_active = bool(data.get("is_active", user.is_active))
        user.is_superuser = bool(data.get("is_superuser", user.is_superuser))
        user.is_staff = True
        user.updated_by = self.user
        user.save()
        self._record_audit("UPDATE", user, old_values=old)
        self._log("platform_user_updated", user_id=str(user.pk))
        return user

    def _validate_platform_operator(self) -> None:
        """Restringe operadores públicos a superusuários do schema public."""
        if self.user is None or not self.user.is_superuser:
            from base.exceptions import PermissionDeniedError

            raise PermissionDeniedError("Somente superusuários podem administrar operadores.")
        if not settings.TESTING and getattr(connection, "schema_name", "public") != "public":
            raise BusinessRuleViolationError(
                "Operadores só podem ser administrados no schema public."
            )

    def create_demo_user(self, data: dict, verification_url_builder):
        """Cria conta DEMO inativa e agenda a confirmação por e-mail."""
        from core.models import CustomUser, Role

        demo_schema = getattr(settings, "DEMO_SCHEMA_NAME", "demo")
        if getattr(connection, "schema_name", demo_schema) != demo_schema and not settings.TESTING:
            raise BusinessRuleViolationError("Cadastro disponível apenas no ambiente DEMO.")
        self.validate_required(data, ["first_name", "last_name", "email", "password"])
        self._validate_password(data["password"])
        email = data["email"].strip().lower()
        if CustomUser.all_objects.filter(email=email, deleted_at__isnull=True).exists():
            raise ValidationError(errors={"email": ["Este e-mail já possui uma conta no DEMO."]})
        role, _ = Role.objects.get_or_create(
            name=Role.Name.COORDINATOR,
            defaults={"created_by": self.user, "updated_by": self.user},
        )
        user = CustomUser.objects.create_user(
            email=email,
            password=data["password"],
            first_name=data["first_name"].strip(),
            last_name=data["last_name"].strip(),
            role=role,
            access_mode=CustomUser.AccessMode.DEMO,
            is_active=False,
            created_by=self.user,
            updated_by=self.user,
        )
        token = signing.dumps({"user_id": str(user.pk)}, salt=DEMO_VERIFY_SALT, compress=True)
        verification_url = verification_url_builder(token)

        from accounts.tasks import send_demo_verification_task

        transaction.on_commit(
            lambda: send_demo_verification_task.delay(
                demo_schema,
                str(user.pk),
                verification_url,
            )
        )
        self._record_audit("INSERT", user)
        self._log("demo_user_created", user_id=str(user.pk))
        return user

    def verify_demo_user(self, token: str):
        """Ativa conta DEMO após validar token assinado de uso único."""
        from core.models import CustomUser

        try:
            payload = signing.loads(
                token,
                salt=DEMO_VERIFY_SALT,
                max_age=DEMO_VERIFY_TTL_SECONDS,
            )
        except signing.BadSignature as exc:
            raise BusinessRuleViolationError("Link de confirmação inválido ou expirado.") from exc
        try:
            user = CustomUser.all_objects.get(
                pk=payload.get("user_id"), access_mode=CustomUser.AccessMode.DEMO
            )
        except CustomUser.DoesNotExist:
            raise ObjectNotFoundError("CustomUser", str(payload.get("user_id"))) from None
        if user.email_verified_at:
            raise BusinessRuleViolationError("Este link de confirmação já foi utilizado.")
        now = timezone.now()
        user.email_verified_at = now
        user.expires_at = now + timedelta(days=7)
        user.is_active = True
        user.updated_by = user
        user.save(
            update_fields=[
                "email_verified_at",
                "expires_at",
                "is_active",
                "updated_by",
                "updated_at",
            ]
        )
        self._record_audit("UPDATE", user, old_values={"email_verified_at": None})
        return user

    def expire_demo_users(self) -> int:
        """Anonimiza e desativa contas DEMO expiradas no schema corrente."""
        from core.models import CustomUser

        expired = list(
            CustomUser.all_objects.filter(
                access_mode=CustomUser.AccessMode.DEMO,
                expires_at__lte=timezone.now(),
                deleted_at__isnull=True,
            )
        )
        for user in expired:
            from notifications.models import MessageLog

            MessageLog.all_objects.filter(recipient=user).update(recipient_address="[REDACTED]")
            user.email = f"expired-{user.pk}@anonymous.invalid"
            user.first_name = "Conta"
            user.last_name = "Expirada"
            user.phone = ""
            user.set_unusable_password()
            user.save(update_fields=["email", "first_name", "last_name", "phone", "password"])
            user.soft_delete()
            self._record_audit("DELETE", user)
        if expired:
            self._log("demo_users_expired", count=len(expired))
        return len(expired)

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
        allowed = {"first_name", "last_name", "phone", "avatar", "is_active"}
        updates = {
            key: value
            for key, value in data.items()
            if key in allowed and (key != "avatar" or value is not None)
        }
        if "email" in data:
            email = data["email"].strip().lower()
            if (
                CustomUser.all_objects.filter(email__iexact=email, deleted_at__isnull=True)
                .exclude(pk=user.pk)
                .exists()
            ):
                raise ValidationError(errors={"email": ["Este e-mail já está em uso."]})
            updates["email"] = email
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
