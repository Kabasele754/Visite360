from datetime import datetime, timedelta

from celery import shared_task
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.ai_core.models import AIRun, AIUsageDaily


@shared_task
def aggregate_ai_usage(date_iso: str | None = None):
    target_date = datetime.fromisoformat(date_iso).date() if date_iso else timezone.localdate() - timedelta(days=1)
    rows = AIRun.objects.filter(created_at__date=target_date, organization__isnull=False).values(
        "organization_id", "provider", "model_name"
    ).annotate(
        requests=Count("id"),
        failures=Count("id", filter=Q(status=AIRun.Status.FAILED)),
        prompt_tokens=Sum("prompt_tokens"),
        completion_tokens=Sum("completion_tokens"),
        cost_usd=Sum("cost_usd"),
    )
    count = 0
    for row in rows:
        AIUsageDaily.objects.update_or_create(
            organization_id=row["organization_id"],
            date=target_date,
            provider=row["provider"],
            model_name=row["model_name"],
            defaults={
                "requests": row["requests"] or 0,
                "failures": row["failures"] or 0,
                "prompt_tokens": row["prompt_tokens"] or 0,
                "completion_tokens": row["completion_tokens"] or 0,
                "cost_usd": row["cost_usd"] or 0,
            },
        )
        count += 1
    return {"date": str(target_date), "rows": count}
