import gzip
import json
import os
import shutil
import sqlite3
import stat
import tarfile
import tempfile
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import (
    SimpleTestCase,
    TestCase,
    TransactionTestCase,
    override_settings,
)
from django.urls import reverse
from PIL import Image

import lma_connect as meta
from lma_connect.plugins.abstracts.models import Abstract, AbstractAuthor
from lma_connect.plugins.people.models import PersonProfile, Speaker
from lma_connect.plugins.program.models import Session, SessionSpeaker

from .global_stats import flag_emoji
from .management.commands.backup_db import integrity_ok, parse_timestamp, select_expired
from .management.commands.backup_media import archive_ok
from .models import Event, Floorplan, InfoBlock, LegalPage, User


def _transparent_logo_png() -> bytes:
    """A non-square PNG with a transparent ground and a black mark — exactly
    the case the icon views have to centre on a square canvas."""
    img = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
    for x in range(150, 250):
        for y in range(50, 150):
            img.putpixel((x, y), (0, 0, 0, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@override_settings(ALLOWED_HOSTS=["testserver"])
class AppIconTests(TestCase):
    def setUp(self):
        # Recreated per test — the 404 test physically deletes the logo FILE,
        # and files (unlike DB rows) are not rolled back between tests.
        self.event = Event.objects.create(
            name="Demo Summit 2026",
            slug="demo-2026",
            start_date=date(2026, 7, 8),
            end_date=date(2026, 7, 10),
            is_published=True,
            logo=SimpleUploadedFile("logo.png", _transparent_logo_png(),
                                    content_type="image/png"),
        )

    def tearDown(self):
        if self.event.logo:
            self.event.logo.delete(save=False)

    def _icon_url(self, size, *, maskable=False, apple=False):
        name = "core:app_icon"
        if maskable:
            name = "core:app_icon_maskable"
        elif apple:
            name = "core:app_icon_opaque"
        return reverse(name, args=[size, self.event.icon_version])

    def test_icon_is_square_and_transparent(self):
        """The icon shows the bare logo on a transparent ground, rendered to
        exactly the requested square size — no white tile around it."""
        resp = self.client.get(self._icon_url(192))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "image/png")
        img = Image.open(BytesIO(resp.content))
        self.assertEqual(img.size, (192, 192))
        self.assertEqual(img.mode, "RGBA")          # alpha channel kept
        self.assertEqual(img.getpixel((0, 0))[3], 0)  # the corner is transparent

    def test_apple_touch_icon_is_opaque(self):
        """Safari discards home-screen icons with an alpha channel and shows
        the grey letter placeholder instead — the iOS variant has to be
        opaque."""
        resp = self.client.get(self._icon_url(180, apple=True))
        self.assertEqual(resp.status_code, 200)
        img = Image.open(BytesIO(resp.content))
        self.assertEqual(img.size, (180, 180))
        self.assertEqual(img.mode, "RGB")  # no alpha channel
        self.assertEqual(img.getpixel((0, 0)), (255, 255, 255))  # the corner is white

    def test_apple_touch_icon_is_linked_in_head(self):
        """The <head> points apple-touch-icon at the opaque route, not at the
        transparent default icon."""
        resp = self.client.get("/")
        self.assertContains(
            resp, f'rel="apple-touch-icon" sizes="180x180" '
                  f'href="{self._icon_url(180, apple=True)}"')

    def test_maskable_has_larger_safe_zone(self):
        """The maskable icon places the mark more tightly (safe zone); the
        "any" icon uses more of the canvas."""
        any_black = self._black_pixels(self._icon_url(512))
        maskable_black = self._black_pixels(self._icon_url(512, maskable=True))
        self.assertGreater(any_black, maskable_black)

    def _black_pixels(self, path: str) -> int:
        """Opaque dark pixels. Alpha has to be checked too: since the ground
        is transparent, a brightness comparison alone would be blind to the
        fact that transparent pixels carry RGB (0,0,0) and would otherwise
        count as "black"."""
        img = Image.open(BytesIO(self.client.get(path).content)).convert("RGBA")
        return sum(1 for r, g, b, a in img.getdata()
                   if a > 128 and (r + g + b) / 3 < 128)

    def test_manifest_icon_srcs_are_versioned_paths_without_query(self):
        """Icon URLs carry the version token in the path, NOT as a ?query —
        iOS ignores apple-touch-icon URLs that have one."""
        resp = self.client.get("/manifest.webmanifest")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        purposes = sorted(ic["purpose"] for ic in data["icons"])
        self.assertEqual(purposes, ["any", "any", "maskable", "maskable"])
        ver = self.event.icon_version
        for ic in data["icons"]:
            self.assertEqual(ic["type"], "image/png")
            self.assertNotIn("?", ic["src"])          # no query string
            self.assertIn(f"-{ver}.png", ic["src"])   # version in the path

    def test_icon_404_without_logo(self):
        url = self._icon_url(192)
        self.event.logo.delete(save=True)
        self.assertEqual(self.client.get(url).status_code, 404)


@override_settings(ALLOWED_HOSTS=["testserver"])
class AbstractWorldMapTests(TestCase):
    """The abstract map shows accepted (= published) abstracts only —
    submissions under review must move neither a country nor the count.

    The countries come from the author rows; there is no country table in the
    code any more (see core.global_stats).
    """

    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Test Summit 2026", slug="test-2026",
            start_date=date(2026, 7, 8), end_date=date(2026, 7, 10),
            is_published=True,
        )

    def _abstract(self, slug, *, published, countries=(("AT", "Austria"),)):
        abstract = Abstract.objects.create(
            event=self.event, slug=slug, title=slug,
            status="review", is_published=published,
        )
        for index, (iso, name) in enumerate(countries):
            AbstractAuthor.objects.create(
                abstract=abstract, full_name=f"Author {index}",
                country_iso=iso, country=name, order=index,
            )
        return abstract

    def _page(self, url_name="abstracts:list", **params):
        resp = self.client.get(reverse(url_name), params)
        self.assertEqual(resp.status_code, 200)
        # The counter spans two template lines — flatten the whitespace.
        return resp, " ".join(resp.content.decode().split())

    def test_unpublished_abstracts_do_not_appear_on_the_map(self):
        self._abstract("published-one", published=True)
        self._abstract("draft-one", published=False,
                       countries=(("MW", "Malawi"),))
        _, html = self._page()
        self.assertIn("1 country · 1 abstract", html)
        # Country names alone are no assertion — the embedded SVG lists every
        # country in the world anyway. Check the pill title and the generated
        # CSS selector instead.
        self.assertIn("published-one", html)
        self.assertIn(".map-abstracts .world-choropleth #AT", html)
        self.assertNotIn(".map-abstracts .world-choropleth #MW", html)

    def test_multi_country_abstract_counts_once(self):
        """Authors from two countries — two countries, but one abstract."""
        self._abstract("collaboration", published=True,
                       countries=(("IT", "Italy"), ("TR", "Türkiye")))
        _, html = self._page()
        self.assertIn("2 countries · 1 abstract", html)

    def test_same_country_twice_counts_once_per_abstract(self):
        """Two authors from the same institution must not inflate the pill."""
        self._abstract("two-locals", published=True,
                       countries=(("AT", "Austria"), ("AT", "Austria")))
        _, html = self._page()
        self.assertIn("1 country · 1 abstract", html)

    def test_author_country_falls_back_to_the_linked_user(self):
        """External co-authors carry their own country; authors with an
        account may leave it blank and inherit the profile's."""
        user = User.objects.create_user(username="mapper", password="x" * 14,
                                        country_iso="NL", country="Netherlands")
        abstract = Abstract.objects.create(
            event=self.event, slug="linked", title="linked",
            status="review", is_published=True,
        )
        AbstractAuthor.objects.create(abstract=abstract, full_name="Linked", user=user)
        _, html = self._page()
        self.assertIn("1 country · 1 abstract", html)
        self.assertIn(".map-abstracts .world-choropleth #NL", html)

    def test_abstract_without_any_country_still_counts(self):
        """A submission whose authors have no country is counted in the total
        but contributes no pill — otherwise the headline would silently drop
        abstracts just because their metadata is incomplete."""
        self._abstract("with-country", published=True)
        self._abstract("no-country", published=True, countries=())
        _, html = self._page()
        self.assertIn("1 country · 2 abstracts", html)

    def test_map_is_omitted_when_nothing_is_published(self):
        """No countries, no card: an empty isos loop would otherwise produce
        the selector `.map-abstracts .world-choropleth` and paint the whole
        world."""
        self._abstract("draft-only", published=False)
        _, html = self._page()
        self.assertNotIn("world-choropleth", html)
        self.assertNotIn("Where our abstracts come from", html)

    def test_headline_count_ignores_filters(self):
        """`published_count` reports every accepted abstract, not the subset
        the active filter happens to show."""
        self._abstract("a", published=True)
        self._abstract("b", published=True)
        self._abstract("c", published=False)
        resp, _ = self._page(type="oral")
        self.assertEqual(resp.context["published_count"], 2)


