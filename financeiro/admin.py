from django.contrib import admin

from financeiro.models import BillingEntry, FinancialPlan, PaymentRecord


@admin.register(FinancialPlan)
class FinancialPlanAdmin(admin.ModelAdmin):
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
        "plan",
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
    raw_id_fields = ["plan", "student", "renegotiated_from"]


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display = [
        "billing",
        "amount",
        "paid_date",
        "payment_method",
        "reconciliation_status",
        "received_by",
        "created_at",
    ]
    list_filter = ["payment_method", "reconciliation_status", "paid_date"]
    search_fields = ["billing__description", "notes"]
    raw_id_fields = ["billing", "received_by"]
