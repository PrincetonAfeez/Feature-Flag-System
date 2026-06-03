"""API view edge cases."""

import pytest
from django.urls import reverse

from flags_django.services import FlagService


@pytest.mark.django_db
def test_snapshot_if_none_match_comma_separated_list(client):
    FlagService.create_flag(
        {
            "environment": "production",
            "key": "flag",
            "default": False,
        }
    )
    url = reverse("flag-snapshot", kwargs={"env": "production"})
    first = client.get(url)
    etag = first["ETag"]
    response = client.get(url, HTTP_IF_NONE_MATCH=f'"stale", {etag}, "other"')
    assert response.status_code == 304


@pytest.mark.django_db
def test_eval_debug_comma_separated_etag_not_applicable(client, django_user_model):
    """Eval endpoint returns JSON errors for unknown environment."""
    staff = django_user_model.objects.create_user("admin", password="pw", is_staff=True)
    client.force_login(staff)
    response = client.post(
        reverse("flag-eval-debug", kwargs={"env": "missing"}),
        data={"flag_key": "x"},
        content_type="application/json",
    )
    assert response.status_code == 404
