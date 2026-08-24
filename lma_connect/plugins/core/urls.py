from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.welcome, name="welcome"),
    path("healthz", views.healthz, name="healthz"),
    path("home/", views.home, name="home"),
    path("info/", views.info, name="info"),
    path("help/", views.help_page, name="help"),
    # Hard-coded attribution / licence page. The footer links here on every
    # page — that link is also the AGPL §13 source offer.
    path("about/", views.about, name="about"),
    path("legal/<slug:slug>/", views.legal, name="legal"),
    path("event/<slug:slug>/", views.event_detail, name="event_detail"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    # The version token lives in the path, not in a ?query — iOS ignores
    # apple-touch-icon URLs carrying one. The token breaks Safari's icon cache.
    path("icon-<int:size>-<slug:ver>.png", views.app_icon, name="app_icon"),
    path("icon-maskable-<int:size>-<slug:ver>.png", views.app_icon,
         {"maskable": True}, name="app_icon_maskable"),
    # The opaque variant without an alpha channel — for everything iOS might
    # touch (apple-touch-icon plus the "any" icons in the manifest, which
    # Safari reads too since 16.4). Android gets the transparent one via
    # "maskable".
    path("icon-opaque-<int:size>-<slug:ver>.png", views.app_icon,
         {"opaque": True}, name="app_icon_opaque"),
]
