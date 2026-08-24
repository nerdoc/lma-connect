# LMA Connect

Mobile-first conference companion app — secure, opinionated, deploy-ready.
Built with Django 5+ and HTMX, no JS framework, no build step.

Written for a scientific summit and released as a starter kit for any
single-event scientific or professional conference. Nothing about that first
event is baked in: the programme, the info sections, the floorplans, the legal
pages, the committees, the awards and the entire colour palette are data an
organizer maintains in the admin, not code someone has to fork.

## What you get

- **Welcome / splash screen** with brandable hero, event logo, organizer logo
- **Program** with sessions grouped by day, track colors, type badges
- **Session detail** with speakers (linked to their profile), live Q&A
  (moderated, with up-votes), live polls (single/multi/open) — attendees
  vote on their phones; results stay hidden in the app by default and the
  **chair drives a full-screen 16:9 room screen from the chair panel**:
  start/stop each poll (open/close voting) and switch the projected source
  live between **Standby / Q&A / poll results** (auto-refreshing; opt-in to
  also reveal results in-app per poll), 4-dimensional rating (slides,
  clarity, practical relevance, overall) — all persisted via HTMX
- **Speakers** with structured affiliation (department · institution · city ·
  country), bio, CV (PDF), LinkedIn, ORCID, list of talks
- **Custom user model** with affiliation fields — a user's department /
  institution / city / country is shown everywhere they appear (committees,
  speaker cards, Q&A posts)
