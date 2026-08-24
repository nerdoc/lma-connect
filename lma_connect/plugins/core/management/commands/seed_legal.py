"""Create imprint, privacy policy, terms of use and accessibility statement
as LegalPage rows of the active event (or one given via --event=<slug>).

Every page is created bilingually — English source in `body`, German version
in `body_de`. Without the German version, German-speaking attendees would be
shown English legal texts, which does not carry weight for incorporating terms
of use or for a data protection notice in a German-speaking country.

A starting point to keep editing in the admin, not an owner of the texts:
pages that already exist are left alone unless --overwrite is given.

    THESE ARE TEMPLATES, NOT FINISHED LEGAL TEXTS.

Everything that identifies a specific organizer is a placeholder in guillemets
(«LIKE THIS»). Fill every one of them in before publishing, and have the
result reviewed by someone qualified in your jurisdiction. The command counts
the remaining placeholders after each run and tells you how many are left.

What the texts assume, and what you have to check:

* GDPR applies. The privacy policy is written for it. If you run outside the
  EU/EEA and none of your attendees are in it, the whole legal basis section
  needs rewriting rather than filling in.
* The app itself is what these texts describe — no analytics, no CDN, no
  third-party cookies, everything served from your own host. That is true of
  this codebase as shipped. If you add an external service, the privacy
  policy stops being accurate the moment you do.
* The retention periods in the privacy policy have to match what your
  deployment actually does (see docs/loeschfristen.md).

Usage: `python manage.py seed_legal [--event my-event-2026] [--overwrite]`
"""

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import formats, translation

from lma_connect.plugins.core.models import Event

IMPRINT = """\
### Provider

**«ORGANISER LEGAL NAME»**
«REGISTERED ADDRESS»

- «LEGAL FORM, e.g. registered association / limited company»
- «REGISTER AND REGISTRATION NUMBER, if your jurisdiction requires one»
- «VAT ID, if applicable»

### Represented by

- **«NAME»** — «ROLE»
- **«NAME»** — «ROLE»

### Contact

- E-Mail: `«CONTACT EMAIL»`
- Web: <«ORGANISER WEBSITE»>

### Purpose of this app

This web app is the official companion application for the conference
**{event_name}** on {dates} in {city}. It is provided free of charge to
registered attendees, speakers, chairs and sponsors of the event.

### Hosting

This service is hosted by **«HOSTING PROVIDER, COMPANY AND ADDRESS»** in
«HOSTING COUNTRY». The provider acts as a data processor on behalf of
«ORGANISER LEGAL NAME» — a data processing agreement according to Art 28 GDPR
is in place.

### Liability

The content of this app has been compiled with care. We accept no liability
for the accuracy, completeness or timeliness of the information provided.
Links to external websites lead to content we do not control and for which
the operators of those sites are solely responsible.

### Copyright

All text, images, logos and other content of this app are protected by
copyright. Reproduction, distribution or any other use beyond the limits of
copyright law requires the prior written consent of the rights holder. The
conference programme, speakers' slides and abstracts remain the intellectual
property of their respective authors.

---

*Last updated: {today}.*
"""

IMPRINT_DE = """\
### Anbieter

**«ORGANISER LEGAL NAME»**
«REGISTERED ADDRESS»

- «RECHTSFORM, z. B. eingetragener Verein / GmbH»
- «REGISTER UND REGISTERNUMMER, sofern erforderlich»
- «UMSATZSTEUER-ID, falls vorhanden»

### Vertreten durch

- **«NAME»** — «FUNKTION»
- **«NAME»** — «FUNKTION»

### Kontakt

- E-Mail: `«CONTACT EMAIL»`
- Web: <«ORGANISER WEBSITE»>

### Zweck dieser App

Diese Web-App ist die offizielle Begleit-App zur Konferenz **{event_name}**
vom {dates_de} in {city}. Sie wird registrierten Teilnehmenden, Vortragenden,
Vorsitzenden und Sponsoren der Veranstaltung kostenlos zur Verfügung gestellt.

### Hosting

Der Dienst wird von **«HOSTING PROVIDER, FIRMA UND ANSCHRIFT»** in
«HOSTING COUNTRY» betrieben. Der Anbieter ist Auftragsverarbeiter im Auftrag
von «ORGANISER LEGAL NAME»; ein Auftragsverarbeitungsvertrag nach Art. 28
DSGVO liegt vor.

### Haftung

Die Inhalte dieser App wurden mit Sorgfalt erstellt. Für Richtigkeit,
Vollständigkeit und Aktualität übernehmen wir keine Haftung. Links auf
externe Websites führen zu Inhalten, auf die wir keinen Einfluss haben und
für die allein deren Betreiber verantwortlich sind.

### Urheberrecht

Sämtliche Texte, Bilder, Logos und weiteren Inhalte dieser App sind
urheberrechtlich geschützt. Vervielfältigung, Verbreitung oder jede andere
Verwertung außerhalb der Grenzen des Urheberrechts bedarf der vorherigen
schriftlichen Zustimmung des Rechteinhabers. Das Konferenzprogramm, die
Folien der Vortragenden und die Abstracts bleiben geistiges Eigentum ihrer
jeweiligen Urheber.

---

*Zuletzt aktualisiert: {today}.*
"""

