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

import lma_connect.plugins.access.models


class Migration(migrations.Migration):

    dependencies = [
        ('lma_access', '0005_loginattempt_loginfailurelog_loginlog'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='accesstoken',
            options={'ordering': ['-created_at'], 'verbose_name': 'Access token', 'verbose_name_plural': 'Access tokens'},
        ),
        migrations.AlterField(
            model_name='accesstoken',
            name='is_active',
            field=models.BooleanField(default=True, help_text='Deactivate to stop the token from being redeemed — use this for a lost badge', verbose_name='Active'),
        ),
        migrations.AlterField(
            model_name='accesstoken',
            name='label',
            field=models.CharField(blank=True, help_text="For the organizers, e.g. 'speaker slot 12' or 'spare'", max_length=200, verbose_name='Label (internal)'),
        ),
        migrations.AlterField(
            model_name='accesstoken',
            name='last_seen_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Last seen'),
        ),
        migrations.AlterField(
            model_name='accesstoken',
            name='notes',
            field=models.TextField(blank=True, verbose_name='Notes (internal)'),
        ),
        migrations.AlterField(
            model_name='accesstoken',
            name='redeemed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Redeemed at'),
        ),
        migrations.AlterField(
            model_name='accesstoken',
            name='token',
            field=models.CharField(default=lma_connect.plugins.access.models._gen_token, help_text='This is what the QR code encodes', max_length=32, unique=True, verbose_name='Token'),
        ),
        migrations.AlterField(
            model_name='accesstoken',
            name='user',
            field=models.ForeignKey(blank=True, help_text='Created on first redemption', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='access_tokens', to=settings.AUTH_USER_MODEL),
        ),
    ]
