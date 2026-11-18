from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone

from accounts.models import Workspace
from clips.models import Clip, ClipVersion
from publishing.models import Publication, PublicationSchedule
from publishing.services import connect
from publishing.tasks import dispatch_due
from subscriptions.models import Subscription, SubscriptionPlan
from subscriptions.services import LimitExceeded
from videos.models import Video


@pytest.mark.django_db
def test_publication_claim_and_status(django_user_model, settings, monkeypatch):
    settings.OAUTH_ENCRYPTION_KEY = Fernet.generate_key().decode()
    owner = django_user_model.objects.create_user("creator")
    workspace = Workspace.objects.create(owner=owner)
    with pytest.raises(LimitExceeded):
        connect(workspace, "channel", "Minha conta", "secret")
    Subscription.objects.update_or_create(workspace=workspace, defaults={"plan": SubscriptionPlan.objects.get(name="Starter")})
    account = connect(workspace, "channel", "Minha conta", "secret")
    assert b"secret" not in bytes(account.grant)
    video = Video.objects.create(workspace=workspace, title="Live")
    clip = Clip.objects.create(video=video, title="Corte")
    version = ClipVersion.objects.create(clip=clip, start=0, end=3, output="test.mp4")
    publication = Publication.objects.create(account=account, version=version, title="Corte")
    PublicationSchedule.objects.create(publication=publication, run_at=timezone.now())
    upload = Mock(return_value="youtube-video")
    monkeypatch.setattr("publishing.tasks.enabled", lambda: True)
    monkeypatch.setattr("publishing.tasks.access_token", lambda account: "access")
    monkeypatch.setattr("publishing.tasks.upload", upload)
    monkeypatch.setattr("publishing.tasks.remote_status", lambda remote_id, access: "processed")
    dispatch_due()
    dispatch_due()
    upload.assert_called_once()
    publication.refresh_from_db()
    assert (publication.status, publication.remote_id) == ("processed", "youtube-video")
