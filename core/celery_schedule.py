"""Agenda central dos processadores recuperáveis por tenant."""

from celery.schedules import crontab

BEAT_SCHEDULE = {
    "recover-durable-communications": {
        "task": "notifications.recover_communications",
        "schedule": 60.0,
    },
    "dispatch-daily-collection-reminders": {
        "task": "financeiro.dispatch_collection_reminders",
        "schedule": crontab(hour=8, minute=0),
    },
}
