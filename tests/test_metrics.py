import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_metrics_require_bearer_token(client, settings):
    settings.METRICS_TOKEN = "metrics-test-token"
    endpoint = reverse("metrics")
    assert client.get(endpoint).status_code == 404
    response = client.get(endpoint, HTTP_AUTHORIZATION="Bearer metrics-test-token")
    assert response.status_code == 200
    assert b'cortalives_processing_jobs{status="done"} 0' in response.content
