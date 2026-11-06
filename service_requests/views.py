"""Entrada HTTP progressiva do atendimento privado."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from base.exceptions import BusinessRuleViolationError, PermissionDeniedError, ValidationError
from base.forms import apply_validation_errors
from base.listing import build_querystring, resolve_listing_state
from base.media import private_file_response
from core.permissions import role_name
from service_requests.forms import RequestForm, ResponseForm
from service_requests.selectors import ServiceRequestSelector
from service_requests.services import ServiceRequestService


@login_required
def service_request_list(request):
    state = resolve_listing_state(
        request,
        scope="service_requests",
        allowed_sorts={"response_due_at"},
        default_sort="response_due_at",
    )
    context = {
        "result": ServiceRequestSelector().list_for_user(request.user, state["page"], state["q"]),
        "q": state["q"],
        "list_query": build_querystring({"q": state["q"]}),
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Solicitações", "url": None},
        ],
    }
    template = (
        "service_requests/partials/requests_table.html"
        if request.headers.get("HX-Request")
        else "service_requests/request_list.html"
    )
    return render(request, template, context)


@login_required
def service_request_create(request):
    if role_name(request.user) != "GUARDIAN":
        raise PermissionDeniedError("Somente a família abre solicitações privadas.")
    form = RequestForm(
        request.POST or None,
        request.FILES or None,
        **ServiceRequestSelector.create_options(request.user),
    )
    if request.method == "POST" and form.is_valid():
        try:
            ticket = ServiceRequestService(user=request.user).create_request(
                form.cleaned_data,
                [form.cleaned_data["file"]] if form.cleaned_data.get("file") else [],
            )
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except BusinessRuleViolationError as exc:
            form.add_error(None, exc.message)
        else:
            messages.success(
                request, "Solicitação registrada. Confira o protocolo e o prazo de resposta."
            )
            return redirect("service_request_detail", pk=ticket.pk)
    return render(
        request, "service_requests/request_form.html", {"form": form, "title": "Nova solicitação"}
    )


@login_required
def service_request_detail(request, pk):
    context = ServiceRequestSelector().detail(pk, request.user)
    context["response_form"] = ResponseForm(initial={"version": context["ticket"].version})
    return render(request, "service_requests/request_detail.html", context)


@login_required
@require_POST
def service_request_respond(request, pk):
    form = ResponseForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            ServiceRequestService(user=request.user).add_request_message(
                pk,
                version=form.cleaned_data["version"],
                body=form.cleaned_data["body"],
                uploads=[form.cleaned_data["file"]] if form.cleaned_data.get("file") else [],
            )
        except (ValidationError, BusinessRuleViolationError) as exc:
            messages.error(request, exc.message)
        else:
            messages.success(
                request, "Mensagem registrada no histórico. A outra parte será avisada."
            )
    else:
        messages.error(request, "Informe uma mensagem válida e confira o anexo.")
    return redirect("service_request_detail", pk=pk)


@login_required
@require_POST
def service_request_action(request, pk):
    service = ServiceRequestService(user=request.user)
    action, version = request.POST.get("action"), request.POST.get("version")
    try:
        if action == "reopen":
            service.reopen_request(pk, version=version)
        elif action == "transfer":
            service.transfer_request(
                pk, version=version, department_id=request.POST.get("department_id")
            )
        elif action == "assign":
            service.assign_request(
                pk, version=version, attendant_id=request.POST.get("attendant_id")
            )
        elif action == "status":
            service.update_request_status(pk, version=version, status=request.POST.get("status"))
        else:
            raise ValidationError(errors={"action": ["Ação inválida."]})
    except (ValidationError, BusinessRuleViolationError) as exc:
        messages.error(request, exc.message)
    else:
        messages.success(request, "Solicitação atualizada. Confira o estado e o prazo atuais.")
    return redirect("service_request_detail", pk=pk)


@login_required
def service_request_attachment(request, pk):
    attachment = ServiceRequestSelector().attachment_for(pk, request.user)
    return private_file_response(attachment.file, as_attachment=True)
