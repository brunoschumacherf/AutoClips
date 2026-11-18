import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from . import instagram, tiktok
from .models import Publication
from .services import access_token, stored_grant, tiktok_access
from .youtube import enabled, remote_status, upload

logger = logging.getLogger(__name__)


@shared_task
def dispatch_due():
    if tiktok.enabled():
        dispatch_tiktok()
    if instagram.enabled():
        dispatch_instagram()
    if not enabled():
        return
    now = timezone.now()
    Publication.objects.filter(account__provider="youtube", status="uploading", updated_at__lt=now - timedelta(hours=2)).update(
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


def dispatch_instagram():
    now = timezone.now()
    jobs = Publication.objects.filter(account__provider="instagram")
    jobs.filter(status__in=["uploading", "publishing"], updated_at__lt=now - timedelta(hours=2)).update(
        status="uncertain", error="Verifique o Instagram antes de repetir a publicação."
    )
    jobs.filter(status="processing", updated_at__lt=now - timedelta(hours=2)).update(
        status="failed", error="O Instagram não concluiu a preparação do vídeo no prazo."
    )
    for job in jobs.filter(status="scheduled", schedule__run_at__lte=now).select_related("account", "version")[:20]:
        record = jobs.filter(pk=job.pk)
        if not record.filter(status="scheduled").update(status="uploading", updated_at=now):
            continue
        try:
            container = instagram.create_container(job, stored_grant(job.account))
        except Exception as error:
            logger.warning("instagram_container_failed publication=%s error_type=%s", job.public_id, type(error).__name__)
            record.update(status="failed", error="O Instagram recusou a preparação do vídeo.")
            continue
        record.update(status="processing", remote_id=container, updated_at=timezone.now())

    for job in jobs.filter(status="processing").select_related("account")[:20]:
        record = jobs.filter(pk=job.pk)
        try:
            token = stored_grant(job.account)
            state = instagram.container_status(job.remote_id, token)
        except Exception as error:
            logger.warning("instagram_status_failed publication=%s error_type=%s", job.public_id, type(error).__name__)
            continue
        if state in {"ERROR", "EXPIRED"}:
            record.filter(status="processing").update(status="failed", error="O Instagram não processou o vídeo.")
        if state != "FINISHED" or not record.filter(status="processing").update(status="publishing", updated_at=timezone.now()):
            continue
        try:
            media_id = instagram.publish(job, token)
        except Exception as error:
            logger.warning("instagram_publish_uncertain publication=%s error_type=%s", job.public_id, type(error).__name__)
            record.update(status="uncertain", error="Verifique o Instagram antes de repetir a publicação.")
            continue
        record.update(status="processed", remote_id=media_id, updated_at=timezone.now())


def dispatch_tiktok():
    now = timezone.now()
    jobs = Publication.objects.filter(account__provider="tiktok")
    jobs.filter(status="uploading", updated_at__lt=now - timedelta(hours=2)).update(
        status="uncertain", error="Verifique a caixa de entrada do TikTok antes de reenviar."
    )
    jobs.filter(status="processing", updated_at__lt=now - timedelta(hours=24)).update(
        status="uncertain", error="O TikTok ainda não confirmou a entrega."
    )
    for job in jobs.filter(status="scheduled", schedule__run_at__lte=now).select_related("account", "version")[:20]:
        record = jobs.filter(pk=job.pk)
        if not record.filter(status="scheduled").update(status="uploading", updated_at=now):
            continue
        try:
            remote_id = tiktok.upload(job, tiktok_access(job.account))
        except Exception as error:
            logger.warning("tiktok_upload_uncertain publication=%s error_type=%s", job.public_id, type(error).__name__)
            record.update(status="uncertain", error="Verifique a caixa de entrada do TikTok antes de reenviar.")
            continue
        record.update(status="processing", remote_id=remote_id, updated_at=timezone.now())

    final_states = {"SEND_TO_USER_INBOX": "inbox", "PUBLISH_COMPLETE": "processed", "FAILED": "failed"}
    for job in jobs.filter(status="processing").select_related("account")[:20]:
        try:
            state = tiktok.upload_status(job.remote_id, tiktok_access(job.account))
        except Exception as error:
            logger.warning("tiktok_status_failed publication=%s error_type=%s", job.public_id, type(error).__name__)
            continue
        if state in final_states:
            jobs.filter(pk=job.pk, status="processing").update(status=final_states[state], updated_at=timezone.now())
