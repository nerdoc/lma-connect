"""
core — Event, Room, Committee, Floorplan, InfoBlock, LegalPage, ConsentRecord.

Built around a single active event: `Event.get_active()` picks the newest
published one and everything else hangs off that. Several events can coexist in
the database (last year's, next year's), which is what makes an upgrade to a
real multi-tenant setup a change of that one method rather than a rewrite.
"""

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

# Revision of the icon rendering procedure — travels in the PATH of the icon
# URLs via Event.icon_version. Bump it on every change to
# core.views._render_app_icon(), otherwise devices (Safari above all) keep the
# old icon under an unchanged URL.
ICON_RENDER_REV = 4


class User(AbstractUser):
    """Custom user with academic affiliation fields shown wherever the user
    appears (committees, speakers, abstract authors, Q&A posts).

    Set as AUTH_USER_MODEL = 'lma_core.User' in settings.py from project
    inception so all FKs target this model directly.
    """

    department = models.CharField(_("Department"), max_length=200, blank=True,
                                  help_text=_("e.g. 'Department of Laboratory Medicine'"))
    institution = models.CharField(_("Institution"), max_length=200, blank=True,
                                   help_text=_("e.g. 'St Mary's University Hospital'"))
    city = models.CharField(_("City"), max_length=120, blank=True)
    country = models.CharField(_("Country"), max_length=120, blank=True)
    country_iso = models.CharField(_("ISO-3166"), max_length=2, blank=True,
                                   help_text=_("e.g. 'AT' — for flag display"))

    @property
    def affiliation_line(self) -> str:
        """One-line display: 'Department, Institution, City, Country' (omits empty parts)."""
        parts = [p for p in (self.department, self.institution, self.city, self.country) if p]
        return ", ".join(parts)


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TranslatedTextMixin:
    """Bilingual text fields without a second model: the primary field holds
    the source language, `<name><TRANSLATION_SUFFIX>` holds the translation.

    Which language is the source differs per model — event master data is
    maintained by the organizers in English (plus `_de` fields), sponsor copy
    arrives from the companies in German (plus `_en` fields). Hence the
    configurable suffix. The fallback rule ("use the translation only when the
    active language matches AND the field is filled in") lives here and
    nowhere else.

    Deliberately not a translation model with one row per language: two
    languages is what conferences of this kind need, and a field pair keeps
    the admin a single form instead of an inline.
    """

    TRANSLATION_LANGUAGE = "de"
    TRANSLATION_SUFFIX = "_de"

    def localized(self, name: str) -> str:
        from django.utils.translation import get_language
        lang = get_language() or ""
        if lang.startswith(self.TRANSLATION_LANGUAGE):
            translated = getattr(self, f"{name}{self.TRANSLATION_SUFFIX}", "") or ""
            if translated.strip():
                return translated
        return getattr(self, name, "") or ""


