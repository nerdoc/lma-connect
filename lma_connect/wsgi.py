"""
WSGI config for the LMA Connect project.

Wraps the Django app with WhiteNoise using an explicit static_prefix so
that sub-path deployments with FORCE_SCRIPT_NAME work correctly:

    Browser   GET /conf/static/foo.css
    Proxy     strips /conf (Uberspace web backend with --remove-prefix)
              → PATH_INFO = /static/foo.css arrives at gunicorn
    WhiteNoise (prefix="/static/") matches and serves the file
    Django   STATIC_URL = "/conf/static/" is only used for URL generation
             in templates, never for routing here.

If FORCE_SCRIPT_NAME is not set (e.g. local dev), STATIC_URL is "/static/"
and the static_prefix matches anyway.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lma_connect.settings")

application = get_wsgi_application()

# Wrap with WhiteNoise — explicit static_prefix avoids the FORCE_SCRIPT_NAME
# vs. STATIC_URL prefix mismatch when deployed behind a reverse-proxy that
# already stripped the script prefix.
try:
    from django.conf import settings
    from whitenoise import WhiteNoise

    # autorefresh=True does a stat() per request. It is what makes admin
    # uploads (event logo, hero image, speaker photos) visible without a
    # service restart. Negligible overhead at the scale this app targets, and
    # static files have content-hashed filenames, so browser caching still
    # works.
    application = WhiteNoise(
        application,
        root=str(settings.STATIC_ROOT),
        prefix="/static/",
        max_age=60 * 60 * 24 * 365,  # 1 year — content-hashed
        autorefresh=True,
    )
    application.add_files(
        str(settings.MEDIA_ROOT),
        prefix="/media/",
    )
except ImportError:
    pass
