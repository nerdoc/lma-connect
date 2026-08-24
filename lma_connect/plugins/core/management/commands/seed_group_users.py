"""Create one test user per group — a login per role, shared password.

For every existing Django group (auth.Group) a user is created and put into
exactly that group. Handy for clicking through what a role can and cannot do.

The username is derived from the group name (slugified with underscores),
e.g. "Operations Team" → "operations_team".

    NEVER RUN THIS AGAINST PRODUCTION.

The default password is deliberately trivial ("1234"). These accounts are for
local test and demo environments only; on a public deployment they are an open
door into every role the app has.

Examples:
    python manage.py seed_group_users
    python manage.py seed_group_users --password something-else
    python manage.py seed_group_users --prefix test_
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify


class Command(BaseCommand):
    help = "Create one test user per auth.Group with a shared password (idempotent)"

    def add_arguments(self, parser):
        parser.add_argument("--password", default="1234",
                            help="Shared password for all users (default: 1234)")
        parser.add_argument("--prefix", default="",
                            help="Optional username prefix, e.g. 'test_'")

    def handle(self, *args, password, prefix, **opts):
        # A docstring warning is not a safeguard. These accounts share a
        # trivial password and cover every role the app has, so refuse to run
        # anywhere DEBUG is off — that is the closest thing to "this is not a
        # developer's machine" Django offers.
        if not settings.DEBUG:
            raise CommandError(
                "Refusing to run with DEBUG=False: this command creates one "
                "account per role sharing a trivial password, which would be "
                "an open door on a live deployment. Run it locally instead."
            )
        User = get_user_model()
        groups = Group.objects.all().order_by("name")

        if not groups.exists():
            self.stdout.write(self.style.WARNING(
                "No groups exist — nothing to do."))
            return

        for group in groups:
            base = slugify(group.name).replace("-", "_")
            username = f"{prefix}{base}"

            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.test",
                    "first_name": group.name,
                    "is_active": True,
                },
            )
            user.set_password(password)
            user.save()
            user.groups.set([group])

            verb = "created" if created else "updated"
            self.stdout.write(self.style.SUCCESS(
                f"✓ {username:24} → group '{group.name}' ({verb})"))

        self.stdout.write(self.style.SUCCESS(
            f"\nDone — {groups.count()} users, password: {password!r}"))
