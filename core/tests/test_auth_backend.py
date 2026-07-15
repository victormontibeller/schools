"""Testes do backend tenant-specific de autenticação e permissões."""

import pytest
from django.contrib.auth.models import Permission
from django.utils import timezone

from core.auth_backends import TenantAuthenticationBackend


@pytest.mark.django_db
def test_backend_rejects_inactive_expired_and_unverified_demo_users(user):
    backend = TenantAuthenticationBackend()
    user.is_active = False
    assert backend.user_can_authenticate(user) is False

    user.is_active = True
    user.expires_at = timezone.now()
    assert backend.user_can_authenticate(user) is False

    user.expires_at = None
    user.access_mode = "DEMO"
    user.email_verified_at = None
    assert backend.user_can_authenticate(user) is False
    user.email_verified_at = timezone.now()
    assert backend.user_can_authenticate(user) is True


@pytest.mark.django_db
def test_backend_ignores_individual_django_permissions(user):
    backend = TenantAuthenticationBackend()
    allowed = Permission.objects.get(content_type__app_label="classes", codename="view_class")
    user.is_superuser = False
    user.user_permissions.add(allowed)

    assert backend.get_user_permissions(user) == set()
    assert backend.get_group_permissions(user) == set()
    assert backend.has_perm(user, "classes.view_class") is False

    user.is_superuser = True
    assert backend.has_perm(user, "classes.view_class") is True
