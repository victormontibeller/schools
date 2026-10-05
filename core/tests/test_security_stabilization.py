"""Regressões de escopo docente e proteção da fronteira HTTP."""

import datetime as dt
import io
import logging
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from django.http import Http404, HttpResponse
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from base.tests.factories import StudentFactory
from classes.models import Class, Enrollment
from core.access_selectors import ObjectAccessSelector
from core.models import RoleModuleAccess
from core.request_security import ActiveTenantMiddleware, HttpTracingMiddleware, LivenessMiddleware
from core.tests.test_rbac_policy import _role_user
from students.selectors import StudentSelector
from teachers.models import Teacher


@pytest.fixture
def teacher_scope(user):
    actor = _role_user("TEACHER", "scoped-teacher@example.test")
    teacher = Teacher.objects.create(user=actor, registration_number="SCOPE")
    cls = Class.objects.create(name="Scoped", academic_year=2026, class_teacher=teacher)
    student = StudentFactory()
    enrollment = Enrollment.objects.create(
        student=student,
        class_obj=cls,
        academic_year=2026,
        enrollment_date=timezone.localdate(),
    )
    return actor, teacher, cls, student, enrollment


@pytest.mark.django_db
@pytest.mark.parametrize(
    "part",
    ["teacher", "user", "user_deleted", "class", "enrollment", "future_enrollment", "student"],
)
def test_revoke_teacher_scope_when_component_invalid(teacher_scope, part):
    actor, teacher, cls, student, enrollment = teacher_scope
    assert ObjectAccessSelector.teacher_can_access_student(actor.pk, student.pk)
    instance = {
        "teacher": teacher,
        "user": actor,
        "user_deleted": actor,
        "class": cls,
        "enrollment": enrollment,
        "future_enrollment": enrollment,
        "student": student,
    }[part]
    if part == "future_enrollment":
        instance.enrollment_date = timezone.localdate() + dt.timedelta(days=1)
    elif part == "user_deleted":
        instance.deleted_at = timezone.now()
    else:
        instance.is_active = False
    instance.save()
    assert not ObjectAccessSelector.teacher_can_access_student(actor.pk, student.pk)
    assert (
        StudentSelector().list_students_for_user(user_id=actor.pk, role_name="TEACHER").total == 0
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route", ["student_profile", "student_guardians_component", "student_photo", "student_edit"]
)
def test_deny_teacher_known_student_url_without_enrollment(client, teacher_scope, route):
    actor, _, _, _, _ = teacher_scope
    outsider = StudentFactory()
    client.force_login(actor)
    assert client.get(reverse(route, args=[outsider.pk]), HTTP_HX_REQUEST="true").status_code == 403


@pytest.mark.django_db
def test_deny_global_guardian_search_even_with_student_edit(client, teacher_scope):
    actor, _, _, student, _ = teacher_scope
    RoleModuleAccess.objects.filter(role=actor.role, module_key="students").update(can_edit=True)
    client.force_login(actor)
    with patch("guardians.selectors.GuardianSelector.search_reusable") as search:
        assert (
            client.get(
                reverse("student_guardian_search", args=[student.pk]), {"q": "private"}
            ).status_code
            == 403
        )
    search.assert_not_called()


@pytest.mark.parametrize("inactive,deleted", [(True, None), (False, timezone.now())])
def test_reject_disabled_tenant_before_schema_selection(inactive, deleted):
    tenant = SimpleNamespace(schema_name="school_a", is_active=not inactive, deleted_at=deleted)
    middleware = ActiveTenantMiddleware(lambda request: HttpResponse())
    with patch(
        "django_tenants.middleware.main.TenantMainMiddleware.get_tenant", return_value=tenant
    ):
        with pytest.raises(Http404):
            middleware.get_tenant(Mock(), "school-a.example.test")


def test_keep_public_tenant_available_for_reactivation():
    tenant = SimpleNamespace(schema_name="public", is_active=False, deleted_at=None)
    middleware = ActiveTenantMiddleware(lambda request: HttpResponse())
    with patch(
        "django_tenants.middleware.main.TenantMainMiddleware.get_tenant", return_value=tenant
    ):
        assert middleware.get_tenant(Mock(), "platform.example.test") == tenant


@pytest.mark.parametrize("method", ["get", "head"])
def test_liveness_bypasses_database_and_host_policy(method, settings):
    settings.ALLOWED_HOSTS = ["schools.example.test"]
    settings.SECURE_SSL_REDIRECT = True
    downstream = Mock(side_effect=AssertionError("Downstream must not run"))
    response = LivenessMiddleware(downstream)(
        getattr(RequestFactory(), method)("/health/", HTTP_HOST="127.0.0.1:8000")
    )
    assert response.status_code == 200
    downstream.assert_not_called()


