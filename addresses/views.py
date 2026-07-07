"""Views do modulo de enderecos (gerenciamento standalone)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render

from base.exceptions import BusinessRuleViolationError, ValidationError


@login_required
def address_card(request: HttpRequest, entity_type: str, entity_id) -> HttpResponse:
    """Renderiza o card inline de enderecos para uma entidade."""
    return _render_address_card(request, entity_type, entity_id)


@login_required
def address_create_for_entity(request: HttpRequest, entity_type: str, entity_id) -> HttpResponse:
    """Cria endereco para uma entidade e redireciona de volta."""
    from addresses.forms import AddressForm
    from addresses.services import AddressService

    service = AddressService(user=request.user)
    method_map = {
        "school": service.create_address_for_school,
        "business_unit": service.create_address_for_business_unit,
        "teacher": service.create_address_for_teacher,
        "student": service.create_address_for_student,
        "guardian": service.create_address_for_guardian,
    }
    create_method = method_map.get(entity_type)

    if not create_method:
        messages.error(request, "Tipo de entidade invalido.")
        return redirect("dashboard")

    if request.method == "POST":
        form = AddressForm(request.POST)
        if form.is_valid():
            try:
                create_method(entity_id, form.cleaned_data)
                if request.headers.get("HX-Request"):
                    return _render_address_card(request, entity_type, entity_id, saved=True)
                messages.success(request, "Endereco cadastrado com sucesso.")
                return _redirect_back(entity_type, entity_id, request)
            except ValidationError as exc:
                for field, errors in exc.errors.items():
                    form.add_error(field, errors)
            except BusinessRuleViolationError as exc:
                messages.error(request, exc.message)
    else:
        form = AddressForm()

    if request.headers.get("HX-Request"):
        return render(
            request,
            "addresses/partials/address_form_card.html",
            {
                "form": form,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "title": "Novo Endereco",
            },
        )

    return render(
        request,
        "addresses/address_form.html",
        {
            "form": form,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "title": "Novo Endereco",
        },
    )


@login_required
def address_edit(request: HttpRequest, address_id) -> HttpResponse:
    """Edita um endereco existente."""
    from addresses.forms import AddressForm
    from addresses.selectors import AddressSelector
    from addresses.services import AddressService

    address = AddressSelector().get_by_id(address_id)
    entity_type, entity_id = _get_address_entity_context(address)

    if request.method == "POST":
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            try:
                AddressService(user=request.user).update_address(address_id, form.cleaned_data)
                if request.headers.get("HX-Request"):
                    return _render_address_card(request, entity_type, entity_id, saved=True)
                messages.success(request, "Endereco atualizado com sucesso.")
                return _redirect_back(None, None, request) or redirect("dashboard")
            except ValidationError as exc:
                for field, errors in exc.errors.items():
                    form.add_error(field, errors)
            except BusinessRuleViolationError as exc:
                messages.error(request, exc.message)
    else:
        form = AddressForm(instance=address)

    if request.headers.get("HX-Request"):
        return render(
            request,
            "addresses/partials/address_form_card.html",
            {
                "form": form,
                "address": address,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "title": "Editar Endereco",
            },
        )

    return render(
        request,
        "addresses/address_form.html",
        {"form": form, "address": address, "title": "Editar Endereco"},
    )


@login_required
def address_deactivate(request: HttpRequest, address_id) -> HttpResponse:
    """Desativa (soft-delete) um endereco."""
    from addresses.services import AddressService

    if request.method == "POST":
        try:
            AddressService(user=request.user).deactivate_address(address_id)
            messages.success(request, "Endereco desativado.")
        except BusinessRuleViolationError as exc:
            messages.error(request, exc.message)
    return redirect(request.META.get("HTTP_REFERER", "dashboard"))


@login_required
def address_city_options(request: HttpRequest) -> HttpResponse:
    """Renderiza o campo de municipio de acordo com a UF selecionada."""
    from addresses.forms import AddressForm
    from locations.selectors import CitySelector

    state = request.GET.get("state", "")
    city = request.GET.get("city", "")
    valid_cities = {item.name for item in CitySelector().list_by_state_code(state)}
    selected_city = city if city in valid_cities else ""
    form = AddressForm(initial={"state": state, "city": selected_city})
    return render(request, "addresses/partials/city_field.html", {"field": form["city"]})


def _redirect_back(
    entity_type: str | None, entity_id: str | None, request: HttpRequest
) -> HttpResponseRedirect:
    """Tenta redirecionar para o referer; fallback: dashboard."""
    referer = request.META.get("HTTP_REFERER", "")
    if referer and "address" not in referer:
        return redirect(referer)
    return redirect("dashboard")


def _render_address_card(
    request: HttpRequest,
    entity_type: str,
    entity_id,
    *,
    saved: bool = False,
) -> HttpResponse:
    """Renderiza o card padrão de enderecos de uma entidade."""
    from addresses.selectors import AddressSelector

    addresses = AddressSelector().get_by_entity(entity_type, entity_id)
    return render(
        request,
        "addresses/partials/address_table.html",
        {
            "addresses": addresses,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "saved": saved,
        },
    )


def _get_address_entity_context(address) -> tuple[str, str]:
    """Descobre a entidade dona do endereco a partir dos vinculos."""
    from addresses.models import (
        BusinessUnitAddress,
        GuardianAddress,
        SchoolAddress,
        StudentAddress,
        TeacherAddress,
    )

    link_checks = [
        ("school", SchoolAddress, "school_id"),
        ("business_unit", BusinessUnitAddress, "business_unit_id"),
        ("teacher", TeacherAddress, "teacher_id"),
        ("student", StudentAddress, "student_id"),
        ("guardian", GuardianAddress, "guardian_id"),
    ]
    for entity_type, link_model, field_name in link_checks:
        link = link_model.objects.filter(address=address).values(field_name).first()
        if link:
            return entity_type, str(link[field_name])
    return "school", ""
