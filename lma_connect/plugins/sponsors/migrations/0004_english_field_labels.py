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
        ('lma_sponsors', '0003_sponsor_is_featured'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='sponsor',
            options={'ordering': ['event', 'tier__order', 'order', 'name'], 'verbose_name': 'Sponsor', 'verbose_name_plural': 'Sponsors'},
        ),
        migrations.AlterModelOptions(
            name='sponsorcontact',
            options={'ordering': ['sponsor', 'order', 'name'], 'verbose_name': 'Sponsor contact', 'verbose_name_plural': 'Sponsor contacts'},
        ),
        migrations.AlterModelOptions(
            name='sponsorimage',
            options={'ordering': ['sponsor', 'order'], 'verbose_name': 'Sponsor image', 'verbose_name_plural': 'Sponsor images'},
        ),
        migrations.AlterModelOptions(
            name='sponsortier',
            options={'ordering': ['event', 'order', 'name'], 'verbose_name': 'Sponsor tier', 'verbose_name_plural': 'Sponsor tiers'},
        ),
        migrations.AlterField(
            model_name='sponsor',
            name='bio_long',
            field=models.TextField(blank=True, verbose_name='Full bio (Markdown)'),
        ),
        migrations.AlterField(
            model_name='sponsor',
            name='bio_long_en',
            field=models.TextField(blank=True, verbose_name='Full bio — EN (Markdown)'),
        ),
        migrations.AlterField(
            model_name='sponsor',
            name='bio_short',
            field=models.CharField(blank=True, help_text='One-sentence pitch for the sponsor list', max_length=300, verbose_name='Short bio'),
        ),
        migrations.AlterField(
            model_name='sponsor',
            name='bio_short_en',
            field=models.CharField(blank=True, help_text='Leave empty and the source text is shown in English too', max_length=300, verbose_name='Short bio (EN)'),
        ),
        migrations.AlterField(
            model_name='sponsor',
            name='booth_location',
            field=models.CharField(blank=True, help_text="e.g. 'Foyer A — booth B12'", max_length=200, verbose_name='Booth location'),
        ),
        migrations.AlterField(
            model_name='sponsor',
            name='booth_location_en',
            field=models.CharField(blank=True, help_text="e.g. 'Foyer A — booth B12'", max_length=200, verbose_name='Booth location (EN)'),
        ),
        migrations.AlterField(
            model_name='sponsor',
            name='booth_x',
            field=models.DecimalField(blank=True, decimal_places=4, help_text='0.0 = left edge, 1.0 = right edge', max_digits=5, null=True, verbose_name='Floorplan X'),
        ),
        migrations.AlterField(
            model_name='sponsor',
            name='booth_y',
            field=models.DecimalField(blank=True, decimal_places=4, help_text='0.0 = top edge, 1.0 = bottom edge', max_digits=5, null=True, verbose_name='Floorplan Y'),
        ),
        migrations.AlterField(
            model_name='sponsor',
            name='contact_email',
            field=models.EmailField(blank=True, max_length=254, verbose_name='Contact email'),
        ),
        migrations.AlterField(
            model_name='sponsor',
            name='contact_person',
            field=models.CharField(blank=True, max_length=200, verbose_name='Contact person'),
        ),
        migrations.AlterField(
            model_name='sponsor',
            name='contract_signed_at',
            field=models.DateField(blank=True, null=True, verbose_name='Contract signed'),
        ),
        migrations.AlterField(
            model_name='sponsor',
            name='highlights_md',
            field=models.TextField(blank=True, help_text='Bullet points on products and news — given prominence on the detail page', verbose_name='Highlights (Markdown)'),
        ),
        migrations.AlterField(
            model_name='sponsor',
            name='is_featured',
            field=models.BooleanField(default=False, help_text="The logo appears on the welcome screen and in the home page header. Only takes effect when 'Show publicly' is set and a logo is uploaded.", verbose_name='Headline sponsor (home page)'),
        ),
        migrations.AlterField(
            model_name='sponsor',
            name='is_published',
            field=models.BooleanField(default=False, verbose_name='Show publicly'),
        ),
        migrations.AlterField(
            model_name='sponsor',
            name='logo',
            field=models.ImageField(blank=True, help_text='Uploaded by the organizers only — see the module docstring on why there is no self-service form', null=True, upload_to='sponsors/logos/', verbose_name='Logo'),
        ),
        migrations.AlterField(
            model_name='sponsor',
            name='notes_internal',
            field=models.TextField(blank=True, help_text='Never shown publicly', verbose_name='Internal notes'),
        ),
        migrations.AlterField(
            model_name='sponsor',
            name='order',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Order within the tier'),
        ),
        migrations.AlterField(
            model_name='sponsor',
            name='paid_at',
            field=models.DateField(blank=True, null=True, verbose_name='Paid'),
        ),
        migrations.AlterField(
            model_name='sponsor',
            name='website',
            field=models.URLField(blank=True, verbose_name='Website'),
        ),
        migrations.AlterField(
            model_name='sponsorcontact',
            name='email',
            field=models.EmailField(blank=True, max_length=254, verbose_name='Email'),
        ),
        migrations.AlterField(
            model_name='sponsorcontact',
            name='expertise',
            field=models.CharField(blank=True, help_text="e.g. 'Haematology, point-of-care testing'", max_length=300, verbose_name='Field of expertise'),
        ),
        migrations.AlterField(
            model_name='sponsorcontact',
            name='order',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Order'),
        ),
        migrations.AlterField(
            model_name='sponsorcontact',
            name='phone',
            field=models.CharField(blank=True, max_length=40, verbose_name='Phone'),
        ),
        migrations.AlterField(
            model_name='sponsorcontact',
            name='photo',
            field=models.ImageField(blank=True, null=True, upload_to='sponsors/contacts/', verbose_name='Photo'),
        ),
        migrations.AlterField(
            model_name='sponsorcontact',
            name='role',
            field=models.CharField(blank=True, help_text="e.g. 'Regional Sales Manager'", max_length=200, verbose_name='Role'),
        ),
        migrations.AlterField(
            model_name='sponsorcontact',
            name='role_en',
            field=models.CharField(blank=True, max_length=200, verbose_name='Role (EN)'),
        ),
        migrations.AlterField(
            model_name='sponsorimage',
            name='caption',
            field=models.CharField(blank=True, max_length=200, verbose_name='Caption'),
        ),
        migrations.AlterField(
            model_name='sponsorimage',
            name='caption_en',
            field=models.CharField(blank=True, max_length=200, verbose_name='Caption (EN)'),
        ),
        migrations.AlterField(
            model_name='sponsorimage',
            name='image',
            field=models.ImageField(upload_to='sponsors/images/', verbose_name='Image'),
        ),
        migrations.AlterField(
            model_name='sponsorimage',
            name='order',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Order'),
        ),
        migrations.AlterField(
            model_name='sponsorlink',
            name='description',
            field=models.CharField(blank=True, max_length=300, verbose_name='Short description'),
        ),
        migrations.AlterField(
            model_name='sponsorlink',
            name='description_en',
            field=models.CharField(blank=True, max_length=300, verbose_name='Short description (EN)'),
        ),
        migrations.AlterField(
            model_name='sponsorlink',
            name='order',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Order'),
        ),
        migrations.AlterField(
            model_name='sponsorlink',
            name='type',
            field=models.CharField(choices=[('product', 'Product'), ('news', 'News'), ('whitepaper', 'Whitepaper / Study'), ('video', 'Video'), ('other', 'Other')], default='other', max_length=20, verbose_name='Type'),
        ),
        migrations.AlterField(
            model_name='sponsortier',
            name='color',
            field=models.CharField(default='#f59e0b', help_text="Hex including the '#' — e.g. gold = #f59e0b", max_length=7, verbose_name='Colour'),
        ),
        migrations.AlterField(
            model_name='sponsortier',
            name='order',
            field=models.PositiveSmallIntegerField(default=0, help_text='0 = topmost', verbose_name='Order'),
        ),
        migrations.AlterField(
            model_name='sponsortier',
            name='perks_md',
            field=models.TextField(blank=True, help_text='What the package includes', verbose_name='Package contents (Markdown)'),
        ),
        migrations.AlterField(
            model_name='sponsortier',
            name='price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Price'),
        ),
        migrations.AlterField(
            model_name='sponsortier',
            name='slot_count',
            field=models.PositiveSmallIntegerField(default=0, help_text='0 = unlimited', verbose_name='Number of slots'),
        ),
    ]