class Event(TranslatedTextMixin, TimestampedModel):
    """One conference / summit. Several events can exist side by side."""

    name = models.CharField(_("Name"), max_length=200)
    short_name = models.CharField(
        _("Short name"), max_length=40, blank=True,
        help_text=_("Compact name for the topbar and the home-screen icon "
                    "(e.g. 'ACME 2026'). Falls back to the full name."))
    slug = models.SlugField(_("Slug"), max_length=120, unique=True)
    subtitle = models.CharField(_("Subtitle"), max_length=300, blank=True)

    # Date & time
    start_date = models.DateField(_("Start date"))
    end_date = models.DateField(_("End date"))
    timezone_name = models.CharField(_("Time zone"), max_length=64, default="Europe/Vienna",
                                     help_text=_("IANA name, e.g. 'Europe/Vienna', "
                                                 "'America/New_York'"))

    # Location
    venue_name = models.CharField(_("Venue"), max_length=200, blank=True)
    address = models.CharField(_("Address"), max_length=300, blank=True)
    city = models.CharField(_("City"), max_length=120, blank=True)
    postal_code = models.CharField(_("Postal code"), max_length=20, blank=True)
    country = models.CharField(_("Country"), max_length=120, blank=True)
    country_iso = models.CharField(_("ISO-3166"), max_length=2, blank=True)

    # Geo (for the map, optional)
    lat = models.DecimalField(_("Latitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    lon = models.DecimalField(_("Longitude"), max_digits=9, decimal_places=6, null=True, blank=True)

    # Branding
    description = models.TextField(_("Description (Markdown)"), blank=True)
    homepage_url = models.URLField(_("Homepage"), blank=True)
    # ─── Brand palette ────────────────────────────────────────────────
    # Five colours drive the whole UI (see templates/_brand_palette.html):
    # they are mapped onto Tabler's CSS variables, so changing them here
    # re-skins buttons, badges, links, the bottom nav and the projection
    # screens at once. They used to be hard-coded in base.html, which meant
    # every conference ran in the first organizer's colours.
    HEX_VALIDATOR = RegexValidator(
        r"^#[0-9a-fA-F]{6}$",
        _("Six-digit hex colour including the leading '#' — e.g. #457b9d."),
    )

    theme_color = models.CharField(_("Primary colour"), max_length=7, default="#457b9d",
                                   validators=[HEX_VALIDATOR],
                                   help_text=_("Buttons, links, active nav item, "
                                               "browser theme colour"))
    accent_color = models.CharField(_("Accent colour"), max_length=7, default="#fe5f55",
                                    validators=[HEX_VALIDATOR],
                                    help_text=_("Attention-drawing elements — "
                                                "danger badges, live markers"))
    highlight_color = models.CharField(_("Highlight colour"), max_length=7, default="#ffcf4d",
                                       validators=[HEX_VALIDATOR],
                                       help_text=_("Warnings, awards, the marker under "
                                                   "the active bottom-nav tab"))
    surface_color = models.CharField(_("Page background"), max_length=7, default="#f2f4ff",
                                     validators=[HEX_VALIDATOR],
                                     help_text=_("Background behind the cards. Keep it "
                                                 "light — the text colour sits on it."))
    text_color = models.CharField(_("Text colour"), max_length=7, default="#3c1518",
                                  validators=[HEX_VALIDATOR],
                                  help_text=_("Body text. Check the contrast against "
                                              "the page background."))
    logo = models.ImageField(_("Event logo (header)"), upload_to="events/event_logos/",
                             blank=True, null=True,
                             help_text=_("Shown in the topbar; also the source for the "
                                         "home-screen icon"))
    banner = models.ImageField(_("Banner"), upload_to="events/banners/", blank=True, null=True)
    welcome_image = models.ImageField(_("Welcome hero image"), upload_to="events/welcome/",
                                      blank=True, null=True,
                                      help_text=_("Main image on the welcome screen"))

    organizer_name = models.CharField(_("Organizer name"), max_length=200, blank=True,
                                      help_text=_("The association, society or company "
                                                  "running the event — shown in the footer"))
    organizer_logo = models.ImageField(_("Organizer logo (footer)"),
                                       upload_to="events/organizer_logos/",
                                       blank=True, null=True,
                                       help_text=_("Shown in the footer and on the welcome screen"))
    organizer_url = models.URLField(_("Organizer URL"), blank=True)

    # Footer / compliance fields. Optional in the model so a fresh scaffold
    # runs, but expected to be filled before any public deployment: most
    # jurisdictions require an imprint and a data-protection notice (in the
    # EU: GDPR Art. 13 plus the national e-commerce act).
    footer_label = models.CharField(_("Footer 'hosted by' label"), max_length=80,
                                    default="Hosted by",
                                    help_text=_("Customisable label preceding the organizer logo"))
    copyright_holder = models.CharField(_("Copyright holder"), max_length=200, blank=True,
                                        help_text=_("Defaults to organizer name if empty"))
    copyright_year_start = models.PositiveSmallIntegerField(
        _("Copyright start year"), null=True, blank=True,
        help_text=_("Year the copyright begins; defaults to event year if empty"))
    # Legal texts: see LegalPage. Deliberately no field per document any more
    # — which pages an organizer needs (imprint, privacy policy, terms,
    # accessibility statement, house rules, code of conduct …) follows from
    # their legal form and country, not from this code.
    footer_extra_md = models.TextField(_("Extra footer text (Markdown)"), blank=True,
                                       help_text=_("Free-form line displayed below the legal links"))
    # Floorplans: see Floorplan. Deliberately no field per floor any more —
    # how many levels a building has and what they are called is something
    # only the organizer knows.

    # Primary contact — quick access, on top of the committee structure
    organizing_secretary = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events_as_secretary",
        verbose_name=_("Organizing Secretary"),
    )

    # Info tab content: see InfoBlock. Deliberately NO topic fields on the
    # event any more (there used to be travel_info / sightseeing_info /
    # general_info) — which sections a conference needs is decided by the
    # organizers in the admin.

    # Emergency number as a field rather than a hard-coded 112, because the
    # app is meant to run outside Europe too. Leaving it empty hides the tile.
    emergency_number = models.CharField(
        _("Emergency number"), max_length=30, blank=True, default="112",
        help_text=_("Shown as a quick-dial tile on the Info tab. 112 covers the EU; "
                    "use 911 (US), 000 (AU) … Leave empty to hide the tile."))

    # ─── Social event (separate evening programme) ───────────────────
    social_event_title = models.CharField(_("Social-Event title"), max_length=200, blank=True,
                                          help_text=_("e.g. 'Conference Dinner', "
                                                      "'Networking Reception'"))
    social_event_start = models.DateTimeField(_("Social-Event start"), null=True, blank=True)
    social_event_end = models.DateTimeField(_("Social-Event end"), null=True, blank=True)
    social_event_venue_name = models.CharField(_("Social-Event venue"), max_length=200, blank=True)
    social_event_address = models.CharField(_("Social-Event address"), max_length=300, blank=True)
    social_event_city = models.CharField(_("Social-Event city"), max_length=120, blank=True)
    social_event_url = models.URLField(_("Social-Event venue website"), blank=True,
                                       help_text=_("Optional — Restaurant/Bar/Location URL"))
    social_event_meeting_point = models.CharField(_("Meeting point"), max_length=200, blank=True,
                                                  help_text=_("e.g. 'Foyer of the main building'"))
    social_event_meeting_time = models.DateTimeField(_("Meeting time"), null=True, blank=True,
                                                     help_text=_("When to be at the meeting point "
                                                                 "(for a shared transfer)"))
    social_event_info = models.TextField(_("Social-Event details (Markdown)"), blank=True,
                                         help_text=_("Dress code, catering, programme, cost …"))

    is_published = models.BooleanField(_("Public"), default=False)

    # ─── Bilingual fields (German translations) ────────────────────────
    # The primary fields above are the source language (English). The _de
    # fields are optional — when empty, the helper falls back to the source.
    # The properties further down return whichever fits the user's active
    # language. See TranslatedTextMixin for the rule.
    subtitle_de = models.CharField(_("Subtitle (DE)"), max_length=300, blank=True)
    venue_name_de = models.CharField(_("Venue (DE)"), max_length=200, blank=True)
    address_de = models.CharField(_("Address (DE)"), max_length=300, blank=True)
    description_de = models.TextField(_("Description — DE (Markdown)"), blank=True)
    footer_extra_md_de = models.TextField(_("Extra footer text — DE (Markdown)"), blank=True)
    social_event_info_de = models.TextField(_("Social-Event details — DE (Markdown)"), blank=True)

    # Tab/section visibility — admin-controlled per event so the same
    # codebase serves multiple events with different feature sets.
    tab_program_enabled = models.BooleanField(_("Show Program tab"), default=True)
    tab_sponsors_enabled = models.BooleanField(_("Show Sponsors tab"), default=True)
    tab_abstracts_enabled = models.BooleanField(_("Show Abstracts tab"), default=True)
    tab_info_enabled = models.BooleanField(_("Show Info tab"), default=True)
    tab_feedback_enabled = models.BooleanField(_("Show Feedback tab"), default=True)

    class Meta:
        verbose_name = _("Event")
        verbose_name_plural = _("Events")
        ordering = ["-start_date"]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("core:event_detail", kwargs={"slug": self.slug})

    @property
    def exhibition_floorplans(self):
        """Only the levels the exhibition takes place on.

        A property rather than a slice in the template: the expo overview and
        the booth pins mean the same plans, and they mean them for a reason
        (that is where the booths are), not because they happen to come first.
        """
        return self.floorplans.filter(is_exhibition_floor=True)

    @property
    def booth_floorplan(self):
        """The reference image for the booth pins (sponsors.booth_x/booth_y).

        The pins are relative coordinates on exactly one image, hence a single
        plan and not the list: the first exhibition level.
        """
        return self.exhibition_floorplans.first()

    @property
    def logo_version(self) -> str:
        """Cache-busting token for the home-screen icons. Derived from the
        logo file's mtime — it changes when the logo does and forces
        iOS/Safari to reload. This matters because Safari caches touch icons
        extremely aggressively: a fetch that failed once survives even
        deleting the icon."""
        if not self.logo:
            return "0"
        try:
            ts = self.logo.storage.get_modified_time(self.logo.name)
            return str(int(ts.timestamp()))
        except (NotImplementedError, OSError, ValueError):
            return str(self.pk or 0)

    @property
    def icon_version(self) -> str:
        """The token that ACTUALLY appears in the icon URLs: logo version
        plus render revision.

        logo_version alone is not enough. It hangs off the logo file's mtime
        and stays the same when only the renderer's code changes — so the URL
        does too. Safari remembers per URL that an icon fetch failed and never
        retries it, so a server-side re-rendered icon under an unchanged URL
        never reaches the device. Bump ICON_RENDER_REV after every change to
        _render_app_icon()."""
        return f"{self.logo_version}r{ICON_RENDER_REV}"

    @classmethod
    def get_active(cls, request=None) -> "Event | None":
        """The active event (single-event mode): the newest published one.

        The single definition of that rule — it used to be duplicated as
        `_active_event()` in every plugin. When a `request` is passed, the
        result is cached per request (including `None`) so that the context
        processor and the view do not fire the same query twice — noticeable
        under HTMX polling.
        """
        if request is not None and hasattr(request, "_active_event_cache"):
            return request._active_event_cache
        event = cls.objects.filter(is_published=True).order_by("-start_date").first()
        if request is not None:
            request._active_event_cache = event
        return event

    # ─── Language-aware getters ─────────────────────────────────────────
    # Return the German variant when the active language is 'de' AND the _de
    # field is filled in, otherwise the source language (the primary field).
    # The rule itself lives in TranslatedTextMixin.

    @property
    def localized_subtitle(self) -> str:        return self.localized("subtitle")
    @property
    def localized_venue_name(self) -> str:      return self.localized("venue_name")
    @property
    def localized_address(self) -> str:         return self.localized("address")
    @property
    def localized_description(self) -> str:     return self.localized("description")
    @property
    def localized_footer_extra_md(self) -> str:  return self.localized("footer_extra_md")
    @property
    def localized_social_event_info(self) -> str: return self.localized("social_event_info")

    @property
    def published_legal_pages(self):
        """Legal pages for the footer bar — in the configured order.

        The single definition of that visibility rule; templates cannot filter
        and should not have to know it.
        """
        return self.legal_pages.filter(is_published=True)

    @property
    def secretary_contact(self):
        """Return the first EventContact with role='secretary' (Organizing Secretary)
        — used by the social-event CTA + contact panels. None if not configured."""
        return self.contacts.filter(role="secretary").first()

    @property
    def published_sponsor_count(self) -> int:
        """Publicly visible sponsors only — for the expo tile on the home
        page, so drafts neither leak nor inflate the count."""
        return self.sponsors.filter(is_published=True).count()

    @property
    def featured_sponsors(self):
        """Headline sponsors whose logo is placed outside the expo page — on
        the welcome screen and in the home page header.

        The single definition of that rule: flagged (`is_featured`), published
        AND carrying a logo. Without a logo there would be nothing to place,
        so such a sponsor drops out here quietly instead of showing up as a
        text placeholder. Several are allowed (equal-ranking headline
        sponsors); the templates render them side by side.
        """
        return (
            self.sponsors.filter(is_published=True, is_featured=True)
            .exclude(logo="")
            .exclude(logo__isnull=True)  # ImageField is null=True — check both
            .select_related("tier")
            .order_by("tier__order", "order", "name")
        )


class Room(TimestampedModel):
    """Hall / room / foyer area. Used for sessions AND poster locations."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(_("Name"), max_length=120)
    slug = models.SlugField(_("Slug"), max_length=120)
    capacity = models.PositiveIntegerField(_("Capacity"), null=True, blank=True)
    floor = models.CharField(_("Floor"), max_length=40, blank=True)
    notes = models.TextField(_("Notes"), blank=True)
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Room")
        verbose_name_plural = _("Rooms")
        unique_together = [("event", "slug")]
        ordering = ["event", "order", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.event.slug})"


class Committee(TimestampedModel):
    """One committee of an event — organizing, scientific, local, jury, …

    Deliberately no fixed type: there used to be four choices with a
    "one per type and event" constraint, which made two scientific committees
    or a second jury impossible and forced everyone else's committee names
    into a vocabulary that came from a single conference. How many committees
    an event has and what they are called is the organizer's decision, so the
    only structure left here is a name, a slug and an order.
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="committees")
    name = models.CharField(_("Name"), max_length=200,
                            help_text=_("e.g. 'Scientific Committee', 'Local Organizing "
                                        "Committee', 'Poster Jury'"))
    slug = models.SlugField(_("Slug"), max_length=120,
                            help_text=_("Used in URLs and anchors — e.g. 'scientific'"))
    description = models.TextField(_("Description"), blank=True)
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Committee")
        verbose_name_plural = _("Committees")
        constraints = [
            models.UniqueConstraint(fields=["event", "slug"],
                                    name="unique_committee_slug_per_event"),
        ]
        ordering = ["event", "order"]

    def __str__(self) -> str:
        return f"{self.name} — {self.event.slug}"


