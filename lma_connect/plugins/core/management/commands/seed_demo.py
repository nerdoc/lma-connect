"""Seed command: create a demo conference with example content.

Everything here is fictional on purpose. This file ships in a public
repository, so it must not contain real people, real institutions, real
companies or real credentials — a demo data set is not the place to publish
anyone's name, and a reader should never have to wonder whether "Acme
Diagnostics" is a genuine sponsor.

What it gives you: one published event, an info tab, rooms, two committees,
tracks, three speakers, a day of sessions with a live poll and Q&A, sponsor
tiers with three sponsors (one of them fully filled in, to show what a
complete sponsor page looks like), abstract categories and awards, two
abstracts and a feedback survey. Enough to see every screen with content in
it.

Idempotent — it can run repeatedly and overwrites nothing. To start over, run
`manage.py flush` or delete the event first.

Usage: python manage.py seed_demo
"""

from datetime import UTC, date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from lma_connect.plugins.abstracts.models import (
    Abstract,
    AbstractAuthor,
    AbstractAward,
    AbstractCategory,
    AbstractReference,
)
from lma_connect.plugins.core.models import (
    Committee,
    CommitteeMembership,
    CommitteeRole,
    Event,
    InfoBlock,
    Room,
)
from lma_connect.plugins.feedback.models import (
    EventSurvey,
    QuestionType,
    SurveyChoice,
    SurveyQuestion,
)
from lma_connect.plugins.people.models import PersonProfile, Speaker
from lma_connect.plugins.program.models import (
    LivePoll,
    LivePollOption,
    LivePollType,
    Question,
    Session,
    SessionChair,
    SessionRoleType,
    SessionSpeaker,
    SessionType,
    Track,
)
from lma_connect.plugins.sponsors.models import (
    Sponsor,
    SponsorContact,
    SponsorLink,
    SponsorTier,
)

User = get_user_model()


def _dt(d: date, h: int, m: int = 0):
    return datetime(d.year, d.month, d.day, h, m, tzinfo=UTC)


