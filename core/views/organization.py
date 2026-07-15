"""Views institucionais da escola e de suas unidades."""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from base.forms import apply_validation_errors


@login_required
def business_unit_list(request: HttpRequest) -> HttpResponse:
    """Lista unidades de negócio do tenant ativo."""
    from base.listing import build_querystring, build_sorting, resolve_listing_state
    from core.selectors import BusinessUnitSelector

    page = int(request.GET.get("page", 1))
    state = resolve_listing_state(
        request,
        scope="business_unit_list",
        allowed_sorts={"name", "-name", "cnpj", "-cnpj", "phone", "-phone", "email", "-email"},
        default_sort="name",
    )
    search, sort = state["q"], state["sort"]
    result = BusinessUnitSelector().list_business_units(search=search, order_by=sort, page=page)
    ctx = {
        "result": result,
        "q": search,
        "sort": sort,
        "sorting": build_sorting(
            current_sort=sort, search=search, sortable_fields=["name", "cnpj", "phone", "email"]
        ),
        "list_query": build_querystring({"q": search, "sort": sort}),
        "clear_query": build_querystring({"q": "", "sort": "name"}, include_blank=True),
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Unidades", "url": None},
        ],
    }
    if request.headers.get("HX-Request"):
        return render(request, "core/partials/business_units_table.html", ctx)
    return render(request, "core/business_units_list.html", ctx)


@login_required
def business_unit_detail(request: HttpRequest, pk) -> HttpResponse:
    """Exibe a ficha completa de uma unidade de negocio."""
    from addresses.selectors import AddressSelector
    from core.selectors import BusinessUnitSelector

    business_unit = BusinessUnitSelector().get_by_id(pk)
    addresses = AddressSelector().get_by_entity("business_unit", business_unit.pk)
    if request.headers.get("HX-Request") and request.GET.get("component") == "information":
        return render(
            request,
            "core/partials/business_unit_information_card.html",
            {"business_unit": business_unit},
        )
    return render(
        request,
        "core/business_unit_detail.html",
        {"business_unit": business_unit, "addresses": addresses},
    )


@login_required
def business_unit_create(request: HttpRequest) -> HttpResponse:
    """Processa o formulario de criacao de empresa."""
    from django.contrib import messages

    from base.exceptions import BusinessRuleViolationError, ValidationError
    from core.forms import BusinessUnitForm
    from core.services import BusinessUnitService

    form = BusinessUnitForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            data = form.cleaned_data.copy()
            logo = data.pop("logo", None)
            business_unit = BusinessUnitService(user=request.user).create_business_unit(data)
            if logo:
                BusinessUnitService(user=request.user).update_business_unit_logo(
                    business_unit.pk, logo
                )
            messages.success(request, "Empresa criada com sucesso.")
            return redirect("business_unit_detail", pk=business_unit.pk)
        except ValidationError as exc:
            apply_validation_errors(form, exc)
        except BusinessRuleViolationError as exc:
            messages.error(request, exc.message)

    return render(
        request,
        "core/business_unit_form.html",
        {"form": form, "title": "Nova Empresa"},
    )


@login_required
def business_unit_edit(request: HttpRequest, pk) -> HttpResponse:
    """Processa o formulario de edicao de empresa."""
    from django.contrib import messages

    from base.exceptions import BusinessRuleViolationError, ValidationError
    from core.forms import BusinessUnitForm
    from core.selectors import BusinessUnitSelector
    from core.services import BusinessUnitService

    business_unit = BusinessUnitSelector().get_by_id(pk)

    if request.method == "POST":
        form = BusinessUnitForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                data = form.cleaned_data.copy()
                logo = data.pop("logo", None)
                BusinessUnitService(user=request.user).update_business_unit(pk, data)
                if logo:
                    BusinessUnitService(user=request.user).update_business_unit_logo(pk, logo)
                business_unit = BusinessUnitSelector().get_by_id(pk)
                if request.headers.get("HX-Request"):
                    return render(
                        request,
                        "core/partials/business_unit_information_card.html",
                        {"business_unit": business_unit, "saved": True},
                    )
                messages.success(request, "Empresa atualizada com sucesso.")
                return redirect("business_unit_detail", pk=pk)
            except ValidationError as exc:
                apply_validation_errors(form, exc)
            except BusinessRuleViolationError as exc:
                messages.error(request, exc.message)
    else:
        form = BusinessUnitForm(
            initial={
                "name": business_unit.name,
                "legal_name": business_unit.legal_name,
                "trade_name": business_unit.trade_name,
                "cnpj": business_unit.cnpj or "",
                "state_registration": business_unit.state_registration,
                "municipal_registration": business_unit.municipal_registration,
                "phone": business_unit.phone,
                "email": business_unit.email,
                "contact_full_name": business_unit.contact_full_name,
                "contact_role": business_unit.contact_role,
                "contact_phone": business_unit.contact_phone,
                "contact_email": business_unit.contact_email,
                "academic_year_start": business_unit.academic_year_start,
                "academic_year_end": business_unit.academic_year_end,
            }
        )

    if not request.headers.get("HX-Request"):
        return render(
            request,
            "core/business_unit_form.html",
            {"form": form, "title": "Editar Unidade", "instance": business_unit},
        )
    return render(
        request,
        "core/partials/organization_information_form.html",
        {
            "form": form,
            "component_id": "business-unit-information-card",
            "component_title": "Informações da Unidade",
            "edit_url": request.path,
            "cancel_url": f"{request.path_info.removesuffix('editar/')}?component=information",
            "organization": business_unit,
        },
    )