PRIVACY = """\
We take your privacy seriously. This page tells you exactly what data this
conference app collects, why we need it, how long we keep it and what rights
you have.

Because the conference takes place in the European Union and the app is aimed
at attendees there, the EU General Data Protection Regulation (GDPR) applies
to this processing under its Art 3(2), even though the controller is
established in Canada.

### 1. Data controller

**«ORGANISER LEGAL NAME»**, «REGISTERED ADDRESS» — see the
[imprint](/legal/imprint/) for full details.

For data-protection questions, please contact:

- E-Mail: `«DATA PROTECTION CONTACT EMAIL»`

«STATE HERE whether you have appointed a data protection officer. Art 37 GDPR
requires one only in specific cases; for an event app of this size it is
usually not required — but that is a decision you have to make and be able to
justify, not one this template can make for you.»

### 2. What data we collect and why

| Data | When | Purpose | Legal basis |
|------|------|---------|-------------|
| Nickname (chosen by you on first token sign-in) | When you redeem a QR token | Display your name on questions, ratings, leaderboard | Art 6(1)(b) — performance of the event |
| Username + password (if you have an account) | When you sign in via /accounts/login/ | Authentication | Art 6(1)(b) |
| Affiliation (department, institution, city, country) | Optional, in your profile | Show context next to your questions and on the speakers list | Art 6(1)(f) — you decide whether to fill it in; leaving it empty costs you nothing |
| Questions you post in Q&A | Each time you submit | Display to other attendees, chair, speaker | Art 6(1)(b) |
| Up-votes on questions | Each tap | Sort questions by popularity | Art 6(1)(b) |
| Poll answers | When you vote in a live poll | Aggregate result chart shown to the room | Art 6(1)(b) |
| Session ratings (4 dimensions + optional comment) | When you rate | Aggregate quality feedback to organisers and speakers | Art 6(1)(f) — our interest in the scientific quality of the programme |
| Survey answers | When you submit a survey | Feedback for organisers (programme, venue, etc.) | Art 6(1)(f) — same |
| Activity score, badges (gamification) | Derived automatically | Make participation a bit more fun; show your own progress on /me/ and on the leaderboard | Art 6(1)(f) — legitimate interest |
| Server log files (IP, user agent, URL, timestamp, status) | On every HTTP request | IT security, debugging, abuse defence | Art 6(1)(f) — legitimate interest |
| Sign-in records (username, IP, user agent, timestamp) | On every sign-in attempt, successful or failed | Brute-force protection (account lockout after 10 wrong tries) and IT security | Art 6(1)(f) |

We do **not** use any analytics, advertising, A/B-testing or social tracking
tools. There are no third-party cookies. The only cookies set by this app
are technical: session cookie, CSRF token, and (if applicable) a Django
language preference.

Everything the app loads — stylesheets, fonts, scripts, images — comes from
our own server. There are no content delivery networks, no web fonts fetched
from elsewhere, no embedded maps or videos. Your browser never contacts a
third party while you use this app.

### 3. Recipients of your data

Your data is processed by:

- «ORGANISER LEGAL NAME» as the organiser and the conference committee
  members listed in the app.
- **«HOSTING PROVIDER»** as our hosting provider and data processor under
  Art 28 GDPR. A formal data processing agreement is in place. The provider
  processes data only on our documented instructions.

There are no other recipients. In particular, we use no content delivery
network, no advertising network and no analytics provider.

Public elements (your nickname, your questions, your ratings without the
comment) are visible to other authenticated attendees of the same event.
Free-text rating comments and survey answers are visible only to the
organiser.

### 4. Transfers to third countries

The app, its database and its automated backups are stored on servers in
«HOSTING COUNTRY»; the offline backup copy is held by the organising team in
«BACKUP LOCATION». Your data is not sold, rented or passed on to third
parties.

«IF anyone outside the EU/EEA can access this data — because your organisation
is established there, or a committee member travels, or a processor operates
from there — NAME the country here and state the legal basis under Chapter V
GDPR: an adequacy decision (Art 45), standard contractual clauses (Art 46) or
an exception under Art 49. If nobody outside the EU/EEA has access, replace
this paragraph with the single sentence: "No data is transferred to a third
country."»

### 5. How long we keep your data

| Data | Retention |
|------|-----------|
| Account data, nickname, affiliation | Deleted as part of the post-conference wrap-up, at the latest **6 months** after the event ends — earlier if you ask us to |
| Questions, up-votes, polls, ratings, surveys (linked to your nickname) | Same point in time — afterwards anonymised and kept only in aggregate form for the conference report |
| Server log files (web server access log) | Rotated automatically by the hosting platform; we do not evaluate them beyond IT security and do not archive them |
| Application log (systemd journal of the app service) | Deleted automatically after **7 days** |
| Sign-in records (username, IP, user agent, timestamp) | Deleted automatically after **7 days** by a nightly job; a lockout itself expires after 1 hour |
| Token-redeem failure counters (rate limiting) | Held in volatile memory only, expire after 15 minutes |
| Database backups | 48 hourly plus 30 daily snapshots, then deleted automatically |
| Media backups (images uploaded by the organiser) | 8 weekly snapshots, then deleted automatically |

The 6-month deletion is a documented step in our conference wrap-up, carried
out by hand — not an automated job. If you want your data removed before
then, one e-mail is enough.

### 6. Your rights

Under the GDPR you have the right to:

- **access** the personal data we hold about you (Art 15),
- have inaccurate data **corrected** (Art 16),
- have your data **deleted** (Art 17),
- have processing **restricted** (Art 18),
- receive your data in a portable format (Art 20),
- **object** to processing based on legitimate interest (Art 21),
- **withdraw consent** at any time, without affecting the lawfulness of
  prior processing (Art 7(3)),
- **lodge a complaint** with a supervisory authority — normally the one of
  your country of residence or workplace. For attendees in Austria that is
  the Datenschutzbehörde, <https://www.dsb.gv.at>.

To exercise any of these rights, contact us at the address above. We will
respond within one month.

### 7. Do you have to provide any of this?

No. Only a nickname is required to use the interactive features, and you are
free to invent one. Everything else — affiliation, questions, ratings,
survey answers — is voluntary, and leaving it out costs you nothing: the
programme, the speaker list and all conference information stay fully
readable either way.

### 8. Automated decision-making

We do not use automated decision-making that produces legal effects or
similarly significantly affects you within the meaning of Art 22 GDPR. Your
activity score and badges are calculated automatically from what you do in
the app, but they influence nothing beyond your own progress display and
your position on the leaderboard. If you would rather not appear on the
leaderboard, tell us and we will take you off it.

### 9. Security

This app is served exclusively over HTTPS with HSTS, uses a restrictive
Content Security Policy that permits no external sources at all, brute-force
protection on sign-in and token redemption, and is built on Django's security
middleware. We do not store passwords in plaintext — they are hashed with
Django's PBKDF2 default.

The database is backed up automatically several times a day. Backups are
stored on the same hosting infrastructure as the app itself, inside a
private area readable only by the operating account, plus one offline copy
held by the organising team within the EU. Old snapshots are pruned
automatically on the schedule shown in section 5.

### 10. Changes

We may update this policy when functionality changes or new legal
requirements apply. The "last updated" date below tells you when it was
last revised. Material changes will be flagged in the app on your next
sign-in.

---

*Last updated: {today}.*
"""

