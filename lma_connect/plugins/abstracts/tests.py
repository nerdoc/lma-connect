"""Audience voting — budget, finality, points, ranking.

The star is the only user action in this app that cannot be undone. So the
tests focus on the edges: the budget, double voting, and that nothing but the
QR stop ever writes one.
"""

import datetime

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from lma_connect.plugins.core.models import Event
from lma_connect.plugins.gamification.models import ScoreAction, ScoreEntry

from .models import STARS_PER_USER, Abstract, AbstractAward, AbstractStarVote
from .services import cast_star, has_voted, star_ranking, stars_left, stars_used

User = get_user_model()


def _make_abstract(event, n: int, **kwargs) -> Abstract:
    defaults = {
        "title": f"Abstract {n}", "slug": f"abstract-{n}",
        "poster_id": f"P-{n:03d}", "abstract_text": "…",
        "is_published": True, "has_poster": True,
    }
    defaults.update(kwargs)
    return Abstract.objects.create(event=event, **defaults)


class StarVotingServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Demo Summit", slug="demo", is_published=True,
            start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2026, 9, 3),
        )
        cls.abstracts = [_make_abstract(cls.event, i) for i in range(1, 6)]

    def setUp(self):
        self.user = User.objects.create_user(username="attendee", password="x")

    def test_star_is_recorded_and_counts_against_quota(self):
        self.assertEqual(stars_left(self.user, self.event), STARS_PER_USER)
        vote = cast_star(self.user, self.abstracts[0])
        self.assertIsNotNone(vote)
        self.assertTrue(has_voted(self.user, self.abstracts[0]))
        self.assertEqual(stars_used(self.user, self.event), 1)
        self.assertEqual(stars_left(self.user, self.event), STARS_PER_USER - 1)

    def test_quota_is_exhausted_after_three_stars(self):
        for a in self.abstracts[:STARS_PER_USER]:
            self.assertIsNotNone(cast_star(self.user, a))
        self.assertEqual(stars_left(self.user, self.event), 0)
        # The fourth star is refused, without raising.
        self.assertIsNone(cast_star(self.user, self.abstracts[STARS_PER_USER]))
        self.assertEqual(
            AbstractStarVote.objects.filter(user=self.user).count(), STARS_PER_USER)

    def test_second_star_on_same_abstract_is_rejected(self):
        cast_star(self.user, self.abstracts[0])
        self.assertIsNone(cast_star(self.user, self.abstracts[0]))
        self.assertEqual(stars_used(self.user, self.event), 1)

    def test_quota_is_per_event(self):
        other = Event.objects.create(
            name="Demo 2027", slug="demo-2027", is_published=False,
            start_date=datetime.date(2027, 9, 1),
            end_date=datetime.date(2027, 9, 3),
        )
        other_abstract = _make_abstract(other, 99)
        for a in self.abstracts[:STARS_PER_USER]:
            cast_star(self.user, a)
        self.assertEqual(stars_left(self.user, other), STARS_PER_USER)
        self.assertIsNotNone(cast_star(self.user, other_abstract))

    def test_anonymous_user_cannot_vote(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertIsNone(cast_star(AnonymousUser(), self.abstracts[0]))
        self.assertEqual(AbstractStarVote.objects.count(), 0)

    def test_ranking_sorts_by_stars_desc(self):
        second = User.objects.create_user(username="attendee2", password="x")
        cast_star(self.user, self.abstracts[1])
        cast_star(second, self.abstracts[1])
        cast_star(second, self.abstracts[0])

        rows = star_ranking(self.event)
        self.assertEqual(rows[0].pk, self.abstracts[1].pk)
        self.assertEqual(rows[0].n_stars, 2)
        self.assertEqual(rows[1].pk, self.abstracts[0].pk)
        self.assertEqual(rows[1].n_stars, 1)
        # Abstracts without votes stay in the list.
        self.assertEqual(len(rows), len(self.abstracts))

    def test_ranking_skips_unpublished(self):
        _make_abstract(self.event, 42, is_published=False)
        self.assertEqual(len(star_ranking(self.event)), len(self.abstracts))


class StarVotingPointsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Demo Summit", slug="demo", is_published=True,
            start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2026, 9, 3),
        )
        cls.abstract = _make_abstract(cls.event, 1)

    def setUp(self):
        self.user = User.objects.create_user(username="attendee", password="x")

    def test_star_awards_points_once(self):
        cast_star(self.user, self.abstract)
        entries = ScoreEntry.objects.filter(
            user=self.user, event=self.event, action=ScoreAction.ABSTRACT_STARRED)
        self.assertEqual(entries.count(), 1)

        # Saving the same row again must not book a second time.
        vote = AbstractStarVote.objects.get(user=self.user, abstract=self.abstract)
        vote.save()
        self.assertEqual(entries.count(), 1)


