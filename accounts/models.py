from django.conf import settings
from django.db import models
from core.models import Record


class UserProfile(Record):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=100, blank=True)


class Workspace(Record):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, default="Meu espaço")
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="shared_workspaces", blank=True)


class AuditLog(Record):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    action = models.CharField(max_length=60)
    resource_id = models.UUIDField()


class TrackedSession(Record):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40, unique=True, editable=False)
    user_agent = models.CharField(max_length=200, blank=True)
