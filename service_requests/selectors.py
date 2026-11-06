"""Escopo privado, capacidade vigente e consultas operacionais do atendimento."""

from django.db.models import F, Q
from django.utils import timezone

from base.context import active_tenant_schema
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, PermissionDeniedError
from base.selectors import PageResult
from core.permissions import can_access, role_name
from core.request_access_catalog import DEPARTMENT_MODULES
from service_requests.models import (
    AdministrativeCalendar,
    DepartmentMembership,
    RequestAttachment,
    ServiceDepartment,
    ServiceRequest,
)


def is_administrator(user):
    return bool(user and user.is_active and (user.is_superuser or role_name(user) == "ADMIN"))


class ServiceStaffSelector:
    @staticmethod
    def capable(user, code, action="edit"):
        return bool(
            user
            and user.is_active
            and not user.deleted_at
            and role_name(user) in {"ADMIN", "SECRETARY", "COORDINATOR", "FINANCE"}
            and user.has_usable_password()
            and can_access(user, "service_requests", "view")
            and can_access(user, "service_requests", action)
            and can_access(user, DEPARTMENT_MODULES[code], action)
        )

    @classmethod
    def attendants(cls, department):
        from core.contracts import CustomUser

        users = CustomUser.objects.filter(
            service_memberships__department=department,
            service_memberships__is_active=True,
            service_memberships__deleted_at__isnull=True,
        ).select_related("role")
        return [user for user in users if cls.capable(user, department.code)]

    @classmethod
    def validate_departments_staffed(cls, changing_user=None, updates=None):
        """Chamado sob o lock ADMIN por contas, matriz e configuração de atendimento."""
        import copy

        for department in ServiceDepartment.objects.filter(enabled=True):
            active = cls.attendants(department)
            if changing_user:
                active = [user for user in active if user.pk != changing_user.pk]
                candidate = copy.copy(changing_user)
                for key, value in (updates or {}).items():
                    setattr(candidate, key, value)
                candidate._role_access_cache = None
                if (
                    cls.capable(candidate, department.code)
                    and DepartmentMembership.objects.filter(
                        department=department,
                        user=changing_user,
                    ).exists()
                ):
                    active.append(candidate)
            if not active:
                raise BusinessRuleViolationError(
                    "Mantenha um atendente ativo e autorizado em cada setor habilitado."
                )

    @staticmethod
    def configuration():
        from core.contracts import CustomUser

        calendar = AdministrativeCalendar.objects.first() or AdministrativeCalendar()
        return {
            "calendar": calendar,
            "departments": [
                ServiceDepartment.objects.prefetch_related("memberships__user")
                .filter(code=code)
                .first()
                or ServiceDepartment(code=code)
                for code in ServiceDepartment.Code.values
            ],
            "user_choices": [
                (str(user.pk), user.get_full_name())
                for user in CustomUser.objects.filter(
                    role__name__in=["ADMIN", "SECRETARY", "COORDINATOR", "FINANCE"]
                )
            ],
        }


