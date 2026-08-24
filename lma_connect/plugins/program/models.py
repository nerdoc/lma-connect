"""
program — Track, Session, Speaker-Assignment, Live-Q&A, Session-Rating, Live-Poll.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from lma_connect.plugins.core.models import Event, Room, TimestampedModel
from lma_connect.plugins.people.models import Speaker


class Track(TimestampedModel):
    """A thematic grouping of sessions. Optional — smaller events do without."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="tracks")
    name = models.CharField(_("Name"), max_length=120)
    slug = models.SlugField(_("Slug"), max_length=120)
    color = models.CharField(_("Colour"), max_length=7, default="#206bc4",
                             help_text=_("Hex including the '#' — accent on the session cards"))
    description = models.TextField(_("Description"), blank=True)
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Track")
        verbose_name_plural = _("Tracks")
        unique_together = [("event", "slug")]
        ordering = ["event", "order", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.event.slug})"


class SessionType(models.TextChoices):
    KEYNOTE = "keynote", _("Keynote")
    TALK = "talk", _("Oral communication")
    PANEL = "panel", _("Panel discussion")
    WORKSHOP = "workshop", _("Workshop")
    SYMPOSIUM = "symposium", _("Symposium")
    BREAK = "break", _("Break / Catering")
    POSTER = "poster", _("Poster session")


class ScreenSource(models.TextChoices):
    """What the chair is currently projecting onto the room screen."""
    STANDBY = "standby", _("Standby")
    QA = "qa", _("Q&A")
    POLL = "poll", _("Umfrage-Ergebnisse")


