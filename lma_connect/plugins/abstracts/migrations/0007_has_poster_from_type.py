"""Bestehende Poster-Abstracts als „Poster hängt aus" markieren.

Bis hierher war `type == poster` das einzige Kriterium dafür, ob ein Abstract
einen QR-Bogen bekommt und bewertbar ist. Das neue Feld `has_poster` löst das
ab, damit auch ein Oral Communication zusätzlich ein Poster aushängen kann.
Diese Migration stellt den bisherigen Stand her — Vorträge mit zusätzlichem
Poster werden danach im Admin angehakt.
"""

from django.db import migrations


def set_has_poster(apps, schema_editor):
    Abstract = apps.get_model("lma_abstracts", "Abstract")
    Abstract.objects.filter(type="poster").update(has_poster=True)


def unset_has_poster(apps, schema_editor):
    Abstract = apps.get_model("lma_abstracts", "Abstract")
    Abstract.objects.update(has_poster=False)


class Migration(migrations.Migration):
    dependencies = [
        ("lma_abstracts", "0006_abstract_has_poster_abstractstarvote"),
    ]
    operations = [
        migrations.RunPython(set_has_poster, unset_has_poster),
    ]
