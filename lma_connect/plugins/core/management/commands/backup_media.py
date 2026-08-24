"""Weekly backup of the media directory (MEDIA_ROOT).

Separate from `backup_db` because uploaded files move to a completely
different rhythm: speaker photos, sponsor logos and floorplans change weekly,
not hourly. Backing them up every hour would only cost disk space without
gaining anything — and unlike the database they can be restored from the
originals if it comes to that.

The result is a `media-YYYYMMDD-HHMM.tar.gz` next to the database backups.
After writing, the archive is read through once end to end, to be sure it can
actually be opened again.

Usage:
    python manage.py backup_media            # create archive and rotate
    python manage.py backup_media --list     # show existing archives
    python manage.py backup_media --verify <file>
"""

from __future__ import annotations

import os
import tarfile
import time
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from .backup_db import TIMESTAMP_FORMAT, backup_dir, human_size

FILENAME_PREFIX = "media-"
FILENAME_SUFFIX = ".tar.gz"

DEFAULT_KEEP = 8  # eight weekly snapshots


def parse_timestamp(path: Path) -> datetime | None:
    name = path.name
    if not (name.startswith(FILENAME_PREFIX) and name.endswith(FILENAME_SUFFIX)):
        return None
    stamp = name[len(FILENAME_PREFIX) : -len(FILENAME_SUFFIX)]
    try:
        return datetime.strptime(stamp, TIMESTAMP_FORMAT)
    except ValueError:
        return None


def existing_archives(directory: Path) -> list[tuple[datetime, Path]]:
    """Alle erkannten Medien-Archive, neueste zuerst."""
    if not directory.is_dir():
        return []
    found = []
    for path in directory.iterdir():
        stamp = parse_timestamp(path)
        if stamp is not None:
            found.append((stamp, path))
    found.sort(key=lambda item: item[0], reverse=True)
    return found


def archive_ok(path: Path) -> tuple[bool, str]:
    """Open the archive and read every member — this also catches an aborted
    transfer, which a mere open test would wave through."""
    try:
        with tarfile.open(path, "r:gz") as tar:
            count = 0
            for member in tar:
                if member.isfile():
                    handle = tar.extractfile(member)
                    if handle is None:
                        return False, f"member not readable: {member.name}"
                    while handle.read(1 << 20):
                        pass
                    count += 1
    except (tarfile.TarError, OSError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return True, f"{count} files"


class Command(BaseCommand):
    help = "Compressed backup of MEDIA_ROOT with rotation (meant to run weekly)."

    def add_arguments(self, parser):
        parser.add_argument("--list", action="store_true", dest="list_only",
                            help="List existing media archives.")
        parser.add_argument("--verify", dest="verify_path",
                            help="Check an existing archive.")
        parser.add_argument("--keep", type=int, default=DEFAULT_KEEP,
                            help=f"Number of archives to keep (default: {DEFAULT_KEEP}).")
        parser.add_argument("--dry-run", action="store_true",
                            help="Show what rotation would delete; delete nothing.")

    def say(self, message: str) -> None:
        if self.verbosity > 0:
            self.stdout.write(message)

    def handle(self, *args, **opts):
        self.verbosity = opts.get("verbosity", 1)
        directory = backup_dir()

        if opts["verify_path"]:
            path = Path(opts["verify_path"]).expanduser()
            if not path.is_file():
                raise CommandError(f"File not found: {path}")
            ok, detail = archive_ok(path)
            if not ok:
                raise CommandError(f"{path.name}: CORRUPT — {detail}")
            self.stdout.write(self.style.SUCCESS(f"{path.name}: readable ({detail})"))
            return

        if opts["list_only"]:
            self.list_archives(directory)
            return

        self.create_archive(directory, opts)

    def create_archive(self, directory: Path, opts) -> None:
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.is_dir():
            raise CommandError(f"MEDIA_ROOT does not exist: {media_root}")

        files = [p for p in media_root.rglob("*") if p.is_file()]
        if not files:
            # Not an error: a fresh installation simply has no uploads yet,
            # and writing an empty archive would only be confusing.
            self.say(f"MEDIA_ROOT ({media_root}) is empty — no archive written.")
            return

        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(0o700)

        stamp = timezone.localtime().strftime(TIMESTAMP_FORMAT)
        final_path = directory / f"{FILENAME_PREFIX}{stamp}{FILENAME_SUFFIX}"
        tmp_path = directory / f".{FILENAME_PREFIX}{stamp}.tmp"

        started = time.monotonic()
        try:
            with tarfile.open(tmp_path, "w:gz", compresslevel=6) as tar:
                # arcname="media" → unpacking produces a clean media/ folder
                # instead of absolute paths.
                tar.add(media_root, arcname="media")

            ok, detail = archive_ok(tmp_path)
            if not ok:
                raise CommandError(
                    f"Archive is not readable: {detail}. The backup was NOT written."
                )

            os.replace(tmp_path, final_path)
            final_path.chmod(0o600)
        finally:
            tmp_path.unlink(missing_ok=True)

        elapsed = time.monotonic() - started
        raw = sum(p.stat().st_size for p in files)
        self.say(
            f"{timezone.localtime().isoformat(timespec='seconds')} OK "
            f"{final_path.name} ({human_size(final_path.stat().st_size)} gz, "
            f"{len(files)} files / {human_size(raw)} raw, {elapsed:.1f}s)"
        )

        self.rotate(directory, opts["keep"], opts["dry_run"])

    def rotate(self, directory: Path, keep: int, dry_run: bool) -> None:
        archives = existing_archives(directory)
        expired = [path for _stamp, path in archives[keep:]]
        if not expired:
            self.say(f"  Rotation: nothing to delete ({len(archives)} archives).")
            return

        freed = 0
        for path in expired:
            freed += path.stat().st_size
            if dry_run:
                self.say(f"  [dry-run] would delete: {path.name}")
            else:
                path.unlink()

        verb = "would free" if dry_run else "deleted"
        self.say(
            f"  Rotation: {len(expired)} of {len(archives)} archives {verb} "
            f"({human_size(freed)}), {len(archives) - len(expired)} remain."
        )

    def list_archives(self, directory: Path) -> None:
        archives = existing_archives(directory)
        if not archives:
            self.stdout.write(self.style.WARNING(f"No media archives in {directory}"))
            return
        total = 0
        self.stdout.write(f"Medien-Archive in {directory}:")
        for stamp, path in archives:
            size = path.stat().st_size
            total += size
            self.stdout.write(f"  {stamp:%Y-%m-%d %H:%M}  {human_size(size):>9}  {path.name}")
        self.stdout.write(f"\n{len(archives)} Archive, {human_size(total)} gesamt.")
