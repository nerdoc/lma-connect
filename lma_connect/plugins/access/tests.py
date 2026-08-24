"""Tests for the ops frontend — currently the publish toggle for abstracts,
the admin grouping and the onboarding acceptance step."""

import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from lma_connect.plugins.abstracts.models import Abstract
from lma_connect.plugins.core.models import Event

from .models import AccessToken
from .permissions import OPS_GROUP_NAME

User = get_user_model()


class AbstractPublishToggleTests(TestCase):
    def setUp(self):
        self.event = Event.objects.create(
            name="Demo Test", slug="demo-test",
            start_date=datetime.date(2026, 9, 1), end_date=datetime.date(2026, 9, 3),
            is_published=True,
        )
        self.abstract = Abstract.objects.create(
            event=self.event, title="Machine learning in the core lab",
            slug="ml-core-lab", abstract_text="…", poster_id="P-001",
        )
        ops_group = Group.objects.create(name=OPS_GROUP_NAME)
        self.ops_user = User.objects.create_user("opsuser", password="x")
        self.ops_user.groups.add(ops_group)
        self.plain_user = User.objects.create_user("attendee", password="x")
        self.url = reverse("access:ops_abstract_toggle_publish",
                           kwargs={"abstract_id": self.abstract.pk})

    def test_toggle_publishes_and_unpublishes(self):
        self.client.force_login(self.ops_user)
        self.client.post(self.url)
        self.abstract.refresh_from_db()
        self.assertTrue(self.abstract.is_published)

        self.client.post(self.url)
        self.abstract.refresh_from_db()
        self.assertFalse(self.abstract.is_published)

    def test_counter_only_rendered_when_requested(self):
        self.client.force_login(self.ops_user)
        without = self.client.post(self.url)
        self.assertNotContains(without, "publish-counter")

        with_counter = self.client.post(self.url, {"with_counter": "1"})
        self.assertContains(with_counter, "publish-counter")

    def test_ops_pages_render_toggle(self):
        self.client.force_login(self.ops_user)
        for url in (reverse("access:ops_abstracts"),
                    reverse("access:ops_abstract_detail", kwargs={"abstract_id": self.abstract.pk})):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, self.url)

    def test_get_is_rejected(self):
        self.client.force_login(self.ops_user)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_non_ops_user_cannot_toggle(self):
        self.client.force_login(self.plain_user)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.abstract.refresh_from_db()
        self.assertFalse(self.abstract.is_published)

    def test_published_abstract_appears_in_public_list(self):
        """The toggle is the only thing deciding public visibility — the
        workflow status is deliberately left untouched."""
        response = self.client.get(reverse("abstracts:list"))
        self.assertNotContains(response, "Machine learning in the core lab")

        self.client.force_login(self.ops_user)
        self.client.post(self.url)
        self.client.logout()

        response = self.client.get(reverse("abstracts:list"))
        self.assertContains(response, "Machine learning in the core lab")
        self.abstract.refresh_from_db()
        self.assertEqual(self.abstract.status, "submitted")


# Without collectstatic the manifest storage does not know the admin assets.
@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class AdminIndexGroupingTests(TestCase):
    """django-axes used to add its own "AXES" box to the admin index — a
    second block on the same subject as "Access": who gets in. The models now
    hang under Access as proxies."""

    def setUp(self):
        self.admin = User.objects.create_superuser("chief", "chief@example.org", "pw-12345")
        self.client.force_login(self.admin)

    def test_axes_models_live_under_access(self):
        index = self.client.get(reverse("admin:index")).content.decode()
        self.assertIn("Failed login attempts", index)
        # The proxy link points at the access app, not at axes.
        self.assertIn("/admin/lma_access/loginattempt/", index)
        self.assertNotIn("/admin/axes/", index)


class NicknameSetupTermsTests(TestCase):
    """The terms of use have to be incorporated during onboarding.

    Without a notice next to the button, the liability limitation and the
    choice of law in the terms may never become part of the contract at all,
    for want of the user having seen them — and the nickname dialogue is the
    only point at which an attendee enters into that contract.
    """

    def setUp(self):
        self.event = Event.objects.create(
            name="Demo Test", slug="demo-terms",
            start_date=datetime.date(2026, 9, 1), end_date=datetime.date(2026, 9, 3),
            is_published=True,
        )
        self.token = AccessToken.objects.create(event=self.event)
        self.url = reverse("access:redeem", kwargs={"token": self.token.token})

    def test_setup_page_links_terms_and_privacy(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("core:legal", kwargs={"slug": "terms"}))
        self.assertContains(response, reverse("core:legal", kwargs={"slug": "privacy"}))
        self.assertContains(response, "By continuing you accept")

    def test_hint_is_translated_for_german_visitors(self):
        """A notice nobody understands incorporates nothing."""
        self.client.cookies["django_language"] = "de"
        response = self.client.get(self.url)
        self.assertContains(response, "Nutzungsbedingungen")
        self.assertContains(response, "Datenschutzerklärung")

    def test_hint_gone_once_the_token_is_redeemed(self):
        """Once redeemed the same link goes straight through — the
        acceptance step must not repeat itself."""
        self.client.post(self.url, {"nickname": "LabFan42"})
        self.token.refresh_from_db()
        self.assertIsNotNone(self.token.user)

        again = self.client.get(self.url)
        self.assertRedirects(again, reverse("core:home"))
