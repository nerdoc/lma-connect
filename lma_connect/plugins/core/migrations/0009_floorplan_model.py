"""Lagepläne bekommen ein eigenes Modell statt zwei fester Felder am Event.

`floorplan` (Erdgeschoss) und `floorplan_upper` (1. Stock) gaben vor, dass ein
Veranstaltungshaus genau zwei Ebenen hat und wie sie heissen. Ihre Dateien
ziehen hier in Floorplan-Datensätze um — die Dateien selbst bleiben liegen, es
wandert nur der Pfad. Das Erdgeschoss wird zur Ausstellungsebene, weil genau das
vorher die fest verdrahtete Annahme für die Booth-Pins war.
"""

import django.db.models.deletion
from django.db import migrations, models

import lma_connect.plugins.core.models

# (Feldname, Titel EN, Titel DE, Reihenfolge, Ausstellungsebene)
LEGACY_PLANS = [
    ("floorplan", "Ground floor", "Erdgeschoss", 10, True),
    ("floorplan_upper", "1st floor", "1. Stock", 20, False),
]


def fields_to_floorplans(apps, schema_editor):
    Event = apps.get_model("lma_core", "Event")
    Floorplan = apps.get_model("lma_core", "Floorplan")
    for event in Event.objects.all():
        for field, title, title_de, order, is_expo in LEGACY_PLANS:
            file_name = getattr(event, field, None)
            if not file_name:
                continue
            Floorplan.objects.create(
                event=event, title=title, title_de=title_de,
                file=file_name.name, order=order, is_exhibition_floor=is_expo,
            )


def floorplans_to_fields(apps, schema_editor):
    Event = apps.get_model("lma_core", "Event")
    Floorplan = apps.get_model("lma_core", "Floorplan")
    for field, title, _title_de, _order, _is_expo in LEGACY_PLANS:
        for plan in Floorplan.objects.filter(title=title):
            Event.objects.filter(pk=plan.event_id).update(**{field: plan.file.name})
            plan.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('lma_core', '0008_info_blocks_replace_info_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='Floorplan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('title', models.CharField(help_text="e.g. 'Ground floor', 'Hall 3', 'Foyer'", max_length=120, verbose_name='Floor / label')),
                ('file', models.FileField(help_text='PDF, PNG or SVG. PDFs get an open button, images are shown inline.', upload_to='events/floorplans/', verbose_name='File')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Order')),
                ('is_exhibition_floor', models.BooleanField(default=False, help_text='Tick the level where the expo takes place. It is shown on the Expo page, and the first ticked plan is the reference image for the sponsor booth pins.', verbose_name='Exhibition floor')),
                ('title_de', models.CharField(blank=True, max_length=120, verbose_name='Beschriftung (DE)')),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='floorplans', to='lma_core.event')),
            ],
            options={
                'verbose_name': 'Floorplan',
                'verbose_name_plural': 'Floorplans',
                'ordering': ['event', 'order', 'id'],
            },
            bases=(lma_connect.plugins.core.models.TranslatedTextMixin, models.Model),
        ),
        migrations.RunPython(fields_to_floorplans, floorplans_to_fields),
        migrations.RemoveField(model_name='event', name='floorplan'),
        migrations.RemoveField(model_name='event', name='floorplan_upper'),
    ]