PRIVACY_DE = """\
Wir nehmen Ihre Privatsphäre ernst. Diese Seite sagt Ihnen genau, welche
Daten diese Konferenz-App erhebt, wozu wir sie brauchen, wie lange wir sie
aufbewahren und welche Rechte Sie haben.

Weil die Konferenz in der Europäischen Union stattfindet und sich die App an
die dortigen Teilnehmenden richtet, gilt für diese Verarbeitung die
EU-Datenschutz-Grundverordnung (DSGVO) nach ihrem Art. 3 Abs. 2 — auch wenn
der Verantwortliche in Kanada niedergelassen ist.

### 1. Verantwortlicher

**«ORGANISER LEGAL NAME»**, «REGISTERED ADDRESS» — die vollständigen
Angaben finden Sie im
[Impressum](/legal/imprint/).

Bei Fragen zum Datenschutz wenden Sie sich bitte an:

- E-Mail: `«CONTACT EMAIL»`

«GEBEN SIE HIER AN, ob Sie eine:n Datenschutzbeauftragte:n bestellt haben.
Art. 37 DSGVO verlangt das nur in bestimmten Fällen; für eine Veranstaltungs-
App dieser Größe in der Regel nicht — das ist aber eine Entscheidung, die Sie
treffen und begründen können müssen, keine, die diese Vorlage Ihnen abnimmt.»

### 2. Welche Daten wir erheben und wozu

| Daten | Wann | Zweck | Rechtsgrundlage |
|-------|------|-------|-----------------|
| Spitzname (von Ihnen bei der ersten Token-Anmeldung gewählt) | Beim Einlösen eines QR-Tokens | Anzeige Ihres Namens an Ihren Q&A-Beiträgen, Bewertungen und in der Bestenliste | Art. 6 Abs. 1 lit. b — Durchführung der Veranstaltung |
| Benutzername + Passwort (sofern Sie ein Konto haben) | Bei der Anmeldung über /accounts/login/ | Authentifizierung | Art. 6 Abs. 1 lit. b |
| Zugehörigkeit (Abteilung, Einrichtung, Stadt, Land) | Freiwillig, in Ihrem Profil | Einordnung neben Ihren Fragen und in der Vortragendenliste | Art. 6 Abs. 1 lit. f — Sie entscheiden, ob Sie das ausfüllen; es leer zu lassen kostet Sie nichts |
| Fragen, die Sie im Q&A stellen | Bei jedem Absenden | Anzeige für andere Teilnehmende, Vorsitz und Vortragende | Art. 6 Abs. 1 lit. b |
| Zustimmungen zu Fragen (Up-Votes) | Bei jedem Tippen | Sortierung der Fragen nach Zuspruch | Art. 6 Abs. 1 lit. b |
| Antworten in Live-Umfragen | Wenn Sie abstimmen | Aggregierte Ergebnisgrafik für den Saal | Art. 6 Abs. 1 lit. b |
| Session-Bewertungen (4 Dimensionen + optionaler Kommentar) | Wenn Sie bewerten | Aggregierte Qualitätsrückmeldung an Veranstalter und Vortragende | Art. 6 Abs. 1 lit. f — unser Interesse an der wissenschaftlichen Qualität des Programms |
| Antworten in Befragungen | Wenn Sie eine Befragung absenden | Rückmeldung an die Veranstalter (Programm, Veranstaltungsort usw.) | Art. 6 Abs. 1 lit. f — dasselbe |
| Aktivitätspunkte, Abzeichen (Gamification) | Automatisch abgeleitet | Teilnahme etwas kurzweiliger machen; Ihren eigenen Fortschritt auf /me/ und in der Bestenliste zeigen | Art. 6 Abs. 1 lit. f — berechtigtes Interesse |
| Server-Protokolldateien (IP, User-Agent, URL, Zeitstempel, Status) | Bei jeder HTTP-Anfrage | IT-Sicherheit, Fehlersuche, Missbrauchsabwehr | Art. 6 Abs. 1 lit. f — berechtigtes Interesse |
| Anmeldeprotokolle (Benutzername, IP, User-Agent, Zeitstempel) | Bei jedem Anmeldeversuch, erfolgreich oder nicht | Schutz vor Brute-Force-Angriffen (Sperre nach 10 Fehlversuchen) und IT-Sicherheit | Art. 6 Abs. 1 lit. f |

Wir setzen **keine** Analyse-, Werbe-, A/B-Test- oder Social-Tracking-Werkzeuge
ein. Es gibt keine Cookies von Dritten. Die einzigen Cookies dieser App sind
technisch notwendig: Sitzungs-Cookie, CSRF-Token und gegebenenfalls eine
Django-Spracheinstellung.

Alles, was die App lädt — Stylesheets, Schriften, Skripte, Bilder — kommt von
unserem eigenen Server. Es gibt keine Content Delivery Networks, keine von
anderswo nachgeladenen Web-Schriften, keine eingebetteten Karten oder Videos.
Ihr Browser nimmt während der Nutzung dieser App zu keinem Dritten Kontakt auf.

### 3. Empfänger Ihrer Daten

Ihre Daten werden verarbeitet von:

- «ORGANISER LEGAL NAME» als Veranstalterin und den in der App genannten
  Mitgliedern des Konferenzkomitees,
- **«HOSTING PROVIDER»** als unserem Hosting-Anbieter
  und Auftragsverarbeiter nach Art. 28 DSGVO. Ein Auftragsverarbeitungsvertrag
  liegt vor. Der Anbieter verarbeitet Daten ausschließlich nach unseren
  dokumentierten Weisungen.

Weitere Empfänger gibt es nicht. Insbesondere nutzen wir kein Content Delivery
Network, kein Werbenetzwerk und keinen Analyse-Anbieter.

Öffentliche Elemente (Ihr Spitzname, Ihre Fragen, Ihre Bewertungen ohne den
Kommentar) sind für andere angemeldete Teilnehmende derselben Veranstaltung
sichtbar. Freitext-Kommentare zu Bewertungen und Antworten in Befragungen
sieht ausschließlich die Veranstalterin.

### 4. Übermittlung in Drittländer

Die App, ihre Datenbank und die automatischen Sicherungen liegen auf Servern
in «HOSTING COUNTRY»; die Offline-Sicherungskopie bewahrt das
Organisationsteam in «BACKUP LOCATION» auf. Ihre Daten werden nicht verkauft,
vermietet oder an Dritte weitergegeben.

«WENN jemand außerhalb der EU/des EWR auf diese Daten zugreifen kann — weil
Ihre Organisation dort niedergelassen ist, ein Komiteemitglied dorthin reist
oder ein Auftragsverarbeiter von dort arbeitet — BENENNEN Sie das Land hier
und nennen Sie die Rechtsgrundlage nach Kapitel V DSGVO: Angemessenheits-
beschluss (Art. 45), Standardvertragsklauseln (Art. 46) oder Ausnahme nach
Art. 49. Greift niemand außerhalb der EU/des EWR zu, ersetzen Sie diesen
Absatz durch den einen Satz: „Es werden keine Daten in ein Drittland
übermittelt."»

### 5. Wie lange wir Ihre Daten aufbewahren

| Daten | Aufbewahrung |
|-------|--------------|
| Kontodaten, Spitzname, Zugehörigkeit | Werden im Rahmen der Nachbereitung gelöscht, spätestens **6 Monate** nach Ende der Veranstaltung — früher, wenn Sie es verlangen |
| Fragen, Up-Votes, Umfragen, Bewertungen, Befragungen (mit Ihrem Spitznamen verknüpft) | Zum selben Zeitpunkt — danach anonymisiert und nur noch in aggregierter Form für den Konferenzbericht aufbewahrt |
| Server-Protokolldateien (Webserver-Zugriffsprotokoll) | Werden von der Hosting-Plattform automatisch rotiert; wir werten sie über die IT-Sicherheit hinaus nicht aus und archivieren sie nicht |
| Anwendungsprotokoll (systemd-Journal des App-Dienstes) | Wird nach **7 Tagen** automatisch gelöscht |
| Anmeldeprotokolle (Benutzername, IP, User-Agent, Zeitstempel) | Werden nach **7 Tagen** durch einen nächtlichen Auftrag automatisch gelöscht; eine Sperre selbst endet nach 1 Stunde |
| Zähler für fehlgeschlagene Token-Einlösungen (Ratenbegrenzung) | Nur im flüchtigen Speicher, verfallen nach 15 Minuten |
| Datenbanksicherungen | 48 stündliche und 30 tägliche Sicherungspunkte, danach automatische Löschung |
| Mediensicherungen (von der Veranstalterin hochgeladene Bilder) | 8 wöchentliche Sicherungspunkte, danach automatische Löschung |

Die Löschung nach 6 Monaten ist ein dokumentierter Schritt unserer
Konferenznachbereitung und erfolgt von Hand — nicht durch einen
automatischen Auftrag. Wenn Sie Ihre Daten früher gelöscht haben möchten,
genügt eine E-Mail.

### 6. Ihre Rechte

Nach der DSGVO haben Sie das Recht,

- **Auskunft** über die zu Ihrer Person gespeicherten Daten zu verlangen
  (Art. 15),
- unrichtige Daten **berichtigen** zu lassen (Art. 16),
- Ihre Daten **löschen** zu lassen (Art. 17),
- die Verarbeitung **einschränken** zu lassen (Art. 18),
- Ihre Daten in einem übertragbaren Format zu erhalten (Art. 20),
- der Verarbeitung auf Grundlage berechtigter Interessen zu
  **widersprechen** (Art. 21),
- eine **Einwilligung jederzeit zu widerrufen**, ohne dass die
  Rechtmäßigkeit der bis dahin erfolgten Verarbeitung berührt wird
  (Art. 7 Abs. 3),
- sich bei einer **Aufsichtsbehörde zu beschweren** — in der Regel bei der
  Ihres Wohnsitz- oder Arbeitsortes. Für Teilnehmende in Österreich ist das
  die Datenschutzbehörde, <https://www.dsb.gv.at>.

Zur Ausübung dieser Rechte wenden Sie sich bitte an die oben genannte
Adresse. Wir antworten innerhalb eines Monats.

### 7. Müssen Sie diese Daten bereitstellen?

Nein. Für die interaktiven Funktionen ist allein ein Spitzname erforderlich,
und den dürfen Sie frei erfinden. Alles Weitere — Zugehörigkeit, Fragen,
Bewertungen, Antworten in Befragungen — ist freiwillig, und es wegzulassen
kostet Sie nichts: Programm, Vortragendenliste und sämtliche
Konferenzinformationen bleiben so oder so vollständig lesbar.

### 8. Automatisierte Entscheidungsfindung

Eine automatisierte Entscheidungsfindung, die Ihnen gegenüber rechtliche
Wirkung entfaltet oder Sie in ähnlicher Weise erheblich beeinträchtigt
(Art. 22 DSGVO), findet nicht statt. Ihre Aktivitätspunkte und Abzeichen
werden zwar automatisch aus Ihren Handlungen in der App berechnet, wirken
sich aber auf nichts aus außer auf Ihre eigene Fortschrittsanzeige und Ihren
Platz in der Bestenliste. Wenn Sie lieber nicht in der Bestenliste
erscheinen möchten, sagen Sie uns Bescheid — dann nehmen wir Sie heraus.

### 9. Sicherheit

Diese App wird ausschließlich über HTTPS mit HSTS ausgeliefert, verwendet
eine restriktive Content Security Policy, die überhaupt keine externen
Quellen zulässt, schützt Anmeldung und Token-Einlösung gegen
Brute-Force-Angriffe und baut auf der Sicherheits-Middleware von Django auf.
Passwörter speichern wir nicht im Klartext — sie werden mit Djangos
PBKDF2-Standard gehasht.

Die Datenbank wird mehrmals täglich automatisch gesichert. Die Sicherungen
liegen auf derselben Hosting-Infrastruktur wie die App, in einem privaten
Bereich, den nur das Betriebskonto lesen kann, dazu eine Offline-Kopie beim
Organisationsteam innerhalb der EU. Alte Sicherungspunkte werden nach dem in
Abschnitt 5 genannten Plan automatisch gelöscht.

### 10. Änderungen

Wir können diese Erklärung anpassen, wenn sich Funktionen ändern oder neue
rechtliche Anforderungen gelten. Das Datum der letzten Aktualisierung unten
sagt Ihnen, wann sie zuletzt überarbeitet wurde. Auf wesentliche Änderungen
weisen wir Sie bei Ihrer nächsten Anmeldung in der App hin.

---

*Zuletzt aktualisiert: {today}.*
"""

