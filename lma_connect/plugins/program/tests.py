from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import AsyncClient, TestCase
from django.urls import reverse
from django.utils import timezone

from lma_connect.plugins.core.models import Event

from .models import (
    LivePoll,
    LivePollOption,
    LivePollResponse,
    Session,
    SessionChair,
)

User = get_user_model()


class PollFixtureMixin:
    """Shared fixture: event, session, chair and attendee, one active
    single-choice poll with 3 votes (2×A, 1×B)."""

    def setUp(self):
        now = timezone.now()
        self.event = Event.objects.create(
            name="Demo Summit", slug="demo",
            start_date=now.date(), end_date=(now + timedelta(days=1)).date(),
            is_published=True,
        )
        self.session = Session.objects.create(
            event=self.event, title="Keynote", slug="keynote",
            starts_at=now, ends_at=now + timedelta(hours=1),
            is_published=True,
        )
        self.chair = User.objects.create_user("chair", password="x")
        self.attendee = User.objects.create_user("attendee", password="x")
        self.outsider = User.objects.create_user("outsider", password="x")
        SessionChair.objects.create(session=self.session, user=self.chair)

        self.poll = LivePoll.objects.create(
            session=self.session, question_text="Best method?",
            type="single", is_active=True,
        )
        self.opt_a = LivePollOption.objects.create(poll=self.poll, text="A", order=0)
        self.opt_b = LivePollOption.objects.create(poll=self.poll, text="B", order=1)
        # 2 votes for A, 1 for B → A leads (66% / 33%).
        LivePollResponse.objects.create(poll=self.poll, user=self.attendee, option=self.opt_a)
        LivePollResponse.objects.create(poll=self.poll, user=self.chair, option=self.opt_a)
        LivePollResponse.objects.create(poll=self.poll, user=self.outsider, option=self.opt_b)

        self.project_url = reverse("program:poll_project", args=[self.poll.id])
        self.results_url = reverse("program:poll_project_results", args=[self.poll.id])


