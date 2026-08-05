"""Orquestração HTTP da régua e do histórico de lembretes financeiros."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from base.exceptions import BusinessRuleViolationError, ValidationError
from base.forms import apply_validation_errors
from base.listing import build_sorting, resolve_listing_state
from core.permissions import EDIT, VIEW, access_policy
from financeiro.forms import CollectionReminderPolicyForm
from financeiro.selectors import ReminderSelector
from financeiro.services import FinanceService
from financeiro.view_helpers import finance_breadcrumbs


@login_required
@access_policy("finance_reminders", EDIT)
def reminder_settings(request: HttpRequest) -> HttpResponse:
    """Configura a régua explícita de cobrança."""
    policy = ReminderSelector().get_policy()
    form = CollectionReminderPolicyForm(request.POST or None, instance=policy)
    if request.method == "POST" and form.is_valid():
        try:
            FinanceService(user=request.user).configure_reminder_policy(
                {
                    "name": form.cleaned_data["name"],
                    "enabled": form.cleaned_data["enabled"],
                    "channels": form.cleaned_data["channels"],
                    "offset_days": form.cleaned_data["offset_days_text"],
                }
            )
            messages.success(request, "Régua de cobrança atualizada.")
            return redirect("reminder_settings")
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except BusinessRuleViolationError as exc:
            messages.error(request, exc.message)
    return render(request, "financeiro/reminder_settings.html", {"form": form, "policy": policy})


@login_required
@access_policy("finance_reminders", VIEW)
def reminder_history(request: HttpRequest) -> HttpResponse:
    """Lista o histórico de lembretes por situação."""
    from financeiro.contracts import CollectionReminder

    state = resolve_listing_state(
        request,
        scope="financial_reminders",
        allowed_sorts={"scheduled_for", "-scheduled_for", "status", "-status"},
        default_sort="-scheduled_for",
    )
    status = request.GET.get("status", "")
    result = ReminderSelector().list_reminders(
        search=state["q"], status=status, order_by=state["sort"], page=state["page"]
    )
    sorting = build_sorting(
        current_sort=state["sort"], search=state["q"], sortable_fields=["scheduled_for", "status"]
    )
    if status:
        for item in sorting.values():
            item["query"] += f"&status={status}"
    context = {
        "result": result,
        "status": status,
        "q": state["q"],
        "sort": state["sort"],
        "sorting": sorting,
        "status_choices": CollectionReminder.Status.choices,
        "breadcrumb_items": finance_breadcrumbs(request.user, ("Lembretes", None)),
    }
    if request.headers.get("HX-Request"):
        return render(request, "financeiro/partials/reminders_table.html", context)
    return render(request, "financeiro/reminder_list.html", context)
