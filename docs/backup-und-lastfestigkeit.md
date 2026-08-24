# Backups und Lastfestigkeit

Betrifft die Produktion auf dem Produktionsserver (`conference.example.org`, Account `<user>`,
`~/lma-connect`). Zwei Ziele: Ein Fehler am Konferenztag darf höchstens
eine Stunde Daten kosten, und die App muss 100 gleichzeitige Teilnehmer
tragen, ohne auszufallen.

---

## 1. Backups

### Was läuft

Zwei getrennte Jobs, weil Datenbank und Medien völlig unterschiedliche
Änderungsraten haben.

**Datenbank** — ändert sich im Sekundentakt, jede Stunde zählt:

| | |
|---|---|
| Command | `python manage.py backup_db` |
| Zeitplan | stündlich **08:00–18:00**, zusätzlich **02:30** nachts |
| Ziel | `~/backups/lma-connect/db-JJJJMMTT-HHMM.sqlite3.gz` (~200 KB pro Stand) |
| Aufbewahrung | jeder Stand der letzten **48 h**, danach ein Stand pro Tag für **30 Tage** |

**Medien** (`media/` — Speaker-Fotos, Sponsorenlogos, Lagepläne) — ändert sich
im Wochentakt, und die Originale existieren ja noch woanders:

| | |
|---|---|
| Command | `python manage.py backup_media` |
| Zeitplan | **sonntags 03:45** |
| Ziel | `~/backups/lma-connect/media-JJJJMMTT-HHMM.tar.gz` (aktuell ~17 MB pro Stand) |
| Aufbewahrung | die letzten **8 Wochenstände** (~135 MB gesamt) |

Für beide gilt:

| | |
|---|---|
| Off-site | `deploy/pull-backups.sh` holt DB- **und** Medien-Stände auf Jannes Rechner |
| Log | `~/logs/lma-backup.log` |
| Rechte | Verzeichnis `0700`, Dateien `0600` — die Backups enthalten personenbezogene Daten |

### Warum kein `cp db.sqlite3`

Die Datenbank läuft im **WAL-Modus**. Frisch committete Transaktionen stehen
dann im `db.sqlite3-wal`, nicht in der Hauptdatei. Ein einfaches Kopieren
liefert deshalb einen Stand, dem die letzten Schreibvorgänge fehlen — oder,
wenn gerade ein Checkpoint läuft, eine inkonsistente Datei.

`backup_db` nutzt stattdessen die **SQLite-Online-Backup-API**. Die erzeugt
einen konsistenten Snapshot bei laufendem Betrieb, ohne die App zu blockieren.
Anschließend wird die Kopie mit `PRAGMA integrity_check` geprüft, komprimiert
und erst dann atomar an ihren endgültigen Namen umbenannt. Ein abgebrochener
Lauf hinterlässt so nie eine halbe Datei, die im Ernstfall für ein gültiges
Backup gehalten wird.

Jeder Fehler beendet den Command mit Exit-Code ≠ 0 → Cron schickt eine Mail.

### Nützliche Aufrufe

```bash
cd ~/lma-connect

.venv/bin/python manage.py backup_db            # Snapshot jetzt
.venv/bin/python manage.py backup_db --list     # was liegt da, wie alt
.venv/bin/python manage.py backup_db --dry-run  # was würde rotiert
.venv/bin/python manage.py backup_db --verify ~/backups/lma-connect/db-20260910-1400.sqlite3.gz

.venv/bin/python manage.py backup_media         # Medien-Archiv jetzt
.venv/bin/python manage.py backup_media --list
.venv/bin/python manage.py backup_media --verify ~/backups/lma-connect/media-20260913-0345.tar.gz
```

---

## 2. Restore — Runbook

**Im Ernstfall in dieser Reihenfolge.** Der häufigste Restore-Fehler ist,
die alten `-wal`/`-shm`-Dateien liegen zu lassen: SQLite mischt sie dann mit
der zurückgespielten Datei und beschädigt sie.

