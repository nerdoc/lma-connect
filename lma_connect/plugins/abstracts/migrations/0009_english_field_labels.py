"""Field labels and help texts are now English source strings.

Verbose names and help texts used to be a mix of German and English msgids.
For an open-source project the source language has to be one thing, and that
thing is English — the German wording moved into locale/de where it belongs.

Nothing here touches the database: verbose_name and help_text are metadata
Django keeps in the migration state, so this migration only exists to keep
that state in sync with the models.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lma_abstracts', '0008_awards_as_model_and_author_country'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='abstractauthor',
            options={'ordering': ['abstract', 'order'], 'verbose_name': 'Abstract author', 'verbose_name_plural': 'Abstract authors'},
        ),
        migrations.AlterModelOptions(
            name='abstractcategory',
            options={'ordering': ['event', 'order', 'name'], 'verbose_name': 'Abstract category', 'verbose_name_plural': 'Abstract categories'},
        ),
        migrations.AlterModelOptions(
            name='abstractreview',
            options={'ordering': ['abstract', 'reviewer'], 'verbose_name': 'Abstract review', 'verbose_name_plural': 'Abstract reviews'},
        ),
        migrations.AlterModelOptions(
            name='abstractstarvote',
            options={'ordering': ['-created_at'], 'verbose_name': 'Audience star', 'verbose_name_plural': 'Audience stars'},
        ),
        migrations.AlterModelOptions(
            name='abstracttag',
            options={'ordering': ['event', 'name'], 'verbose_name': 'Abstract tag', 'verbose_name_plural': 'Abstract tags'},
        ),
        migrations.AlterField(
            model_name='abstract',
            name='abstract_text',
            field=models.TextField(help_text='Main body — typically 250–300 words', verbose_name='Abstract text (Markdown)'),
        ),
        migrations.AlterField(
            model_name='abstract',
            name='decision_notes',
            field=models.TextField(blank=True, verbose_name='Decision notes (internal)'),
        ),
        migrations.AlterField(
            model_name='abstract',
            name='has_poster',
            field=models.BooleanField(default=False, help_text='A poster with a QR code hangs for this abstract — also possible for talks that additionally show a poster', verbose_name='Poster on display'),
        ),
        migrations.AlterField(
            model_name='abstract',
            name='is_published',
            field=models.BooleanField(default=False, verbose_name='Publicly visible'),
        ),
        migrations.AlterField(
            model_name='abstract',
            name='keywords',
            field=models.CharField(blank=True, help_text='Comma separated', max_length=400, verbose_name='Keywords'),
        ),
        migrations.AlterField(
            model_name='abstract',
            name='location',
            field=models.CharField(blank=True, help_text='Where the poster hangs — e.g. Foyer A, wall 5', max_length=200, verbose_name='Location'),
        ),
        migrations.AlterField(
            model_name='abstract',
            name='poster_id',
            field=models.CharField(blank=True, help_text='e.g. P-042 for poster no. 42, O-15 for oral no. 15', max_length=20, verbose_name='Poster / talk ID'),
        ),
        migrations.AlterField(
            model_name='abstract',
            name='submitted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Submitted at'),
        ),
        migrations.AlterField(
            model_name='abstract',
            name='title',
            field=models.CharField(max_length=400, verbose_name='Title'),
        ),
        migrations.AlterField(
            model_name='abstract',
            name='type',
            field=models.CharField(choices=[('poster', 'Poster'), ('oral', 'Oral communication'), ('keynote', 'Keynote')], default='poster', max_length=20, verbose_name='Type'),
        ),
        migrations.AlterField(
            model_name='abstractauthor',
            name='is_corresponding',
            field=models.BooleanField(default=False, verbose_name='Corresponding author'),
        ),
        migrations.AlterField(
            model_name='abstractauthor',
            name='is_presenting',
            field=models.BooleanField(default=False, verbose_name='Presenting author'),
        ),
        migrations.AlterField(
            model_name='abstractauthor',
            name='order',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Order'),
        ),
        migrations.AlterField(
            model_name='abstractauthor',
            name='user',
            field=models.ForeignKey(blank=True, help_text='Optional — when the author has an account', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='abstract_authorships', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='abstractcategory',
            name='color',
            field=models.CharField(default='#206bc4', max_length=7, verbose_name='Colour'),
        ),
        migrations.AlterField(
            model_name='abstractcategory',
            name='description',
            field=models.TextField(blank=True, verbose_name='Description'),
        ),
        migrations.AlterField(
            model_name='abstractcategory',
            name='order',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Order'),
        ),
        migrations.AlterField(
            model_name='abstractreference',
            name='citation_text',
            field=models.TextField(help_text='Full citation, e.g. Smith J et al. Nature 2024;612:45-53', verbose_name='Citation'),
        ),
        migrations.AlterField(
            model_name='abstractreference',
            name='order',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Number'),
        ),
        migrations.AlterField(
            model_name='abstractreview',
            name='comment',
            field=models.TextField(blank=True, verbose_name='Comment (optional)'),
        ),
        migrations.AlterField(
            model_name='abstractreview',
            name='score',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(1, '1 — excellent'), (2, '2 — very good'), (3, '3 — good'), (4, '4 — borderline'), (5, '5 — weak'), (6, '6 — unsuitable')], null=True, verbose_name='Score 1–6'),
        ),
        migrations.AlterField(
            model_name='abstractreview',
            name='submitted_at',
            field=models.DateTimeField(blank=True, help_text='Set when a score is submitted for the first time', null=True, verbose_name='Submitted at'),
        ),
        migrations.AlterField(
            model_name='abstracttag',
            name='color',
            field=models.CharField(default='#6c757d', max_length=7, verbose_name='Colour'),
        ),
    ]
