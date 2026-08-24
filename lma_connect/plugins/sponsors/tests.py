"""Bilingual sponsor copy.

The rule (core.models.TranslatedTextMixin): the primary field holds the source
language — German here, because that is what sponsors deliver — and `<name>_en`
the translation. An empty EN field falls back to the source, so an English
reader never sees an empty bio, only an untranslated one.
"""

import base64
import datetime
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.translation import override

from lma_connect.plugins.core.models import Event, Floorplan

from .models import Sponsor, SponsorContact, SponsorDownload, SponsorImage, SponsorLink


class SponsorLocalizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Demo Summit", slug="demo", is_published=True,
            start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2026, 9, 3),
        )
        cls.sponsor = Sponsor.objects.create(
            event=cls.event, name="Roche", slug="roche", is_published=True,
            bio_short="Diagnostik aus Basel",
            bio_short_en="Diagnostics from Basel",
            bio_long="Ausführliche deutsche Bio",
            bio_long_en="Full English bio",
            highlights_md="- Neuheit A",
            highlights_md_en="- Novelty A",
            booth_location="Foyer A — Stand B12",
            booth_location_en="Foyer A — Booth B12",
        )

    def test_german_uses_primary_fields(self):
        with override("de"):
            self.assertEqual(self.sponsor.localized_bio_short, "Diagnostik aus Basel")
            self.assertEqual(self.sponsor.localized_bio_long, "Ausführliche deutsche Bio")
            self.assertEqual(self.sponsor.localized_highlights_md, "- Neuheit A")
            self.assertEqual(self.sponsor.localized_booth_location, "Foyer A — Stand B12")

    def test_english_uses_translation_fields(self):
        with override("en"):
            self.assertEqual(self.sponsor.localized_bio_short, "Diagnostics from Basel")
            self.assertEqual(self.sponsor.localized_bio_long, "Full English bio")
            self.assertEqual(self.sponsor.localized_highlights_md, "- Novelty A")
            self.assertEqual(self.sponsor.localized_booth_location, "Foyer A — Booth B12")

    def test_english_falls_back_to_german_when_untranslated(self):
        untranslated = Sponsor.objects.create(
            event=self.event, name="Werfen", slug="werfen", is_published=True,
            bio_short="Nur deutsch gepflegt", bio_long="Auch nur deutsch",
        )
        with override("en"):
            self.assertEqual(untranslated.localized_bio_short, "Nur deutsch gepflegt")
            self.assertEqual(untranslated.localized_bio_long, "Auch nur deutsch")

    def test_whitespace_only_translation_is_not_used(self):
        """A field accidentally filled with spaces must not displace the
        source text — otherwise the English page shows nothing at all."""
        self.sponsor.bio_short_en = "   "
        with override("en"):
            self.assertEqual(self.sponsor.localized_bio_short, "Diagnostik aus Basel")

    def test_related_models_localize(self):
        image = SponsorImage.objects.create(
            sponsor=self.sponsor, image="sponsors/images/x.jpg",
            caption="Unser Labor", caption_en="Our lab",
        )
        contact = SponsorContact.objects.create(
            sponsor=self.sponsor, name="A. Muster",
            role="Vertrieb", role_en="Sales",
            expertise="Hämatologie", expertise_en="Haematology",
        )
        link = SponsorLink.objects.create(
            sponsor=self.sponsor, url="https://example.org",
            label="Produktseite", label_en="Product page",
            description="Mehr Infos", description_en="More info",
        )
        download = SponsorDownload.objects.create(
            sponsor=self.sponsor, file="sponsors/downloads/x.pdf",
            title="Datenblatt", title_en="Datasheet",
            description="PDF, 2 Seiten", description_en="PDF, 2 pages",
        )
        with override("en"):
            self.assertEqual(image.localized_caption, "Our lab")
            self.assertEqual(contact.localized_role, "Sales")
            self.assertEqual(contact.localized_expertise, "Haematology")
            self.assertEqual(link.localized_label, "Product page")
            self.assertEqual(link.localized_description, "More info")
            self.assertEqual(download.localized_title, "Datasheet")
            self.assertEqual(download.localized_description, "PDF, 2 pages")
        with override("de"):
            self.assertEqual(image.localized_caption, "Unser Labor")
            self.assertEqual(contact.localized_role, "Vertrieb")
            self.assertEqual(link.localized_label, "Produktseite")
            self.assertEqual(download.localized_title, "Datenblatt")


class SponsorViewLocalizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Demo Summit", slug="demo", is_published=True,
            start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2026, 9, 3),
        )
        cls.sponsor = Sponsor.objects.create(
            event=cls.event, name="Roche", slug="roche", is_published=True,
            bio_short="Diagnostik aus Basel", bio_short_en="Diagnostics from Basel",
            bio_long="Deutsche Langbio", bio_long_en="English long bio",
            highlights_md="- Neuheit A", highlights_md_en="- Novelty A",
            booth_location="Foyer A — Stand B12", booth_location_en="Foyer A — Booth B12",
        )

    def test_detail_page_renders_english(self):
        response = self.client.get(
            reverse("sponsors:detail", kwargs={"slug": "roche"}),
            headers={"accept-language": "en"},
        )
        self.assertContains(response, "Diagnostics from Basel")
        self.assertContains(response, "English long bio")
        self.assertContains(response, "Novelty A")
        self.assertContains(response, "Foyer A — Booth B12")
        self.assertNotContains(response, "Deutsche Langbio")

    def test_detail_page_renders_german(self):
        # German is only reachable through the switcher cookie — the
        # Accept-Language header is deliberately ignored.
        self.client.cookies["django_language"] = "de"
        response = self.client.get(
            reverse("sponsors:detail", kwargs={"slug": "roche"}),
        )
        self.assertContains(response, "Deutsche Langbio")
        self.assertNotContains(response, "English long bio")

    def test_list_page_renders_english_short_bio(self):
        response = self.client.get(
            reverse("sponsors:list"), headers={"accept-language": "en"},
        )
        self.assertContains(response, "Diagnostics from Basel")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class BoothCardTests(TestCase):
    """"Where to find us" is tied to having a booth.

    Sponsors without one (logo-only sponsors) get neither the card nor the
    floorplan on their detail page — the plan would otherwise point at a
    location this sponsor does not have.
    """

    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Demo Summit", slug="demo", is_published=True,
            start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2026, 9, 3),
        )
        cls.plan = Floorplan.objects.create(
            event=cls.event, title="Ground floor", is_exhibition_floor=True,
            file=SimpleUploadedFile(
                "plan.png",
                base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
                ),
                content_type="image/png",
            ),
        )

    def _detail(self, sponsor: Sponsor):
        return self.client.get(sponsor.get_absolute_url())

    def test_logo_sponsor_without_booth_shows_no_map(self):
        sponsor = Sponsor.objects.create(
            event=self.event, name="Werfen", slug="werfen", is_published=True,
            bio_short="Nur Logo-Sponsoring",
        )
        response = self._detail(sponsor)
        self.assertNotContains(response, "Where to find us")
        self.assertNotContains(response, self.event.booth_floorplan.file.url)

    def test_stale_coordinates_alone_do_not_bring_the_map_back(self):
        """Leftover coordinates without a location used to be enough to
        bring the map back."""
        sponsor = Sponsor.objects.create(
            event=self.event, name="Siemens", slug="siemens", is_published=True,
            booth_x="0.4000", booth_y="0.6000",
        )
        response = self._detail(sponsor)
        self.assertNotContains(response, "Where to find us")
        self.assertNotContains(response, self.event.booth_floorplan.file.url)

    def test_exhibitor_with_coordinates_gets_map_and_marker(self):
        sponsor = Sponsor.objects.create(
            event=self.event, name="Roche", slug="roche", is_published=True,
            booth_location="Foyer A — Stand A1", booth_x="0.1800", booth_y="0.3200",
        )
        response = self._detail(sponsor)
        self.assertContains(response, "Where to find us")
        self.assertContains(response, self.event.booth_floorplan.file.url)
        self.assertContains(response, "Booth marker")

    def test_exhibitor_without_coordinates_gets_location_but_no_image_plan(self):
        """Without a marker the plan would say nothing — but the location
        text stays regardless."""
        sponsor = Sponsor.objects.create(
            event=self.event, name="Abbott", slug="abbott", is_published=True,
            booth_location="Foyer B — Stand B7",
        )
        response = self._detail(sponsor)
        self.assertContains(response, "Foyer B — Stand B7")
        self.assertNotContains(response, self.event.booth_floorplan.file.url)

    def test_zero_coordinates_are_a_valid_marker(self):
        """0.0 = linker/oberer Rand, nicht „nicht gepflegt"."""
        sponsor = Sponsor.objects.create(
            event=self.event, name="Beckman", slug="beckman", is_published=True,
            booth_location="Eingang", booth_x="0.0000", booth_y="0.0000",
        )
        self.assertTrue(sponsor.has_booth_marker)
        self.assertContains(self._detail(sponsor), "Booth marker")


