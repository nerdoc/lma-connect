import logging
from io import BytesIO

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import get_language
from django.views.decorators.cache import cache_control, never_cache

from .models import ICON_RENDER_REV, Event, EventContactRole, LegalPage

logger = logging.getLogger(__name__)


def welcome(request):
    """Splash / welcome screen shown before entering the app proper."""
    event = Event.get_active(request)
    return render(request, "core/welcome.html", {
        "event": event,
        # The welcome screen is NOT one of the bottom-nav tabs, so active_tab
        # stays unset and no tab is highlighted.
    })


def home(request):
    event = Event.get_active(request)
    committees = []
    current_session = None
    next_session = None
    floorplans = []
    if event:
        floorplans = event.floorplans.all()
        committees = (
            event.committees.prefetch_related("memberships__user").order_by("order")
        )
        now = timezone.now()
        sessions = (
            event.sessions.filter(is_published=True)
            .select_related("track", "room")
            .prefetch_related("speakers__speaker__profile__user")
            .order_by("starts_at")
        )
        current_session = sessions.filter(
            starts_at__lte=now, ends_at__gte=now,
        ).first()
        next_session = sessions.filter(starts_at__gt=now).first()
    return render(request, "core/home.html", {
        "event": event,
        "committees": committees,
        "current_session": current_session,
        "next_session": next_session,
        "floorplans": floorplans,
        "active_tab": "home",
    })


def event_detail(request, slug):
    event = get_object_or_404(Event, slug=slug, is_published=True)
    return render(request, "core/event_detail.html", {
        "event": event,
        "active_tab": "home",
    })


def info(request):
    """Info tab — venue, floorplans, admin-managed info blocks, contacts, committees."""
    event = Event.get_active(request)
    committees = []
    info_blocks = []
    floorplans = []
    if event:
        # Prefetch members and users → no N+1 per committee/member (as home()).
        committees = (
            event.committees.prefetch_related("memberships__user").order_by("order")
        )
        info_blocks = event.info_blocks.filter(is_published=True)
        floorplans = event.floorplans.all()
    return render(request, "core/info.html", {
        "event": event, "committees": committees, "info_blocks": info_blocks,
        "floorplans": floorplans, "active_tab": "info",
    })


def about(request):
    """Provenance page — who built the app, its licence, how to reuse it.

    Deliberately free of event data: this is about the *software*, not the
    conference running on it. Everything it prints comes from the hard-coded
    constants in `lma_connect/__init__.py`, so re-branding an event in the
    admin cannot erase the attribution. It also serves as the "source offer"
    the AGPL asks for from network-deployed software (§13).
    """
    event = Event.get_active(request)
    return render(request, "core/about.html", {
        "event": event, "active_tab": "info",
    })


def help_page(request):
    """User-facing help — how to use the app (Q&A, polls, rating, token login, etc.)."""
    event = Event.get_active(request)
    # Screenshots exist per language (static/img/help/<lang>/…) so the images
    # speak the same language as the text beside them. Fallback: en.
    lang = "de" if (get_language() or "").startswith("de") else "en"
    # Who exhibitors should talk to: the sponsoring contact if one is
    # maintained, otherwise the organizing secretary. Deliberately not
    # hard-coded — both come from the admin (event → contacts). With neither
    # filled in, the template falls back to the registration desk.
    industry_contact = None
    if event:
        industry_contact = (
            event.contacts.filter(role=EventContactRole.SPONSORING).first()
            or event.secretary_contact
        )
    return render(request, "core/help.html", {
        "event": event, "active_tab": "info",
        "shots": f"img/help/{lang}/",
        "industry_contact": industry_contact,
    })


# The icon shows the bare event logo on a transparent ground — the home
# screen should show the brand, not a white tile around it. It still has to be
# square and exactly the requested size, otherwise iOS/Android distort it.
#
# EXCEPTION on iOS (``opaque=True``, see app_icon_opaque): for "Add to Home
# Screen" Safari only accepts icons WITHOUT an alpha channel — given a
# transparent PNG it shows the grey letter placeholder instead of the icon. A
# transparent app icon is therefore unreachable on iOS; there we flatten onto
# white.
_ICON_OPAQUE_BG = (255, 255, 255)
# Home-screen icon sizes: 180 = apple-touch-icon, 192/512 = manifest (Android).
_ICON_SIZES = (192, 512)
_APPLE_TOUCH_SIZE = 180


