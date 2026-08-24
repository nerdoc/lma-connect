"""Gamification — points + achievements on top of existing user actions.

Token users are full Django users, so every Q&A post / up-vote / poll vote /
session rating / survey submission is already user-bound. This layer just:
  1. logs a ScoreEntry whenever such an action happens (via signals)
  2. checks achievement rules after each entry and awards Achievements

Nothing here requires extra forms or taps from the attendee — points just
accrue. They can see their score + badges on /me/ and the leaderboard.
"""

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _

from lma_connect.plugins.core.models import Event, TimestampedModel


class ScoreAction(models.TextChoices):
    QUESTION_ASKED = "question_asked", _("Asked a question")
    QUESTION_UPVOTED = "question_upvoted", _("Up-voted a question")
    POLL_VOTED = "poll_voted", _("Voted in a live poll")
    SESSION_RATED = "session_rated", _("Rated a session")
    SURVEY_SUBMITTED = "survey_submitted", _("Submitted the feedback survey")
    BOOTH_CHECKIN = "booth_checkin", _("Checked in at an exhibitor booth")
    BOOTH_QUIZ = "booth_quiz", _("Answered a booth quiz correctly")
    POSTER_CHECKIN = "poster_checkin", _("Checked in at a poster")
    # Historical: the former 1–5 star poster rating. No longer awarded
    # (superseded by ABSTRACT_STARRED), but kept as a choice so that
    # ScoreEntry rows booked back then stay readable.
    POSTER_RATED = "poster_rated", _("Rated a poster")
    ABSTRACT_STARRED = "abstract_starred", _("Gave a star to an abstract")


# Points awarded per action.
ACTION_POINTS = {
    ScoreAction.QUESTION_ASKED: 10,
    ScoreAction.QUESTION_UPVOTED: 1,
    ScoreAction.POLL_VOTED: 5,
    ScoreAction.SESSION_RATED: 5,
    ScoreAction.SURVEY_SUBMITTED: 25,
    ScoreAction.BOOTH_CHECKIN: 5,
    ScoreAction.BOOTH_QUIZ: 15,
    ScoreAction.POSTER_CHECKIN: 5,
    ScoreAction.POSTER_RATED: 10,
    # Deliberately worth more than a check-in: a star is scarce (three per
    # event) and requires a decision, not just walking past.
    ScoreAction.ABSTRACT_STARRED: 15,
}


class ScoreEntry(TimestampedModel):
    """One row per points-earning action. Aggregate with Sum('points')."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="score_entries")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="score_entries")
    action = models.CharField(_("Action"), max_length=30, choices=ScoreAction.choices)
    points = models.PositiveSmallIntegerField(_("Points"))
    # Optional dedup key — e.g. "poll:42" so a re-vote on the same poll
    # doesn't grant points twice. NULL = no dedup.
    dedup_key = models.CharField(_("Dedup key"), max_length=100, blank=True, db_index=True)

    class Meta:
        verbose_name = _("Score entry")
        verbose_name_plural = _("Score entries")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "event"])]

    def __str__(self) -> str:
        return f"{self.user} +{self.points} ({self.get_action_display()})"

    @classmethod
    def total_for(cls, user, event) -> int:
        return cls.objects.filter(user=user, event=event).aggregate(t=Sum("points"))["t"] or 0


class Achievement(models.Model):
    """A badge definition. Seeded via management command / fixture.

    The award condition is keyed by `key` and evaluated in services.ACHIEVEMENT_RULES.
    """

    key = models.SlugField(_("Key"), max_length=50, unique=True,
                           help_text=_("Must match a rule in services.ACHIEVEMENT_RULES"))
    name = models.CharField(_("Name"), max_length=120)
    description = models.CharField(_("Description"), max_length=300)
    icon_class = models.CharField(_("Tabler icon class"), max_length=60, default="ti-award",
                                  help_text=_("e.g. 'ti-trophy', 'ti-message-circle'"))
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return self.name


class UserAchievement(TimestampedModel):
    """A badge a user has earned at an event. One row per (user, event, achievement)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="achievements")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="user_achievements")
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name="awarded_to")
    awarded_at = models.DateTimeField(_("Awarded at"), auto_now_add=True)

    class Meta:
        verbose_name = _("User achievement")
        verbose_name_plural = _("User achievements")
        unique_together = [("user", "event", "achievement")]
        ordering = ["-awarded_at"]

    def __str__(self) -> str:
        return f"{self.user} — {self.achievement.name}"
