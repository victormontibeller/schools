"""Audiência e revalidação dos eventos escolares e financeiros do piloto."""

from core.permissions import can_access, role_name


class DomainEventAudience:
    @staticmethod
    def family_rows(student_ids, *, primary=False, financial=False):
        from guardians.selectors import GuardianSelector

        links = GuardianSelector().custodial_links_for_students(student_ids)
        if primary:
            links = links.filter(is_primary=True)
        rows = {}
        for link in links:
            user = link.guardian.user
            if role_name(user) != "GUARDIAN" or (
                financial and not can_access(user, "finance_billings", "view")
            ):
                continue
            row = rows.setdefault(user.pk, {"user": user, "student_ids": []})
            row["student_ids"].append(str(link.student_id))
        return list(rows.values())

    @staticmethod
    def class_student_ids(class_id=None):
        from classes.contracts import Enrollment

        query = Enrollment.objects.filter(status="ACTIVE", student__is_active=True)
        if class_id:
            query = query.filter(class_obj_id=class_id)
        return query.values_list("student_id", flat=True)

    @staticmethod
    def staff_calendar_users():
        from core.contracts import CustomUser

        users = CustomUser.objects.filter(
            is_active=True,
            role__name__in=["ADMIN", "COORDINATOR", "SECRETARY", "FINANCE", "TEACHER"],
        ).select_related("role")
        return [
            u
            for u in users
            if can_access(u, "academic_calendar", "view")
            and (
                role_name(u) != "TEACHER"
                or bool(getattr(u, "teacher_profile", None) and u.teacher_profile.is_active)
            )
        ]

    @classmethod
    def eligible(cls, delivery, user):
        from guardians.selectors import GuardianSelector

        if not user or not user.is_active or user.deleted_at:
            return False
        scope = delivery.payload.get("scope") or {}
        student_ids = scope.get("student_ids", [])
        custodial_ids = set()
        if student_ids:
            if role_name(user) != "GUARDIAN":
                return False
            custodial_ids = set(
                map(
                    str,
                    GuardianSelector()
                    .custodial_links_for_user(user.pk)
                    .filter(student_id__in=student_ids)
                    .values_list("student_id", flat=True),
                )
            )
            if not custodial_ids:
                return False
        source = delivery.source_type
        if source == "activity":
            from activities.contracts import Activity

            item = Activity.objects.filter(pk=delivery.source_id).first()
            return bool(
                item
                and can_access(user, "activities", "view")
                and item.class_obj_id
                and set(map(str, cls.class_student_ids(item.class_obj_id))) & custodial_ids
            )
        if source == "calendar_event":
            from academic_calendar.contracts import CalendarEvent

            item = CalendarEvent.objects.filter(pk=delivery.source_id, is_cancelled=False).first()
            if not item or not can_access(user, "academic_calendar", "view"):
                return False
            if student_ids:
                return bool(
                    item.is_public
                    and item.audience in {"ALL", "GUARDIANS", "CLASS"}
                    and (
                        item.audience != "CLASS"
                        or (
                            item.class_obj_id
                            and set(map(str, cls.class_student_ids(item.class_obj_id)))
                            & custodial_ids
                        )
                    )
                )
            return user.pk in {u.pk for u in cls.staff_calendar_users()} and item.audience in {
                "ALL",
                "TEACHERS",
            }
        if source == "enrollment_application":
            from enrollments.contracts import EnrollmentApplication

            item = EnrollmentApplication.objects.filter(pk=delivery.source_id).first()
            if (
                not item
                or not GuardianSelector()
                .custodial_links_for_user(user.pk)
                .filter(student_id=item.student_id, is_primary=True)
                .exists()
            ):
                return False
            return (
                item.status == "ENROLLED"
                if delivery.payload["event"] == "enrollment_confirmed"
                else item.status not in {"ENROLLED", "CANCELLED", "REJECTED"}
            )
        if source == "payment":
            from financeiro.contracts import PaymentRecord

            item = PaymentRecord.objects.filter(pk=delivery.source_id).first()
            expected = (
                "CONFIRMED" if delivery.payload["event"] == "payment_confirmed" else "REVERSED"
            )
            return bool(
                item and item.status == expected and can_access(user, "finance_billings", "view")
            )
        return False
