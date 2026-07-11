"""
Settings único para o projeto School Manager.

Detecta o ambiente automaticamente:
  - TESTING:  perfil rápido (SQLite, sem django_tenants) — default em pytest
  - TEST_PG:  perfil multi-tenant completo (PostgreSQL + django_tenants) — DJANGO_ENV=test_pg
  - PRODUCTION: quando DJANGO_ENV=production no ambiente
  - DEVELOPMENT: padrão
Ver ADR-0001 — Bifurcação TESTING.
"""

import sys
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Detecção de ambiente ───────────────────────────────────────────────────────
_IN_PYTEST = "pytest" in sys.modules
DJANGO_ENV = config("DJANGO_ENV", default="development")
TEST_PG = _IN_PYTEST and DJANGO_ENV == "test_pg"
TESTING = _IN_PYTEST and not TEST_PG
DEBUG = TEST_PG or TESTING or config("DEBUG", default=True, cast=bool)

DEV_SECRET_KEY = "dev-secret-key-not-for-production-change-me"  # noqa: S105
SECRET_KEY = config("SECRET_KEY", default=DEV_SECRET_KEY)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())
TRUSTED_PROXY_IPS = config("TRUSTED_PROXY_IPS", default="", cast=Csv())

if DJANGO_ENV == "production":
    if DEBUG:
        raise RuntimeError("DEBUG deve ser False em produção.")
    if SECRET_KEY == DEV_SECRET_KEY:
        raise RuntimeError("SECRET_KEY obrigatória e sem valor padrão em produção.")
    if not ALLOWED_HOSTS:
        raise RuntimeError("ALLOWED_HOSTS obrigatório em produção.")

# ── Apps ───────────────────────────────────────────────────────────────────────
BASE_APPS = [
    "axes",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
    "tenancy",
    "core",
    "accounts",
    "locations",
    "audit",
]

# Observabilidade via django-prometheus exposta em /metrics/ (Sprint 08.5).
# Em ambiente de testes unitários, mantemos fora para não interferir no SQLite
# in-memory e no roteamento de castas do django_tenants.
if not TESTING:
    BASE_APPS.append("django_prometheus")

# Apps que rodam por schema de tenant (dados por escola)
TENANT_SPECIFIC_APPS = [
    "teachers",
    "students",
    "guardians",
    "classes",
    "rooms",
    "agenda",
    "activities",
    "academic_calendar",
    "attendance",
    "enrollments",
    "notifications",
    "dashboard",
    "addresses",
    "financeiro",
]

if TESTING:
    # Perfil rápido: sem django_tenants, SQLite, fixtures mínimas.
    INSTALLED_APPS = BASE_APPS + TENANT_SPECIFIC_APPS
    DATABASE_ROUTERS = []
else:
    # Perfil "full" (dev, prod e TEST_PG): django_tenants + PostgreSQL.
    SHARED_APPS = ["django_tenants"] + BASE_APPS
    # Auth, sessões e o CustomUser existem no public e isoladamente em cada
    # schema. `tenancy` permanece exclusivamente compartilhado.
    TENANT_APPS = [
        "django.contrib.contenttypes",
        "django.contrib.auth",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.admin",
        "core",
        "audit",
    ] + TENANT_SPECIFIC_APPS
    INSTALLED_APPS = list(SHARED_APPS) + [a for a in TENANT_APPS if a not in SHARED_APPS]
    DATABASE_ROUTERS = ["django_tenants.routers.TenantSyncRouter"]

TENANT_MODEL = "tenancy.School"
TENANT_DOMAIN_MODEL = "tenancy.Domain"

# ── Middleware ─────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    *([] if TESTING else ["django_prometheus.middleware.PrometheusBeforeMiddleware"]),
    *([] if TESTING else ["django_tenants.middleware.main.TenantMainMiddleware"]),
    "core.middleware.TenantContextMiddleware",
    "axes.middleware.AxesMiddleware",
    "core.middleware.CorrelationIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.HtmxBoostMiddleware",
    "core.middleware.ExceptionHandlerMiddleware",
    "core.middleware.PermissionPolicyMiddleware",
    "core.middleware.AuditContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    *([] if TESTING else ["django_prometheus.middleware.PrometheusAfterMiddleware"]),
]