class CommitteeRole(models.TextChoices):
    CHAIR = "chair", _("Chair")
    CO_CHAIR = "co_chair", _("Co-Chair")
    SECRETARY = "secretary", _("Secretary")
    MEMBER = "member", _("Member")


class CommitteeMembership(TimestampedModel):
    """Through model — user ↔ committee, with a role and an order."""

    committee = models.ForeignKey(Committee, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="committee_memberships")
    role = models.CharField(_("Role"), max_length=20, choices=CommitteeRole.choices,
                            default=CommitteeRole.MEMBER)
    affiliation = models.CharField(_("Affiliation"), max_length=200, blank=True,
                                   help_text=_("Overrides the profile affiliation when set"))
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Committee membership")
        verbose_name_plural = _("Committee memberships")
        unique_together = [("committee", "user")]
        ordering = ["committee", "order", "user__last_name"]

    def __str__(self) -> str:
        return f"{self.user} ({self.get_role_display()} — {self.committee})"


class EventContactRole(models.TextChoices):
    SECRETARY = "secretary", _("Organizing Secretary")
    REGISTRATION = "registration", _("Registration")
    SPONSORING = "sponsoring", _("Sponsoring")
    ABSTRACTS = "abstracts", _("Abstracts / Scientific")
    PRESS = "press", _("Press")
    TECHNICAL = "technical", _("Technical / IT")
    OTHER = "other", _("Other")


