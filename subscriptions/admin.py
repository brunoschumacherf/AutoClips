from django.contrib import admin, messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.views.decorators.http import require_POST, require_safe

from clips.views import serve
from .models import CreditGrant, PixOffer, PixOrder, SubscriptionPlan
from .payments import review_order


@admin.register(PixOffer)
class PixOfferAdmin(admin.ModelAdmin):
    list_display = ("name", "amount", "plan", "credit_minutes", "credit_clips", "active")
    list_filter = ("active",)
    search_fields = ("name",)


@admin.register(PixOrder)
class PixOrderAdmin(admin.ModelAdmin):
    list_display = ("offer_name", "buyer", "amount", "status", "created_at", "reviewed_at")
    list_filter = ("status", "created_at")
    search_fields = ("offer_name", "workspace__owner__email", "=public_id")
    list_select_related = ("workspace__owner",)
    fields = ("public_id", "workspace", "offer_name", "amount", "plan", "credit_minutes", "credit_clips",
              "status", "receipt_download", "created_at", "reviewed_at", "review_note")
    readonly_fields = fields
    change_form_template = "admin/pix_order.html"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Cliente", ordering="workspace__owner__email")
    def buyer(self, order):
        user = order.workspace.owner
        return user.email or user.get_username()

    @admin.display(description="Comprovante")
    def receipt_download(self, order):
        if not order.receipt:
            return "Aguardando envio"
        return format_html('<a href="{}">Baixar comprovante</a>', reverse("admin:pix-receipt", args=[order.public_id]))

    def get_urls(self):
        return [
            path("receipt/<uuid:public_id>/", self.admin_site.admin_view(require_safe(self.download)), name="pix-receipt"),
            path("review/<uuid:public_id>/", self.admin_site.admin_view(require_POST(self.review)), name="pix-review"),
        ] + super().get_urls()

    def download(self, request, public_id):
        order = get_object_or_404(PixOrder, public_id=public_id)
        if not self.has_view_permission(request, order) or not order.receipt:
            raise Http404
        return serve(order.receipt, request, download=True)

    def review(self, request, public_id):
        order = get_object_or_404(PixOrder, public_id=public_id)
        if not self.has_change_permission(request, order):
            raise Http404
        decision = request.POST.get("decision")
        note = request.POST.get("note", "").strip()
        if decision not in {"approve", "reject"} or len(note) > 300:
            self.message_user(request, "Confira a decisão e o tamanho da observação.", messages.ERROR)
        elif decision == "approve" and request.POST.get("confirmed") != "yes":
            self.message_user(request, "Confirme a entrada do valor no extrato bancário.", messages.ERROR)
        elif review_order(order, decision == "approve", note):
            self.message_user(request, "Pedido revisado.", messages.SUCCESS)
        else:
            self.message_user(request, "Somente pedidos em análise podem ser revisados.", messages.ERROR)
        return redirect("admin:subscriptions_pixorder_change", order.pk)


@admin.register(CreditGrant)
class CreditGrantAdmin(admin.ModelAdmin):
    list_display = ("workspace", "period", "seconds", "clips", "order")
    readonly_fields = ("workspace", "period", "seconds", "clips", "order")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "default_plan", "monthly_seconds", "monthly_clips", "social_accounts")
    search_fields = ("name",)
    ordering = ("-is_default", "monthly_seconds", "name")
    readonly_fields = ("default_plan",)

    @admin.display(description="Plano padrão", boolean=True, ordering="is_default")
    def default_plan(self, plan):
        return plan.is_default

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (obj is None or not obj.is_default)

    def get_readonly_fields(self, request, obj=None):
        return (*self.readonly_fields, "name") if obj and obj.is_default else self.readonly_fields
