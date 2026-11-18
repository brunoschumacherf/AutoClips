import math

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from accounts.models import Workspace
from .models import CreditGrant, Subscription, SubscriptionPlan, UsageRecord


class LimitExceeded(ValueError):
    pass


def plan_for(workspace):
    free, _ = SubscriptionPlan.objects.get_or_create(name="Free", defaults={
        "is_default": True, "monthly_seconds": 3600, "monthly_clips": 30, "storage_bytes": 2 * 1024**3, "max_height": 720,
    })
    subscription, _ = Subscription.objects.select_related("plan").get_or_create(workspace=workspace, defaults={"plan": free})
    if subscription.paid_until and subscription.paid_until <= timezone.now():
        return free
    return subscription.plan


def period_start():
    return timezone.localdate().replace(day=1)


def credits_for(workspace, period):
    totals = CreditGrant.objects.filter(workspace=workspace, period=period).aggregate(seconds=Sum("seconds"), clips=Sum("clips"))
    return totals["seconds"] or 0, totals["clips"] or 0


@transaction.atomic
def reserve(video, *, duration=0, clips=0, size=0):
    workspace = Workspace.objects.select_for_update().get(pk=video.workspace_id)
    plan = plan_for(workspace)
    previous, _ = UsageRecord.objects.get_or_create(video=video, defaults={"workspace": workspace, "period": period_start()})
    monthly = UsageRecord.objects.filter(workspace=workspace, period=previous.period).exclude(pk=previous.pk)
    totals = monthly.aggregate(seconds=Sum("seconds"), clips=Sum("clips"))
    occupied = UsageRecord.objects.filter(workspace=workspace).exclude(pk=previous.pk).aggregate(total=Sum("bytes"))["total"] or 0
    previous.seconds = max(previous.seconds, math.ceil(duration))
    previous.clips = max(previous.clips, clips)
    previous.bytes = max(previous.bytes, size)
    extra_seconds, extra_clips = credits_for(workspace, previous.period)
    if (totals["seconds"] or 0) + previous.seconds > plan.monthly_seconds + extra_seconds:
        raise LimitExceeded("Limite mensal de processamento atingido.")
    if (totals["clips"] or 0) + previous.clips > plan.monthly_clips + extra_clips:
        raise LimitExceeded("Saldo de cortes insuficiente. Consulte sua franquia ou adicione créditos.")
    if occupied + previous.bytes > plan.storage_bytes:
        raise LimitExceeded("Limite de armazenamento atingido.")
    previous.save()


@transaction.atomic
def adjust_storage(video, delta):
    workspace = Workspace.objects.select_for_update().get(pk=video.workspace_id)
    plan = plan_for(workspace)
    records = UsageRecord.objects.filter(workspace=workspace)
    current = records.filter(video=video).first()
    if not current:
        return
    used = records.aggregate(total=Sum("bytes"))["total"] or 0
    if delta > 0 and used + delta > plan.storage_bytes:
        raise LimitExceeded("Limite de armazenamento atingido.")
    current.bytes = max(0, current.bytes + delta)
    current.save(update_fields=["bytes", "updated_at"])
