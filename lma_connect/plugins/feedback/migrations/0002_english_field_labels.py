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
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lma_feedback', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='eventsurvey',
            options={'ordering': ['event', '-created_at'], 'verbose_name': 'Event survey', 'verbose_name_plural': 'Event surveys'},
        ),
        migrations.AlterModelOptions(
            name='surveyquestion',
            options={'ordering': ['survey', 'order'], 'verbose_name': 'Survey question', 'verbose_name_plural': 'Survey questions'},
        ),
        migrations.AlterModelOptions(
            name='surveyresponse',
            options={'ordering': ['-created_at'], 'verbose_name': 'Survey response', 'verbose_name_plural': 'Survey responses'},
        ),
        migrations.AlterField(
            model_name='eventsurvey',
            name='allow_anonymous',
            field=models.BooleanField(default=True, help_text='When off: login required and answers are attributed to the user', verbose_name='Allow anonymous responses'),
        ),
        migrations.AlterField(
            model_name='eventsurvey',
            name='closes_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Closes at'),
        ),
        migrations.AlterField(
            model_name='eventsurvey',
            name='intro_text',
            field=models.TextField(blank=True, verbose_name='Introduction (Markdown)'),
        ),
        migrations.AlterField(
            model_name='eventsurvey',
            name='is_published',
            field=models.BooleanField(default=False, verbose_name='Active'),
        ),
        migrations.AlterField(
            model_name='eventsurvey',
            name='opens_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Opens at'),
        ),
        migrations.AlterField(
            model_name='eventsurvey',
            name='title',
            field=models.CharField(help_text="e.g. 'Your feedback on the conference'", max_length=200, verbose_name='Title'),
        ),
        migrations.AlterField(
            model_name='surveyanswer',
            name='value_bool',
            field=models.BooleanField(blank=True, null=True, verbose_name='Yes/No value'),
        ),
        migrations.AlterField(
            model_name='surveyanswer',
            name='value_int',
            field=models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name='Likert value'),
        ),
        migrations.AlterField(
            model_name='surveyanswer',
            name='value_text',
            field=models.TextField(blank=True, verbose_name='Free-text value'),
        ),
        migrations.AlterField(
            model_name='surveychoice',
            name='order',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Order'),
        ),
        migrations.AlterField(
            model_name='surveychoice',
            name='value',
            field=models.CharField(blank=True, help_text='Optional internal value; defaults to the text', max_length=80, verbose_name='Value'),
        ),
        migrations.AlterField(
            model_name='surveyquestion',
            name='help_text',
            field=models.CharField(blank=True, help_text='Optional — e.g. what the scale means', max_length=300, verbose_name='Help text'),
        ),
        migrations.AlterField(
            model_name='surveyquestion',
            name='is_required',
            field=models.BooleanField(default=False, verbose_name='Required'),
        ),
        migrations.AlterField(
            model_name='surveyquestion',
            name='likert_max_label',
            field=models.CharField(blank=True, help_text="e.g. 'too long'", max_length=40, verbose_name='Likert label (max)'),
        ),
        migrations.AlterField(
            model_name='surveyquestion',
            name='likert_min_label',
            field=models.CharField(blank=True, help_text="e.g. 'too short'", max_length=40, verbose_name='Likert label (min)'),
        ),
        migrations.AlterField(
            model_name='surveyquestion',
            name='order',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Order'),
        ),
        migrations.AlterField(
            model_name='surveyquestion',
            name='text',
            field=models.CharField(max_length=400, verbose_name='Question'),
        ),
        migrations.AlterField(
            model_name='surveyquestion',
            name='type',
            field=models.CharField(choices=[('yes_no', 'Yes / No'), ('likert_5', 'Likert scale 1–5'), ('open_text', 'Open text'), ('multi_choice', 'Multiple choice'), ('single_choice', 'Single choice')], max_length=20, verbose_name='Type'),
        ),
        migrations.AlterField(
            model_name='surveyresponse',
            name='submitted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Submitted at'),
        ),
        migrations.AlterField(
            model_name='surveyresponse',
            name='user',
            field=models.ForeignKey(blank=True, help_text='NULL = anonymous (when allow_anonymous is on)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='survey_responses', to=settings.AUTH_USER_MODEL),
        ),
    ]
