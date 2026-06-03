"""Tests for the API module."""

import pytest
from django.urls import reverse

from flags_django.models import Environment
from flags_django.services import FlagService


@pytest.mark.django_db
def test_snapshot_unknown_environment_returns_404_without_creating_it(client):
    url = reverse("flag-snapshot", kwargs={"env": "ghost"})
    response = client.get(url)

    assert response.status_code == 404
    # The read must not have created the environment as a side effect.
    assert not Environment.objects.filter(slug="ghost").exists()


@pytest.mark.django_db
def test_snapshot_endpoint_etag_and_304(client):
    FlagService.create_flag(
        {
            "environment": "production",
            "key": "new_checkout",
            "name": "New Checkout",
            "default": False,
            "rollout_percentage": 0,
        }
    )

    url = reverse("flag-snapshot", kwargs={"env": "production"})
    response = client.get(url)

    assert response.status_code == 200
    assert response["ETag"] == '"production-1"'
    assert response["Cache-Control"] == "private, must-revalidate"
    assert response.json()["flags"]["new_checkout"]["key"] == "new_checkout"

    unchanged = client.get(url, HTTP_IF_NONE_MATCH=response["ETag"])
    assert unchanged.status_code == 304
    assert unchanged["ETag"] == '"production-1"'
    assert unchanged["Cache-Control"] == "private, must-revalidate"

    FlagService.enable_flag("production", "new_checkout")
    changed = client.get(url, HTTP_IF_NONE_MATCH=response["ETag"])
    assert changed.status_code == 200
    assert changed["ETag"] == '"production-2"'


@pytest.mark.django_db
def test_snapshot_endpoint_honors_wildcard_if_none_match(client):
    FlagService.create_flag(
        {
            "environment": "production",
            "key": "new_checkout",
            "name": "New Checkout",
            "default": False,
            "rollout_percentage": 0,
        }
    )
    url = reverse("flag-snapshot", kwargs={"env": "production"})
    response = client.get(url, HTTP_IF_NONE_MATCH="*")
    assert response.status_code == 304


