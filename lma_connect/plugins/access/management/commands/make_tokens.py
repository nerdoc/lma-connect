"""Bulk generator for access tokens.

One token per badge. Print them as QR cards from the organizer-only sheet at
/qr/print/?kind=tokens.

Examples:
    python manage.py make_tokens --event my-event-2026 --count 300
    python manage.py make_tokens --event my-event-2026 --count 5 --label "Speaker"
    python manage.py make_tokens --event my-event-2026 --count 40 --category company
"""

from django.core.management.base import BaseCommand, CommandError

from lma_connect.plugins.access.models import AccessToken
from lma_connect.plugins.core.models import Event
from lma_connect.plugins.people.models import ParticipantCategory


class Command(BaseCommand):
    help = "Generate n access tokens for an event"

    def add_arguments(self, parser):
        parser.add_argument("--event", required=True, help="Event slug")
        parser.add_argument("--count", type=int, required=True, help="How many tokens")
        parser.add_argument("--label", default="", help="Optional shared label")
        parser.add_argument(
            "--category", default=ParticipantCategory.DELEGATE,
            choices=[c for c, _ in ParticipantCategory.choices],
            help="Participant group for this batch of QR codes "
                 "(delegate, speaker, company …)")

    def handle(self, *args, event, count, label, category, **opts):
        try:
            ev = Event.objects.get(slug=event)
        except Event.DoesNotExist:
            raise CommandError(f"No event with slug={event!r}") from None
        if count < 1 or count > 5000:
            raise CommandError("count has to be between 1 and 5000")

        tokens = []
        for _ in range(count):
            t = AccessToken.objects.create(event=ev, label=label, category=category)
            tokens.append(t)

        self.stdout.write(self.style.SUCCESS(
            f"✓ created {len(tokens)} token(s) for {ev.slug} (group: {category})"))
        for t in tokens:
            self.stdout.write(f"  {t.token}  →  {t.get_redeem_url()}")
