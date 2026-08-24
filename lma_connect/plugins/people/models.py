"""
people — PersonProfile (a per-event extension of the user) and Speaker (a
profile with talk subjects).

A person has at most one profile per event, and can be a speaker AND a
committee member at the same time: the roles are separate rows, not a field on
the user, because someone chairing one session and presenting in another is
the normal case at a conference, not an exception.
"""

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from lma_connect.plugins.core.models import Event, TimestampedModel


class ParticipantCategory(models.TextChoices):
    DELEGATE = "delegate", _("Delegate")
    SPEAKER = "speaker", _("Speaker")
    ORGANIZER = "organizer", _("Organizer")
    COMMITTEE = "committee", _("Committee / Reviewer")
    COMPANY = "company", _("Company / Industry")
    STAFF = "staff", _("Staff")
    PRESS = "press", _("Press")
    STUDENT = "student", _("Student")
    OTHER = "other", _("Other")


class PersonProfile(TimestampedModel):
    """One profile per user and event — bio, affiliation, photo, visibility
    flags."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="event_profiles")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="profiles")

    category = models.CharField(_("Category"), max_length=20,
                                choices=ParticipantCategory.choices,
                                default=ParticipantCategory.DELEGATE,
                                help_text=_("Type of participant — drives badge layout, "
                                            "list filters and access rules"))
    social_event_registered = models.BooleanField(
        _("Registered for social event"), default=False,
        help_text=_("Tick when the participant has booked/paid the social evening"),
    )

    bio = models.TextField(_("Bio (Markdown)"), blank=True)
    photo = models.ImageField(_("Photo"), upload_to="people/photos/", blank=True, null=True)
    affiliation = models.CharField(_("Affiliation"), max_length=200, blank=True)
    position = models.CharField(_("Position"), max_length=200, blank=True,
                                help_text=_("e.g. 'Head of Laboratory Medicine'"))
    country = models.CharField(_("Country"), max_length=120, blank=True,
                               help_text=_("Country of the affiliation, e.g. 'Austria'"))
    country_iso = models.CharField(_("ISO-3166"), max_length=2, blank=True,
                                   help_text=_("Two-letter code, e.g. 'AT' — drives the "
                                               "world map and the flag display"))
    cv = models.FileField(_("CV"), upload_to="people/cv/", blank=True, null=True,
                          help_text=_("Curriculum vitae as a PDF"))

    pronouns = models.CharField(_("Pronouns"), max_length=40, blank=True,
                                help_text=_("e.g. they/them or she/her — empty means "
                                            "nothing is shown"))

    # Social links (all opt-in)
    linkedin_url = models.URLField(_("LinkedIn"), blank=True)
    orcid = models.CharField(_("ORCID"), max_length=19, blank=True,
                             help_text=_("Format: 0000-0000-0000-0000"))
    website = models.URLField(_("Website"), blank=True)

    # Visibility — opt-in, and only ever set after an explicit consent record
    # exists (see core.ConsentRecord): showing someone's photo and CV to the
    # public is a decision only they can make.
    profile_public = models.BooleanField(_("Profile public"), default=False,
                                         help_text=_("Only set to true once the matching "
                                                     "consent has been recorded"))

    class Meta:
        verbose_name = _("Person profile")
        verbose_name_plural = _("Person profiles")
        unique_together = [("user", "event")]
        ordering = ["event", "user__last_name", "user__first_name"]

    def __str__(self) -> str:
        return f"{self.user.get_full_name() or self.user.username} ({self.event.slug})"

    def get_absolute_url(self) -> str:
        return reverse("people:detail", kwargs={"username": self.user.username})


class Speaker(TimestampedModel):
    """One-to-one with PersonProfile — the speaker-specific fields. Exists
    only for people who actually speak."""

    profile = models.OneToOneField(PersonProfile, on_delete=models.CASCADE, related_name="speaker")
    talk_subjects = models.CharField(_("Topic tags"), max_length=400, blank=True,
                                     help_text=_("Comma separated, e.g. "
                                                 "'pre-analytics, AI, haematology'"))
    affiliation = models.CharField(_("Affiliation"), max_length=300, blank=True,
                                   help_text=_("One-line affiliation/position shown on the "
                                               "session cards, e.g. 'Head of Laboratory "
                                               "Medicine, University Hospital Salzburg'"))
    intro = models.TextField(_("Speaker intro"), blank=True,
                             help_text=_("A few sentences about the speaker — shown "
                                         "publicly on the session and speaker pages"))
    chair_notes = models.TextField(_("Chair notes"), blank=True,
                                   help_text=_("Private notes for the session chair to "
                                               "introduce the speaker — never shown "
                                               "publicly, only in the chair view"))
    is_keynote = models.BooleanField(_("Keynote speaker"), default=False)

    class Meta:
        verbose_name = _("Speaker")
        verbose_name_plural = _("Speakers")
        ordering = ["-is_keynote", "profile__user__last_name"]

    def __str__(self) -> str:
        return f"Speaker — {self.profile}"
