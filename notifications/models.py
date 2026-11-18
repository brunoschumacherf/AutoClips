from django.db import models
from core.models import Record


class Notification(Record):
    workspace = models.ForeignKey("accounts.Workspace", on_delete=models.CASCADE)
    message = models.CharField(max_length=240)
    read_at = models.DateTimeField(null=True)
