"""
sponsors — tiers (gold/silver/bronze), sponsors with their own detail page,
their contacts, images, downloads and links.

Logo uploads go through the organizers only; there is no self-service upload
form, because accepting arbitrary SVGs from third parties means accepting XXE
and stored XSS.

Bilingual: sponsors supply their copy in the language they operate in — for
the conference this was written for, German. So unlike the event models, the
primary field here holds German and `<name>_en` the translation. Templates
never touch the fields directly, only `localized_*` (the rule lives in
core.models.TranslatedTextMixin). Swap TRANSLATION_LANGUAGE / _SUFFIX below if
your sponsors write in a different language.
"""

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from lma_connect.plugins.core.models import (
    Event,
    TimestampedModel,
    TranslatedTextMixin,
)


class EnglishTranslationMixin(TranslatedTextMixin):
    """Source language German, translation in `<name>_en`."""

    TRANSLATION_LANGUAGE = "en"
    TRANSLATION_SUFFIX = "_en"


class SponsorTier(TimestampedModel):
    """A sponsoring tier of an event (e.g. platinum/gold/silver/bronze)."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="sponsor_tiers")
    name = models.CharField(_("Name"), max_length=80)
    slug = models.SlugField(_("Slug"), max_length=80)
    color = models.CharField(_("Colour"), max_length=7, default="#f59e0b",
                             help_text=_("Hex including the '#' — e.g. gold = #f59e0b"))
    perks_md = models.TextField(_("Package contents (Markdown)"), blank=True,
                                help_text=_("What the package includes"))
    price = models.DecimalField(_("Price"), max_digits=10, decimal_places=2,
                                null=True, blank=True)
    slot_count = models.PositiveSmallIntegerField(_("Number of slots"), default=0,
                                                  help_text=_("0 = unlimited"))
    order = models.PositiveSmallIntegerField(_("Order"), default=0,
                                             help_text=_("0 = topmost"))

    class Meta:
        verbose_name = _("Sponsor tier")
        verbose_name_plural = _("Sponsor tiers")
        unique_together = [("event", "slug")]
        ordering = ["event", "order", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.event.slug})"


class Sponsor(EnglishTranslationMixin, TimestampedModel):
    """A sponsor with its own public detail page at /sponsors/<slug>/."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="sponsors")
    tier = models.ForeignKey(SponsorTier, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="sponsors")

    name = models.CharField(_("Name"), max_length=200)
    slug = models.SlugField(_("Slug"), max_length=120)
    logo = models.ImageField(_("Logo"), upload_to="sponsors/logos/", blank=True, null=True,
                             help_text=_("Uploaded by the organizers only — see the "
                                         "module docstring on why there is no "
                                         "self-service form"))
    banner = models.ImageField(_("Banner"), upload_to="sponsors/banners/", blank=True, null=True)

    bio_short = models.CharField(_("Short bio"), max_length=300, blank=True,
                                 help_text=_("One-sentence pitch for the sponsor list"))
    bio_short_en = models.CharField(_("Short bio (EN)"), max_length=300, blank=True,
                                    help_text=_("Leave empty and the source text is "
                                                "shown in English too"))
    bio_long = models.TextField(_("Full bio (Markdown)"), blank=True)
    bio_long_en = models.TextField(_("Full bio — EN (Markdown)"), blank=True)

    website = models.URLField(_("Website"), blank=True)
    contact_email = models.EmailField(_("Contact email"), blank=True)
    contact_person = models.CharField(_("Contact person"), max_length=200, blank=True)

    booth_location = models.CharField(_("Booth location"), max_length=200, blank=True,
                                      help_text=_("e.g. 'Foyer A — booth B12'"))
    booth_location_en = models.CharField(_("Booth location (EN)"), max_length=200, blank=True,
                                         help_text=_("e.g. 'Foyer A — booth B12'"))
    # Marker on the floorplan — normalised coordinates 0..1 (fraction of the
    # image's width/height). NULL means no marker, text location only.
    booth_x = models.DecimalField(_("Floorplan X"), max_digits=5, decimal_places=4,
                                  null=True, blank=True,
                                  help_text=_("0.0 = left edge, 1.0 = right edge"))
    booth_y = models.DecimalField(_("Floorplan Y"), max_digits=5, decimal_places=4,
                                  null=True, blank=True,
                                  help_text=_("0.0 = top edge, 1.0 = bottom edge"))

    highlights_md = models.TextField(_("Highlights (Markdown)"), blank=True,
                                     help_text=_("Bullet points on products and news — "
                                                 "given prominence on the detail page"))
    highlights_md_en = models.TextField(_("Highlights — EN (Markdown)"), blank=True)

    contract_signed_at = models.DateField(_("Contract signed"), null=True, blank=True)
    paid_at = models.DateField(_("Paid"), null=True, blank=True)
    notes_internal = models.TextField(_("Internal notes"), blank=True,
                                      help_text=_("Never shown publicly"))

    is_published = models.BooleanField(_("Show publicly"), default=False)
    # Headline placement outside the expo page. Deliberately its own flag
    # rather than "tier == platinum": which tier gets prominent placement is a
    # contractual question that changes from event to event, and tier names
    # are free text, so they make a poor switch.
    is_featured = models.BooleanField(
        _("Headline sponsor (home page)"), default=False,
        help_text=_("The logo appears on the welcome screen and in the home page "
                    "header. Only takes effect when 'Show publicly' is set and a "
                    "logo is uploaded."))
    order = models.PositiveSmallIntegerField(_("Order within the tier"), default=0)

    class Meta:
        verbose_name = _("Sponsor")
        verbose_name_plural = _("Sponsors")
        unique_together = [("event", "slug")]
        ordering = ["event", "tier__order", "order", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.event.slug})"

    def get_absolute_url(self) -> str:
        return reverse("sponsors:detail", kwargs={"slug": self.slug})

    # Whether a sponsor counts as an exhibitor still hangs off the source
    # language's booth_location — a booth filled in only in the translation
    # would be an editing mistake and should not produce a half-translated
    # exhibitor list.
    @property
    def localized_bio_short(self) -> str:      return self.localized("bio_short")
    @property
    def localized_bio_long(self) -> str:       return self.localized("bio_long")
    @property
    def localized_highlights_md(self) -> str:  return self.localized("highlights_md")
    @property
    def localized_booth_location(self) -> str: return self.localized("booth_location")

    @property
    def is_exhibitor(self) -> bool:
        """Exhibitor with a booth — the same criterion sponsor_list() uses.

        Logo-only sponsors have no location, and therefore get no floorplan on
        their detail page either.
        """
        return bool(self.booth_location)

    @property
    def has_booth_marker(self) -> bool:
        """Whether the booth can be marked on the floorplan.

        Checked against None explicitly: 0.0 is a valid coordinate (the left
        resp. top edge) and must not count as "not filled in".
        """
        return self.booth_x is not None and self.booth_y is not None


