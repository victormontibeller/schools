"""Backends de cache: autenticação sempre compartilhada e sem fail-open em execução real."""


def build_caches(*, testing, redis_url):
    if testing:
        return {
            "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
            "authentication": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "auth-test",
            },
        }
    return {
        name: {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": redis_url,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "IGNORE_EXCEPTIONS": False,
            },
            "KEY_PREFIX": prefix,
        }
        for name, prefix in [("default", "schools"), ("authentication", "schools-auth")]
    }
