"""URLs do modulo Financeiro Escolar."""

from django.urls import path

from financeiro import views

urlpatterns = [
    path("financeiro/", views.finance_dashboard, name="finance_dashboard"),
    path("financeiro/planos/", views.plan_list, name="plan_list"),
    path("financeiro/planos/novo/", views.plan_create, name="plan_create"),
    path("financeiro/planos/<uuid:pk>/", views.plan_detail, name="plan_detail"),
    path("financeiro/planos/<uuid:pk>/ativar/", views.plan_activate, name="plan_activate"),
    path("financeiro/planos/<uuid:pk>/suspender/", views.plan_suspend, name="plan_suspend"),
    path(
        "financeiro/planos/<uuid:pk>/gerar/",
        views.plan_generate_billings,
        name="plan_generate_billings",
    ),
    path("financeiro/cobrancas/", views.billing_list, name="billing_list"),
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
        views.billing_apply_late_fees,
        name="billing_apply_late_fees",
    ),
    path(
        "financeiro/cobrancas/<uuid:pk>/pagamentos/<uuid:payment_id>/<str:action>/",
        views.billing_reconcile_payment,
        name="billing_reconcile_payment",
    ),
    path("financeiro/gerar-lote/", views.bulk_generate_billings, name="bulk_generate_billings"),
    path("financeiro/relatorio/", views.revenue_report, name="finance_revenue_report"),
    path("financeiro/inadimplencia/", views.overdue_report, name="finance_overdue_report"),
]
