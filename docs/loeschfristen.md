# Löschfristen — was die Datenschutzerklärung verspricht und was es einlöst

Betrifft die Produktion auf dem Produktionsserver (`conference.example.org`, Account `<user>`,
`~/lma-connect`).

Abschnitt 5 der Datenschutzerklärung (`/legal/privacy/`, gepflegt über
`manage.py seed_legal`) nennt für jede Datenart eine Aufbewahrungsdauer. Eine
solche Zusage ist nach Art. 13 Abs. 2 lit. a DSGVO verbindlich — sie muss von
etwas eingelöst werden, das auch dann läuft, wenn niemand daran denkt. Diese
Seite hält fest, was das jeweils ist, damit die Zusage und die Technik nicht
auseinanderlaufen.

## Die Zuordnung

| Zusage in der Datenschutzerklärung | Eingelöst durch | Wo konfiguriert |
|---|---|---|
| Kontodaten, Spitzname, Zugehörigkeit, Beiträge — **6 Monate** nach der Veranstaltung | Von Hand im Rahmen der Nachbereitung; die Erklärung sagt das ausdrücklich dazu | — |
| Anwendungsprotokoll (systemd-Journal) — **7 Tage** | `journald` des Nutzer-Dienstes | `~/.config/systemd/journald.conf.d/` → `Storage=persistent`, `MaxRetentionSec=7d` |
| Anmeldeprotokolle (django-axes) — **7 Tage** | Nächtlicher Cron, siehe unten | `crontab -e` auf dem Server |
| Sperre nach 10 Fehlversuchen — **1 Stunde** | `AXES_COOLOFF_TIME` | `lma_connect/settings.py` |
| Zähler für fehlgeschlagene Token-Einlösungen — **15 Minuten** | Django-Cache, nur im Arbeitsspeicher | `lma_connect/plugins/access/views.py` |
| Datenbanksicherungen — 48 stündliche + 30 tägliche | `manage.py backup_db` prunet selbst | siehe [Backups](backup-und-lastfestigkeit.md) |
| Mediensicherungen — 8 wöchentliche | `manage.py backup_media` prunet selbst | siehe [Backups](backup-und-lastfestigkeit.md) |
| Webserver-Zugriffsprotokoll | Rotation durch Uberspace, nicht durch uns | — |

## Der Cron für die Anmeldeprotokolle

`AccessLog` bekommt bei jedem Anmeldeversuch eine Zeile — auch bei
erfolgreichen — mit Benutzername, IP, User-Agent und Zeitstempel. Aufgeräumt
wird sie von django-axes nie; ohne Cron wächst sie unbegrenzt. Genau das war
der Befund: 27 Zeilen, die älteste vom 17. Juni 2026.

`AccessFailureLog` wird hier gar nicht befüllt — `AXES_ENABLE_ACCESS_FAILURE_LOG`
steht auf dem Default `False`. Der zweite Befehl in der Cron-Zeile ist damit
heute ein No-Op; er bleibt als Versicherung drin, falls die Einstellung je
gekippt wird.

```cron
#--- LMA Connect: Loeschfristen der Anmelde-Protokolle (Task #72) ---
# Datenschutzerklaerung sagt 7 Tage; django-axes loescht von selbst nichts.
# Gleiche Frist wie journald (MaxRetentionSec=7d).
10 4 * * * cd $HOME/lma-connect && { date -Is; .venv/bin/python manage.py axes_reset_logs --age 7 || echo "FEHLER: axes_reset_logs"; .venv/bin/python manage.py axes_reset_failure_logs --age 7 || echo "FEHLER: axes_reset_failure_logs"; } >> $HOME/logs/lma-retention.log 2>&1
```

Drei Fallstricke stecken in der Zeile:

- **Kein `%` im Cron-Befehl.** Cron übersetzt `%` in einen Zeilenumbruch, ein
  `date "+%F %T"` zerlegt den Eintrag also still. Deshalb `date -Is`.
- **`{ a; b; }` liefert nur den Status von `b`.** Scheitert der erste Befehl
  (DB gesperrt, Migration halb durch), landet der Traceback zwar im Log, die
  Gruppe endet aber mit 0 und Cron schickt keine Mail. Deshalb die beiden
  `|| echo "FEHLER: …"` — danach lässt sich das Log auf ein Wort greppen.
- **`AccessAttempt` bleibt außen vor** — und zwar zu Recht. Das ist der
  laufende Sperrzähler, kein Protokoll. axes räumt ihn selbst auf:
  `clean_expired_user_attempts` löscht bei *jedem* Anmeldeversuch global alle
  Zeilen, die älter als die Cool-Off-Schwelle sind (hier 1 Stunde). Die
  Löschung ist aber **ereignisgetrieben**: Nach der letzten Anmeldung der
  Konferenz bleiben die dann noch offenen Zeilen liegen, weil kein Versuch mehr
  kommt, der das Aufräumen auslöst. Deshalb gehört ein einmaliges
  `manage.py axes_reset` in die Nachbereitungs-Checkliste. Als Cron taugt es
  nicht — es löscht *alle* Zähler und hebt damit laufende Sperren auf.

### Nachsehen, ob es greift

```bash
ssh <host>
tail ~/logs/lma-retention.log            # eine Zeile pro Nacht: Zeitstempel + "N logs removed."
cd ~/lma-connect && .venv/bin/python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lma_connect.settings')
django.setup()
from axes.models import AccessLog
print(AccessLog.objects.count(), AccessLog.objects.order_by('attempt_time').values_list('attempt_time', flat=True).first())
"
```

Der älteste Zeitstempel darf nie mehr als sieben Tage zurückliegen.

## Wenn sich eine Frist ändert

Die Fristen stehen an zwei Stellen: im Text von `seed_legal.py` (englisch
*und* deutsch, Abschnitt 5 bzw. „Wie lange wir Ihre Daten aufbewahren") und in
der jeweiligen Technik oben. Beide gemeinsam ändern, sonst verspricht die
Erklärung etwas, das nichts einhält — oder umgekehrt.

Nach einer Textänderung:

```bash
python manage.py seed_legal --overwrite    # ersetzt EN und DE zusammen
```

`--overwrite` überschreibt auch Handkorrekturen aus dem Admin. Ohne den Schalter
bleiben vorhandene Seiten unangetastet.