class PollProjectionTests(PollFixtureMixin, TestCase):
    """Chair projection (16:9) plus results hidden from attendees."""

    def test_default_results_hidden_from_attendees(self):
        self.assertFalse(LivePoll.objects.get(pk=self.poll.pk).is_results_public)

    def test_chair_sees_projection_with_tallies(self):
        self.client.force_login(self.chair)
        resp = self.client.get(self.project_url)
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("Best method?", body)
        self.assertIn("67%", body)   # A: 2/3 → gerundet 67
        self.assertIn("33%", body)   # B: 1/3
        self.assertIn("LIVE", body)

    def test_staff_may_project_even_without_chair_row(self):
        staff = User.objects.create_user("ops", password="x", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.project_url).status_code, 200)

    def test_non_chair_attendee_is_forbidden(self):
        self.client.force_login(self.attendee)
        self.assertEqual(self.client.get(self.project_url).status_code, 403)
        self.assertEqual(self.client.get(self.results_url).status_code, 403)

    def test_anonymous_is_redirected_to_login(self):
        resp = self.client.get(self.project_url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp["Location"])

    def test_results_partial_refreshes_live_tallies(self):
        self.client.force_login(self.chair)
        # Neue Stimme → Partial spiegelt sie sofort wider.
        newbie = User.objects.create_user("newbie", password="x")
        LivePollResponse.objects.create(poll=self.poll, user=newbie, option=self.opt_b)
        resp = self.client.get(self.results_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "4")  # total votes
        # A: 2/4 = 50%, B: 2/4 = 50%
        self.assertContains(resp, "50%")

    def test_attendee_detail_hides_results_but_shows_form(self):
        self.client.force_login(self.attendee)
        resp = self.client.get(reverse("program:detail", args=[self.session.slug]))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("room screen", body)      # the note, not the results
        vote_url = reverse("program:poll_vote", args=[self.poll.id])
        self.assertIn(vote_url, body)            # Abstimm-Formular vorhanden
        self.assertNotIn("66%", body)            # and no result percentages

    def test_chair_panel_shows_screen_remote(self):
        self.client.force_login(self.chair)
        resp = self.client.get(reverse("program:chair_panel", args=[self.session.slug]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Best method?")
        self.assertContains(resp, "Room screen")
        self.assertContains(resp, reverse("program:session_screen", args=[self.session.slug]))
        self.assertContains(resp, reverse("program:poll_toggle_active", args=[self.poll.id]))
        self.assertContains(resp, reverse("program:screen_set_source", args=[self.session.slug]))
        # Regression: multi-line {# #} comments must not leak through as text.
        self.assertNotContains(resp, "{#")
        self.assertNotContains(resp, "Chair-Fernbedienung")

    def test_attendee_detail_shows_results_when_flag_public(self):
        self.poll.is_results_public = True
        self.poll.save(update_fields=["is_results_public"])
        self.client.force_login(self.attendee)
        resp = self.client.get(reverse("program:detail", args=[self.session.slug]))
        self.assertContains(resp, "vote")  # Ergebnisbereich sichtbar


class PollToggleTests(PollFixtureMixin, TestCase):
    """Opening and closing a poll from the chair panel."""

    def setUp(self):
        super().setUp()
        self.toggle_url = reverse("program:poll_toggle_active", args=[self.poll.id])

    def test_chair_stops_and_starts_poll(self):
        self.client.force_login(self.chair)
        self.assertTrue(self.poll.is_active)
        self.client.post(self.toggle_url)
        self.poll.refresh_from_db()
        self.assertFalse(self.poll.is_active)      # gestoppt
        self.client.post(self.toggle_url)
        self.poll.refresh_from_db()
        self.assertTrue(self.poll.is_active)       # wieder gestartet

    def test_toggle_requires_post(self):
        self.client.force_login(self.chair)
        self.assertEqual(self.client.get(self.toggle_url).status_code, 405)

    def test_non_chair_cannot_toggle(self):
        self.client.force_login(self.attendee)
        self.assertEqual(self.client.post(self.toggle_url).status_code, 403)
        self.poll.refresh_from_db()
        self.assertTrue(self.poll.is_active)       # unchanged


class ScreenSwitcherTests(PollFixtureMixin, TestCase):
    """Chair-gesteuerter Beamer-Umschalter (Standby / Q&A / Poll)."""

    def setUp(self):
        super().setUp()
        self.source_url = reverse("program:screen_set_source", args=[self.session.slug])
        self.screen_url = reverse("program:session_screen", args=[self.session.slug])
        self.content_url = reverse("program:screen_content", args=[self.session.slug])

    def test_default_source_is_standby(self):
        self.assertEqual(self.session.screen_source, "standby")
        self.client.force_login(self.chair)
        resp = self.client.get(self.content_url)
        self.assertContains(resp, "continue shortly")   # Standby-Text

    def test_full_beamer_page_renders_for_chair(self):
        self.client.force_login(self.chair)
        resp = self.client.get(self.screen_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "LIVE")
        self.assertContains(resp, "screen-content")     # HTMX-Polling-Container

    def test_chair_switches_to_qa(self):
        self.client.force_login(self.chair)
        self.client.post(self.source_url, {"source": "qa"})
        self.session.refresh_from_db()
        self.assertEqual(self.session.screen_source, "qa")

    def test_chair_projects_specific_poll(self):
        self.client.force_login(self.chair)
        self.client.post(self.source_url, {"source": "poll", "poll": self.poll.id})
        self.session.refresh_from_db()
        self.assertEqual(self.session.screen_source, "poll")
        self.assertEqual(self.session.screen_poll_id, self.poll.id)
        # The projected content now shows the question and the results.
        resp = self.client.get(self.content_url)
        self.assertContains(resp, "Best method?")
        self.assertContains(resp, "67%")

    def test_projecting_poll_from_other_session_is_404(self):
        other = Session.objects.create(
            event=self.event, title="Other", slug="other",
            starts_at=self.session.starts_at, ends_at=self.session.ends_at,
            is_published=True,
        )
        foreign_poll = LivePoll.objects.create(
            session=other, question_text="Nope", type="single")
        self.client.force_login(self.chair)
        resp = self.client.post(
            self.source_url, {"source": "poll", "poll": foreign_poll.id})
        self.assertEqual(resp.status_code, 404)

    def test_invalid_source_is_bad_request(self):
        self.client.force_login(self.chair)
        self.assertEqual(
            self.client.post(self.source_url, {"source": "bogus"}).status_code, 400)

    def test_deleted_projected_poll_falls_back_to_standby(self):
        self.client.force_login(self.chair)
        self.client.post(self.source_url, {"source": "poll", "poll": self.poll.id})
        self.poll.delete()   # SET_NULL → screen_poll None, source bleibt "poll"
        resp = self.client.get(self.content_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "continue shortly")   # Fallback Standby

    def test_screen_page_is_chair_only(self):
        self.client.force_login(self.attendee)
        self.assertEqual(self.client.get(self.screen_url).status_code, 403)
        self.assertEqual(self.client.get(self.content_url).status_code, 403)
        self.assertEqual(
            self.client.post(self.source_url, {"source": "qa"}).status_code, 403)


class SpeakerIntroVisibilityTests(PollFixtureMixin, TestCase):
    """Task #82 — the speaker's public intro shows on the session page, the
    chair notes only in the chair view (never to attendees)."""

    def setUp(self):
        super().setUp()
        from lma_connect.plugins.people.models import PersonProfile, Speaker
        from .models import SessionSpeaker

        speaker_user = User.objects.create_user("speaker", password="x",
                                                first_name="Ada", last_name="Lovelace")
        profile = PersonProfile.objects.create(user=speaker_user, event=self.event,
                                               profile_public=True)
        self.speaker = Speaker.objects.create(
            profile=profile, affiliation="Analytical Engine Lab, London",
            intro="Pioneer of programmable computation.",
            chair_notes="SECRET-CHAIR-NOTE: mention the Babbage anecdote.",
        )
        SessionSpeaker.objects.create(session=self.session, speaker=self.speaker)

    def test_public_detail_shows_intro_but_not_chair_notes(self):
        self.client.force_login(self.attendee)
        resp = self.client.get(reverse("program:detail", args=[self.session.slug]))
        self.assertContains(resp, "Analytical Engine Lab, London")
        self.assertContains(resp, "Pioneer of programmable computation.")
        self.assertNotContains(resp, "SECRET-CHAIR-NOTE")

    def test_speaker_page_shows_intro_but_not_chair_notes(self):
        self.client.force_login(self.attendee)
        resp = self.client.get(reverse("people:detail", args=["speaker"]))
        self.assertContains(resp, "Pioneer of programmable computation.")
        self.assertNotContains(resp, "SECRET-CHAIR-NOTE")

    def test_chair_panel_shows_chair_notes(self):
        self.client.force_login(self.chair)
        resp = self.client.get(reverse("program:chair_panel", args=[self.session.slug]))
        self.assertContains(resp, "Ada Lovelace")
        self.assertContains(resp, "SECRET-CHAIR-NOTE")

    def test_attendee_cannot_open_chair_panel(self):
        self.client.force_login(self.attendee)
        resp = self.client.get(reverse("program:chair_panel", args=[self.session.slug]))
        self.assertEqual(resp.status_code, 403)

    def test_chair_can_save_notes_for_own_session(self):
        self.client.force_login(self.chair)
        url = reverse("program:chair_speaker_notes", args=[self.session.slug, self.speaker.id])
        resp = self.client.post(url, {"chair_notes": "  New note from the panel  "})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "New note from the panel")
        self.speaker.refresh_from_db()
        self.assertEqual(self.speaker.chair_notes, "New note from the panel")

    def test_chair_of_other_session_cannot_save_notes(self):
        from .models import SessionSpeaker
        other = Session.objects.create(
            event=self.event, title="Other", slug="other",
            starts_at=timezone.now(), ends_at=timezone.now() + timedelta(hours=1),
            is_published=True,
        )
        other_chair = User.objects.create_user("other_chair", password="x")
        SessionChair.objects.create(session=other, user=other_chair)
        self.client.force_login(other_chair)
        # Not chair of self.session → 403, even though the speaker exists.
        url = reverse("program:chair_speaker_notes", args=[self.session.slug, self.speaker.id])
        resp = self.client.post(url, {"chair_notes": "hijack"})
        self.assertEqual(resp.status_code, 403)
        # Chair of `other`, but the speaker is not assigned there → 404.
        url = reverse("program:chair_speaker_notes", args=[other.slug, self.speaker.id])
        resp = self.client.post(url, {"chair_notes": "hijack"})
        self.assertEqual(resp.status_code, 404)
        self.speaker.refresh_from_db()
        self.assertEqual(self.speaker.chair_notes,
                         "SECRET-CHAIR-NOTE: mention the Babbage anecdote.")

    def test_notes_require_post(self):
        self.client.force_login(self.chair)
        url = reverse("program:chair_speaker_notes", args=[self.session.slug, self.speaker.id])
        self.assertEqual(self.client.get(url).status_code, 405)


class LiveStreamTests(TestCase):
    """SSE endpoints in live.py — served only under ASGI."""

    async def test_ping_stream_is_event_stream(self):
        response = await AsyncClient().get(reverse("live:ping") + "?interval=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")
        self.assertEqual(response["Cache-Control"], "no-cache")
        first = await anext(response.streaming_content)
        self.assertEqual(first, b": ping 1\n\n")
        await response.streaming_content.aclose()

    async def test_ping_interval_is_clamped(self):
        response = await AsyncClient().get(reverse("live:ping") + "?interval=abc")
        self.assertEqual(response.status_code, 200)
        await response.streaming_content.aclose()

    def test_stream_under_wsgi_is_503(self):
        # WSGI would collect the endless async iterator into a list — the
        # guard has to answer 503 before that happens.
        response = self.client.get(reverse("live:ping"))
        self.assertEqual(response.status_code, 503)