class EventContact(TimestampedModel):
    """Generic contact entry for an event — used for Organizing Secretary,
    registration desk, press contact, etc. Multiple per role allowed."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="contacts")
    role = models.CharField(_("Role"), max_length=20, choices=EventContactRole.choices,
                            default=EventContactRole.SECRETARY)
    name = models.CharField(_("Name"), max_length=200,
                            help_text=_("Person or organization name displayed first"))
    company = models.CharField(_("Company / Organization"), max_length=200, blank=True)
    email = models.EmailField(_("Email"), blank=True)
    phone = models.CharField(_("Phone"), max_length=40, blank=True)
    website = models.URLField(_("Website"), blank=True)
    address = models.CharField(_("Address"), max_length=300, blank=True)
    notes = models.TextField(_("Notes (Markdown)"), blank=True)
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Event contact")
        verbose_name_plural = _("Event contacts")
        ordering = ["event", "order", "role"]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_role_display()} — {self.event.slug})"


class Floorplan(TranslatedTextMixin, TimestampedModel):
    """One floorplan of an event — one level, one file, one label.

    There used to be two fixed fields on the event ("ground floor" and "first
    floor"). How many levels a building has and what they are called (foyer,
    basement, hall 3 …) is something only the organizer knows — hence any
    number of plans, each with its own label and order.
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="floorplans")
    title = models.CharField(_("Floor / label"), max_length=120,
                             help_text=_("e.g. 'Ground floor', 'Hall 3', 'Foyer'"))
    file = models.FileField(_("File"), upload_to="events/floorplans/",
                            help_text=_("PDF, PNG or SVG. PDFs get an open button, "
                                        "images are shown inline."))
    order = models.PositiveSmallIntegerField(_("Order"), default=0)
    is_exhibition_floor = models.BooleanField(
        _("Exhibition floor"), default=False,
        help_text=_("Tick the level where the expo takes place. It is shown on the "
                    "Expo page, and the first ticked plan is the reference image for "
                    "the sponsor booth pins."))
    title_de = models.CharField(_("Label (DE)"), max_length=120, blank=True)

    class Meta:
        verbose_name = _("Floorplan")
        verbose_name_plural = _("Floorplans")
        ordering = ["event", "order", "id"]

    def __str__(self) -> str:
        return f"{self.title} ({self.event.slug})"

    @property
    def localized_title(self) -> str:
        return self.localized("title")

    @property
    def is_pdf(self) -> bool:
        """PDFs cannot be shown inline — the template branches on this.

        Here rather than as a template filter on the URL, so that query
        strings (signed storage URLs) cannot break the detection.
        """
        return self.file.name.lower().endswith(".pdf")


