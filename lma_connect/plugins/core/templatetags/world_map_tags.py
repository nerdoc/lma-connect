"""Template tag that renders a choropleth world map highlighting either
speaker or abstract countries. The data behind it is derived from the
database — see `core.global_stats`."""
from pathlib import Path

from django import template
from django.conf import settings

from ..global_stats import abstract_countries, speaker_countries
from ..models import Event

register = template.Library()

_SVG_PATH = Path(settings.BASE_DIR) / "lma_connect/static/core/world_map.svg"
try:
    _WORLD_SVG = _SVG_PATH.read_text(encoding="utf-8")
except FileNotFoundError:
    _WORLD_SVG = ""

# Colours reference the brand palette rendered per event (see base.html) and
# carry a literal fallback for contexts without an event.
_CONFIG = {
    "speakers": {
        "source": speaker_countries,
        "color": "var(--lma-primary, #457b9d)",
        "color_hover": "var(--lma-primary-dark, #2d5874)",
        "klass": "map-speakers",
    },
    "abstracts": {
        "source": abstract_countries,
        "color": "var(--lma-accent, #fe5f55)",
        "color_hover": "var(--lma-accent-dark, #d63f35)",
        "klass": "map-abstracts",
    },
}


@register.inclusion_tag("core/_world_map.html", takes_context=True)
def world_map(context, kind, title=""):
    """Render a world map.

    kind = "speakers" or "abstracts".
    """
    cfg = _CONFIG.get(kind)
    if cfg is None:
        return {}

    event = Event.get_active(context.get("request"))
    entries, total = cfg["source"](event)
    isos = sorted(entry["iso"] for entry in entries)
    return {
        "kind": kind,
        "title": title,
        "klass": cfg["klass"],
        "color": cfg["color"],
        "color_hover": cfg["color_hover"],
        "isos": isos,
        "entries": entries,
        "country_count": len(isos),
        "total_count": total,
        "world_svg": _WORLD_SVG,
    }
