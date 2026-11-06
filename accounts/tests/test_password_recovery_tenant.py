"""Consumo concorrente do token no PostgreSQL e limite no Redis compartilhado."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.test import override_settings

from accounts.authentication_limits import AuthenticationLimit
from accounts.recovery_services import PasswordRecoveryService
from accounts.recovery_tokens import recovery_token_generator
from base.context import current_tenant
from base.exceptions import BusinessRuleViolationError
from notifications.tests.test_outbox_tenant import outbox_tenant as tenant_fixture
from notifications.tests.test_outbox_tenant import race

pg_tenant = tenant_fixture
pytestmark = [
    pytest.mark.tenant,
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(os.environ.get("DJANGO_ENV") != "test_pg", reason="PostgreSQL"),
]


def test_concurrent_recovery_consumes_token_once_under_database_lock(pg_tenant):
    school, delivery = pg_tenant
    user = delivery.recipient
    token = recovery_token_generator.make_token(user)

    def confirm(index):
        try:
            PasswordRecoveryService().confirm_password_reset(
                user_id=user.pk,
                token=token,
                password=f"AuroraFicticia824!{index}",
                schema_name=school.schema_name,
            )
            return True
        except BusinessRuleViolationError:
            return False

    assert sorted(race(school, confirm)) == [False, True]


@pytest.mark.skipif(
    not os.environ.get("AUTH_LIMIT_TEST_REDIS_URL"), reason="Redis isolado explícito"
)
def test_real_redis_shares_atomic_limit_across_connections():
    cache_settings = {
        "authentication": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": os.environ["AUTH_LIMIT_TEST_REDIS_URL"],
            "KEY_PREFIX": f"schools-test-{uuid.uuid4().hex}",
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }

    def reserve(_):
        marker = current_tenant.set("redis_school")
        try:
            return AuthenticationLimit.reserve(
                scope="real",
                ip="192.0.2.5",
                recipient="ficticio@example.test",
                limit=100,
                seconds=5,
            )[0]
        finally:
            current_tenant.reset(marker)

    # Somente chaves de prefixo aleatório e TTL curto; nunca FLUSHDB no Redis da tarefa.
    with override_settings(CACHES=cache_settings):
        with ThreadPoolExecutor(max_workers=12) as executor:
            assert sum(executor.map(reserve, range(24))) == 3