@pytest.mark.django_db
def test_eval_debug_requires_staff(client):
    FlagService.create_flag(
        {
            "environment": "production",
            "key": "new_checkout",
            "name": "New Checkout",
            "default": False,
            "rollout_percentage": 100,
            "enabled": True,
        }
    )

    response = client.post(
        reverse("flag-eval-debug", kwargs={"env": "production"}),
        data={"flag_key": "new_checkout"},
        content_type="application/json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_eval_debug_endpoint_uses_core(client, django_user_model):
    staff = django_user_model.objects.create_user("admin", password="pw", is_staff=True)
    client.force_login(staff)

    FlagService.create_flag(
        {
            "environment": "production",
            "key": "new_checkout",
            "name": "New Checkout",
            "default": False,
            "rollout_percentage": 100,
            "enabled": True,
        }
    )

    response = client.post(
        reverse("flag-eval-debug", kwargs={"env": "production"}),
        data={"flag_key": "new_checkout", "context": {"user_id": "u1"}},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["value"] is True
    assert response.json()["reason"] == "percentage_rollout"


@pytest.mark.django_db
def test_eval_debug_unknown_flag_returns_404(client, django_user_model):
    staff = django_user_model.objects.create_user("admin2", password="pw", is_staff=True)
    client.force_login(staff)

    response = client.post(
        reverse("flag-eval-debug", kwargs={"env": "production"}),
        data={"flag_key": "does_not_exist"},
        content_type="application/json",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_eval_debug_invalid_json_returns_400(client, django_user_model):
    staff = django_user_model.objects.create_user("admin3", password="pw", is_staff=True)
    client.force_login(staff)

    response = client.post(
        reverse("flag-eval-debug", kwargs={"env": "production"}),
        data="not json",
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_eval_debug_missing_flag_key_returns_400(client, django_user_model):
    staff = django_user_model.objects.create_user("admin4", password="pw", is_staff=True)
    client.force_login(staff)

    response = client.post(
        reverse("flag-eval-debug", kwargs={"env": "production"}),
        data={"context": {"user_id": "u1"}},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "flag_key must be a non-empty string"


@pytest.mark.django_db
def test_eval_debug_rejects_boolean_flag_key(client, django_user_model):
    staff = django_user_model.objects.create_user("admin_fk_bool", password="pw", is_staff=True)
    client.force_login(staff)

    response = client.post(
        reverse("flag-eval-debug", kwargs={"env": "production"}),
        data={"flag_key": True, "context": {}},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "flag_key must be a non-empty string"


@pytest.mark.django_db
def test_eval_debug_rejects_list_flag_key(client, django_user_model):
    staff = django_user_model.objects.create_user("admin_fk_list", password="pw", is_staff=True)
    client.force_login(staff)

    response = client.post(
        reverse("flag-eval-debug", kwargs={"env": "production"}),
        data={"flag_key": [], "context": {}},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "flag_key must be a non-empty string"


@pytest.mark.django_db
def test_eval_debug_rejects_empty_string_flag_key(client, django_user_model):
    staff = django_user_model.objects.create_user("admin_fk_empty", password="pw", is_staff=True)
    client.force_login(staff)

    response = client.post(
        reverse("flag-eval-debug", kwargs={"env": "production"}),
        data={"flag_key": "", "context": {}},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "flag_key must be a non-empty string"


@pytest.mark.django_db
def test_eval_debug_accepts_string_flag_key(client, django_user_model):
    staff = django_user_model.objects.create_user("admin_fk_str", password="pw", is_staff=True)
    client.force_login(staff)

    FlagService.create_flag(
        {
            "environment": "production",
            "key": "new_checkout",
            "name": "New Checkout",
            "default": False,
            "rollout_percentage": 100,
            "enabled": True,
        }
    )

    response = client.post(
        reverse("flag-eval-debug", kwargs={"env": "production"}),
        data={"flag_key": "new_checkout", "context": {"user_id": "u1"}},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["flag_key"] == "new_checkout"


@pytest.mark.django_db
def test_eval_debug_oversized_body_returns_413(client, django_user_model):
    staff = django_user_model.objects.create_user("admin5", password="pw", is_staff=True)
    client.force_login(staff)

    oversized = {"flag_key": "x", "context": {"blob": "a" * 70000}}
    response = client.post(
        reverse("flag-eval-debug", kwargs={"env": "production"}),
        data=oversized,
        content_type="application/json",
    )

    assert response.status_code == 413


@pytest.mark.django_db
def test_snapshot_returns_500_when_flag_definition_is_corrupt(client):
    FlagService.create_flag(
        {
            "environment": "production",
            "key": "new_checkout",
            "name": "New Checkout",
            "default": False,
            "rollout_percentage": 0,
        }
    )
    flag = FlagService.get_flag("production", "new_checkout")
    flag.default_value = "not_bool"
    flag.save(update_fields=["default_value"])

    response = client.get(reverse("flag-snapshot", kwargs={"env": "production"}))

    assert response.status_code == 500
    assert "default must be a boolean" in response.json()["error"]


@pytest.mark.django_db
def test_eval_debug_returns_500_when_flag_definition_is_corrupt(client, django_user_model):
    staff = django_user_model.objects.create_user("admin6", password="pw", is_staff=True)
    client.force_login(staff)

    FlagService.create_flag(
        {
            "environment": "production",
            "key": "new_checkout",
            "name": "New Checkout",
            "default": False,
            "rollout_percentage": 0,
        }
    )
    flag = FlagService.get_flag("production", "new_checkout")
    flag.default_value = "not_bool"
    flag.save(update_fields=["default_value"])

    response = client.post(
        reverse("flag-eval-debug", kwargs={"env": "production"}),
        data={"flag_key": "new_checkout", "context": {"user_id": "u1"}},
        content_type="application/json",
    )

    assert response.status_code == 500
    assert "default must be a boolean" in response.json()["error"]


@pytest.mark.django_db
def test_eval_debug_rejects_list_context(client, django_user_model):
    staff = django_user_model.objects.create_user("admin_ctx_list", password="pw", is_staff=True)
    client.force_login(staff)

    FlagService.create_flag(
        {
            "environment": "production",
            "key": "new_checkout",
            "name": "New Checkout",
            "default": False,
            "rollout_percentage": 100,
            "enabled": True,
        }
    )

    response = client.post(
        reverse("flag-eval-debug", kwargs={"env": "production"}),
        data={"flag_key": "new_checkout", "context": []},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "context must be a JSON object"


@pytest.mark.django_db
def test_eval_debug_rejects_string_context(client, django_user_model):
    staff = django_user_model.objects.create_user("admin_ctx_str", password="pw", is_staff=True)
    client.force_login(staff)

    FlagService.create_flag(
        {
            "environment": "production",
            "key": "new_checkout",
            "name": "New Checkout",
            "default": False,
            "rollout_percentage": 100,
            "enabled": True,
        }
    )

    response = client.post(
        reverse("flag-eval-debug", kwargs={"env": "production"}),
        data={"flag_key": "new_checkout", "context": "bad"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "context must be a JSON object"


@pytest.mark.django_db
def test_eval_debug_omitted_context_still_works(client, django_user_model):
    staff = django_user_model.objects.create_user("admin_ctx_omit", password="pw", is_staff=True)
    client.force_login(staff)

    FlagService.create_flag(
        {
            "environment": "production",
            "key": "new_checkout",
            "name": "New Checkout",
            "default": False,
            "rollout_percentage": 0,
            "enabled": True,
        }
    )

    response = client.post(
        reverse("flag-eval-debug", kwargs={"env": "production"}),
        data={"flag_key": "new_checkout"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["value"] is False


@pytest.mark.django_db
def test_eval_debug_rejects_boolean_user_id(client, django_user_model):
    staff = django_user_model.objects.create_user("admin7", password="pw", is_staff=True)
    client.force_login(staff)

    FlagService.create_flag(
        {
            "environment": "production",
            "key": "new_checkout",
            "name": "New Checkout",
            "default": False,
            "rollout_percentage": 0,
            "enabled": True,
        }
    )

    response = client.post(
        reverse("flag-eval-debug", kwargs={"env": "production"}),
        data={"flag_key": "new_checkout", "context": {"user_id": True}},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "user_id" in response.json()["error"]
