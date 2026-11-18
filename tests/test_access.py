import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_public_and_authentication_pages(client):
    for name in ("landing", "account_login", "account_signup", "account_reset_password"):
        assert client.get(reverse(name)).status_code == 200
    assert client.get(reverse("dashboard")).status_code == 302
    assert client.get(reverse("api-video-list")).status_code == 403


@pytest.mark.django_db
def test_signup_and_dashboard(client, django_user_model):
    password = "correct horse ground finder 67!"
    response = client.post(reverse("account_signup"), {
        "email": "member@example.test", "password1": password, "password2": password,
    })
    assert response.status_code == 302
    assert django_user_model.objects.filter(email="member@example.test").exists()
    for name in ("dashboard", "library", "analytics", "publications", "usage", "settings"):
        assert client.get(reverse(name)).status_code == 200


@pytest.mark.django_db
def test_video_filters_use_workspace_scope(client, django_user_model):
    from accounts.models import Workspace
    from videos.models import Video

    user = django_user_model.objects.create_user("filter-owner")
    workspace = Workspace.objects.create(owner=user)
    other = Workspace.objects.create(owner=django_user_model.objects.create_user("filter-other"))
    Video.objects.create(workspace=workspace, title="Live publicada", status=Video.State.DONE)
    Video.objects.create(workspace=workspace, title="Live na fila", status=Video.State.PENDING)
    Video.objects.create(workspace=other, title="Live privada", status=Video.State.DONE)
    client.force_login(user)
    response = client.get(reverse("api-video-list"), {"search": "Live", "status": "done", "ordering": "title"})
    assert response.status_code == 200
    assert [item["title"] for item in response.json()["results"]] == ["Live publicada"]
