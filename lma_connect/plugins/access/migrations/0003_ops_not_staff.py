"""Operations-Team-Mitglieder brauchen kein is_staff/Admin.

Das Ops-Backend (/ops/) ist gruppenbasiert (`ops_required` prüft die Gruppe
"Operations Team" bzw. Superuser) — `is_staff`/Django-Admin ist dafür nicht
nötig. Frühere Setups gaben Ops-Leuten trotzdem is_staff. Diese Migration
entzieht es bestehenden Ops-Mitgliedern (Superuser ausgenommen).

Konten, die aus anderen Gründen Admin brauchen, sollten Superuser sein oder
gezielt is_staff im Django-Admin gesetzt bekommen — nicht qua Ops-Gruppe.
"""

from django.db import migrations

OPS_GROUP = "Operations Team"


def demote_ops(apps, schema_editor):
    User = apps.get_model("lma_core", "User")
    Group = apps.get_model("auth", "Group")
    try:
        group = Group.objects.get(name=OPS_GROUP)
    except Group.DoesNotExist:
        return
    (
        User.objects.filter(groups=group, is_staff=True, is_superuser=False)
        .update(is_staff=False)
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("lma_access", "0002_initial"),
        ("lma_core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(demote_ops, noop),
    ]
