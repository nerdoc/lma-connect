"""Import or update a sponsor's public profile from a directory holding a
`profile.json` plus the images it references.

Sponsors send their exhibitor profile as a Word document; the organizers
transcribe it into `profile.json` once (a template is printed by
`--example`) and run this command on every machine that has a database —
locally for a look, then on the server. The JSON and the images stay
outside the repository: they are sponsor marketing material, not code.

The sponsor is matched by `slug` within the active event (or `--event`)
and created when missing. Scalar fields are only written when present in
the JSON, so tier, logo, booth location and floorplan marker that were set
in the admin survive a re-import. The related collections — images,
contacts, links, downloads, quiz — are replaced wholesale, because that is the only
way a re-import of a corrected profile can also remove an entry.

Copy arrives in whatever language the sponsor writes in. Put that text in
the primary fields (`bio_long`, `role`, …); it is shown to every visitor.
Fill the `_en` twins only when a separate English version exists.

Usage: `python manage.py import_sponsor /path/to/roche [--event slug] [--dry-run]`
"""

import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from lma_connect.plugins.core.models import Event
from lma_connect.plugins.expo.models import BoothChoice, BoothQuiz
from lma_connect.plugins.sponsors.images import to_webp, webp_name
from lma_connect.plugins.sponsors.models import (
    Sponsor,
    SponsorContact,
    SponsorDownload,
    SponsorImage,
    SponsorLink,
)

SPONSOR_FIELDS = [
    "name", "bio_short", "bio_short_en", "bio_long", "bio_long_en",
    "website", "contact_email", "contact_person",
    "booth_location", "booth_location_en",
    "highlights_md", "highlights_md_en", "is_published", "is_featured",
]
IMAGE_FIELDS = ["logo", "banner"]
CONTACT_FIELDS = ["name", "role", "role_en", "expertise", "expertise_en",
                  "email", "phone", "linkedin_url"]
LINK_FIELDS = ["label", "label_en", "url", "type", "description", "description_en"]
DOWNLOAD_FIELDS = ["title", "title_en", "description", "description_en", "type"]

EXAMPLE = {
    "slug": "acme",
    "name": "ACME Diagnostics GmbH",
    "website": "https://example.com",
    "contact_email": "booth@example.com",
    "bio_short": "One-line pitch (max. 300 characters).",
    "bio_long": "Full description, Markdown allowed.",
    "highlights_md": "- **Product A**: what it does\n- **Product B**: what it does",
    "logo": "logo.png",
    "banner": "banner.jpg",
    "images": [{"file": "pic1.jpg", "caption": "Caption"}],
    "contacts": [{"name": "Jane Doe", "role": "Product Manager", "expertise": "Haematology",
                  "email": "jane@example.com", "photo": "jane.jpg"}],
    "downloads": [{"file": "brochure.pdf", "title": "Product brochure",
                   "description": "Short description", "type": "brochure"}],
    "links": [{"label": "Product page", "url": "https://example.com/p",
               "type": "product", "description": "Short description"}],
    "quiz": {"question": "Question asked at the booth?", "hint": "Ask our team!",
             "choices": [{"text": "Right answer", "is_correct": True},
                         {"text": "Wrong answer"}]},
}


