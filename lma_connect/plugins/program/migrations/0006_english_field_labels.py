"""Field labels and help texts are now English source strings.

Verbose names and help texts used to be a mix of German and English msgids.
For an open-source project the source language has to be one thing, and that
thing is English — the German wording moved into locale/de where it belongs.

Nothing here touches the database: verbose_name and help_text are metadata
Django keeps in the migration state, so this migration only exists to keep
that state in sync with the models.
"""
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lma_program', '0005_session_screen_poll_session_screen_source'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='livepoll',
            options={'ordering': ['-created_at'], 'verbose_name': 'Live poll', 'verbose_name_plural': 'Live polls'},
        ),
        migrations.AlterModelOptions(
            name='livepollresponse',
            options={'ordering': ['-created_at'], 'verbose_name': 'Live poll response', 'verbose_name_plural': 'Live poll responses'},
        ),
        migrations.AlterModelOptions(
            name='question',
            options={'ordering': ['-created_at'], 'verbose_name': 'Live Q&A question', 'verbose_name_plural': 'Live Q&A questions'},
        ),
        migrations.AlterModelOptions(
            name='sessionrating',
            options={'ordering': ['-created_at'], 'verbose_name': 'Session rating', 'verbose_name_plural': 'Session ratings'},
        ),
        migrations.AlterField(
            model_name='livepoll',
            name='closes_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Closes at'),
        ),
        migrations.AlterField(
            model_name='livepoll',
            name='is_active',
            field=models.BooleanField(default=False, verbose_name='Active'),
        ),
        migrations.AlterField(
            model_name='livepoll',
            name='is_results_public',
            field=models.BooleanField(default=False, help_text='Off = attendees only vote and see no results on their own device; the chair projects the outcome from the projection view. Switch on to release the results into the app as well.', verbose_name='Show results in the app'),
        ),
        migrations.AlterField(
            model_name='livepoll',
            name='opens_at',
            field=models.DateTimeField(blank=True, help_text='Empty = activated by hand', null=True, verbose_name='Opens at'),
        ),
        migrations.AlterField(
            model_name='livepoll',
            name='question_text',
            field=models.CharField(max_length=400, verbose_name='Question'),
        ),
        migrations.AlterField(
            model_name='livepoll',
            name='type',
            field=models.CharField(choices=[('single', 'Single choice'), ('multi', 'Multi choice'), ('open', 'Open text')], default='single', max_length=20, verbose_name='Type'),
        ),
        migrations.AlterField(
            model_name='livepolloption',
            name='order',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Order'),
        ),
        migrations.AlterField(
            model_name='livepolloption',
            name='text',
            field=models.CharField(max_length=200, verbose_name='Answer'),
        ),
        migrations.AlterField(
            model_name='livepollresponse',
            name='text_answer',
            field=models.TextField(blank=True, verbose_name='Free-text answer'),
        ),
        migrations.AlterField(
            model_name='question',
            name='answered_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Answered at'),
        ),
        migrations.AlterField(
            model_name='question',
            name='asker_display_name',
            field=models.CharField(blank=True, help_text='Pseudonym — empty when posting under the real name', max_length=80, verbose_name='Display name'),
        ),
        migrations.AlterField(
            model_name='question',
            name='flagged_count',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Times flagged'),
        ),
        migrations.AlterField(
            model_name='question',
            name='is_answered',
            field=models.BooleanField(default=False, verbose_name='Answered'),
        ),
        migrations.AlterField(
            model_name='question',
            name='is_approved',
            field=models.BooleanField(default=False, help_text='Required in moderated sessions; set automatically otherwise', verbose_name='Approved'),
        ),
        migrations.AlterField(
            model_name='question',
            name='text',
            field=models.TextField(max_length=2000, verbose_name='Question'),
        ),
        migrations.AlterField(
            model_name='session',
            name='ends_at',
            field=models.DateTimeField(verbose_name='Ends at'),
        ),
        migrations.AlterField(
            model_name='session',
            name='is_published',
            field=models.BooleanField(default=False, verbose_name='Published'),
        ),
        migrations.AlterField(
            model_name='session',
            name='qa_enabled',
            field=models.BooleanField(default=True, help_text='Attendees may submit questions during the session', verbose_name='Live Q&A enabled'),
        ),
        migrations.AlterField(
            model_name='session',
            name='rating_enabled',
            field=models.BooleanField(default=True, verbose_name='Rating enabled'),
        ),
        migrations.AlterField(
            model_name='session',
            name='screen_poll',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='lma_program.livepoll', verbose_name='Projected poll'),
        ),
        migrations.AlterField(
            model_name='session',
            name='screen_source',
            field=models.CharField(choices=[('standby', 'Standby'), ('qa', 'Q&A'), ('poll', 'Umfrage-Ergebnisse')], default='standby', max_length=10, verbose_name='Screen source'),
        ),
        migrations.AlterField(
            model_name='session',
            name='starts_at',
            field=models.DateTimeField(verbose_name='Starts at'),
        ),
        migrations.AlterField(
            model_name='session',
            name='summary',
            field=models.TextField(blank=True, verbose_name='Summary (Markdown)'),
        ),
        migrations.AlterField(
            model_name='session',
            name='title',
            field=models.CharField(max_length=300, verbose_name='Title'),
        ),
        migrations.AlterField(
            model_name='session',
            name='type',
            field=models.CharField(choices=[('keynote', 'Keynote'), ('talk', 'Oral communication'), ('panel', 'Panel discussion'), ('workshop', 'Workshop'), ('symposium', 'Symposium'), ('break', 'Break / Catering'), ('poster', 'Poster session')], default='talk', max_length=20, verbose_name='Type'),
        ),
        migrations.AlterField(
            model_name='sessionrating',
            name='comment',
            field=models.TextField(blank=True, verbose_name='Comment (Markdown, optional)'),
        ),
        migrations.AlterField(
            model_name='sessionrating',
            name='is_anonymous',
            field=models.BooleanField(default=True, help_text='Protects the raw responses; the aggregate stays visible', verbose_name='Show anonymously'),
        ),
        migrations.AlterField(
            model_name='sessionrating',
            name='rating_clarity',
            field=models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name='Clarity (English)'),
        ),
        migrations.AlterField(
            model_name='sessionspeaker',
            name='order',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Order'),
        ),
        migrations.AlterField(
            model_name='sessionspeaker',
            name='role',
            field=models.CharField(choices=[('chair', 'Chair'), ('speaker', 'Speaker'), ('co_author', 'Co-author'), ('discussant', 'Discussant')], default='speaker', max_length=20, verbose_name='Role'),
        ),
        migrations.AlterField(
            model_name='track',
            name='color',
            field=models.CharField(default='#206bc4', help_text="Hex including the '#' — accent on the session cards", max_length=7, verbose_name='Colour'),
        ),
        migrations.AlterField(
            model_name='track',
            name='description',
            field=models.TextField(blank=True, verbose_name='Description'),
        ),
        migrations.AlterField(
            model_name='track',
            name='order',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Order'),
        ),
    ]
