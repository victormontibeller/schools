from django.contrib import admin

from financeiro.models import (
    BillingEntry,
    CollectionReminder,
    CollectionReminderPolicy,
    FinancialContractAmendment,
    FinancialPlanTemplate,
    FinancialSequence,
    PaymentAllocation,
    PaymentRecord,
    StudentFinancialContract,
)


@admin.register(FinancialPlanTemplate)
class FinancialPlanTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "academic_year", "billing_frequency", "installment_count"]
    list_filter = ["academic_year", "billing_frequency"]
    search_fields = ["name"]


@admin.register(StudentFinancialContract)
class StudentFinancialContractAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "student",
        "class_obj",
        "academic_year",
        "status",
        "installment_count",
        "installment_value",
        "due_day",
        "created_at",
    ]
    list_filter = ["status", "billing_frequency", "academic_year"]
    search_fields = [
        "name",
        "student__first_name",
        "student__last_name",
        "student__enrollment_number",
    ]
    raw_id_fields = ["student", "class_obj"]


@admin.register(BillingEntry)
class BillingEntryAdmin(admin.ModelAdmin):
    list_display = [
        "description",
        "student",
        "contract",
        "installment_number",
        "net_value",
        "paid_value",
        "due_date",
        "status",
    ]
    list_filter = ["status", "due_date"]
    search_fields = [
        "description",
        "student__first_name",
        "student__last_name",
        "student__enrollment_number",
    ]
    raw_id_fields = ["contract", "student", "renegotiated_from"]


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display = [
        "receipt_number",
        "amount",
        "paid_date",
        "payment_method",
        "status",
        "received_by",
        "created_at",
    ]
    list_filter = ["payment_method", "status", "paid_date"]
    search_fields = ["receipt_number", "reference", "notes"]
    raw_id_fields = ["received_by"]


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    list_display = ["payment", "billing", "amount", "principal_amount"]
    raw_id_fields = ["payment", "billing"]


@admin.register(FinancialContractAmendment)
class FinancialContractAmendmentAdmin(admin.ModelAdmin):
    list_display = ["contract", "revision", "effective_competency", "created_at"]
    raw_id_fields = ["contract"]


@admin.register(CollectionReminderPolicy)
class CollectionReminderPolicyAdmin(admin.ModelAdmin):
    list_display = ["name", "enabled", "offset_days", "channels"]


@admin.register(CollectionReminder)
class CollectionReminderAdmin(admin.ModelAdmin):
    list_display = ["billing", "channel", "scheduled_for", "status", "sent_at"]
    list_filter = ["channel", "status", "scheduled_for"]
    raw_id_fields = ["billing", "guardian", "recipient"]


@admin.register(FinancialSequence)
class FinancialSequenceAdmin(admin.ModelAdmin):
    list_display = ["kind", "year", "last_value"]
    readonly_fields = ["kind", "year", "last_value"]