```bash
ssh <user>@<host>
cd ~/lma-connect

# 1. App anhalten — solange sie schreibt, ist jeder Restore ein Ratespiel.
systemctl --user stop lma-connect.service

# 2. Den kaputten Stand WEGSICHERN, nicht löschen. Er wird eventuell noch
#    gebraucht, um verlorene Einträge von Hand zu retten.
mv db.sqlite3 db.sqlite3.broken-$(date +%Y%m%d-%H%M)
rm -f db.sqlite3-wal db.sqlite3-shm

# 3. Gewünschten Stand wählen …
ls -lt ~/backups/lma-connect/ | head

# 4. … prüfen, BEVOR er eingespielt wird.
.venv/bin/python manage.py backup_db --verify ~/backups/lma-connect/db-20260910-1400.sqlite3.gz

# 5. Einspielen.
gunzip -c ~/backups/lma-connect/db-20260910-1400.sqlite3.gz > db.sqlite3

# 6. Schema gegen den Code prüfen — ein älteres Backup kann Migrationen fehlen.
.venv/bin/python manage.py migrate --check || .venv/bin/python manage.py migrate

# 7. Starten und verifizieren.
systemctl --user start lma-connect.service
curl -sf https://conference.example.org/healthz && echo " — App ist oben"
```

Danach in der App stichprobenartig prüfen: aktives Event sichtbar, Programm
vollständig, ein Test-Login mit Token.

**Datenverlust einordnen:** Zurückgespielt wird der Stand der letzten vollen
Stunde. Alles, was danach passiert ist (Fragen, Votes, Ratings, Scans), ist
weg — es sei denn, es lässt sich aus `db.sqlite3.broken-*` nachziehen.

### Medien zurückspielen

Getrennt von der Datenbank und praktisch nie zeitkritisch — hochgeladene
Bilder lassen sich zur Not auch neu hochladen.

```bash
cd ~/lma-connect
mv media media.broken-$(date +%Y%m%d-%H%M)
tar -xzf ~/backups/lma-connect/media-20260913-0345.tar.gz    # entpackt nach ./media/
```

**Achtung:** Datenbank und Medien werden zu verschiedenen Zeitpunkten
gesichert. Nach einem Restore beider kann es Datenbankeinträge geben, deren
Bilddatei im älteren Medien-Archiv noch fehlt — Django zeigt dann ein
kaputtes Bild an. Im Zweifel die betroffenen Uploads einmal neu hochladen.

### Off-site-Kopie holen

Läuft auf dem **lokalen Rechner**, nicht auf dem Server:

```bash
deploy/pull-backups.sh                 # nach ~/Backups/lma-connect
deploy/pull-backups.sh /pfad/zum/ziel  # eigenes Ziel
```

Holt nur neue Dateien, überschreibt nie vorhandene, und prüft die jüngste
geholte Datei direkt mit `integrity_check`. Für die Konferenztage lohnt ein
Cron-Eintrag auf dem Mac (Beispiel steht im Skript-Kopf).

---

## 3. Lastfestigkeit: 100 gleichzeitige Teilnehmer

### Der eigentliche Engpass

Vor dieser Änderung lief gunicorn mit **2 Sync-Workern**. Das heißt wörtlich:
Die App konnte **zwei** Requests gleichzeitig bearbeiten. Nummer drei wartete.
Ein einzelner langsamer Request — Icon-Rendering, ein großer Programm-Query —
belegte die Hälfte der gesamten Kapazität. Bei 100 Teilnehmern in derselben
Kaffeepause wäre das die erste Stelle gewesen, die reißt.

### Was geändert wurde

**gunicorn** (`deploy/lma-connect.service`)

| Vorher | Nachher | Warum |
|---|---|---|
| `--workers 2` (sync) | `--worker-class gthread --workers 3 --threads 4` | 2 → **12 parallele Requests**. Die Views sind I/O-gebunden (SQLite-Reads, Templates), dafür sind Threads das richtige Mittel. 3 Worker = 3 CPU-Kerne. |
| `--max-requests 500` | `--max-requests 2000` | Bei 500 wäre am Konferenztag dauernd ein Worker im Neustart — genau dann, wenn er gebraucht wird. |
| `Restart=on-failure` | `Restart=always` + `StartLimitIntervalSec=0` | Vorher galt systemds Default-Ratelimit: nach 5 Starts in 10 s bleibt der Dienst **tot liegen**. Jetzt kommt er aus jedem Zustand wieder hoch. |
| — | `--graceful-timeout 30`, `--keep-alive 5` | Sauberes Worker-Recycling, weniger TCP-Handshakes bei mobilen Clients. |

**SQLite** (`settings.py`)

- `timeout` 5 s → **20 s**: Django-Default ist zu knapp, wenn viele Teilnehmer
  gleichzeitig schreiben (QR-Scans, Votes, Feedback). Danach gibt es
  `database is locked`.
