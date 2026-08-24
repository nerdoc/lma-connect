"""Expo — gamification at booths and posters.

Two ways to engage, both starting with a QR scan (check-in):

  • Booth (sponsor):   scan → check-in points → multiple-choice question.
                       A correct answer earns bonus points. The answer is on
                       display at the booth or has to be asked for, which is
                       what makes it real engagement rather than a tap.
  • Poster (abstract): scan → check-in points → one audience star.
                       Scales without editorial work: no question to write.

The plain "was there" / "took part" bookkeeping lives entirely in the
gamification ScoreEntry table (via dedup_key); only the content sits here, the
quiz questions. The poster stars themselves are AbstractStarVote rows in the
abstracts plugin — they belong to the abstract's life cycle (the audience
award), not to the expo mechanics.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from lma_connect.plugins.abstracts.models import Abstract
from lma_connect.plugins.core.models import TimestampedModel
from lma_connect.plugins.sponsors.models import Sponsor


class BoothQuiz(TimestampedModel):
    """One multiple-choice question per sponsor booth.

    Without an active quiz the booth stays a plain check-in (scan points only).
    """

    sponsor = models.OneToOneField(Sponsor, on_delete=models.CASCADE,
                                   related_name="quiz")
    question = models.CharField(_("Question"), max_length=300,
                                help_text=_("The answer should be findable at the booth, "
                                            "or something staff can be asked about"))
    hint = models.CharField(_("Hint (optional)"), max_length=200, blank=True,
                            help_text=_("e.g. 'Ask the booth staff' or 'see the roll-up'"))
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Booth quiz")
        verbose_name_plural = _("Booth quizzes")

    def __str__(self) -> str:
        return f"Quiz: {self.sponsor.name}"

    @property
    def correct_choice(self):
        return self.choices.filter(is_correct=True).first()


class BoothChoice(models.Model):
    """One answer option of a booth quiz question."""

    quiz = models.ForeignKey(BoothQuiz, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(_("Answer text"), max_length=200)
    is_correct = models.BooleanField(_("Correct"), default=False)
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Answer option")
        verbose_name_plural = _("Answer options")
        ordering = ["order", "id"]

    def __str__(self) -> str:
        mark = " ✓" if self.is_correct else ""
        return f"{self.text}{mark}"


class PosterRating(TimestampedModel):
    """DEPRECATED — the former 1–5 star rating of a poster.

    Superseded by the audience vote (abstracts.AbstractStarVote): one final
    star instead of a score that can be changed at will. The model only stays
    around so previously collected ratings remain readable — the app no longer
    writes anything here.
    """

    abstract = models.ForeignKey(Abstract, on_delete=models.CASCADE,
                                 related_name="poster_ratings")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="poster_ratings")
    stars = models.PositiveSmallIntegerField(
        _("Stars"), validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(_("Comment (optional)"), blank=True)

    class Meta:
        verbose_name = _("Poster rating")
        verbose_name_plural = _("Poster ratings")
        unique_together = [("abstract", "user")]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.stars}★ — {self.abstract.poster_id or self.abstract.slug}"
