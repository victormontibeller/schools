"""Backends de autenticação e permissões por papel."""

from django.contrib.auth.backends import ModelBackend

DEMO_PERMISSION_ALLOWLIST = frozenset(
    {
        "agenda.view_timeslot",
        "agenda.add_scheduleentry",
        "agenda.change_scheduleentry",
        "agenda.view_scheduleentry",
        "activities.add_activity",
        "activities.change_activity",
        "activities.view_activity",
        "activities.add_activityscore",
        "activities.change_activityscore",
        "activities.view_activityscore",
        "attendance.add_attendancerecord",
        "attendance.change_attendancerecord",
        "attendance.view_attendancerecord",
        "attendance.add_attendanceentry",
        "attendance.change_attendanceentry",
        "attendance.view_attendanceentry",
        "classes.add_class",
        "classes.change_class",
        "classes.view_class",
        "classes.add_enrollment",
        "classes.change_enrollment",
        "classes.view_enrollment",
        "enrollments.add_enrollmentapplication",
        "enrollments.change_enrollmentapplication",
        "enrollments.view_enrollmentapplication",
    }
)


class RolePermissionBackend(ModelBackend):
    """Autentica no schema corrente e agrega permissões do papel do usuário."""

    def user_can_authenticate(self, user) -> bool:
        """Recusa contas expiradas e contas DEMO ainda não verificadas."""
        if not super().user_can_authenticate(user) or getattr(user, "is_expired", False):
            return False
        access_mode = getattr(user, "access_mode", "STANDARD")
        return access_mode != "DEMO" or user.email_verified_at is not None

    def get_user_permissions(self, user_obj, obj=None) -> set[str]:
        """Une permissões diretas às permissões do papel tenant-specific."""
        permissions = set(super().get_user_permissions(user_obj, obj=obj))
        if obj is None and getattr(user_obj, "role_id", None):
            permissions.update(
                f"{app_label}.{codename}"
                for app_label, codename in user_obj.role.permissions.values_list(
                    "content_type__app_label", "codename"
                )
            )
        if getattr(user_obj, "access_mode", "STANDARD") == "DEMO":
            permissions.intersection_update(DEMO_PERMISSION_ALLOWLIST)
        return permissions