class Command(BaseCommand):
    help = "Seed a fictional demo conference (idempotent)."

    def handle(self, *args, **opts):
        # ── People ────────────────────────────────────────────────────
        # Fictional throughout; the email domains use .example, which is
        # reserved by RFC 2606 and can never belong to anyone.
        secretary, _ = User.objects.get_or_create(
            username="r.mercer",
            defaults={"first_name": "Robin", "last_name": "Mercer",
                      "email": "robin.mercer@example.test", "is_staff": True},
        )
        chair, _ = User.objects.get_or_create(
            username="p.okonkwo",
            defaults={"first_name": "Priya", "last_name": "Okonkwo"})
        speaker_a, _ = User.objects.get_or_create(
            username="a.lindqvist",
            defaults={"first_name": "Alex", "last_name": "Lindqvist"})
        speaker_b, _ = User.objects.get_or_create(
            username="s.duarte",
            defaults={"first_name": "Sam", "last_name": "Duarte"})

        # ── Event ─────────────────────────────────────────────────────
        # Dated a year out from today, so the demo never looks expired.
        start = date.today() + timedelta(days=365)
        event, created = Event.objects.get_or_create(
            slug="demo-conference",
            defaults=dict(
                name="Demo Conference",
                short_name="Demo 26",
                subtitle="A fictional conference to explore this app with",
                start_date=start,
                end_date=start + timedelta(days=1),
                timezone_name="Europe/Vienna",
                venue_name="Riverside Congress Centre",
                address="1 Riverside Walk",
                city="Norhaven",
                postal_code="10101",
                country="Austria",
                country_iso="AT",
                lat=47.811_944,
                lon=13.040_000,
                description="A demo event seeded by `manage.py seed_demo`. "
                            "Everything in it is made up.",
                homepage_url="https://conference.example.org",
                # The palette LMA Connect ships with; every event can change
                # all five colours in the admin.
                theme_color="#457b9d",
                accent_color="#fe5f55",
                organizer_name="Demo Society for Applied Nothing",
                organizing_secretary=secretary,
                is_published=True,
                emergency_number="112",
            ),
        )
        self.stdout.write(self.style.SUCCESS(
            f"Event: {event} ({'created' if created else 'exists'})"))

        # ── Info tab ──────────────────────────────────────────────────
        # The entire text part of the info tab, as a demonstration that
        # topics, order and icons come from the data and not the template.
        for order, block in enumerate((
            {
                "title": "How to get there",
                "icon": "train",
                "body": ("**By train:** Norhaven Central, then bus 4 or a taxi (~10 min).\n"
                         "**By car:** motorway exit Norhaven-Mitte, parking at the venue.\n"
                         "**Airport:** Norhaven Airport, 4 km, taxi ~12 min."),
                "title_de": "Anreise",
                "body_de": ("**Mit dem Zug:** Norhaven Hbf, dann Bus 4 oder Taxi (~10 Min).\n"
                            "**Mit dem Auto:** Autobahnabfahrt Norhaven-Mitte, Parken "
                            "direkt am Veranstaltungsort.\n"
                            "**Flughafen:** Norhaven Airport, 4 km, Taxi ~12 Min."),
            },
            {
                "title": "Around the venue",
                "icon": "camera",
                "body": ("- The old harbour and its warehouses\n"
                         "- Norhaven Botanical Garden\n"
                         "- The riverside walk, 20 minutes end to end\n"
                         "- Market square — coffee, books, cheese"),
                "title_de": "Rund um den Veranstaltungsort",
                "body_de": ("- Der alte Hafen und seine Speicher\n"
                            "- Botanischer Garten Norhaven\n"
                            "- Die Uferpromenade, 20 Minuten von Ende zu Ende\n"
                            "- Marktplatz — Kaffee, Bücher, Käse"),
            },
            {
                # Placeholders, not real credentials: this file lives in the
                # repository, and the actual guest access belongs solely in
                # the admin of the respective deployment.
                "title": "WiFi",
                "icon": "wifi",
                "body": ("**Network:** Conference-Guest\n\n"
                         "- Username: `<from the venue>`\n"
                         "- Password: `<from the venue>`\n"
                         "- Valid: for the duration of the event\n\n"
                         "_Replace this block with the real credentials in the admin._"),
                "title_de": "WLAN",
                "body_de": ("**Netzwerk:** Conference-Guest\n\n"
                            "- Benutzername: `<vom Veranstaltungsort>`\n"
                            "- Kennwort: `<vom Veranstaltungsort>`\n"
                            "- Gültig: für die Dauer der Veranstaltung\n\n"
                            "_Diesen Block im Admin durch die echten "
                            "Zugangsdaten ersetzen._"),
            },
            {
                "title": "Practical info",
                "icon": "info-circle",
                "body": "**Hashtag:** #DemoConference — share your impressions!",
                "title_de": "Praktische Infos",
                "body_de": "**Hashtag:** #DemoConference — gerne posten!",
            },
        ), start=1):
            InfoBlock.objects.get_or_create(
                event=event, title=block["title"],
                defaults={**block, "order": order * 10},
            )

        # ── Rooms ─────────────────────────────────────────────────────
        room_main, _ = Room.objects.get_or_create(
            event=event, slug="hall-a",
            defaults={"name": "Hall A", "capacity": 280, "floor": "Ground", "order": 1})
        Room.objects.get_or_create(
            event=event, slug="break-room-b",
            defaults={"name": "Break Room B", "capacity": 80, "floor": "Ground", "order": 2})
        room_foyer, _ = Room.objects.get_or_create(
            event=event, slug="foyer-poster",
            defaults={"name": "Foyer (poster walk)", "capacity": 0,
                      "floor": "Ground", "order": 3})

        # ── Committees ────────────────────────────────────────────────
        # Free-form per event, so pick names that fit yours.
        org_comm, _ = Committee.objects.get_or_create(
            event=event, slug="organizing",
            defaults={"name": "Organizing Committee", "order": 1})
        sci_comm, _ = Committee.objects.get_or_create(
            event=event, slug="scientific",
            defaults={"name": "Scientific Committee", "order": 2})

        for c, user, role, order in [
            (org_comm, secretary, CommitteeRole.SECRETARY, 1),
            (org_comm, chair, CommitteeRole.CHAIR, 0),
            (sci_comm, secretary, CommitteeRole.MEMBER, 1),
            (sci_comm, speaker_b, CommitteeRole.CHAIR, 0),
        ]:
            CommitteeMembership.objects.get_or_create(
                committee=c, user=user,
                defaults={"role": role, "order": order})

        # ── Tracks ────────────────────────────────────────────────────
        track_ai, _ = Track.objects.get_or_create(
            event=event, slug="data-and-methods",
            defaults={"name": "Data & Methods", "color": "#206bc4", "order": 1})
        track_pre, _ = Track.objects.get_or_create(
            event=event, slug="practice",
            defaults={"name": "Practice", "color": "#f59e0b", "order": 2})

        # ── Speaker profiles ──────────────────────────────────────────
        # Countries are set, which is what puts pins on the world map.
        for u, aff, country, ciso, intro, keynote, bio in [
            (speaker_a, "Riverside University Hospital", "Germany", "DE",
             "Data science in diagnostics", True,
             "Alex leads a working group on computational methods in "
             "diagnostics. Research interests: model validation, federated "
             "learning, and why most published models never reach a lab."),
            (speaker_b, "Institute of Applied Measurement", "Netherlands", "NL",
             "Measurement quality & stability", False,
             "Sam works on sample stability and pre-analytical error. "
             "Convinced that most of what goes wrong goes wrong before the "
             "instrument ever sees the sample."),
            (chair, "Norhaven Medical School", "Austria", "AT",
             "Protein diagnostics", False,
             "Priya runs the protein diagnostics group and chairs the panel "
             "discussion at this demo event."),
        ]:
            profile, pcreated = PersonProfile.objects.get_or_create(
                user=u, event=event,
                defaults={"affiliation": aff, "position": intro,
                          "country": country, "country_iso": ciso,
                          "profile_public": True, "bio": bio})
            if not pcreated:
                # Update the fields a re-run may have added since.
                profile.country = country
                profile.country_iso = ciso
                profile.bio = bio
                profile.save()
            Speaker.objects.get_or_create(
                profile=profile,
                defaults={"is_keynote": keynote, "affiliation": intro,
                          "talk_subjects": "data, diagnostics, quality"})

        # ── Sessions ──────────────────────────────────────────────────
        sessions_data = [
            ("Opening & welcome", SessionType.KEYNOTE, track_ai, room_main,
             9, 0, 9, 30, []),
            ("Machine learning in the lab — substance or hype?", SessionType.KEYNOTE,
             track_ai, room_main, 9, 30, 10, 30, [(speaker_a, SessionRoleType.SPEAKER)]),
            ("Coffee break & poster walk", SessionType.BREAK, None, room_foyer,
             10, 30, 11, 0, []),
            ("Sample stability: what ten years of data tell us", SessionType.TALK,
             track_pre, room_main, 11, 0, 11, 45, [(speaker_b, SessionRoleType.SPEAKER)]),
            ("Panel: how does automation change daily work?", SessionType.PANEL,
             track_ai, room_main, 11, 45, 12, 30,
             [(speaker_a, SessionRoleType.SPEAKER), (speaker_b, SessionRoleType.DISCUSSANT)]),
        ]
        for title, stype, tr, rm, sh, sm, eh, em, speakers in sessions_data:
            sess, _ = Session.objects.get_or_create(
                event=event, slug=slugify(title)[:200],
                defaults=dict(
                    track=tr, room=rm, title=title, type=stype,
                    starts_at=_dt(start, sh, sm), ends_at=_dt(start, eh, em),
                    summary=f"Demo session: {title}",
                    qa_enabled=stype != SessionType.BREAK,
                    rating_enabled=stype != SessionType.BREAK,
                    is_published=True),
            )
            for u, role in speakers:
                sp = Speaker.objects.get(profile__user=u, profile__event=event)
                SessionSpeaker.objects.get_or_create(
                    session=sess, speaker=sp, role=role, defaults={"order": 0})

        # ── Live poll and Q&A on the panel ────────────────────────────
        panel = Session.objects.filter(event=event, type=SessionType.PANEL).first()
        if panel:
            poll, pcreated = LivePoll.objects.get_or_create(
                session=panel,
                question_text="Which area benefits most from automation?",
                defaults={"type": LivePollType.SINGLE_CHOICE, "is_active": True,
                          "is_results_public": True},
            )
            if pcreated:
                for o, txt in enumerate([
                    "Result interpretation", "Quality control",
                    "Workflow", "Stability and pre-analytics",
                ], start=1):
                    LivePollOption.objects.create(poll=poll, text=txt, order=o)

            # Give the chair a known password so the chair panel can be tried
            # out straight away. Demo data only — see seed_group_users on why
            # trivial passwords never go near a production deployment.
            chair.set_password("chair")
            chair.save()
            SessionChair.objects.get_or_create(session=panel, user=chair)

            # A few demo questions, so the chair view and the public Q&A have
            # content. Unmoderated: every question is visible immediately. The
            # up-votes make the sort-by-popularity order meaningful.
            from lma_connect.plugins.program.models import QuestionUpvote
            voters = list(User.objects.all()[:5])
            demo_q = [
                ("How do you validate the training data against drift over time?", 4),
                ("What is the false-negative rate of your triage model in practice?", 2),
                ("Have you piloted this outside an academic setting yet?", 1),
                ("Which regulatory pathway did you choose?", 0),
            ]
            for i, (qtext, n_votes) in enumerate(demo_q):
                q, qcreated = Question.objects.get_or_create(
                    session=panel, text=qtext,
                    defaults={"asker_display_name": f"attendee{i + 1}",
                              "is_approved": True},
                )
                if qcreated:
                    for v in voters[:n_votes]:
                        QuestionUpvote.objects.get_or_create(question=q, user=v)

        # ── Sponsors ──────────────────────────────────────────────────
        gold, _ = SponsorTier.objects.get_or_create(
            event=event, slug="gold",
            defaults={"name": "Gold", "color": "#f59e0b", "price": 12000, "order": 1,
                      "perks_md": "- Prominent logo placement\n"
                                  "- 30 min speaking slot\n"
                                  "- Booth in the foyer"})
        silver, _ = SponsorTier.objects.get_or_create(
            event=event, slug="silver",
            defaults={"name": "Silver", "color": "#9ca3af", "price": 6000, "order": 2})

        sponsor_data = [
            ("Acme Diagnostics", "acme", gold,
             "Fictional manufacturer of fictional in-vitro diagnostics.",
             "Foyer A — booth A1", 0.18, 0.32,
             "- A new high-sensitivity assay that does not exist\n"
             "- A compact analyser that does not exist either\n"
             "- Result interpretation, allegedly assisted"),
            ("Helix Instruments", "helix", gold,
             "Fictional pioneer of imaging and lab automation.",
             "Foyer A — booth A2", 0.32, 0.32, ""),
            ("Vector Biotech", "vector", silver,
             "Fictional specialist for haemostasis and critical diagnostics.",
             "Foyer B — booth B7", 0.62, 0.55, ""),
        ]
        for name, slug, tier, bio, booth, bx, by, hl in sponsor_data:
            Sponsor.objects.get_or_create(
                event=event, slug=slug,
                defaults=dict(name=name, tier=tier, bio_short=bio,
                              bio_long=f"{bio} We look forward to meeting you.",
                              website=f"https://{slug}.example.com",
                              booth_location=booth, booth_x=bx, booth_y=by,
                              highlights_md=hl,
                              is_published=True, order=0))

        # One sponsor filled in completely — contacts and links — so the
        # detail page can be seen with everything switched on, rather than as
        # a page of empty sections.
        acme = Sponsor.objects.filter(event=event, slug="acme").first()
        if acme and not acme.contacts.exists():
            for o, (n, role, exp, mail) in enumerate([
                ("Dr. Mira Sandoval", "Regional Sales Manager",
                 "Haematology, clinical chemistry", "mira.sandoval@acme.example.com"),
                ("Dr. Tomás Reiner", "Medical Affairs",
                 "Molecular diagnostics, oncology", "tomas.reiner@acme.example.com"),
                ("Yuki Adeyemi", "Field Application Specialist",
                 "Workflow optimisation", "yuki.adeyemi@acme.example.com"),
            ], start=1):
                SponsorContact.objects.create(
                    sponsor=acme, name=n, role=role, expertise=exp, email=mail,
                    order=o,
                )

        if acme and not acme.links.exists():
            for o, (label, url, ltype, descr) in enumerate([
                ("Product page", "https://acme.example.com/analyser",
                 "product", "A modular platform, in the way of brochures"),
                ("Whitepaper: validating models", "https://acme.example.com/whitepaper",
                 "whitepaper", "Twenty pages nobody will read to the end"),
                ("Press release", "https://acme.example.com/press",
                 "news", "Quarterly figures and pipeline updates"),
            ], start=1):
                SponsorLink.objects.create(
                    sponsor=acme, label=label, url=url, type=ltype,
                    description=descr, order=o,
                )

        # ── Abstracts ─────────────────────────────────────────────────
        cat_diag, _ = AbstractCategory.objects.get_or_create(
            event=event, slug="diagnostics",
            defaults={"name": "Diagnostics", "color": "#206bc4", "order": 1})
        cat_ai, _ = AbstractCategory.objects.get_or_create(
            event=event, slug="methods",
            defaults={"name": "Computational methods", "color": "#8b5cf6", "order": 2})

        # Awards are per-event rows. Exactly one of them can be the audience
        # award — that is the one the star votes decide.
        for slug, name, audience, order in [
            ("best-poster", "Best Poster", False, 1),
            ("audience-choice", "Audience Choice Award", True, 2),
        ]:
            AbstractAward.objects.get_or_create(
                event=event, slug=slug,
                defaults={"name": name, "is_audience_choice": audience, "order": order})

        abstr1, created = Abstract.objects.get_or_create(
            event=event, slug="triage-model-emergency-department",
            defaults=dict(
                category=cat_ai, type="poster", poster_id="P-001",
                location="Foyer A, wall 5",
                title="A triage model in the emergency department — a prospective study",
                abstract_text=("**Background.** Sensitive assays produce many borderline "
                               "results. **Method.** A random forest trained on 12,400 "
                               "fictional cases. **Result.** AUC 0.91, NPV 99.2 %. "
                               "**Conclusion.** Plausible as a triage tool, and entirely "
                               "made up."),
                keywords="triage, machine learning, emergency medicine",
                status="accepted", is_published=True, has_poster=True,
                submitted_by=speaker_a))
        if created:
            for o, name, aff, country, ciso, presenting in [
                (1, "Alex Lindqvist", "Riverside University Hospital", "Germany", "DE", True),
                (2, "Priya Okonkwo", "Norhaven Medical School", "Austria", "AT", False),
            ]:
                AbstractAuthor.objects.create(
                    abstract=abstr1, full_name=name, affiliation=aff,
                    country=country, country_iso=ciso,
                    is_presenting=presenting, order=o)
            for o, ref in [
                (1, "Fictional A et al. Journal of Made-Up Results 2024;331:445-453."),
                (2, "Invented B et al. Annals of Nothing 2023;44:1234-1242."),
            ]:
                AbstractReference.objects.create(
                    abstract=abstr1, order=o, citation_text=ref)

        abstr2, created2 = Abstract.objects.get_or_create(
            event=event, slug="sample-stability-review",
            defaults=dict(
                category=cat_diag, type="oral", poster_id="O-04",
                location="Hall A, 14:30",
                title="Sample stability: ten years of data, summarised",
                abstract_text=("**Aim.** A systematic review of 1,247 fictional stability "
                               "studies. **Results.** Median stability at room temperature "
                               "≥ 24 h for 86 % of analytes."),
                keywords="stability, pre-analytics, review",
                status="accepted", is_published=True,
                submitted_by=speaker_b))
        if created2:
            AbstractAuthor.objects.create(
                abstract=abstr2, full_name="Sam Duarte",
                affiliation="Institute of Applied Measurement",
                country="Netherlands", country_iso="NL",
                is_presenting=True, order=1)

        # ── Feedback survey ───────────────────────────────────────────
        survey, _ = EventSurvey.objects.get_or_create(
            event=event, slug="post-event",
            defaults={"title": "Your feedback", "is_published": True,
                      "title_de": "Ihr Feedback",
                      "intro_text": "Thanks for coming — three minutes, and you are done.",
                      "intro_text_de": "Danke fürs Kommen — drei Minuten, und Sie sind fertig."})

        # (order, type, text EN, text DE, likert min EN/DE, likert max EN/DE,
        #  choices as (EN, DE) pairs)
        questions_data = [
            (1, QuestionType.LIKERT_5,
             "How were the session lengths?", "Wie waren die Längen der Sessions?",
             ("too short", "zu kurz"), ("too long", "zu lang"), []),
            (2, QuestionType.LIKERT_5,
             "Was there enough time for networking?", "Gab es genug Zeit zum Netzwerken?",
             ("far too little", "viel zu wenig"), ("just right", "genau richtig"), []),
            (3, QuestionType.YES_NO,
             "Would you come again next year?", "Würden Sie nächstes Jahr wiederkommen?",
             ("", ""), ("", ""), []),
            (4, QuestionType.OPEN_TEXT,
             "What worked particularly well?", "Was hat besonders gut funktioniert?",
             ("", ""), ("", ""), []),
            (5, QuestionType.OPEN_TEXT,
             "What did not, or could be better?", "Was nicht — oder was könnte besser sein?",
             ("", ""), ("", ""), []),
            (6, QuestionType.MULTI_CHOICE,
             "Which topics would you like next time?",
             "Welche Themen wünschen Sie sich beim nächsten Mal?",
             ("", ""), ("", ""),
             [("Computational methods", "Computergestützte Methoden"),
              ("Pre-analytics", "Präanalytik"),
              ("Haematology", "Hämatologie"),
              ("Clinical chemistry", "Klinische Chemie"),
              ("Microbiology", "Mikrobiologie"),
              ("Genomics", "Genomik"),
              ("Point-of-care testing", "Point-of-Care-Testung")]),
        ]
        for order, qtype, text, text_de, lmin, lmax, choices in questions_data:
            q, qcreated = SurveyQuestion.objects.get_or_create(
                survey=survey, order=order,
                defaults={"type": qtype, "text": text, "text_de": text_de,
                          "is_required": False,
                          "likert_min_label": lmin[0], "likert_min_label_de": lmin[1],
                          "likert_max_label": lmax[0], "likert_max_label_de": lmax[1]})
            if qcreated and choices:
                for ci, (ctxt, ctxt_de) in enumerate(choices, start=1):
                    SurveyChoice.objects.create(question=q, text=ctxt, text_de=ctxt_de,
                                                order=ci)

        self.stdout.write(self.style.SUCCESS("✓ Seed complete"))
