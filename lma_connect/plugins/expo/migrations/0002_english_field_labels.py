"""Field labels and help texts are now English source strings.

Verbose names and help texts used to be a mix of German and English msgids.
For an open-source project the source language has to be one thing, and that
thing is English — the German wording moved into locale/de where it belongs.

Nothing here touches the database: verbose_name and help_text are metadata
Django keeps in the migration state, so this migration only exists to keep
that state in sync with the models.
"""
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lma_expo', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='boothchoice',
            options={'ordering': ['order', 'id'], 'verbose_name': 'Answer option', 'verbose_name_plural': 'Answer options'},
        ),
        migrations.AlterModelOptions(
            name='boothquiz',
            options={'verbose_name': 'Booth quiz', 'verbose_name_plural': 'Booth quizzes'},
        ),
        migrations.AlterModelOptions(
            name='posterrating',
            options={'ordering': ['-created_at'], 'verbose_name': 'Poster rating', 'verbose_name_plural': 'Poster ratings'},
        ),
        migrations.AlterField(
            model_name='boothchoice',
            name='is_correct',
            field=models.BooleanField(default=False, verbose_name='Correct'),
        ),
        migrations.AlterField(
            model_name='boothchoice',
            name='order',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Order'),
        ),
        migrations.AlterField(
            model_name='boothchoice',
            name='text',
            field=models.CharField(max_length=200, verbose_name='Answer text'),
        ),
        migrations.AlterField(
            model_name='boothquiz',
            name='hint',
            field=models.CharField(blank=True, help_text="e.g. 'Ask the booth staff' or 'see the roll-up'", max_length=200, verbose_name='Hint (optional)'),
        ),
        migrations.AlterField(
            model_name='boothquiz',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Active'),
        ),
        migrations.AlterField(
            model_name='boothquiz',
            name='question',
            field=models.CharField(help_text='The answer should be findable at the booth, or something staff can be asked about', max_length=300, verbose_name='Question'),
        ),
        migrations.AlterField(
            model_name='posterrating',
            name='comment',
            field=models.TextField(blank=True, verbose_name='Comment (optional)'),
        ),
        migrations.AlterField(
            model_name='posterrating',
            name='stars',
            field=models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name='Stars'),
        ),
    ]
