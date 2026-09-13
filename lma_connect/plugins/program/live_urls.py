"""Routes for the SSE process — mounted under /events/ (see lma_connect/urls.py)."""

from django.urls import path

from . import live

app_name = "live"

urlpatterns = [
    path("ping/", live.ping_stream, name="ping"),
]
