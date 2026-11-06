"""Elegibilidade vigente de emissões duráveis e ativação de acesso."""

from urllib.parse import quote, urlencode

from django.core import signing
from django.urls import reverse
from django.utils import timezone

from base.exceptions import ObjectNotFoundError

INVITATION_SALTS = {
    "staff": "schools.staff-invite.v1",
    "teacher": "schools.teacher-invite.v1",
    "guardian": "schools.guardian-invite.v1",
}


class InvitationSelector:
    @staticmethod
    def guardian_has_custody(guardian_id):
        from guardians.contracts import StudentGuardian

        return StudentGuardian.objects.filter(
            guardian_id=guardian_id,
            guardian__is_active=True,
            guardian__deleted_at__isnull=True,
            student__is_active=True,
            student__deleted_at__isnull=True,
            has_custody=True,
            is_active=True,
        ).exists()

    @classmethod
    def is_current_token(cls, user, token, *, schema, kind):
        from accounts.invitation_tokens import INVITATION_TTL
        from tenancy.selectors import SchoolSelector

        if user is None or user.is_active or user.deleted_at or user.email_verified_at:
            return False
        try:
            SchoolSelector().get_active_by_schema(schema)
            payload = signing.loads(token, salt=INVITATION_SALTS[kind], max_age=INVITATION_TTL)
        except (ObjectNotFoundError, signing.BadSignature, ValueError, KeyError):
            return False
        if not isinstance(payload, dict) or (
            payload.get("schema") != schema
            or payload.get("user_id") != str(user.pk)
            or payload.get("nonce") != str(user.invitation_nonce)
            or not user.invitation_expires_at
            or user.invitation_expires_at <= timezone.now()
        ):
            return False
        if kind in {"guardian", "teacher"}:
            linked = getattr(user, f"{kind}_profile", None)
            if linked is None or not linked.is_active or linked.deleted_at:
                return False
            if kind == "guardian":
                if user.email.casefold() != linked.email.strip().casefold():
                    return False
                return (
                    bool(user.role and user.role.name == "GUARDIAN")
                    and payload.get("guardian_id") == str(linked.pk)
                    and cls.guardian_has_custody(linked.pk)
                )
            return bool(user.role and user.role.name == "TEACHER")
        return bool(
            user.role and user.role.name in {"ADMIN", "SECRETARY", "COORDINATOR", "FINANCE"}
        )

    @staticmethod
    def action_path(kind):
        if kind == "teacher":
            return reverse("teacher_invitation", kwargs={"token": "__token__"})
        return reverse(f"{kind}_invitation")

    @staticmethod
    def transport_url(delivery):
        scope = delivery.payload["scope"]
        if scope["invitation_kind"] == "teacher":
            return delivery.payload["url"].replace(
                "__token__", quote(scope["invitation_token"], safe="")
            )
        return delivery.payload["url"] + "?" + urlencode({"token": scope["invitation_token"]})
