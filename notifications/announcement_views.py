"""Orquestração HTTP da autoria, leitura e ciência de comunicados."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from base.exceptions import BusinessRuleViolationError, ValidationError
from base.forms import apply_validation_errors
from base.listing import build_querystring, build_sorting, resolve_listing_state
from base.media import private_file_response
from notifications.announcement_forms import (
    AnnouncementAttachmentForm,
    AnnouncementForm,
    AnnouncementScheduleForm,
)
from notifications.announcement_selectors import (
    AnnouncementAudienceSelector,
    AnnouncementSelector,
    can_manage_announcements,
)
from notifications.announcement_services import AnnouncementService

SORTS = {
    "title": "title",
    "-title": "-title",
    "published_at": "published_at",
    "-published_at": "-published_at",
    "audience": "audience",
    "-audience": "-audience",
}


@login_required
def announcement_list(request):
    state = resolve_listing_state(
        request, scope="announcements_list", allowed_sorts=set(SORTS), default_sort="-published_at"
    )
    context = {
        "result": AnnouncementSelector().list_for_user(
            request.user, state["q"], SORTS[state["sort"]], state["page"]
        ),
        "q": state["q"],
        "sort": state["sort"],
        "can_manage": can_manage_announcements(request.user, "create"),
        "sorting": build_sorting(
            current_sort=state["sort"],
            search=state["q"],
            sortable_fields=["title", "published_at", "audience"],
        ),
        "list_query": build_querystring({"q": state["q"], "sort": state["sort"]}),
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Comunicados", "url": None},
        ],
    }
    template = (
        "notifications/partials/announcements_table.html"
        if request.headers.get("HX-Request")
        else "notifications/announcement_list.html"
    )
    return render(request, template, context)


@login_required
def announcement_create(request):
    return _form(request)


@login_required
def announcement_edit(request, pk):
    return _form(request, pk)


def _form(request, pk=None):
    if not can_manage_announcements(request.user, "edit" if pk else "create"):
        from base.exceptions import PermissionDeniedError

        raise PermissionDeniedError("Sem permissão para gerenciar comunicados.")
    announcement = AnnouncementSelector().get_by_id(pk) if pk else None
    form = AnnouncementForm(
        request.POST or None,
        instance=announcement,
        choices=AnnouncementAudienceSelector.form_options(),
    )
    if request.method == "POST" and form.is_valid():
        service = AnnouncementService(user=request.user)
        try:
            announcement = (
                service.update_announcement(pk, form.cleaned_data)
                if pk
                else service.create_announcement(form.cleaned_data)
            )
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except BusinessRuleViolationError as exc:
            form.add_error(None, exc.message)
        else:
            messages.success(
                request, "Rascunho salvo. Confira a prévia e os destinatários antes de publicar."
            )
            return redirect("announcement_detail", pk=announcement.pk)
    return render(
        request,
        "notifications/announcement_form.html",
        {
            "form": form,
            "announcement": announcement,
            "title": "Editar comunicado" if pk else "Novo comunicado",
        },
    )


@login_required
def announcement_detail(request, pk):
    context = AnnouncementSelector().detail(pk, request.user, request.GET.get("revision"))
    if context["receipt"]:
        AnnouncementService(user=request.user).mark_announcement_viewed(context["revision"].pk)
        context = AnnouncementSelector().detail(pk, request.user, request.GET.get("revision"))
    context["schedule_form"] = AnnouncementScheduleForm(
        initial={"version": context["announcement"].version}
    )
    context["attachment_form"] = AnnouncementAttachmentForm(
        initial={"version": context["announcement"].version}
    )
    context["draft_attachments"] = (
        AnnouncementSelector().draft_attachments(context["announcement"])
        if context["can_manage"]
        else []
    )
    return render(request, "notifications/announcement_detail.html", context)


@login_required
@require_POST
def announcement_action(request, pk):
    service = AnnouncementService(user=request.user)
    version = request.POST.get("version")
    action = request.POST.get("action")
    try:
        if action == "publish":
            service.publish_announcement(pk, version=version)
            messages.success(
                request, "Comunicado publicado. As entregas estão registradas e serão processadas."
            )
        elif action == "correct":
            service.open_announcement_correction(pk, version=version)
            messages.success(request, "Correção aberta. A revisão publicada permanece disponível.")
        elif action == "cancel":
            service.cancel_announcement_schedule(pk, version=version)
            messages.success(request, "Agendamento cancelado. O comunicado voltou a rascunho.")
        elif action == "schedule":
            form = AnnouncementScheduleForm(request.POST)
            if not form.is_valid():
                raise ValidationError(errors={"scheduled_at": ["Informe data e horário válidos."]})
            service.schedule_announcement(pk, **form.cleaned_data)
            messages.success(
                request, "Publicação agendada. A audiência será conferida no horário da publicação."
            )
        elif action == "remove_attachment":
            service.remove_announcement_attachment(
                pk, request.POST.get("attachment_id"), version=version
            )
            messages.success(
                request, "Anexo removido do rascunho. Revisões anteriores foram preservadas."
            )
        else:
            raise BusinessRuleViolationError("Ação inválida.")
    except (BusinessRuleViolationError, ValidationError) as exc:
        messages.error(request, exc.message)
    return redirect("announcement_detail", pk=pk)


@login_required
@require_POST
def announcement_upload(request, pk):
    form = AnnouncementAttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            AnnouncementService(user=request.user).add_announcement_attachment(
                pk, form.cleaned_data["file"], version=form.cleaned_data["version"]
            )
            messages.success(request, "Anexo privado adicionado ao rascunho.")
        except (BusinessRuleViolationError, ValidationError) as exc:
            messages.error(request, exc.message)
    else:
        messages.error(request, "Selecione um PDF ou imagem válida e recarregue a versão atual.")
    return redirect("announcement_detail", pk=pk)


@login_required
def announcement_attachment(request, pk):
    attachment = AnnouncementSelector().attachment_for(pk, request.user)
    return private_file_response(attachment.file, as_attachment=True)


@login_required
@require_POST
def announcement_acknowledge(request, pk):
    receipt = AnnouncementService(user=request.user).acknowledge_announcement(pk)
    messages.success(
        request,
        "Sua ciência desta revisão foi registrada. Isso não constitui autorização ou assinatura.",
    )
    return redirect("announcement_detail", pk=receipt.revision.announcement_id)


@login_required
@require_POST
def announcement_retry(request, pk):
    from notifications.outbox_services import OutboxService

    try:
        delivery = OutboxService(user=request.user).request_delivery_retry(pk)
    except BusinessRuleViolationError as exc:
        messages.error(request, exc.message)
        return redirect("announcement_list")
    messages.success(request, "Reprocessamento registrado somente para esta entrega.")
    return redirect("announcement_detail", pk=delivery.announcement_id)