def test_liveness_does_not_bypass_other_paths():
    downstream = Mock(return_value=HttpResponse(status=404))
    assert (
        LivenessMiddleware(downstream)(RequestFactory().get("/health/private/")).status_code == 404
    )
    downstream.assert_called_once()


@pytest.mark.parametrize(
    "logger_name", ["django.request", "django.security.DisallowedHost", "django.server"]
)
def test_format_http_errors_without_secrets(logger_name):
    from logging.config import dictConfig

    from django.conf import settings

    marker = "SYNTHETIC-SECRET-DO-NOT-EXPORT"
    output = io.StringIO()
    dictConfig(settings.LOGGING)
    handler = logging.getLogger("django").handlers[0]
    old_stream = handler.stream
    handler.setStream(output)
    try:
        try:
            raise RuntimeError(marker)
        except RuntimeError:
            logging.getLogger(logger_name).error(
                "Bad path /%s?token=%s",
                marker,
                marker,
                exc_info=True,
                extra={"request": RequestFactory().get("/" + marker), "status_code": 500},
            )
    finally:
        handler.setStream(old_stream)
    assert marker not in output.getvalue()
    assert "http_request_completed" in output.getvalue()


def test_export_safe_http_span_on_unknown_error():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    middleware = HttpTracingMiddleware(lambda request: HttpResponse(status=500))
    middleware.tracer = provider.get_tracer("security-regression")
    middleware(RequestFactory().get("/SYNTHETIC-SECRET?token=SYNTHETIC-SECRET"))
    span = exporter.get_finished_spans()[0]
    assert span.name == "unresolved"
    assert "SYNTHETIC-SECRET" not in str(span.to_json())
    assert span.attributes["http.response.status_code"] == 500
    provider.shutdown()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route,kwargs",
    [
        ("guardian_invitation", {}),
        ("teacher_invitation", {"token": "invalid"}),
        ("password_reset_confirm", {"uidb64": "invalid", "token": "invalid"}),
        ("demo_verify", {"token": "invalid"}),
    ],
)
def test_token_pages_disallow_cache_and_only_share_origin(client, route, kwargs):
    response = client.get(reverse(route, kwargs=kwargs))
    assert response["Referrer-Policy"] == "strict-origin"
    assert response["Cache-Control"] == "no-store"


@pytest.mark.django_db
@pytest.mark.parametrize("condition", ["future", "expired", "inactive", "deleted"])
def test_schedule_validity_revokes_student_list_and_preserves_historical_matrix(
    teacher_scope, condition
):
    from agenda.models import Schedule, TimeSlot
    from agenda.selectors import ScheduleSelector
    from base.tests.factories import SubjectFactory

    actor, teacher, cls, student, _ = teacher_scope
    cls.class_teacher = None
    cls.save()
    today = timezone.localdate()
    slot = TimeSlot.objects.create(
        shift="MORNING", slot_number=1, start_time=dt.time(8), end_time=dt.time(9)
    )
    schedule = Schedule.objects.create(
        class_obj=cls,
        teacher=teacher,
        subject=SubjectFactory(),
        time_slot=slot,
        day_of_week="MON",
        valid_from=today - dt.timedelta(days=30),
    )
    assert ObjectAccessSelector.teacher_can_access_student(actor.pk, student.pk)
    if condition == "future":
        schedule.valid_from = today + dt.timedelta(days=1)
    elif condition == "expired":
        schedule.valid_until = today - dt.timedelta(days=1)
    elif condition == "inactive":
        schedule.is_active = False
    else:
        schedule.deleted_at = timezone.now()
    schedule.save()
    assert not ObjectAccessSelector.teacher_can_access_student(actor.pk, student.pk)
    assert (
        StudentSelector().list_students_for_user(user_id=actor.pk, role_name="TEACHER").total == 0
    )
    if condition == "expired":
        assert ScheduleSelector.teacher_can_access_class(
            cls.pk, user_id=actor.pk, as_of=today - dt.timedelta(days=2)
        )


