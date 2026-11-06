"""Comandos privados de solicitação, resposta e transição com versão esperada."""

from django.utils import timezone

from accounts.user_guards import lock_administrator_role
from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from base.services import BaseService, service_command
from core.permissions import role_name
from service_requests.calendar_services import ResponseDeadline
from service_requests.models import (
    AdministrativeCalendar,
    RequestAttachment,
    RequestMessage,
    RequestSequence,
    RequestTransition,
    ServiceDepartment,
    ServiceRequest,
)
from service_requests.selectors import (
    ServiceRequestSelector,
    ServiceStaffSelector,
    is_administrator,
)


class ServiceRequestService(BaseService):
    def _locked(self, pk, version):
        lock_administrator_role()
        self.user = ServiceRequestSelector.fresh_user(self.user.pk)
        if not self.user:
            raise PermissionDeniedError("Conta inativa.")
        ServiceRequestSelector().get_for_user(pk, self.user)
        ticket = ServiceRequest.objects.select_for_update().get(pk=pk)
        try:
            valid = ticket.version == int(version)
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise BusinessRuleViolationError("A solicitação mudou. Recarregue antes de continuar.")
        if not ServiceRequestSelector.can_respond(ticket, self.user):
            raise PermissionDeniedError("Sem capacidade de resposta neste setor.")
        return ticket

    def _history(self, ticket, event, before_status="", before_department=""):
        entry = RequestTransition.objects.create(
            request=ticket,
            event=event,
            from_status=before_status,
            to_status=ticket.status,
            from_department=before_department,
            to_department=ticket.department.code,
            cycle=ticket.cycle,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", entry)
        self._record_audit("UPDATE", ticket)
        self._log(
            "service_request_transition", request_id=str(ticket.pk), event=event, cycle=ticket.cycle
        )

    def _message(self, ticket, body, uploads):
        from django.core.exceptions import ValidationError as DjangoValidationError

        from base.upload_validators import validate_document_upload

        self.validate_required({"body": body}, ["body"])
        if len(body) > 20000 or len(uploads) > 3:
            raise ValidationError(errors={"body": ["Use até 20000 caracteres e três anexos."]})
        for upload in uploads:
            try:
                validate_document_upload(upload)
            except DjangoValidationError as exc:
                raise ValidationError(errors={"file": exc.messages}) from None
        message = RequestMessage.objects.create(
            request=ticket,
            author=self.user,
            body=body,
            is_staff_response=role_name(self.user) != "GUARDIAN",
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", message)
        for upload in uploads:
            attachment = RequestAttachment(
                message=message, created_by=self.user, updated_by=self.user
            )
            attachment.file.save(upload.name, upload, save=False)
            self._uploads.append(attachment.file)
            attachment.save()
            self._record_audit("INSERT", attachment)
        self._log(
            "service_request_message_created", request_id=str(ticket.pk), entry_id=str(message.pk)
        )
        return message

    def _cleanup_uploads(self):
        for file in self._uploads:
            file.storage.delete(file.name)

    def create_request(self, data, uploads=()):
        from guardians.selectors import GuardianSelector
        from service_requests.event_services import RequestEventService
        from students.contracts import ImportUsageService

        ServiceRequestSelector.assert_school_active()
        self.validate_required(data, ["subject", "body", "department_id", "student_id"])
        ImportUsageService(user=self.user).seal_for_use(student_ids=[data["student_id"]])
        lock_administrator_role()
        actor = ServiceRequestSelector.fresh_user(self.user.pk)
        self.user = actor
        if role_name(actor) != "GUARDIAN" or not GuardianSelector().user_can_access_student(
            actor.pk, data.get("student_id")
        ):
            raise PermissionDeniedError(
                "Somente o responsável com guarda pode abrir a solicitação."
            )
        if not AdministrativeCalendar.objects.exclude(immediate_contact="").exists():
            raise BusinessRuleViolationError(
                "A escola deve configurar o contato imediato antes de abrir atendimento."
            )
        self.validate_required(data, ["subject", "body", "department_id", "student_id"])
        if len(data["subject"]) > 180:
            raise ValidationError(errors={"subject": ["Assunto deve ter até 180 caracteres."]})
        try:
            department = ServiceDepartment.objects.get(pk=data["department_id"], enabled=True)
        except ServiceDepartment.DoesNotExist:
            raise ObjectNotFoundError("ServiceDepartment", str(data["department_id"])) from None
        if not ServiceStaffSelector.attendants(department):
            raise BusinessRuleViolationError(
                "O setor está sem atendimento. Use o contato imediato da escola."
            )
        now = timezone.now()
        sequence, _ = RequestSequence.objects.get_or_create(year=timezone.localdate().year)
        protocol = f"ATE-{sequence.year}-{sequence.next_number:06d}"
        sequence.next_number += 1
        sequence.save()
        self._record_audit("UPDATE", sequence)
        self._uploads = []
        try:
            ticket = ServiceRequest.objects.create(
                protocol=protocol,
                author=actor,
                student_id=data["student_id"],
                department=department,
                subject=data["subject"],
                cycle_opened_at=now,
                response_due_at=ResponseDeadline.calculate(now),
                created_by=self.user,
                updated_by=self.user,
            )
            self._record_audit("INSERT", ticket)
            self._message(ticket, data["body"], uploads)
            self._history(ticket, "opened")
            RequestEventService(user=self.user).emit_request_event(
                ticket, "request_opened", str(ticket.pk)
            )
            return ticket
        except Exception:
            self._cleanup_uploads()
            raise

    def add_request_message(self, pk, *, version, body, uploads=()):
        from service_requests.event_services import RequestEventService

        ticket = self._locked(pk, version)
        if ticket.status in {"RESOLVED", "CANCELLED"}:
            raise BusinessRuleViolationError("Reabra uma solicitação resolvida antes de responder.")
        if not ServiceRequestSelector.can_public_respond(ticket, self.user):
            raise PermissionDeniedError("Vincule um atendente ao setor antes da resposta pública.")
        self._uploads = []
        try:
            message = self._message(ticket, body, uploads)
            before = ticket.status
            if message.is_staff_response:
                if not ticket.first_response_at:
                    ticket.first_response_at = timezone.now()
                ticket.status = "WAITING_FAMILY"
                if not ticket.attendant_id:
                    ticket.attendant = self.user
            else:
                ticket.status = "IN_PROGRESS"
            ticket.updated_by = self.user
            ticket.save()
            self._history(ticket, "response", before)
            RequestEventService(user=self.user).emit_request_event(
                ticket, "request_response", str(message.pk), to_author=message.is_staff_response
            )
            return message
        except Exception:
            self._cleanup_uploads()
            raise

    def update_request_status(self, pk, *, version, status):
        ticket = self._locked(pk, version)
        if status not in ServiceRequest.Status.values or status == "OPEN":
            raise ValidationError(errors={"status": ["Transição inválida."]})
        if role_name(self.user) == "GUARDIAN" and status != "CANCELLED":
            raise PermissionDeniedError("A família pode cancelar ou reabrir sua solicitação.")
        if ticket.status in {"RESOLVED", "CANCELLED"}:
            raise BusinessRuleViolationError("A solicitação está encerrada.")
        if status in {"RESOLVED", "WAITING_FAMILY"} and not ticket.first_response_at:
            raise BusinessRuleViolationError(
                "Envie uma resposta pública antes de concluir ou aguardar a família."
            )
        before = ticket.status
        ticket.status = status
        ticket.updated_by = self.user
        ticket.save()
        self._history(ticket, "status", before)
        return ticket

    @service_command
    def reopen_request(self, pk, *, version):
        from service_requests.event_services import RequestEventService

        ticket = self._locked(pk, version)
        if ticket.author_id != self.user.pk or role_name(self.user) != "GUARDIAN":
            raise PermissionDeniedError("Somente o autor pode reabrir a solicitação.")
        if ticket.status != "RESOLVED":
            raise BusinessRuleViolationError("Somente uma solicitação resolvida pode ser reaberta.")
        if not ticket.department.enabled or not ServiceStaffSelector.attendants(ticket.department):
            raise BusinessRuleViolationError("O setor está indisponível. Use o contato imediato.")
        ticket.cycle += 1
        ticket.status = "OPEN"
        ticket.cycle_opened_at = timezone.now()
        ticket.response_due_at = ResponseDeadline.calculate(ticket.cycle_opened_at)
        ticket.first_response_at = None
        ticket.updated_by = self.user
        ticket.save()
        self._history(ticket, "reopened", "RESOLVED")
        RequestEventService(user=self.user).emit_request_event(
            ticket, "request_reopened", str(ticket.cycle)
        )
        return ticket

    def transfer_request(self, pk, *, version, department_id):
        ticket = self._locked(pk, version)
        if not is_administrator(self.user):
            raise PermissionDeniedError("Somente a Administração transfere solicitações.")
        try:
            target = ServiceDepartment.objects.get(pk=department_id, enabled=True)
        except ServiceDepartment.DoesNotExist:
            raise ObjectNotFoundError("ServiceDepartment", str(department_id)) from None
        if not ServiceStaffSelector.attendants(target):
            raise BusinessRuleViolationError("O setor de destino precisa de atendente ativo.")
        if ticket.status in {"RESOLVED", "CANCELLED"}:
            raise BusinessRuleViolationError("Reabra a solicitação antes de transferir o setor.")
        before = ticket.department.code
        ticket.department = target
        ticket.attendant = None
        ticket.updated_by = self.user
        ticket.save()
        self._history(ticket, "transferred", ticket.status, before)
        from service_requests.event_services import RequestEventService

        RequestEventService(user=self.user).emit_request_event(
            ticket, "request_transferred", str(ticket.version), to_author=False
        )
        return ticket

    def assign_request(self, pk, *, version, attendant_id):
        ticket = self._locked(pk, version)
        if role_name(self.user) == "GUARDIAN":
            raise PermissionDeniedError("A família não atribui atendentes.")
        users = {str(u.pk): u for u in ServiceStaffSelector.attendants(ticket.department)}
        if attendant_id and str(attendant_id) not in users:
            raise PermissionDeniedError("Atendente fora do setor ou sem capacidade.")
        ticket.attendant = users.get(str(attendant_id))
        ticket.updated_by = self.user
        ticket.save()
        self._history(ticket, "assigned", ticket.status)
        return ticket
