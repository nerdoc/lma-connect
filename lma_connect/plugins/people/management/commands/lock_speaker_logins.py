"""Take the login away from speaker accounts, without touching their data.

Why this command exists
───────────────────────
A speaker's name lives on the *user* row (`first_name` / `last_name`), and
`Speaker → PersonProfile → User` is a CASCADE chain. Deleting a speaker's user
account therefore does not just remove a login — it silently takes the whole
speaker with it: bio, affiliation, photo, CV, ORCID, talk subjects, the
session assignments and the public speaker page. That is a data loss, not a
permission change.

So when speakers should not be able to sign in, the answer is not to delete
their accounts but to make those accounts unusable for signing in:

* the password is set to Django's "unusable" marker — no password login,
* every access token bound to them is deactivated and unbound — no QR login.

Everything the app *displays* keeps working, because none of it depends on the
account being able to authenticate.

Who is skipped
──────────────
Speaking is a role, not a rank: the same person can chair a session, review
abstracts or run the operations desk. Anyone holding such a role needs their
login, so this command leaves them alone and reports them. Staff and
superusers are never touched either.

Usage
─────
    python manage.py lock_speaker_logins              # dry run — shows the plan
    python manage.py lock_speaker_logins --apply      # actually locks them
    python manage.py lock_speaker_logins --apply --event <event-slug>
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from lma_connect.plugins.access.models import AccessToken
from lma_connect.plugins.access.permissions import OPS_GROUP_NAME
from lma_connect.plugins.people.models import Speaker


def can_sign_in_with_password(user) -> bool:
    """Whether this account could actually authenticate with a password.

    Not the same as Django's `has_usable_password()`: that one only checks for
    the "!" prefix, so an account whose password field was never set — an
    empty string, which is what bulk-created accounts end up with — counts as
    usable there while no password on earth validates against it. For a report
    that people act on, the honest question is "could this account sign in",
    and an empty hash cannot.
    """
    return bool(user.password) and not user.password.startswith("!")


class Command(BaseCommand):
    help = "Remove password and token logins from speaker accounts (keeps all their data)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Actually lock the accounts. Without it the command only reports.",
        )
        parser.add_argument(
            "--event", default=None,
            help="Limit to the speakers of one event (slug). Default: all events.",
        )

    def handle(self, *args, apply, event, **opts):
        User = get_user_model()

        speakers = Speaker.objects.select_related("profile__user")
        if event:
            speakers = speakers.filter(profile__event__slug=event)

        user_ids = {s.profile.user_id for s in speakers}
        if not user_ids:
            self.stdout.write(self.style.WARNING("No speakers found — nothing to do."))
            return

        # Roles that need a working login. Reviewers are identified by an
        # existing review assignment, chairs by a SessionChair row — the same
        # primitives the permission layer itself checks.
        privileged = set(
            User.objects.filter(pk__in=user_ids)
            .filter(
                Q(is_staff=True)
                | Q(is_superuser=True)
                | Q(groups__name=OPS_GROUP_NAME)
                | Q(chaired_sessions__isnull=False)
                | Q(abstract_reviews__isnull=False)
            )
            .values_list("pk", flat=True)
        )

        targets = User.objects.filter(pk__in=user_ids - privileged).order_by("username")
        tokens = AccessToken.objects.filter(user__in=targets)

        # Report first — this is the part that runs in a dry run too.
        self.stdout.write(f"Speakers found:              {len(user_ids)}")
        self.stdout.write(f"  skipped (chair/reviewer/ops/staff): {len(privileged)}")
        self.stdout.write(f"  to lock:                   {targets.count()}")
        self.stdout.write(f"  access tokens to release:  {tokens.count()}")

        with_password = [u.username for u in targets if can_sign_in_with_password(u)]
        self.stdout.write(
            f"  of those, able to sign in with a password today: {len(with_password)}"
            + (f" — {', '.join(with_password)}" if with_password else "")
        )

        if privileged:
            names = User.objects.filter(pk__in=privileged).values_list("username", flat=True)
            self.stdout.write(self.style.WARNING(
                "  keeping their login: " + ", ".join(sorted(names))
            ))

        if not apply:
            self.stdout.write(self.style.WARNING(
                "\nDry run — nothing changed. Re-run with --apply to lock these accounts."
            ))
            return

        with transaction.atomic():
            locked = 0
            for user in targets:
                user.set_unusable_password()
                user.save(update_fields=["password"])
                locked += 1
            # Unbind as well as deactivate: a token that stays bound would log
            # its holder straight back in if it were ever reactivated.
            released = tokens.update(is_active=False, user=None)

        self.stdout.write(self.style.SUCCESS(
            f"\nLocked {locked} speaker account(s); released {released} access token(s). "
            "Their names, affiliations and speaker pages are untouched."
        ))
