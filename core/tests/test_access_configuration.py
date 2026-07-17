"""Testes da matriz tenant-specific de acessos por grupo e ação."""

import uuid
from types import SimpleNamespace

import pytest
from django.urls import reverse

from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from core.access_catalog import (
    ACTION_FIELDS,
    CONFIGURABLE_ROLES,
    CREATE,
    DEACTIVATE,
    DEFAULT_ACCESS,
    EDIT,
    MODULES,
    ROLE_LABELS,
    SECRETARY,
    TEACHER,
    VIEW,
    ModuleDefinition,
    action_for_operation,
    default_actions,
    department_defaults,
    module_for_app,
)


def _create_role_user(role_name: str, email: str):
    from core.models import CustomUser, Role

    role = Role.objects.get(name=role_name)
    return CustomUser.objects.create_user(
        email=email,
        password="Senha123",
        first_name="Teste",
        last_name="Acesso",
        role=role,
    )


def _current_matrix_state():
    from core.access.selectors import AccessConfigurationSelector

    matrix = AccessConfigurationSelector().get_full_matrix()
    access = {
        role_name: {
            module_key: {action for action, enabled in values.items() if enabled}
            for module_key, values in role_values.items()
        }
        for role_name, role_values in matrix.values.items()
    }
    versions = {role.name: role.version for role in matrix.roles}
    return access, versions


def _current_matrix_payload():
    from core.access.forms import AccessConfigurationForm

    access, versions = _current_matrix_state()
    payload = {
        AccessConfigurationForm.version_field_name(role_name): str(version)
        for role_name, version in versions.items()
    }
    for role_name, role_values in access.items():
        for module_key, actions in role_values.items():
            if actions:
                payload[AccessConfigurationForm.field_name(module_key, role_name)] = list(actions)
    return payload


@pytest.mark.django_db
def test_bootstrap_creates_exact_defaults_without_deactivation():
    from core.models import RoleModuleAccess

    for module in MODULES:
        for role_name in module.eligible_roles:
            access = RoleModuleAccess.objects.get(role__name=role_name, module_key=module.key)
            expected = DEFAULT_ACCESS.get(module.key, {}).get(role_name, frozenset())
            for action, field in ACTION_FIELDS.items():
                assert getattr(access, field) is (action in expected)
            assert access.can_deactivate is False


