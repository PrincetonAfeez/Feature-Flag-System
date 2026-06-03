"""App configuration for the feature flag system."""

from django.apps import AppConfig


class FlagsDjangoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "flags_django"
