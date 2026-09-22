import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_register_login_me_flow(api_client):
    register_payload = {"email": "jane@example.com", "password": "correct-horse-battery"}
    response = api_client.post(reverse("auth-register"), register_payload)
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    access_token = body["data"]["tokens"]["access"]
    assert User.objects.filter(email="jane@example.com").exists()

    login_response = api_client.post(reverse("auth-login"), register_payload)
    assert login_response.status_code == 200
    assert login_response.json()["success"] is True

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    me_response = api_client.get(reverse("auth-me"))
    assert me_response.status_code == 200
    assert me_response.json()["data"]["email"] == "jane@example.com"


@pytest.mark.django_db
def test_login_with_wrong_password_returns_standard_error_envelope(api_client):
    User.objects.create_user(email="jane@example.com", password="correct-horse-battery")
    response = api_client.post(reverse("auth-login"), {"email": "jane@example.com", "password": "wrong"})
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False


def test_me_requires_authentication(api_client):
    response = api_client.get(reverse("auth-me"))
    assert response.status_code == 401
