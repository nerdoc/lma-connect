"""On-the-fly QR code generation — as SVG (scales losslessly) or PNG.

URL scheme:
    /qr/<path>.svg   → path relative to the site root, e.g. /qr/program/<slug>/.svg
    /qr/<path>.png   → PNG variant
    /qr/?u=<url>     → free-form (e.g. external) URL, urlencoded

/qr/print/ renders a printable card sheet for a list of existing
tokens/sessions/polls — one card per item, sized for A4.
"""

from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _

from lma_connect.plugins.abstracts.models import Abstract
from lma_connect.plugins.access.models import AccessToken
from lma_connect.plugins.access.permissions import organizer_required
from lma_connect.plugins.core.models import Event
from lma_connect.plugins.program.models import LivePoll, Session
from lma_connect.plugins.sponsors.models import Sponsor

from .services import abs_url, qr_png_response, qr_svg_response


@organizer_required
def image(request, path: str):
    """QR code for a relative path. ?fmt=svg|png selects the format (default png).

    Organizer staff only (staff/admin or the operations team). Attendees scan
    the finished codes (e.g. the login token on their badge) and create their
    own account that way — they never need this endpoint.
    """
    fmt = request.GET.get("fmt", "png").lower()
    target = abs_url(request, path)
    if fmt == "svg":
        return qr_svg_response(target)
    return qr_png_response(target)


@organizer_required
def free(request):
    """QR code for a free-form URL via ?u=. Organizer staff only (see `image`)."""
    raw = request.GET.get("u", "").strip()
    if not raw:
        return HttpResponseBadRequest(_("Missing ?u=<url> parameter"))
    fmt = request.GET.get("fmt", "png").lower()
    if fmt == "svg":
        return qr_svg_response(raw)
    return qr_png_response(raw)


@organizer_required
def print_sheet(request):
    """Printable QR card sheet. Organizer staff only (staff/admin/ops).

    Query param `kind`: tokens | sessions | polls | booths | posters
    (default: tokens). Optional `event=<slug>` filter.

    `booths`/`posters` point at the expo check-in URLs (/expo/s|p/<slug>/)
    rather than the plain detail pages, so scanning them also awards points.
    """
    kind = request.GET.get("kind", "tokens")
    event_slug = request.GET.get("event")

    event = None
    if event_slug:
        event = Event.objects.filter(slug=event_slug).first()

    category = request.GET.get("category")

    items = []
    if kind == "tokens":
        qs = AccessToken.objects.filter(is_active=True).select_related("event", "user")
        if event:
            qs = qs.filter(event=event)
        if category:
            qs = qs.filter(category=category)
        for t in qs.order_by("category", "-created_at")[:200]:
            items.append({
                "title": t.label or _("Access token"),
                "subtitle": t.user.first_name if t.user else _("(not redeemed yet)"),
                "url": abs_url(request, t.get_redeem_url()),
                "code": t.token,
                "group": t.get_category_display(),
            })
    elif kind == "sessions":
        qs = Session.objects.filter(is_published=True).select_related("event", "track")
        if event:
            qs = qs.filter(event=event)
        for s in qs.order_by("starts_at")[:200]:
            items.append({
                "title": s.title,
                "subtitle": f"{s.starts_at:%a %d.%m %H:%M} · {s.room.name if s.room else ''}",
                "url": abs_url(request, reverse("program:detail", args=[s.slug])),
                "code": s.slug,
            })
    elif kind == "polls":
        qs = LivePoll.objects.filter(is_active=True).select_related("session")
        if event:
            qs = qs.filter(session__event=event)
        for p in qs.order_by("-created_at")[:200]:
            items.append({
                "title": p.question_text,
                "subtitle": f"{_('Live poll')} · {p.session.title}",
                "url": abs_url(
                    request,
                    reverse("program:detail", args=[p.session.slug]) + f"#poll-{p.id}",
                ),
                "code": str(p.id),
            })
    elif kind == "booths":
        qs = Sponsor.objects.filter(is_published=True).select_related("event", "tier")
        if event:
            qs = qs.filter(event=event)
        for sp in qs.order_by("name")[:200]:
            items.append({
                "title": sp.name,
                "subtitle": sp.booth_location or _("Expo booth"),
                "url": abs_url(request, reverse("expo:booth_stop", args=[sp.slug])),
                "code": sp.slug,
            })
    elif kind == "posters":
        # `has_poster` rather than `type`: an oral presentation can have a
        # poster on display as well, and then it needs a QR sheet too.
        qs = Abstract.objects.filter(is_published=True, has_poster=True).select_related("event")
        if event:
            qs = qs.filter(event=event)
        for ab in qs.order_by("poster_id", "title")[:200]:
            items.append({
                "title": ab.title,
                "subtitle": f"{_('Poster')} {ab.poster_id}" if ab.poster_id else _("Poster"),
                "url": abs_url(request, reverse("expo:poster_stop", args=[ab.slug])),
                "code": ab.slug,
            })

    return render(request, "qr/print.html", {
        "items": items, "kind": kind, "event": event, "category": category,
    })