def _render_app_icon(logo_field, size: int, *, maskable: bool,
                     opaque: bool = False) -> bytes:
    """Render the event logo centred on a square canvas and return PNG bytes.

    ``maskable`` reserves the safe zone Android requires (the icon gets
    clipped to a circle/squircle), so the logo stays fully visible after
    masking. ``opaque`` flattens onto white instead of keeping the alpha
    channel — mandatory for iOS (see _ICON_OPAQUE_BG).
    """
    from PIL import Image

    with logo_field.open("rb") as fh:
        src = Image.open(fh)
        src.load()
    src = src.convert("RGBA")

    bg = (*_ICON_OPAQUE_BG, 255) if opaque else (0, 0, 0, 0)
    canvas = Image.new("RGBA", (size, size), bg)
    # maskable: place the logo within the central ~66% (the W3C spec's
    # 40%-radius safe zone plus a little margin). opaque: leave some air,
    # otherwise iOS' rounded corners nibble at the logo's outline. Otherwise
    # use the full area — without a white ground there is no frame to respect.
    if maskable:
        ratio = 0.66
    elif opaque:
        ratio = 0.90
    else:
        ratio = 1.0
    box = max(1, int(size * ratio))
    logo = src.copy()
    logo.thumbnail((box, box), Image.LANCZOS)
    offset = ((size - logo.width) // 2, (size - logo.height) // 2)
    canvas.alpha_composite(logo, offset)

    buf = BytesIO()
    # Without opaque the alpha channel is kept — there it is the point.
    (canvas.convert("RGB") if opaque else canvas).save(buf, format="PNG")
    return buf.getvalue()


@cache_control(public=True, max_age=86400)
def app_icon(request, size: int, ver: str = "", maskable: bool = False,
             opaque: bool = False):
    """Serve the active event's logo as a square home-screen icon in the
    requested size — transparent ground, opaque for iOS (``opaque``).

    ``ver`` is a cache-busting token in the path (see Event.icon_version).
    Irrelevant to the rendering itself, but part of the cache key, so that
    changing the logo is guaranteed to produce new bytes.
    """
    size = max(48, min(int(size), 1024))
    event = Event.get_active(request)
    if not (event and event.logo):
        raise Http404("No event logo configured")

    cache_key = (f"core:app_icon:{ICON_RENDER_REV}:{event.logo.name}:{ver}"
                 f":{size}:{int(bool(maskable))}:{int(bool(opaque))}")
    png = cache.get(cache_key)
    if png is None:
        try:
            png = _render_app_icon(event.logo, size, maskable=bool(maskable),
                                   opaque=bool(opaque))
        except (FileNotFoundError, OSError):
            raise Http404("Event logo is not a renderable image")
        cache.set(cache_key, png, 60 * 60 * 24)
    return HttpResponse(png, content_type="image/png")


@cache_control(public=True, max_age=3600)
def manifest(request):
    """Web app manifest — makes the app launch from the iOS/Android home
    screen like a native one (standalone, own status bar colour, the event
    logo as the app icon).

    Serves JSON built from the active event, so branding and logo follow
    automatically. Content type is application/manifest+json (W3C spec).
    """
    event = Event.get_active(request)
    name = (event.name if event else "Conference App")[:200]
    # short_name: iOS/Android recommend ≤12 characters for the home-screen
    # label. A maintained short name wins; otherwise collect whole words up to
    # the limit — a hard cut would end mid-word ("Internationa").
    if event and event.short_name:
        short = event.short_name[:12]
    else:
        short_words: list[str] = []
        for word in name.split():
            candidate = (" ".join([*short_words, word])).strip()
            if len(candidate) > 12 and short_words:
                break
            short_words.append(word)
        short = (" ".join(short_words) or name)[:12]
    theme = (event.theme_color if event and event.theme_color else "#206bc4")

    icons = []
    if event and event.logo:
        # Server-side rendered PNGs, square and correctly sized, rather than
        # the raw logo — otherwise iOS/Android show a distorted app icon. One
        # "any" and one "maskable" icon per size (Android adaptive icons).
        #
        # "any" is served OPAQUE: since iOS 16.4 Safari reads the manifest too
        # and discards icons with an alpha channel. "maskable" stays
        # transparent — that is the variant Android's launcher picks, and
        # there the bare logo is exactly what we want.
        ver = event.icon_version

        def icon_src(name: str, size: int) -> str:
            return request.build_absolute_uri(reverse(name, args=[size, ver]))

        for s in _ICON_SIZES:
            icons.append({
                "src": icon_src("core:app_icon_opaque", s),
                "sizes": f"{s}x{s}",
                "type": "image/png",
                "purpose": "any",
            })
            icons.append({
                "src": icon_src("core:app_icon_maskable", s),
                "sizes": f"{s}x{s}",
                "type": "image/png",
                "purpose": "maskable",
            })

    # Under a sub-path deployment (FORCE_SCRIPT_NAME) start_url and scope
    # have to carry the prefix, otherwise the installed PWA opens next to the
    # app instead of inside it.
    app_root = ((settings.FORCE_SCRIPT_NAME or "").rstrip("/")) + "/"
    data = {
        "name": name,
        "short_name": short,
        "description": ((event.description or name) if event else name)[:300],
        "start_url": app_root,
        "scope": app_root,
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#ffffff",
        "theme_color": theme,
        "lang": "en",
        "icons": icons,
    }
    response = JsonResponse(data)
    response["Content-Type"] = "application/manifest+json"
    return response


def legal(request, slug: str):
    """Render a legal page of the active event, as maintained in the admin.

    Unknown slugs are a 404 — with one exception: for the canonical pages
    (LegalPage.CANONICAL) that the app links to itself, a "not written yet"
    note is rendered instead. Otherwise a footer or help-page link would lead
    nowhere until someone gets round to writing the text.
    """
    event = Event.get_active(request)
    page = None
    if event:
        page = event.legal_pages.filter(slug=slug, is_published=True).first()
    if page is None and slug not in LegalPage.CANONICAL:
        raise Http404("Unknown legal page")
    return render(request, "core/legal.html", {
        "event": event,
        "page_title": page.localized_title if page else LegalPage.CANONICAL[slug],
        "content": page.localized_body if page else "",
        "slug": slug,
    })


@never_cache
def healthz(request):
    """Liveness / readiness check for external monitoring and deploy smoke
    tests.

    Deliberately thin: one `SELECT 1` against the database, nothing else. The
    endpoint may be polled every minute — it must never itself produce the
    load it is supposed to measure. No auth, because it discloses nothing;
    HTTP 503 on database trouble, so an uptime monitor raises the alarm before
    the server is down completely.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # noqa: BLE001 — any DB error means "not ready" here
        logger.exception("healthz: database unreachable")
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)

    return JsonResponse({"status": "ok", "database": "ok"})
