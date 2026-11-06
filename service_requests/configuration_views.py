"""Configuração administrativa de setores e calendário."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from base.exceptions import BusinessRuleViolationError, ValidationError
from core.permissions import access_policy
from service_requests.configuration_services import ServiceConfigurationService
from service_requests.forms import CalendarForm, DepartmentForm
from service_requests.selectors import ServiceStaffSelector


@login_required
@access_policy("__admin__", "edit")
def service_request_configuration(request):
    data = ServiceStaffSelector.configuration()
    calendar = data["calendar"]
    form = CalendarForm(
        initial={
            "version": calendar.version,
            "weekdays": calendar.weekdays,
            "opens_at": calendar.opens_at,
            "closes_at": calendar.closes_at,
            "closed_dates": "\n".join(calendar.closed_dates),
            "immediate_contact": calendar.immediate_contact,
        }
    )
    sector_forms = []
    for department in data["departments"]:
        sector_forms.append(
            (
                department,
                DepartmentForm(
                    user_choices=data["user_choices"],
                    initial={
                        "code": department.code,
                        "version": department.version,
                        "enabled": department.enabled,
                        "user_ids": (
                            [str(m.user_id) for m in department.memberships.all()]
                            if department.pk and not department._state.adding
                            else []
                        ),
                    },
                ),
            )
        )
    if request.method == "POST":
        is_calendar = request.POST.get("action") == "calendar"
        submitted = (
            CalendarForm(request.POST)
            if is_calendar
            else DepartmentForm(request.POST, user_choices=data["user_choices"])
        )
        if submitted.is_valid():
            service = ServiceConfigurationService(user=request.user)
            try:
                if is_calendar:
                    service.update_calendar(submitted.cleaned_data)
                else:
                    service.update_department(**submitted.cleaned_data)
            except (ValidationError, BusinessRuleViolationError) as exc:
                messages.error(request, exc.message)
            else:
                messages.success(request, "Configuração de atendimento salva.")
                return redirect("service_request_configuration")
        else:
            messages.error(request, "Confira os campos da configuração.")
        if is_calendar:
            form = submitted
        else:
            sector_forms = [
                (
                    department,
                    submitted if department.code == request.POST.get("code") else sector_form,
                )
                for department, sector_form in sector_forms
            ]
    return render(
        request,
        "service_requests/configuration.html",
        {"calendar_form": form, "sector_forms": sector_forms},
    )
