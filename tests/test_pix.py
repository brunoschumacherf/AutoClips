from binascii import crc_hqx
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.services import personal_workspace
from subscriptions.models import CreditGrant, PixOffer, PixOrder, Subscription, SubscriptionPlan
from subscriptions.payments import create_order, review_order
from subscriptions.pix import payload
from subscriptions.services import credits_for, period_start, plan_for, reserve
from videos.models import Video


@pytest.mark.django_db
def test_pix_checkout_admin_review_and_credit(settings, tmp_path, client, django_user_model):
    settings.ADMIN_USER = "operador"
    settings.ADMIN_PASSWORD = "admin-test-pass"
    settings.PIX_MERCHANT_CITY = "São Paulo"
    settings.MEDIA_ROOT = tmp_path
    owner = django_user_model.objects.create_user("pix-owner")
    fake_admin = django_user_model.objects.create_superuser("other-admin", password="other-test-pass")
    offer = PixOffer.objects.create(name="30 minutos", amount=Decimal("19.90"), credit_minutes=30, credit_clips=5)
    client.force_login(owner)
    response = client.post(reverse("pix-start", args=[offer.public_id]))
    assert response.status_code == 302
    order = PixOrder.objects.get()
    code = payload(order)
    assert "62151351000150" in code and "540519.90" in code and "6009SAO PAULO" in code
    assert order.public_id.hex[:25] in code
    assert code[-4:] == f"{crc_hqx(code[:-4].encode(), 0xFFFF):04X}"
    assert client.get(reverse("pix-qr", args=[order.public_id])).headers["Content-Type"] == "image/svg+xml"
    other = Client()
    other.force_login(fake_admin)
    assert other.get(reverse("pix-order", args=[order.public_id])).status_code == 404
    assert other.get(reverse("admin:index")).status_code == 302
    assert other.post(reverse("admin:login"), {"username": "other-admin", "password": "other-test-pass"}).status_code == 200
    response = client.post(reverse("pix-order", args=[order.public_id]), {
        "receipt": SimpleUploadedFile("recibo.pdf", b"%PDF-1.4\n", content_type="application/pdf"),
    })
    assert response.status_code == 302
    order.refresh_from_db()
    assert order.status == PixOrder.Status.REVIEW and CreditGrant.objects.count() == 0

    panel = Client()
    assert panel.post(reverse("admin:login"), {"username": "operador", "password": "admin-test-pass"}).status_code == 302
    assert panel.get(reverse("admin:index")).status_code == 200
    assert panel.get(reverse("admin:subscriptions_pixorder_change", args=[order.pk])).status_code == 200
    assert other.get(reverse("admin:pix-receipt", args=[order.public_id])).status_code == 302
    proof = panel.get(reverse("admin:pix-receipt", args=[order.public_id]))
    assert proof.status_code == 200 and "attachment" in proof.headers["Content-Disposition"]
    assert b"".join(proof.streaming_content).startswith(b"%PDF-")
    review = reverse("admin:pix-review", args=[order.public_id])
    assert panel.post(review, {"decision": "approve"}).status_code == 302
    assert CreditGrant.objects.count() == 0
    for _ in range(2):
        assert panel.post(review, {"decision": "approve", "confirmed": "yes"}).status_code == 302
    assert CreditGrant.objects.count() == 1
    assert credits_for(order.workspace, period_start()) == (1800, 5)
    video = Video.objects.create(workspace=order.workspace, title="Com créditos")
    reserve(video, duration=4200, clips=31)
    settings.ADMIN_PASSWORD = "rotated-admin-password"
    assert panel.get(reverse("admin:index")).status_code == 302


@pytest.mark.django_db
def test_subscription_renews_and_expires(django_user_model):
    workspace = personal_workspace(django_user_model.objects.create_user("pix-subscriber"))
    starter = SubscriptionPlan.objects.get(name="Starter")
    offer = PixOffer.objects.create(name="Starter por 30 dias", amount=Decimal("29.90"), plan=starter)
    for _ in range(2):
        order = create_order(workspace, offer)
        order.status = PixOrder.Status.REVIEW
        order.receipt = "private/receipts/test.pdf"
        order.save(update_fields=["status", "receipt"])
        assert review_order(order, True)
    subscription = Subscription.objects.get(workspace=workspace)
    assert plan_for(workspace) == starter and subscription.paid_until > timezone.now() + timedelta(days=59)
    subscription.paid_until = timezone.now() - timedelta(days=1)
    subscription.save(update_fields=["paid_until"])
    assert plan_for(workspace).name == "Free"
