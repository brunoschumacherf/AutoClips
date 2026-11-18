from django.db import models
from core.models import Record


class AIAnalysis(Record):
    video = models.OneToOneField("videos.Video", on_delete=models.CASCADE)
    signals = models.JSONField(default=dict)


class Highlight(Record):
    analysis = models.ForeignKey(AIAnalysis, on_delete=models.CASCADE, related_name="highlights")
    rank = models.PositiveIntegerField()
    start = models.FloatField()
    end = models.FloatField()
    score = models.PositiveSmallIntegerField()
    components = models.JSONField(default=dict)

    class Meta:
        ordering = ["rank"]
        constraints = [
            models.UniqueConstraint(fields=["analysis", "rank"], name="unique_highlight_rank"),
            models.CheckConstraint(condition=models.Q(score__lte=100) & models.Q(end__gt=models.F("start")), name="valid_highlight"),
        ]
