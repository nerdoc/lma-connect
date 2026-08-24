"""Country statistics for the world-map cards — derived from the database.

Two maps exist: where the speakers come from (program list) and where the
abstracts come from (abstract list). Both used to be hand-maintained Python
dicts filled with the names and institutions of one specific conference, which
meant every other conference running this code saw that conference's people.
They are now derived from data the organizer maintains anyway:

* speakers  → `PersonProfile.country_iso` of everyone assigned to a *published*
              session of the event
* abstracts → `AbstractAuthor.country_iso` of every *published* abstract,
              falling back to the linked user's country when the author row
              leaves it blank (external co-authors often have no account)

Country *names* come from the same rows (the free-text `country` field next to
the ISO code), so no country table has to be shipped, maintained or
translated. The flag is computed from the ISO-3166-1 alpha-2 code: regional
indicator symbols are a fixed offset in the code points, which makes a lookup
table dead weight.

Publishing is the editorial "accepted" signal, so submissions still under
review or rejected never reach a map.
"""
from __future__ import annotations

# Offset from ASCII 'A' to REGIONAL INDICATOR SYMBOL LETTER A (U+1F1E6).
_REGIONAL_INDICATOR_OFFSET = 0x1F1E6 - ord("A")


def flag_emoji(iso: str) -> str:
    """`"AT"` → 🇦🇹. Returns "" for anything that is not a two-letter code."""
    code = (iso or "").strip().upper()
    if len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(ord(char) + _REGIONAL_INDICATOR_OFFSET) for char in code)


def summarize(rows) -> list[dict]:
    """Group `(iso, country_name, label)` triples into per-country entries.

    Sorted by descending number of entries, so the busiest countries lead the
    pill list. Rows without an ISO code drop out — they cannot be placed on
    the map, and a pill without a country would say nothing.

    The display name is the first non-empty `country_name` seen for that ISO
    code; if every row leaves it blank, the ISO code itself is shown.
    """
    grouped: dict[str, dict] = {}
    for iso, country_name, label in rows:
        code = (iso or "").strip().upper()
        if len(code) != 2 or not code.isalpha():
            continue
        bucket = grouped.setdefault(code, {"name": "", "labels": []})
        if not bucket["name"] and country_name:
            bucket["name"] = country_name.strip()
        if label and label not in bucket["labels"]:
            bucket["labels"].append(label)

    return [
        {
            "iso": iso,
            "name": data["name"] or iso,
            "flag": flag_emoji(iso),
            "count": len(data["labels"]),
            "entries": data["labels"],
        }
        for iso, data in sorted(grouped.items(), key=lambda kv: (-len(kv[1]["labels"]), kv[0]))
    ]


def speaker_countries(event) -> tuple[list[dict], int]:
    """Countries of the speakers of `event` plus the total speaker count.

    "Speaker" here means: assigned to a published session. A speaker profile
    that exists but is not on the program yet would otherwise show up on the
    public map before the program is announced.
    """
    from lma_connect.plugins.people.models import Speaker

    if event is None:
        return [], 0

    speakers = (
        Speaker.objects
        .filter(profile__event=event, session_assignments__session__is_published=True)
        .select_related("profile", "profile__user")
        .distinct()
    )

    rows = []
    total = 0
    for speaker in speakers:
        total += 1
        profile = speaker.profile
        name = profile.user.get_full_name() or profile.user.username
        affiliation = profile.affiliation or profile.user.institution
        label = f"{name} ({affiliation})" if affiliation else name
        rows.append((profile.country_iso, profile.country, label))
    return summarize(rows), total


def abstract_countries(event) -> tuple[list[dict], int]:
    """Countries of the published abstracts of `event` plus their total count.

    One abstract can contribute several countries — a collaboration between
    two institutions abroad is exactly the thing this map is supposed to show.
    Per abstract each country is counted once, no matter how many of its
    authors sit there.
    """
    from lma_connect.plugins.abstracts.models import Abstract

    if event is None:
        return [], 0

    abstracts = (
        Abstract.objects
        .filter(event=event, is_published=True)
        .prefetch_related("authors__user")
    )

    rows = []
    total = 0
    for abstract in abstracts:
        total += 1
        seen: set[str] = set()
        for author in abstract.authors.all():
            iso = author.country_iso or (author.user.country_iso if author.user else "")
            name = author.country or (author.user.country if author.user else "")
            code = (iso or "").strip().upper()
            if not code or code in seen:
                continue
            seen.add(code)
            rows.append((code, name, abstract.title))
    return summarize(rows), total