class EventLocalizationRegressionTests(TestCase):
    """Der Mixin-Umbau darf die bestehende EN→DE-Richtung beim Event nicht drehen."""

    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Demo Summit", slug="demo", is_published=True,
            start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2026, 9, 3),
            subtitle="Digital diagnostics", subtitle_de="Digitale Diagnostik",
            description="English description",
        )

    def test_german_prefers_de_field(self):
        with override("de"):
            self.assertEqual(self.event.localized_subtitle, "Digitale Diagnostik")

    def test_english_uses_source_field(self):
        with override("en"):
            self.assertEqual(self.event.localized_subtitle, "Digital diagnostics")

    def test_german_falls_back_to_source_when_untranslated(self):
        with override("de"):
            self.assertEqual(self.event.localized_description, "English description")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class FeaturedSponsorTests(TestCase):
    """Headline sponsor placement (Event.featured_sponsors) on the welcome
    screen and in the home page hero."""

    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Demo Summit", slug="demo", is_published=True,
            start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2026, 9, 3),
        )

    @staticmethod
    def _logo(name: str = "roche.png") -> SimpleUploadedFile:
        # A 1x1 PNG is enough: only the file path reaches the template.
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        return SimpleUploadedFile(name, png, content_type="image/png")

    def _make(self, slug: str, **kwargs) -> Sponsor:
        defaults = {"is_published": True, "is_featured": True, "logo": self._logo(f"{slug}.png")}
        defaults.update(kwargs)
        return Sponsor.objects.create(
            event=self.event, name=slug.title(), slug=slug, **defaults,
        )

    def test_featured_requires_flag_publication_and_logo(self):
        wanted = self._make("roche")
        self._make("not-flagged", is_featured=False)
        self._make("draft", is_published=False)
        self._make("no-logo", logo=None)
        self.assertEqual(list(self.event.featured_sponsors), [wanted])

    def test_logo_appears_on_welcome_screen(self):
        sponsor = self._make("roche")
        response = self.client.get(reverse("core:welcome"))
        self.assertContains(response, sponsor.logo.url)

    def test_logo_appears_in_home_hero(self):
        sponsor = self._make("roche")
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, sponsor.logo.url)
        # Linked in the hero — deliberately not on the welcome screen.
        self.assertContains(response, sponsor.get_absolute_url())

    def test_no_featured_sponsor_renders_nothing_extra(self):
        self._make("not-flagged", is_featured=False)
        self.assertNotContains(
            self.client.get(reverse("core:welcome")), 'class="welcome-sponsors"',
        )


class WebpConversionTests(TestCase):
    """sponsors.images.to_webp — the rules both import commands rely on."""

    @staticmethod
    def _png(mode, size, **info):
        from io import BytesIO

        from PIL import Image
        buf = BytesIO()
        Image.new(mode, size, (200, 30, 30, 128) if mode == "RGBA" else (200, 30, 30)).save(buf, "PNG")
        buf.seek(0)
        return buf

    def _open(self, data):
        from io import BytesIO

        from PIL import Image
        return Image.open(BytesIO(data))

    def test_caps_width_and_keeps_aspect_ratio(self):
        from lma_connect.plugins.sponsors.images import to_webp
        img = self._open(to_webp(self._png("RGB", (3200, 1600)), "image"))
        self.assertEqual(img.format, "WEBP")
        self.assertEqual(img.size, (1600, 800))

    def test_small_images_are_not_upscaled(self):
        from lma_connect.plugins.sponsors.images import to_webp
        self.assertEqual(self._open(to_webp(self._png("RGB", (300, 100)), "logo")).size, (300, 100))

    def test_alpha_survives_for_logos(self):
        from lma_connect.plugins.sponsors.images import to_webp
        img = self._open(to_webp(self._png("RGBA", (100, 50)), "logo"))
        self.assertEqual(img.mode, "RGBA")
        self.assertEqual(img.getpixel((0, 0))[3], 128)

    def test_cmyk_jpeg_becomes_rgb(self):
        from io import BytesIO

        from PIL import Image

        from lma_connect.plugins.sponsors.images import to_webp
        buf = BytesIO()
        Image.new("CMYK", (100, 100)).save(buf, "JPEG")
        buf.seek(0)
        self.assertEqual(self._open(to_webp(buf, "logo")).mode, "RGB")

    def test_unreadable_file_raises_oserror(self):
        from io import BytesIO

        from lma_connect.plugins.sponsors.images import to_webp
        with self.assertRaises(OSError):
            to_webp(BytesIO(b"%PDF-1.4 not an image"), "image")
