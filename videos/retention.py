from django.db import transaction

from clips.models import ClipVersion
from publishing.models import Publication
from rendering.models import RenderJob
from subscriptions.models import UsageRecord
from subscriptions.services import adjust_storage
from .models import Video


@transaction.atomic
def expire_media(video_id):
    video = Video.objects.select_for_update().get(pk=video_id)
    versions = ClipVersion.objects.filter(clip__video=video).select_for_update()
    if RenderJob.objects.filter(version__in=versions, status__in=["pending", "running"]).exists():
        return
    if Publication.objects.filter(version__in=versions, status__in=["scheduled", "uploading", "uncertain"]).exists():
        return
    for obj, keys in [(video, ("source", "audio")), *((version, ("output", "thumbnail", "srt", "vtt")) for version in versions)]:
        for key in keys:
            field = getattr(obj, key)
            if field:
                field.delete(save=False)
        obj.save(update_fields=keys)
    record = UsageRecord.objects.filter(video=video).first()
    if record:
        adjust_storage(video, -record.bytes)
