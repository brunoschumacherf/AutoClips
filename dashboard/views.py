from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from accounts.services import personal_workspace, visible_workspaces
from clips.models import Clip
from notifications.models import Notification
from publishing.models import Publication, SocialAccount
from publishing import instagram, tiktok, youtube
from subscriptions import pix
from subscriptions.models import PixOffer, PixOrder, Subscription, UsageRecord
from subscriptions.services import credits_for, period_start, plan_for
from videos.models import Video


@login_required
def home(request):
    workspace = personal_workspace(request.user)
    workspaces = visible_workspaces(request.user)
    videos = Video.objects.filter(workspace__in=workspaces)
    completed = videos.filter(status=Video.State.DONE)
    return render(request, "dashboard.html", {
        "videos": videos[:8],
        "metrics": [
            ("Vídeos processados", completed.count()),
            ("Cortes gerados", Clip.objects.filter(video__in=videos, deleted_at__isnull=True, current_version__render__status="done").count()),
            ("Minutos analisados", round((completed.aggregate(total=Sum("duration"))["total"] or 0) / 60, 1)),
            ("Em processamento", videos.exclude(status__in=[Video.State.DONE, Video.State.FAILED, Video.State.CANCELED]).count()),
        ],
        "notifications": Notification.objects.filter(workspace__in=workspaces).order_by("-created_at")[:5],
        "published": Publication.objects.filter(account__workspace__in=workspaces, status="processed").count(),
        "plan": plan_for(workspace),
    })


@login_required
def library(request):
    from django.core.paginator import Paginator

    videos = Video.objects.filter(workspace__in=visible_workspaces(request.user))
    return render(request, "library.html", {"page": Paginator(videos, 20).get_page(request.GET.get("page"))})


@login_required
def usage(request):
    workspace = personal_workspace(request.user)
    totals = UsageRecord.objects.filter(workspace=workspace, period=period_start()).aggregate(
        seconds=Sum("seconds"), clips=Sum("clips"),
    )
    size = UsageRecord.objects.filter(workspace=workspace).aggregate(total=Sum("bytes"))["total"] or 0
    extra_seconds, extra_clips = credits_for(workspace, period_start())
    plan = plan_for(workspace)
    used_clips = totals["clips"] or 0
    return render(request, "usage.html", {
        "offers": PixOffer.objects.filter(active=True).order_by("amount") if pix.enabled() else (),
        "orders": PixOrder.objects.filter(workspace=workspace).order_by("-created_at")[:25],
        "extra_minutes": extra_seconds // 60, "extra_clips": extra_clips,
        "paid_until": Subscription.objects.filter(workspace=workspace, paid_until__gt=timezone.now())
        .values_list("paid_until", flat=True).first(),
        "plan": plan, "minutes": round((totals["seconds"] or 0) / 60, 1),
        "clips": used_clips, "clip_balance": max(0, plan.monthly_clips + extra_clips - used_clips),
        "extra_clip_balance": max(0, extra_clips - max(0, used_clips - plan.monthly_clips)), "storage": round(size / 1024**2, 1),
    })


@login_required
def publications(request):
    workspaces = visible_workspaces(request.user)
    return render(request, "publications.html", {
        "youtube_enabled": youtube.enabled(),
        "instagram_enabled": instagram.enabled(),
        "tiktok_enabled": tiktok.enabled(),
        "publications": Publication.objects.filter(account__workspace__in=workspaces).select_related("account").order_by("-created_at")[:50],
        "accounts": SocialAccount.objects.filter(workspace__in=workspaces),
    })
