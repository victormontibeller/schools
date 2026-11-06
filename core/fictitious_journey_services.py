"""Exercita jornadas fictícias pelo mesmo domínio utilizado pelas telas."""

import datetime as dt
from decimal import Decimal

from base.exceptions import BusinessRuleViolationError
from base.services import BaseService, system_command
from core.fictitious import require_fictitious
from core.fictitious_selectors import FictitiousSelector


class FictitiousJourneyService(BaseService):
    @system_command
    def create_journey_evidence(self, population):
        from financeiro.services import FinanceService, PaymentService
        from notifications.announcement_services import AnnouncementService
        from service_requests.models import ServiceDepartment
        from service_requests.selectors import ServiceRequestSelector
        from service_requests.services import ServiceRequestService
        from student_diary.contracts import DiarySheet
        from student_diary.services import StudentDiaryService
        from student_diary.workflow_services import DiaryWorkflowService

        require_fictitious()
        people, children = population["people"], population["students"]
        today = dt.date.today()
        publications = []
        for index, class_obj in enumerate(population["classes"], 1):
            teacher = people[f"TEACHER{index}"]
            StudentDiaryService(user=teacher).save_daily_diaries(
                class_obj.pk, today, FictitiousSelector.diary_payload(class_obj)
            )
            sheet = DiarySheet.objects.get(class_obj=class_obj, date=today)
            workflow = DiaryWorkflowService(user=teacher)
            review = DiaryWorkflowService(user=people["COORDINATOR"])
            workflow.submit_sheet(sheet.pk)
            review.request_changes(
                sheet.pk, "Exercício fictício: conferir o registro antes da publicação."
            )
            workflow.submit_sheet(sheet.pk)
            publication = review.approve_sheet(sheet.pk)
            publications.append(str(publication.pk))
        communication = AnnouncementService(user=people["COORDINATOR"])
        draft = communication.create_announcement(
            {
                "title": "Bem-vindos ao ensaio fictício",
                "body": "Este comunicado é exclusivamente um exercício de treinamento.",
                "audience": "FAMILIES",
                "send_email": True,
                "requires_acknowledgement": True,
            }
        )
        revision = communication.publish_announcement(draft.pk, version=draft.version)
        if revision.recipients.filter(user=people["G1"]).count() != 1:
            raise BusinessRuleViolationError("Deduplicação de irmãos falhou no ensaio.")
        AnnouncementService(user=people["G1"]).mark_announcement_viewed(revision.pk)
        AnnouncementService(user=people["G1"]).acknowledge_announcement(revision.pk)
        draft.refresh_from_db()
        draft = communication.open_announcement_correction(draft.pk, version=draft.version)
        correction = communication.publish_announcement(draft.pk, version=draft.version)
        if correction.recipients.filter(acknowledged_at__isnull=False).exists():
            raise BusinessRuleViolationError("Ciência não pode ser herdada na correção.")
        department = ServiceDepartment.objects.get(code="SECRETARY")
        ticket = ServiceRequestService(user=people["G1"]).create_request(
            {
                "student_id": children["S1"].pk,
                "department_id": department.pk,
                "subject": "Treinamento de atendimento privado",
                "body": "Mensagem fictícia de abertura.",
            }
        )
        if ServiceRequestSelector.can_read(ticket, people["G2"]):
            raise BusinessRuleViolationError("Outro responsável recebeu acesso indevido.")
        support = ServiceRequestService(user=people["SECRETARY"])
        support.add_request_message(
            ticket.pk, version=ticket.version, body="Resposta fictícia da Secretaria."
        )
        ticket.refresh_from_db()
        support.update_request_status(ticket.pk, version=ticket.version, status="RESOLVED")
        ticket.refresh_from_db()
        ServiceRequestService(user=people["G1"]).reopen_request(ticket.pk, version=ticket.version)
        finance = FinanceService(user=people["FINANCE"])
        billing = finance.create_ad_hoc_billing(
            {
                "student_id": children["S1"].pk,
                "description": "Cobrança fictícia para treinamento",
                "amount": Decimal("100.00"),
                "due_date": today,
            }
        )
        payments = PaymentService(user=people["FINANCE"])
        payment = payments.create_payment(
            allocations=[{"billing_id": billing.pk, "amount": Decimal("40.00")}], paid_date=today
        )
        payments.confirm_payment(payment.pk)
        payments.reverse_payment(payment.pk, reason="Exercício fictício de estorno.")
        self.create_media_evidence(people["ADMIN"], children["S1"].pk)
        self._log("fictitious_journeys_exercised", class_count=len(publications))
        return {
            "diary_publications": publications,
            "announcement": str(draft.pk),
            "announcement_original": str(revision.pk),
            "announcement_correction": str(correction.pk),
            "request": str(ticket.pk),
            "payment_reversed": str(payment.pk),
            "checks": [
                "all_classes_enrolled",
                "children_without_accounts_or_email",
                "diary_review_return_publish",
                "siblings_deduplicated",
                "acknowledgement_per_revision",
                "request_private_to_author",
                "request_reopened",
                "payment_confirmed_reversed",
            ],
        }

    @system_command
    def create_media_evidence(self, administrator, student_id):
        """Acrescenta mídia sintética privada necessária ao ensaio de recuperação."""
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        from students.selectors import StudentSelector
        from students.services import StudentService

        require_fictitious()
        student = StudentSelector().get_student_by_id(student_id)
        content = BytesIO()
        Image.new("RGB", (24, 24), "#2359c4").save(content, format="PNG")
        student = StudentService(user=administrator).update_student(
            student.pk,
            {
                "first_name": student.first_name,
                "last_name": student.last_name,
                "birth_date": student.birth_date,
                "version": student.version,
                "photo": SimpleUploadedFile(
                    "fixture.png", content.getvalue(), content_type="image/png"
                ),
            },
        )
        return str(student.pk)
