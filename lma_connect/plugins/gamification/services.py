"""Point awarding + achievement checking."""

from django.db.models import Count, Sum

from .models import ACTION_POINTS, Achievement, ScoreAction, ScoreEntry, UserAchievement


def award(user, event, action: str, dedup_key: str = "") -> ScoreEntry | None:
    """Log a ScoreEntry for `action`. If dedup_key is given and an entry with
    that key already exists for this user+event, do nothing (returns None).
    After logging, re-check achievements.
    """
    if user is None or not getattr(user, "is_authenticated", False) or event is None:
        return None
    if dedup_key and ScoreEntry.objects.filter(
        user=user, event=event, dedup_key=dedup_key
    ).exists():
        return None
    points = ACTION_POINTS.get(action, 0)
    if points <= 0:
        return None
    entry = ScoreEntry.objects.create(
        user=user, event=event, action=action, points=points, dedup_key=dedup_key,
    )
    check_achievements(user, event)
    return entry


def has_action(user, event, dedup_key: str) -> bool:
    """Read-only: does a ScoreEntry with this dedup_key already exist?

    Mirrors the dedup check inside award(), for views that want to show
    "already done?" without spelling the query out themselves.
    """
    if user is None or not getattr(user, "is_authenticated", False) or event is None:
        return False
    return ScoreEntry.objects.filter(
        user=user, event=event, dedup_key=dedup_key).exists()


# ── Achievement rules ────────────────────────────────────────────────
# Each rule: callable(counts: dict) -> bool, where `counts` maps a
# ScoreAction value to the number of distinct ScoreEntry rows the user has
# for that action at the event. ScoreEntry is the single source of truth
# (dedup_key already prevents double-counting), so the rules need no
# cross-plugin imports.

def _action_counts(user, event) -> dict:
    rows = (
        ScoreEntry.objects.filter(user=user, event=event)
        .values("action").annotate(n=Count("id"))
    )
    return {r["action"]: r["n"] for r in rows}


_Q = ScoreAction.QUESTION_ASKED
_UV = ScoreAction.QUESTION_UPVOTED
_PV = ScoreAction.POLL_VOTED
_SR = ScoreAction.SESSION_RATED
_SV = ScoreAction.SURVEY_SUBMITTED
_BC = ScoreAction.BOOTH_CHECKIN
_BQ = ScoreAction.BOOTH_QUIZ
_PC = ScoreAction.POSTER_CHECKIN
_AS = ScoreAction.ABSTRACT_STARRED

ACHIEVEMENT_RULES = {
    "first_question":    lambda c: c.get(_Q, 0) >= 1,
    "discussion_driver": lambda c: c.get(_Q, 0) >= 5,
    "active_voter":      lambda c: c.get(_UV, 0) >= 10,
    "poll_enthusiast":   lambda c: c.get(_PV, 0) >= 3,
    "honest_critic":     lambda c: c.get(_SR, 0) >= 5,
    "feedback_champion": lambda c: c.get(_SV, 0) >= 1,
    "fully_engaged":     lambda c: (
        c.get(_Q, 0) >= 1 and c.get(_PV, 0) >= 1
        and c.get(_SR, 0) >= 1 and c.get(_SV, 0) >= 1
    ),
    # Expo — booths and posters.
    # Since the audience vote, poster_fan/expo_champion count poster
    # check-ins rather than ratings: stars are capped at 3 per event, so a
    # threshold of 5 on them would be unreachable.
    "booth_explorer":    lambda c: c.get(_BC, 0) >= 3,
    "quiz_whiz":         lambda c: c.get(_BQ, 0) >= 5,
    "poster_fan":        lambda c: c.get(_PC, 0) >= 5,
    "expo_champion":     lambda c: c.get(_BQ, 0) >= 3 and c.get(_PC, 0) >= 5,
    # Publikums-Voting — alle Sterne vergeben.
    "star_giver":        lambda c: c.get(_AS, 0) >= 3,
}


def check_achievements(user, event):
    """Grant any achievement whose rule now passes and isn't yet awarded."""
    if user is None or not getattr(user, "is_authenticated", False) or event is None:
        return
    already = set(
        UserAchievement.objects.filter(user=user, event=event)
        .values_list("achievement__key", flat=True)
    )
    counts = _action_counts(user, event)
    for ach in Achievement.objects.all():
        if ach.key in already:
            continue
        rule = ACHIEVEMENT_RULES.get(ach.key)
        if rule and rule(counts):
            UserAchievement.objects.get_or_create(user=user, event=event, achievement=ach)


def user_stats(user, event) -> dict:
    """Everything the /me/ page and leaderboard need for one user."""
    score = ScoreEntry.total_for(user, event)
    earned = list(
        UserAchievement.objects.filter(user=user, event=event)
        .select_related("achievement").order_by("achievement__order")
    )
    earned_keys = {ua.achievement.key for ua in earned}
    all_achievements = list(Achievement.objects.all())
    locked = [a for a in all_achievements if a.key not in earned_keys]
    breakdown = list(
        ScoreEntry.objects.filter(user=user, event=event)
        .values("action").annotate(n=Count("id")).order_by("action")
    )
    counts = {r["action"]: r["n"] for r in breakdown}
    return {
        "score": score,
        "earned": earned,
        "locked": locked,
        "total_badges": len(all_achievements),
        "breakdown": breakdown,
        "recent": list(ScoreEntry.objects.filter(user=user, event=event)[:15]),
        "expo": {
            "booths": counts.get(ScoreAction.BOOTH_CHECKIN, 0),
            "quiz_correct": counts.get(ScoreAction.BOOTH_QUIZ, 0),
            "posters": counts.get(ScoreAction.POSTER_CHECKIN, 0),
        },
        "stars": _star_progress(user, event),
    }


def _star_progress(user, event) -> dict:
    """The audience-vote budget, including a ready-made slot list for the
    template (True = given, False = still available)."""
    from lma_connect.plugins.abstracts.models import STARS_PER_USER
    from lma_connect.plugins.abstracts.services import stars_left, stars_used

    used = stars_used(user, event)
    left = stars_left(user, event)
    return {
        "used": used,
        "left": left,
        "total": STARS_PER_USER,
        "slots": [True] * used + [False] * left,
    }


def leaderboard(event, limit: int = 20):
    """Top-N users by score for an event. Returns list of (user, points)."""
    rows = list(
        ScoreEntry.objects.filter(event=event)
        .values("user")
        .annotate(points=Sum("points"))
        .order_by("-points")[:limit]
    )
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user_map = {u.pk: u for u in User.objects.filter(pk__in=[r["user"] for r in rows])}
    return [(user_map[r["user"]], r["points"]) for r in rows if r["user"] in user_map]