TERMS = """\
Welcome to the **{event_name}** companion app, operated by
«ORGANISER LEGAL NAME» (see the [imprint](/legal/imprint/)). By using this
app you agree to the
following rules. They exist to keep the event respectful, useful and lawful
for everyone involved.

### 1. Who can use the app

The app is intended for registered attendees, speakers, chairs, committee
members and sponsors of the event. The organiser may grant or revoke
access at any time.

### 2. Your account / token

- Your QR-token login is **personal** — do not share it. Anyone who scans
  your token can post and vote in your name.
- If you lose your badge or believe someone else may have used your token,
  please contact the registration desk. The organiser can revoke the
  token and issue a new one.
- You are responsible for the content posted under your nickname.

### 3. Acceptable conduct

When you post a question, comment or any other content, you agree to:

- stay **on topic** (the science, the talk, the panel),
- be **civil and respectful** — no personal attacks, no harassment, no
  slurs, no discrimination based on gender, origin, religion, sexual
  orientation, age, disability or any protected characteristic,
- not post **unlawful** content (defamation, incitement, infringement of
  trade secrets or intellectual property),
- not use the Q&A or polls for **advertising, spam or promotional
  content** unrelated to the session,
- not share **patient data, personally identifiable information of
  third parties**, or anything covered by professional confidentiality
  (e. g. medical, attorney–client or banking secrecy),
- not attempt to **scrape, copy or systematically extract** data from the
  app, or to circumvent its security measures (rate limits, login
  protection, content security policy).

### 4. Moderation

- Session chairs and organisers may **hide or remove** any post that
  violates these terms, without prior notice.
- Repeated violations may lead to **revocation of your access token**
  and removal from the app.
- Decisions of the organiser take immediate effect for the duration of the
  event. You can contest any of them at any time via the contact address in
  the imprint, and we will tell you why the decision was made.

### 5. Intellectual property

The app's design, code, logos and text are protected by copyright and
remain the property of the organiser and its licensors. Speaker
materials, abstracts and slides remain the intellectual property of their
respective authors and may not be downloaded, screenshot or redistributed
outside the app unless the author explicitly permits it.

### 6. Availability and changes

The app is provided **"as is"** during and around the event. We make
reasonable efforts to keep it available and accurate, but cannot guarantee
uninterrupted service. The organiser may add, change or remove features
at any time, including ending the service after the event.

### 7. Limitation of liability

To the extent permitted by applicable law:

- We are liable without limitation for intent and gross negligence and for
  personal injury caused by us.
- For simple negligence we are liable only for the breach of obligations
  essential to the use of this app, and only up to the damage typically
  foreseeable for a free companion app.
- We are not liable for content posted by other attendees in Q&A, polls or
  comments, nor for the scientific content of talks, slides or abstracts.

### 8. Data protection

How we handle your personal data is described in the
[privacy policy](/legal/privacy/). By using the app you confirm that you
have read and understood it.

### 9. Applicable law

These terms are governed by the laws of the Province of Quebec and the
federal laws of Canada applicable therein, excluding their conflict-of-laws
rules and the UN Convention on Contracts for the International Sale of Goods
(CISG). If you use this app as a consumer, the mandatory protective
provisions of the country in which you have your habitual residence remain
unaffected by this choice of law.

### 10. Severability

Should any provision of these terms be or become invalid, the validity of
the remaining provisions shall not be affected. The invalid provision
shall be replaced by a valid provision that comes as close as possible to
the economic intent of the original provision.

---

*Last updated: {today}.*
"""

