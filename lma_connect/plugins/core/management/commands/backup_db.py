"""Consistent online backup of the SQLite database.

Uses SQLite's online backup API (`sqlite3.Connection.backup()`) rather than a
file copy: the source may keep being read AND written while it runs, and the
copy is guaranteed to be a consistent snapshot including every transaction
still in the WAL. `cp db.sqlite3 backup.sqlite3` gives you neither — with
`journal_mode=WAL` (see settings.py) the WAL holds committed transactions the
main file does not know about yet.

Steps per run:
  1. Snapshot into a temporary file in the target directory
  2. `PRAGMA integrity_check` on the *copy* — a broken backup is worse than
     none, because it pretends to be safety
  3. gzip compression
  4. Atomic rename onto the final name
  5. Rotation according to the retention policy

The exit code is non-zero on any error, so cron sends mail.

Usage:
    python manage.py backup_db                  # snapshot and rotate
    python manage.py backup_db --list           # show existing backups
    python manage.py backup_db --verify <file>  # check a backup's integrity
"""

from __future__ import annotations

import gzip
import os
import shutil
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

# Filename scheme: db-20260807-1400.sqlite3.gz — sorts correctly
# lexicographically and is readable without any tooling.
FILENAME_PREFIX = "db-"
FILENAME_SUFFIX = ".sqlite3.gz"
TIMESTAMP_FORMAT = "%Y%m%d-%H%M"

DEFAULT_KEEP_HOURLY = 48
DEFAULT_KEEP_DAILY = 30


def backup_dir() -> Path:
    """Target directory — override with DJANGO_BACKUP_DIR."""
    raw = os.environ.get("DJANGO_BACKUP_DIR")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / "backups" / "lma-connect"


def parse_timestamp(path: Path) -> datetime | None:
    """Timestamp from the filename; None when the name does not match."""
    name = path.name
    if not (name.startswith(FILENAME_PREFIX) and name.endswith(FILENAME_SUFFIX)):
        return None
    stamp = name[len(FILENAME_PREFIX) : -len(FILENAME_SUFFIX)]
    try:
        return datetime.strptime(stamp, TIMESTAMP_FORMAT)
    except ValueError:
        return None


def existing_backups(directory: Path) -> list[tuple[datetime, Path]]:
    """Every recognised backup, newest first."""
    if not directory.is_dir():
        return []
    found = []
    for path in directory.iterdir():
        stamp = parse_timestamp(path)
        if stamp is not None:
            found.append((stamp, path))
    found.sort(key=lambda item: item[0], reverse=True)
    return found


def select_expired(
    backups: list[tuple[datetime, Path]],
    now: datetime,
    keep_hourly: int,
    keep_daily: int,
) -> list[Path]:
    """Decide which backups may be deleted.

    Kept are:
      * everything from the last `keep_hourly` hours (the fine-grained history
        that is actually needed when something goes wrong), and
      * the *newest* backup of each calendar day, going back `keep_daily` days.

    Everything else goes. An empty backup directory can never result from
    this, as long as at least one run falls within the window.
    """
    hourly_cutoff = now - timedelta(hours=keep_hourly)
    daily_cutoff = (now - timedelta(days=keep_daily)).date()

    keep: set[Path] = set()
    daily_seen: set = set()

    # `backups` is sorted descending → the first backup of a day is its newest.
    for stamp, path in backups:
        if stamp >= hourly_cutoff:
            keep.add(path)
            continue
        day = stamp.date()
        if day >= daily_cutoff and day not in daily_seen:
            daily_seen.add(day)
            keep.add(path)

    return [path for _stamp, path in backups if path not in keep]


def integrity_ok(path: Path) -> tuple[bool, str]:
    """`PRAGMA integrity_check` against an uncompressed SQLite file."""
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute("PRAGMA integrity_check").fetchall()
    finally:
        conn.close()
    result = "; ".join(row[0] for row in rows)
    return result == "ok", result


def human_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


