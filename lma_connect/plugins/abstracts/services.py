"""Audience voting — the star budget behind the audience award.

Every attendee has STARS_PER_USER stars per event and gives at most one of
them to any single abstract. A cast vote is final; there is deliberately no
function here to take one back.

Counting always happens *per event*, so a recurring conference tops the budget
back up.
"""

from django.db import IntegrityError, transaction

from .models import STARS_PER_USER, AbstractStarVote


def stars_used(user, event) -> int:
    """How many stars has `user` already given at `event`?"""
    if user is None or not getattr(user, "is_authenticated", False) or event is None:
        return 0
    return AbstractStarVote.objects.filter(user=user, abstract__event=event).count()


def stars_left(user, event) -> int:
    """The remaining budget — never negative.

    Zero without a login: someone not signed in has no budget to spend, and
    the detail page would otherwise promise guests "3 stars left".
    """
    if user is None or not getattr(user, "is_authenticated", False) or event is None:
        return 0
    return max(0, STARS_PER_USER - stars_used(user, event))


def has_voted(user, abstract) -> bool:
    """Has `user` already given this abstract their star?"""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return AbstractStarVote.objects.filter(user=user, abstract=abstract).exists()


def cast_star(user, abstract) -> AbstractStarVote | None:
    """Give a star. Returns the new vote — or None when the budget is spent
    or this abstract already carries a star from this user.

    The realistic double case is a double tap on the same button, which
    `unique_together` catches at the database level — hence the IntegrityError
    branch instead of a check up front. The atomic() keeps the insert and the
    budget count together, so a failed insert leaves no half transaction
    behind.
    """
    if user is None or not getattr(user, "is_authenticated", False) or abstract is None:
        return None
    try:
        with transaction.atomic():
            used = AbstractStarVote.objects.filter(
                user=user, abstract__event=abstract.event).count()
            if used >= STARS_PER_USER:
                return None
            return AbstractStarVote.objects.create(user=user, abstract=abstract)
    except IntegrityError:
        # unique_together — this abstract already has a star from this user.
        return None


def star_ranking(event, published_only: bool = True):
    """Abstracts by audience stars, the best first.

    Returns Abstract objects carrying an `n_stars` attribute. Abstracts
    without votes are included (n_stars=0), so ops sees the complete list.
    """
    from django.db.models import Count

    from .models import Abstract

    if event is None:
        return []
    qs = Abstract.objects.filter(event=event)
    if published_only:
        qs = qs.filter(is_published=True)
    return list(
        qs.select_related("category")
        .annotate(n_stars=Count("star_votes"))
        .order_by("-n_stars", "poster_id", "title")
    )
