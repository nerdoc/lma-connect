"""
feedback — the post-event survey.

A generic question model with five types:
- yes_no        — "Was there enough time for networking?"
- likert_5      — 1 = too little, 5 = too much (for "too long / too short" …)
- open_text     — "What went well, what did not?"
- single_choice — one option out of several
- multi_choice  — "Which topics interest you most?" (several)

Responses can be stored anonymously (user is nullable). Each user fills in a
given survey once.

Texts are bilingual: English is the source (the organizers maintain the
survey, like the event master data), German lives in the `_de` twin fields
and is used when the visitor's language is German — see TranslatedTextMixin.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from lma_connect.plugins.core.models import Event, TimestampedModel, TranslatedTextMixin


class EventSurvey(TranslatedTextMixin, TimestampedModel):
    """One survey per event — typically the post-event feedback."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="surveys")
    title = models.CharField(_("Title"), max_length=200,
                             help_text=_("e.g. 'Your feedback on the conference'"))
    slug = models.SlugField(_("Slug"), max_length=120)
    intro_text = models.TextField(_("Introduction (Markdown)"), blank=True)
    title_de = models.CharField(_("Title (DE)"), max_length=200, blank=True,
                                help_text=_("Leave empty and the English text is shown "
                                            "to German-speaking visitors too"))
    intro_text_de = models.TextField(_("Introduction — DE (Markdown)"), blank=True)
    opens_at = models.DateTimeField(_("Opens at"), null=True, blank=True)
    closes_at = models.DateTimeField(_("Closes at"), null=True, blank=True)
    is_published = models.BooleanField(_("Active"), default=False)
    allow_anonymous = models.BooleanField(_("Allow anonymous responses"), default=True,
                                          help_text=_("When off: login required and answers "
                                                      "are attributed to the user"))

    class Meta:
        verbose_name = _("Event survey")
        verbose_name_plural = _("Event surveys")
        unique_together = [("event", "slug")]
        ordering = ["event", "-created_at"]

    def __str__(self) -> str:
        return f"{self.title} ({self.event.slug})"

    @property
    def localized_title(self) -> str:
        return self.localized("title")

    @property
    def localized_intro_text(self) -> str:
        return self.localized("intro_text")


class QuestionType(models.TextChoices):
    YES_NO = "yes_no", _("Yes / No")
    LIKERT_5 = "likert_5", _("Likert scale 1–5")
    OPEN_TEXT = "open_text", _("Open text")
    MULTI_CHOICE = "multi_choice", _("Multiple choice")
    SINGLE_CHOICE = "single_choice", _("Single choice")


class SurveyQuestion(TranslatedTextMixin, TimestampedModel):
    """One question in a survey. Sequence via `order`."""

    survey = models.ForeignKey(EventSurvey, on_delete=models.CASCADE, related_name="questions")
    text = models.CharField(_("Question"), max_length=400)
    help_text = models.CharField(_("Help text"), max_length=300, blank=True,
                                 help_text=_("Optional — e.g. what the scale means"))
    type = models.CharField(_("Type"), max_length=20, choices=QuestionType.choices)
    is_required = models.BooleanField(_("Required"), default=False)
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    # Labels for the ends of the Likert scale (only relevant for likert_5)
    likert_min_label = models.CharField(_("Likert label (min)"), max_length=40, blank=True,
                                        help_text=_("e.g. 'too short'"))
    likert_max_label = models.CharField(_("Likert label (max)"), max_length=40, blank=True,
                                        help_text=_("e.g. 'too long'"))

    # German twins — empty means "fall back to the English text"
    text_de = models.CharField(_("Question (DE)"), max_length=400, blank=True)
    help_text_de = models.CharField(_("Help text (DE)"), max_length=300, blank=True)
    likert_min_label_de = models.CharField(_("Likert label (min, DE)"), max_length=40, blank=True)
    likert_max_label_de = models.CharField(_("Likert label (max, DE)"), max_length=40, blank=True)

    class Meta:
        verbose_name = _("Survey question")
        verbose_name_plural = _("Survey questions")
        ordering = ["survey", "order"]

    def __str__(self) -> str:
        return f"{self.order}. {self.text[:80]}"

    @property
    def localized_text(self) -> str:
        return self.localized("text")

    @property
    def localized_help_text(self) -> str:
        return self.localized("help_text")

    @property
    def localized_likert_min_label(self) -> str:
        return self.localized("likert_min_label")

    @property
    def localized_likert_max_label(self) -> str:
        return self.localized("likert_max_label")


class SurveyChoice(TranslatedTextMixin, models.Model):
    """An answer option (for single_choice / multi_choice). Leave empty for
    yes_no, likert and open text questions."""

    question = models.ForeignKey(SurveyQuestion, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(_("Text"), max_length=200)
    text_de = models.CharField(_("Text (DE)"), max_length=200, blank=True)
    value = models.CharField(_("Value"), max_length=80, blank=True,
                             help_text=_("Optional internal value; defaults to the text"))
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    class Meta:
        ordering = ["question", "order"]

    def __str__(self) -> str:
        return self.text

    @property
    def localized_text(self) -> str:
        return self.localized("text")


class SurveyResponse(TimestampedModel):
    """One complete set of answers from a user (or anonymous)."""

    survey = models.ForeignKey(EventSurvey, on_delete=models.CASCADE, related_name="responses")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name="survey_responses",
                             help_text=_("NULL = anonymous (when allow_anonymous is on)"))
    submitted_at = models.DateTimeField(_("Submitted at"), null=True, blank=True)

    class Meta:
        verbose_name = _("Survey response")
        verbose_name_plural = _("Survey responses")
        ordering = ["-created_at"]
        # When a user is set: one response per user and survey.
        constraints = [
            models.UniqueConstraint(
                fields=["survey", "user"],
                condition=models.Q(user__isnull=False),
                name="uniq_survey_user_response",
            ),
        ]

    def __str__(self) -> str:
        who = self.user.username if self.user else "anonymous"
        return f"{self.survey.slug} · {who}"


class SurveyAnswer(models.Model):
    """A single answer to one question. Multi-choice produces several rows,
    one per selected choice."""

    response = models.ForeignKey(SurveyResponse, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(SurveyQuestion, on_delete=models.CASCADE, related_name="answers")

    # Generic value fields — whichever fits the question type is filled in.
    value_bool = models.BooleanField(_("Yes/No value"), null=True, blank=True)
    value_int = models.PositiveSmallIntegerField(
        _("Likert value"), null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    value_text = models.TextField(_("Free-text value"), blank=True)
    choice = models.ForeignKey(SurveyChoice, on_delete=models.SET_NULL,
                               null=True, blank=True, related_name="answers")

    class Meta:
        ordering = ["response", "question__order"]
        # single_choice / likert / yes_no / open_text: one answer per
        # question. multi_choice: one per selected choice.
        constraints = [
            models.UniqueConstraint(
                fields=["response", "question", "choice"],
                name="uniq_response_question_choice",
            ),
        ]