class Command(BaseCommand):
    help = "Consistent, compressed online backup of the SQLite DB, with rotation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--list",
            action="store_true",
            dest="list_only",
            help="List existing backups; create nothing.",
        )
        parser.add_argument(
            "--verify",
            dest="verify_path",
            help="Check the integrity of an existing backup (.gz or .sqlite3).",
        )
        parser.add_argument(
            "--keep-hourly",
            type=int,
            default=DEFAULT_KEEP_HOURLY,
            help=f"Hours for which every backup is kept (default: {DEFAULT_KEEP_HOURLY}).",
        )
        parser.add_argument(
            "--keep-daily",
            type=int,
            default=DEFAULT_KEEP_DAILY,
            help=f"Days for which one daily backup is kept (default: {DEFAULT_KEEP_DAILY}).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what rotation would delete; delete nothing.",
        )

    def say(self, message: str) -> None:
        """Output that respects `--verbosity 0`.

        Under cron (default verbosity 1) every line lands in the log file; in
        tests it stays quiet. Errors go through CommandError to stderr anyway
        and are unaffected by this.
        """
        if self.verbosity > 0:
            self.stdout.write(message)

    def handle(self, *args, **opts):
        self.verbosity = opts.get("verbosity", 1)
        directory = backup_dir()

        if opts["verify_path"]:
            self.verify(Path(opts["verify_path"]).expanduser())
            return

        if opts["list_only"]:
            self.list_backups(directory)
            return

        self.create_backup(directory, opts)

    # ── Actions ───────────────────────────────────────────────────────────

    def create_backup(self, directory: Path, opts) -> None:
        db_settings = settings.DATABASES["default"]
        if "sqlite3" not in db_settings["ENGINE"]:
            raise CommandError(
                f"backup_db only supports SQLite (currently: {db_settings['ENGINE']}). "
                "Use mysqldump for MariaDB/MySQL instead."
            )

        source = Path(db_settings["NAME"])
        if not source.is_file():
            raise CommandError(f"Database not found: {source}")

        directory.mkdir(parents=True, exist_ok=True)
        # A backup is a complete copy of the database — nicknames,
        # affiliations, Q&A posts, feedback: personal data throughout. So the
        # permissions are set explicitly to owner-only on every run, instead
        # of relying on the umask (which differs between cron environments).
        directory.chmod(0o700)

        stamp = timezone.localtime().strftime(TIMESTAMP_FORMAT)
        final_path = directory / f"{FILENAME_PREFIX}{stamp}{FILENAME_SUFFIX}"
        # Two temporary files, both in the target directory (same filesystem
        # → the final rename is atomic).
        snapshot_path = directory / f".{FILENAME_PREFIX}{stamp}.snapshot.tmp"
        gz_tmp_path = directory / f".{FILENAME_PREFIX}{stamp}.gz.tmp"

        started = time.monotonic()
        try:
            self.snapshot(source, snapshot_path)

            ok, detail = integrity_ok(snapshot_path)
            if not ok:
                raise CommandError(
                    f"integrity_check of the snapshot failed: {detail}. "
                    "The backup was NOT written."
                )

            raw_size = snapshot_path.stat().st_size
            with open(snapshot_path, "rb") as src, gzip.open(gz_tmp_path, "wb", compresslevel=6) as dst:
                shutil.copyfileobj(src, dst)

            os.replace(gz_tmp_path, final_path)
            final_path.chmod(0o600)
        finally:
            for tmp in (snapshot_path, gz_tmp_path):
                tmp.unlink(missing_ok=True)

        elapsed = time.monotonic() - started
        gz_size = final_path.stat().st_size
        self.say(
            f"{timezone.localtime().isoformat(timespec='seconds')} OK "
            f"{final_path.name} ({human_size(gz_size)} gz, "
            f"{human_size(raw_size)} raw, {elapsed:.1f}s)"
        )

        self.rotate(directory, opts["keep_hourly"], opts["keep_daily"], opts["dry_run"])

    def snapshot(self, source: Path, target: Path) -> None:
        """Online backup of the running database into `target`."""
        target.unlink(missing_ok=True)
        # timeout: wait if a writer currently holds the database, instead of
        # aborting immediately with "database is locked".
        src_conn = sqlite3.connect(source, timeout=30)
        dst_conn = sqlite3.connect(target)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

    def rotate(self, directory: Path, keep_hourly: int, keep_daily: int, dry_run: bool) -> None:
        backups = existing_backups(directory)
        expired = select_expired(backups, timezone.localtime().replace(tzinfo=None),
                                 keep_hourly, keep_daily)
        if not expired:
            self.say(f"  Rotation: nothing to delete ({len(backups)} backups).")
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
            f"  Rotation: {len(expired)} of {len(backups)} backups {verb} "
            f"({human_size(freed)}), {len(backups) - len(expired)} remain."
        )

    def list_backups(self, directory: Path) -> None:
        backups = existing_backups(directory)
        if not backups:
            self.stdout.write(self.style.WARNING(f"No backups in {directory}"))
            return

        total = 0
        self.stdout.write(f"Backups in {directory}:")
        for stamp, path in backups:
            size = path.stat().st_size
            total += size
            self.stdout.write(f"  {stamp:%Y-%m-%d %H:%M}  {human_size(size):>9}  {path.name}")
        self.stdout.write(f"\n{len(backups)} backups, {human_size(total)} in total.")
        newest = backups[0][0]
        age = datetime.now() - newest
        style = self.style.SUCCESS if age < timedelta(hours=2) else self.style.WARNING
        self.stdout.write(style(f"Newest backup is {age.total_seconds() / 3600:.1f} h old."))

    def verify(self, path: Path) -> None:
        if not path.is_file():
            raise CommandError(f"File not found: {path}")

        if path.suffix == ".gz":
            tmp = path.with_suffix(".verify.tmp")
            try:
                with gzip.open(path, "rb") as src, open(tmp, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                ok, detail = integrity_ok(tmp)
            finally:
                tmp.unlink(missing_ok=True)
        else:
            ok, detail = integrity_ok(path)

        if not ok:
            raise CommandError(f"{path.name}: CORRUPT — {detail}")
        self.stdout.write(self.style.SUCCESS(f"{path.name}: integrity_check ok"))
