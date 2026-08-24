from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404, render

from lma_connect.plugins.core.models import Event

from .models import Sponsor


def sponsor_list(request):
    """Expo overview: exhibitors with a booth on top, logo-only sponsors
    below them.

    Deliberately NOT grouped or sorted by tier: every exhibitor appears as an
    equal in alphabetical order. The tier stays internal (contract, price) and
    is never surfaced to attendees.
    """
    event = Event.get_active(request)
    exhibitors: list = []
    logo_sponsors: list = []
    if event:
        published = event.sponsors.filter(is_published=True)
        # Exhibitor with a booth = booth_location is filled in.
        exhibitors = list(
            published.exclude(booth_location="").order_by(Lower("name"))
        )
        # Sponsors without a booth — logos only.
        logo_sponsors = list(
            published.filter(booth_location="").order_by(Lower("name"))
        )
    return render(request, "sponsors/list.html", {
        "event": event,
        "exhibitors": exhibitors,
        "logo_sponsors": logo_sponsors,
        "active_tab": "sponsors",
    })


def sponsor_detail(request, slug):
    event = Event.get_active(request)
    sponsor = get_object_or_404(
        Sponsor.objects.select_related("tier", "event"),
        slug=slug, is_published=True,
    )
    return render(request, "sponsors/detail.html", {
        "event": event, "sponsor": sponsor, "active_tab": "sponsors",
    })
