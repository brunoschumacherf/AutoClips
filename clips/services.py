from django.db import transaction
from django.utils import timezone

from rendering.models import RenderJob
from videos.services import enqueue
from .models import Clip, ClipVersion


def captions_for(video, start, end):
    captions = []
    for segment in video.transcription.segments.filter(start__lt=end, end__gt=start):
        words = [
            {"start": max(start, word["start"]), "end": min(end, word["end"]), "text": word["text"]}
            for word in segment.words if word["start"] < end and word["end"] > start and word["text"]
        ]
        captions.append({"start": max(start, segment.start), "end": min(end, segment.end),
                         "text": segment.text, "words": words})
    return captions


@transaction.atomic
def version_for(clip, start, end, aspect, style, captions=None):
    from rendering.tasks import render_clip

    clip = Clip.objects.select_for_update().get(pk=clip.pk, deleted_at__isnull=True)
    version = ClipVersion.objects.create(
        clip=clip, start=start, end=end, aspect=aspect, style=style,
        captions=captions_for(clip.video, start, end) if captions is None else captions,
    )
    RenderJob.objects.create(version=version)
    clip.current_version = version
    clip.save(update_fields=["current_version", "updated_at"])
    enqueue(render_clip, version.pk)
    return version


def remove(clip):
    Clip.objects.filter(pk=clip.pk).update(deleted_at=timezone.now())
