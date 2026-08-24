"""Reviewer sollen kein is_staff/Admin haben.

Frühere Seeds legten Mitglieder der Gruppe "Abstract Reviewer" mit
is_staff=True an (Admin-Zugriff). Das gab ihnen faktisch auch Chair-Rechte
für ALLE Sessions und Django-Admin-Zugang. Bewertet wird aber ausschließlich
über das Frontend (login + Zuweisung) — Admin/Chair braucht ein Reviewer nicht.

Diese Migration entzieht bestehenden Reviewern is_staff. Superuser werden
ausgenommen (deren Rechte sind absichtlich). Reine Ops-Mitglieder (nicht in
der Reviewer-Gruppe) bleiben unberührt.
"""

from django.db import migrations

REVIEWER_GROUP = "Abstract Reviewer"


def demote_reviewers(apps, schema_editor):
    User = apps.get_model("lma_core", "User")
    Group = apps.get_model("auth", "Group")
    try:
        group = Group.objects.get(name=REVIEWER_GROUP)
    except Group.DoesNotExist:
        return
    (
        User.objects.filter(groups=group, is_staff=True, is_superuser=False)
        .update(is_staff=False)
    )


def noop(apps, schema_editor):
    # Kein sinnvolles Rückwärts — wir wollen is_staff nicht blind wieder setzen.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("lma_abstracts", "0004_abstract_peer_review"),
        ("lma_core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(demote_reviewers, noop),
    ]