@login_required
def school_detail(request: HttpRequest) -> HttpResponse:
    """Exibe os dados institucionais da empresa do tenant ativo."""
    from django.contrib import messages

    from addresses.selectors import AddressSelector
    from core.selectors import SchoolSelector

    school = SchoolSelector().get_current_school()
    if not school:
        messages.error(request, "Escola nao encontrada no tenant ativo.")
        return redirect("business_unit_list")

    addresses = AddressSelector().get_by_entity("school", school.pk)
    if request.headers.get("HX-Request") and request.GET.get("component") == "information":
        return render(
            request,
            "core/partials/school_information_card.html",
            {"school": school},
        )
    return render(
        request,
        "core/school_detail.html",
        {"school": school, "addresses": addresses},
    )


@login_required
def school_edit(request: HttpRequest) -> HttpResponse:
    """Tela de edicao dos dados da empresa (escola)."""
    from django.contrib import messages

    from base.exceptions import BusinessRuleViolationError, ValidationError
    from core.forms import SchoolEditForm
    from core.selectors import SchoolSelector
    from core.services import SchoolService

    school = SchoolSelector().get_current_school()
    if not school:
        messages.error(request, "Escola nao encontrada no tenant ativo.")
        return redirect("business_unit_list")

    if request.method == "POST":
        form = SchoolEditForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                service = SchoolService(user=request.user)
                data = form.cleaned_data.copy()

                # Tratar logo separadamente
                logo = data.pop("logo", None)
                service.update_school(school.pk, data)

                if logo:
                    service.update_logo(school.pk, logo)

                school = SchoolSelector().get_current_school()
                if request.headers.get("HX-Request"):
                    return render(
                        request,
                        "core/partials/school_information_card.html",
                        {"school": school, "saved": True},
                    )
                messages.success(request, "Configurações da escola atualizadas com sucesso.")
                return redirect("school_settings_detail")
            except ValidationError as exc:
                apply_validation_errors(form, exc)
            except BusinessRuleViolationError as exc:
                messages.error(request, exc.message)
    else:
        initial = {
            "name": school.name,
            "legal_name": school.legal_name,
            "trade_name": school.trade_name,
            "cnpj": school.cnpj or "",
            "state_registration": school.state_registration,
            "municipal_registration": school.municipal_registration,
            "phone": school.phone,
            "email": school.email,
            "contact_full_name": school.contact_full_name,
            "contact_role": school.contact_role,
            "contact_phone": school.contact_phone,
            "contact_email": school.contact_email,
            "academic_year_start": school.academic_year_start,
            "academic_year_end": school.academic_year_end,
        }
        form = SchoolEditForm(initial=initial)

    if not request.headers.get("HX-Request"):
        return render(
            request,
            "core/school_form.html",
            {
                "form": form,
                "school": school,
                "title": "Editar Escola",
                "instance": school,
            },
        )
    return render(
        request,
        "core/partials/organization_information_form.html",
        {
            "form": form,
            "component_id": "school-information-card",
            "component_title": "Informações da Escola",
            "edit_url": request.path,
            "cancel_url": f"{reverse('school_settings_detail')}?component=information",
            "organization": school,
        },
    )
