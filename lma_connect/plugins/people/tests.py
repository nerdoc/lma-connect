from datetime import date
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from lma_connect.plugins.abstracts.models import Abstract, AbstractReview
from lma_connect.plugins.access.models import AccessToken
from lma_connect.plugins.access.permissions import OPS_GROUP_NAME
from lma_connect.plugins.core.models import Event
from lma_connect.plugins.people.models import PersonProfile, Speaker
from lma_connect.plugins.program.models import Session, SessionChair

User = get_user_model()


class LockSpeakerLoginsTests(TestCase):
    """Speakers should be presentable without being able to sign in.

    The tempting shortcut — deleting their user accounts — destroys the
    speakers themselves, because Speaker → PersonProfile → User cascades. These
    tests pin down the alternative: the accounts stay, the logins go.
    """

    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Lock Test", slug="lock-test",
            start_date=date(2026, 7, 8), end_date=date(2026, 7, 10),
            is_published=True,
        )

    def make_speaker(self, username, password="secret-pw-123"):
        user = User.objects.create_user(
            username=username, password=password,
            first_name=username.title(), last_name="Example",
        )
        profile = PersonProfile.objects.create(
            user=user, event=self.event, affiliation="Some Institute",
            profile_public=True,
        )
        Speaker.objects.create(profile=profile)
        return user

    def run_command(self, *args):
        out = StringIO()
        call_command("lock_speaker_logins", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        user = self.make_speaker("dry")
        output = self.run_command()
        user.refresh_from_db()
        self.assertTrue(user.has_usable_password())
        self.assertTrue(user.check_password("secret-pw-123"))
        self.assertIn("Dry run", output)

    def test_apply_removes_the_password_login(self):
        self.make_speaker("plain")
        self.run_command("--apply")
        plain = User.objects.get(username="plain")
        self.assertFalse(plain.check_password("secret-pw-123"))
        self.assertFalse(plain.has_usable_password())

    def test_apply_keeps_name_affiliation_and_the_speaker_page(self):
        """The whole point: locking must not cost a single displayed field."""
        user = self.make_speaker("visible")
        self.run_command("--apply")
        user.refresh_from_db()
        self.assertEqual(user.get_full_name(), "Visible Example")
        self.assertEqual(user.event_profiles.get().affiliation, "Some Institute")
        self.assertEqual(Speaker.objects.filter(profile__user=user).count(), 1)
        resp = self.client.get(reverse("people:detail", kwargs={"username": "visible"}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Visible Example")

    def test_bound_access_token_is_deactivated_and_unbound(self):
        user = self.make_speaker("tokened")
        token = AccessToken.objects.create(
            event=self.event, token="tok-lock-0001", user=user, is_active=True,
        )
        self.run_command("--apply")
        token.refresh_from_db()
        self.assertFalse(token.is_active)
        self.assertIsNone(token.user, "a still-bound token would sign them back in")

    def test_chairs_reviewers_ops_and_staff_keep_their_login(self):
        """Speaking is a role, not a rank — these people need to sign in."""
        chair = self.make_speaker("chair")
        session = Session.objects.create(
            event=self.event, title="A talk",
            starts_at="2026-07-08T09:00:00Z", ends_at="2026-07-08T10:00:00Z",
        )
        SessionChair.objects.create(session=session, user=chair)

        reviewer = self.make_speaker("reviewer")
        abstract = Abstract.objects.create(event=self.event, title="An abstract")
        AbstractReview.objects.create(abstract=abstract, reviewer=reviewer)

        ops = self.make_speaker("ops")
        ops.groups.add(Group.objects.create(name=OPS_GROUP_NAME))

        staff = self.make_speaker("staffer")
        staff.is_staff = True
        staff.save(update_fields=["is_staff"])

        self.make_speaker("plain")

        self.run_command("--apply")

        for username in ("chair", "reviewer", "ops", "staffer"):
            with self.subTest(username=username):
                self.assertTrue(
                    User.objects.get(username=username).check_password("secret-pw-123"),
                    f"{username} holds a role and must keep signing in",
                )
        self.assertFalse(
            User.objects.get(username="plain").check_password("secret-pw-123"))

    def test_event_filter_limits_the_scope(self):
        other = Event.objects.create(
            name="Other", slug="other-event",
            start_date=date(2026, 9, 1), end_date=date(2026, 9, 2),
        )
        mine = self.make_speaker("mine")
        theirs = User.objects.create_user(username="theirs", password="secret-pw-123")
        profile = PersonProfile.objects.create(user=theirs, event=other)
        Speaker.objects.create(profile=profile)

        self.run_command("--apply", "--event", self.event.slug)

        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertFalse(mine.has_usable_password())
        self.assertTrue(theirs.check_password("secret-pw-123"))

    def test_report_does_not_call_an_empty_password_a_login(self):
        """Bulk-created accounts carry an empty password hash. Django's
        has_usable_password() calls that "usable"; nobody can sign in with it,
        and a report that claims otherwise sends people chasing ghosts."""
        user = self.make_speaker("blank")
        User.objects.filter(pk=user.pk).update(password="")
        output = self.run_command()
        self.assertIn("able to sign in with a password today: 0", output)


class SpeakerDetailVisibilityTests(TestCase):
    """A profile that is not released must not be reachable by guessing the
    URL — the privacy policy promises profiles appear only once released."""

    def test_unreleased_profile_is_404(self):
        event = Event.objects.create(name="E", slug="e", is_published=True,
                                     start_date=date(2026, 9, 11), end_date=date(2026, 9, 12))
        user = get_user_model().objects.create_user("hidden", password="x")
        PersonProfile.objects.create(user=user, event=event, profile_public=False)
        self.assertEqual(self.client.get("/speakers/hidden/").status_code, 404)
        PersonProfile.objects.filter(user=user).update(profile_public=True)
        self.assertEqual(self.client.get("/speakers/hidden/").status_code, 200)
