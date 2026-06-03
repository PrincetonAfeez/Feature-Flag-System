"""End-to-end: CLI write path → snapshot read → staff eval → local core eval."""

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse

from flags_core.evaluator import evaluate_snapshot
from flags_core.serialization import snapshot_from_dict


@pytest.mark.django_db
def test_cli_create_snapshot_and_eval_agree(client, django_user_model):
    out = StringIO()
    call_command(
        "flagctl",
        "create",
        "e2e_flag",
        "--env",
        "production",
        "--default",
        "false",
        stdout=out,
    )
    call_command("flagctl", "enable", "e2e_flag", "--env", "production", stdout=out)
    call_command("flagctl", "rollout", "e2e_flag", "100", "--env", "production", stdout=out)

    snapshot_url = reverse("flag-snapshot", kwargs={"env": "production"})
    snapshot_response = client.get(snapshot_url)
    assert snapshot_response.status_code == 200
    payload = snapshot_response.json()
    assert payload["flags"]["e2e_flag"]["enabled"] is True
    assert payload["flags"]["e2e_flag"]["rollout_percentage"] == 100

    staff = django_user_model.objects.create_user("e2e_admin", password="pw", is_staff=True)
    client.force_login(staff)
    eval_response = client.post(
        reverse("flag-eval-debug", kwargs={"env": "production"}),
        data=json.dumps({"flag_key": "e2e_flag", "context": {"user_id": "user_42"}}),
        content_type="application/json",
    )
    assert eval_response.status_code == 200
    api_result = eval_response.json()
    assert api_result["value"] is True
    assert api_result["reason"] == "percentage_rollout"

    snapshot = snapshot_from_dict(payload)
    local_result = evaluate_snapshot(snapshot, "e2e_flag", {"user_id": "user_42"})
    assert local_result.value == api_result["value"]
    assert local_result.reason == api_result["reason"]
