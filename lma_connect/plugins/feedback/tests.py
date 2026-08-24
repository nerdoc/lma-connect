"""Bilingual survey texts: German twins win for German visitors, empty twins
fall back to the English source."""

import datetime

from django.conf import settings
from django.test import TestCase
from django.utils import translation

from lma_connect.plugins.core.models import Event

from .models import EventSurvey, QuestionType, SurveyChoice, SurveyQuestion


class LocalizedSurveyTextsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = Event.objects.create(
            name="Demo", slug="demo", is_published=True,
            start_date=datetime.date(2026, 9, 1), end_date=datetime.date(2026, 9, 3))
        cls.survey = EventSurvey.objects.create(
            event=cls.event, slug="post", title="Your feedback", title_de="Ihr Feedback",
            intro_text="Three minutes.", is_published=True,
        )
        cls.q = SurveyQuestion.objects.create(
            survey=cls.survey, order=1, type=QuestionType.LIKERT_5,
            text="How were the session lengths?", text_de="Wie waren die Session-Längen?",
            likert_min_label="too short", likert_min_label_de="zu kurz",
            likert_max_label="too long",  # no DE twin → fallback
        )
        cls.choice_q = SurveyQuestion.objects.create(
            survey=cls.survey, order=2, type=QuestionType.SINGLE_CHOICE,
            text="Topic?", text_de="Thema?",
        )
        cls.choice = SurveyChoice.objects.create(
            question=cls.choice_q, order=1, text="Genomics", text_de="Genomik")

    def test_english_returns_source(self):
        with translation.override("en"):
            self.assertEqual(self.survey.localized_title, "Your feedback")
            self.assertEqual(self.q.localized_text, "How were the session lengths?")
            self.assertEqual(self.q.localized_likert_min_label, "too short")
            self.assertEqual(self.choice.localized_text, "Genomics")

    def test_german_prefers_de_fields_and_falls_back(self):
        with translation.override("de"):
            self.assertEqual(self.survey.localized_title, "Ihr Feedback")
            self.assertEqual(self.survey.localized_intro_text, "Three minutes.")  # fallback
            self.assertEqual(self.q.localized_text, "Wie waren die Session-Längen?")
            self.assertEqual(self.q.localized_likert_min_label, "zu kurz")
            self.assertEqual(self.q.localized_likert_max_label, "too long")  # fallback
            self.assertEqual(self.choice.localized_text, "Genomik")

    def test_detail_view_renders_german_texts(self):
        # Language comes from the switcher cookie only (DefaultLanguageMiddleware).
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "de"
        resp = self.client.get(f"/feedback/{self.survey.slug}/")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("Ihr Feedback", body)
        self.assertIn("Wie waren die Session-Längen?", body)
        self.assertIn("Genomik", body)
        self.assertNotIn("Genomics", body)