@override_settings(ALLOWED_HOSTS=["testserver"])
class SpeakerWorldMapTests(TestCase):
    """The speaker map counts the people actually on the programme."""

    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Test Summit 2026", slug="test-2026",
            start_date=date(2026, 7, 8), end_date=date(2026, 7, 10),
            is_published=True,
        )

    def _speaker(self, username, iso, country):
        user = User.objects.create_user(username=username, password="x" * 14,
                                        first_name=username.title(), last_name="Speaker")
        profile = PersonProfile.objects.create(
            user=user, event=self.event, country_iso=iso, country=country,
            affiliation=f"{country} University",
        )
        return Speaker.objects.create(profile=profile)

    def _session(self, slug, *, published):
        return Session.objects.create(
            event=self.event, slug=slug, title=slug, is_published=published,
            starts_at=datetime(2026, 7, 8, 9, 0, tzinfo=UTC),
            ends_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        )

    def _page(self):
        resp = self.client.get(reverse("program:list"))
        self.assertEqual(resp.status_code, 200)
        return " ".join(resp.content.decode().split())

    def test_only_speakers_of_published_sessions_are_counted(self):
        """A speaker profile that exists but is not on the programme yet must
        not show up before the programme is announced."""
        on_air = self._speaker("live", "AT", "Austria")
        hidden = self._speaker("draft", "MW", "Malawi")
        SessionSpeaker.objects.create(session=self._session("s1", published=True),
                                      speaker=on_air)
        SessionSpeaker.objects.create(session=self._session("s2", published=False),
                                      speaker=hidden)
        html = self._page()
        self.assertIn("1 country · 1 speaker", html)
        self.assertIn(".map-speakers .world-choropleth #AT", html)
        self.assertNotIn(".map-speakers .world-choropleth #MW", html)

    def test_a_speaker_in_two_sessions_counts_once(self):
        speaker = self._speaker("busy", "DE", "Germany")
        for slug in ("s1", "s2"):
            SessionSpeaker.objects.create(session=self._session(slug, published=True),
                                          speaker=speaker)
        html = self._page()
        self.assertIn("1 country · 1 speaker", html)


class FlagEmojiTests(SimpleTestCase):
    """Flags are computed from the ISO code, not looked up in a table — so
    every country works, including ones nobody thought of."""

    def test_two_letter_codes_become_regional_indicators(self):
        self.assertEqual(flag_emoji("AT"), "\U0001F1E6\U0001F1F9")
        self.assertEqual(flag_emoji("mw"), "\U0001F1F2\U0001F1FC")

    def test_anything_that_is_not_a_country_code_yields_nothing(self):
        for value in ("", "A", "AUT", "A1", None):
            self.assertEqual(flag_emoji(value), "")


class DefaultLanguageTests(TestCase):
    """The configured LANGUAGE_CODE has to be everyone's default — the
    browser's Accept-Language header must not decide the language, only the
    cookie set by the in-app switcher."""

    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Demo Summit 2026", slug="demo-2026",
            start_date=date(2026, 7, 8), end_date=date(2026, 7, 10),
            is_published=True,
        )

    def test_german_browser_gets_english_without_cookie(self):
        resp = self.client.get("/", HTTP_ACCEPT_LANGUAGE="de-DE,de;q=0.9")
        self.assertEqual(resp.headers.get("Content-Language"), "en")

    def test_language_cookie_still_switches_to_german(self):
        self.client.cookies["django_language"] = "de"
        resp = self.client.get("/")
        self.assertEqual(resp.headers.get("Content-Language"), "de")

    def test_invalid_cookie_falls_back_to_english(self):
        self.client.cookies["django_language"] = "xx"
        resp = self.client.get("/", HTTP_ACCEPT_LANGUAGE="de-DE,de;q=0.9")
        self.assertEqual(resp.headers.get("Content-Language"), "en")


