import pytest

from accounts.models import Workspace
from subscriptions.models import UsageRecord
from subscriptions.services import LimitExceeded, adjust_storage, plan_for, reserve
from videos.models import Video


@pytest.mark.django_db
def test_quota_rejects_overcommit_and_preserves_previous_usage(django_user_model):
    workspace = Workspace.objects.create(owner=django_user_model.objects.create_user("quota"))
    plan = plan_for(workspace)
    plan.monthly_seconds = 10
    plan.monthly_clips = 3
    plan.storage_bytes = 100
    plan.save()
    first = Video.objects.create(workspace=workspace, title="Primeiro")
    second = Video.objects.create(workspace=workspace, title="Segundo")
    reserve(first, duration=7, clips=2, size=40)
    reserve(first, duration=7, clips=2, size=40)
    with pytest.raises(LimitExceeded):
        reserve(second, duration=4, clips=1, size=40)
    with pytest.raises(LimitExceeded):
        reserve(second, duration=3, clips=2, size=40)
    reserve(second, duration=3, clips=1, size=40)
    with pytest.raises(LimitExceeded):
        adjust_storage(second, 21)
    adjust_storage(second, 20)
    assert UsageRecord.objects.get(video=first).bytes == 40
    assert UsageRecord.objects.get(video=second).bytes == 60