class InfoBlock(TranslatedTextMixin, TimestampedModel):
    """A freely editable section on the Info tab — WiFi, catering, emergency
    numbers, dress code, hashtag, whatever the event needs.

    Deliberately generic instead of one event field per topic: which pieces of
    information a conference needs is something the organizers know better
    than the code does. Title, icon, body and order all come from the admin;
    the template only iterates.
    """

    # Tabler icon without the 'ti-' prefix. Validated because the value goes
    # into a class attribute in the template unescaped — a space in it would
    # be a class injection.
    ICON_VALIDATOR = RegexValidator(
        r"^[a-z0-9-]+$",
        _("Only lowercase letters, digits and hyphens — e.g. 'wifi', 'tools-kitchen-2'."),
    )

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="info_blocks")
    title = models.CharField(_("Title"), max_length=200)
    icon = models.CharField(
        _("Icon"), max_length=50, blank=True, default="info-circle",
        validators=[ICON_VALIDATOR],
        help_text=_("Tabler icon name without the 'ti-' prefix — e.g. 'wifi', "
                    "'tools-kitchen-2', 'urgent'. See tabler.io/icons"))
    body = models.TextField(_("Text (Markdown)"), blank=True)
    order = models.PositiveSmallIntegerField(_("Order"), default=0)
    is_published = models.BooleanField(
        _("Published"), default=True,
        help_text=_("Uncheck to hide the block without deleting it."))

    # Translations — empty means: show the source language (English).
    title_de = models.CharField(_("Title (DE)"), max_length=200, blank=True)
    body_de = models.TextField(_("Text — DE (Markdown)"), blank=True)

    class Meta:
        verbose_name = _("Info block")
        verbose_name_plural = _("Info blocks")
        ordering = ["event", "order", "id"]

    def __str__(self) -> str:
        return f"{self.title} ({self.event.slug})"

    @property
    def localized_title(self) -> str:
        return self.localized("title")

    @property
    def localized_body(self) -> str:
        return self.localized("body")


