"""Seed the default achievement definitions. Ships with the app — these are
domain definitions, not demo data."""

from django.db import migrations

ACHIEVEMENTS = [
    ("first_question",   "Curious Mind",       "Asked your first question",                "ti-message-circle",  10),
    ("discussion_driver", "Discussion Driver",  "Asked 5 or more questions",                "ti-messages",        20),
    ("active_voter",     "Active Voter",        "Up-voted 10 or more questions",            "ti-arrow-big-up",    30),
    ("poll_enthusiast",  "Poll Enthusiast",     "Voted in 3 or more live polls",            "ti-chart-bar",       40),
    ("honest_critic",    "Honest Critic",       "Rated 5 or more sessions",                 "ti-star",            50),
    ("feedback_champion", "Feedback Champion",  "Submitted the post-event feedback survey", "ti-clipboard-check", 60),
    ("fully_engaged",    "Fully Engaged",       "Asked a question, voted, rated and gave feedback", "ti-flame",   70),
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
        ("lma_gamification", "0001_initial"),
    ]
    operations = [
        migrations.RunPython(create_achievements, remove_achievements),
    ]
