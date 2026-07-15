"""Regressões que garantem a ausência do suporte cross-schema."""

import pytest
from django.urls import Resolver404, resolve


def test_support_routes_and_model_do_not_exist():
    import tenancy.models

    assert not hasattr(tenancy.models, "SupportAccessGrant")
    with pytest.raises(Resolver404):
        resolve("/platform/support/")
    with pytest.raises(Resolver404):
        resolve("/support/consume/")


@pytest.mark.django_db
def test_support_mode_and_permission_do_not_exist():
    from django.contrib.auth.models import Permission

    from core.models import CustomUser

    assert "SUPPORT" not in CustomUser.AccessMode.values
    assert not Permission.objects.filter(codename="access_tenant").exists()
