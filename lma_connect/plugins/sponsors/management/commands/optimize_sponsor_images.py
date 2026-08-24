"""Convert every sponsor image that is not WebP yet — logos, banners,
gallery images, contact photos — using the same rules as `import_sponsor`
(see sponsors.images). Catches what was uploaded through the admin.

Each file is replaced individually: the new WebP is written, the row
repointed, and the old file removed once that row's transaction commits.
A file Pillow cannot read is reported and left alone.

Usage: `python manage.py optimize_sponsor_images [--dry-run]`
"""

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from lma_connect.plugins.sponsors.images import to_webp, webp_name
from lma_connect.plugins.sponsors.models import Sponsor, SponsorContact, SponsorImage

# (queryset, field name, MAX_WIDTH kind)
TARGETS = [
    (Sponsor.objects.all(), "logo", "logo"),
    (Sponsor.objects.all(), "banner", "banner"),
    (SponsorImage.objects.all(), "image", "image"),
    (SponsorContact.objects.all(), "photo", "photo"),
]


class Command(BaseCommand):
    help = "Re-encode all sponsor logos/banners/images/photos as WebP."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would change, write nothing")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        before = after = converted = skipped = 0
        for queryset, field, kind in TARGETS:
            for obj in queryset.exclude(**{field: ""}):
                ff = getattr(obj, field)
                if not ff or ff.name.lower().endswith(".webp"):
                    continue
                try:
                    old_size = ff.size
                    with ff.open("rb") as fh:
                        data = to_webp(fh, kind)
                except (OSError, ValueError) as exc:
                    skipped += 1
                    self.stderr.write(f"  skip {ff.name}: {exc}")
                    continue
                before += old_size
                after += len(data)
                converted += 1
                self.stdout.write(f"  {obj} {field}: {ff.name} "
                                  f"{old_size // 1024} kB -> {len(data) // 1024} kB")
                if dry:
                    continue
                with transaction.atomic():
                    storage, old_name = ff.storage, ff.name
                    ff.save(webp_name(old_name), ContentFile(data), save=True)
                    transaction.on_commit(lambda s=storage, n=old_name: s.delete(n))

        verb = "Would convert" if dry else "Converted"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} {converted} file(s): {before // 1024} kB -> {after // 1024} kB"
            + (f", {skipped} skipped" if skipped else "")))
