"""Die drei festen Info-Themenfelder am Event weichen den Info-Blöcken.

travel_info / sightseeing_info / general_info (+ _de) waren geraten: sie legten
fest, worüber eine Konferenz informiert. Ihr Inhalt zieht hier verlustfrei in
InfoBlock-Datensätze um, danach fallen die Spalten weg. Rückwärts läuft es
genauso — die drei Blöcke wandern zurück in die Felder, alle anderen bleiben
als Info-Blöcke bestehen (sie hatten vorher keinen Platz im Modell).
"""

from django.db import migrations, models

# (Feldname, Blocktitel EN, Blocktitel DE, Icon, Sortierung) — die Titel sind
# zugleich der Schlüssel für den Rückweg.
FIELD_BLOCKS = [
    ("travel_info", "How to get there", "Anreise", "train", 10),
    ("sightseeing_info", "Sightseeing", "Sightseeing", "camera", 20),
    ("general_info", "Practical info", "Praktische Infos", "info-circle", 30),
]


def fields_to_blocks(apps, schema_editor):
    Event = apps.get_model("lma_core", "Event")
    InfoBlock = apps.get_model("lma_core", "InfoBlock")
    for event in Event.objects.all():
        for field, title, title_de, icon, order in FIELD_BLOCKS:
            body = getattr(event, field, "") or ""
            body_de = getattr(event, f"{field}_de", "") or ""
            if not body.strip() and not body_de.strip():
                continue
            InfoBlock.objects.create(
                event=event, title=title, title_de=title_de, icon=icon,
                body=body, body_de=body_de, order=order, is_published=True,
            )


def blocks_to_fields(apps, schema_editor):
    Event = apps.get_model("lma_core", "Event")
    InfoBlock = apps.get_model("lma_core", "InfoBlock")
    for field, title, _title_de, _icon, _order in FIELD_BLOCKS:
        for block in InfoBlock.objects.filter(title=title):
            Event.objects.filter(pk=block.event_id).update(
                **{field: block.body, f"{field}_de": block.body_de})
            block.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('lma_core', '0007_alter_event_general_info_infoblock'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='emergency_number',
            field=models.CharField(blank=True, default='112', help_text='Shown as a quick-dial tile on the Info tab. 112 covers the EU; use 911 (US), 000 (AU) … Leave empty to hide the tile.', max_length=30, verbose_name='Emergency number'),
        ),
        migrations.RunPython(fields_to_blocks, blocks_to_fields),
        migrations.RemoveField(model_name='event', name='general_info'),
        migrations.RemoveField(model_name='event', name='general_info_de'),
        migrations.RemoveField(model_name='event', name='sightseeing_info'),
        migrations.RemoveField(model_name='event', name='sightseeing_info_de'),
        migrations.RemoveField(model_name='event', name='travel_info'),
        migrations.RemoveField(model_name='event', name='travel_info_de'),
    ]
