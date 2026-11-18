import copy
import mimetypes
from pathlib import Path

from asgiref.sync import sync_to_async
from django import forms
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.handlers.asgi import ASGIRequest
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_safe

from accounts.services import visible_workspaces
from rendering.models import RenderJob
from rendering.tasks import settle_video
from videos.events import changed
from publishing.youtube import enabled
from .models import Clip
from .services import captions_for, remove, version_for


def lookup(user, public_id):
    return get_object_or_404(Clip.objects.select_related("video", "highlight", "current_version").filter(
        video__workspace__in=visible_workspaces(user), deleted_at__isnull=True,
    ), public_id=public_id)


class Editor(forms.Form):
    title = forms.CharField(label="Título", max_length=180)
    start = forms.DecimalField(label="Início (s)", min_value=0, decimal_places=2, max_digits=7)
    end = forms.DecimalField(label="Fim (s)", min_value=0, decimal_places=2, max_digits=7)
    aspect = forms.ChoiceField(label="Formato", choices=[(value, value) for value in ("9:16", "16:9", "1:1")])
    position = forms.IntegerField(label="Altura das legendas (%)", min_value=15, max_value=90)
    color = forms.RegexField(label="Cor da legenda", regex=r"^#[0-9A-Fa-f]{6}$", widget=forms.TextInput(attrs={"type": "color"}))
    center = forms.IntegerField(label="Centro horizontal manual (%)", min_value=0, max_value=100, required=False)
    captions = forms.CharField(label="Legendas (uma linha por trecho)", max_length=20000, required=False, widget=forms.Textarea(attrs={"rows": 6}))

    def __init__(self, clip, *args, **kwargs):
        self.clip = clip
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        start, end = float(data["start"]), float(data["end"])
        if not start < end <= self.clip.video.duration + 0.011 or end - start > 180:
            raise forms.ValidationError("Escolha um intervalo válido de até 180 segundos.")
        end = min(end, self.clip.video.duration)
        version = self.clip.current_version
        edited = data["captions"].splitlines()
        previous = [caption["text"] for caption in version.captions]
        captions = captions_for(self.clip.video, start, end)
        if edited != previous:
            if len(edited) != len(captions):
                raise forms.ValidationError(f"Este intervalo tem {len(captions)} trechos. Informe uma linha por trecho ou salve o intervalo primeiro.")
            for caption, text in zip(captions, edited):
                if caption["text"] != text:
                    caption.update(text=text, words=[])
        elif round(version.start, 2) == round(start, 2) and round(version.end, 2) == round(end, 2):
            captions = copy.deepcopy(version.captions)
            start, end = version.start, version.end
        data.update(start=start, end=end, cues=captions)
        return data


@login_required
def edit(request, public_id):
    clip = lookup(request.user, public_id)
    version = clip.current_version
    if version is None:
        raise Http404
    center = version.style.get("center")
    form = Editor(clip, request.POST or None, initial={
        "title": clip.title, "start": round(version.start, 2), "end": round(version.end, 2),
        "aspect": version.aspect, "color": version.style.get("color", "#FFFFFF"),
        "position": version.style.get("position", 74), "center": None if center is None else round(center * 100),
        "captions": "\n".join(caption["text"] for caption in version.captions),
    })
    if request.method == "POST" and not clip.video.source:
        form.add_error(None, "O vídeo original expirou.")
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        style = {"color": data["color"], "position": data["position"]}
        if data["center"] is not None:
            style["center"] = data["center"] / 100
        with transaction.atomic():
            Clip.objects.filter(pk=clip.pk).update(title=data["title"])
            version_for(clip, data["start"], data["end"], data["aspect"], style, data["cues"])
        return redirect("clip", public_id=public_id)
    return render(request, "editor.html", {"clip": clip, "form": form, "version": version, "can_publish": enabled() and clip.video.workspace.owner_id == request.user.pk})


@login_required
@require_POST
def delete(request, public_id):
    clip = lookup(request.user, public_id)
    with transaction.atomic():
        remove(clip)
        RenderJob.objects.filter(version__clip=clip, status__in=["pending", "running"]).update(status="canceled")
    settle_video(clip.video_id)
    changed(clip.video.public_id)
    return redirect("video", public_id=clip.video.public_id)


@login_required
@require_POST
def cancel_render(request, public_id):
    clip = lookup(request.user, public_id)
    RenderJob.objects.filter(version=clip.current_version, status__in=["pending", "running"]).update(status="canceled")
    settle_video(clip.video_id)
    changed(clip.video.public_id)
    return redirect("clip", public_id=public_id)


def stream_range(file, remaining):
    try:
        while remaining:
            chunk = file.read(min(remaining, 65536))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
    finally:
        file.close()


async def async_range(file, remaining):
    iterator = stream_range(file, remaining)
    try:
        while chunk := await sync_to_async(next)(iterator, None):
            yield chunk
    finally:
        await sync_to_async(iterator.close)()
        await sync_to_async(file.close)()


def stream_for(request, file, size):
    return async_range(file, size) if isinstance(request, ASGIRequest) else stream_range(file, size)


def serve(field, request, download=False):
    if not field:
        raise Http404
    content_type = mimetypes.guess_type(field.name)[0] or "application/octet-stream"
    requested = request.headers.get("Range", "")
    if not download and requested.startswith("bytes="):
        size = field.size
        try:
            lower, upper = requested[6:].split("-", 1)
            start = int(lower) if lower else max(0, size - int(upper))
            end = min(int(upper), size - 1) if lower and upper else size - 1
            if not 0 <= start <= end:
                raise ValueError
        except ValueError:
            return HttpResponse(status=416, headers={"Content-Range": f"bytes */{size}"})
        source = field.open("rb")
        source.seek(start)
        length = end - start + 1
        return StreamingHttpResponse(stream_for(request, source, length), status=206, content_type=content_type, headers={
            "Accept-Ranges": "bytes", "Content-Length": str(length), "Content-Range": f"bytes {start}-{end}/{size}",
            "Cache-Control": "private, no-store",
        })
    if isinstance(request, ASGIRequest):
        from django.utils.http import content_disposition_header

        size = field.size
        response = StreamingHttpResponse(stream_for(request, field.open("rb"), size), content_type=content_type)
        response["Content-Length"] = size
        disposition = content_disposition_header(download, Path(field.name).name)
        if disposition:
            response["Content-Disposition"] = disposition
    else:
        response = FileResponse(field.open("rb"), content_type=content_type, as_attachment=download, filename=Path(field.name).name)
    response["Accept-Ranges"] = "bytes"
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_safe
def asset(request, public_id, kind):
    clip = lookup(request.user, public_id)
    version = clip.current_version
    fields = {"preview": "output", "download": "output", "thumbnail": "thumbnail", "srt": "srt", "vtt": "vtt"}
    if not version or kind not in fields:
        raise Http404
    return serve(getattr(version, fields[kind]), request, download=kind in {"download", "srt", "vtt"})


@login_required
@require_safe
def source(request, public_id):
    from videos.views import lookup as lookup_video

    video = lookup_video(request.user, public_id)
    return serve(video.source, request)
