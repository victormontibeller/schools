"""URLs canônicas do contas a receber financeiro."""

from django.urls import path

from financeiro import document_views, operational_views, report_views, views

urlpatterns = [
    path("financeiro/", views.finance_dashboard, name="finance_dashboard"),
    path(
        "financeiro/modelos/",
        operational_views.financial_template_list,
        name="financial_template_list",
    ),
    path(
        "financeiro/modelos/novo/",
        operational_views.financial_template_create,
        name="financial_template_create",
    ),
    path(
        "financeiro/modelos/<uuid:pk>/",
        operational_views.financial_template_detail,
        name="financial_template_detail",
    ),
    path(
        "financeiro/modelos/<uuid:pk>/editar/",
        operational_views.financial_template_edit,
        name="financial_template_edit",
    ),
    path("financeiro/contratos/", views.contract_list, name="contract_list"),
    path("financeiro/contratos/novo/", views.contract_create, name="contract_create"),
    path("financeiro/contratos/<uuid:pk>/", views.contract_detail, name="contract_detail"),
    path(
        "financeiro/contratos/<uuid:pk>/editar/",
        operational_views.contract_edit,
        name="contract_edit",
    ),
    path(
        "financeiro/contratos/<uuid:pk>/ativar/",
        views.contract_activate,
        name="contract_activate",
    ),
    path(
        "financeiro/contratos/<uuid:pk>/suspender/",
        views.contract_suspend,
        name="contract_suspend",
    ),
    path(
        "financeiro/contratos/<uuid:pk>/aditivos/novo/",
        operational_views.contract_amendment_create,
        name="contract_amendment_create",
    ),
    path(
        "financeiro/contratos/<uuid:pk>/gerar/",
        views.contract_materialize_billings,
        name="contract_materialize_billings",
    ),
    path("financeiro/cobrancas/", views.billing_list, name="billing_list"),
    path(
        "financeiro/cobrancas/nova/", operational_views.ad_hoc_billing_create, name="billing_create"
    ),
    path("financeiro/cobrancas/<uuid:pk>/", views.billing_detail, name="billing_detail"),
    path(
        "financeiro/cobrancas/<uuid:pk>/baixa/",
        views.billing_register_payment,
        name="billing_register_payment",
    ),
    path("financeiro/cobrancas/<uuid:pk>/cancelar/", views.billing_cancel, name="billing_cancel"),
    path(
        "financeiro/cobrancas/<uuid:pk>/renegociar/",
        views.billing_renegotiate,
        name="billing_renegotiate",
    ),
    path(
        "financeiro/cobrancas/<uuid:pk>/multa/",
        views.billing_assess_late_charges,
        name="billing_assess_late_charges",
    ),
    path(
        "financeiro/cobrancas/<uuid:pk>/lembrete/",
        document_views.billing_send_reminder,
        name="billing_send_reminder",
    ),
    path("financeiro/baixas/nova/", operational_views.payment_create, name="payment_create"),
    path("financeiro/conciliacoes/", operational_views.payment_queue, name="payment_queue"),
    path(
        "financeiro/conciliacoes/<uuid:pk>/",
        operational_views.payment_detail,
        name="payment_detail",
    ),
    path(
        "financeiro/conciliacoes/<uuid:pk>/confirmar/",
        operational_views.payment_confirm,
        name="payment_confirm",
    ),
    path(
        "financeiro/conciliacoes/<uuid:pk>/estornar/",
        operational_views.payment_reverse,
        name="payment_reverse",
    ),
    path(
        "financeiro/pagamentos/<uuid:pk>/recibo.pdf",
        document_views.payment_receipt_pdf,
        name="payment_receipt_pdf",
    ),
    path(
        "financeiro/alunos/<uuid:student_id>/extrato/",
        document_views.student_statement,
        name="student_financial_statement",
    ),
    path(
        "financeiro/alunos/<uuid:student_id>/extrato.pdf",
        document_views.student_statement_pdf,
        name="student_financial_statement_pdf",
    ),
    path(
        "financeiro/lembretes/configuracao/",
        operational_views.reminder_settings,
        name="reminder_settings",
    ),
    path("financeiro/lembretes/", operational_views.reminder_history, name="reminder_history"),
    path(
        "financeiro/materializar-lote/",
        views.bulk_materialize_billings,
        name="bulk_materialize_billings",
    ),
    path("financeiro/relatorio/", report_views.revenue_report, name="finance_revenue_report"),
    path(
        "financeiro/inadimplencia/",
        report_views.overdue_report,
        name="finance_overdue_report",
    ),
]
