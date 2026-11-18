from io import BytesIO
from pathlib import Path

import qrcode
import qrcode.image.svg
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from accounts.services import personal_workspace
from . import pix
from .models import PixOffer, PixOrder
from .payments import attach_receipt, create_order


class ReceiptForm(forms.Form):
    receipt = forms.FileField(label="Comprovante Pix (PDF, PNG ou JPEG, até 5 MB)")

    def clean_receipt(self):
        upload = self.cleaned_data["receipt"]
        if not 0 < upload.size <= 5 * 1024**2:
            raise ValidationError("O comprovante deve ter até 5 MB.")
        signature = upload.read(8)
        upload.seek(0)
        formats = {".pdf": b"%PDF-", ".png": b"\x89PNG\r\n\x1a\n", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff"}
        expected = formats.get(Path(upload.name).suffix.lower())
        if not expected or not signature.startswith(expected):
            raise ValidationError("Envie um comprovante PDF, PNG ou JPEG válido.")
        return upload


@login_required
@require_POST
def start(request, public_id):
    if not pix.enabled():
        raise Http404
    offer = get_object_or_404(PixOffer, public_id=public_id, active=True)
    order = create_order(personal_workspace(request.user), offer)
    return redirect("pix-order", public_id=order.public_id)


def own_order(request, public_id):
    return get_object_or_404(PixOrder, public_id=public_id, workspace__owner=request.user)


@login_required
@never_cache
def order_detail(request, public_id):
    order = own_order(request, public_id)
    form = ReceiptForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if form.is_valid():
            try:
                attach_receipt(order, form.cleaned_data["receipt"])
            except ValidationError as error:
                form.add_error("receipt", error)
            else:
                return redirect("pix-order", public_id=public_id)
    return render(request, "pix_order.html", {
        "order": order, "form": form, "pix_code": pix.payload(order)
        if order.status == PixOrder.Status.AWAITING and pix.enabled() else "",
    })


@login_required
@never_cache
def qr(request, public_id):
    order = own_order(request, public_id)
    if not pix.enabled() or order.status != PixOrder.Status.AWAITING:
        raise Http404
    graphic = qrcode.make(pix.payload(order), image_factory=qrcode.image.svg.SvgPathImage)
    output = BytesIO()
    graphic.save(output)
    return HttpResponse(output.getvalue(), content_type="image/svg+xml")
