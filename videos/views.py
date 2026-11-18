from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.services import personal_workspace, visible_workspaces
from rendering.models import RenderJob
from subscriptions.services import LimitExceeded
from .events import changed
from .forms import IntakeForm
from .models import Video
from .services import submit


def lookup(user, public_id):
    return get_object_or_404(Video.objects.filter(workspace__in=visible_workspaces(user)), public_id=public_id)


@login_required
def create(request):
    form = IntakeForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            video = submit(personal_workspace(request.user), form.cleaned_data)
        except LimitExceeded as error:
            form.add_error(None, str(error))
        else:
            return redirect("video", public_id=video.public_id)
    return render(request, "form.html", {"form": form, "title": "Novo processamento", "button": "Processar vídeo", "upload": True})


def video_context(video):
    clips = video.clips.filter(deleted_at__isnull=True).select_related("highlight", "current_version__render")
    return {"video": video, "clips": clips, "active": video.status not in [Video.State.DONE, Video.State.FAILED, Video.State.CANCELED] or
            any(clip.current_version and clip.current_version.render.status in {"pending", "running"} for clip in clips)}


@login_required
def detail(request, public_id):
    return render(request, "video.html", video_context(lookup(request.user, public_id)))


@login_required
def progress(request, public_id):
    return render(request, "progress.html", video_context(lookup(request.user, public_id)))


@login_required
@require_POST
def cancel(request, public_id):
    video = lookup(request.user, public_id)
    with transaction.atomic():
        video = Video.objects.select_for_update().get(pk=video.pk)
        if video.status not in [Video.State.DONE, Video.State.FAILED, Video.State.CANCELED]:
            video.status = Video.State.CANCELED
            video.save(update_fields=["status", "updated_at"])
            changed(video.public_id)
            RenderJob.objects.filter(version__clip__video=video, status__in=["pending", "running"]).update(status="canceled")
    return redirect("video", public_id=public_id)