- **Sponsors** with image carousel, multiple contacts (each with field of
  expertise + email/phone/LinkedIn), highlights, typed external links
  (product / news / whitepaper / video), **file downloads** (datasheets,
  whitepapers, brochures — admin uploads on the sponsor's behalf), and a
  pin marker on the floorplan
- **Abstracts** with strict structure (poster ID, location, authors with
  affiliation + ORCID + presenting flag, references with DOI), full-text
  search, jury awards (Best Poster / Best Oral / etc.) with gold-glow
  highlighting + dedicated filter
- **Feedback survey** with five question types (yes/no, Likert with custom
  endpoint labels, open text, single + multi choice) — anonymous allowed
- **Info tab** with venue, floorplans, freely definable info blocks (travel,
  sightseeing, WiFi, catering … all maintained in the admin, none hard-coded),
  event contacts (Organizing Secretary, Registration, …), collapsible
  committees with member lists
- **Legal pages** — freely definable per event (Imprint, Privacy policy,
  Terms of use, Accessibility statement, Code of Conduct … all maintained in
  the admin, none hard-coded), written as Markdown and served from
  `/legal/<slug>/`. `manage.py seed_legal` creates the usual four as a
  starting point.
- **Passwordless login via QR-code tokens** — no email/password, just scan
  your badge. New attendees pick a nickname and they're in. Tokens are
  revokable per attendee from the admin.
- **Dynamic QR-code service** — generate codes for any session/poll/token
  on the fly (`/qr/<path>/`), plus a print sheet with cards for badges —
  organizer-only (staff / Operations Team / superuser)
- **Per-event tab visibility** — each event admin can hide tabs they don't
  use (e.g. a workshop without sponsors/abstracts); the bottom-nav and the
  home-page quick-tiles both respect the flags
- **Compliant footer** — copyright (with auto year-range), "hosted by"
  organizer logo (customisable label), and one link per published legal page
- **Mobile-first**: sticky topbar, fixed bottom-tab nav, safe-area aware
  for iPhone notch/Dynamic Island, ≥44px touch targets

## Tech stack

Lean by design:

- **Django** ≥ 5.2 (LTS-friendly)
- **django-htmx** for live interactions (no JS framework)
- **django-markdownify** for safe (BLEACH-cleaned) Markdown rendering
- **qrcode** for SVG/PNG QR generation
- **django-q2** for background jobs
- **Pillow** for image fields
- **Tabler.io** + Tabler Icons for styling — vendored under `static/vendor/`,
  served from our own host, no CDN (see `docs/vendor-assets.md`)
- **SQLite** (dev) / **MariaDB** (prod, optional)

No Conjunto, no GDAPS, no Celery, no Redis. No npm. No build step.

## Quick start

```bash
git clone https://github.com/labmedalliance/lma-connect
cd lma-connect
uv sync                           # creates .venv with all deps
source .venv/bin/activate
cp .env.example .env              # set DJANGO_SECRET_KEY etc.
python manage.py migrate
python manage.py createsuperuser  # for /admin/
python manage.py runserver 5130
```

Open http://127.0.0.1:5130 → click "Enter" → you're at `/home/`.

To pre-populate with demo data (a fictional summit, speakers, sponsors,
abstracts, a survey, and a few access tokens):

```bash
python manage.py seed_demo
```

## Configuring your event

1. Go to `/admin/lma_core/event/add/` and create your event:
   - **Basics**: name, slug, dates, subtitle
   - **Venue**: address, geo (for "open in maps")
   - **Brand colours**: five colours — primary, accent, highlight, page
     background and text — drive the whole interface (buttons, badges, links,
     bottom navigation, projection screens). Everything else is derived from
     them, so picking five values re-skins the app
   - **Branding & images**: event logo, hero image (welcome screen), banner,
     organizer logo + name + URL
   - **Footer**: "hosted by" label, copyright holder + start year
   - **Legal pages (Markdown)**: as many as your jurisdiction needs —
     imprint, privacy policy, terms of use, accessibility statement, code of
     conduct … `manage.py seed_legal` creates the usual four **as templates**
     with every organizer-specific detail marked «LIKE THIS». Fill those in
     and have the result reviewed; the command counts what is still missing on
     every run. Footer links appear only for published pages.
   - **Tab visibility**: turn off any tabs your event doesn't use
   - **Info blocks** (inline on the Event): every text section of the Info
     tab — travel, sightseeing, WiFi, catering, dress code … each with its
     own title, [Tabler icon](https://tabler.io/icons), Markdown body, sort
     order, published flag and German translation. No section is hard-coded:
     add a block instead of touching a template
   - **Info tab**: emergency number for the quick-dial tile (`112` by
     default, empty hides the tile)
   - **Floorplans** (inline on the Event): as many levels as the venue has,
     each with its own label, file (PDF/PNG/SVG), sort order and German
     label. Tick *exhibition floor* on the level where the expo happens —
     that one is shown on the Expo page and is the reference image for the
     sponsor booth pins
2. Add **users** with affiliation (department / institution / city /
   country) in `/admin/lma_core/user/` — these fields show wherever the
   user appears
3. Add **rooms**, **committees** (with chairs and members), **tracks**,
   **event contacts** (Organizing Secretary etc. — inline on the Event)
4. Add **sessions** with speakers
5. Optional: **abstracts** (with **abstract awards** — define the prizes your
   jury hands out, and tick "audience choice" on the one attendees vote for),
   **sponsors** (with carousel images, contacts, links, downloads),
   **survey questions**
6. Generate access tokens for attendees:
   ```bash
   python manage.py make_tokens --event <slug> --count 300 --label "Speaker"
   ```
7. Print QR-code badges via `/qr/print/?kind=tokens&event=<slug>`
   (organizer-only: staff / Operations Team / superuser). Also
   `kind=sessions` and `kind=polls`.

## Customisation strategy

The app is **single-event-mode** by default but supports multiple events
in the database. Tabs and quick-tiles respect each event's visibility
flags, so you can run multiple deployments off one codebase or toggle
features on a single deployment.

For deeper customisation:

- **Templates** live in `templates/` (project-level base) and per-plugin
  in `lma_connect/plugins/<name>/templates/<name>/`. Override at the
  project level.
- **Branding**: the palette lives in `templates/_brand_palette.html`, which
  renders five event fields into CSS custom properties and maps them onto
  Tabler's variables. Nothing else in the codebase may hard-code a brand
  colour — the one exception is `templates/500.html`, which Django renders
  without a request and therefore without an event. Logos and the hero image
  are uploaded per event.
- **Plugins**: each app under `lma_connect/plugins/` is a
  self-contained Django app (models, views, urls, templates):
  `core`, `people`, `program`, `sponsors`, `abstracts`, `feedback`,
  `access` (token login), `qr`. Disable a *tab* via `Event.tab_*_enabled`
  to hide it from the navigation. Removing a plugin entirely needs a code
  change in `settings.LOCAL_PLUGINS`.

If you want a different project module name, rename `lma_connect` (a global
find-and-replace is enough — no migration touches the module path). The app
labels are `lma_*`, which is what makes admin URLs `/admin/lma_core/` etc.;
renaming those additionally means editing each `apps.py` **and** writing a
migration, so only do it if you have a reason.

## Security checklist before going live

- [ ] `DJANGO_DEBUG=False` and a strong, unique `DJANGO_SECRET_KEY`
- [ ] `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` set
- [ ] HTTPS (HSTS settings auto-activated when `DEBUG=False`)
- [ ] Rate-limit Q&A, survey and token-redeem endpoints
      (django-axes recommended)
- [ ] CSP headers active and free of external sources — front-end assets are
      vendored, so no third party sees your attendees' IP addresses
- [ ] `collectstatic` run after every change under `static/vendor/`
- [ ] Data Processing Agreement (DPA / AVV) with your hosting provider —
      and reference it in your Imprint + Privacy pages
- [ ] Imprint and Privacy filled in as `Legal pages` in the `Event` admin
- [ ] Backup strategy for `db.sqlite3` (or your MariaDB) —
      see [Backups & load resilience](docs/backup-und-lastfestigkeit.md)
- [ ] Retention periods your privacy page promises are actually enforced —
      django-axes deletes nothing on its own, see
      [Löschfristen](docs/loeschfristen.md)
- [ ] `python manage.py check --deploy` clean

## Operations

Backups, restore runbook and the tuning that lets the app carry ~100
concurrent attendees are documented in
**[docs/backup-und-lastfestigkeit.md](docs/backup-und-lastfestigkeit.md)**;
the scheduled jobs that enforce the retention periods promised on the privacy
page are in **[docs/loeschfristen.md](docs/loeschfristen.md)**.

```bash
python manage.py backup_db          # consistent, compressed SQLite snapshot
python manage.py backup_db --list   # what is stored, and how old
python manage.py backup_media       # tar.gz of MEDIA_ROOT (weekly is enough)
deploy/loadtest.py --url https://your.app --users 100 --duration 60
```

`GET /healthz` returns `{"status": "ok"}` (HTTP 503 when the database is
unreachable) — point an uptime monitor at it.

Deployment templates for the systemd unit and the backup cron entries live in
[`deploy/`](deploy/).

## Authentication model

Two distinct flows:

- **Admins / staff** sign in via `/admin/` with username + password.
  Standard Django auth — only people who manage the event need these.
- **Attendees** sign in via QR-code tokens. Each attendee is a regular
  Django user under the hood (so all the Q&A / poll / rating tracking
  just works), but they never type a username or password. They scan a
  token, pick a nickname, and they're in.

There is **no public registration form**. This is intentional and
removes most abuse vectors.

## Roles & permissions

The app is **publicly readable by default** — login only gates writing
and moderating actions. Access is built from seven independent role
primitives (a real person can hold several at once). Verified by a
live smoke test of 60 endpoints × 7 roles (Task #52, 2026-08-05):

| Role | Granted by | Unlocks |
|---|---|---|
| Anonymous | — | Read everything public: program, speakers, sponsors, abstracts, surveys, leaderboard |
| Attendee | QR-token login | Q&A questions + upvotes, live-poll votes, session ratings, feedback surveys, expo booth/poster check-ins, audience stars, `/me/` profile |
| Reviewer | `AbstractReview` assignment | Score **own** review assignments under `/abstracts/reviews/` — foreign reviews 404, even for staff and superusers |
| Session chair | `SessionChair` entry | Chair panel, Q&A moderation, poll start/stop, projection screen — for **their** sessions only (403 elsewhere) |
| Operations Team | Django group `Operations Team` | `/ops/` backend: token management, user support, aggregated abstract results, star ranking, audience award. `is_staff` alone does **not** grant `/ops/` |
| Staff | `is_staff` | Django admin (per assigned model perms), chair of **all** sessions, QR generator |
| Superuser | `is_superuser` | Everything (except foreign review forms — those stay reviewer-scoped) |

Notes:

- The participant **category** (Delegate / Speaker / Industry …) is a
  display/filter attribute only — it never grants permissions.
- QR endpoints (`/qr/…`) require *organizer* status: staff **or**
  Operations Team **or** superuser.
- Anonymous survey submission is allowed only when the survey has
  `allow_anonymous=True`, limited to once per browser session plus an
  IP cap; question upvotes only work on approved questions.

### Permission matrix

One row per function, one column per role primitive. A cell shows
whether that primitive **on its own** unlocks the action. Verified
against the source and a live smoke test (Django test client, isolated
test DB, 60 endpoints × 7 roles, including object-scoping probes —
Task #52, 2026-08-05); rows added since are marked *(new)*.

| ✓ allowed | – blocked (redirect / 403) | ⚠ conditional | *own* = own objects only | *perms* = assigned model perms only |
|---|---|---|---|---|

| Function | Anon | Attendee | Reviewer | Chair | Ops | Staff | Super |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **Public reading — no login** | | | | | | | |
| Welcome / Home / Info / Help / About / Legal | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Program & session detail | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Speakers · Sponsors · Abstracts (list + detail) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| View feedback survey · Leaderboard | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Redeem login token `/t/<token>/` ¹ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Attendee actions — login required** | | | | | | | |
| Ask a Q&A question | – | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Upvote a question ² · answer a live poll | – | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Rate a session (4-dimension rating) | – | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Submit feedback survey ³ | ⚠ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Own profile `/me/` | – | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Expo: booth check-in + quiz `/expo/s/<slug>/` | – | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Expo: poster check-in + audience star `/expo/p/<slug>/` | – | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Abstract review — gate = assignment ⁴** | | | | | | | |
| Open review area `/abstracts/reviews/` | – | *own* | *own* | *own* | *own* | *own* | *own* |
| Score an abstract / save · clear score | – | *own* | *own* | *own* | *own* | *own* | *own* |
| **Session moderation — chair or staff/superuser ⁵** | | | | | | | |
| Open chair panel | – | – | – | *own* | – | ✓ | ✓ |
| Approve · star · mark question answered | – | – | – | *own* | – | ✓ | ✓ |
| Add · delete question in chair panel | – | – | – | *own* | – | ✓ | ✓ |
| Edit private speaker notes in chair panel *(new)* | – | – | – | *own* | – | ✓ | ✓ |
| Start/stop live poll · poll projection (beamer) | – | – | – | *own* | – | ✓ | ✓ |
| Open beamer screen · switch source `/program/<slug>/screen/` | – | – | – | *own* | – | ✓ | ✓ |
| **QR codes — organizer (staff / ops / superuser) ⁶** | | | | | | | |
| Free QR generator `/qr/` · `/qr/<path>` | – | – | – | – | ✓ | ✓ | ✓ |
| QR print sheet `/qr/print/` | – | – | – | – | ✓ | ✓ | ✓ |
| **Operations backend `/ops/` — group or superuser ⁷** | | | | | | | |
| Ops dashboard · token management (create, QR, print, toggle) | – | – | – | – | ✓ | – | ✓ |
| View aggregated abstract results · publish abstract | – | – | – | – | ✓ | – | ✓ |
| Star ranking · grant audience award | – | – | – | – | ✓ | – | ✓ |
| User support: profile/category, password reset, unlock lockout, replacement token | – | – | – | – | ✓ | – | ✓ |
| **Admin — `is_staff`** | | | | | | | |
| Django admin `/admin/` ⁸ | – | – | – | – | – | *perms* | ✓ |

Footnotes:

1. The redeem link is public (it *is* the login). Protection: tokens can
   be deactivated; IP lockout after repeated attempts with invalid tokens.
2. Upvotes only apply to **approved** questions (`is_approved=True`). In
   moderated sessions, questions are invisible and not upvotable until
   the chair approves them (404 otherwise).
3. `feedback:submit` has no login decorator. Anonymous submission only
   when `allow_anonymous=True` — otherwise login is required. Logged-in
   users: exactly one (overwritable) response. Anonymous: once per
   browser session **plus** an IP cap against ballot stuffing.
4. Review scoping is strictly per object: every logged-in user can reach
   `/abstracts/reviews/` but sees only their own assignments. Foreign
   `review_id`s return 404 — **even for staff and superusers** (confirmed
   live). Aggregated results exist only under `/ops/abstracts/`.
5. The chair gate is the central `@chair_required` decorator (resolves
   the session from slug, question or poll). A chair moderates only
   *their* sessions — a foreign session returns 403 (confirmed live).
   Staff/superusers are automatically chair of all sessions.
6. `organizer_required` = staff **or** Operations Team **or** superuser.
   Attendees and chairs get a login redirect.
7. `ops_required` checks **group or superuser** — `is_staff` alone is not
   enough (confirmed live: staff got a login redirect on all 15 `/ops/`
   endpoints).
8. Staff only see admin models for which permissions were explicitly
   granted; superusers see everything.

Design decisions behind the matrix:

- **Publicly readable.** No global login requirement; login is enforced
  per view for writing/moderating actions — fitting for a mobile
  conference app where program and info are open to everyone.
- **Three separate permission axes.** `Operations Team` (support
  backend), `is_staff` (Django admin + chair everywhere) and
  `SessionChair` (per-session moderation) are decoupled. Only the QR
  area (`organizer_required`) deliberately unites staff and ops.
- **Audience stars only on site.** Poster stars can only be given via
  the poster QR code (`/expo/p/…`) — with login, a 3-star budget per
  person and final submission. Quiz answers have a failed-attempt
  cooldown, anonymous feedback an IP cap: every new write path has
  abuse protection.
- **Category ≠ permission.** The participant category (Delegate /
  Speaker / Industry …) only drives display and ops filters, never
  rights. Whoever should moderate needs a `SessionChair` entry; whoever
  should support needs the Ops group.

## What is deliberately NOT in the code

A running list, because it is the whole point of this repository being
reusable. All of it is data in the admin:

| Concern | Where it lives |
|---|---|
| Info tab sections (travel, WiFi, catering …) | `InfoBlock` per event |
| Floorplans, and which level holds the expo | `Floorplan` per event |
| Legal pages, and which ones exist at all | `LegalPage` per event |
| Committees, and how many of each | `Committee` per event |
| Abstract awards, incl. which is the audience prize | `AbstractAward` per event |
| Sponsor tiers | `SponsorTier` per event |
| Survey questions and their types | `SurveyQuestion` per event |
| The five brand colours | fields on `Event` |
| Emergency number | field on `Event` |
| Which tabs appear at all | `Event.tab_*_enabled` |
| Speaker and abstract-author countries (the world maps) | `country_iso` on the profile / author rows |

Still fixed in code, and the honest list of what a second conference might
want changed: session types, participant categories, consent types, the
gamification point table (`gamification/models.ACTION_POINTS`) and the
achievement rules, the 1–6 review scale, and `STARS_PER_USER`. All of them
are single, well-marked constants — but they are constants.

## Contributing

Issues and PRs welcome. The codebase intentionally stays small and
focused — please discuss large feature additions in an issue first.

Source language is **English**: code, comments, docstrings, commit messages
and every `gettext` msgid. German exists as a translation in `locale/de/`,
not as source strings.

## Who built it, and how you may use it

**LMA Connect** was designed and developed by **Janne Cadamuro / LabMed
Alliance Inc.**

Copyright © 2026 Janne Cadamuro / LabMed Alliance Inc.

The same information is rendered in the app itself: every page footer names
LMA Connect, its authors and its licence and links to **`/about/`**, which
repeats all of it in full. That is deliberate — the attribution lives in
hard-coded constants in [`lma_connect/__init__.py`](lma_connect/__init__.py)
and a context-processor, not in event data, so re-branding an event in the
admin cannot erase it. The `/about/` link is also this deployment's *source
offer* under AGPL §13.

## License

LMA Connect is free and open-source software, licensed under the
**GNU Affero General Public License v3.0 or later** (`AGPL-3.0-or-later`).
The full text is in [LICENSE](LICENSE).

You are free to:

- run the app for your own conference, commercially or not;
- study the source, adapt it and build on it;
- pass it on, modified or unmodified.

On these conditions:

- **Share alike** — anything you build on it must be released under the AGPL
  as well.
- **Also when you only host it** — if you run a modified version as a network
  service, you have to offer your users its source code (AGPL §13). This is
  what separates the AGPL from the plain GPL, and it is the reason it was
  picked for a web app.
- **Keep the attribution** — leave the copyright notices, the `/about/` page
  and the footer credit in place, and state what you changed. Adding yourself
  to the credits is expected; removing the original authors is not permitted.
- **No warranty** — the software is provided as is.

The licence covers the *software*. Everything an organizer maintains inside it
— programme, texts, logos, images, abstracts, trademarks, the event brand —
belongs to that organizer and is not covered by it.

When you fork, keep the constants in `lma_connect/__init__.py` truthful: bump
`VERSION`, point `SOURCE_URL` at *your* repository (§13 wants the source of the
version people actually use), and append your name to the credits rather than
replacing what is there.

### Built on

All front-end assets are vendored under `static/vendor/` and served from your
own host — no third-party CDN ever sees your attendees' IP addresses.

| Component | Licence |
|---|---|
| Django | BSD-3-Clause |
| django-htmx | MIT |
| django-markdownify | MIT |
| django-q2 | MIT |
| django-axes | MIT |
| django-csp | BSD-3-Clause |
| python-dotenv | BSD-3-Clause |
| qrcode | BSD-3-Clause |
| Pillow | MIT-CMU |
| Gunicorn | MIT |
| WhiteNoise | MIT |
| htmx | 0BSD |
| Tabler | MIT |
| Tabler Icons | MIT |