if DEBUG and not TESTING:
    try:
        import debug_toolbar  # noqa: F401

        INSTALLED_APPS += ["debug_toolbar"]
        MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE
        INTERNAL_IPS = ["127.0.0.1"]
    except ImportError:
        pass

# ── URLs / WSGI / ASGI ────────────────────────────────────────────────────────
ROOT_URLCONF = "core.urls"
WSGI_APPLICATION = "core.wsgi.application"
ASGI_APPLICATION = "core.asgi.application"

# ── Templates ─────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.current_school",
                "core.context_processors.support_access",
                "core.context_processors.accessible_modules",
                "core.context_processors.school_navigation",
            ],
        },
    },
]

# ── Banco de dados ─────────────────────────────────────────────────────────────
if TESTING:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
else:
    # Perfil "full" (dev, prod e TEST_PG): django_tenants + PostgreSQL.
    _db_name = config("DB_NAME", default="schools_db")
    if TEST_PG:
        # DB dedicado em testes evita colidir com o dev.
        _db_name = config("DB_TEST_NAME", default="schools_test_db")
    DATABASES = {
        "default": {
            "ENGINE": "django_tenants.postgresql_backend",
            "NAME": _db_name,
            "USER": config("DB_USER", default="postgres"),
            "PASSWORD": config("DB_PASSWORD", default=""),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
        }
    }

# ── Auth ───────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "core.CustomUser"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

LOGIN_URL = "login"

# ── Axes (proteção contra brute-force no login) ───────────────────────────────
# Ver docs/04_SECURITY.md §33. Axes bloqueia por IP+username após N tentativas
# falhas; usa o cache (Redis em prod, DummyCache em testes) para não exigir
# round-trip no banco a cada request.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "core.auth_backends.RolePermissionBackend",
]

AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # 1 hora
AXES_LOCKOUT_PARAMETERS = [["ip_address", "username"]]
AXES_RESET_ON_SUCCESS = True
AXES_ENABLE_ACCESS = True  # loga tentativas (access attempts) para auditoria
AXES_ACCESS_ATTEMPT_EXPIRY = 60 * 60 * 24  # 24h
AXES_HANDLER = "axes.handlers.database.AxesDatabaseHandler"
# ── i18n ───────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# ── Static / Media ─────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "design_system" / "refs" / "duralux"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Cache (Redis) ──────────────────────────────────────────────────────────────
REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/0")

CACHES = (
    {
        "default": {
            "BACKEND": (
                "django_redis.cache.RedisCache"
                if not (TESTING or TEST_PG)
                else "django.core.cache.backends.dummy.DummyCache"
            ),
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "KEY_PREFIX": "schools",
        }
    }
    if not (TESTING or TEST_PG)
    else {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
)

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# ── Celery ─────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = config("RABBITMQ_URL", default="amqp://guest:guest@localhost:5672//")
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
DEMO_SCHEMA_NAME = config("DEMO_SCHEMA_NAME", default="demo")
DEV_PLATFORM_ADMIN_PASSWORD = config("DEV_PLATFORM_ADMIN_PASSWORD", default="")
DEV_DEMO_ADMIN_PASSWORD = config("DEV_DEMO_ADMIN_PASSWORD", default="")
METRICS_TOKEN = config("METRICS_TOKEN", default="")
READINESS_TOKEN = config("READINESS_TOKEN", default="")

# ── Logging (JSON estruturado) ─────────────────────────────────────────────────
LOG_LEVEL = "CRITICAL" if (TESTING or TEST_PG) else config("LOG_LEVEL", default="INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "filters": {
        "correlation_id": {"()": "core.middleware.CorrelationIdFilter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["correlation_id"],
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

# ── Email ──────────────────────────────────────────────────────────────────────
# Em dev: console.EmailBackend (emails aparecem no terminal).
# Em prod/test_pg: SMTP com credenciais do .env.
if TESTING or TEST_PG:
    EMAIL_BACKEND = "django.core.mail.backends.dummy.DummyBackend"
elif DEBUG:
    EMAIL_BACKEND = config(
        "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
    )
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = config("EMAIL_HOST", default="smtp.example.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@schools.example.com")

# ── Segurança ──────────────────────────────────────────────────────────────────
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True

if DJANGO_ENV == "production":
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
