"""Models for the feature flag system."""

from django.db import models
from django.db.models import Q

def default_false():
    return False


class Environment(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["slug"]

    def __str__(self) -> str:
        return self.slug


class FeatureFlag(models.Model):
    key = models.CharField(max_length=120)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    environment = models.ForeignKey(Environment, on_delete=models.PROTECT, related_name="flags")
    enabled = models.BooleanField(default=False)
    kill_switch = models.BooleanField(default=False)
    default_value = models.JSONField(default=default_false)
    rollout_percentage = models.PositiveSmallIntegerField(default=0)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["environment__slug", "key"]
        constraints = [
            models.UniqueConstraint(
                fields=["environment", "key"], name="unique_flag_key_per_environment"
            ),
            models.CheckConstraint(
                condition=Q(rollout_percentage__gte=0) & Q(rollout_percentage__lte=100),
                name="flag_rollout_percentage_0_100",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.environment.slug}:{self.key}"


class FlagRule(models.Model):
    flag = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE, related_name="rules")
    order = models.PositiveIntegerField()
    attribute = models.CharField(max_length=120)
    operator = models.CharField(max_length=40)
    value = models.JSONField()
    result = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["flag", "order"]
        constraints = [
            models.UniqueConstraint(fields=["flag", "order"], name="unique_rule_order_per_flag"),
        ]

    def __str__(self) -> str:
        return f"{self.flag.key} rule {self.order}"


class AuditLog(models.Model):
    flag = models.ForeignKey(FeatureFlag, on_delete=models.PROTECT, related_name="audit_logs")
    environment = models.ForeignKey(
        Environment, on_delete=models.PROTECT, related_name="audit_logs"
    )
    action = models.CharField(max_length=80)
    # actor is a free-form label (e.g. "cli", "system"). MVP has no auth, so this
    # is intentionally not a User FK. See README "Threat model".
    actor = models.CharField(max_length=150)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M:%S} {self.action} {self.flag.key}"


class SnapshotVersion(models.Model):
    environment = models.OneToOneField(
        Environment,
        on_delete=models.CASCADE,
        related_name="snapshot_version",
    )
    version = models.PositiveIntegerField(default=0)
    etag = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["environment__slug"]

    # `etag` stores the raw version token (e.g. "production-1"). All HTTP and
    # client comparisons must go through `quoted_etag`, which wraps it in quotes
    # per RFC 7232; the raw column is never compared against a request header.
    def save(self, *args, **kwargs):
        self.etag = f"{self.environment.slug}-{self.version}"
        super().save(*args, **kwargs)

    @property
    def quoted_etag(self) -> str:
        return f'"{self.etag}"'

    def __str__(self) -> str:
        return self.quoted_etag