class PosterStopVotingTests(TestCase):
    """The QR stop is the only place a star can come into existence."""

    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Demo Summit", slug="demo", is_published=True,
            start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2026, 9, 3),
        )
        cls.abstract = _make_abstract(cls.event, 1)
        cls.oral_with_poster = _make_abstract(
            cls.event, 2, type="oral", poster_id="O-02", has_poster=True)
        cls.oral_without_poster = _make_abstract(
            cls.event, 3, type="oral", poster_id="O-03", has_poster=False)

    def setUp(self):
        self.user = User.objects.create_user(username="attendee", password="pw-12345")
        self.client.force_login(self.user)

    def _url(self, abstract):
        return reverse("expo:poster_stop", kwargs={"slug": abstract.slug})

    def test_get_shows_vote_button_but_stores_nothing(self):
        resp = self.client.get(self._url(self.abstract))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(AbstractStarVote.objects.count(), 0)

    def test_confirm_step_does_not_store_yet(self):
        resp = self.client.get(self._url(self.abstract), {"confirm": "1"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["confirming"])
        self.assertEqual(AbstractStarVote.objects.count(), 0)

    def test_post_stores_the_star(self):
        resp = self.client.post(self._url(self.abstract))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(has_voted(self.user, self.abstract))

    def test_second_post_does_not_double_count(self):
        self.client.post(self._url(self.abstract))
        self.client.post(self._url(self.abstract))
        self.assertEqual(
            AbstractStarVote.objects.filter(
                user=self.user, abstract=self.abstract).count(), 1)

    def test_oral_with_poster_is_reachable(self):
        self.assertEqual(
            self.client.get(self._url(self.oral_with_poster)).status_code, 200)

    def test_abstract_without_poster_is_404(self):
        self.assertEqual(
            self.client.get(self._url(self.oral_without_poster)).status_code, 404)

    def test_login_required(self):
        self.client.logout()
        resp = self.client.get(self._url(self.abstract))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_page_after_voting_offers_no_way_back(self):
        self.client.post(self._url(self.abstract))
        resp = self.client.get(self._url(self.abstract))
        self.assertTrue(resp.context["voted"])
        self.assertFalse(resp.context["confirming"])
        # Neither a confirmation nor an undo button.
        self.assertNotContains(resp, "confirm=1")

    def test_exhausted_quota_hides_the_button(self):
        others = [_make_abstract(self.event, 10 + i) for i in range(STARS_PER_USER)]
        for a in others:
            self.client.post(self._url(a))

        resp = self.client.get(self._url(self.abstract))
        self.assertEqual(resp.context["stars_left"], 0)
        self.assertFalse(resp.context["confirming"])
        self.assertNotContains(resp, "confirm=1")

    def test_confirm_param_ignored_when_quota_is_empty(self):
        others = [_make_abstract(self.event, 20 + i) for i in range(STARS_PER_USER)]
        for a in others:
            self.client.post(self._url(a))

        resp = self.client.get(self._url(self.abstract), {"confirm": "1"})
        self.assertFalse(resp.context["confirming"])
        # A direct POST must not get around the limit either.
        self.client.post(self._url(self.abstract))
        self.assertFalse(has_voted(self.user, self.abstract))


class VotingHintTests(TestCase):
    """The detail page only carries the note — voting happens at the poster."""

    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Demo Summit", slug="demo", is_published=True,
            start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2026, 9, 3),
        )
        cls.with_poster = _make_abstract(cls.event, 1)
        cls.without_poster = _make_abstract(
            cls.event, 2, type="oral", poster_id="O-02", has_poster=False)

    def setUp(self):
        self.user = User.objects.create_user(username="attendee", password="pw-12345")

    def _url(self, abstract):
        return reverse("abstracts:detail", kwargs={"slug": abstract.slug})

    def test_hint_shown_for_poster_abstracts(self):
        self.client.force_login(self.user)
        resp = self.client.get(self._url(self.with_poster))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Audience Choice")
        self.assertEqual(resp.context["stars_left"], STARS_PER_USER)
        self.assertFalse(resp.context["user_star_given"])

    def test_detail_page_never_stores_a_vote(self):
        self.client.force_login(self.user)
        self.client.post(self._url(self.with_poster))
        self.assertEqual(AbstractStarVote.objects.count(), 0)

    def test_hint_hidden_without_poster(self):
        resp = self.client.get(self._url(self.without_poster))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "Audience Choice")

    def test_anonymous_visitor_sees_page(self):
        resp = self.client.get(self._url(self.with_poster))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["stars_left"], 0)

    def test_given_star_is_reflected(self):
        cast_star(self.user, self.with_poster)
        self.client.force_login(self.user)
        resp = self.client.get(self._url(self.with_poster))
        self.assertTrue(resp.context["user_star_given"])

    def test_me_page_shows_star_quota(self):
        cast_star(self.user, self.with_poster)
        self.client.force_login(self.user)
        resp = self.client.get(reverse("access:me"))
        self.assertEqual(resp.status_code, 200)
        stars = resp.context["stats"]["stars"]
        self.assertEqual(stars["used"], 1)
        self.assertEqual(stars["left"], STARS_PER_USER - 1)
        self.assertEqual(stars["slots"], [True, False, False])


class AudienceAwardOpsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Demo Summit", slug="demo", is_published=True,
            start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2026, 9, 3),
        )
        cls.first = _make_abstract(cls.event, 1)
        cls.second = _make_abstract(cls.event, 2)
        # Which award the audience decides is per-event data, not a fixed
        # slug — the ops view looks it up via this flag.
        cls.audience_award = AbstractAward.objects.create(
            event=cls.event, name="Audience Choice Award",
            slug="audience-choice", is_audience_choice=True,
        )

    def setUp(self):
        self.ops = User.objects.create_user(
            username="ops", password="pw-12345", is_superuser=True, is_staff=True)
        self.client.force_login(self.ops)

    def _award_url(self, abstract):
        return reverse("access:ops_abstract_audience_award",
                       kwargs={"abstract_id": abstract.pk})

    def test_award_is_set_and_toggled_off(self):
        self.client.post(self._award_url(self.first))
        self.first.refresh_from_db()
        self.assertEqual(self.first.award, self.audience_award)
        self.assertIsNotNone(self.first.award_at)

        self.client.post(self._award_url(self.first))
        self.first.refresh_from_db()
        self.assertIsNone(self.first.award)

    def test_only_one_audience_choice_per_event(self):
        self.client.post(self._award_url(self.first))
        self.client.post(self._award_url(self.second))
        self.first.refresh_from_db()
        self.second.refresh_from_db()
        self.assertIsNone(self.first.award)
        self.assertEqual(self.second.award, self.audience_award)

    def test_jury_awards_survive_the_audience_vote(self):
        """Handing out the audience award must not wipe another abstract's
        jury prize — only the audience award itself moves."""
        jury = AbstractAward.objects.create(event=self.event, name="Best Poster",
                                            slug="best-poster")
        self.first.award = jury
        self.first.save(update_fields=["award"])

        self.client.post(self._award_url(self.second))
        self.first.refresh_from_db()
        self.assertEqual(self.first.award, jury)

    def test_without_a_configured_award_nothing_happens(self):
        """An event that hands out no audience prize gets an explanation, not
        a silent no-op or a crash."""
        self.audience_award.delete()
        resp = self.client.post(self._award_url(self.first), follow=True)
        self.first.refresh_from_db()
        self.assertIsNone(self.first.award)
        self.assertContains(resp, "No audience-choice award is configured")

    def test_ranking_page_renders(self):
        resp = self.client.get(reverse("access:ops_abstract_stars"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["stars_per_user"], STARS_PER_USER)

    def test_ranking_page_with_votes_and_tie(self):
        """Bars, leader marker and tie notice all render."""
        voter = User.objects.create_user(username="voter", password="x")
        cast_star(voter, self.first)
        cast_star(voter, self.second)

        resp = self.client.get(reverse("access:ops_abstract_stars"))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["is_tie"])
        self.assertEqual(len(resp.context["leaders"]), 2)
        self.assertEqual(resp.context["total_votes"], 2)
        self.assertEqual(resp.context["n_voters"], 1)

    def test_ranking_counts_voters_not_votes(self):
        a = User.objects.create_user(username="a", password="x")
        b = User.objects.create_user(username="b", password="x")
        cast_star(a, self.first)
        cast_star(a, self.second)
        cast_star(b, self.first)

        resp = self.client.get(reverse("access:ops_abstract_stars"))
        self.assertEqual(resp.context["total_votes"], 3)
        self.assertEqual(resp.context["n_voters"], 2)
        self.assertFalse(resp.context["is_tie"])
        self.assertEqual(resp.context["leaders"][0].pk, self.first.pk)