class InfoBlockTests(TestCase):
    """The info page must hold no content in the template any more — blocks
    come from the admin, in the configured order, and unpublished ones stay
    invisible."""

    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Demo Summit 2026", slug="demo-2026",
            start_date=date(2026, 7, 8), end_date=date(2026, 7, 10),
            is_published=True,
        )
        InfoBlock.objects.create(event=cls.event, title="Catering", icon="tools-kitchen-2",
                                 body="Lunch in the foyer.", order=2)
        InfoBlock.objects.create(event=cls.event, title="WiFi", icon="wifi",
                                 body="Network: **Guest**", title_de="WLAN",
                                 body_de="Netzwerk: **Gast**", order=1)
        InfoBlock.objects.create(event=cls.event, title="Draft block", body="not ready",
                                 is_published=False, order=3)

    def test_published_blocks_render_in_order(self):
        body = self.client.get(reverse("core:info")).content.decode()
        # Match on the body texts rather than the titles: "Catering" also
        # appears in a CSS comment in the base template and would be an
        # unreliable anchor.
        self.assertLess(body.index("<strong>Guest</strong>"), body.index("Lunch in the foyer."))
        self.assertIn("ti-wifi", body)

    def test_unpublished_block_is_hidden(self):
        body = self.client.get(reverse("core:info")).content.decode()
        self.assertNotIn("Draft block", body)

    def test_german_translation_wins_when_language_is_german(self):
        self.client.cookies["django_language"] = "de"
        body = self.client.get(reverse("core:info")).content.decode()
        self.assertIn("WLAN", body)
        self.assertIn("<strong>Gast</strong>", body)

    def test_german_falls_back_to_source_when_translation_empty(self):
        self.client.cookies["django_language"] = "de"
        body = self.client.get(reverse("core:info")).content.decode()
        self.assertIn("Catering", body)
        self.assertIn("Lunch in the foyer.", body)

    def test_icon_rejects_values_that_would_inject_css_classes(self):
        block = InfoBlock(event=self.event, title="Bad", icon="wifi text-danger")
        with self.assertRaises(ValidationError):
            block.full_clean()


