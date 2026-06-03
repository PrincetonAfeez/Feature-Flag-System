"""Tests for the admin module."""

from django.contrib.admin.sites import AdminSite

from flags_django.admin import (
    AuditLogAdmin,
    EnvironmentAdmin,
    FeatureFlagAdmin,
    SnapshotVersionAdmin,
)
from flags_django.models import AuditLog, Environment, FeatureFlag, SnapshotVersion

ADMINS = [
    (FeatureFlagAdmin, FeatureFlag),
    (AuditLogAdmin, AuditLog),
    (SnapshotVersionAdmin, SnapshotVersion),
    (EnvironmentAdmin, Environment),
]


def test_admin_is_inspection_only():
    site = AdminSite()
    for admin_cls, model in ADMINS:
        admin_obj = admin_cls(model, site)
        assert admin_obj.has_add_permission(None) is False
        assert admin_obj.has_change_permission(None) is False
        assert admin_obj.has_delete_permission(None) is False