- **`transaction_mode="IMMEDIATE"`** — der wichtigste Punkt. Im Default
  (`DEFERRED`) startet eine Transaktion als Leser und fordert die Schreib-Lock
  erst beim ersten `UPDATE` an. Kollidiert sie dort mit einem anderen
  Schreiber, wirft SQLite **sofort** `SQLITE_BUSY` — der `busy_timeout` greift
  in diesem Upgrade-Fall nämlich nicht, weil sonst ein Deadlock entstünde.
  Mit `IMMEDIATE` wird die Lock gleich zu Beginn geholt und das Warten läuft
  sauber über den Timeout. Genau das verhindert die sporadischen
  „database is locked"-Fehler unter Last.

  Das ist keine Theorie. Gemessen mit 12 parallelen Schreibern à 200
  Transaktionen nach dem Muster „lesen, dann schreiben" (also genau dem, was
  ein QR-Scan mit Punktezählung tut), beide Male mit `timeout=20`:

  | `transaction_mode` | erfolgreiche Writes | `database is locked` |
  |---|---|---|
  | `DEFERRED` (Django-Default) | **261 / 2400** | **2139** |
  | `IMMEDIATE` (jetzt aktiv) | **2400 / 2400** | **0** |

  Knapp 90 % der Schreibvorgänge wären unter Last verloren gegangen — und der
  `timeout` von 20 s hätte daran nichts geändert, weil er in diesem Fall
  konstruktionsbedingt nicht greift. `IMMEDIATE` war dabei sogar schneller
  (0,13 s statt 0,19 s), weil keine Transaktion zurückgerollt und wiederholt
  werden muss.
- `CONN_MAX_AGE=60` + `CONN_HEALTH_CHECKS`: spart pro Request den
  Verbindungsaufbau samt PRAGMA-Setup.
- `temp_store=MEMORY`, `cache_size=-16000` (16 MB Page-Cache pro Connection).

**Sessions** (`settings.py`)

`SESSION_ENGINE = cached_db`. Session-Lesevorgänge laufen jetzt über den
Prozess-Cache, Schreibvorgänge weiterhin in die DB. Jeder Request eines
eingeloggten Nutzers spart damit ein `SELECT` auf `django_session` — bei
100 Teilnehmern, die permanent durch Programm und Q&A navigieren, ist das der
günstigste Einzelgewinn an DB-Last. Logout und Invalidierung funktionieren
unverändert, weil die DB führend bleibt.

**Health-Endpoint**

`GET /healthz` → `{"status": "ok", "database": "ok"}`, HTTP **503** wenn die
DB nicht antwortet. Kein Auth, nicht cachebar, macht genau ein `SELECT 1`.

Von außen genügt `curl -sf https://conference.example.org/healthz`. **Auf dem Server
selbst** sind zwei Dinge zu beachten, sonst bekommt man nie eine 200:

```bash
curl -sf -H "X-Forwarded-Proto: https" http://127.0.0.1:8130/healthz
```

- Ohne `127.0.0.1` in `DJANGO_ALLOWED_HOSTS` antwortet Django mit **400**
  (`DisallowedHost`). Deshalb steht es dort inzwischen mit drin — zusammen mit
  `localhost`. Unbedenklich, weil externe Requests immer über den
  Uberspace-Proxy laufen, der den echten Host-Header setzt.
- Ohne `X-Forwarded-Proto: https` greift `SECURE_SSL_REDIRECT` und man bekommt
  eine **301** auf die öffentliche URL statt der Statusantwort.

---

## 4. Lasttest

`deploy/loadtest.py` simuliert N Teilnehmer mit eigener Session, die sich
durch Home, Programm, Speaker, Sponsoren und Abstracts klicken — mit
Denkpausen, also kein reiner Hammer-Test.

```bash
# Gegen die lokale Instanz
deploy/loadtest.py --url http://127.0.0.1:8000 --users 50 --duration 30

# Gegen die Produktion — VOR der Konferenz, nicht während
deploy/loadtest.py --url https://conference.example.org --users 100 --duration 60
```

**Bestanden** heißt: 0 Fehler und p95 < 1 s. Der Exit-Code spiegelt das
Ergebnis, das Skript lässt sich also in eine Pipeline hängen.

### Gemessen am 2026-08-08, gegen die echte Produktion

Vier Läufe, jeweils 100 simulierte Teilnehmer, um Ursache und Wirkung
auseinanderzuhalten:

| Lauf | Absender | Weg | Fehler | Durchsatz | p95 |
|---|---|---|---|---|---|
| 1 | MacBook | HTTPS über Proxy | **97 (4,76 %)** | 23,3 req/s | 5,385 s |
| 2 | Server | direkt auf `:8130` | 0 | 50,3 req/s | 0,079 s |
| 3 | Server (60 Nutzer) | HTTPS über Proxy | 0 | 28,6 req/s | 0,124 s |
| 4 | Server | HTTPS über Proxy | **0** | 45,8 req/s | 0,159 s |

