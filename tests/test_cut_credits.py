import pytest

from accounts.services import personal_workspace
from ai_engine.models import AIAnalysis, Highlight
from subscriptions.models import CreditGrant, PixOrder, SubscriptionPlan, UsageRecord
from subscriptions.services import LimitExceeded, period_start, plan_for
from videos.models import Video
from videos.tasks import generate_clips


@pytest.mark.django_db
def test_three_default_plans_and_additional_plan():
    assert set(SubscriptionPlan.objects.filter(is_default=True).values_list("name", flat=True)) == {
        "Free", "Starter", "Pro",
    }
    extra = SubscriptionPlan.objects.create(name="Criador", monthly_seconds=300, monthly_clips=4, storage_bytes=1024)
    assert not extra.is_default


@pytest.mark.django_db
def test_create_cuts_debits_once_and_rolls_back_on_error(django_user_model, monkeypatch):
    workspace = personal_workspace(django_user_model.objects.create_user(username="cut-credit-owner"))
    plan = plan_for(workspace)
    plan.monthly_clips = 1
    plan.save(update_fields=["monthly_clips"])
    video = Video.objects.create(
        title="Live", workspace=workspace, status=Video.State.GENERATING, options={"aspect": "9:16"}
    )
    analysis = AIAnalysis.objects.create(video=video)
    for rank in (1, 2):
        Highlight.objects.create(analysis=analysis, rank=rank, start=0, end=5, score=80)

    with pytest.raises(LimitExceeded, match="Saldo de cortes insuficiente"):
        generate_clips(video)
    assert video.clips.count() == 0
    assert not UsageRecord.objects.filter(video=video).exists()

    order = PixOrder.objects.create(workspace=workspace, offer_name="1 corte", amount=1)
    CreditGrant.objects.create(order=order, workspace=workspace, period=period_start(), clips=1, seconds=0)

    def fail_render_setup(*args):
        raise RuntimeError("render setup failed")

    monkeypatch.setattr("videos.tasks.version_for", fail_render_setup)
    with pytest.raises(RuntimeError, match="render setup failed"):
        generate_clips(video)
    assert video.clips.count() == 0
    assert not UsageRecord.objects.filter(video=video).exists()

    monkeypatch.setattr("videos.tasks.version_for", lambda *args: None)
    generate_clips(video)
    generate_clips(video)
    assert video.clips.count() == 2
    assert UsageRecord.objects.get(video=video).clips == 2
