from django.db import models
from core.models import Record


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=30, unique=True)
    is_default = models.BooleanField(default=False, editable=False)
    monthly_seconds = models.PositiveIntegerField()
    monthly_clips = models.PositiveIntegerField()
    storage_bytes = models.PositiveBigIntegerField()
    max_height = models.PositiveIntegerField(default=1080)
    social_accounts = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name


class Subscription(Record):
    workspace = models.OneToOneField("accounts.Workspace", on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    paid_until = models.DateTimeField(null=True, blank=True)


class UsageRecord(Record):
    workspace = models.ForeignKey("accounts.Workspace", on_delete=models.CASCADE)
    video = models.OneToOneField("videos.Video", on_delete=models.CASCADE)
    period = models.DateField(db_index=True)
    seconds = models.PositiveIntegerField(default=0)
    clips = models.PositiveIntegerField(default=0)
    bytes = models.PositiveBigIntegerField(default=0)


class PixOffer(Record):
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    plan = models.ForeignKey(SubscriptionPlan, null=True, blank=True, on_delete=models.PROTECT)
    credit_minutes = models.PositiveIntegerField(default=0)
    credit_clips = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="pix_offer_positive_amount"),
            models.CheckConstraint(
                condition=(
                    models.Q(plan__isnull=False, credit_minutes=0, credit_clips=0)
                    | (models.Q(plan__isnull=True) & (models.Q(credit_minutes__gt=0) | models.Q(credit_clips__gt=0)))
                ),
                name="pix_offer_has_plan_or_credit",
            ),
        ]

    def __str__(self):
        return self.name


class PixOrder(Record):
    class Status(models.TextChoices):
        AWAITING = "awaiting", "Aguardando comprovante"
        REVIEW = "review", "Em análise"
        APPROVED = "approved", "Aprovado"
        REJECTED = "rejected", "Recusado"

    workspace = models.ForeignKey("accounts.Workspace", on_delete=models.CASCADE)
    offer_name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    plan = models.ForeignKey(SubscriptionPlan, null=True, on_delete=models.PROTECT)
    credit_minutes = models.PositiveIntegerField(default=0)
    credit_clips = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.AWAITING, db_index=True)
    receipt = models.FileField(upload_to="private/receipts/", blank=True)
    reviewed_at = models.DateTimeField(null=True)
    review_note = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return f"{self.offer_name} · {self.get_status_display()}"


class CreditGrant(Record):
    order = models.OneToOneField(PixOrder, on_delete=models.PROTECT)
    workspace = models.ForeignKey("accounts.Workspace", on_delete=models.CASCADE)
    period = models.DateField()
    seconds = models.PositiveIntegerField()
    clips = models.PositiveIntegerField()

    class Meta:
        indexes = [models.Index(fields=["workspace", "period"])]
