# Task #82 — short_intro becomes affiliation (data preserved via RenameField),
# plus a public multi-line intro and private chair notes.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lma_people", "0003_english_field_labels"),
    ]

    operations = [
        migrations.RenameField(
            model_name="speaker",
            old_name="short_intro",
            new_name="affiliation",
        ),
        migrations.AlterField(
            model_name="speaker",
            name="affiliation",
            field=models.CharField(
                blank=True,
                help_text="One-line affiliation/position shown on the session cards, "
                          "e.g. 'Head of Laboratory Medicine, University Hospital Salzburg'",
                max_length=300,
                verbose_name="Affiliation",
            ),
        ),
        migrations.AddField(
            model_name="speaker",
            name="intro",
            field=models.TextField(
                blank=True,
                help_text="A few sentences about the speaker — shown publicly on the "
                          "session and speaker pages",
                verbose_name="Speaker intro",
            ),
        ),
        migrations.AddField(
            model_name="speaker",
            name="chair_notes",
            field=models.TextField(
                blank=True,
                help_text="Private notes for the session chair to introduce the speaker "
                          "— never shown publicly, only in the chair view",
                verbose_name="Chair notes",
            ),
        ),
    ]
