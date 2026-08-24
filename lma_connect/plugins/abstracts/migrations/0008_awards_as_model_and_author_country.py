"""Awards become a per-event model, and abstract authors get a country.

Two changes, both about data that used to live in the code:

* `Abstract.award` was a CharField with six fixed choices (Best Poster,
  Audience Choice, Innovation, …). Which prizes a conference hands out is a
  decision of its jury and changes from year to year, so awards are now rows
  an organizer maintains in the admin. Which one the audience votes for is a
  flag on the award, not a hard-coded slug.
* `AbstractAuthor` gains `country` / `country_iso`. The "where our abstracts
  come from" map used to read a hand-written table of that one conference's
  submissions; it now reads these fields. Most co-authors are external and
  have no user account, which is why the country sits on the author row and
  not on the linked user.

The award data migration is written so the round trip is lossless: the
generated awards keep the old choice values as their slugs, so migrating
backwards restores exactly the strings that were there before.
"""
import django.db.models.deletion
from django.db import migrations, models

# The six choices that used to be hard-coded, in their original order. The
# key becomes the award's slug, which is what makes the reverse exact.
LEGACY_AWARDS = [
    ("best_poster", "Best Poster", False),
    ("best_oral", "Best Oral Presentation", False),
    ("audience_choice", "Audience Choice Award", True),
    ("innovation", "Innovation Award", False),
    ("young_investigator", "Young Investigator Award", False),
    ("jury_special", "Jury Special Mention", False),
]


def create_awards_from_choices(apps, schema_editor):
    """Create an award row per (event, award value) actually in use, and point
    the abstracts at it.

    Only values that are really used are created — an event that never handed
    out an Innovation Award should not find one sitting in its admin.
    """
    Abstract = apps.get_model("lma_abstracts", "Abstract")
    AbstractAward = apps.get_model("lma_abstracts", "AbstractAward")

    labels = {slug: (name, audience) for slug, name, audience in LEGACY_AWARDS}
    order = {slug: index for index, (slug, _name, _audience) in enumerate(LEGACY_AWARDS)}

    in_use = (
        Abstract.objects.exclude(award_legacy="")
        .values_list("event_id", "award_legacy")
        .distinct()
    )
    created: dict[tuple[int, str], object] = {}
    for event_id, slug in in_use:
        name, is_audience = labels.get(slug, (slug.replace("_", " ").title(), False))
        created[(event_id, slug)] = AbstractAward.objects.create(
            event_id=event_id, name=name, slug=slug,
            order=order.get(slug, 99), is_audience_choice=is_audience,
        )

    for (event_id, slug), award in created.items():
        Abstract.objects.filter(event_id=event_id, award_legacy=slug).update(award=award)


def restore_award_strings(apps, schema_editor):
    """Reverse: write the award's slug back into the legacy char column."""
    Abstract = apps.get_model("lma_abstracts", "Abstract")
    for abstract in Abstract.objects.exclude(award__isnull=True).select_related("award"):
        abstract.award_legacy = abstract.award.slug
        abstract.save(update_fields=["award_legacy"])


class Migration(migrations.Migration):

    dependencies = [
        ('lma_abstracts', '0007_has_poster_from_type'),
        ('lma_core', '0011_committees_free_form_and_brand_palette'),
    ]

    operations = [
        migrations.CreateModel(
            name='AbstractAward',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(help_text="e.g. 'Best Poster', 'Young Investigator Award'", max_length=120, verbose_name='Name')),
                ('slug', models.SlugField(max_length=120, verbose_name='Slug')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Order')),
                ('is_audience_choice', models.BooleanField(default=False, help_text="Tick the one award decided by the attendees' star votes. The operations dashboard hands it out with one click, and only one abstract per event can hold it.", verbose_name='Audience choice')),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='abstract_awards', to='lma_core.event')),
            ],
            options={
                'verbose_name': 'Abstract award',
                'verbose_name_plural': 'Abstract awards',
                'ordering': ['event', 'order', 'name'],
            },
        ),
        # Keep the old column around under a different name while the data is
        # copied over — renaming rather than dropping is what makes the
        # migration reversible without losing which abstract won what.
        migrations.RenameField(
            model_name='abstract',
            old_name='award',
            new_name='award_legacy',
        ),
        migrations.AddField(
            model_name='abstract',
            name='award',
            field=models.ForeignKey(blank=True, help_text='When set, the abstract is marked as a winner', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='abstracts', to='lma_abstracts.abstractaward', verbose_name='Award'),
        ),
        migrations.RunPython(create_awards_from_choices, restore_award_strings),
        migrations.RemoveField(
            model_name='abstract',
            name='award_legacy',
        ),
        migrations.AddConstraint(
            model_name='abstractaward',
            constraint=models.UniqueConstraint(fields=('event', 'slug'), name='unique_abstract_award_slug_per_event'),
        ),
        migrations.AddConstraint(
            model_name='abstractaward',
            constraint=models.UniqueConstraint(condition=models.Q(('is_audience_choice', True)), fields=('event',), name='unique_audience_choice_award_per_event'),
        ),
        migrations.AddField(
            model_name='abstractauthor',
            name='country',
            field=models.CharField(blank=True, help_text="Country of the affiliation, e.g. 'Austria'", max_length=120, verbose_name='Country'),
        ),
        migrations.AddField(
            model_name='abstractauthor',
            name='country_iso',
            field=models.CharField(blank=True, help_text="Two-letter code, e.g. 'AT' — drives the world map and the flag display", max_length=2, verbose_name='ISO-3166'),
        ),
        migrations.AlterField(
            model_name='abstract',
            name='award_at',
            field=models.DateField(blank=True, null=True, verbose_name='Award date'),
        ),
        migrations.AlterField(
            model_name='abstract',
            name='award_note',
            field=models.CharField(blank=True, help_text="Short text, e.g. 'Highest impact factor in study design'", max_length=300, verbose_name='Award rationale (optional)'),
        ),
        migrations.AlterField(
            model_name='abstractauthor',
            name='email',
            field=models.EmailField(blank=True, max_length=254, verbose_name='Email'),
        ),
        migrations.AlterField(
            model_name='abstractauthor',
            name='full_name',
            field=models.CharField(help_text='Plain text — an account is not required', max_length=200, verbose_name='Full name'),
        ),
    ]
