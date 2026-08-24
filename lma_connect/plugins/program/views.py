from collections import defaultdict
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from lma_connect.plugins.core.models import Event

from .models import (
    LivePoll,
    LivePollOption,
    LivePollResponse,
    Question,
    QuestionUpvote,
    ScreenSource,
    Session,
    SessionChair,
    SessionRating,
)

# Slow down Q&A flooding and point farming: at most N questions per (user,
# session) within the window. Best effort — LocMemCache is process-local; move
# to Redis or a file cache in a multi-worker setup.
_QA_MAX_PER_WINDOW = 5
_QA_WINDOW_SECONDS = 60


def _is_chair(user, session: Session) -> bool:
    """True if `user` may moderate Q&A for `session` — i.e. is a SessionChair
    of it, or is staff/superuser."""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff or user.is_superuser:
        return True
    return SessionChair.objects.filter(session=session, user=user).exists()


def chair_required(view_func):
    """Require a login plus chair rights for the session in question.

    Resolves the session from the `slug`, `question_id` OR `poll_id` URL
    kwarg, checks `_is_chair` and hands the result to the view:
      request.chair_session   — the session (always)
      request.chair_question  — the question (question_id routes only)
      request.chair_poll      — the poll (poll_id routes only)
    Replaces the inline checks that used to be repeated in every view.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if "slug" in kwargs:
            session = get_object_or_404(
                Session.objects.select_related("event"),
                slug=kwargs["slug"], is_published=True,
            )
        elif "question_id" in kwargs:
            question = get_object_or_404(
                Question.objects.select_related("session__event"),
                id=kwargs["question_id"],
            )
            session = question.session
            request.chair_question = question
        elif "poll_id" in kwargs:
            poll = get_object_or_404(
                LivePoll.objects.select_related("session__event"),
                id=kwargs["poll_id"],
            )
            session = poll.session
            request.chair_poll = poll
        else:  # pragma: no cover — a programming error, not a chair route
            raise PermissionDenied("No session context for chair check.")
        if not _is_chair(request.user, session):
            raise PermissionDenied("You are not a chair of this session.")
        request.chair_session = session
        return view_func(request, *args, **kwargs)
    return login_required(_wrapped)


def session_list(request):
    event = Event.get_active(request)
    sessions_by_day: dict = defaultdict(list)
    tracks = []
    current_session_id = None
    if event:
        sessions = (
            event.sessions.filter(is_published=True)
            .select_related("track", "room")
            .prefetch_related("speakers__speaker__profile__user")
            .order_by("starts_at")
        )
        now = timezone.now()
        for s in sessions:
            sessions_by_day[s.starts_at.date()].append(s)
            if s.starts_at <= now <= s.ends_at:
                current_session_id = s.id
        tracks = event.tracks.order_by("order")
    return render(request, "program/list.html", {
        "event": event,
        "sessions_by_day": dict(sessions_by_day),
        "tracks": tracks,
        "current_session_id": current_session_id,
        "active_tab": "program",
    })


def session_detail(request, slug):
    event = Event.get_active(request)
    session = get_object_or_404(
        Session.objects.select_related("track", "room", "event")
        .prefetch_related("speakers__speaker__profile__user", "chairs__user"),
        slug=slug, is_published=True,
    )
    return render(request, "program/detail.html", {
        "event": event,
        "session": session,
        "session_chairs": list(session.chairs.select_related("user").all()),
        "is_chair": _is_chair(request.user, session),
        "active_tab": "program",
        **_session_interaction_context(session, request.user),
    })


def _session_interaction_context(session: Session, user) -> dict:
    """Aggregated live data for the session detail page (Q&A, polls, rating).
    Public Q&A list: approved questions, starred ones first."""
    questions = (
        session.questions.filter(is_approved=True)
        .annotate(votes=Count("upvotes"))
        .order_by("-is_starred", "-votes", "-created_at")
    )
    user_upvoted_ids = set()
    user_rating = None
    user_poll_choice_ids: dict[int, set[int]] = {}
    user_poll_text: dict[int, str] = {}
    if user.is_authenticated:
        user_upvoted_ids = set(
            QuestionUpvote.objects.filter(user=user, question__session=session)
            .values_list("question_id", flat=True)
        )
        user_rating = SessionRating.objects.filter(session=session, user=user).first()
        for resp in LivePollResponse.objects.filter(poll__session=session, user=user):
            if resp.option_id:
                user_poll_choice_ids.setdefault(resp.poll_id, set()).add(resp.option_id)
            if resp.text_answer:
                user_poll_text[resp.poll_id] = resp.text_answer
    polls = list(session.polls.filter(is_active=True).prefetch_related("options"))
    poll_results = {p.id: _poll_results(p) for p in polls}

    return {
        "questions": questions,
        "user_upvoted_ids": user_upvoted_ids,
        "polls": polls,
        "poll_results": poll_results,
        "user_poll_choice_ids": user_poll_choice_ids,
        "user_poll_text": user_poll_text,
        "user_rating": user_rating,
        "agg": _rating_agg_flat(session),
        "dimensions": RATING_DIMENSION_LABELS,
    }


def _poll_results(poll: LivePoll) -> dict:
    """Aggregierte Stimmen pro Option + Total."""
    counts = (
        poll.responses.values("option_id")
        .annotate(n=Count("id"))
        .order_by()
    )
    by_option = {row["option_id"]: row["n"] for row in counts if row["option_id"]}
    total_votes = sum(by_option.values())
    text_answers = list(
        poll.responses.exclude(text_answer="").values_list("text_answer", flat=True)
    )
    return {"by_option": by_option, "total": total_votes, "text_answers": text_answers}


# ─── HTMX-Endpoints ───────────────────────────────────────

@login_required
@require_POST
def question_create(request, slug):
    session = get_object_or_404(Session, slug=slug, is_published=True, qa_enabled=True)
    text = (request.POST.get("text") or "").strip()
    if not text:
        return HttpResponseBadRequest(_("Question must not be empty"))
    # Rate limit: keeps Q&A spam off the public wall and stops unbounded
    # point farming (every question awards QUESTION_ASKED points).
    rate_key = f"qa_rate:{request.user.pk}:{session.pk}"
    if (cache.get(rate_key) or 0) >= _QA_MAX_PER_WINDOW:
        return HttpResponse(
            _("Too many questions in a short time — please wait a moment."), status=429)
    cache.set(rate_key, (cache.get(rate_key) or 0) + 1, _QA_WINDOW_SECONDS)
    Question.objects.create(
        session=session,
        asker=request.user,
        text=text[:2000],
        # In a moderated session it only becomes visible once approved;
        # otherwise release it straight away
        is_approved=not session.qa_moderated,
    )
    return _render_qa_partial(request, session)


@login_required
@require_POST
def question_upvote(request, question_id: int):
    question = get_object_or_404(Question, id=question_id, is_approved=True)
    upvote, created = QuestionUpvote.objects.get_or_create(
        question=question, user=request.user
    )
    if not created:
        upvote.delete()
    return _render_qa_partial(request, question.session)


def _render_qa_partial(request, session: Session):
    ctx = _session_interaction_context(session, request.user)
    return render(request, "program/_qa_panel.html", {
        "session": session, **ctx,
    })


@login_required
@require_POST
def poll_vote(request, poll_id: int):
    poll = get_object_or_404(LivePoll, id=poll_id, is_active=True)
    if poll.type == "open":
        text = (request.POST.get("text_answer") or "").strip()
        if text:
            LivePollResponse.objects.update_or_create(
                poll=poll, user=request.user, option=None,
                defaults={"text_answer": text[:2000]},
            )
    elif poll.type == "single":
        opt_id = request.POST.get("option")
        if opt_id:
            opt = get_object_or_404(LivePollOption, id=opt_id, poll=poll)
            # Single choice: drop the previous answer, store the new one
            LivePollResponse.objects.filter(poll=poll, user=request.user).delete()
            LivePollResponse.objects.create(poll=poll, user=request.user, option=opt)
    elif poll.type == "multi":
        opt_ids = request.POST.getlist("options")
        valid_ids = list(poll.options.filter(id__in=opt_ids).values_list("id", flat=True))
        LivePollResponse.objects.filter(poll=poll, user=request.user).delete()
        LivePollResponse.objects.bulk_create([
            LivePollResponse(poll=poll, user=request.user, option_id=oid)
            for oid in valid_ids
        ])
    return _render_poll_partial(request, poll)


def _render_poll_partial(request, poll: LivePoll):
    user = request.user
    user_choice_ids: set[int] = set()
    user_text = ""
    if user.is_authenticated:
        for resp in LivePollResponse.objects.filter(poll=poll, user=user):
            if resp.option_id:
                user_choice_ids.add(resp.option_id)
            if resp.text_answer:
                user_text = resp.text_answer
    return render(request, "program/_poll_card.html", {
        "poll": poll,
        "results": _poll_results(poll),
        "user_choice_ids": user_choice_ids,
        "user_text": user_text,
    })


# ─── Poll projection (the chair puts results on the wall, 16:9) ───

def _poll_project_context(poll: LivePoll) -> dict:
    """Results prepared for the projection view: per option a count and a
    percentage, precomputed so the template stays thin."""
    results = _poll_results(poll)
    total = results["total"]
    options = []
    for opt in poll.options.all():
        cnt = results["by_option"].get(opt.id, 0)
        options.append({
            "text": opt.text,
            "count": cnt,
            "pct": round(cnt * 100 / total) if total else 0,
        })
    # Highlight the leading option — only when there are votes at all.
    leader = max((o["count"] for o in options), default=0)
    for o in options:
        o["is_leader"] = total > 0 and o["count"] == leader and leader > 0
    return {
        "poll": poll,
        "options": options,
        "total": total,
        "text_answers": results["text_answers"],
    }


@chair_required
def poll_project(request, poll_id: int):
    """Full-screen result view (16:9) for projection. Chairs and staff only.

    Shows the results regardless of `is_results_public` — that flag governs
    visibility inside the attendees' app, which is a separate decision.
    """
    poll = request.chair_poll
    return render(request, "program/poll_project.html", {
        "event": poll.session.event,
        "session": poll.session,
        **_poll_project_context(poll),
    })


@chair_required
def poll_project_results(request, poll_id: int):
    """The result block only — reloaded via HTMX every few seconds."""
    poll = request.chair_poll
    return render(request, "program/_poll_project_results.html",
                  _poll_project_context(poll))


# ─── Screen switcher (the chair drives the projected source) ──────

SCREEN_QA_LIMIT = 8  # about as many questions as fit legibly on a wall


def _screen_content_context(session: Session) -> dict:
    """Context for whatever is currently projected (standby / Q&A / poll)."""
    source = session.screen_source
    ctx: dict = {"session": session, "event": session.event, "screen_source": source}
    if source == ScreenSource.POLL and session.screen_poll_id:
        poll = (
            LivePoll.objects.filter(id=session.screen_poll_id, session=session)
            .prefetch_related("options").first()
        )
        if poll:
            ctx.update(_poll_project_context(poll))
            return ctx
        # The poll was deleted → fall back to standby.
        ctx["screen_source"] = ScreenSource.STANDBY
    elif source == ScreenSource.QA:
        ctx["screen_questions"] = list(
            session.questions.filter(is_approved=True)
            .annotate(votes=Count("upvotes"))
            .order_by("-is_starred", "-votes", "-created_at")[:SCREEN_QA_LIMIT]
        )
    return ctx


def _current_screen_label(session: Session) -> str:
    if session.screen_source == ScreenSource.POLL:
        poll = LivePoll.objects.filter(
            id=session.screen_poll_id, session=session).first()
        if poll:
            return f"{poll.question_text[:50]}"
        return str(ScreenSource.STANDBY.label)
    return str(ScreenSource(session.screen_source).label)


def _chair_screen_context(session: Session) -> dict:
    return {
        "session": session,
        "screen_polls": list(session.polls.order_by("-created_at")),
        "screen_source": session.screen_source,
        "screen_poll_id": session.screen_poll_id,
        "current_screen_label": _current_screen_label(session),
    }


def _render_chair_screen(request, session: Session):
    return render(request, "program/_chair_screen.html",
                  _chair_screen_context(session))


@chair_required
@require_POST
def poll_toggle_active(request, poll_id: int):
    """The chair opens or closes a poll (the is_active flag)."""
    poll = request.chair_poll
    poll.is_active = not poll.is_active
    poll.save(update_fields=["is_active", "updated_at"])
    return _render_chair_screen(request, poll.session)


RATING_DIMENSIONS = ("slides", "clarity", "relevance", "overall")
RATING_DIMENSION_LABELS = [
    ("slides", "Slides"),
    ("clarity", "Clarity (English)"),
    ("relevance", "Practical relevance"),
    ("overall", "Overall"),
]


def _rating_aggregate(session: Session) -> dict:
    """Averages per dimension plus the number of ratings."""
    return session.ratings.aggregate(
        avg_slides=Avg("rating_slides"),
        avg_clarity=Avg("rating_clarity"),
        avg_relevance=Avg("rating_relevance"),
        avg_overall=Avg("rating_overall"),
        n=Count("id"),
    )


def _rating_agg_flat(session: Session) -> dict:
    """A flat form of `_rating_aggregate`: dim_key → average (plus n), so the
    template can reach it via dict_get:dim_key."""
    raw = _rating_aggregate(session)
    return {
        "n": raw["n"],
        "slides": raw["avg_slides"],
        "clarity": raw["avg_clarity"],
        "relevance": raw["avg_relevance"],
        "overall": raw["avg_overall"],
    }


@login_required
@require_POST
def session_rate(request, slug):
    """Four-dimensional rating update: individual dimensions are set via
    dimension+value, the comment via 'comment'. One row per (session, user)."""
    session = get_object_or_404(Session, slug=slug, is_published=True, rating_enabled=True)
    rating, _created = SessionRating.objects.get_or_create(
        session=session, user=request.user,
        defaults={"is_anonymous": True},
    )
    dimension = request.POST.get("dimension")
    value_raw = request.POST.get("value")
    if dimension and value_raw:
        if dimension not in RATING_DIMENSIONS:
            return HttpResponseBadRequest(_("Invalid dimension"))
        try:
            value_int = int(value_raw)
        except ValueError:
            return HttpResponseBadRequest(_("Value must be between 1 and 5"))
        if not 1 <= value_int <= 5:
            return HttpResponseBadRequest(_("Value must be between 1 and 5"))
        setattr(rating, f"rating_{dimension}", value_int)
        rating.save(update_fields=[f"rating_{dimension}", "updated_at"])

    if "comment" in request.POST:
        rating.comment = (request.POST.get("comment") or "").strip()[:4000]
        rating.save(update_fields=["comment", "updated_at"])

    return _render_rating_partial(request, session)


def _render_rating_partial(request, session: Session):
    return render(request, "program/_rating_card.html", {
        "session": session,
        "user_rating": session.ratings.filter(user=request.user).first()
            if request.user.is_authenticated else None,
        "agg": _rating_agg_flat(session),
        "dimensions": RATING_DIMENSION_LABELS,
    })


# ─── Session-chair Q&A moderation ──────────────────────────

def _chair_questions(session: Session):
    """All questions for the chair view — starred first, then upvotes, then time.
    Includes unapproved ones (the chair decides what to show publicly)."""
    return (
        session.questions
        .annotate(votes=Count("upvotes"))
        .select_related("asker", "added_by_chair")
        .order_by("-is_starred", "-votes", "-created_at")
    )


@chair_required
def chair_panel(request, slug):
    session = request.chair_session
    return render(request, "program/chair_panel.html", {
        "event": session.event,
        "session": session,
        "active_tab": "program",
        "chair_speakers": _chair_speakers(session),
        **_chair_panel_context(session),
        **_chair_screen_context(session),
    })


def _chair_speakers(session: Session):
    return list(session.speakers.select_related("speaker__profile__user"))


@chair_required
@require_POST
def chair_speaker_notes(request, slug, speaker_id: int):
    """The chair saves their private intro notes for one speaker — only for a
    speaker assigned to *this* session (being chair of session A gives no
    write access to speakers of session B)."""
    session = request.chair_session
    assignment = get_object_or_404(
        session.speakers.select_related("speaker__profile__user"),
        speaker_id=speaker_id,
    )
    speaker = assignment.speaker
    speaker.chair_notes = (request.POST.get("chair_notes") or "").strip()[:5000]
    speaker.save(update_fields=["chair_notes", "updated_at"])
    return render(request, "program/_chair_speaker_card.html", {
        "session": session, "sp": assignment, "saved": True,
    })


def _chair_panel_context(session: Session) -> dict:
    return {
        "chair_questions": _chair_questions(session),
        "approved_count": session.questions.filter(is_approved=True).count(),
        "starred_count": session.questions.filter(is_starred=True).count(),
        "total_count": session.questions.count(),
    }


def _render_chair_list(request, session: Session):
    return render(request, "program/_chair_question_list.html", {
        "session": session, **_chair_panel_context(session),
    })


@chair_required
@require_POST
def chair_question_star(request, question_id: int):
    q = request.chair_question
    q.is_starred = not q.is_starred
    q.starred_at = timezone.now() if q.is_starred else None
    # Starring a question implies approving it for public display.
    if q.is_starred and not q.is_approved:
        q.is_approved = True
    q.save(update_fields=["is_starred", "starred_at", "is_approved", "updated_at"])
    return _render_chair_list(request, q.session)


@chair_required
@require_POST
def chair_question_approve(request, question_id: int):
    q = request.chair_question
    q.is_approved = not q.is_approved
    if not q.is_approved:
        # Hiding a question also un-stars it.
        q.is_starred = False
        q.starred_at = None
    q.save(update_fields=["is_approved", "is_starred", "starred_at", "updated_at"])
    return _render_chair_list(request, q.session)


@chair_required
@require_POST
def chair_question_answered(request, question_id: int):
    q = request.chair_question
    q.is_answered = not q.is_answered
    q.answered_at = timezone.now() if q.is_answered else None
    q.save(update_fields=["is_answered", "answered_at", "updated_at"])
    return _render_chair_list(request, q.session)


@chair_required
@require_POST
def chair_question_add(request, slug):
    """Chair prepares their own question — pre-starred and approved."""
    session = request.chair_session
    text = (request.POST.get("text") or "").strip()
    if not text:
        return HttpResponseBadRequest(_("Question text required"))
    Question.objects.create(
        session=session,
        added_by_chair=request.user,
        asker_display_name="Chair",
        text=text[:2000],
        is_approved=True,
        is_starred=True,
        starred_at=timezone.now(),
    )
    return _render_chair_list(request, session)


@chair_required
@require_POST
def chair_question_delete(request, question_id: int):
    q = request.chair_question
    session = q.session
    q.delete()
    return _render_chair_list(request, session)


# ─── Beamer-Screen-Views (brauchen chair_required, s. o.) ──────────

@chair_required
def session_screen(request, slug):
    """Full-screen room display (16:9). Shows whatever the chair currently
    selects; refreshes itself via HTMX polling."""
    session = request.chair_session
    return render(request, "program/screen.html", _screen_content_context(session))


@chair_required
def screen_content(request, slug):
    """The projected content only — reloaded via HTMX every few seconds."""
    session = request.chair_session
    return render(request, "program/_screen_content.html",
                  _screen_content_context(session))


@chair_required
@require_POST
def screen_set_source(request, slug):
    """The chair switches the projected source (standby / qa / poll)."""
    session = request.chair_session
    source = request.POST.get("source")
    if source not in ScreenSource.values:
        return HttpResponseBadRequest(_("Invalid source"))
    if source == ScreenSource.POLL:
        poll = get_object_or_404(
            LivePoll, id=request.POST.get("poll"), session=session)
        session.screen_poll = poll
    session.screen_source = source
    session.save(update_fields=["screen_source", "screen_poll", "updated_at"])
    return _render_chair_screen(request, session)
