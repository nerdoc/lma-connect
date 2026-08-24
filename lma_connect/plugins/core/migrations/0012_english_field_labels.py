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
        ('lma_core', '0011_committees_free_form_and_brand_palette'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='committeemembership',
            options={'ordering': ['committee', 'order', 'user__last_name'], 'verbose_name': 'Committee membership', 'verbose_name_plural': 'Committee memberships'},
        ),
        migrations.AlterModelOptions(
            name='consentrecord',
            options={'ordering': ['-created_at'], 'verbose_name': 'Consent', 'verbose_name_plural': 'Consents'},
        ),
        migrations.AlterModelOptions(
            name='room',
            options={'ordering': ['event', 'order', 'name'], 'verbose_name': 'Room', 'verbose_name_plural': 'Rooms'},
        ),
        migrations.AlterField(
            model_name='committeemembership',
            name='affiliation',
            field=models.CharField(blank=True, help_text='Overrides the profile affiliation when set', max_length=200, verbose_name='Affiliation'),
        ),
        migrations.AlterField(
            model_name='committeemembership',
            name='order',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Order'),
        ),
        migrations.AlterField(
            model_name='committeemembership',
            name='role',
            field=models.CharField(choices=[('chair', 'Chair'), ('co_chair', 'Co-Chair'), ('secretary', 'Secretary'), ('member', 'Member')], default='member', max_length=20, verbose_name='Role'),
        ),
        migrations.AlterField(
            model_name='consentrecord',
            name='granted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Granted at'),
        ),
        migrations.AlterField(
            model_name='consentrecord',
            name='notes',
            field=models.TextField(blank=True, verbose_name='Notes'),
        ),
        migrations.AlterField(
            model_name='consentrecord',
            name='type',
            field=models.CharField(choices=[('newsletter', 'Newsletter'), ('profile_public', 'Show profile publicly'), ('photo_usage', 'Photo / video usage'), ('qa_real_name', 'Post Q&A under real name instead of a pseudonym')], max_length=30, verbose_name='Type'),
        ),
        migrations.AlterField(
            model_name='consentrecord',
            name='withdrawn_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Withdrawn at'),
        ),
        migrations.AlterField(
            model_name='event',
            name='address',
            field=models.CharField(blank=True, max_length=300, verbose_name='Address'),
        ),
        migrations.AlterField(
            model_name='event',
            name='address_de',
            field=models.CharField(blank=True, max_length=300, verbose_name='Address (DE)'),
        ),
        migrations.AlterField(
            model_name='event',
            name='city',
            field=models.CharField(blank=True, max_length=120, verbose_name='City'),
        ),
        migrations.AlterField(
            model_name='event',
            name='country',
            field=models.CharField(blank=True, max_length=120, verbose_name='Country'),
        ),
        migrations.AlterField(
            model_name='event',
            name='description',
            field=models.TextField(blank=True, verbose_name='Description (Markdown)'),
        ),
        migrations.AlterField(
            model_name='event',
            name='description_de',
            field=models.TextField(blank=True, verbose_name='Description — DE (Markdown)'),
        ),
        migrations.AlterField(
            model_name='event',
            name='end_date',
            field=models.DateField(verbose_name='End date'),
        ),
        migrations.AlterField(
            model_name='event',
            name='lat',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Latitude'),
        ),
        migrations.AlterField(
            model_name='event',
            name='logo',
            field=models.ImageField(blank=True, help_text='Shown in the topbar; also the source for the home-screen icon', null=True, upload_to='events/event_logos/', verbose_name='Event logo (header)'),
        ),
        migrations.AlterField(
            model_name='event',
            name='lon',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Longitude'),
        ),
        migrations.AlterField(
            model_name='event',
            name='organizer_name',
            field=models.CharField(blank=True, help_text='The association, society or company running the event — shown in the footer', max_length=200, verbose_name='Organizer name'),
        ),
        migrations.AlterField(
            model_name='event',
            name='postal_code',
            field=models.CharField(blank=True, max_length=20, verbose_name='Postal code'),
        ),
        migrations.AlterField(
            model_name='event',
            name='short_name',
            field=models.CharField(blank=True, help_text="Compact name for the topbar and the home-screen icon (e.g. 'ACME 2026'). Falls back to the full name.", max_length=40, verbose_name='Short name'),
        ),
        migrations.AlterField(
            model_name='event',
            name='social_event_info',
            field=models.TextField(blank=True, help_text='Dress code, catering, programme, cost …', verbose_name='Social-Event details (Markdown)'),
        ),
        migrations.AlterField(
            model_name='event',
            name='social_event_meeting_point',
            field=models.CharField(blank=True, help_text="e.g. 'Foyer of the main building'", max_length=200, verbose_name='Meeting point'),
        ),
        migrations.AlterField(
            model_name='event',
            name='social_event_meeting_time',
            field=models.DateTimeField(blank=True, help_text='When to be at the meeting point (for a shared transfer)', null=True, verbose_name='Meeting time'),
        ),
        migrations.AlterField(
            model_name='event',
            name='social_event_title',
            field=models.CharField(blank=True, help_text="e.g. 'Conference Dinner', 'Networking Reception'", max_length=200, verbose_name='Social-Event title'),
        ),
        migrations.AlterField(
            model_name='event',
            name='start_date',
            field=models.DateField(verbose_name='Start date'),
        ),
        migrations.AlterField(
            model_name='event',
            name='subtitle',
            field=models.CharField(blank=True, max_length=300, verbose_name='Subtitle'),
        ),
        migrations.AlterField(
            model_name='event',
            name='subtitle_de',
            field=models.CharField(blank=True, max_length=300, verbose_name='Subtitle (DE)'),
        ),
        migrations.AlterField(
            model_name='event',
            name='timezone_name',
            field=models.CharField(default='Europe/Vienna', help_text="IANA name, e.g. 'Europe/Vienna', 'America/New_York'", max_length=64, verbose_name='Time zone'),
        ),
        migrations.AlterField(
            model_name='event',
            name='venue_name',
            field=models.CharField(blank=True, max_length=200, verbose_name='Venue'),
        ),
        migrations.AlterField(
            model_name='event',
            name='venue_name_de',
            field=models.CharField(blank=True, max_length=200, verbose_name='Venue (DE)'),
        ),
        migrations.AlterField(
            model_name='event',
            name='welcome_image',
            field=models.ImageField(blank=True, help_text='Main image on the welcome screen', null=True, upload_to='events/welcome/', verbose_name='Welcome hero image'),
        ),
        migrations.AlterField(
            model_name='floorplan',
            name='title_de',
            field=models.CharField(blank=True, max_length=120, verbose_name='Label (DE)'),
        ),
        migrations.AlterField(
            model_name='infoblock',
            name='title_de',
            field=models.CharField(blank=True, max_length=200, verbose_name='Title (DE)'),
        ),
        migrations.AlterField(
            model_name='legalpage',
            name='title_de',
            field=models.CharField(blank=True, max_length=200, verbose_name='Title (DE)'),
        ),
        migrations.AlterField(
            model_name='room',
            name='capacity',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Capacity'),
        ),
        migrations.AlterField(
            model_name='room',
            name='floor',
            field=models.CharField(blank=True, max_length=40, verbose_name='Floor'),
        ),
        migrations.AlterField(
            model_name='room',
            name='notes',
            field=models.TextField(blank=True, verbose_name='Notes'),
        ),
        migrations.AlterField(
            model_name='room',
            name='order',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Order'),
        ),
        migrations.AlterField(
            model_name='user',
            name='institution',
            field=models.CharField(blank=True, help_text="e.g. 'St Mary's University Hospital'", max_length=200, verbose_name='Institution'),
        ),
    ]
