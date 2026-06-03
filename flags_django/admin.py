"""Admin configuration for the feature flag system."""

from django.contrib import admin

from flags_django.models import AuditLog, Environment, FeatureFlag, FlagRule, SnapshotVersion


class ReadOnlyAdminMixin:
    """Inspection-only admin.

    All writes must go through the service layer (CLI / services), which validates
    the definition, writes an audit log, and bumps the snapshot version. The Django
    admin in the MVP exists for inspection only, so it never creates, edits, or
    deletes rows directly — that keeps the audit trail trustworthy and prevents
    unvalidated definitions from becoming live config. See ADR 0004 and the README
    "Threat model" section.
    """

    # obj=None default keeps this compatible with both ModelAdmin.has_add_permission
    # (request) and InlineModelAdmin.has_add_permission (request, obj).
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class FlagRuleInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = FlagRule
    extra = 0


@admin.register(Environment)
class EnvironmentAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("slug", "name", "created_at", "updated_at")
    search_fields = ("slug", "name")


@admin.register(FeatureFlag)
class FeatureFlagAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "key",
        "environment",
        "enabled",
        "kill_switch",
        "default_value",
        "rollout_percentage",
        "version",
        "archived_at",
    )
    list_filter = ("environment", "enabled", "kill_switch", "archived_at")
    search_fields = ("key", "name", "description")
    inlines = [FlagRuleInline]


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("created_at", "environment", "flag", "action", "actor")
    list_filter = ("environment", "action")
    search_fields = ("flag__key", "actor", "action")


@admin.register(SnapshotVersion)
class SnapshotVersionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("environment", "version", "etag", "updated_at")
