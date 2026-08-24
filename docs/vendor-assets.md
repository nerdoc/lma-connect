# Vendor-Assets (Tabler, Icon-Font, htmx)

Tabler, der Icon-Webfont und htmx liegen unter `static/vendor/` **im Repo** und
werden vom eigenen Server ausgeliefert. Vorher kamen sie von `cdn.jsdelivr.net`.

## Warum kein CDN

Zwei Gründe, ein technischer und ein rechtlicher:

- **Am Konferenztag zählt Unabhängigkeit.** Ein CDN-Asset im `<head>` heißt: Die
  Oberfläche hängt am Konferenz-WLAN *und* an fremder Infrastruktur. Fällt eines
  von beidem aus, steht die App ohne Styles da — im Saal, während des Vortrags.
- **Jeder CDN-Aufruf überträgt die IP-Adresse jedes Teilnehmers an einen
  Dritten.** Das ist eine Offenlegung im Sinne von Art 13 Abs 1 lit e DSGVO und
  müsste in der Datenschutzerklärung als Empfänger stehen, samt Drittlandpfad
  (jsDelivr liefert über ein globales Multi-CDN aus). Aufgedeckt im
  SHIELD-Audit zu Task #66: Die Erklärung behauptete das Gegenteil.

## Bestand

| Datei | Quelle (npm-Paket) | Version |
|---|---|---|
| `vendor/tabler/tabler.min.css` | `@tabler/core` `dist/css/tabler.min.css` | 1.4.0 |
| `vendor/tabler/tabler.min.js` | `@tabler/core` `dist/js/tabler.min.js` | 1.4.0 |
| `vendor/tabler-icons/tabler-icons.min.css` | `@tabler/icons-webfont` | 3.34.0 |
| `vendor/tabler-icons/fonts/tabler-icons.{woff2,woff}` | `@tabler/icons-webfont` `dist/fonts/` | 3.34.0 |
| `vendor/htmx/htmx.min.js` | `htmx.org` `dist/htmx.min.js` | 2.0.3 |

Das Paket liefert die Icons zusätzlich als `.ttf` (2,3 MB). Die brauchen nur
Browser, die kein woff2 können — IE, Safari vor 10, Android vor 5 —, also
keiner, der diese App je öffnet. Datei und CSS-Referenz sind deshalb entfernt.
Wer noch weiter abspecken will, kann auch `.woff` (1,2 MB) streichen; woff2
allein deckt alles ab Baujahr 2016 ab.

**Wichtig:** Jede im CSS referenzierte Datei muss existieren.
`CompressedManifestStaticFilesStorage` bricht `collectstatic` sonst mit
`MissingFileError` ab. Beim Streichen eines Formats also immer die
`src:`-Deklaration im Icon-CSS mit anpassen.

SHA-384 der Originaldateien, wie sie beim Vendoring geladen wurden (das sind die
SRI-Hashes, die vorher in den Templates standen — sie belegen, dass die Dateien
im Repo bitgenau die sind, die vom CDN kamen):

```
tabler.min.css        sha384-kz+I4+mczbNiZfLAJMxOlJaZmnbRYhARHNkR2k6tal4gz7OL33/0puDD3SvkiNX9
tabler.min.js         sha384-pku3birjgGovaJ9ngF7SaxKkF/eYUvBjiMJ+jTtWbNesIj2Rud2K63+4JD7EF4gk
tabler-icons.min.css  sha384-8zE3cHqgn3iJlsilASXr1IcXFP7TnplbXZSbvKuaUYjPUpcK7QhlyLE/cY7lIBTp
htmx.min.js           sha384-0895/pl2MU10Hqc6jd4RvrthNlDiE9U1tWmX7WRESftEDRosgxNsQG/Ze9YMRzHq
```

**Abweichungen vom Original** (deshalb weichen die Hashes der Dateien im Repo
von den oben notierten ab):

1. Aus `tabler.min.css`, `tabler.min.js` und `tabler-icons.min.css` ist die
   abschließende `sourceMappingURL`-Zeile entfernt (38–49 Bytes). Ohne das
   bricht `collectstatic` ab, weil die `.map`-Dateien fehlen — und die
   mitzuliefern hieße gut 2 MB Ballast, den nur DevTools je anfassen.
2. Aus der `@font-face`-Regel in `tabler-icons.min.css` ist die
   `truetype`-Quelle entfernt, passend zur nicht mitgelieferten `.ttf`.

## Update auf eine neue Version

```bash
cd /Pfad/zum/repo
B=https://cdn.jsdelivr.net/npm
TABLER=1.4.0; ICONS=3.34.0; HTMX=2.0.3        # <- hochzählen

curl -sSfo static/vendor/tabler/tabler.min.css       "$B/@tabler/core@$TABLER/dist/css/tabler.min.css"
curl -sSfo static/vendor/tabler/tabler.min.js        "$B/@tabler/core@$TABLER/dist/js/tabler.min.js"
curl -sSfo static/vendor/tabler-icons/tabler-icons.min.css "$B/@tabler/icons-webfont@$ICONS/dist/tabler-icons.min.css"
for f in woff2 woff; do                        # kein ttf, siehe oben
  curl -sSfo "static/vendor/tabler-icons/fonts/tabler-icons.$f" \
       "$B/@tabler/icons-webfont@$ICONS/dist/fonts/tabler-icons.$f"
done
# Frisch geladenes Icon-CSS referenziert wieder die ttf — Quelle rausnehmen:
perl -pi -e 's{,url\("\./fonts/tabler-icons\.ttf[^)]*\) format\("truetype"\)}{}' \
  static/vendor/tabler-icons/tabler-icons.min.css
curl -sSfo static/vendor/htmx/htmx.min.js "$B/htmx.org@$HTMX/dist/htmx.min.js"

# Hash notieren, BEVOR der Sourcemap-Kommentar entfernt wird:
for f in static/vendor/tabler/tabler.min.css static/vendor/tabler/tabler.min.js \
         static/vendor/tabler-icons/tabler-icons.min.css static/vendor/htmx/htmx.min.js; do
  echo "$(basename $f) sha384-$(openssl dgst -sha384 -binary $f | openssl base64 -A)"
done

# Sourcemap-Verweise entfernen (sonst schlaegt collectstatic fehl):
perl -0pi -e 's{(?://|/\*)#\s*sourceMappingURL=[^\s*]*(?:\s*\*/)?\s*$}{}' \
  static/vendor/tabler/tabler.min.css static/vendor/tabler/tabler.min.js \
  static/vendor/tabler-icons/tabler-icons.min.css

uv run python manage.py collectstatic --noinput   # muss ohne Fehler durchlaufen
uv run python manage.py test
```

Danach die Versionstabelle und die Hashes oben aktualisieren.

## Folgen fürs Deployment

`collectstatic` ist bei jeder Änderung an `static/vendor/` **Pflicht** — die
Templates lösen die Pfade über den Manifest-Storage auf, und ohne passenden
Manifest-Eintrag wirft jede Seite `ValueError: Missing staticfiles manifest
entry`. Das trifft auch die Testsuite.

Die CSP in `settings.py` führt seit dem Vendoring **keine Fremddomain** mehr in
`script-src`, `style-src` und `font-src`. Wer wieder ein CDN-Asset einbindet,
muss die Domain dort ergänzen — und die Datenschutzerklärung
(`seed_legal.py`, Abschnitte 2–4) um den neuen Empfänger.