def test_real_otel_entrypoint_never_exports_request_or_exception_secrets():
    import os
    import subprocess
    import sys
    from pathlib import Path

    script = """
import pytest
import django
import logging
import sys
import types
from django.conf import settings
django.setup()
assert not any("opentelemetry" in item for item in settings.MIDDLEWARE)
from unittest.mock import patch
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import path
from django.test import Client, override_settings
from opentelemetry import trace
marker = "SYNTHETIC-SECRET-EXPORTED"
def ok(request, token):
    return HttpResponse("ok")
def redirect(request, token):
    return HttpResponseRedirect("/success/" + token + "/")
def invalid(request, token):
    return HttpResponse(status=400)
def failure(request, token):
    raise RuntimeError(token)
module = types.ModuleType("safe_http_test_urls")
module.urlpatterns = [
    path("success/<token>/", ok, name="success"),
    path("redirect/<token>/", redirect, name="redirect"),
    path("invalid/<token>/", invalid, name="invalid"),
    path("failure/<token>/", failure, name="failure"),
]
from core.views.public import handler500, handler404
module.handler500 = handler500
module.handler404 = handler404
sys.modules[module.__name__] = module
def safe_render(*args, **kwargs):
    return HttpResponse(status=kwargs["status"])
with patch("core.views.public.render", side_effect=safe_render), override_settings(
    ROOT_URLCONF=module.__name__, DEBUG=False, ALLOWED_HOSTS=["testserver"],
    MIDDLEWARE=["core.request_security.HttpTracingMiddleware",
                "core.middleware.SecurityHeadersMiddleware"],
):
    client = Client(raise_request_exception=False)
    for route in ("success", "redirect", "invalid", "failure", "unknown"):
        response = client.get(
            "/" + route + "/" + marker + "/?token=" + marker,
            HTTP_REFERER="https://example.test/" + marker,
        )
        assert response.status_code in {200, 302, 400, 404, 500}
trace.get_tracer_provider().force_flush()
"""
    env = dict(
        os.environ,
        DJANGO_SETTINGS_MODULE="core.settings",
        OTEL_PYTHON_DISABLED_INSTRUMENTATIONS="django,logging",
        OTEL_TRACES_EXPORTER="console",
        OTEL_METRICS_EXPORTER="none",
        OTEL_LOGS_EXPORTER="none",
        OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED="false",
        LOG_LEVEL="INFO",
    )
    process = subprocess.run(  # noqa: S603 - trusted runtime and fixed synthetic script
        [
            str(Path(sys.executable).with_name("opentelemetry-instrument")),
            sys.executable,
            "-c",
            script,
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert "SYNTHETIC-SECRET-EXPORTED" not in process.stdout + process.stderr
    assert '"http.response.status_code": 500' in process.stdout
    assert '"name": "failure"' in process.stdout


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route", ["addresses:address_card", "addresses:address_create", "addresses:address_edit"]
)
def test_deny_student_address_routes_outside_teacher_scope(client, teacher_scope, route):
    from addresses.models import Address, StudentAddress

    actor, _, _, _, _ = teacher_scope
    RoleModuleAccess.objects.filter(role=actor.role, module_key="students").update(
        can_edit=True, can_create=True
    )
    outsider = StudentFactory()
    address = Address.objects.create(
        street="Private",
        number="1",
        district="District",
        postal_code="01001000",
        city="São Paulo",
        state="SP",
    )
    StudentAddress.objects.create(student=outsider, address=address)
    client.force_login(actor)
    args = [address.pk] if route == "addresses:address_edit" else ["student", outsider.pk]
    assert client.get(reverse(route, args=args)).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "command",
    ["update", "deactivate", "restore", "address_create", "address_update", "address_deactivate"],
)
def test_deny_student_mutations_outside_teacher_scope_before_audit(teacher_scope, command):
    from addresses.models import Address, StudentAddress
    from addresses.services import AddressService
    from base.exceptions import PermissionDeniedError
    from students.services import StudentService

    actor, _, _, _, _ = teacher_scope
    RoleModuleAccess.objects.filter(role=actor.role, module_key="students").update(
        can_edit=True, can_create=True, can_deactivate=True
    )
    outsider = StudentFactory()
    address = Address.objects.create(
        street="Private",
        number="1",
        district="District",
        postal_code="01001000",
        city="São Paulo",
        state="SP",
    )
    StudentAddress.objects.create(student=outsider, address=address)
    service = StudentService(user=actor)
    addresses = AddressService(user=actor)
    calls = {
        "update": lambda: service.update_student(outsider.pk, {"first_name": "Changed"}),
        "deactivate": lambda: service.deactivate_student(outsider.pk),
        "restore": lambda: service.restore_student(outsider.pk),
        "address_create": lambda: addresses.create_address_for_student(outsider.pk, {}),
        "address_update": lambda: addresses.update_address(address.pk, {}),
        "address_deactivate": lambda: addresses.deactivate_address(address.pk),
    }
    with (
        patch.object(service, "_record_audit") as student_audit,
        patch.object(addresses, "_record_audit") as address_audit,
    ):
        with pytest.raises(PermissionDeniedError):
            calls[command]()
        student_audit.assert_not_called()
        address_audit.assert_not_called()
    outsider.refresh_from_db()
    assert outsider.first_name == "Aluno" and outsider.is_active
