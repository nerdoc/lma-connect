"""Helpers for rendering the per-event brand palette into CSS.

Tabler expects some of its colours twice: once as a colour value
(`--tblr-primary`) and once as a bare RGB triple (`--tblr-primary-rgb`), which
it uses to build `rgba(...)` shades. CSS cannot take a hex string apart, so the
triple has to be produced server-side — that is what `hex_to_rgb` is for.

`brand_color` is the single place that knows which event field backs which
role, and what to fall back to when no event is configured. Templates ask for
a role, never for a field name and never for a literal.
"""
from django import template

register = template.Library()

# Used whenever a field holds something that is not a #rrggbb value. Cannot
# happen through the admin (the model validates the format), but a fixture or
# a direct DB write can still get it wrong, and a broken CSS variable would
# take the whole page's colours down with it.
_FALLBACK = "0, 0, 0"

# role → (event field, fallback). The fallbacks are the palette this app
# shipped with; they apply on a fresh install with no event yet, and they are
# the ONE place a brand colour may be written as a literal.
_ROLES = {
    "primary":   ("theme_color", "#457b9d"),
    "accent":    ("accent_color", "#fe5f55"),
    "highlight": ("highlight_color", "#ffcf4d"),
    "surface":   ("surface_color", "#f2f4ff"),
    "ink":       ("text_color", "#3c1518"),
}


@register.simple_tag
def brand_color(event, role: str) -> str:
    """The event's colour for `role`, or the shipped default.

    Used both by templates/_brand_palette.html and by the few places that
    need a real hex value rather than a CSS variable — an SVG `stop-color`,
    for instance, where custom properties are not reliably resolved.
    """
    field, fallback = _ROLES.get(role, (None, "#000000"))
    value = getattr(event, field, "") if (event and field) else ""
    return value or fallback


def _channels(value: str) -> list[int] | None:
    raw = (value or "").strip().lstrip("#")
    if len(raw) != 6:
        return None
    try:
        return [int(raw[i:i + 2], 16) for i in (0, 2, 4)]
    except ValueError:
        return None


@register.filter
def hex_to_rgb(value: str) -> str:
    """`"#457b9d"` → `"69, 123, 157"` — the triple Tabler's *-rgb vars want."""
    rgb = _channels(value)
    return ", ".join(str(c) for c in rgb) if rgb else _FALLBACK


@register.filter
def shade(value: str, percent) -> str:
    """Darken (negative) or lighten (positive) a hex colour by `percent`.

    `"#457b9d"|shade:"-20"` → a hex colour 20 % of the way towards black.

    Computed here rather than with the CSS `color-mix()` function, which
    Safari only learned in 16.2 — an attendee on an older phone would get an
    invalid value, and an invalid custom property takes the whole declaration
    with it. A hex string works in every browser that has ever rendered this
    app.
    """
    rgb = _channels(value)
    try:
        pct = float(percent)
    except (TypeError, ValueError):
        return value
    if rgb is None:
        return value
    target = 255 if pct > 0 else 0
    weight = min(abs(pct), 100) / 100
    mixed = (round(c + (target - c) * weight) for c in rgb)
    return "#" + "".join(f"{max(0, min(255, c)):02x}" for c in mixed)
