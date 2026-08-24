"""Committees become free-form, and the brand palette moves into the event.

Two changes that both take a decision out of the code and hand it to the
organizer:

* Committee had a fixed `type` (organizing / scientific / local / advisory)
  with a "one per type and event" constraint. That ruled out a second
  scientific committee, a poster jury or any committee whose name is not one
  of those four. It is replaced by a free name plus a slug.
* Event gains three more colours, so the full five-colour palette that drives
  the interface can be set per event. Until now three of the five were
  hard-coded in base.html, which meant every conference ran in the colours of
  the one this app was first written for.

The data migration derives each committee's slug from its old type, so
existing rows keep working and their URLs stay stable.
"""
import django.core.validators
from django.db import migrations, models
from django.utils.text import slugify

# The labels the four old choices carried. Used in both directions: forwards
# to give a committee a name when it had none, backwards to map a slug onto a
# type again.
LEGACY_TYPES = {
    "organizing": "Organizing committee",
    "scientific": "Scientific committee",
    "local": "Local committee",
    "advisory": "Advisory board",
}


def fill_slugs(apps, schema_editor):
    """Give every committee a slug — from its type, or from its name."""
    Committee = apps.get_model("lma_core", "Committee")
    seen: set[tuple[int, str]] = set()
    for committee in Committee.objects.all().order_by("event_id", "order", "pk"):
        base = committee.type or slugify(committee.name) or "committee"
        slug, suffix = base, 2
        while (committee.event_id, slug) in seen:
            slug, suffix = f"{base}-{suffix}", suffix + 1
        seen.add((committee.event_id, slug))
        committee.slug = slug
        if not committee.name:
            committee.name = LEGACY_TYPES.get(committee.type, "Committee")
        committee.save(update_fields=["slug", "name"])


def restore_types(apps, schema_editor):
    """Reverse: map the slug back onto one of the four old type values.

    A slug that is not one of them (which is the whole point of the change)
    cannot be represented, so it falls back to "organizing" — the reverse of
    this migration is a rollback path, not a lossless round trip.
    """
    Committee = apps.get_model("lma_core", "Committee")
    for committee in Committee.objects.all():
        committee.type = committee.slug if committee.slug in LEGACY_TYPES else "organizing"
        committee.save(update_fields=["type"])


class Migration(migrations.Migration):

    dependencies = [
        ('lma_core', '0010_legal_pages_replace_event_fields'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='committee',
            options={'ordering': ['event', 'order'], 'verbose_name': 'Committee', 'verbose_name_plural': 'Committees'},
        ),
        # Drop the old "one committee per type" rule before the type field
        # itself goes, otherwise the constraint outlives its column.
        migrations.AlterUniqueTogether(
            name='committee',
            unique_together=set(),
        ),
        # Added with a default so existing rows survive the ALTER; the default
        # is removed again further down, once every row has a real slug.
        migrations.AddField(
            model_name='committee',
            name='slug',
            field=models.SlugField(default='', help_text="Used in URLs and anchors — e.g. 'scientific'", max_length=120, verbose_name='Slug'),
        ),
        migrations.RunPython(fill_slugs, restore_types),
        migrations.AddConstraint(
            model_name='committee',
            constraint=models.UniqueConstraint(fields=('event', 'slug'), name='unique_committee_slug_per_event'),
        ),
        # Give `type` a default before dropping it. Django reconstructs the
        # column from this state when the migration runs backwards, and
        # re-adding a NOT NULL column without a default fails on a table that
        # already has rows — which would make the rollback impossible.
        migrations.AlterField(
            model_name='committee',
            name='type',
            field=models.CharField(choices=[('organizing', 'Organizing committee'), ('scientific', 'Scientific committee'), ('local', 'Local committee'), ('advisory', 'Advisory board')], default='organizing', max_length=20, verbose_name='Typ'),
        ),
        migrations.RemoveField(
            model_name='committee',
            name='type',
        ),
        migrations.AlterField(
            model_name='committee',
            name='slug',
            field=models.SlugField(help_text="Used in URLs and anchors — e.g. 'scientific'", max_length=120, verbose_name='Slug'),
        ),
        migrations.AlterField(
            model_name='committee',
            name='description',
            field=models.TextField(blank=True, verbose_name='Description'),
        ),
        migrations.AlterField(
            model_name='committee',
            name='name',
            field=models.CharField(help_text="e.g. 'Scientific Committee', 'Local Organizing Committee', 'Poster Jury'", max_length=200, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='committee',
            name='order',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Order'),
        ),
        migrations.AddField(
            model_name='event',
            name='highlight_color',
            field=models.CharField(default='#ffcf4d', help_text='Warnings, awards, the marker under the active bottom-nav tab', max_length=7, validators=[django.core.validators.RegexValidator('^#[0-9a-fA-F]{6}$', "Six-digit hex colour including the leading '#' — e.g. #457b9d.")], verbose_name='Highlight colour'),
        ),
        migrations.AddField(
            model_name='event',
            name='surface_color',
            field=models.CharField(default='#f2f4ff', help_text='Background behind the cards. Keep it light — the text colour sits on it.', max_length=7, validators=[django.core.validators.RegexValidator('^#[0-9a-fA-F]{6}$', "Six-digit hex colour including the leading '#' — e.g. #457b9d.")], verbose_name='Page background'),
        ),
        migrations.AddField(
            model_name='event',
            name='text_color',
            field=models.CharField(default='#3c1518', help_text='Body text. Check the contrast against the page background.', max_length=7, validators=[django.core.validators.RegexValidator('^#[0-9a-fA-F]{6}$', "Six-digit hex colour including the leading '#' — e.g. #457b9d.")], verbose_name='Text colour'),
        ),
        migrations.AlterField(
            model_name='event',
            name='accent_color',
            field=models.CharField(default='#fe5f55', help_text='Attention-drawing elements — danger badges, live markers', max_length=7, validators=[django.core.validators.RegexValidator('^#[0-9a-fA-F]{6}$', "Six-digit hex colour including the leading '#' — e.g. #457b9d.")], verbose_name='Accent colour'),
        ),
        migrations.AlterField(
            model_name='event',
            name='theme_color',
            field=models.CharField(default='#457b9d', help_text='Buttons, links, active nav item, browser theme colour', max_length=7, validators=[django.core.validators.RegexValidator('^#[0-9a-fA-F]{6}$', "Six-digit hex colour including the leading '#' — e.g. #457b9d.")], verbose_name='Primary colour'),
        ),
    ]
