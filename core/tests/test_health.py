import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_health_check_ok(client):
    response = client.get(reverse("health-check"))
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_service_landing(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