class Command(BaseCommand):
    help = "Import/update a sponsor profile from <dir>/profile.json plus images."

    def add_arguments(self, parser):
        parser.add_argument("directory", nargs="?", help="Folder with profile.json and images")
        parser.add_argument("--event", help="Event slug (default: active event)")
        parser.add_argument("--dry-run", action="store_true",
                            help="Validate and report, write nothing")
        parser.add_argument("--example", action="store_true",
                            help="Print an example profile.json and exit")

    def handle(self, *args, **opts):
        if opts["example"]:
            self.stdout.write(json.dumps(EXAMPLE, indent=2, ensure_ascii=False))
            return
        if not opts["directory"]:
            raise CommandError("Give the profile directory (or --example).")

        directory = Path(opts["directory"]).expanduser()
        profile_path = directory / "profile.json"
        if not profile_path.is_file():
            raise CommandError(f"{profile_path} not found")
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"{profile_path}: invalid JSON — {exc}") from exc
        slug = profile.get("slug")
        if not slug:
            raise CommandError("profile.json needs a 'slug'")

        event = self._event(opts["event"])
        self._check_files(directory, profile)

        # File writes are not covered by the transaction, so a dry run must
        # skip them instead of leaving orphaned uploads in MEDIA_ROOT.
        self.write_files = not opts["dry_run"]
        with transaction.atomic():
            sponsor = self._import(directory, profile, event)
            # Count inside the transaction — after a dry-run rollback there
            # would be nothing left to count.
            summary = (
                f"{sponsor.images.count()} images, {sponsor.contacts.count()} contacts, "
                f"{sponsor.links.count()} links, {sponsor.downloads.count()} downloads, quiz: "
                f"{'yes' if BoothQuiz.objects.filter(sponsor=sponsor).exists() else 'no'}")
            if opts["dry_run"]:
                transaction.set_rollback(True)

        verb = "Would update" if opts["dry_run"] else "Updated"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} sponsor '{sponsor.name}' ({sponsor.slug}) of {event.slug}: {summary}"))

    # ------------------------------------------------------------------

    def _event(self, slug):
        if slug:
            try:
                return Event.objects.get(slug=slug)
            except Event.DoesNotExist as exc:
                raise CommandError(f"No event with slug '{slug}'") from exc
        event = Event.get_active()
        if event is None:
            raise CommandError("No published event — pass --event <slug>")
        return event

    def _check_files(self, directory, profile):
        names = [profile.get(f) for f in IMAGE_FIELDS if profile.get(f)]
        names += [img.get("file") for img in profile.get("images", [])]
        names += [dl.get("file") for dl in profile.get("downloads", [])]
        names += [c["photo"] for c in profile.get("contacts", []) if c.get("photo")]
        missing = [n for n in names if not n or not (directory / n).is_file()]
        if missing:
            raise CommandError("Referenced files not found: " + ", ".join(map(str, missing)))
        # Image names are plain file names inside the profile folder — no
        # reaching out of it with "../", even though only the operator runs this.
        root = directory.resolve()
        outside = [n for n in names if not (directory / n).resolve().is_relative_to(root)]
        if outside:
            raise CommandError("Files must live inside the profile folder: " + ", ".join(outside))

    def _import(self, directory, profile, event):
        sponsor, created = Sponsor.objects.get_or_create(
            event=event, slug=profile["slug"],
            defaults={"name": profile.get("name", profile["slug"])})
        self.stdout.write(("Created" if created else "Found") + f" sponsor {sponsor}")

        for field in SPONSOR_FIELDS:
            if field in profile:
                setattr(sponsor, field, profile[field])
        for field in IMAGE_FIELDS:
            if profile.get(field):
                self._discard(getattr(sponsor, field))
                self._attach(getattr(sponsor, field), directory / profile[field], field)
        self._save(sponsor)

        if "images" in profile:
            # Deleting the rows leaves the files behind; drop them as well so
            # a re-import does not accumulate suffixed copies in MEDIA_ROOT.
            for old in sponsor.images.all():
                self._discard(old.image)
                old.delete()
            for order, img in enumerate(profile["images"]):
                row = SponsorImage(sponsor=sponsor, order=order,
                                   caption=img.get("caption", ""),
                                   caption_en=img.get("caption_en", ""))
                self._attach(row.image, directory / img["file"], "image")
                self._save(row)

        if "contacts" in profile:
            for old in sponsor.contacts.all():
                self._discard(old.photo)
                old.delete()
            for order, c in enumerate(profile["contacts"]):
                row = SponsorContact(sponsor=sponsor, order=order,
                                     **{f: c.get(f, "") for f in CONTACT_FIELDS})
                if c.get("photo"):
                    self._attach(row.photo, directory / c["photo"], "photo")
                self._save(row)

        if "links" in profile:
            sponsor.links.all().delete()
            for order, link in enumerate(profile["links"]):
                self._save(SponsorLink(
                    sponsor=sponsor, order=order,
                    **{f: link.get(f, "other" if f == "type" else "") for f in LINK_FIELDS}))

        if "downloads" in profile:
            for old in sponsor.downloads.all():
                self._discard(old.file)
                old.delete()
            for order, dl in enumerate(profile["downloads"]):
                row = SponsorDownload(
                    sponsor=sponsor, order=order,
                    **{f: dl.get(f, "other" if f == "type" else "") for f in DOWNLOAD_FIELDS})
                self._attach(row.file, directory / dl["file"])
                self._save(row)

        if "quiz" in profile:
            BoothQuiz.objects.filter(sponsor=sponsor).delete()
            q = profile["quiz"]
            if q:
                quiz = BoothQuiz.objects.create(
                    sponsor=sponsor, question=q["question"], hint=q.get("hint", ""),
                    is_active=q.get("is_active", True))
                choices = q.get("choices", [])
                if sum(1 for c in choices if c.get("is_correct")) != 1:
                    raise CommandError("quiz.choices needs exactly one 'is_correct': true")
                for order, c in enumerate(choices):
                    BoothChoice.objects.create(quiz=quiz, order=order, text=c["text"],
                                               is_correct=bool(c.get("is_correct")))
        return sponsor

    def _save(self, obj):
        """Validate like the admin form would — objects.create() skips the
        URLField/EmailField validators, which is how a 'javascript:' link
        from a mistyped profile would otherwise end up in an href."""
        try:
            obj.full_clean(exclude=["image", "logo", "banner", "photo", "file"]
                           if not self.write_files else None)
        except ValidationError as exc:
            raise CommandError(f"{obj._meta.verbose_name} '{obj}': {exc.message_dict}") from exc
        obj.save()

    def _discard(self, field_file):
        """Remove a replaced upload from storage — but only once the
        transaction commits. Deleting eagerly would leave the old rows
        pointing at missing files if a later step of the import fails."""
        if not self.write_files or not field_file:
            return
        storage, name = field_file.storage, field_file.name
        transaction.on_commit(lambda: storage.delete(name))

    def _attach(self, field_file, path, kind=None):
        """Store `path` in the field. Images (`kind` set) are converted to
        WebP (see sponsors.images); other files — PDFs — are copied as-is."""
        if not self.write_files:
            return
        if kind is None:
            with path.open("rb") as fh:
                field_file.save(path.name, File(fh), save=False)
            return
        try:
            data = to_webp(path, kind)
        except OSError as exc:
            raise CommandError(f"{path.name}: not a readable image — {exc}") from exc
        field_file.save(webp_name(path.name), ContentFile(data), save=False)
        self.stdout.write(f"  {path.name}: {path.stat().st_size // 1024} kB -> "
                          f"{len(data) // 1024} kB webp")