class AwardModelMigrationTests(TransactionTestCase):
    """Turning the award choices into rows moves production content: which
    abstract won what. The migration has to carry it in both directions
    (task #67)."""

    migrate_from = ("lma_abstracts", "0007_has_poster_from_type")
    migrate_to = ("lma_abstracts", "0008_awards_as_model_and_author_country")
    # Pinned alongside, so rolling the abstracts app back does not drag the
    # core app's historical state along with it: at abstracts/0007 the core
    # models would otherwise be read at their pre-0010 shape while the actual
    # tables are current, and creating an Event would look for columns that no
    # longer exist.
    core_at = ("lma_core", "0011_committees_free_form_and_brand_palette")

    def _migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        targets = [self.core_at, target]
        executor.migrate(targets)
        return executor.loader.project_state(targets).apps

    def _legacy_event_and_abstracts(self, apps):
        EventModel = apps.get_model("lma_core", "Event")
        AbstractModel = apps.get_model("lma_abstracts", "Abstract")
        event = EventModel.objects.create(
            name="Legacy", slug="legacy",
            start_date=datetime.date(2026, 7, 8), end_date=datetime.date(2026, 7, 10),
        )
        return event, AbstractModel

    def test_award_strings_become_rows_and_survive_the_round_trip(self):
        old_apps = self._migrate(self.migrate_from)
        event, AbstractModel = self._legacy_event_and_abstracts(old_apps)
        AbstractModel.objects.create(event=event, slug="a", title="A",
                                     abstract_text="x", award="best_poster")
        AbstractModel.objects.create(event=event, slug="b", title="B",
                                     abstract_text="x", award="audience_choice")
        AbstractModel.objects.create(event=event, slug="c", title="C",
                                     abstract_text="x", award="")

        new_apps = self._migrate(self.migrate_to)
        AwardModel = new_apps.get_model("lma_abstracts", "AbstractAward")
        awards = {a.slug: a for a in AwardModel.objects.all()}
        # Only the values actually in use become rows — an unused choice must
        # not show up in someone's admin.
        self.assertEqual(set(awards), {"best_poster", "audience_choice"})
        self.assertEqual(awards["best_poster"].name, "Best Poster")
        self.assertTrue(awards["audience_choice"].is_audience_choice)
        self.assertFalse(awards["best_poster"].is_audience_choice)

        NewAbstract = new_apps.get_model("lma_abstracts", "Abstract")
        by_slug = {a.slug: a for a in NewAbstract.objects.all()}
        self.assertEqual(by_slug["a"].award_id, awards["best_poster"].pk)
        self.assertEqual(by_slug["b"].award_id, awards["audience_choice"].pk)
        self.assertIsNone(by_slug["c"].award_id)

        # Backwards: the exact original strings come back.
        back_apps = self._migrate(self.migrate_from)
        back = {a.slug: a.award
                for a in back_apps.get_model("lma_abstracts", "Abstract").objects.all()}
        self.assertEqual(back, {"a": "best_poster", "b": "audience_choice", "c": ""})

    def tearDown(self):
        # Later tests expect the current schema.
        self._migrate(self.migrate_to)
        super().tearDown()
