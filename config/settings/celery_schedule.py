"""Celery Beat schedule for Twinscopes background jobs."""

from celery.schedules import crontab


CELERY_BEAT_SCHEDULE = {
    "enterprise-platform-health-hourly": {
        "task": "apps.monitoring.tasks.check_platform_health",
        "schedule": crontab(minute=5),
        "options": {"expires": 60 * 45},
    },
    "enterprise-ai-usage-daily": {
        "task": "apps.ai_core.tasks.aggregate_ai_usage",
        "schedule": crontab(hour=1, minute=30),
        "options": {"expires": 60 * 60 * 4},
    },
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
    "organization-intelligence-due-sync": {
        "task": "apps.domain_intelligence.tasks.queue_due_organization_intelligence",
        "schedule": crontab(hour="*/6", minute=20),
        "options": {"expires": 60 * 60 * 5},
    },
    "organization-intelligence-readiness-nightly": {
        "task": "apps.domain_intelligence.tasks.refresh_all_intelligence_readiness",
        "schedule": crontab(hour=1, minute=50),
        "options": {"expires": 60 * 60 * 4},
    },
}
