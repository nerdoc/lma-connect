"""Field labels and help texts are now English source strings.

Verbose names and help texts used to be a mix of German and English msgids.
For an open-source project the source language has to be one thing, and that
thing is English — the German wording moved into locale/de where it belongs.

Nothing here touches the database: verbose_name and help_text are metadata
Django keeps in the migration state, so this migration only exists to keep
that state in sync with the models.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lma_people', '0002_personprofile_category_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='personprofile',
            options={'ordering': ['event', 'user__last_name', 'user__first_name'], 'verbose_name': 'Person profile', 'verbose_name_plural': 'Person profiles'},
        ),
        migrations.AlterField(
            model_name='personprofile',
            name='country',
            field=models.CharField(blank=True, help_text="Country of the affiliation, e.g. 'Austria'", max_length=120, verbose_name='Country'),
        ),
        migrations.AlterField(
            model_name='personprofile',
            name='country_iso',
            field=models.CharField(blank=True, help_text="Two-letter code, e.g. 'AT' — drives the world map and the flag display", max_length=2, verbose_name='ISO-3166'),
        ),
        migrations.AlterField(
            model_name='personprofile',
            name='cv',
            field=models.FileField(blank=True, help_text='Curriculum vitae as a PDF', null=True, upload_to='people/cv/', verbose_name='CV'),
        ),
        migrations.AlterField(
            model_name='personprofile',
            name='photo',
            field=models.ImageField(blank=True, null=True, upload_to='people/photos/', verbose_name='Photo'),
        ),
        migrations.AlterField(
            model_name='personprofile',
            name='position',
            field=models.CharField(blank=True, help_text="e.g. 'Head of Laboratory Medicine'", max_length=200, verbose_name='Position'),
        ),
        migrations.AlterField(
            model_name='personprofile',
            name='profile_public',
            field=models.BooleanField(default=False, help_text='Only set to true once the matching consent has been recorded', verbose_name='Profile public'),
        ),
        migrations.AlterField(
            model_name='personprofile',
            name='pronouns',
            field=models.CharField(blank=True, help_text='e.g. they/them or she/her — empty means nothing is shown', max_length=40, verbose_name='Pronouns'),
        ),
        migrations.AlterField(
            model_name='personprofile',
            name='website',
            field=models.URLField(blank=True, verbose_name='Website'),
        ),
        migrations.AlterField(
            model_name='speaker',
            name='is_keynote',
            field=models.BooleanField(default=False, verbose_name='Keynote speaker'),
        ),
        migrations.AlterField(
            model_name='speaker',
            name='short_intro',
            field=models.CharField(blank=True, help_text='One-sentence intro for the session cards', max_length=300, verbose_name='Short intro'),
        ),
        migrations.AlterField(
            model_name='speaker',
            name='talk_subjects',
            field=models.CharField(blank=True, help_text="Comma separated, e.g. 'pre-analytics, AI, haematology'", max_length=400, verbose_name='Topic tags'),
        ),
    ]
