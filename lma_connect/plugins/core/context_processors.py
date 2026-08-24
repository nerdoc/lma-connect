"""Global context-processors — the active event (for topbar/footer logos and
the welcome anchor), the current year (for copyright lines), and the app's own
provenance (author, licence, source), which every page footer renders."""

from datetime import date

from lma_connect import (
    APP_NAME,
    COPYRIGHT_HOLDER,
    COPYRIGHT_YEAR,
    LICENSE_NAME,
    LICENSE_SPDX,
    LICENSE_URL,
    SOURCE_URL,
    VERSION,
)

from .models import Event


def active_event(request):
    # Cached per request inside Event.get_active, so the same query does not
    # run again in the individual views (which call it the same way).
    return {
        "event": Event.get_active(request),
        "current_year": date.today().year,
    }


def app_meta(request):
    """Who built the app, under which licence, and where its source lives.

    Read straight from `lma_connect/__init__.py` — hard-coded, not event data.
    The footer renders it on every page, so the attribution survives any
    re-branding an organizer does in the admin, and the `/about/` link it
    carries is what satisfies AGPL §13 ("offer the source to remote users").
    """
    return {
        "app": {
            "name": APP_NAME,
            "version": VERSION,
            "copyright_holder": COPYRIGHT_HOLDER,
            "copyright_year": COPYRIGHT_YEAR,
            "license_spdx": LICENSE_SPDX,
            "license_name": LICENSE_NAME,
            "license_url": LICENSE_URL,
            "source_url": SOURCE_URL,
        }
    }
