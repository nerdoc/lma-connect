"""Access tokens — passwordless onboarding via QR code.

Workflow:
1. The organizers generate tokens in bulk (manage.py make_tokens).
2. The token is printed on the ticket or badge as a QR code: /t/<token>/
3. The attendee scans it and lands on the nickname setup — no classic
   registration form, a single field: the display name.
4. On submit a user is created automatically (random username) and logged in
   straight away.
5. The token stays bound to that user — a later scan logs them straight in.

No email, no password, no password reset: the badge in someone's hand is the
credential. Which also means a lost badge is a lost account, so tokens can be
deactivated individually in the admin.
"""

import secrets
import string

from axes.models import AccessAttempt as AxesAccessAttempt
from axes.models import AccessFailureLog as AxesAccessFailureLog
from axes.models import AccessLog as AxesAccessLog
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from lma_connect.plugins.core.models import Event, TimestampedModel
from lma_connect.plugins.people.models import ParticipantCategory


def _gen_token(length: int = 16) -> str:
    """URL-safe random token. 16 chars alphanum = ~95 bits of entropy."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class AccessToken(TimestampedModel):
    """A reusable login token belonging to one person.

    `user` starts out NULL — it is created on first redemption and bound to
    the token permanently after that.
    """

    token = models.CharField(_("Token"), max_length=32, unique=True, default=_gen_token,
                             help_text=_("This is what the QR code encodes"))
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="access_tokens")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name="access_tokens",
                             help_text=_("Created on first redemption"))
    label = models.CharField(_("Label (internal)"), max_length=200, blank=True,
                             help_text=_("For the organizers, e.g. 'speaker slot 12' "
                                         "or 'spare'"))
    category = models.CharField(_("Group / Category"), max_length=20,
                                choices=ParticipantCategory.choices,
                                default=ParticipantCategory.DELEGATE,
                                help_text=_("Participant group this QR batch belongs to "
                                            "(Delegate, Speaker, Industry …) — assigned to "
                                            "the attendee's profile on first redemption"))
    is_active = models.BooleanField(_("Active"), default=True,
                                    help_text=_("Deactivate to stop the token from being "
                                                "redeemed — use this for a lost badge"))
    redeemed_at = models.DateTimeField(_("Redeemed at"), null=True, blank=True)
    last_seen_at = models.DateTimeField(_("Last seen"), null=True, blank=True)
    notes = models.TextField(_("Notes (internal)"), blank=True)

    class Meta:
        verbose_name = _("Access token")
        verbose_name_plural = _("Access tokens")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.token[:8]}… ({self.event.slug})"

    def get_redeem_url(self) -> str:
        return reverse("access:redeem", kwargs={"token": self.token})


# ─── django-axes under "Access" instead of its own admin block ──────────────
#
# Otherwise axes registers its three models under an app called "AXES" — a
# second box on the admin index covering the same subject as this plugin: who
# gets in. Proxy models (no table of their own, no database effect) move them
# under this plugin and give them readable names along the way. They are
# registered in access/admin.py; the original registration is switched off
# with AXES_ENABLE_ADMIN = False.

class LoginAttempt(AxesAccessAttempt):
    class Meta:
        proxy = True
        verbose_name = _("Failed login attempt")
        verbose_name_plural = _("Failed login attempts")


class LoginFailureLog(AxesAccessFailureLog):
    class Meta:
        proxy = True
        verbose_name = _("Login failure log")
        verbose_name_plural = _("Login failure log")


class LoginLog(AxesAccessLog):
    class Meta:
        proxy = True
        verbose_name = _("Login log")
        verbose_name_plural = _("Login log")
