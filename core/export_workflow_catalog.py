"""Allowlist explícita de exportação; novos campos exigem revisão e inclusão deliberada."""

FIELDS = {
    "notifications.Announcement": (
        "title body audience attachment_ids class_ids user_ids student_id author_id "
        "status send_email requires_acknowledgement acknowledgement_due_at scheduled_at "
        "published_at "
    ).split(),
    "notifications.AnnouncementRevision": (
        "announcement_id number title body audience audience_snapshot "
        "requires_acknowledgement acknowledgement_due_at published_at published_by_id "
    ).split(),
    "notifications.AnnouncementRecipient": (
        "revision_id user_id guardian_id student_ids first_viewed_at acknowledged_at "
    ).split(),
    "notifications.AnnouncementAttachment": ("announcement_id label ").split(),
    "service_requests.AdministrativeCalendar": (
        "key weekdays opens_at closes_at closed_dates immediate_contact "
    ).split(),
    "service_requests.ServiceDepartment": ("code enabled ").split(),
    "service_requests.DepartmentMembership": ("department_id user_id ").split(),
    "service_requests.RequestSequence": ("year next_number ").split(),
    "service_requests.ServiceRequest": (
        "protocol student_id author_id department_id attendant_id subject status cycle "
        "cycle_opened_at response_due_at first_response_at "
    ).split(),
    "service_requests.RequestMessage": ("request_id author_id body is_staff_response ").split(),
    "service_requests.RequestAttachment": ("message_id ").split(),
    "service_requests.RequestTransition": (
        "request_id event from_status to_status from_department to_department cycle "
    ).split(),
    "financeiro.StudentFinancialContract": (
        "template_id student_id class_obj_id academic_year name status billing_frequency "
        "installment_count installment_value due_day discount_value late_fee_percent "
        "daily_interest_percent start_competency end_competency terms_revision notes "
    ).split(),
    "financeiro.BillingEntry": (
        "contract_id amendment_id cancelling_amendment_id student_id installment_number "
        "schedule_revision category description principal_value discount_value "
        "late_fee_value interest_value late_fee_percent daily_interest_percent "
        "reversal_allocation_id paid_value paid_principal_value paid_late_fee_value "
        "paid_interest_value competency due_date interest_calculated_until status "
        "cancelled_reason renegotiated_from_id notes "
    ).split(),
    "financeiro.FinancialPlanTemplate": (
        "name academic_year billing_frequency installment_count installment_value due_day "
        "discount_value late_fee_percent daily_interest_percent description "
    ).split(),
    "financeiro.FinancialContractAmendment": (
        "contract_id revision effective_competency changed_terms reason "
    ).split(),
    "financeiro.PaymentRecord": (
        "amount paid_date payment_method reference received_by_id status reconciled_at "
        "confirmed_by_id reversed_at reversed_by_id reversal_reason receipt_number notes "
    ).split(),
    "financeiro.PaymentAllocation": (
        "payment_id billing_id amount principal_amount late_fee_amount interest_amount "
    ).split(),
    "financeiro.FinancialSequence": ("kind year last_value ").split(),
    "financeiro.CollectionReminderPolicy": ("name enabled offset_days channels ").split(),
}

MEDIA_FIELDS = {
    "notifications.AnnouncementAttachment": ["file"],
    "service_requests.RequestAttachment": ["file"],
}

RELATION_FIELDS = {"notifications.AnnouncementAttachment": ["revisions"]}
