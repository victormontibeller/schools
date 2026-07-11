"""Testes de concessões temporárias de suporte."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core import signing
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from base.exceptions import BusinessRuleViolationError, PermissionDeniedError
from tenancy.services import SUPPORT_TOKEN_SALT, SupportAccessService


@pytest.fixture()
def demo_school(user):
    """Cria tenant DEMO no perfil SQLite."""
    from tenancy.models import Domain, School

    school = School.objects.create(
        schema_name="demo",
        name="Demo",
        created_by=user,
        updated_by=user,
    )
    Domain.objects.create(domain="demo.localhost", tenant=school, is_primary=True)
    return school


@pytest.mark.django_db
def test_create_grant_requires_platform_permission(demo_school):
    """Usuário comum não pode criar concessão cross-tenant."""
    from core.models import CustomUser

    common = CustomUser.objects.create_user(
        email="common@test.local",
        password="Senha123",
        first_name="Common",
        last_name="User",
    )
    with pytest.raises(PermissionDeniedError):
        SupportAccessService(user=common).create_grant(
            demo_school.pk, "Suporte solicitado pela escola"
        )


@pytest.mark.django_db
def test_create_grant_returns_signed_single_tenant_token(user, demo_school):
    """Concessão autorizada contém apenas o ID opaco do registro."""
    grant, token = SupportAccessService(user=user).create_grant(
        demo_school.pk, "Diagnóstico solicitado pela coordenação"
    )
    payload = signing.loads(token, salt=SUPPORT_TOKEN_SALT)
    assert payload == {"grant_id": str(grant.pk)}
    assert grant.tenant == demo_school


@pytest.mark.django_db
def test_consume_grant_rejects_different_tenant(user, demo_school):
    """Token nunca pode ser consumido em schema diferente."""
    _, token = SupportAccessService(user=user).create_grant(
        demo_school.pk, "Diagnóstico solicitado pela coordenação"
    )
    with pytest.raises(PermissionDeniedError):
        SupportAccessService().consume_grant(token, "outra_escola")


@pytest.mark.django_db
def test_consume_grant_is_single_use(user, demo_school):
    """Segundo consumo do mesmo token é bloqueado."""
    _, token = SupportAccessService(user=user).create_grant(
        demo_school.pk, "Diagnóstico solicitado pela coordenação"
    )
    grant, _ = SupportAccessService().consume_grant(token, "demo")
    from audit.models import AuditLog

    assert AuditLog.objects.filter(
        support_grant_id=grant.pk,
        platform_actor_id=user.pk,
    ).exists()
    with pytest.raises(BusinessRuleViolationError):
        SupportAccessService().consume_grant(token, "demo")


@pytest.mark.django_db
def test_consume_grant_rejects_expired_token_record(user, demo_school):
    """Concessão expirada no banco é recusada mesmo com assinatura válida."""
    grant, token = SupportAccessService(user=user).create_grant(
        demo_school.pk, "Diagnóstico solicitado pela coordenação"
    )
    grant.expires_at = timezone.now() - timedelta(seconds=1)
    grant.save(update_fields=["expires_at"])
    with pytest.raises(BusinessRuleViolationError):
        SupportAccessService().consume_grant(token, "demo")


@pytest.mark.django_db
def test_support_form_and_selector_list_only_tenants(user, demo_school):
    """Formulário e selector não oferecem o schema público como destino."""
    from tenancy.forms import SupportAccessForm
    from tenancy.models import School
    from tenancy.selectors import SchoolSelector

    School.objects.create(schema_name="public", name="Platform", created_by=user, updated_by=user)
    form = SupportAccessForm()
    assert form.fields["tenant_id"].choices == [(str(demo_school.pk), "Demo")]
    result = SchoolSelector().list_active()
    assert {school.schema_name for school in result.items} == {"demo", "public"}
    assert SchoolSelector().get_current_school().schema_name == "public"


@pytest.mark.django_db
def test_support_create_view_renders_and_redirects_to_tenant(client, user, demo_school):
    """Operador autorizado informa motivo e é enviado ao domínio do tenant."""
    client.force_login(user)
    response = client.get(reverse("support_access_create"))
    assert response.status_code == 200

    response = client.post(
        reverse("support_access_create"),
        {"tenant_id": str(demo_school.pk), "reason": "Diagnóstico autorizado pela escola"},
    )
    assert response.status_code == 302
    assert response.url.startswith("https://demo.localhost/support/consume/?token=")


@pytest.mark.django_db
def test_support_consume_view_records_operator_and_grant_in_session(client, user):
    """Callback autentica conta técnica preservando o ator público na sessão."""
    grant = SimpleNamespace(
        pk="1c266dbd-68bf-4c9b-9676-151f6643aa88",
        operator_id=user.pk,
        expires_at=timezone.now(),
    )
    with patch("tenancy.services.SupportAccessService.consume_grant", return_value=(grant, user)):
        response = client.get(reverse("support_access_consume"), {"token": "signed"})
    assert response.status_code == 302
    assert response.url == reverse("dashboard")
    assert client.session["platform_actor_id"] == str(user.pk)
    assert client.session["support_grant_id"] == str(grant.pk)


@pytest.mark.django_db
def test_support_end_view_closes_grant_and_logs_out(client, user):
    """Encerramento explícito invalida a sessão técnica."""
    client.force_login(user)
    session = client.session
    session["support_grant_id"] = "1c266dbd-68bf-4c9b-9676-151f6643aa88"
    session.save()
    with patch("tenancy.services.SupportAccessService.end_grant") as end_grant:
        response = client.post(reverse("support_access_end"))
    assert response.status_code == 302
    end_grant.assert_called_once()
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["platform.localhost"])
def test_platform_dashboard_uses_only_shared_catalog(client, user, demo_school):
    """Operador público vê indicadores e escolas sem consultar tabelas escolares."""
    from tenancy.models import Domain, School

    user.is_staff = True
    user.is_superuser = True
    user.save(update_fields=["is_staff", "is_superuser"])
    School.objects.create(
        schema_name="public",
        name="School Manager Platform",
        created_by=user,
        updated_by=user,
    )
    Domain.objects.create(domain="localhost", tenant=demo_school, is_primary=False)
    client.force_login(user)

    response = client.get(reverse("platform_dashboard"), HTTP_HOST="platform.localhost")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Administração da Plataforma" in content
    assert "Demo" in content
    assert "Professores" not in content
    assert "Acesso de suporte" in content


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["platform.localhost"])
def test_platform_login_redirects_to_platform_dashboard(client, user):
    """Login no domínio público nunca encaminha ao dashboard escolar."""
    user.set_password("Senha123")
    user.is_staff = True
    user.save(update_fields=["password", "is_staff"])

    response = client.post(
        reverse("login"),
        {"email": user.email, "password": "Senha123"},
        HTTP_HOST="platform.localhost",
    )

    assert response.status_code == 302
    assert response.url == reverse("platform_dashboard")