TERMS_DE = """\
Willkommen in der Begleit-App zur **{event_name}**, betrieben von
«ORGANISER LEGAL NAME» (siehe [Impressum](/legal/imprint/)). Mit der Nutzung
dieser App
erkennen Sie die folgenden Regeln an. Es gibt sie, damit die Veranstaltung für
alle Beteiligten respektvoll, nützlich und rechtmäßig bleibt.

### 1. Wer die App nutzen darf

Die App richtet sich an registrierte Teilnehmende, Vortragende, Vorsitzende,
Komiteemitglieder und Sponsoren der Veranstaltung. Die Veranstalterin kann den
Zugang jederzeit gewähren oder entziehen.

### 2. Ihr Zugang / Ihr Token

- Ihre Anmeldung per QR-Token ist **persönlich** — geben Sie sie nicht weiter.
  Wer Ihr Token scannt, kann in Ihrem Namen Beiträge verfassen und abstimmen.
- Wenn Sie Ihr Badge verlieren oder vermuten, dass jemand anderes Ihr Token
  benutzt hat, wenden Sie sich bitte an die Registrierung. Die Veranstalterin
  kann das Token sperren und ein neues ausstellen.
- Für die unter Ihrem Spitznamen veröffentlichten Inhalte sind Sie
  verantwortlich.

### 3. Umgangsregeln

Wenn Sie eine Frage, einen Kommentar oder sonstige Inhalte veröffentlichen,
verpflichten Sie sich,

- **beim Thema zu bleiben** (die Wissenschaft, der Vortrag, die Diskussion),
- **sachlich und respektvoll** zu bleiben — keine persönlichen Angriffe,
  keine Belästigung, keine Beschimpfungen, keine Diskriminierung wegen
  Geschlecht, Herkunft, Religion, sexueller Orientierung, Alter, Behinderung
  oder eines anderen geschützten Merkmals,
- keine **rechtswidrigen** Inhalte zu veröffentlichen (Beleidigung,
  Verhetzung, Verletzung von Geschäftsgeheimnissen oder geistigem Eigentum),
- Q&A und Umfragen nicht für **Werbung, Spam oder Eigenwerbung** ohne Bezug
  zur Session zu nutzen,
- keine **Patientendaten, personenbezogenen Daten Dritter** oder Inhalte zu
  teilen, die einer beruflichen Verschwiegenheitspflicht unterliegen
  (z. B. ärztliche, anwaltliche oder Bankgeheimnisse),
- nicht zu versuchen, Daten aus der App **auszulesen, zu kopieren oder
  systematisch zu extrahieren** oder ihre Sicherheitsvorkehrungen
  (Ratenbegrenzung, Anmeldeschutz, Content Security Policy) zu umgehen.

### 4. Moderation

- Sessionvorsitzende und Veranstalter dürfen Beiträge, die gegen diese
  Bedingungen verstoßen, **ohne Vorankündigung ausblenden oder entfernen**.
- Wiederholte Verstöße können zur **Sperre Ihres Zugangstokens** und zum
  Ausschluss aus der App führen.
- Entscheidungen der Veranstalterin gelten für die Dauer der Veranstaltung
  sofort. Sie können jede davon jederzeit über die Kontaktadresse im
  Impressum beanstanden; wir sagen Ihnen dann, warum so entschieden wurde.

### 5. Geistiges Eigentum

Gestaltung, Quellcode, Logos und Texte der App sind urheberrechtlich
geschützt und bleiben Eigentum der Veranstalterin und ihrer Lizenzgeber.
Vortragsunterlagen, Abstracts und Folien bleiben geistiges Eigentum ihrer
jeweiligen Urheber und dürfen außerhalb der App nicht heruntergeladen,
abfotografiert oder weiterverbreitet werden, sofern der Urheber es nicht
ausdrücklich gestattet.

### 6. Verfügbarkeit und Änderungen

Die App wird rund um die Veranstaltung **wie besehen** bereitgestellt. Wir
bemühen uns nach Kräften um Verfügbarkeit und Richtigkeit, können einen
unterbrechungsfreien Betrieb aber nicht zusichern. Die Veranstalterin darf
Funktionen jederzeit ergänzen, ändern oder entfernen und den Dienst nach der
Veranstaltung einstellen.

### 7. Haftungsbeschränkung

Soweit das anwendbare Recht es zulässt:

- Für Vorsatz und grobe Fahrlässigkeit sowie für von uns verursachte
  Personenschäden haften wir unbeschränkt.
- Für einfache Fahrlässigkeit haften wir nur bei Verletzung von Pflichten,
  die für die Nutzung dieser App wesentlich sind, und nur bis zu dem für eine
  kostenlose Begleit-App typischerweise vorhersehbaren Schaden.
- Für Beiträge anderer Teilnehmender in Q&A, Umfragen oder Kommentaren sowie
  für die wissenschaftlichen Inhalte von Vorträgen, Folien und Abstracts
  haften wir nicht.

### 8. Datenschutz

Wie wir mit Ihren personenbezogenen Daten umgehen, steht in der
[Datenschutzerklärung](/legal/privacy/). Mit der Nutzung der App bestätigen
Sie, dass Sie sie gelesen und verstanden haben.

### 9. Anwendbares Recht

Diese Bedingungen unterliegen dem Recht der Provinz Québec und dem dort
anwendbaren Bundesrecht Kanadas unter Ausschluss der Kollisionsnormen und des
UN-Kaufrechts (CISG). Nutzen Sie die App als Verbraucher, bleiben die
zwingenden Schutzvorschriften des Staates Ihres gewöhnlichen Aufenthalts von
dieser Rechtswahl unberührt.

### 10. Salvatorische Klausel

Sollte eine Bestimmung dieser Bedingungen unwirksam sein oder werden, bleibt
die Wirksamkeit der übrigen Bestimmungen davon unberührt. An die Stelle der
unwirksamen Bestimmung tritt eine wirksame, die dem wirtschaftlichen Zweck
der ursprünglichen möglichst nahekommt.

---

*Zuletzt aktualisiert: {today}.*
"""

