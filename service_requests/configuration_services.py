"""Configuração auditada e proteção de setores atendidos."""

from accounts.user_guards import lock_administrator_role
from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, PermissionDeniedError
from base.services import BaseService
from service_requests.calendar_services import ResponseDeadline
from service_requests.models import AdministrativeCalendar, DepartmentMembership, ServiceDepartment
from service_requests.selectors import (
    ServiceRequestSelector,
    ServiceStaffSelector,
    is_administrator,
)


class ServiceConfigurationService(BaseService):
    def _authorize(self):
        ServiceRequestSelector.assert_school_active()
        lock_administrator_role()
        self.user = ServiceRequestSelector.fresh_user(self.user.pk)
        if not is_administrator(self.user):
            raise PermissionDeniedError("Somente a Administração configura o atendimento.")

    def update_calendar(self, data):
        self._authorize()
        calendar, created = AdministrativeCalendar.objects.get_or_create(key="school")
        if not created and calendar.version != data["version"]:
            raise BusinessRuleViolationError("O calendário mudou. Recarregue a configuração.")
        closed = ResponseDeadline.validate(
            data["weekdays"], data["opens_at"], data["closes_at"], data["closed_dates"]
        )
        self.validate_required(data, ["immediate_contact"])
        calendar.weekdays = data["weekdays"]
        calendar.opens_at, calendar.closes_at = data["opens_at"], data["closes_at"]
        calendar.closed_dates = closed
        calendar.immediate_contact = data["immediate_contact"][:200]
        calendar.updated_by = self.user
        if created:
            calendar.created_by = self.user
        calendar.save()
        self._record_audit("INSERT" if created else "UPDATE", calendar)
        self._log("service_calendar_configured", calendar_id=str(calendar.pk))
        return calendar

    def update_department(self, code, *, enabled, user_ids, version):
        from core.contracts import CustomUser

        self._authorize()
        if code not in ServiceDepartment.Code.values:
            raise ObjectNotFoundError("ServiceDepartment", code)
        department, created = ServiceDepartment.objects.get_or_create(code=code)
        if not created and department.version != version:
            raise BusinessRuleViolationError("O setor mudou. Recarregue a configuração.")
        users = list(CustomUser.objects.filter(pk__in=user_ids).select_related("role"))
        if len(users) != len(set(user_ids)) or any(
            not ServiceStaffSelector.capable(u, code) for u in users
        ):
            raise BusinessRuleViolationError(
                "Selecione atendentes ativos com capacidade para este setor."
            )
        if enabled and not users:
            raise BusinessRuleViolationError(
                "Um setor habilitado exige atendente ativo e autorizado."
            )
        if (
            not enabled
            and department.requests.exclude(status__in=["RESOLVED", "CANCELLED"]).exists()
        ):
            raise BusinessRuleViolationError(
                "Resolva ou transfira as solicitações antes de desabilitar o setor."
            )
        selected = {u.pk for u in users}
        for member in department.memberships.filter(is_active=True):
            if member.user_id not in selected:
                self._deactivate(DepartmentMembership, member.pk, "DepartmentMembership")
        for user in users:
            member, new = DepartmentMembership.all_objects.get_or_create(
                department=department,
                user=user,
                defaults={"created_by": self.user, "updated_by": self.user},
            )
            if new:
                self._record_audit("INSERT", member)
            elif not member.is_active:
                member.restore(user=self.user)
                self._record_audit("RESTORE", member)
        department.enabled = enabled
        department.updated_by = self.user
        if created:
            department.created_by = self.user
        department.save()
        self._record_audit("INSERT" if created else "UPDATE", department)
        self._log("service_department_configured", department_id=str(department.pk))
        return department