@pytest.mark.django_db
def test_access_settings_renders_only_configurable_groups(client, user):
    client.force_login(user)

    response = client.get(reverse("access_settings"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "O Administrador sempre possui acesso total" not in content
    for role_name in CONFIGURABLE_ROLES:
        assert f">{ROLE_LABELS[role_name]}</th>" in content
    assert ">Administrador</th>" not in content
    assert "Matriz de acessos" in content
    assert "Ações de Secretaria" not in content
    assert content.count("sm-access-role-column") == 5
    assert 'data-bs-auto-close="outside"' in content
    assert "Escopo próprio" not in content
    assert "Vinculados" not in content
    assert "sm-access-scope-note" not in content
    assert "sm-access-scope-badge" not in content
    assert "sm-compact-table sm-access-table" in content
    assert '<h6 class="card-title mb-0">Matriz de acessos</h6>' in content
    assert 'class="btn btn-sm btn-primary"' in content
    assert "feather-save" in content
    assert 'class="input-group input-group-sm sm-list-search"' in content
    assert "sm-access-search-wrap" in content
    assert 'placeholder="Buscar..."' in content
    assert 'aria-label="Buscar módulos"' in content
    assert "data-access-search-input" in content
    assert "data-access-search-clear" in content
    assert "data-access-module-row" in content
    assert "data-access-department-row" in content
    assert 'data-access-search="Secretaria Salas"' in content
    assert 'data-access-search="Secretaria Aspectos da rotina"' in content
    assert "Nenhum módulo encontrado." in content
    assert '<div class="fw-semibold mb-2">' not in content
    assert 'aria-label="Combinação indisponível"' in content


@pytest.mark.django_db
def test_access_settings_denies_non_administrator(client):
    client.force_login(_create_role_user("COORDINATOR", "coord-access@test.com"))

    assert client.get(reverse("access_settings")).status_code == 403


@pytest.mark.django_db
def test_bootstrap_preserves_customized_access(user):
    from core.access.services import AccessConfigurationService
    from core.models import Role, RoleModuleAccess

    role = Role.objects.get(name="SECRETARY")
    access = RoleModuleAccess.objects.get(role=role, module_key="financeiro")
    access.can_view = True
    access.updated_by = user
    access.save()

    assert AccessConfigurationService().create_missing_access_defaults() == 0
    access.refresh_from_db()
    assert access.can_view is True


@pytest.mark.django_db
def test_http_action_uses_configured_action_not_only_module(client):
    finance_user = _create_role_user("FINANCE", "finance-actions@test.com")
    client.force_login(finance_user)

    assert client.get(reverse("classes_list")).status_code == 200
    assert client.post(reverse("class_create"), {}).status_code == 403


@pytest.mark.django_db
def test_service_call_cannot_bypass_action_policy():
    from classes.services import ClassService

    finance_user = _create_role_user("FINANCE", "finance-service@test.com")
    with pytest.raises(PermissionDeniedError):
        ClassService(user=finance_user).create_class({})


@pytest.mark.django_db
def test_unknown_module_and_action_are_denied():
    from core.permissions import can_access

    secretary = _create_role_user("SECRETARY", "secretary-unknown@test.com")
    assert can_access(secretary, "unknown", "view") is False
    assert can_access(secretary, "students", "publish") is False


@pytest.mark.django_db
def test_users_with_permission_matches_role_matrix_and_admin_overrides():
    from core.access.selectors import AccessConfigurationSelector

    admin = _create_role_user("ADMIN", "admin-query@test.com")
    coordinator = _create_role_user("COORDINATOR", "coord-query@test.com")
    teacher = _create_role_user("TEACHER", "teacher-query@test.com")
    finance = _create_role_user("FINANCE", "finance-query@test.com")

    users = AccessConfigurationSelector.users_with_permission("student_diary", "edit")

    assert admin in users
    assert coordinator in users
    assert teacher in users
    assert finance not in users
    assert not AccessConfigurationSelector.users_with_permission("unknown", "edit").exists()
    assert not AccessConfigurationSelector.users_with_permission(
        "student_diary", "publish"
    ).exists()


@pytest.mark.django_db
def test_deactivation_is_denied_by_default(client):
    coordinator = _create_role_user("COORDINATOR", "coord-deactivate@test.com")
    client.force_login(coordinator)

    response = client.post(
        reverse(
            "activity_group_deactivate",
            kwargs={"pk": uuid.uuid4(), "group_id": uuid.uuid4()},
        )
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_access_form_normalizes_dependencies_and_builds_rows():
    from core.access.forms import AccessConfigurationForm

    versions = {role_name: 0 for role_name in CONFIGURABLE_ROLES}
    form = AccessConfigurationForm(
        {
            **{
                AccessConfigurationForm.version_field_name(role_name): "0"
                for role_name in CONFIGURABLE_ROLES
            },
            AccessConfigurationForm.field_name("students", "SECRETARY"): [EDIT],
            AccessConfigurationForm.field_name("teachers", "SECRETARY"): [VIEW, CREATE],
        },
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["access_matrix"]["SECRETARY"]["students"] == {VIEW, EDIT}
    assert form.cleaned_data["access_matrix"]["SECRETARY"]["teachers"] == {VIEW, CREATE}
    assert form.cleaned_data["expected_versions"] == versions
    assert len(form.role_columns) == 5
    assert len(form.matrix_rows) == len(MODULES)
    classes = next(row for row in form.matrix_rows if row["module"].key == "classes")
    assert classes["cells"][-1]["available"] is False
    assert all("scope_label" not in cell for row in form.matrix_rows for cell in row["cells"])


def test_diary_configuration_exposes_only_view_and_edit_actions():
    from core.access.forms import AccessConfigurationForm

    form = AccessConfigurationForm()
    secretary_field = form.fields[
        AccessConfigurationForm.field_name("diary_configuration", "SECRETARY")
    ]
    coordinator_field = form.fields[
        AccessConfigurationForm.field_name("diary_configuration", "COORDINATOR")
    ]

    assert tuple(value for value, _label in secretary_field.choices) == (VIEW, EDIT)
    assert tuple(value for value, _label in coordinator_field.choices) == (VIEW, EDIT)
    assert "access__diary_configuration__TEACHER" not in form.fields


@pytest.mark.django_db
def test_access_migration_reconciles_defaults_and_preserves_room_deactivation():
    import importlib

    from django.apps import apps

    from core.models import RoleModuleAccess

    rooms_access = RoleModuleAccess.objects.get(
        role__name="SECRETARY",
        module_key="rooms",
    )
    rooms_access.can_view = False
    rooms_access.can_create = False
    rooms_access.can_edit = False
    rooms_access.can_deactivate = True
    rooms_access.save()
    RoleModuleAccess.objects.filter(
        role__name__in=("SECRETARY", "COORDINATOR"),
        module_key="diary_configuration",
    ).update(
        can_view=False,
        can_create=True,
        can_edit=False,
        can_deactivate=True,
    )

    migration = importlib.import_module(
        "core.migrations.0003_secretaria_rooms_diary_configuration_access"
    )
    migration.reconcile_secretary_access(apps, None)

    rooms_access.refresh_from_db()
    assert rooms_access.can_view is True
    assert rooms_access.can_create is True
    assert rooms_access.can_edit is True
    assert rooms_access.can_deactivate is True
    for role_name in ("SECRETARY", "COORDINATOR"):
        access = RoleModuleAccess.objects.get(
            role__name=role_name,
            module_key="diary_configuration",
        )
        assert access.can_view is True
        assert access.can_create is False
        assert access.can_edit is True
        assert access.can_deactivate is False


def test_access_form_rejects_unknown_module_and_action_tampering():
    from core.access.forms import AccessConfigurationForm

    versions = {
        AccessConfigurationForm.version_field_name(role_name): "0"
        for role_name in CONFIGURABLE_ROLES
    }
    form = AccessConfigurationForm(
        {
            **versions,
            "access__unknown__SECRETARY": [VIEW],
            AccessConfigurationForm.field_name("students", "SECRETARY"): ["publish"],
        },
    )

    assert form.is_valid() is False
    assert "inválidos" in form.non_field_errors()[0]
    assert "Faça uma escolha válida" in str(form.errors)


@pytest.mark.django_db
def test_access_selector_reports_missing_role_in_full_matrix():
    from core.access.selectors import AccessConfigurationSelector
    from core.models import Role

    selector = AccessConfigurationSelector()
    full_matrix = selector.get_full_matrix()
    assert tuple(role.name for role in full_matrix.roles) == CONFIGURABLE_ROLES
    assert full_matrix.values["SECRETARY"]["students"][VIEW] is True
    assert "classes" not in full_matrix.values["GUARDIAN"]

    secretary = Role.objects.get(name="SECRETARY")
    Role.objects.filter(pk=secretary.pk).update(is_active=False)
    with pytest.raises(ObjectNotFoundError):
        selector.get_full_matrix()


@pytest.mark.django_db
def test_access_matrix_updates_only_changed_group_and_skips_noop_audit(user):
    from audit.models import AuditLog
    from core.access.services import AccessConfigurationService
    from core.models import Role, RoleModuleAccess

    service = AccessConfigurationService(user=user)
    access_matrix, versions = _current_matrix_state()
    audit_count = AuditLog.objects.count()
    service.update_access_matrix(access_matrix, versions)

    assert AuditLog.objects.count() == audit_count
    assert {
        role.name: role.version for role in Role.objects.filter(name__in=CONFIGURABLE_ROLES)
    } == versions

    access_matrix, versions = _current_matrix_state()
    access_matrix["SECRETARY"]["students"] = {EDIT, DEACTIVATE}
    service.update_access_matrix(access_matrix, versions)

    updated_versions = {
        role.name: role.version for role in Role.objects.filter(name__in=CONFIGURABLE_ROLES)
    }
    assert updated_versions["SECRETARY"] == versions["SECRETARY"] + 1
    assert all(
        updated_versions[role_name] == version
        for role_name, version in versions.items()
        if role_name != "SECRETARY"
    )
    student_access = RoleModuleAccess.objects.get(role__name="SECRETARY", module_key="students")
    assert student_access.can_view is True
    assert student_access.can_create is False
    assert student_access.can_edit is True
    assert student_access.can_deactivate is True
    assert AuditLog.objects.filter(
        model_name="RoleModuleAccess",
        object_id=str(student_access.pk),
        operation="UPDATE",
    ).exists()


@pytest.mark.django_db
def test_access_matrix_rolls_back_every_group_on_stale_version(user):
    from core.access.services import AccessConfigurationService
    from core.models import Role, RoleModuleAccess

    service = AccessConfigurationService(user=user)
    access_matrix, versions = _current_matrix_state()
    access_matrix["SECRETARY"]["students"].add(DEACTIVATE)
    finance = Role.objects.get(name="FINANCE")
    finance.updated_by = user
    finance.save(update_fields=["updated_by", "updated_at"])

    with pytest.raises(BusinessRuleViolationError):
        service.update_access_matrix(access_matrix, versions)

    assert (
        RoleModuleAccess.objects.get(role__name="SECRETARY", module_key="students").can_deactivate
        is False
    )


@pytest.mark.django_db
def test_access_matrix_rejects_incomplete_roles_modules_and_unsupported_actions(user):
    from core.access.services import AccessConfigurationService

    service = AccessConfigurationService(user=user)
    access_matrix, versions = _current_matrix_state()

    incomplete_roles = dict(access_matrix)
    incomplete_roles.pop("GUARDIAN")
    with pytest.raises(ValidationError):
        service.update_access_matrix(incomplete_roles, versions)

    incomplete_modules = {role: dict(values) for role, values in access_matrix.items()}
    incomplete_modules["SECRETARY"].pop("students")
    with pytest.raises(ValidationError):
        service.update_access_matrix(incomplete_modules, versions)

    invalid_action = {role: dict(values) for role, values in access_matrix.items()}
    invalid_action["SECRETARY"]["students"] = {VIEW, "publish"}
    with pytest.raises(ValidationError):
        service.update_access_matrix(invalid_action, versions)


@pytest.mark.django_db
def test_access_settings_post_redirects_and_htmx_renders_saved_state(client, user):
    client.force_login(user)
    payload = _current_matrix_payload()

    response = client.post(reverse("access_settings"), payload)
    assert response.status_code == 302
    assert response.url == reverse("access_settings")

    payload = _current_matrix_payload()
    response = client.post(
        reverse("access_settings"),
        payload,
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="access-matrix-card",
    )
    assert response.status_code == 200
    assert "Acessos atualizados com sucesso" in response.content.decode()
    assert "<html" not in response.content.decode()


@pytest.mark.django_db
def test_access_settings_post_does_not_preload_matrix(client, user):
    from unittest.mock import patch

    client.force_login(user)
    payload = _current_matrix_payload()

    with patch(
        "core.access.selectors.AccessConfigurationSelector.get_full_matrix"
    ) as get_full_matrix:
        response = client.post(reverse("access_settings"), payload)

    assert response.status_code == 302
    get_full_matrix.assert_not_called()


@pytest.mark.django_db
def test_access_settings_renders_concurrency_conflict(client, user):
    from core.access.services import AccessConfigurationService

    client.force_login(user)
    payload = _current_matrix_payload()
    access_matrix, versions = _current_matrix_state()
    access_matrix["SECRETARY"]["students"].add(DEACTIVATE)
    AccessConfigurationService(user=user).update_access_matrix(access_matrix, versions)

    response = client.post(reverse("access_settings"), payload)

    assert response.status_code == 200
    assert "alterados por outra pessoa" in response.content.decode()


def test_catalog_resolves_modules_actions_and_department_inheritance(monkeypatch):
    from core import access_catalog

    assert module_for_app("teachers", subject=True) == "subjects"
    assert module_for_app("students") == "students"
    assert module_for_app("unknown") is None
    assert action_for_operation("remove_member", is_post=False) == "deactivate"
    assert action_for_operation("create_item", is_post=False) == CREATE
    assert action_for_operation("send_notice", is_post=False) == EDIT
    assert action_for_operation("details", is_post=False) == VIEW

    assert department_defaults("Acadêmico", "COORDINATOR") == {VIEW, CREATE, EDIT}
    assert department_defaults("Secretaria", "SECRETARY") == {VIEW, CREATE, EDIT}
    assert department_defaults("Secretaria", "COORDINATOR") == {VIEW}
    assert department_defaults("Coordenação", "COORDINATOR") == {VIEW, CREATE, EDIT}
    assert department_defaults("Coordenação", "TEACHER") == {VIEW}
    assert department_defaults("Financeiro", "FINANCE") == {VIEW, CREATE, EDIT}
    assert department_defaults("Acompanhamento", "GUARDIAN") == {VIEW}
    assert department_defaults("Administração", "SECRETARY") == frozenset()

    future = ModuleDefinition(
        key="future_academic",
        label="Futuro",
        department="Acadêmico",
        eligible_roles=frozenset({SECRETARY, TEACHER}),
        scoped_roles=frozenset({TEACHER}),
    )
    monkeypatch.setitem(access_catalog.MODULES_BY_KEY, future.key, future)
    assert default_actions(future.key, TEACHER) == {VIEW, CREATE, EDIT}
    assert default_actions(future.key, SECRETARY) == frozenset()
    assert default_actions("missing", TEACHER) == frozenset()


def test_access_declarations_resolve_strictly_for_views_and_services():
    from core.permissions import (
        access_policy,
        can_execute_service,
        modules_for_user,
        resolve_view_access,
    )

    with pytest.raises(ValueError):
        access_policy("missing", VIEW)
    with pytest.raises(ValueError):
        access_policy("students", "publish")

    @access_policy("students", EDIT)
    def explicit_view(request):
        return request

    assert resolve_view_access(explicit_view, "anything", "GET") == ("students", EDIT)

    def subject_view(request):
        return request

    subject_view.__module__ = "teachers.views"
    assert resolve_view_access(subject_view, "subject_list", "GET") == ("subjects", VIEW)

    def core_view(request):
        return request

    core_view.__module__ = "core.views"
    assert resolve_view_access(core_view, "dashboard", "GET") == ("dashboard", VIEW)
    assert resolve_view_access(core_view, "school_edit", "POST") == ("__admin__", EDIT)

    def address_view(request):
        return request

    address_view.__module__ = "addresses.views"
    assert resolve_view_access(
        address_view, "address_edit", "POST", {"entity_type": "guardian"}
    ) == ("guardians", EDIT)

    def unknown_view(request):
        return request

    unknown_view.__module__ = "unknown.views"
    assert resolve_view_access(unknown_view, "index", "GET") == (None, VIEW)

    secretary = SimpleNamespace(
        is_authenticated=True,
        is_superuser=False,
        access_mode="STANDARD",
        role=SimpleNamespace(name="SECRETARY"),
    )
    assert can_execute_service(secretary, "addresses", "update_teacher_address") is True
    assert can_execute_service(secretary, "addresses", "update_business_unit_address") is False
    assert can_execute_service(secretary, "unknown", "update_record") is False
    assert "students" in modules_for_user(secretary)

    admin = SimpleNamespace(
        is_authenticated=True,
        is_superuser=False,
        role=SimpleNamespace(name="ADMIN"),
    )
    assert modules_for_user(admin) == {"*"}
