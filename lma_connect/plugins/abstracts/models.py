"""
abstracts — structured scientific submissions: title, category, poster ID and
location, ordered authors (with affiliation and a presenting flag), body text,
references, committee reviews and the audience star vote.
"""

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from lma_connect.plugins.core.models import Event, TimestampedModel


class AbstractCategory(TimestampedModel):
    """Topic category for abstracts. Defined freely per event."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="abstract_categories")
    name = models.CharField(_("Name"), max_length=120)
    slug = models.SlugField(_("Slug"), max_length=120)
    color = models.CharField(_("Colour"), max_length=7, default="#206bc4")
    description = models.TextField(_("Description"), blank=True)
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Abstract category")
        verbose_name_plural = _("Abstract categories")
        unique_together = [("event", "slug")]
        ordering = ["event", "order", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.event.slug})"


class AbstractTag(TimestampedModel):
    """Cross-cutting tag for abstracts (e.g. AI/ML, quality control,
    resource-limited settings).

    Unlike Category (the main topic, a single FK) tags are many-to-many — an
    abstract can carry several. Defined freely per event.
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="abstract_tags")
    name = models.CharField(_("Name"), max_length=80)
    slug = models.SlugField(_("Slug"), max_length=80)
    color = models.CharField(_("Colour"), max_length=7, default="#6c757d")

    class Meta:
        verbose_name = _("Abstract tag")
        verbose_name_plural = _("Abstract tags")
        unique_together = [("event", "slug")]
        ordering = ["event", "name"]

    def __str__(self) -> str:
        return self.name


class AbstractType(models.TextChoices):
    POSTER = "poster", _("Poster")
    ORAL = "oral", _("Oral communication")
    KEYNOTE = "keynote", _("Keynote")


class AbstractStatus(models.TextChoices):
    SUBMITTED = "submitted", _("Submitted")
    UNDER_REVIEW = "review", _("Under review")
    ACCEPTED = "accepted", _("Accepted")
    REJECTED = "rejected", _("Rejected")
    WITHDRAWN = "withdrawn", _("Withdrawn")


