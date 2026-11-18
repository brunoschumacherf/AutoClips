from django.db import models
from core.models import Record


class Stream(Record):
    workspace = models.ForeignKey("accounts.Workspace", on_delete=models.CASCADE)
    platform = models.CharField(max_length=20)
    url = models.URLField()
    video = models.ForeignKey("videos.Video", on_delete=models.SET_NULL, null=True)
