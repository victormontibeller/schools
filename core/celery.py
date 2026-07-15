"""Configuração do Celery."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
app = Celery("schools")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Import explícito registra os signals tanto no worker quanto no publisher.
from core import celery_signals as _celery_signals  # noqa: E402,F401