ACCESSIBILITY = """\
We want every attendee of **{event_name}** to be able to use this app. This
statement is a voluntary commitment — we are not a public-sector body and are
therefore not covered by the EU Web Accessibility Directive, but we hold
ourselves to its standard anyway.

### Conformance status

We aim for
[Web Content Accessibility Guidelines (WCAG) 2.1 Level AA](https://www.w3.org/TR/WCAG21/).
Some parts of the app do not yet meet that standard — they are listed under
"known limitations" below.

### What we have done

- Mobile-first responsive layout (works from 320 px upwards).
- Sufficient colour contrast for text and interactive elements.
- Touch targets of at least 44 × 44 px.
- Forms with explicit labels and `aria-label` on icon-only buttons.
- Standard semantic HTML (headings, lists, landmarks).
- Sticky top bar and bottom navigation accessible by keyboard.

### Known limitations

- Some Markdown-rendered content (speaker bios, sponsor highlights) is
  authored by third parties and may not always meet contrast or
  alt-text requirements.
- The image carousels on sponsor pages do not yet have full keyboard
  controls — use the navigation arrows or swipe to advance.
- The floor plans are images with a visual booth marker; an accessible
  text-list alternative is on the roadmap.

### Feedback

If you encounter any barriers using this app, please let us know — we
will do our best to fix the issue or provide the information in an
accessible alternative format.

- E-Mail: `«CONTACT EMAIL»`

You can also speak to any member of the organising team at the registration
desk during the conference.

---

*Last updated: {today}.*
"""

