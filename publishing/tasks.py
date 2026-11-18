import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import Publication
from .services import access_token
from .youtube import enabled, remote_status, upload

logger = logging.getLogger(__name__)


@shared_task
def dispatch_due():
    if not enabled():
        return
    now = timezone.now()
    Publication.objects.filter(status="uploading", updated_at__lt=now - timedelta(hours=2)).update(
        status="uncertain", error="Envio interrompido. Verifique o YouTube Studio antes de reenviar."
    )
    jobs = Publication.objects.filter(status="scheduled", schedule__run_at__lte=now, account__provider="youtube")[:20]
    for job in jobs.select_related("account", "version"):
        if not Publication.objects.filter(pk=job.pk, status="scheduled").update(status="uploading", updated_at=now):
            continue
        try:
            remote_id = upload(job, access_token(job.account))
            Publication.objects.filter(pk=job.pk).update(status="uploaded", remote_id=remote_id, updated_at=timezone.now())
        except Exception as error:
            logger.warning("publication_upload_error publication=%s error_type=%s", job.public_id, type(error).__name__)
            Publication.objects.filter(pk=job.pk).update(
                status="uncertain", error="O envio não pôde ser confirmado. Verifique o YouTube Studio."
            )
    for job in Publication.objects.filter(status="uploaded", account__provider="youtube").select_related("account")[:20]:
        try:
            status = remote_status(job.remote_id, access_token(job.account))
        except Exception as error:
            logger.warning("publication_status_error publication=%s error_type=%s", job.public_id, type(error).__name__)
            continue
        if status in {"processed", "failed", "rejected", "deleted"}:
            Publication.objects.filter(pk=job.pk).update(status=status)
