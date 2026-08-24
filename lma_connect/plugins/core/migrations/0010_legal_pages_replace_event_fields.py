"""Die vier festen Rechtstext-Felder am Event weichen den Legal-Seiten.

imprint_md / privacy_md / terms_md / accessibility_md (+ _de) legten fest,
welche Dokumente ein Veranstalter hat. Das hängt aber an Rechtsform und Land.
Ihr Inhalt zieht hier verlustfrei in LegalPage-Datensätze um, danach fallen die
Spalten weg.

ACHTUNG beim Rückwärtsfahren: Nur die vier kanonischen Seiten wandern zurück in
die Felder — und auch von ihnen nur der Text, nicht Titel, Reihenfolge oder das
Veröffentlicht-Flag. Alles darüber hinaus (eine später angelegte Hausordnung,
ein Code of Conduct) ist danach weg, weil die Tabelle gedroppt wird. Vor einem
Rollback also `manage.py dumpdata lma_core.LegalPage > legalpages.json`.
"""

import django.db.models.deletion
from django.db import migrations, models

import lma_connect.plugins.core.models

# (Feldname, Slug, Titel EN, Titel DE, Sortierung) — der Slug ist zugleich der
# Schlüssel für den Rückweg und die URL: /legal/<slug>/. Die Slugs sind
# dieselben wie bisher, damit bestehende Links und Lesezeichen weiter greifen.
FIELD_PAGES = [
    ("imprint_md", "imprint", "Imprint", "Impressum", 10),
    ("privacy_md", "privacy", "Privacy policy", "Datenschutzerklärung", 20),
    ("terms_md", "terms", "Terms of use", "Nutzungsbedingungen", 30),
    ("accessibility_md", "accessibility", "Accessibility statement",
     "Barrierefreiheitserklärung", 40),
]


def fields_to_pages(apps, schema_editor):
    Event = apps.get_model("lma_core", "Event")
    LegalPage = apps.get_model("lma_core", "LegalPage")
    for event in Event.objects.all():
        for field, slug, title, title_de, order in FIELD_PAGES:
            body = getattr(event, field, "") or ""
            body_de = getattr(event, f"{field}_de", "") or ""
            if not body.strip() and not body_de.strip():
                continue
            LegalPage.objects.create(
                event=event, slug=slug, title=title, title_de=title_de,
                body=body, body_de=body_de, order=order, is_published=True,
            )


def pages_to_fields(apps, schema_editor):
    Event = apps.get_model("lma_core", "Event")
    LegalPage = apps.get_model("lma_core", "LegalPage")
    for field, slug, _title, _title_de, _order in FIELD_PAGES:
        for page in LegalPage.objects.filter(slug=slug):
            Event.objects.filter(pk=page.event_id).update(
                **{field: page.body, f"{field}_de": page.body_de})
            page.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('lma_core', '0009_floorplan_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='LegalPage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('slug', models.SlugField(help_text="Address of the page: /legal/<slug>/. Use 'imprint' and 'privacy' for those two — the app links to them directly.", verbose_name='URL slug')),
                ('title', models.CharField(max_length=200, verbose_name='Title')),
                ('body', models.TextField(blank=True, verbose_name='Text (Markdown)')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Order')),
                ('is_published', models.BooleanField(default=True, help_text='Uncheck to hide the page and its footer link without deleting it.', verbose_name='Published')),
                ('title_de', models.CharField(blank=True, max_length=200, verbose_name='Titel (DE)')),
                ('body_de', models.TextField(blank=True, verbose_name='Text — DE (Markdown)')),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='legal_pages', to='lma_core.event')),
            ],
            options={
                'verbose_name': 'Legal page',
                'verbose_name_plural': 'Legal pages',
                'ordering': ['event', 'order', 'id'],
                'constraints': [models.UniqueConstraint(fields=('event', 'slug'), name='unique_legal_page_slug_per_event')],
            },
            bases=(lma_connect.plugins.core.models.TranslatedTextMixin, models.Model),
        ),
        migrations.RunPython(fields_to_pages, pages_to_fields),
        migrations.RemoveField(
            model_name='event',
            name='accessibility_md',
        ),
        migrations.RemoveField(
            model_name='event',
            name='accessibility_md_de',
        ),
        migrations.RemoveField(
            model_name='event',
            name='imprint_md',
        ),
        migrations.RemoveField(
            model_name='event',
            name='imprint_md_de',
        ),
        migrations.RemoveField(
            model_name='event',
            name='privacy_md',
        ),
        migrations.RemoveField(
            model_name='event',
            name='privacy_md_de',
        ),
        migrations.RemoveField(
            model_name='event',
            name='terms_md',
        ),
        migrations.RemoveField(
            model_name='event',
            name='terms_md_de',
        ),
    ]
