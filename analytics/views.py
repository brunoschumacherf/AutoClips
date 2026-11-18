from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import render

from accounts.services import visible_workspaces
from publishing.models import Publication
from videos.models import Video


@login_required
def overview(request):
    workspaces = visible_workspaces(request.user)
    videos = Video.objects.filter(workspace__in=workspaces)
    days = videos.filter(status=Video.State.DONE).annotate(day=TruncDate("created_at")).values("day").annotate(
        total=Count("id"), seconds=Sum("duration"),
    ).order_by("-day")[:30]
    return render(request, "analytics.html", {
        "days": [{"day": item["day"], "total": item["total"], "minutes": round(item["seconds"] / 60, 1)} for item in days],
        "failed": videos.filter(status=Video.State.FAILED).count(),
        "published": Publication.objects.filter(account__workspace__in=workspaces, status="processed").count(),
    })