class ServiceRequestSelector:
    @staticmethod
    def assert_school_active():
        from tenancy.selectors import SchoolSelector

        return SchoolSelector().get_active_by_schema(active_tenant_schema())

    @staticmethod
    def fresh_user(user_id):
        from core.contracts import CustomUser

        return CustomUser.objects.select_related("role").filter(pk=user_id, is_active=True).first()

    @classmethod
    def can_read(cls, request, user):
        from guardians.selectors import GuardianSelector

        user = cls.fresh_user(user.pk) if user else None
        if not user or not can_access(user, "service_requests", "view"):
            return False
        if is_administrator(user):
            return True
        if role_name(user) == "GUARDIAN":
            return request.author_id == user.pk and GuardianSelector().user_can_access_student(
                user.pk, request.student_id
            )
        return (
            ServiceStaffSelector.capable(user, request.department.code, "view")
            and DepartmentMembership.objects.filter(
                department_id=request.department_id,
                user=user,
            ).exists()
        )

    @classmethod
    def can_respond(cls, request, user):
        user = cls.fresh_user(user.pk) if user else None
        return (
            cls.can_read(request, user)
            and can_access(user, "service_requests", "edit")
            and (
                is_administrator(user)
                or role_name(user) == "GUARDIAN"
                or ServiceStaffSelector.capable(cls.fresh_user(user.pk), request.department.code)
            )
        )

    @classmethod
    def can_public_respond(cls, request, user):
        user = cls.fresh_user(getattr(user, "pk", None))
        if not cls.can_respond(request, user):
            return False
        if role_name(user) == "GUARDIAN":
            return True
        return DepartmentMembership.objects.filter(
            department_id=request.department_id, user=user
        ).exists()

    def get_for_user(self, pk, user):
        self.assert_school_active()
        try:
            item = ServiceRequest.objects.select_related(
                "department", "student", "author", "attendant"
            ).get(pk=pk)
        except ServiceRequest.DoesNotExist:
            raise ObjectNotFoundError("ServiceRequest", str(pk)) from None
        if not self.can_read(item, user):
            raise PermissionDeniedError("Solicitação fora do seu escopo de atendimento.")
        return item

    def list_for_user(self, user, page=1, search=""):
        self.assert_school_active()
        user = self.fresh_user(getattr(user, "pk", None))
        if not user or not can_access(user, "service_requests", "view"):
            raise PermissionDeniedError("Sem acesso ao atendimento.")
        query = ServiceRequest.objects.select_related(
            "department", "student", "author", "attendant"
        )
        if role_name(user) == "GUARDIAN":
            from guardians.selectors import GuardianSelector

            query = query.filter(
                author=user,
                student_id__in=GuardianSelector().custodial_student_ids_for_user(user.pk),
            )
        elif not is_administrator(user):
            codes = [
                code
                for code in DEPARTMENT_MODULES
                if ServiceStaffSelector.capable(user, code, "view")
            ]
            query = query.filter(
                department__code__in=codes,
                department__memberships__user=user,
                department__memberships__is_active=True,
                department__memberships__deleted_at__isnull=True,
            )
        if search:
            query = query.filter(Q(protocol__icontains=search) | Q(subject__icontains=search))
        page = max(1, int(page))
        items = list(
            query.order_by("first_response_at", "response_due_at")[(page - 1) * 20 : page * 20]
        )
        for item in items:
            item.response_overdue = self.is_overdue(item)
        return PageResult(
            items=items,
            total=query.count(),
            page=page,
            page_size=20,
        )

    @staticmethod
    def is_overdue(item):
        return (
            item.status not in {"RESOLVED", "CANCELLED"}
            and not item.first_response_at
            and item.response_due_at < timezone.now()
        )

    def detail(self, pk, user):
        item = self.get_for_user(pk, user)
        calendar = AdministrativeCalendar.objects.first() or AdministrativeCalendar()
        return {
            "ticket": item,
            "messages_list": item.messages.select_related("author").prefetch_related("attachments"),
            "history": item.transitions.select_related("created_by"),
            "calendar": calendar,
            "overdue": self.is_overdue(item),
            "can_respond": self.can_respond(item, user),
            "can_public_respond": self.can_public_respond(item, user),
            "is_author": item.author_id == user.pk,
            "is_admin": is_administrator(user),
            "is_staff": role_name(user) != "GUARDIAN",
            "department_choices": [
                (str(d.pk), str(d)) for d in ServiceDepartment.objects.filter(enabled=True)
            ],
            "attendant_choices": [("", "Sem atribuição")]
            + [
                (str(u.pk), u.get_full_name())
                for u in ServiceStaffSelector.attendants(item.department)
            ],
        }

    @staticmethod
    def create_options(user):
        from guardians.selectors import GuardianSelector
        from students.contracts import Student

        return {
            "student_choices": [
                (str(s.pk), s.get_full_name())
                for s in Student.objects.filter(
                    pk__in=GuardianSelector().custodial_student_ids_for_user(user.pk)
                )
            ],
            "department_choices": [
                (str(d.pk), str(d)) for d in ServiceDepartment.objects.filter(enabled=True)
            ],
        }

    def attachment_for(self, pk, user):
        try:
            attachment = RequestAttachment.objects.select_related(
                "message__request__department"
            ).get(pk=pk)
        except RequestAttachment.DoesNotExist:
            raise ObjectNotFoundError("RequestAttachment", str(pk)) from None
        self.get_for_user(attachment.message.request_id, user)
        return attachment

    @staticmethod
    def overdue_ids():
        return (
            ServiceRequest.objects.filter(
                first_response_at__isnull=True,
                response_due_at__lt=timezone.now(),
                status__in=["OPEN", "IN_PROGRESS", "WAITING_FAMILY"],
            )
            .exclude(overdue_notified_cycle=F("cycle"))
            .values_list("pk", flat=True)[:100]
        )