class SponsorImage(EnglishTranslationMixin, TimestampedModel):
    """A carousel image on the sponsor detail page."""

    sponsor = models.ForeignKey(Sponsor, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(_("Image"), upload_to="sponsors/images/")
    caption = models.CharField(_("Caption"), max_length=200, blank=True)
    caption_en = models.CharField(_("Caption (EN)"), max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Sponsor image")
        verbose_name_plural = _("Sponsor images")
        ordering = ["sponsor", "order"]

    def __str__(self) -> str:
        return f"{self.sponsor.name} #{self.order}"

    @property
    def localized_caption(self) -> str: return self.localized("caption")


class SponsorContact(EnglishTranslationMixin, TimestampedModel):
    """A named contact at a sponsor. Several are allowed — unlike the single
    sponsor.contact_* fields, which stay the generic fallback."""

    sponsor = models.ForeignKey(Sponsor, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(_("Name"), max_length=200)
    role = models.CharField(_("Role"), max_length=200, blank=True,
                            help_text=_("e.g. 'Regional Sales Manager'"))
    role_en = models.CharField(_("Role (EN)"), max_length=200, blank=True)
    expertise = models.CharField(_("Field of expertise"), max_length=300, blank=True,
                                 help_text=_("e.g. 'Haematology, point-of-care testing'"))
    expertise_en = models.CharField(_("Field of expertise (EN)"), max_length=300, blank=True)
    email = models.EmailField(_("Email"), blank=True)
    phone = models.CharField(_("Phone"), max_length=40, blank=True)
    linkedin_url = models.URLField(_("LinkedIn"), blank=True)
    photo = models.ImageField(_("Photo"), upload_to="sponsors/contacts/", blank=True, null=True)
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Sponsor contact")
        verbose_name_plural = _("Sponsor contacts")
        ordering = ["sponsor", "order", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.sponsor.name})"

    @property
    def localized_role(self) -> str:      return self.localized("role")
    @property
    def localized_expertise(self) -> str: return self.localized("expertise")


class SponsorDownload(EnglishTranslationMixin, TimestampedModel):
    """File the sponsor sent us for attendees to download (whitepaper,
    datasheet, brochure, slides). Admin uploads on behalf of the sponsor —
    sponsors do not have direct upload access (no public form)."""

    DOWNLOAD_TYPES = [
        ("whitepaper", _("Whitepaper / Study")),
        ("datasheet", _("Datasheet")),
        ("brochure", _("Brochure")),
        ("presentation", _("Presentation / Slides")),
        ("manual", _("Manual / User guide")),
        ("other", _("Other")),
    ]

    sponsor = models.ForeignKey(Sponsor, on_delete=models.CASCADE, related_name="downloads")
    title = models.CharField(_("Title"), max_length=200)
    title_en = models.CharField(_("Title (EN)"), max_length=200, blank=True)
    description = models.CharField(_("Short description"), max_length=300, blank=True)
    description_en = models.CharField(_("Short description (EN)"), max_length=300, blank=True)
    file = models.FileField(_("File"), upload_to="sponsors/downloads/")
    type = models.CharField(_("Type"), max_length=20, choices=DOWNLOAD_TYPES, default="other")
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Sponsor download")
        verbose_name_plural = _("Sponsor downloads")
        ordering = ["sponsor", "order"]

    def __str__(self) -> str:
        return f"{self.title} ({self.sponsor.name})"

    @property
    def file_extension(self) -> str:
        name = self.file.name if self.file else ""
        return name.rsplit(".", 1)[-1].lower() if "." in name else ""

    @property
    def localized_title(self) -> str:       return self.localized("title")
    @property
    def localized_description(self) -> str: return self.localized("description")


class SponsorLink(EnglishTranslationMixin, models.Model):
    """Free-form external links — products, news, videos. Only shown when present."""

    LINK_TYPES = [
        ("product", _("Product")),
        ("news", _("News")),
        ("whitepaper", _("Whitepaper / Study")),
        ("video", _("Video")),
        ("other", _("Other")),
    ]

    sponsor = models.ForeignKey(Sponsor, on_delete=models.CASCADE, related_name="links")
    label = models.CharField(_("Label"), max_length=200)
    label_en = models.CharField(_("Label (EN)"), max_length=200, blank=True)
    url = models.URLField(_("URL"))
    type = models.CharField(_("Type"), max_length=20, choices=LINK_TYPES, default="other")
    description = models.CharField(_("Short description"), max_length=300, blank=True)
    description_en = models.CharField(_("Short description (EN)"), max_length=300, blank=True)
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    class Meta:
        ordering = ["sponsor", "order"]

    def __str__(self) -> str:
        return f"{self.label} ({self.sponsor.name})"

    @property
    def localized_label(self) -> str:       return self.localized("label")
    @property
    def localized_description(self) -> str: return self.localized("description")
