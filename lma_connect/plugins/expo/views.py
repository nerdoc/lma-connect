"""Expo check-in views — where every printed QR card points.

Booth:  /expo/s/<slug>/   → check-in plus a multiple-choice quiz
Poster: /expo/p/<slug>/   → check-in plus one audience star

Both require a login: anyone not signed in is sent to the login page via
?next= and lands back here afterwards.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from lma_connect.plugins.abstracts.models import STARS_PER_USER, Abstract
from lma_connect.plugins.abstracts.services import cast_star, has_voted, stars_left
from lma_connect.plugins.core.models import Event
from lma_connect.plugins.gamification.models import ScoreAction
from lma_connect.plugins.gamification.services import award, has_action
from lma_connect.plugins.sponsors.models import Sponsor

# Keep the quiz from being solvable by clicking through every option: after a
# couple of wrong answers, a short cooldown per (user, booth). Best effort —
# the counter lives in LocMemCache and is per worker process.
_QUIZ_MAX_FAILS = 2       # wrong answers before the cooldown kicks in
_QUIZ_COOLDOWN = 300      # cooldown in seconds


@login_required
def booth_stop(request, slug):
    """Booth check-in plus the optional quiz."""
    event = Event.get_active(request)
    # The slug is only unique per (event, slug), so always filter by the
    # active event — a recurring conference would otherwise raise
    # MultipleObjectsReturned. With no active event (event=None) nothing
    # matches, which gives a clean 404 instead of a false success message.
    sponsor = get_object_or_404(
        Sponsor.objects.select_related("event"),
        event=event, slug=slug, is_published=True)

    # Check-in points, once per booth.
    checkin_key = f"booth:{sponsor.pk}"
    if award(request.user, event, ScoreAction.BOOTH_CHECKIN, dedup_key=checkin_key):
        messages.success(request, _("Checked in at %(name)s — points added!")
                         % {"name": sponsor.name})

    quiz = getattr(sponsor, "quiz", None)
    if quiz and not quiz.is_active:
        quiz = None

    quiz_key = f"booth-quiz:{sponsor.pk}"
    already_solved = has_action(request.user, event, quiz_key)
    result = None  # "correct" | "wrong" | None
    fail_key = f"booth-quiz-fails:{request.user.pk}:{sponsor.pk}"

    if quiz and request.method == "POST" and not already_solved:
        if (cache.get(fail_key) or 0) >= _QUIZ_MAX_FAILS:
            messages.warning(request, _("Too many wrong answers — please wait a moment "
                                        "and try again."))
        else:
            try:
                choice_id = int(request.POST.get("choice", ""))
            except (TypeError, ValueError):
                choice_id = None
            chosen = quiz.choices.filter(pk=choice_id).first() if choice_id else None
            if chosen and chosen.is_correct:
                award(request.user, event, ScoreAction.BOOTH_QUIZ, dedup_key=quiz_key)
                already_solved = True
                result = "correct"
                messages.success(request, _("Correct! Bonus points unlocked."))
            else:
                cache.set(fail_key, (cache.get(fail_key) or 0) + 1, _QUIZ_COOLDOWN)
                result = "wrong"
                messages.warning(request, _("Not quite — give it another go."))

    return render(request, "expo/booth_stop.html", {
        "event": event, "sponsor": sponsor, "quiz": quiz,
        "already_solved": already_solved, "result": result,
        "active_tab": "sponsors",
    })


@login_required
def poster_stop(request, slug):
    """Poster check-in plus the audience star (final, behind a confirmation).

    The star can deliberately only be given here — to vote you have to scan
    the QR code on the poster, which means actually standing in front of it.
    """
    event = Event.get_active(request)
    # The slug is only unique per (event, slug), so filter by the active
    # event: that keeps the check-in points and the vote (which books against
    # abstract.event) in the same event. `has_poster` rather than `type`,
    # because a talk can have a poster on display as well.
    abstract = get_object_or_404(
        Abstract.objects.select_related("event", "category"),
        event=event, slug=slug, is_published=True, has_poster=True)

    # Check-in points, once per poster.
    if award(request.user, event, ScoreAction.POSTER_CHECKIN,
             dedup_key=f"poster:{abstract.pk}"):
        messages.success(request, _("Checked in at the poster — points added!"))

    voted = has_voted(request.user, abstract)
    left = stars_left(request.user, event)

    if request.method == "POST" and not voted:
        if cast_star(request.user, abstract):
            messages.success(request, _("Star given — thanks for your vote!"))
        elif stars_left(request.user, event) == 0:
            messages.warning(request, _("You have already given all %(n)d of your stars.")
                             % {"n": STARS_PER_USER})
        return redirect("expo:poster_stop", slug=abstract.slug)

    return render(request, "expo/poster_stop.html", {
        "event": event, "abstract": abstract,
        "voted": voted,
        "stars_left": left,
        "stars_total": STARS_PER_USER,
        # Budget display: True = already given, False = still available.
        "star_slots": [True] * (STARS_PER_USER - left) + [False] * left,
        # Two-step without JavaScript: the first click reloads the same page
        # with ?confirm=1 and shows the question; only its POST saves.
        "confirming": request.GET.get("confirm") == "1" and not voted and left > 0,
        "active_tab": "abstracts",
    })