class LegalPageTests(TestCase):
    """Legal texts come from the admin instead of four fixed event fields:
    any number of pages, each with its own slug and footer link."""

    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Demo Summit 2026", slug="demo-2026",
            start_date=date(2026, 7, 8), end_date=date(2026, 7, 10),
            is_published=True, organizer_name="LabMedAlliance",
        )
        LegalPage.objects.create(event=cls.event, slug="privacy", title="Privacy policy",
                                 body="We store **little**.", title_de="Datenschutz",
                                 body_de="Wir speichern **wenig**.", order=2)
        LegalPage.objects.create(event=cls.event, slug="imprint", title="Imprint",
                                 body="Association X, Salzburg.", order=1)
        LegalPage.objects.create(event=cls.event, slug="conduct", title="Code of Conduct",
                                 body="Be kind.", is_published=False, order=3)

    def test_page_renders_its_markdown(self):
        resp = self.client.get(reverse("core:legal", args=["privacy"]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "<strong>little</strong>")

    def test_footer_links_every_published_page_in_order(self):
        body = self.client.get(reverse("core:info")).content.decode()
        self.assertLess(body.index("/legal/imprint/"), body.index("/legal/privacy/"))
        self.assertNotIn("/legal/conduct/", body)

    def test_markdown_tables_render_as_tables(self):
        """The GDPR Art. 13 disclosures (processing activities, retention
        periods) live in Markdown tables. Without the tables extension they
        turn into a desert of pipes — the tag whitelist alone is not
        enough."""
        page = LegalPage.objects.get(slug="privacy")
        page.body = "| Data | Purpose |\n|------|---------|\n| Nickname | Display |"
        page.save(update_fields=["body"])
        resp = self.client.get(reverse("core:legal", args=["privacy"]))
        self.assertContains(resp, "<table>")
        self.assertContains(resp, "<td>Nickname</td>")

    def test_unpublished_page_is_not_served(self):
        # 'conduct' is not a canonical slug — with no visible page, 404 it is.
        resp = self.client.get(reverse("core:legal", args=["conduct"]))
        self.assertEqual(resp.status_code, 404)

    def test_unknown_slug_is_404(self):
        self.assertEqual(self.client.get("/legal/nonsense/").status_code, 404)

    def test_canonical_slug_without_page_explains_itself(self):
        """The footer and the help page link 'imprint'/'privacy' directly — a
        text nobody has written yet must not end in a 404 there."""
        resp = self.client.get(reverse("core:legal", args=["terms"]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Terms of use")

    def test_placeholder_keeps_the_admin_path_to_itself(self):
        """Since the onboarding acceptance step, the placeholder page is the
        first one a new attendee opens — a path into the admin does not belong
        there."""
        anonymous = self.client.get(reverse("core:legal", args=["terms"]))
        self.assertNotContains(anonymous, "/admin/lma_core/legalpage/")

        staff = get_user_model().objects.create_user("ops", password="x", is_staff=True)
        self.client.force_login(staff)
        self.assertContains(self.client.get(reverse("core:legal", args=["terms"])),
                            "/admin/lma_core/legalpage/")

    def test_german_translation_wins_when_language_is_german(self):
        self.client.cookies["django_language"] = "de"
        resp = self.client.get(reverse("core:legal", args=["privacy"]))
        self.assertContains(resp, "Datenschutz")
        self.assertContains(resp, "<strong>wenig</strong>")

    def test_slug_is_unique_per_event(self):
        duplicate = LegalPage(event=self.event, slug="privacy", title="Second privacy")
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_seed_legal_creates_pages_and_keeps_edits(self):
        call_command("seed_legal", "--event", self.event.slug)
        slugs = set(self.event.legal_pages.values_list("slug", flat=True))
        self.assertEqual(slugs, {"imprint", "privacy", "terms", "accessibility", "conduct"})
        # Texts already written stay put — a second run is harmless.
        self.assertEqual(self.event.legal_pages.get(slug="privacy").body,
                         "We store **little**.")
        call_command("seed_legal", "--event", self.event.slug, "--overwrite")
        self.assertIn("GDPR", self.event.legal_pages.get(slug="privacy").body)

    def test_seed_legal_writes_both_languages(self):
        """Without body_de, German speakers would get the English legal
        text — which for incorporating terms and for the Art. 13 disclosures
        is not a detail."""
        # --overwrite because setUp already created 'imprint' and 'privacy',
        # and a plain run would rightly leave them alone.
        call_command("seed_legal", "--event", self.event.slug, "--overwrite")
        for slug in ("imprint", "privacy", "terms", "accessibility"):
            with self.subTest(slug=slug):
                page = self.event.legal_pages.get(slug=slug)
                self.assertTrue(page.body.strip())
                self.assertTrue(page.body_de.strip())
        self.assertIn("DSGVO", self.event.legal_pages.get(slug="privacy").body_de)
        self.assertIn("Salvatorische", self.event.legal_pages.get(slug="terms").body_de)
        # Dates in the German text come from Django's catalogue, not from
        # strftime in the C locale — otherwise it would read "8 July 2026".
        imprint = self.event.legal_pages.get(slug="imprint")
        self.assertIn("8. Juli 2026", imprint.body_de)
        self.assertIn("8 July 2026", imprint.body)

    def test_overwrite_refreshes_the_german_text_too(self):
        """Replacing only one language would let the other go stale against
        it."""
        call_command("seed_legal", "--event", self.event.slug)
        page = self.event.legal_pages.get(slug="terms")
        page.body_de = "Veraltet."
        page.save(update_fields=["body_de"])

        call_command("seed_legal", "--event", self.event.slug, "--overwrite")
        page.refresh_from_db()
        self.assertNotEqual(page.body_de, "Veraltet.")
        self.assertIn("Haftungsbeschränkung", page.body_de)


class InfoFieldMigrationTests(TransactionTestCase):
    """Moving to info blocks drops three columns holding production content
    (travel, sightseeing, practical info — each bilingual). It must lose
    nothing doing so, in either direction."""

    migrate_from = ("lma_core", "0007_alter_event_general_info_infoblock")
    migrate_to = ("lma_core", "0008_info_blocks_replace_info_fields")

    def _migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([target])
        return executor.loader.project_state([target]).apps

    def test_field_content_survives_the_round_trip(self):
        old_apps = self._migrate(self.migrate_from)
        OldEvent = old_apps.get_model("lma_core", "Event")
        OldEvent.objects.create(
            name="Legacy", slug="legacy",
            start_date=date(2026, 7, 8), end_date=date(2026, 7, 10),
            travel_info="Take the train.", travel_info_de="Mit dem Zug.",
            sightseeing_info="Visit the fortress.",
            general_info="", general_info_de="",
        )

        new_apps = self._migrate(self.migrate_to)
        InfoBlockModel = new_apps.get_model("lma_core", "InfoBlock")
        blocks = {b.title: b for b in InfoBlockModel.objects.all()}
        # Leere Felder erzeugen keinen leeren Block.
        self.assertEqual(set(blocks), {"How to get there", "Sightseeing"})
        self.assertEqual(blocks["How to get there"].body, "Take the train.")
        self.assertEqual(blocks["How to get there"].body_de, "Mit dem Zug.")
        self.assertEqual(blocks["How to get there"].icon, "train")
        self.assertLess(blocks["How to get there"].order, blocks["Sightseeing"].order)

        # Backwards: the content lands back in its fields.
        back_apps = self._migrate(self.migrate_from)
        BackEvent = back_apps.get_model("lma_core", "Event")
        event = BackEvent.objects.get(slug="legacy")
        self.assertEqual(event.travel_info, "Take the train.")
        self.assertEqual(event.travel_info_de, "Mit dem Zug.")
        self.assertEqual(event.sightseeing_info, "Visit the fortress.")
        self.assertEqual(back_apps.get_model("lma_core", "InfoBlock").objects.count(), 0)

    def tearDown(self):
        # Nachfolgende Tests erwarten den aktuellen Schemastand.
        self._migrate(self.migrate_to)
        super().tearDown()


class FloorplanMigrationTests(TransactionTestCase):
    """Moving floorplans to their own table must not lose uploaded files:
    only the path moves, the file itself stays where it is."""

    migrate_from = ("lma_core", "0008_info_blocks_replace_info_fields")
    migrate_to = ("lma_core", "0009_floorplan_model")

    def _migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([target])
        return executor.loader.project_state([target]).apps

    def test_uploaded_plans_become_floorplan_rows(self):
        old_apps = self._migrate(self.migrate_from)
        OldEvent = old_apps.get_model("lma_core", "Event")
        OldEvent.objects.create(
            name="Legacy", slug="legacy",
            start_date=date(2026, 7, 8), end_date=date(2026, 7, 10),
            floorplan="events/floorplans/eg.png",
            floorplan_upper="events/floorplans/og.pdf",
        )

        new_apps = self._migrate(self.migrate_to)
        plans = list(new_apps.get_model("lma_core", "Floorplan").objects.order_by("order"))
        self.assertEqual([p.title for p in plans], ["Ground floor", "1st floor"])
        self.assertEqual(plans[0].file.name, "events/floorplans/eg.png")
        # The ground floor was the hard-wired booth reference — it inherits
        # the exhibition flag.
        self.assertTrue(plans[0].is_exhibition_floor)
        self.assertFalse(plans[1].is_exhibition_floor)

        back_apps = self._migrate(self.migrate_from)
        event = back_apps.get_model("lma_core", "Event").objects.get(slug="legacy")
        self.assertEqual(event.floorplan.name, "events/floorplans/eg.png")
        self.assertEqual(event.floorplan_upper.name, "events/floorplans/og.pdf")

    def tearDown(self):
        self._migrate(self.migrate_to)
        super().tearDown()


class LegalFieldMigrationTests(TransactionTestCase):
    """Moving to legal pages drops eight columns that can hold finished legal
    texts (four documents, each bilingual). It must lose nothing doing so, in
    either direction."""

    migrate_from = ("lma_core", "0009_floorplan_model")
    migrate_to = ("lma_core", "0010_legal_pages_replace_event_fields")

    def _migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([target])
        return executor.loader.project_state([target]).apps

    def test_field_content_survives_the_round_trip(self):
        old_apps = self._migrate(self.migrate_from)
        OldEvent = old_apps.get_model("lma_core", "Event")
        OldEvent.objects.create(
            name="Legacy", slug="legacy",
            start_date=date(2026, 7, 8), end_date=date(2026, 7, 10),
            imprint_md="Association X.", imprint_md_de="Verein X.",
            privacy_md="We store little.",
            terms_md="", terms_md_de="",
            accessibility_md="", accessibility_md_de="",
        )

        new_apps = self._migrate(self.migrate_to)
        LegalPageModel = new_apps.get_model("lma_core", "LegalPage")
        pages = {p.slug: p for p in LegalPageModel.objects.all()}
        # Empty fields do not produce an empty page.
        self.assertEqual(set(pages), {"imprint", "privacy"})
        self.assertEqual(pages["imprint"].body, "Association X.")
        self.assertEqual(pages["imprint"].body_de, "Verein X.")
        self.assertEqual(pages["imprint"].title, "Imprint")
        self.assertLess(pages["imprint"].order, pages["privacy"].order)

        # Backwards: the content lands back in its fields.
        back_apps = self._migrate(self.migrate_from)
        event = back_apps.get_model("lma_core", "Event").objects.get(slug="legacy")
        self.assertEqual(event.imprint_md, "Association X.")
        self.assertEqual(event.imprint_md_de, "Verein X.")
        self.assertEqual(event.privacy_md, "We store little.")
        # Going backwards the table is gone again — the content sits fully in
        # the fields, not duplicated in both places.
        with self.assertRaises(LookupError):
            back_apps.get_model("lma_core", "LegalPage")

    def tearDown(self):
        # Nachfolgende Tests erwarten den aktuellen Schemastand.
        self._migrate(self.migrate_to)
        super().tearDown()


class CommitteeTypeMigrationTests(TransactionTestCase):
    """Dropping `Committee.type` removes a column that carries production
    content — every committee's kind. The slug has to take its place without
    losing anything, in either direction (task #67)."""

    migrate_from = ("lma_core", "0010_legal_pages_replace_event_fields")
    migrate_to = ("lma_core", "0011_committees_free_form_and_brand_palette")

    def _migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([target])
        return executor.loader.project_state([target]).apps

    def test_type_becomes_a_slug_and_survives_the_round_trip(self):
        old_apps = self._migrate(self.migrate_from)
        OldEvent = old_apps.get_model("lma_core", "Event")
        event = OldEvent.objects.create(
            name="Legacy", slug="legacy",
            start_date=date(2026, 7, 8), end_date=date(2026, 7, 10),
        )
        OldCommittee = old_apps.get_model("lma_core", "Committee")
        OldCommittee.objects.create(event=event, type="scientific",
                                    name="Scientific Committee", order=2)
        OldCommittee.objects.create(event=event, type="organizing", name="", order=1)

        new_apps = self._migrate(self.migrate_to)
        committees = {c.slug: c for c
                      in new_apps.get_model("lma_core", "Committee").objects.all()}
        self.assertEqual(set(committees), {"scientific", "organizing"})
        self.assertEqual(committees["scientific"].name, "Scientific Committee")
        # A committee that only ever had a type gets a readable name from it.
        self.assertEqual(committees["organizing"].name, "Organizing committee")

        # Backwards: the slug maps onto the old type again.
        back_apps = self._migrate(self.migrate_from)
        back = {c.type for c
                in back_apps.get_model("lma_core", "Committee").objects.all()}
        self.assertEqual(back, {"scientific", "organizing"})

    def test_new_events_get_the_full_brand_palette(self):
        """The three added colours must have defaults — an event created before
        the migration would otherwise render with empty CSS variables."""
        self._migrate(self.migrate_to)
        event = Event.objects.create(
            name="Palette", slug="palette",
            start_date=date(2026, 7, 8), end_date=date(2026, 7, 10),
        )
        for field in ("theme_color", "accent_color", "highlight_color",
                      "surface_color", "text_color"):
            value = getattr(event, field)
            self.assertRegex(value, r"^#[0-9a-f]{6}$", f"{field} is not a hex colour")

    def tearDown(self):
        # Later tests expect the current schema.
        self._migrate(self.migrate_to)
        super().tearDown()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class FloorplanTests(TestCase):
    """Floorplans used to come from two fixed fields ("ground floor",
    "first floor"). Any number of levels with their own labels now come from
    the admin, including which of them is the exhibition floor."""

    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Demo Summit 2026", slug="demo-2026",
            start_date=date(2026, 7, 8), end_date=date(2026, 7, 10),
            is_published=True,
        )
        cls.expo = Floorplan.objects.create(
            event=cls.event, title="Hall 3", title_de="Halle 3", order=1,
            is_exhibition_floor=True,
            file=SimpleUploadedFile("hall3.png", _transparent_logo_png(),
                                    content_type="image/png"))
        cls.upper = Floorplan.objects.create(
            event=cls.event, title="Attic", order=2,
            file=SimpleUploadedFile("attic.pdf", b"%PDF-1.4 ", content_type="application/pdf"))

    def test_info_page_shows_every_level_in_order(self):
        body = self.client.get(reverse("core:info")).content.decode()
        self.assertLess(body.index("Hall 3"), body.index("Attic"))

    def test_only_the_flagged_level_counts_as_exhibition_floor(self):
        self.assertEqual(list(self.event.exhibition_floorplans), [self.expo])
        self.assertEqual(self.event.booth_floorplan, self.expo)

    def test_pdf_and_image_are_rendered_differently(self):
        body = self.client.get(reverse("core:info")).content.decode()
        self.assertIn("Open PDF", body)               # the attic plan
        self.assertIn(self.expo.file.url, body)       # the hall image, inline
        self.assertTrue(self.upper.is_pdf)
        self.assertFalse(self.expo.is_pdf)

    def test_german_label_is_used_when_available(self):
        self.client.cookies["django_language"] = "de"
        body = self.client.get(reverse("core:info")).content.decode()
        self.assertIn("Halle 3", body)
        self.assertIn("Attic", body)  # without a translation the source stays


# Without collectstatic the manifest storage does not know the admin assets.
# For this test the plain storage is enough: what is checked is the reference,
# not the hash.
@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class AdminIconHelpTests(TestCase):
    """Wer einen Info-Block anlegt, muss wissen, welche Icon-Namen es gibt.
    The icon field gets a preview and a link into the gallery for that."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("chief", "chief@example.org", "pw-12345")
        cls.event = Event.objects.create(
            name="Demo Summit 2026", slug="demo-2026",
            start_date=date(2026, 7, 8), end_date=date(2026, 7, 10),
        )

    def test_event_form_ships_the_icon_preview_assets(self):
        self.client.force_login(self.admin)
        body = self.client.get(
            reverse("admin:lma_core_event_change", args=[self.event.pk])).content.decode()
        self.assertIn("admin_icon_preview", body)
        self.assertIn("tabler-icons", body)

    def test_social_event_is_an_open_section_on_the_event_form(self):
        """The social event has no admin page of its own — it lives as a
        section on the event, and folded away at the bottom it was simply not
        findable."""
        self.client.force_login(self.admin)
        body = self.client.get(
            reverse("admin:lma_core_event_change", args=[self.event.pk])).content.decode()
        self.assertIn("Social Event", body)
        self.assertIn('name="social_event_title"', body)
        # The section comes before the tab visibility, i.e. in the top third …
        self.assertLess(body.index("social_event_title"), body.index("tab_program_enabled"))
        # … and is not collapsed.
        head = body[:body.index("social_event_title")]
        self.assertNotIn("collapse", head.rsplit("<fieldset", 1)[-1])


class EmergencyNumberTests(TestCase):
    """The emergency tile used to be hard-wired to 112 — wrong outside the
    EU. It now follows the event field and disappears when that is empty."""

    def _event(self, number):
        return Event.objects.create(
            name="Event", slug=f"ev-{number or 'none'}",
            start_date=date(2026, 7, 8), end_date=date(2026, 7, 10),
            is_published=True, emergency_number=number,
        )

    def test_tile_dials_the_configured_number(self):
        self._event("911")
        body = self.client.get(reverse("core:info")).content.decode()
        self.assertIn('href="tel:911"', body)
        self.assertIn("Emergency 911", body)

    def test_tile_disappears_when_number_is_empty(self):
        self._event("")
        body = self.client.get(reverse("core:info")).content.decode()
        self.assertNotIn("tel:", body)


class HealthzTests(TestCase):
    """The health endpoint is polled by external monitoring — it has to be
    reachable without a login and must never be cached."""

    def test_returns_ok_without_authentication(self):
        resp = self.client.get("/healthz")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content), {"status": "ok", "database": "ok"})

    def test_is_not_cacheable(self):
        resp = self.client.get("/healthz")
        self.assertIn("no-store", resp.headers.get("Cache-Control", ""))


class BackupRotationTests(SimpleTestCase):
    """Rotation decides which backups get deleted — a bug here deletes, in
    case of doubt, exactly the snapshot that was needed. Hence tested
    explicitly, without touching real files."""

    def _backups(self, stamps):
        """(datetime, Path)-Paare wie existing_backups() sie liefert: neueste zuerst."""
        items = [
            (stamp, Path(f"/tmp/db-{stamp:%Y%m%d-%H%M}.sqlite3.gz"))
            for stamp in stamps
        ]
        items.sort(key=lambda item: item[0], reverse=True)
        return items

    def test_keeps_everything_inside_the_hourly_window(self):
        now = datetime(2026, 9, 10, 18, 0)
        stamps = [now - timedelta(hours=h) for h in range(0, 40)]
        expired = select_expired(self._backups(stamps), now, keep_hourly=48, keep_daily=30)
        self.assertEqual(expired, [])

    def test_thins_older_backups_to_one_per_day(self):
        now = datetime(2026, 9, 10, 18, 0)
        # A day ten days back with four snapshots — exactly the newest of
        # them may survive, because it falls outside the hourly window.
        old_day = [datetime(2026, 8, 31, hour, 0) for hour in (8, 11, 14, 17)]
        expired = select_expired(self._backups(old_day), now, keep_hourly=48, keep_daily=30)
        self.assertEqual(
            [path.name for path in expired],
            ["db-20260831-1400.sqlite3.gz",
             "db-20260831-1100.sqlite3.gz",
             "db-20260831-0800.sqlite3.gz"],
        )

    def test_drops_backups_beyond_the_daily_window(self):
        now = datetime(2026, 9, 10, 18, 0)
        ancient = datetime(2026, 1, 1, 9, 0)
        expired = select_expired(self._backups([ancient]), now, keep_hourly=48, keep_daily=30)
        self.assertEqual([path.name for path in expired], ["db-20260101-0900.sqlite3.gz"])

    def test_never_empties_an_up_to_date_backup_directory(self):
        """As long as a current snapshot exists, rotation must not clear
        everything away — one would be left without a backup."""
        now = datetime(2026, 9, 10, 18, 0)
        stamps = [now - timedelta(hours=h) for h in range(0, 24 * 60, 3)]
        backups = self._backups(stamps)
        expired = select_expired(backups, now, keep_hourly=48, keep_daily=30)
        self.assertLess(len(expired), len(backups))
        remaining = [path for _stamp, path in backups if path not in expired]
        self.assertIn(backups[0][1], remaining)

    def test_parse_timestamp_ignores_foreign_files(self):
        self.assertIsNone(parse_timestamp(Path("/tmp/README.md")))
        self.assertIsNone(parse_timestamp(Path("/tmp/db-kaputt.sqlite3.gz")))
        self.assertEqual(
            parse_timestamp(Path("/tmp/db-20260910-1400.sqlite3.gz")),
            datetime(2026, 9, 10, 14, 0),
        )


class BackupCommandTests(TestCase):
    """End to end against a real SQLite file: the snapshot has to actually
    contain the data and pass the integrity check."""

    def test_creates_verifiable_backup_containing_the_data(self):
        Event.objects.create(
            name="Backup Probe", slug="backup-probe",
            start_date=date(2026, 7, 8), end_date=date(2026, 7, 10),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.sqlite3"
            conn = sqlite3.connect(source)
            conn.execute("CREATE TABLE probe (id INTEGER PRIMARY KEY, label TEXT)")
            conn.execute("INSERT INTO probe (label) VALUES ('konferenz')")
            conn.commit()
            conn.close()

            target = Path(tmpdir) / "backups"
            with override_settings(
                DATABASES={"default": {
                    "ENGINE": "django.db.backends.sqlite3", "NAME": str(source),
                }}
            ), mock.patch.dict(os.environ, {"DJANGO_BACKUP_DIR": str(target)}):
                call_command("backup_db", verbosity=0)

            written = list(target.glob("db-*.sqlite3.gz"))
            self.assertEqual(len(written), 1)
            # No temporary files left behind.
            self.assertEqual(list(target.glob(".*tmp")), [])

            restored = Path(tmpdir) / "restored.sqlite3"
            with gzip.open(written[0], "rb") as src, open(restored, "wb") as dst:
                shutil.copyfileobj(src, dst)
            conn = sqlite3.connect(restored)
            self.assertEqual(conn.execute("SELECT label FROM probe").fetchone()[0], "konferenz")
            conn.close()

            ok, detail = integrity_ok(restored)
            self.assertTrue(ok, detail)

    def test_refuses_non_sqlite_engines(self):
        with override_settings(
            DATABASES={"default": {"ENGINE": "django.db.backends.mysql", "NAME": "demo"}}
        ), self.assertRaises(CommandError):
            call_command("backup_db", verbosity=0)

    def test_backup_files_are_not_world_readable(self):
        """A backup is a full copy of personal data — neither the directory
        nor the file may be readable by others."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.sqlite3"
            sqlite3.connect(source).close()

            target = Path(tmpdir) / "backups"
            with override_settings(
                DATABASES={"default": {
                    "ENGINE": "django.db.backends.sqlite3", "NAME": str(source),
                }}
            ), mock.patch.dict(os.environ, {"DJANGO_BACKUP_DIR": str(target)}):
                call_command("backup_db", verbosity=0)

            written = next(target.glob("db-*.sqlite3.gz"))
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(written.stat().st_mode), 0o600)


class BackupMediaTests(TestCase):
    """Media backup: weekly rhythm, its own archive, the same file
    permissions as the database backups."""

    def _media_tree(self, root: Path) -> None:
        (root / "events" / "logos").mkdir(parents=True)
        (root / "events" / "logos" / "demo.png").write_bytes(b"\x89PNG-nicht-echt")
        (root / "speakers").mkdir()
        (root / "speakers" / "portrait.jpg").write_bytes(b"\xff\xd8jpeg-nicht-echt")

    def test_archives_media_tree_and_can_be_read_back(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            media = Path(tmpdir) / "media"
            media.mkdir()
            self._media_tree(media)
            target = Path(tmpdir) / "backups"

            with override_settings(MEDIA_ROOT=str(media)), \
                    mock.patch.dict(os.environ, {"DJANGO_BACKUP_DIR": str(target)}):
                call_command("backup_media", verbosity=0)

            written = list(target.glob("media-*.tar.gz"))
            self.assertEqual(len(written), 1)
            self.assertEqual(list(target.glob(".*tmp")), [])
            self.assertEqual(stat.S_IMODE(written[0].stat().st_mode), 0o600)

            with tarfile.open(written[0]) as tar:
                names = tar.getnames()
            self.assertIn("media/events/logos/demo.png", names)
            self.assertIn("media/speakers/portrait.jpg", names)

    def test_empty_media_root_writes_no_archive(self):
        """A fresh installation has no uploads yet — an empty archive would
        only be misleading."""
        with tempfile.TemporaryDirectory() as tmpdir:
            media = Path(tmpdir) / "media"
            media.mkdir()
            target = Path(tmpdir) / "backups"

            with override_settings(MEDIA_ROOT=str(media)), \
                    mock.patch.dict(os.environ, {"DJANGO_BACKUP_DIR": str(target)}):
                call_command("backup_media", verbosity=0)

            self.assertEqual(list(target.glob("media-*.tar.gz")) if target.exists() else [], [])

    def test_rotation_keeps_only_the_requested_number(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "backups"
            target.mkdir()
            for day in range(1, 13):
                (target / f"media-202609{day:02d}-0345.tar.gz").write_bytes(b"x")

            media = Path(tmpdir) / "media"
            media.mkdir()
            self._media_tree(media)

            with override_settings(MEDIA_ROOT=str(media)), \
                    mock.patch.dict(os.environ, {"DJANGO_BACKUP_DIR": str(target)}):
                call_command("backup_media", keep=4, verbosity=0)

            remaining = sorted(p.name for p in target.glob("media-*.tar.gz"))
            self.assertEqual(len(remaining), 4)
            # The four newest survive — including the one just created.
            self.assertIn("media-20260912-0345.tar.gz", remaining)
            self.assertNotIn("media-20260901-0345.tar.gz", remaining)

    def test_corrupt_archive_is_reported(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            broken = Path(tmpdir) / "media-20260901-0345.tar.gz"
            broken.write_bytes(b"das ist kein gzip-tar")
            ok, detail = archive_ok(broken)
            self.assertFalse(ok, detail)

    def test_missing_media_root_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with override_settings(MEDIA_ROOT=str(Path(tmpdir) / "gibtsnicht")), \
                    self.assertRaises(CommandError):
                call_command("backup_media", verbosity=0)


class SeedDemoCommandTests(TestCase):
    """`seed_demo` is the first thing anyone runs after cloning, so a failure
    in it is a failure of the whole quick start."""

    def test_it_runs_and_is_idempotent(self):
        call_command("seed_demo", verbosity=0)
        event = Event.objects.get(slug="demo-conference")
        self.assertTrue(event.is_published)
        self.assertTrue(event.sessions.exists())
        self.assertTrue(event.sponsors.exists())
        self.assertTrue(event.abstract_awards.filter(is_audience_choice=True).exists())

        counts = (Event.objects.count(), event.sessions.count(),
                  event.sponsors.count(), event.abstracts.count())
        call_command("seed_demo", verbosity=0)
        event.refresh_from_db()
        self.assertEqual(
            (Event.objects.count(), event.sessions.count(),
             event.sponsors.count(), event.abstracts.count()),
            counts, "a second run must not duplicate anything")

    def test_demo_data_names_nobody_real(self):
        """The seed ships in a public repository. Real people and real
        companies do not belong in it — this test is the tripwire."""
        call_command("seed_demo", verbosity=0)
        haystack = " ".join([
            *Event.objects.values_list("name", flat=True),
            *Event.objects.values_list("organizer_name", flat=True),
            *User.objects.values_list("first_name", flat=True),
            *User.objects.values_list("last_name", flat=True),
        ])
        for forbidden in ("Cadamuro", "LabMed", "Roche", "Siemens", "Werfen", "D4"):
            self.assertNotIn(forbidden, haystack)


class BrandPaletteTests(TestCase):
    """The five brand colours drive the interface. If changing them in the
    admin does not change the rendered CSS, the whole point of moving them out
    of base.html is lost."""

    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Palette Test", slug="palette-test",
            start_date=date(2026, 7, 8), end_date=date(2026, 7, 10),
            is_published=True,
            theme_color="#112233", accent_color="#445566",
            highlight_color="#778899", surface_color="#aabbcc",
            text_color="#ddeeff",
        )

    def test_event_colours_reach_the_stylesheet(self):
        body = self.client.get(reverse("core:home")).content.decode()
        for value in ("#112233", "#445566", "#778899", "#aabbcc", "#ddeeff"):
            self.assertIn(value, body, f"{value} missing from the rendered palette")
        # And the RGB triple Tabler needs, derived from the primary colour.
        self.assertIn("--lma-primary-rgb:   17, 34, 51", body)

    def test_no_css_needs_color_mix(self):
        """color-mix() only works from Safari 16.2. An invalid custom property
        takes its whole declaration with it, so an attendee on an older phone
        would get unstyled controls rather than slightly-off colours — every
        shade is computed server-side instead."""
        for url in (reverse("core:home"), reverse("core:welcome"),
                    reverse("core:info"), reverse("program:list")):
            with self.subTest(url=url):
                self.assertNotIn("color-mix", self.client.get(url).content.decode())

    def test_templates_do_not_hard_code_the_shipped_palette(self):
        """A literal brand colour in a template is a colour another conference
        cannot change. 500.html is the documented exception — Django renders it
        without a request, so there is no event to read."""
        shipped = ("#457b9d", "#fe5f55", "#ffcf4d")
        offenders = []
        for path in Path("templates").rglob("*.html"):
            if path.name in {"500.html", "_brand_palette.html"}:
                continue
            text = path.read_text()
            offenders += [f"{path}: {c}" for c in shipped if c in text]
        for path in Path("lma_connect").rglob("*.html"):
            text = path.read_text()
            offenders += [f"{path}: {c}" for c in shipped if c in text]
        self.assertEqual(offenders, [])

class AttributionTests(TestCase):
    """The app's provenance is hard-coded, not event data. These tests exist so
    a later re-branding, a template cleanup or a fork cannot quietly drop the
    authorship, the licence or the source link the AGPL requires."""

    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Attribution Test", slug="attribution-test",
            start_date=date(2026, 7, 8), end_date=date(2026, 7, 10),
            is_published=True, organizer_name="Some Other Organizer",
            copyright_holder="Some Other Organizer",
        )

    def test_about_page_names_authors_licence_and_source(self):
        resp = self.client.get(reverse("core:about"))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        for needle in (meta.APP_NAME, meta.AUTHOR, meta.ORGANIZATION,
                       meta.LICENSE_SPDX, meta.SOURCE_URL, meta.VERSION):
            self.assertIn(needle, body, f"{needle} missing from /about/")

    def test_footer_credits_the_app_on_every_page(self):
        for url in (reverse("core:home"), reverse("core:info"),
                    reverse("core:help"), reverse("program:list")):
            with self.subTest(url=url):
                body = self.client.get(url).content.decode()
                self.assertIn(meta.APP_NAME, body)
                self.assertIn(meta.LICENSE_SPDX, body)
                self.assertIn(reverse("core:about"), body)

    def test_welcome_splash_credits_the_app_too(self):
        """The splash screen does not extend base.html — it carries its own
        copy of the credit line, which is easy to forget when editing it."""
        body = self.client.get(reverse("core:welcome")).content.decode()
        self.assertIn(meta.APP_NAME, body)
        self.assertIn(reverse("core:about"), body)

    def test_credit_survives_without_a_configured_event(self):
        """No event, no organizer branding — the attribution still shows. The
        footer used to render only inside an `{% if event %}`."""
        Event.objects.all().delete()
        body = self.client.get(reverse("core:home")).content.decode()
        self.assertIn(meta.APP_NAME, body)
        self.assertIn(meta.LICENSE_SPDX, body)

    def test_organizer_branding_does_not_replace_the_app_credit(self):
        """The organizer's own copyright line and the app's credit are two
        different statements and both have to be readable."""
        body = self.client.get(reverse("core:home")).content.decode()
        self.assertIn("Some Other Organizer", body)
        self.assertIn(meta.COPYRIGHT_HOLDER, body)

    def test_licence_file_is_the_agpl_and_version_matches_pyproject(self):
        root = Path(__file__).resolve().parents[3]
        licence = (root / "LICENSE").read_text()
        self.assertIn("GNU AFFERO GENERAL PUBLIC LICENSE", licence)
        self.assertIn("Version 3, 19 November 2007", licence)
        pyproject = (root / "pyproject.toml").read_text()
        self.assertIn(f'license = "{meta.LICENSE_SPDX}"', pyproject)
        self.assertIn(f'version = "{meta.VERSION}"', pyproject)


class LoadLegalPagesCommandTests(TestCase):
    """load_legal_pages: validation that does not depend on event-specific texts."""

    def setUp(self):
        self.event = Event.objects.create(
            name="Demo Conference", slug="demo-conf", is_published=True,
            start_date=date(2026, 9, 11), end_date=date(2026, 9, 12))

    def test_rejects_invalid_slug_filename(self):
        """A bad slug would not fail here but in every footer's {% url %}."""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "bad slug.en.md").write_text("# X\n\nbody\n")
            with self.assertRaises(CommandError):
                call_command("load_legal_pages", "--dir", d, "--event", self.event.slug)