class Session(TimestampedModel):
    """A slot in the programme. starts_at < ends_at."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="sessions")
    track = models.ForeignKey(Track, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="sessions")
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="sessions")

    title = models.CharField(_("Title"), max_length=300)
    slug = models.SlugField(_("Slug"), max_length=200)
    summary = models.TextField(_("Summary (Markdown)"), blank=True)
    type = models.CharField(_("Type"), max_length=20, choices=SessionType.choices,
                            default=SessionType.TALK)

    starts_at = models.DateTimeField(_("Starts at"))
    ends_at = models.DateTimeField(_("Ends at"))

    qa_enabled = models.BooleanField(_("Live Q&A enabled"), default=True,
                                     help_text=_("Attendees may submit questions during the session"))
    qa_moderated = models.BooleanField(_("Q&A pre-moderated"), default=False,
                                       help_text=_("Off (default): questions appear immediately, everyone "
                                                   "can up-vote, and the chair stars the ones to be asked. "
                                                   "On: questions stay hidden until the chair approves them "
                                                   "— use for sensitive sessions."))
    rating_enabled = models.BooleanField(_("Rating enabled"), default=True)

    is_published = models.BooleanField(_("Published"), default=False)

    # Room screen: the chair switches the projected source at runtime.
    screen_source = models.CharField(
        _("Screen source"), max_length=10,
        choices=ScreenSource.choices, default=ScreenSource.STANDBY)
    screen_poll = models.ForeignKey(
        "LivePoll", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", verbose_name=_("Projected poll"))

    class Meta:
        verbose_name = _("Session")
        verbose_name_plural = _("Sessions")
        unique_together = [("event", "slug")]
        ordering = ["starts_at", "track"]
        indexes = [
            models.Index(fields=["event", "starts_at"]),
            models.Index(fields=["track", "starts_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.event.slug})"


class SessionRoleType(models.TextChoices):
    CHAIR = "chair", _("Chair")
    SPEAKER = "speaker", _("Speaker")
    CO_AUTHOR = "co_author", _("Co-author")
    DISCUSSANT = "discussant", _("Discussant")


class SessionSpeaker(TimestampedModel):
    """Through model — session ↔ speaker, with a role and an order."""

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="speakers")
    speaker = models.ForeignKey(Speaker, on_delete=models.CASCADE, related_name="session_assignments")
    role = models.CharField(_("Role"), max_length=20, choices=SessionRoleType.choices,
                            default=SessionRoleType.SPEAKER)
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Session-Speaker")
        verbose_name_plural = _("Session-Speakers")
        unique_together = [("session", "speaker", "role")]
        ordering = ["session", "order"]

    def __str__(self) -> str:
        return f"{self.speaker} — {self.get_role_display()} at {self.session}"


# ─── Session chairs ───────────────────────────────────

class SessionChair(TimestampedModel):
    """A user assigned to chair a session. Grants Q&A-moderation rights for
    *this* session only (no global permission needed). Shown as "Chair" on
    the session detail page.
    """

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="chairs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="chaired_sessions")
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Session chair")
        verbose_name_plural = _("Session chairs")
        unique_together = [("session", "user")]
        ordering = ["session", "order"]

    def __str__(self) -> str:
        return f"{self.user} chairs {self.session}"


# ─── Live-Q&A ─────────────────────────────────────────

class Question(TimestampedModel):
    """Live question for the panel discussion. Posted by signed-in users, or
    prepared by the session chair (added_by_chair)."""

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="questions")
    asker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                              null=True, blank=True, related_name="asked_questions")
    asker_display_name = models.CharField(_("Display name"), max_length=80, blank=True,
                                          help_text=_("Pseudonym — empty when posting under "
                                                      "the real name"))
    text = models.TextField(_("Question"), max_length=2000)

    is_approved = models.BooleanField(_("Approved"), default=False,
                                      help_text=_("Required in moderated sessions; "
                                                  "set automatically otherwise"))
    is_answered = models.BooleanField(_("Answered"), default=False)
    answered_at = models.DateTimeField(_("Answered at"), null=True, blank=True)
    flagged_count = models.PositiveSmallIntegerField(_("Times flagged"), default=0)

    # Chair moderation
    is_starred = models.BooleanField(_("Starred by chair"), default=False,
                                     help_text=_("Chair marked this to actually be asked"))
    starred_at = models.DateTimeField(_("Starred at"), null=True, blank=True)
    added_by_chair = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name="prepared_questions",
                                       help_text=_("Set when the chair prepared this question themselves"))

    class Meta:
        verbose_name = _("Live Q&A question")
        verbose_name_plural = _("Live Q&A questions")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["session", "is_approved"])]

    def __str__(self) -> str:
        snippet = self.text[:60]
        return f"Q: {snippet}…" if len(self.text) > 60 else f"Q: {snippet}"


class QuestionUpvote(models.Model):
    """A user up-voted a question. Once per user and question."""

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="upvotes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="question_upvotes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("question", "user")]


# ─── Session rating ─────────────────────────────────────

class SessionRating(TimestampedModel):
    """Four-dimensional rating per session and user: slides, clarity of the
    English, practical relevance, overall."""

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="ratings")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="session_ratings")
    rating_slides = models.PositiveSmallIntegerField(
        _("Slides"), null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)])
    rating_clarity = models.PositiveSmallIntegerField(
        _("Clarity (English)"), null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)])
    rating_relevance = models.PositiveSmallIntegerField(
        _("Practical relevance"), null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)])
    rating_overall = models.PositiveSmallIntegerField(
        _("Overall"), null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(_("Comment (Markdown, optional)"), blank=True)
    is_anonymous = models.BooleanField(_("Show anonymously"), default=True,
                                       help_text=_("Protects the raw responses; the "
                                                   "aggregate stays visible"))

    class Meta:
        verbose_name = _("Session rating")
        verbose_name_plural = _("Session ratings")
        unique_together = [("session", "user")]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        v = self.rating_overall or "—"
        return f"{v}★ — {self.session}"


# ─── Live-Polling ───────────────────────────────────────

class LivePollType(models.TextChoices):
    SINGLE_CHOICE = "single", _("Single choice")
    MULTI_CHOICE = "multi", _("Multi choice")
    OPEN_TEXT = "open", _("Open text")


class LivePoll(TimestampedModel):
    """A live poll attached to a session. The speaker or chair starts it at
    runtime."""

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="polls")
    question_text = models.CharField(_("Question"), max_length=400)
    type = models.CharField(_("Type"), max_length=20, choices=LivePollType.choices,
                            default=LivePollType.SINGLE_CHOICE)
    opens_at = models.DateTimeField(_("Opens at"), null=True, blank=True,
                                    help_text=_("Empty = activated by hand"))
    closes_at = models.DateTimeField(_("Closes at"), null=True, blank=True)
    is_active = models.BooleanField(_("Active"), default=False)
    is_results_public = models.BooleanField(
        _("Show results in the app"), default=False,
        help_text=_("Off = attendees only vote and see no results on their own "
                    "device; the chair projects the outcome from the projection "
                    "view. Switch on to release the results into the app as well."))

    class Meta:
        verbose_name = _("Live poll")
        verbose_name_plural = _("Live polls")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Poll: {self.question_text[:60]}"


class LivePollOption(models.Model):
    poll = models.ForeignKey(LivePoll, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(_("Answer"), max_length=200)
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    class Meta:
        ordering = ["poll", "order"]

    def __str__(self) -> str:
        return self.text


class LivePollResponse(TimestampedModel):
    """One user's answer. Multi-choice produces several rows, one per option."""

    poll = models.ForeignKey(LivePoll, on_delete=models.CASCADE, related_name="responses")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="poll_responses")
    option = models.ForeignKey(LivePollOption, on_delete=models.CASCADE,
                               null=True, blank=True, related_name="responses")
    text_answer = models.TextField(_("Free-text answer"), blank=True)

    class Meta:
        verbose_name = _("Live poll response")
        verbose_name_plural = _("Live poll responses")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["poll", "user", "option"],
                                    name="uniq_poll_user_option"),
        ]
