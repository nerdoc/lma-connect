"""Load finished legal texts from Markdown files into the LegalPage rows of an
event.

`seed_legal` writes the generic TEMPLATE with «placeholders». This command is
its counterpart for the finished texts of one concrete deployment: a
directory of `<slug>.<lang>.md` files — `<slug>.en.md` is the source language,
`<slug>.de.md` the German version — whose first line is the page title
(`# Imprint`) and whose remainder is the Markdown body.

Keeping the finished texts as files in the repository (rather than only in
the admin of one database) means they are versioned, diffable, and can be
handed to a lawyer for review as plain files; a fresh deployment gets them
with one command instead of a copy-and-paste session.

Pages that already exist are left alone unless --overwrite is given — same
rule as seed_legal. Both languages are always written together.

Usage:
    python manage.py load_legal_pages --dir lma_connect/plugins/core/legal/<event-dir> \
        [--event <event-slug>] [--overwrite]
"""

from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_slug

from lma_connect.plugins.core.models import Event, LegalPage

# Footer order of the canonical pages; anything else comes after, alphabetically.
ORDER = {"imprint": 10, "privacy": 20, "terms": 30, "accessibility": 40}


def parse_page_file(path: Path) -> tuple[str, str]:
    """Split a page file into (title, body). The title is the first line,
    which must be a Markdown H1; the body is everything after it."""
    text = path.read_text(encoding="utf-8")
    first, _, rest = text.partition("\n")
    if not first.startswith("# "):
        raise CommandError(f"{path}: first line must be the title as '# …', got {first!r}")
    return first[2:].strip(), rest.strip() + "\n"


class Command(BaseCommand):
    help = "Load finished legal pages (<slug>.en.md / <slug>.de.md) into an Event."

    def add_arguments(self, parser):
        parser.add_argument("--dir", required=True, help="Directory with <slug>.<lang>.md files.")
        parser.add_argument("--event", dest="event_slug",
                            help="Event slug. Default: latest published event.")
        parser.add_argument("--overwrite", action="store_true",
                            help="Replace pages that already exist (both languages).")

    def handle(self, *args, **opts):
        directory = Path(opts["dir"])
        if not directory.is_dir():
            raise CommandError(f"Not a directory: {directory}")

        event_slug = opts.get("event_slug")
        if event_slug:
            try:
                event = Event.objects.get(slug=event_slug)
            except Event.DoesNotExist as exc:
                raise CommandError(f"Event '{event_slug}' not found.") from exc
        else:
            event = Event.objects.filter(is_published=True).order_by("-start_date").first()
            if not event:
                raise CommandError("No published event — pass --event=<slug>.")

        en_files = sorted(directory.glob("*.en.md"))
        if not en_files:
            raise CommandError(f"No *.en.md files in {directory}")

        self.stdout.write(self.style.SUCCESS(f"Event: {event.slug}  ({directory})"))
        placeholders = 0
        for en_path in en_files:
            slug = en_path.name[: -len(".en.md")]
            try:
                validate_slug(slug)
            except ValidationError as exc:
                # A bad slug would not fail here but in every footer's {% url %}.
                raise CommandError(f"{en_path.name}: '{slug}' is not a valid slug") from exc
            title, body = parse_page_file(en_path)
            de_path = directory / f"{slug}.de.md"
            if de_path.exists():
                title_de, body_de = parse_page_file(de_path)
            else:
                # Without a German version the German UI falls back to English —
                # for legal texts that is worth a warning, not a silent default.
                title_de, body_de = "", ""
                self.stdout.write(self.style.WARNING(f"  {slug}: no {de_path.name} — German falls back to English"))

            placeholders += body.count("«") + body_de.count("«")
            order = ORDER.get(slug, 100)
            page = event.legal_pages.filter(slug=slug).first()
            if page is None:
                LegalPage.objects.create(
                    event=event, slug=slug, title=title, title_de=title_de,
                    body=body, body_de=body_de, order=order, is_published=True,
                )
                action = "created"
            elif opts["overwrite"]:
                page.title, page.title_de = title, title_de
                page.body, page.body_de = body, body_de
                page.save(update_fields=["title", "title_de", "body", "body_de"])
                action = "overwritten (EN + DE)"
            else:
                action = "kept (use --overwrite to replace)"
            self.stdout.write(f"  /legal/{slug}/  {len(body):>6} / {len(body_de):>6} chars — {action}")

        if placeholders:
            self.stdout.write(self.style.ERROR(
                f"{placeholders} «placeholders» left in the files — these texts are not finished."))
