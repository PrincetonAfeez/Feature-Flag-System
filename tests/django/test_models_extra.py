"""Django model methods and defaults."""

import pytest

from flags_django.models import SnapshotVersion
from flags_django.services import FlagService


@pytest.mark.django_db
def test_snapshot_version_etag_updates_on_save():
    FlagService.create_flag(
        {"environment": "staging", "key": "f1", "default": False},
    )
    version = SnapshotVersion.objects.get(environment__slug="staging")
    assert version.etag == "staging-1"
    assert version.quoted_etag == '"staging-1"'
    version.version = 5
    version.save()
    assert version.etag == "staging-5"
    assert str(version) == '"staging-5"'
