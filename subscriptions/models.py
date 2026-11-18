from django.db import models
from core.models import Record


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=30, unique=True)
    monthly_seconds = models.PositiveIntegerField()
    monthly_clips = models.PositiveIntegerField()
    storage_bytes = models.PositiveBigIntegerField()
    max_height = models.PositiveIntegerField(default=1080)
    social_accounts = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name


class Subscription(Record):
    workspace = models.OneToOneField("accounts.Workspace", on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)


class UsageRecord(Record):
    workspace = models.ForeignKey("accounts.Workspace", on_delete=models.CASCADE)
    video = models.OneToOneField("videos.Video", on_delete=models.CASCADE)
    period = models.DateField(db_index=True)
    seconds = models.PositiveIntegerField(default=0)
    clips = models.PositiveIntegerField(default=0)
    bytes = models.PositiveBigIntegerField(default=0)
