from django.db import models
from core.models import Record


class Video(Record):
    class State(models.TextChoices):
        PENDING = "pending", "Pendente"
        IMPORTING = "importing", "Importando"
        TRANSCRIBING = "transcribing", "Transcrevendo"
        ANALYZING = "analyzing", "Analisando"
        GENERATING = "generating", "Gerando cortes"
        RENDERING = "rendering", "Renderizando"
        DONE = "done", "Concluído"
        FAILED = "failed", "Falhou"
        CANCELED = "canceled", "Cancelado"

    workspace = models.ForeignKey("accounts.Workspace", on_delete=models.CASCADE, related_name="videos")
    title = models.CharField(max_length=180)
    source = models.FileField(upload_to="sources/", blank=True)
    audio = models.FileField(upload_to="audio/", blank=True)
    duration = models.FloatField(default=0)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=State.choices, default=State.PENDING)
    error = models.CharField(max_length=300, blank=True)
    options = models.JSONField(default=dict)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["workspace", "status"])]


class VideoSource(Record):
    video = models.OneToOneField(Video, on_delete=models.CASCADE, related_name="origin")
    url = models.URLField(max_length=500, blank=True)
    kind = models.CharField(max_length=15, default="upload")


class ProcessingJob(Record):
    video = models.OneToOneField(Video, on_delete=models.CASCADE, related_name="job")
    lease = models.UUIDField(null=True)
    locked_until = models.DateTimeField(null=True)
    attempts = models.PositiveIntegerField(default=0)