class AbstractAward(TimestampedModel):
    """A prize an event hands out for an abstract — Best Poster, Innovation
    Award, Jury Special Mention, whatever the jury decided on.

    Used to be a fixed list of six choices in the code. Which prizes exist is
    a decision of each conference's jury, though, and it changes from year to
    year — so awards are maintained per event in the admin instead.
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="abstract_awards")
    name = models.CharField(_("Name"), max_length=120,
                            help_text=_("e.g. 'Best Poster', 'Young Investigator Award'"))
    slug = models.SlugField(_("Slug"), max_length=120)
    order = models.PositiveSmallIntegerField(_("Order"), default=0)
    is_audience_choice = models.BooleanField(
        _("Audience choice"), default=False,
        help_text=_("Tick the one award decided by the attendees' star votes. "
                    "The operations dashboard hands it out with one click, and "
                    "only one abstract per event can hold it."))

    class Meta:
        verbose_name = _("Abstract award")
        verbose_name_plural = _("Abstract awards")
        ordering = ["event", "order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["event", "slug"],
                                    name="unique_abstract_award_slug_per_event"),
            # At most one audience-choice award per event: the ops view hands
            # "the" audience award out, so a second one would make that
            # ambiguous. Partial constraint — plenty of jury awards may exist.
            models.UniqueConstraint(fields=["event"], condition=models.Q(is_audience_choice=True),
                                    name="unique_audience_choice_award_per_event"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.event.slug})"


class Abstract(TimestampedModel):
    """A scientific abstract — poster or talk."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="abstracts")
    category = models.ForeignKey(AbstractCategory, on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name="abstracts")

    type = models.CharField(_("Type"), max_length=20, choices=AbstractType.choices,
                            default=AbstractType.POSTER)

    # The poster ID is the public identifier, e.g. P-042 or O-15.
    poster_id = models.CharField(_("Poster / talk ID"), max_length=20, blank=True,
                                 help_text=_("e.g. P-042 for poster no. 42, "
                                             "O-15 for oral no. 15"))
    location = models.CharField(_("Location"), max_length=200, blank=True,
                                help_text=_("Where the poster hangs — e.g. Foyer A, wall 5"))

    title = models.CharField(_("Title"), max_length=400)
    slug = models.SlugField(_("Slug"), max_length=240)

    abstract_text = models.TextField(_("Abstract text (Markdown)"),
                                     help_text=_("Main body — typically 250–300 words"))
    keywords = models.CharField(_("Keywords"), max_length=400, blank=True,
                                help_text=_("Comma separated"))
    peer_review = models.TextField(
        _("PEER pre-review (Markdown)"), blank=True,
        help_text=_("AI-generated pre-review for committee members — "
                    "shown on the review page as a helper / second opinion. "
                    "Markdown supported."),
    )
    tags = models.ManyToManyField(AbstractTag, blank=True, related_name="abstracts",
                                  verbose_name=_("Tags"))

    submitted_at = models.DateTimeField(_("Submitted at"), null=True, blank=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name="submitted_abstracts")

    status = models.CharField(_("Status"), max_length=20, choices=AbstractStatus.choices,
                              default=AbstractStatus.SUBMITTED)
    decision_notes = models.TextField(_("Decision notes (internal)"), blank=True)

    # Award — handed out by the jury. SET_NULL rather than CASCADE: deleting
    # an award from the list must not delete the abstract that won it.
    award = models.ForeignKey(AbstractAward, on_delete=models.SET_NULL,
                              null=True, blank=True, related_name="abstracts",
                              verbose_name=_("Award"),
                              help_text=_("When set, the abstract is marked as a winner"))
    award_note = models.CharField(_("Award rationale (optional)"), max_length=300, blank=True,
                                  help_text=_("Short text, e.g. 'Highest impact factor in study design'"))
    award_at = models.DateField(_("Award date"), null=True, blank=True)

    is_published = models.BooleanField(_("Publicly visible"), default=False)

    # Deliberately separate from `type`: an oral communication can have a
    # poster on display as well. `type` stays the formal kind of submission,
    # `has_poster` says whether a physical poster (with a QR code) hangs
    # somewhere — only those get a QR sheet and can be star-voted on.
    has_poster = models.BooleanField(
        _("Poster on display"), default=False,
        help_text=_("A poster with a QR code hangs for this abstract — also "
                    "possible for talks that additionally show a poster"))

    class Meta:
        verbose_name = _("Abstract")
        verbose_name_plural = _("Abstracts")
        unique_together = [("event", "slug")]
        ordering = ["event", "type", "poster_id", "title"]
        indexes = [
            models.Index(fields=["event", "status"]),
            models.Index(fields=["event", "category"]),
        ]

    def __str__(self) -> str:
        return f"[{self.poster_id or '?'}] {self.title[:80]}"

    def get_absolute_url(self) -> str:
        return reverse("abstracts:detail", kwargs={"slug": self.slug})


class AbstractAuthor(TimestampedModel):
    """Through model — abstract ↔ author (order plus a presenting flag).

    Authors may be linked to a user (for speakers with an account) or exist as
    plain text only (for external co-authors without one).
    """

    abstract = models.ForeignKey(Abstract, on_delete=models.CASCADE, related_name="authors")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name="abstract_authorships",
                             help_text=_("Optional — when the author has an account"))

    full_name = models.CharField(_("Full name"), max_length=200,
                                 help_text=_("Plain text — an account is not required"))
    email = models.EmailField(_("Email"), blank=True)
    affiliation = models.CharField(_("Affiliation"), max_length=300, blank=True)
    orcid = models.CharField(_("ORCID"), max_length=19, blank=True)

    # Country of the affiliation. Kept on the author row rather than read from
    # the linked user, because most co-authors are external and have no
    # account at all. It is what feeds the "where our abstracts come from"
    # map; when left blank, the linked user's country is used as a fallback.
    country = models.CharField(_("Country"), max_length=120, blank=True,
                               help_text=_("Country of the affiliation, e.g. 'Austria'"))
    country_iso = models.CharField(_("ISO-3166"), max_length=2, blank=True,
                                   help_text=_("Two-letter code, e.g. 'AT' — drives the "
                                               "world map and the flag display"))

    is_presenting = models.BooleanField(_("Presenting author"), default=False)
    is_corresponding = models.BooleanField(_("Corresponding author"), default=False)
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Abstract author")
        verbose_name_plural = _("Abstract authors")
        ordering = ["abstract", "order"]

    def __str__(self) -> str:
        marker = "*" if self.is_presenting else ""
        return f"{self.full_name}{marker}"


