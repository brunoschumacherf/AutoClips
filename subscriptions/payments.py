from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import AuditLog, Workspace
from notifications.models import Notification
from .models import CreditGrant, PixOrder, Subscription
from .services import period_start, plan_for


def create_order(workspace, offer):
    return PixOrder.objects.create(
        workspace=workspace, offer_name=offer.name, amount=offer.amount,
        plan=offer.plan, credit_minutes=offer.credit_minutes, credit_clips=offer.credit_clips,
    )


def attach_receipt(order, upload):
    stored = None
    try:
        with transaction.atomic():
            order = PixOrder.objects.select_for_update().get(pk=order.pk)
            if order.status != PixOrder.Status.AWAITING:
                raise ValidationError("Este pedido já recebeu um comprovante.")
            order.receipt.save(f"{order.public_id}{Path(upload.name).suffix.lower()}", upload, save=False)
            stored = order.receipt
            order.status = PixOrder.Status.REVIEW
            order.save(update_fields=["receipt", "status", "updated_at"])
    except Exception:
        if stored:
            stored.storage.delete(stored.name)
        raise


@transaction.atomic
def review_order(order, approved, note=""):
    workspace = Workspace.objects.select_for_update().get(pk=order.workspace_id)
    order = PixOrder.objects.select_for_update().get(pk=order.pk)
    if order.status != PixOrder.Status.REVIEW or not order.receipt:
        return False
    now = timezone.now()
    if approved and order.plan_id:
        plan_for(workspace)
        subscription = Subscription.objects.get(workspace=workspace)
        start = now
        if subscription.plan_id == order.plan_id and subscription.paid_until and subscription.paid_until > now:
            start = subscription.paid_until
        subscription.plan_id = order.plan_id
        subscription.paid_until = start + timedelta(days=30)
        subscription.save(update_fields=["plan", "paid_until", "updated_at"])
    elif approved:
        CreditGrant.objects.create(order=order, workspace=workspace, period=period_start(),
                                   seconds=order.credit_minutes * 60, clips=order.credit_clips)
    order.status = PixOrder.Status.APPROVED if approved else PixOrder.Status.REJECTED
    order.reviewed_at = now
    order.review_note = note
    order.save(update_fields=["status", "reviewed_at", "review_note", "updated_at"])
    AuditLog.objects.create(workspace=workspace, action=f"pix.{order.status}", resource_id=order.public_id)
    Notification.objects.create(workspace=workspace, message=f"Pedido Pix: {order.get_status_display().lower()}.")
    return True
