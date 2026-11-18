import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from celery import current_app
from django.db import transaction

logger = logging.getLogger(__name__)


def group_name(public_id):
    return f"video.{public_id}"


def changed(public_id):
    if current_app.conf.task_always_eager:
        return

    def deliver():
        try:
            async_to_sync(get_channel_layer().group_send)(group_name(public_id), {"type": "video.change"})
        except Exception as error:
            logger.warning("progress_delivery_failed video=%s error_type=%s", public_id, type(error).__name__)

    transaction.on_commit(deliver)
