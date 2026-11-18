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
