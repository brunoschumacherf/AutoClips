from django.db import models
from core.models import Record


class SocialAccount(Record):
    workspace = models.ForeignKey("accounts.Workspace", on_delete=models.CASCADE)
    provider = models.CharField(max_length=15)
    external_id = models.CharField(max_length=150)
    label = models.CharField(max_length=150)
    grant = models.BinaryField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace", "provider", "external_id"], name="unique_social_identity")]


class Publication(Record):
    account = models.ForeignKey(SocialAccount, on_delete=models.CASCADE)
    version = models.ForeignKey("clips.ClipVersion", on_delete=models.PROTECT)
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="scheduled", db_index=True)
    remote_id = models.CharField(max_length=150, blank=True)
    error = models.CharField(max_length=300, blank=True)


class PublicationSchedule(Record):
    publication = models.OneToOneField(Publication, on_delete=models.CASCADE, related_name="schedule")
    run_at = models.DateTimeField(db_index=True)
