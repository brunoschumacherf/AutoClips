from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from accounts.services import personal_workspace, visible_workspaces
from clips.models import Clip
from notifications.models import Notification
from publishing.models import Publication, SocialAccount
from publishing import instagram, tiktok, youtube
from subscriptions.models import UsageRecord
from subscriptions.services import period_start, plan_for
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
    return render(request, "usage.html", {
        "plan": plan_for(workspace), "minutes": round((totals["seconds"] or 0) / 60, 1),
        "clips": totals["clips"] or 0, "storage": round(size / 1024**2, 1),
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
