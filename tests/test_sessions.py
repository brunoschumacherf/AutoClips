import pytest
from django.test import Client
from django.urls import reverse

from accounts.models import TrackedSession


@pytest.mark.django_db
def test_revoke_only_own_session(client, django_user_model):
    owner = django_user_model.objects.create_user("owner-sessions")
    stranger = django_user_model.objects.create_user("stranger-sessions")
    second = Client(HTTP_USER_AGENT="second-browser")
    second.force_login(owner)
    client.force_login(owner)
    other = Client()
    other.force_login(stranger)
    owned_session = TrackedSession.objects.get(user=owner, session_key=second.cookies["sessionid"].value)
    foreign_session = TrackedSession.objects.get(user=stranger)
    assert client.get(reverse("sessions")).status_code == 200
    assert client.post(reverse("session-revoke", args=[foreign_session.public_id])).status_code == 404
    assert client.post(reverse("session-revoke", args=[owned_session.public_id])).status_code == 302
    assert second.get(reverse("dashboard")).status_code == 302
    assert client.get(reverse("dashboard")).status_code == 200
