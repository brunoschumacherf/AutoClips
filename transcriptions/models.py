from django.db import models
from core.models import Record


class Transcription(Record):
    video = models.OneToOneField("videos.Video", on_delete=models.CASCADE)
    language = models.CharField(max_length=12)
    confidence = models.FloatField(null=True)


class Speaker(Record):
    transcription = models.ForeignKey(Transcription, on_delete=models.CASCADE)
    label = models.CharField(max_length=40)


class TranscriptionSegment(Record):
    transcription = models.ForeignKey(Transcription, on_delete=models.CASCADE, related_name="segments")
    speaker = models.ForeignKey(Speaker, on_delete=models.SET_NULL, null=True)
    start = models.FloatField()
    end = models.FloatField()
    text = models.TextField()
    words = models.JSONField(default=list)
    confidence = models.FloatField(null=True)

    class Meta:
        ordering = ["start", "pk"]
        constraints = [models.CheckConstraint(condition=models.Q(end__gt=models.F("start")), name="transcript_end_after_start")]
