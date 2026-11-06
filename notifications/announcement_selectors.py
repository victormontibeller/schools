"""Audiência efetiva e autorização de cada revisão publicada."""

from django.db.models import OuterRef, Q, Subquery

from base.exceptions import ObjectNotFoundError, PermissionDeniedError
from base.selectors import BaseSelector, PageResult
from core.permissions import can_access, role_name
from notifications.models import Announcement, AnnouncementRecipient, AnnouncementRevision

STAFF_ROLES = {"ADMIN", "COORDINATOR", "SECRETARY", "FINANCE", "TEACHER"}


def can_manage_announcements(user, action="view"):
    return bool(
        user
        and user.is_active
        and (user.is_superuser or role_name(user) in {"ADMIN", "COORDINATOR"})
        and can_access(user, "notifications", action)
    )


class AnnouncementAudienceSelector:
    @staticmethod
    def form_options():
        from classes.contracts import Class
        from core.contracts import CustomUser
        from students.contracts import Student

        return {
            "class_ids": [
                (str(item.pk), str(item)) for item in Class.objects.filter(is_active=True)
            ],
            "user_ids": [
                (str(item.pk), item.get_full_name())
                for item in CustomUser.objects.exclude(role__isnull=True)
            ],
            "student_id": [("", "Sem contexto individual")]
            + [
                (str(item.pk), item.get_full_name())
                for item in Student.objects.filter(is_active=True)
            ],
        }

    @staticmethod
    def resolve(announcement):
        from classes.contracts import Enrollment
        from core.contracts import CustomUser
        from guardians.contracts import StudentGuardian

        result = {}
        links = StudentGuardian.objects.filter(
            is_active=True,
            has_custody=True,
            guardian__is_active=True,
            guardian__deleted_at__isnull=True,
            student__is_active=True,
            student__deleted_at__isnull=True,
        ).select_related("guardian__user__role")
        if announcement.audience == Announcement.Audience.CLASSES:
            students = Enrollment.objects.filter(
                class_obj_id__in=announcement.class_ids,
                status="ACTIVE",
                is_active=True,
                class_obj__is_active=True,
                class_obj__deleted_at__isnull=True,
            ).values("student_id")
            links = links.filter(student_id__in=students)
        elif announcement.audience == Announcement.Audience.INDIVIDUAL:
            links = links.filter(guardian__user_id__in=announcement.user_ids)
            if announcement.student_id:
                links = links.filter(student_id=announcement.student_id)
        if announcement.audience != Announcement.Audience.STAFF:
            for link in links:
                guardian = link.guardian
                user = guardian.user
                if user and (user.deleted_at or role_name(user) != "GUARDIAN"):
                    continue
                key = f"g:{guardian.pk}"
                row = result.setdefault(
                    key, {"guardian": guardian, "user": user, "student_ids": []}
                )
                row["student_ids"].append(str(link.student_id))
        if announcement.audience in {Announcement.Audience.STAFF, Announcement.Audience.INDIVIDUAL}:
            users = CustomUser.objects.filter(role__name__in=STAFF_ROLES).select_related("role")
            if announcement.audience == Announcement.Audience.INDIVIDUAL:
                users = users.filter(pk__in=announcement.user_ids)
            for user in users:
                if role_name(user) == "TEACHER":
                    profile = getattr(user, "teacher_profile", None)
                    if not profile or not profile.is_active or profile.deleted_at:
                        continue
                result[f"u:{user.pk}"] = {"guardian": None, "user": user, "student_ids": []}
        return list(result.values())

    @classmethod
    def preview(cls, announcement):
        rows = cls.resolve(announcement)
        return {
            "total": len(rows),
            "inactive": sum(not row["user"] or not row["user"].is_active for row in rows),
            "missing_email": sum(
                not (row["user"].email if row["user"] else row["guardian"].email) for row in rows
            ),
        }

    @staticmethod
    def current_user(receipt):
        from core.contracts import CustomUser
        from guardians.contracts import Guardian

        if receipt.guardian_id:
            guardian = Guardian.objects.filter(pk=receipt.guardian_id, is_active=True).first()
            user_id = guardian.user_id if guardian else None
        else:
            user_id = receipt.user_id
        return (
            CustomUser.objects.select_related("role").filter(pk=user_id).first()
            if user_id
            else None
        )

    @classmethod
    def is_eligible(cls, receipt, user=None):
        from guardians.contracts import StudentGuardian

        target = cls.current_user(receipt)
        if (
            not target
            or not target.is_active
            or target.deleted_at
            or (user and target.pk != user.pk)
        ):
            return False
        if receipt.guardian_id:
            return (
                role_name(target) == "GUARDIAN"
                and StudentGuardian.objects.filter(
                    guardian_id=receipt.guardian_id,
                    student_id__in=receipt.student_ids,
                    is_active=True,
                    has_custody=True,
                    student__is_active=True,
                    student__deleted_at__isnull=True,
                ).exists()
            )
        if role_name(target) not in STAFF_ROLES:
            return False
        if role_name(target) == "TEACHER":
            profile = getattr(target, "teacher_profile", None)
            return bool(profile and profile.is_active and not profile.deleted_at)
        return True