**Lauf 1 und Lauf 4 unterscheiden sich in genau einer Sache: dem Absender.**
Gleiche Nutzerzahl, gleiche öffentliche URL, gleicher Proxy, gleiches TLS.
Der eine meldet 97 Timeouts, der andere null. Der Engpass war also das
Testgerät, nicht die App.

Bestätigt wird das durch das Server-Journal: gunicorn hat während Lauf 1
**exakt 1940 Requests** protokolliert — genau die, die der Client als
erfolgreich zählte. Die 97 Timeouts sind nie angekommen. Dazu null
Tracebacks, null `database is locked`, null Worker-Timeouts.

Warum der Laptop bremst: 100 Python-Threads handeln parallel TLS aus und
entpacken ~100 KB große Seiten. Das ist wegen des GIL für den Client mehr
Arbeit als das Ausliefern für den Server. Sichtbar an der **schnellsten**
Antwort — 340 ms vom Mac gegen 16 ms vom Server. Der Client stand schon beim
allerersten Request in der eigenen Warteschlange.

Ressourcen während Lauf 4, **inklusive** des mitlaufenden Testgenerators:

| | gemessen | Limit |
|---|---|---|
| RAM (alle Account-Prozesse) | max **868 MB** | 1536 MB |
| Load | max **2,54** | 3 CPUs |

Die App allein lag bei 229 MB. Die drei Worker passen also bequem ins
RAM-Budget — die weiter unten beschriebene Notbremse
(`--workers 2 --threads 6`) wird nicht gebraucht.

### Wenn ein Lauf „NICHT BESTANDEN" meldet

**Erst prüfen, wer der Engpass war**, bevor irgendetwas an der App geändert
wird. Das Skript weist inzwischen selbst darauf hin, wenn der Verdacht auf
das Testgerät fällt. Die Gegenprobe in zwei Schritten:

```bash
# 1. Hat die App die fehlenden Requests überhaupt gesehen?
ssh <user>@<host> \
  "journalctl --user -u lma-connect.service --since '-15min' --no-pager \
   | grep -c lma-loadtest"
# Deckt sich die Zahl mit den ERFOLGREICHEN Requests des Clients, sind die
# Fehler nie angekommen → Engpass liegt beim Client oder auf dem Weg.

# 2. Denselben Test vom Server aus fahren — ohne Laptop und Heimleitung:
ssh <user>@<host> \
  "cd ~/lma-connect && .venv/bin/python deploy/loadtest.py \
   --url https://conference.example.org --users 100 --duration 45"
```

Für einen Test **direkt gegen den Backend-Port** (ohne Proxy und TLS)
braucht es zwei Header, sonst gibt es 400 bzw. 301:

```bash
.venv/bin/python deploy/loadtest.py --url http://127.0.0.1:8130 \
  --users 100 --duration 45 \
  --header "Host: conference.example.org" --header "X-Forwarded-Proto: https"
```

### Gegen die Produktion: `loadtest-prod.sh`

```bash
deploy/loadtest-prod.sh          # 100 Nutzer, 60 s
deploy/loadtest-prod.sh 150 90   # 150 Nutzer, 90 s
```

Der Wrapper fährt denselben Test, misst aber zusätzlich im Sekundentakt RAM
und Load auf dem Server mit und zählt anschließend kritische Zeilen im
Journal. Der Grund steht im nächsten Abschnitt: Auf Uberspace ist nicht die
CPU das knappe Gut, sondern der **Arbeitsspeicher**.

### Das eigentliche Limit: 1536 MB RAM pro Account

Uberspace gibt jedem Account eine faire Scheibe CPU, aber ein **hartes
RAM-Limit von 1536 MB** — wer darüber geht, dessen Prozesse werden abgeschossen.
Dieses Budget teilen sich auf `<user>` **drei** Dienste:

| Dienst | RAM im Leerlauf |
|---|---|
| lma-connect (3 Worker) | 160 MB |
| lma-website | 111 MB |
| stability | 268 MB |
| **Summe aller Account-Prozesse** | **675 MB von 1536 MB** |

Im Leerlauf also 44 % ausgeschöpft. Unter Last wachsen die gunicorn-Worker,
und genau diesen Spitzenwert misst `loadtest-prod.sh`.