class LegalPage(TranslatedTextMixin, TimestampedModel):
    """One legal text of an event — imprint, privacy policy, terms, whatever.

    There used to be four fixed Markdown fields on the event. Which documents
    an organizer needs follows from their legal form and their country, not
    from this code: an association needs different ones than a company, a
    public body additionally needs an accessibility statement, some events
    want house rules or a code of conduct. Hence any number of pages with
    their own slug, title and order, all from the admin.
    """

    # The slugs the app itself links to (the footer fallback and the data
    # protection paragraph on the help page). Only for those does the view
    # show a "not written yet" note instead of a 404 — a dead link coming out
    # of our own template should explain what is missing rather than send the
    # user nowhere.
    CANONICAL = {
        "imprint": _("Imprint"),
        "privacy": _("Privacy policy"),
        "terms": _("Terms of use"),
        "accessibility": _("Accessibility statement"),
    }

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="legal_pages")
    slug = models.SlugField(
        _("URL slug"), max_length=50,
        help_text=_("Address of the page: /legal/<slug>/. Use 'imprint' and "
                    "'privacy' for those two — the app links to them directly."))
    title = models.CharField(_("Title"), max_length=200)
    body = models.TextField(_("Text (Markdown)"), blank=True)
    order = models.PositiveSmallIntegerField(_("Order"), default=0)
    is_published = models.BooleanField(
        _("Published"), default=True,
        help_text=_("Uncheck to hide the page and its footer link without deleting it."))

    # Translations — empty means: show the source language (English).
    title_de = models.CharField(_("Title (DE)"), max_length=200, blank=True)
    body_de = models.TextField(_("Text — DE (Markdown)"), blank=True)

    class Meta:
        verbose_name = _("Legal page")
        verbose_name_plural = _("Legal pages")
        ordering = ["event", "order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["event", "slug"],
                                    name="unique_legal_page_slug_per_event"),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.event.slug}/{self.slug})"

    def get_absolute_url(self) -> str:
        return reverse("core:legal", kwargs={"slug": self.slug})

    @property
    def localized_title(self) -> str:
        return self.localized("title")

    @property
    def localized_body(self) -> str:
        return self.localized("body")


class ConsentType(models.TextChoices):
    NEWSLETTER = "newsletter", _("Newsletter")
    PROFILE_PUBLIC = "profile_public", _("Show profile publicly")
    PHOTO_USAGE = "photo_usage", _("Photo / video usage")
    QA_REAL_NAME = "qa_real_name", _("Post Q&A under real name instead of a pseudonym")


class ConsentRecord(TimestampedModel):
    """One consent per user + event + type. Granular and revocable, as GDPR
    Art. 7 requires: consent given for one purpose says nothing about another,
    and withdrawing it has to be as easy as giving it."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="consent_records")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="consent_records")
    type = models.CharField(_("Type"), max_length=30, choices=ConsentType.choices)
    granted_at = models.DateTimeField(_("Granted at"), null=True, blank=True)
    withdrawn_at = models.DateTimeField(_("Withdrawn at"), null=True, blank=True)
    notes = models.TextField(_("Notes"), blank=True)

    class Meta:
        verbose_name = _("Consent")
        verbose_name_plural = _("Consents")
        unique_together = [("user", "event", "type")]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} · {self.get_type_display()} · {self.event.slug}"

    @property
    def is_active(self) -> bool:
        return self.granted_at is not None and self.withdrawn_at is None