class AnnouncementSelector(BaseSelector):
    model_class = Announcement

    def receipt_for(self, revision, user):
        receipts = (
            AnnouncementRecipient.objects.filter(revision=revision)
            .filter(Q(user=user) | Q(guardian__user=user))
            .select_related("guardian__user__role", "user__role")
        )
        for receipt in receipts:
            if AnnouncementAudienceSelector.is_eligible(receipt, user):
                return receipt
        raise PermissionDeniedError("Esta revisão não está disponível para sua conta.")

    def visible_revisions(self, user):
        if can_manage_announcements(user):
            return AnnouncementRevision.objects.all()
        candidates = AnnouncementRecipient.objects.filter(
            Q(user=user) | Q(guardian__user=user)
        ).select_related("guardian__user__role", "user__role")
        ids = [
            r.revision_id for r in candidates if AnnouncementAudienceSelector.is_eligible(r, user)
        ]
        return AnnouncementRevision.objects.filter(pk__in=ids)

    def list_for_user(self, user, search="", order_by="-published_at", page=1):
        if can_manage_announcements(user):
            queryset = Announcement.objects.all()
        else:
            visible = self.visible_revisions(user)
            latest = visible.filter(announcement_id=OuterRef("pk")).order_by("-number")
            queryset = (
                Announcement.objects.filter(revisions__in=visible)
                .distinct()
                .annotate(
                    visible_title=Subquery(latest.values("title")[:1]),
                    visible_published_at=Subquery(latest.values("published_at")[:1]),
                    visible_audience=Subquery(latest.values("audience")[:1]),
                )
            )
            order_by = (
                order_by.replace("title", "visible_title")
                .replace("published_at", "visible_published_at")
                .replace("audience", "visible_audience")
            )
        if search:
            queryset = queryset.filter(
                **{
                    (
                        "title__icontains"
                        if can_manage_announcements(user)
                        else "visible_title__icontains"
                    ): search
                }
            )
        page = max(1, page)
        items = list(queryset.order_by(order_by)[(page - 1) * 20 : page * 20])
        for item in items:
            item.audience_label = Announcement.Audience(
                getattr(item, "visible_audience", item.audience)
            ).label
        return PageResult(
            items=items,
            total=queryset.count(),
            page=page,
            page_size=20,
        )

    def detail(self, announcement_id, user, revision_id=None):
        announcement = self.get_by_id(announcement_id)
        revisions = self.visible_revisions(user).filter(announcement=announcement)
        revision = (
            revisions.filter(pk=revision_id).first()
            if revision_id
            else revisions.order_by("-number").first()
        )
        manager = can_manage_announcements(user)
        if not revision and not manager:
            raise PermissionDeniedError("Comunicado fora da sua audiência.")
        receipt = None if manager or not revision else self.receipt_for(revision, user)
        return {
            "announcement": announcement,
            "revision": revision,
            "revisions": revisions,
            "receipt": receipt,
            "can_manage": manager,
            "can_edit": can_manage_announcements(user, "edit"),
            "preview": AnnouncementAudienceSelector.preview(announcement) if manager else None,
            "recipients": (
                revision.recipients.select_related("user", "guardian").prefetch_related(
                    "deliveries"
                )
                if manager and revision
                else []
            ),
            "attachments": (
                revision.attachments.all()
                if revision
                else announcement.attachments.filter(revisions__isnull=True)
            ),
        }

    @staticmethod
    def draft_attachments(announcement):
        return announcement.attachments.filter(pk__in=announcement.attachment_ids)

    def attachment_for(self, attachment_id, user):
        from notifications.models import AnnouncementAttachment

        try:
            attachment = AnnouncementAttachment.objects.get(pk=attachment_id)
        except AnnouncementAttachment.DoesNotExist:
            raise ObjectNotFoundError("AnnouncementAttachment", str(attachment_id)) from None
        if (
            not can_manage_announcements(user)
            and not attachment.revisions.filter(pk__in=self.visible_revisions(user)).exists()
        ):
            raise PermissionDeniedError("Anexo fora da sua audiência.")
        return attachment
