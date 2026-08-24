"""Seed the Expo achievement definitions (booths & posters). Domain data,
ships with the app — the award rules live in services.ACHIEVEMENT_RULES."""

from django.db import migrations

ACHIEVEMENTS = [
    ("booth_explorer", "Booth Explorer", "Checked in at 3 or more exhibitor booths", "ti-building-store", 80),
    ("quiz_whiz",      "Quiz Whiz",      "Answered 5 booth quizzes correctly",       "ti-bulb",          90),
    ("poster_fan",     "Poster Fan",     "Rated 5 or more posters",                  "ti-star",         100),
    ("expo_champion",  "Expo Champion",  "3 booth quizzes correct and 5 posters rated", "ti-trophy",    110),
]


def create_achievements(apps, schema_editor):
    Achievement = apps.get_model("lma_gamification", "Achievement")
    for key, name, desc, icon, order in ACHIEVEMENTS:
        Achievement.objects.update_or_create(
            key=key,
            defaults={"name": name, "description": desc, "icon_class": icon, "order": order},
        )


def remove_achievements(apps, schema_editor):
    Achievement = apps.get_model("lma_gamification", "Achievement")
    Achievement.objects.filter(key__in=[a[0] for a in ACHIEVEMENTS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("lma_gamification", "0003_alter_scoreentry_action"),
    ]
    operations = [
        migrations.RunPython(create_achievements, remove_achievements),
    ]
