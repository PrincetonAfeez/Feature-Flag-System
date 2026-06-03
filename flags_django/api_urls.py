"""URL configuration for the feature flag system."""

from django.urls import path

from flags_django import api_views

urlpatterns = [
    path("environments/<slug:env>/snapshot/", api_views.snapshot, name="flag-snapshot"),
    path("environments/<slug:env>/eval/", api_views.eval_debug, name="flag-eval-debug"),
]
