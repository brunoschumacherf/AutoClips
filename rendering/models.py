from django.db import models
from core.models import Record


class RenderJob(Record):
    version = models.OneToOneField("clips.ClipVersion", on_delete=models.CASCADE, related_name="render")
    status = models.CharField(max_length=12, default="pending", db_index=True)
    error = models.CharField(max_length=300, blank=True)
    lease = models.UUIDField(null=True)
    locked_until = models.DateTimeField(null=True)
    attempts = models.PositiveIntegerField(default=0)