ACCESSIBILITY_DE = """\
Wir möchten, dass jede und jeder Teilnehmende der **{event_name}** diese App
nutzen kann. Diese Erklärung ist eine freiwillige Selbstverpflichtung — wir
sind keine öffentliche Stelle und fallen daher nicht unter die
EU-Richtlinie über den barrierefreien Zugang zu Websites, halten uns aber
trotzdem an deren Maßstab.

### Stand der Konformität

Wir streben die
[Web Content Accessibility Guidelines (WCAG) 2.1 Stufe AA](https://www.w3.org/TR/WCAG21/)
an. Einzelne Teile der App erfüllen diesen Standard noch nicht — sie sind
unten unter „Bekannte Einschränkungen" aufgeführt.

### Was wir umgesetzt haben

- Mobile-first-Layout, das ab 320 px Breite funktioniert.
- Ausreichender Farbkontrast bei Text und Bedienelementen.
- Touch-Flächen von mindestens 44 × 44 px.
- Formulare mit ausdrücklichen Beschriftungen und `aria-label` an
  Schaltflächen, die nur aus einem Symbol bestehen.
- Übliches semantisches HTML (Überschriften, Listen, Landmarks).
- Feststehende Kopfzeile und untere Navigation sind per Tastatur bedienbar.

### Bekannte Einschränkungen

- Manche über Markdown eingepflegten Inhalte (Kurzbiografien der
  Vortragenden, Sponsorenbeiträge) stammen von Dritten und erfüllen nicht
  immer die Anforderungen an Kontrast oder Alternativtexte.
- Die Bildergalerien auf den Sponsorenseiten lassen sich noch nicht
  vollständig per Tastatur bedienen — nutzen Sie die Pfeile oder wischen Sie.
- Die Lagepläne sind Bilder mit einer optischen Standmarkierung; eine
  barrierefreie Alternative als Textliste ist geplant.

### Rückmeldungen

Wenn Sie bei der Nutzung dieser App auf Barrieren stoßen, sagen Sie uns bitte
Bescheid — wir tun unser Bestes, das Problem zu beheben oder Ihnen die
Information in einer barrierefreien Form zur Verfügung zu stellen.

- E-Mail: `«CONTACT EMAIL»`

Sie können sich während der Konferenz auch an jedes Mitglied des
Organisationsteams an der Registrierung wenden.

---

*Zuletzt aktualisiert: {today}.*
"""


