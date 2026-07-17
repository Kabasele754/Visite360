"""Celery Beat schedule for Twinscopes background jobs."""

from celery.schedules import crontab


CELERY_BEAT_SCHEDULE = {
    "growth-ai-sync-all-sources-nightly": {
        "task": "apps.growth_ai.tasks.sync_all_growth_sources",
        "schedule": crontab(hour=2, minute=15),
        "options": {"expires": 60 * 60 * 4},
    },
    "growth-ai-aggregate-yesterday": {
        "task": "apps.growth_ai.tasks.aggregate_internal_daily_snapshots",
        "schedule": crontab(hour=3, minute=0),
        "options": {"expires": 60 * 60 * 4},
    },
    "growth-ai-clean-old-runs-weekly": {
        "task": "apps.growth_ai.tasks.cleanup_old_growth_data",
        "schedule": crontab(day_of_week="sunday", hour=4, minute=0),
        "options": {"expires": 60 * 60 * 6},
    },
}
