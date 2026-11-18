import logging
import tempfile
from pathlib import Path

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from core.jobs import claim, release
from core.media import save_artifact
from notifications.models import Notification
from subscriptions.services import LimitExceeded, adjust_storage, plan_for
from videos.events import changed
from videos.models import Video
from .models import RenderJob
from .services import render

logger = logging.getLogger(__name__)


@transaction.atomic
def settle_video(video_id):
    video = Video.objects.select_for_update().filter(pk=video_id, status=Video.State.RENDERING).first()
    if not video:
        return
    statuses = list(RenderJob.objects.filter(version__clip__video=video, version__clip__highlight__isnull=False)
                    .values_list("status", flat=True))
    if not statuses or any(status in {"pending", "running"} for status in statuses):
        return
    video.status = Video.State.DONE if "done" in statuses else Video.State.FAILED
    video.error = "" if video.status == Video.State.DONE else "Nenhum corte pôde ser renderizado."
    video.save(update_fields=["status", "error", "updated_at"])
    changed(video.public_id)
    Notification.objects.create(workspace=video.workspace, message=f"{video.title}: {video.get_status_display()}.")


@shared_task(bind=True, max_retries=3)
def render_clip(self, version_id):
    query = RenderJob.objects.filter(version_id=version_id)
    job = claim(query, None, ["pending", "running"], "running")
    if not job:
        return
    version = job.version
    video = version.clip.video
    stored = []
    try:
        if video.status == Video.State.CANCELED or version.clip.deleted_at:
            query.filter(lease=job.lease).update(status="canceled")
            return
        with tempfile.TemporaryDirectory() as directory:
            files = render(version, Path(directory), plan_for(video.workspace))
            with transaction.atomic():
                video.refresh_from_db(fields=["status"])
                if video.status == Video.State.CANCELED or not query.filter(status="running", lease=job.lease).exists():
                    return
                adjust_storage(video, sum(path.stat().st_size for path in files.values()))
                for key, path in files.items():
                    field = getattr(version, key)
                    save_artifact(field, path, version.public_id)
                    stored.append(field)
                version.save(update_fields=[*files, "updated_at"])
                query.filter(lease=job.lease).update(status="done", error="")
    except Exception as error:
        for field in stored:
            field.storage.delete(field.name)
        logger.warning("render_failed clip=%s error_type=%s", version.public_id, type(error).__name__)
        if job.attempts < 3 and not isinstance(error, ValueError):
            release(job)
            raise self.retry(countdown=15 * 2 ** (job.attempts - 1))
        query.filter(status="running", lease=job.lease).update(status="failed", error=str(error) if isinstance(error, LimitExceeded) else "Falha na renderização.")
    finally:
        release(job)
        changed(video.public_id)
        settle_video(video.pk)
