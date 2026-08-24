"""Achievements ans Publikums-Voting anpassen.

Neu: `star_giver` — alle Sterne vergeben.
Geändert: `poster_fan` / `expo_champion` zählen jetzt Poster-Check-ins statt
Bewertungen. Sterne sind auf 3 pro Event begrenzt, eine 5er-Schwelle darauf
wäre unerreichbar; die Regeln dazu stehen in services.ACHIEVEMENT_RULES.
"""

from django.db import migrations

NEW = [
    ("star_giver", "Star Giver", "Gave away all 3 audience stars", "ti-stars", 120),
]

UPDATED = [
    ("poster_fan",    "Poster Fan",    "Visited 5 or more posters",                     "ti-star",   100),
    ("expo_champion", "Expo Champion", "3 booth quizzes correct and 5 posters visited",  "ti-trophy", 110),
]

# Für die Rückwärts-Migration: die Texte, wie sie vor dem Voting lauteten.
PREVIOUS = [
    ("poster_fan",    "Poster Fan",    "Rated 5 or more posters",                       "ti-star",   100),
    ("expo_champion", "Expo Champion", "3 booth quizzes correct and 5 posters rated",   "ti-trophy", 110),
]


def _upsert(apps, rows):
    Achievement = apps.get_model("lma_gamification", "Achievement")
    for key, name, desc, icon, order in rows:
        Achievement.objects.update_or_create(
            key=key,
            defaults={"name": name, "description": desc, "icon_class": icon, "order": order},
        )


def apply_changes(apps, schema_editor):
    _upsert(apps, NEW + UPDATED)


def revert_changes(apps, schema_editor):
    Achievement = apps.get_model("lma_gamification", "Achievement")
    Achievement.objects.filter(key__in=[a[0] for a in NEW]).delete()
    _upsert(apps, PREVIOUS)


class Migration(migrations.Migration):
    dependencies = [
        ("lma_gamification", "0005_alter_scoreentry_action"),
    ]
    operations = [
        migrations.RunPython(apply_changes, revert_changes),
    ]
