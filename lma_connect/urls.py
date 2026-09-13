from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.http import HttpResponsePermanentRedirect
from django.urls import get_script_prefix, include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),  # set_language endpoint
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("program/", include("lma_connect.plugins.program.urls", namespace="program")),
    path("speakers/", include("lma_connect.plugins.people.urls", namespace="people")),
    path("sponsors/", include("lma_connect.plugins.sponsors.urls", namespace="sponsors")),
    path("abstracts/", include("lma_connect.plugins.abstracts.urls", namespace="abstracts")),
    path("feedback/", include("lma_connect.plugins.feedback.urls", namespace="feedback")),
    path("qr/", include("lma_connect.plugins.qr.urls", namespace="qr")),
    path("expo/", include("lma_connect.plugins.expo.urls", namespace="expo")),
    # Long-lived SSE streams — served by the separate ASGI process
    # (deploy/lma-connect-sse.service), see docs/live-updates-sse.md.
    path("events/", include("lma_connect.plugins.program.live_urls", namespace="live")),
    path("", include("lma_connect.plugins.gamification.urls", namespace="gamification")),
    path("", include("lma_connect.plugins.access.urls", namespace="access")),
    path("", include("lma_connect.plugins.core.urls", namespace="core")),
]

def _legacy_prefix_redirect(new_prefix: str):
    """Build a view that permanently redirects a renamed URL prefix.

    Not `RedirectView(url=...)`: that would emit an absolute path without the
    script prefix and break sub-path deployments (FORCE_SCRIPT_NAME).
    `get_script_prefix()` returns "/" or e.g. "/conf/", so the target stays
    correct in both setups.
    """
    def view(request, rest=""):
        return HttpResponsePermanentRedirect(f"{get_script_prefix()}{new_prefix}{rest}")
    return view


# Legacy German URL prefixes from the app's first deployment. Badges, posters
# and slide decks printed for that event carry QR codes pointing at /programm/
# and /sponsoren/ — those must not 404 after the rename. Permanent redirects
# keep them alive at no maintenance cost; drop this block once no printed
# material referencing them is in circulation any more.
urlpatterns += [
    path("programm/", _legacy_prefix_redirect("program/")),
    path("programm/<path:rest>", _legacy_prefix_redirect("program/")),
    path("sponsoren/", _legacy_prefix_redirect("sponsors/")),
    path("sponsoren/<path:rest>", _legacy_prefix_redirect("sponsors/")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # uvicorn has no WhiteNoise wrapper (that lives in wsgi.py) — serve statics
    # in dev so the ASGI process can run the whole app on one port.
    urlpatterns += staticfiles_urlpatterns()