# (slug, title EN, title DE, template EN, template DE, order). The slugs match
# LegalPage.CANONICAL, which is what the footer and the help page link to.
PAGES = [
    ("imprint", "Imprint", "Impressum", IMPRINT, IMPRINT_DE, 10),
    ("privacy", "Privacy policy", "Datenschutzerklärung", PRIVACY, PRIVACY_DE, 20),
    ("terms", "Terms of use", "Nutzungsbedingungen", TERMS, TERMS_DE, 30),
    ("accessibility", "Accessibility statement", "Barrierefreiheitserklärung",
     ACCESSIBILITY, ACCESSIBILITY_DE, 40),
]


class Command(BaseCommand):
    help = "Seed the Imprint / Privacy / Terms / Accessibility legal pages of an Event."

    def add_arguments(self, parser):
        parser.add_argument(
            "--event",
            dest="event_slug",
            help="Event slug. Default: latest published event.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace the text of pages that already exist — BOTH languages, "
                 "English and German, including anything edited by hand in the "
                 "admin. Without this flag only missing pages are created and a "
                 "re-run never silently resets an edited page.",
        )

    def handle(self, *args, **opts):
        event_slug = opts.get("event_slug")
        if event_slug:
            try:
                event = Event.objects.get(slug=event_slug)
            except Event.DoesNotExist as exc:
                raise CommandError(f"Event '{event_slug}' not found.") from exc
        else:
            event = (
                Event.objects.filter(is_published=True).order_by("-start_date").first()
            )
            if not event:
                raise CommandError("No published event — pass --event=<slug>.")

        if event.start_date and event.end_date:
            dates = (
                f"{event.start_date.strftime('%-d %B %Y')}"
                f" – {event.end_date.strftime('%-d %B %Y')}"
            )
            # German month names come from Django's own catalogues —
            # strftime runs in the C locale and would otherwise put
            # "1 September 2026" into the German text as well.
            with translation.override("de"):
                dates_de = (
                    f"{formats.date_format(event.start_date, 'j. F Y')}"
                    f" – {formats.date_format(event.end_date, 'j. F Y')}"
                )
        else:
            dates = "TBD"
            dates_de = "noch offen"
        ctx = {
            "event_name": event.name,
            "dates": dates,
            "dates_de": dates_de,
            "city": event.city or "«CITY»",
            "today": date.today().isoformat(),
        }

        overwrite = opts.get("overwrite")
        self.stdout.write(self.style.SUCCESS(f"Event: {event.slug}"))
        for slug, title, title_de, template, template_de, order in PAGES:
            body = template.format(**ctx)
            body_de = template_de.format(**ctx)
            page = event.legal_pages.filter(slug=slug).first()
            if page is None:
                event.legal_pages.create(
                    slug=slug, title=title, title_de=title_de,
                    body=body, body_de=body_de, order=order, is_published=True,
                )
                action = "created"
            elif overwrite:
                # Both languages together — they come from the same source.
                # Replacing only one would let one version go stale against
                # the other, which for legal texts is worse than overwriting a
                # hand-edit, something --overwrite warns about anyway.
                page.body = body
                page.body_de = body_de
                page.save(update_fields=["body", "body_de"])
                action = "overwritten (EN + DE)"
            else:
                body = page.body
                action = "kept (use --overwrite to replace)"
            url = f"/legal/{slug}/"
            self.stdout.write(f"  {url:<24}{len(body):>6} chars — {action}")

        # Count what is still unfilled. A legal page published with
        # «PLACEHOLDERS» in it is worse than none at all: it looks like an
        # imprint while naming nobody. So the command says out loud how much
        # work is left, every single run.
        remaining = sum(
            page.body.count("«") + page.body_de.count("«")
            for page in event.legal_pages.all()
        )
        if remaining:
            self.stdout.write(self.style.ERROR(
                f"{remaining} placeholders still to fill in — search for « in "
                f"/admin/lma_core/legalpage/. These are TEMPLATES: complete them "
                f"and have them reviewed by someone qualified in your "
                f"jurisdiction before the app goes public."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                "No placeholders left. Re-check the texts whenever the "
                "organisation, the hosting provider or the retention periods "
                "change."
            ))
