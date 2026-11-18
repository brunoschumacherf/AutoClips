from django.db import models
from core.models import Record


class Clip(Record):
    video = models.ForeignKey("videos.Video", on_delete=models.CASCADE, related_name="clips")
    highlight = models.OneToOneField("ai_engine.Highlight", on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=180)
    deleted_at = models.DateTimeField(null=True)
    current_version = models.ForeignKey("ClipVersion", on_delete=models.SET_NULL, null=True, related_name="+")


class ClipVersion(Record):
    clip = models.ForeignKey(Clip, on_delete=models.CASCADE, related_name="versions")
    start = models.FloatField()
    end = models.FloatField()
    aspect = models.CharField(max_length=5, default="9:16")
    style = models.JSONField(default=dict)
    captions = models.JSONField(default=list)
    output = models.FileField(upload_to="clips/", blank=True)
    thumbnail = models.FileField(upload_to="thumbnails/", blank=True)
    srt = models.FileField(upload_to="captions/", blank=True)
    vtt = models.FileField(upload_to="captions/", blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(start__gte=0) & models.Q(end__gt=models.F("start")), name="valid_clip_range")]