**Gemessen ist das inzwischen** (siehe Messtabelle oben): unter 100 Nutzern
lag die App bei 229 MB und der gesamte Account bei 868 MB — und darin steckte
noch der Testgenerator, der im Ernstfall nicht mitläuft. Rund 670 MB Reserve.
Es ist also nichts zu tun.

**Falls es doch einmal eng wird**, ist der Hebel nicht „mehr kaufen" (RAM ist
bei Uberspace nicht zukaufbar), sondern die Worker-Aufteilung: Threads teilen sich den
Speicher ihres Prozesses, Worker nicht. `--workers 2 --threads 6` ergibt
dieselben 12 parallelen Requests wie `3 × 4`, braucht aber nur zwei
Python-Prozesse statt drei — grob ein Drittel weniger Speicher, zum Preis von
etwas weniger CPU-Parallelität.

Zum Vergleich die Kapazitätsrechnung: `/programm/` — die schwerste Seite —
braucht serverseitig **39 ms**. Bei 12 parallelen Slots sind das rechnerisch
rund 300 Requests/s. 100 Teilnehmer, die alle zwei Sekunden etwas anklicken,
erzeugen etwa 50 Requests/s. Die CPU ist also nicht der Engpass, sondern hatte
vor dieser Änderung nur keine Gelegenheit, benutzt zu werden.

---

## 5. Monitoring

Ein externer Uptime-Check auf `https://conference.example.org/healthz` (z. B.
UptimeRobot, kostenlos, 5-Minuten-Intervall) ist die billigste sinnvolle
Absicherung: Er meldet auch dann, wenn die App aus einem Grund steht, der
sich per systemd nicht selbst repariert.

Zusätzlich am Konferenztag griffbereit:

```bash
systemctl --user status lma-connect.service
journalctl --user -u lma-connect.service -n 100 --no-pager
.venv/bin/python manage.py backup_db --list      # Backup wirklich aktuell?
```

---

## 6. Offene Punkte

- **Backups sind nicht verschlüsselt.** Bewusste Entscheidung: Teilnehmer
  melden sich unter frei gewählten Nicknames an, die Daten sind also weitgehend
  pseudonym. Schutz besteht über die Dateirechte (Home `0700`, Backups `0600`)
  — auf dem geteilten Uberspace kommt kein anderer Account daran.

  Was dabei mitgesichert wird und *nicht* pseudonym ist: die Klarnamen von
  Speakern, Chairs und Committee-Mitgliedern (die stehen ohnehin öffentlich im
  Programm), Affiliations, Freitexte aus Q&A und Feedback sowie die
  Passwort-Hashes der Redaktions-Accounts. Falls die Off-site-Kopie irgendwann
  auf einem Gerät landet, das nicht ohnehin vollverschlüsselt ist, wäre ein
  `age`-Wrapper um `pull-backups.sh` die naheliegende Nachrüstung.

  Die Vorlage in `seed_legal.py` behauptete „Database backups are encrypted at
  rest" — das war schlicht falsch und ist jetzt durch eine Beschreibung des
  tatsächlichen Vorgehens ersetzt.

  **Nebenbefund, gehört nicht zu diesem Task:** Auf der Produktion waren die
  Legal-Texte des Events komplett **leer** — `seed_legal` wurde dort nie
  ausgeführt, `/legal/privacy/`, `/legal/imprint/` usw. rendern also leere
  Seiten. Aufgegriffen in Task #66: die Texte liegen seither als
  `LegalPage`-Datensätze (Admin: Event → „Legal pages") statt in festen
  Event-Feldern. Vor Public-Launch muss das gefüllt und die
  `[TBD: …]`-Platzhalter durch echte Vereinsdaten ersetzt werden. `seed_legal`
  legt nur fehlende Seiten an und überschreibt gepflegte Texte nur mit
  `--overwrite` — ein zweiter Lauf ist damit ungefährlich.
- **Rate-Limiting über mehrere Worker.** Das Token-Redeem-Limit im
  access-Plugin liegt im `LocMemCache`, der pro gunicorn-Worker existiert.
  Effektiv ist das Limit damit um den Faktor 3 lockerer als konfiguriert
  (vorher: Faktor 2). Für einen Konferenz-Kontext vertretbar; wer es exakt
  will, braucht einen geteilten Cache oder einen DB-basierten Zähler.
- **Access-Log.** gunicorn schreibt jeden Request ins journal. Nützlich zum
  Debuggen, erzeugt aber I/O. Falls am Konferenztag Last-Probleme auftreten,
  ist `--access-logfile` der erste Kandidat zum Abschalten.