class AbstractReview(TimestampedModel):
    """A committee member's review of an abstract.

    The existence of the row *is* the assignment: score=NULL means still open,
    a set score means done. The scale runs from 1 (excellent) to 6
    (unsuitable), following the German school-grade convention — low is good.
    """

    SCORE_CHOICES = [
        (1, _("1 — excellent")),
        (2, _("2 — very good")),
        (3, _("3 — good")),
        (4, _("4 — borderline")),
        (5, _("5 — weak")),
        (6, _("6 — unsuitable")),
    ]

    abstract = models.ForeignKey(Abstract, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name="abstract_reviews")
    score = models.PositiveSmallIntegerField(_("Score 1–6"), choices=SCORE_CHOICES,
                                             null=True, blank=True)
    comment = models.TextField(_("Comment (optional)"), blank=True)
    submitted_at = models.DateTimeField(_("Submitted at"), null=True, blank=True,
                                        help_text=_("Set when a score is submitted "
                                                    "for the first time"))

    class Meta:
        verbose_name = _("Abstract review")
        verbose_name_plural = _("Abstract reviews")
        unique_together = [("abstract", "reviewer")]
        ordering = ["abstract", "reviewer"]
        indexes = [
            models.Index(fields=["reviewer", "score"]),
        ]

    def __str__(self) -> str:
        s = self.score if self.score is not None else "—"
        return f"{self.reviewer} → {self.abstract.poster_id or self.abstract.title[:40]}: {s}"

    @property
    def is_done(self) -> bool:
        return self.score is not None


# Star budget per attendee and event. Deliberately a constant and not an
# event field: the number is printed in the programme and on the posters, so
# it must not change while a conference is running.
STARS_PER_USER = 3


class AbstractStarVote(TimestampedModel):
    """An attendee's vote for the audience award — final.

    The existence of the row *is* the vote: there is no `stars` field, because
    everyone gives at most one star per abstract. STARS_PER_USER stars are
    available per event in total.

    Deliberately immutable — the app offers neither changing nor taking a vote
    back, which is why the QR stop asks for a confirmation before saving.
    """

    abstract = models.ForeignKey(Abstract, on_delete=models.CASCADE,
                                 related_name="star_votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="abstract_star_votes")

    class Meta:
        verbose_name = _("Audience star")
        verbose_name_plural = _("Audience stars")
        unique_together = [("abstract", "user")]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "abstract"]),
        ]

    def __str__(self) -> str:
        return f"★ {self.user} → {self.abstract.poster_id or self.abstract.slug}"


class AbstractReference(models.Model):
    """A cited reference — kept as its own row so an export (BibTeX/CSL) can
    be added later without touching the abstract text.

    One free-text citation per row is enough for now; splitting it into
    authors/title/journal/year can follow when something actually consumes it.
    """

    abstract = models.ForeignKey(Abstract, on_delete=models.CASCADE, related_name="references")
    order = models.PositiveSmallIntegerField(_("Number"), default=0)
    citation_text = models.TextField(_("Citation"),
                                     help_text=_("Full citation, e.g. "
                                                 "Smith J et al. Nature 2024;612:45-53"))
    doi = models.CharField(_("DOI"), max_length=120, blank=True)
    url = models.URLField(_("URL"), blank=True)

    class Meta:
        ordering = ["abstract", "order"]

    def __str__(self) -> str:
        return f"[{self.order}] {self.citation_text[:60]}"
