"""Operations team frontend: token management and user support.

Guarded by `@ops_required` — the user has to be in the Django group
"Operations Team" (or be a superuser). This is the desk staff's tool during
the conference: someone lost their badge, someone locked themselves out,
someone needs a fresh QR code.

URLs under /ops/:
    /ops/                             — dashboard
    /ops/tokens/                      — token list
    /ops/tokens/new/                  — generate tokens (single or bulk)
    /ops/tokens/<id>/qr/              — QR for a single token (PNG)
    /ops/users/                       — user search
    /ops/users/<id>/                  — user detail and actions
    /ops/users/<id>/reset-password/   — set a temporary password
    /ops/users/<id>/unlock/           — lift a django-axes lockout
    /ops/users/<id>/new-token/        — issue a new access token for a user
"""

import secrets

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from lma_connect.plugins.core.models import Event
from lma_connect.plugins.qr.services import qr_png_response

from .models import AccessToken
from .permissions import ops_required

User = get_user_model()


def _is_protected_target(user) -> bool:
    """Accounts with elevated privileges (staff/superuser) must NOT be
    manageable from the ops support frontend.

    Otherwise an ops member could take over an admin account through a
    password reset or a fresh login token, and promote themselves that way.
    Ops looks after ordinary attendee accounts, nothing else.
    """
    return user.is_staff or user.is_superuser


@ops_required
def abstracts_results(request):
    """Aggregated reviewer results per abstract, sorted by average score."""
    from lma_connect.plugins.abstracts.models import Abstract

    event = Event.get_active(request)
    sort = request.GET.get("sort", "avg")  # avg | sum | n | poster
    min_required = 3

    # A few dozen abstracts at most → aggregate in Python, no ORM tricks
    qs = Abstract.objects.filter(event=event) if event else Abstract.objects.all()
    abstracts = list(
        qs.select_related("category").prefetch_related("reviews__reviewer")
    )

    rows = []
    for a in abstracts:
        all_reviews = list(a.reviews.all())
        done_scores = [r.score for r in all_reviews if r.score is not None]
        n_assigned = len(all_reviews)
        n_done = len(done_scores)
        avg = sum(done_scores) / n_done if n_done else None
        total = sum(done_scores) if n_done else None
        spread = max(done_scores) - min(done_scores) if n_done > 1 else 0
        rows.append({
            "abstract": a,
            "n_assigned": n_assigned,
            "n_done": n_done,
            "avg": avg,
            "sum": total,
            "spread": spread,
            "below_min": n_done < min_required,
            "scores": sorted(done_scores) if done_scores else [],
        })

    # Sort
    if sort == "sum":
        rows.sort(key=lambda r: (r["sum"] is None, r["sum"] or 99))
    elif sort == "n":
        rows.sort(key=lambda r: (-r["n_done"], r["abstract"].poster_id or ""))
    elif sort == "poster":
        rows.sort(key=lambda r: r["abstract"].poster_id or "")
    else:  # avg default (best first, 1 = best)
        rows.sort(key=lambda r: (r["avg"] is None, r["avg"] or 99))

    total_assigned = sum(r["n_assigned"] for r in rows)
    total_done = sum(r["n_done"] for r in rows)
    below_min_count = sum(1 for r in rows if r["below_min"] and r["n_assigned"] > 0)

    return render(request, "access/ops/abstracts_results.html", {
        "event": event, "rows": rows, "sort": sort,
        "min_required": min_required,
        "total_assigned": total_assigned,
        "total_done": total_done,
        "below_min_count": below_min_count,
        "n_published": sum(1 for a in abstracts if a.is_published),
        "n_total": len(abstracts),
        "active_tab": "ops", "active_ops": "abstracts",
    })


@ops_required
@require_POST
def abstract_toggle_publish(request, abstract_id: int):
    """HTMX: toggle `is_published` straight from the review result list.

    Deliberately decoupled from `status`: visibility is an editorial decision,
    the workflow status a formal one. Only `is_published` governs what
    attendees see under /abstracts/.
    """
    from lma_connect.plugins.abstracts.models import Abstract

    abstract = get_object_or_404(Abstract, pk=abstract_id)
    abstract.is_published = not abstract.is_published
    abstract.save(update_fields=["is_published", "updated_at"])

    html = render_to_string("access/ops/_publish_toggle.html",
                            {"abstract": abstract, "with_counter": True}, request)
    if request.POST.get("with_counter"):
        scope = Abstract.objects.filter(event=abstract.event)
        html += render_to_string("access/ops/_publish_counter.html", {
            "n_published": scope.filter(is_published=True).count(),
            "n_total": scope.count(),
        }, request)
    return HttpResponse(html)


@ops_required
def abstract_results_detail(request, abstract_id: int):
    """Every review of one abstract — reviewer, score, comment, submit date."""
    from lma_connect.plugins.abstracts.models import Abstract

    abstract = get_object_or_404(
        Abstract.objects.select_related("category", "event")
        .prefetch_related("authors", "reviews__reviewer"),
        pk=abstract_id,
    )
    reviews = list(abstract.reviews.select_related("reviewer").order_by("reviewer__username"))
    done = [r for r in reviews if r.score is not None]
    avg = sum(r.score for r in done) / len(done) if done else None
    total = sum(r.score for r in done) if done else None
    return render(request, "access/ops/abstract_results_detail.html", {
        "event": Event.get_active(request), "abstract": abstract, "reviews": reviews,
        "avg": avg, "total": total, "n_done": len(done), "n_assigned": len(reviews),
        "active_tab": "ops", "active_ops": "abstracts",
    })


@ops_required
def abstract_star_ranking(request):
    """Audience vote: ranking by stars given, plus handing out the award.

    Deliberately separate from the reviewer result list: there the committee
    scores (scale 1–6, low = good), here the audience votes (stars, high =
    good). Two sources, two pages.
    """
    from lma_connect.plugins.abstracts.models import (
        STARS_PER_USER,
        AbstractAward,
        AbstractStarVote,
    )
    from lma_connect.plugins.abstracts.services import star_ranking

    event = Event.get_active(request)
    rows = star_ranking(event)
    votes = AbstractStarVote.objects.filter(abstract__event=event) if event else \
        AbstractStarVote.objects.none()
    total_votes = votes.count()
    n_voters = votes.values("user").distinct().count()

    # Make a tie at the top visible — otherwise the first table row looks
    # like a clear winner when it is not.
    top_stars = rows[0].n_stars if rows and rows[0].n_stars else 0
    leaders = [r for r in rows if top_stars and r.n_stars == top_stars]

    # The template compares against this to decide whether the trophy button
    # grants or revokes. None means the event has no audience award defined —
    # the template then explains that instead of offering a dead button.
    audience_award = AbstractAward.objects.filter(
        event=event, is_audience_choice=True).first() if event else None

    return render(request, "access/ops/abstract_stars.html", {
        "event": event, "rows": rows,
        "total_votes": total_votes,
        "n_voters": n_voters,
        "stars_per_user": STARS_PER_USER,
        "leaders": leaders,
        "is_tie": len(leaders) > 1,
        "audience_award": audience_award,
        "active_tab": "ops", "active_ops": "stars",
    })


@ops_required
@require_POST
def abstract_set_audience_award(request, abstract_id: int):
    """Grant or revoke the audience-choice award.

    Only one abstract per event can hold it — a new winner replaces the old
    one. The other awards (best poster, jury prizes, …) are untouched.

    Which award counts as "the audience one" is a per-event flag, not a fixed
    slug: an event may call it Audience Choice Award, Publikumspreis or
    People's Choice, and some events do not hand one out at all.
    """
    from lma_connect.plugins.abstracts.models import Abstract, AbstractAward

    abstract = get_object_or_404(Abstract, pk=abstract_id)
    audience_award = AbstractAward.objects.filter(
        event=abstract.event, is_audience_choice=True).first()

    if audience_award is None:
        messages.error(request, _("No audience-choice award is configured for this event. "
                                  "Create one in the admin and tick “Audience choice”."))
        return redirect("access:ops_abstract_stars")

    if abstract.award_id == audience_award.pk:
        abstract.award = None
        abstract.award_at = None
        abstract.save(update_fields=["award", "award_at", "updated_at"])
        messages.success(request, _("Removed the audience award from “%(title)s”.")
                         % {"title": abstract.title[:60]})
    else:
        Abstract.objects.filter(
            event=abstract.event, award=audience_award,
        ).exclude(pk=abstract.pk).update(award=None, award_at=None)
        abstract.award = audience_award
        abstract.award_at = timezone.localdate()
        abstract.save(update_fields=["award", "award_at", "updated_at"])
        messages.success(request, _("“%(title)s” now holds the %(award)s.")
                         % {"title": abstract.title[:60], "award": audience_award.name})

    return redirect("access:ops_abstract_stars")


@ops_required
def dashboard(request):
    """Ops dashboard with quick stats."""
    from lma_connect.plugins.people.models import ParticipantCategory

    event = Event.get_active(request)
    tokens_qs = AccessToken.objects.all()
    if event:
        tokens_qs = tokens_qs.filter(event=event)

    stats = {
        "tokens_total": tokens_qs.count(),
        "tokens_active": tokens_qs.filter(is_active=True).count(),
        "tokens_redeemed": tokens_qs.exclude(user=None).count(),
        "tokens_open": tokens_qs.filter(user=None, is_active=True).count(),
        "users_total": User.objects.count(),
        "users_active_today": User.objects.filter(
            last_login__gte=timezone.now() - timezone.timedelta(days=1)
        ).count(),
    }
    return render(request, "access/ops/dashboard.html", {
        "event": event, "stats": stats, "categories": ParticipantCategory.choices,
        "active_tab": "ops", "active_ops": "dashboard",
    })


@ops_required
def tokens_list(request):
    """Token list with filters (status, group) and search (label/token/username)."""
    from lma_connect.plugins.people.models import ParticipantCategory

    event = Event.get_active(request)
    status = request.GET.get("status", "")
    category = request.GET.get("category", "")
    q = request.GET.get("q", "").strip()

    qs = AccessToken.objects.select_related("user", "event")
    if event:
        qs = qs.filter(event=event)
    if status == "open":
        qs = qs.filter(user=None, is_active=True)
    elif status == "redeemed":
        qs = qs.exclude(user=None)
    elif status == "inactive":
        qs = qs.filter(is_active=False)
    if category in dict(ParticipantCategory.choices):
        qs = qs.filter(category=category)
    if q:
        qs = qs.filter(
            Q(token__icontains=q) | Q(label__icontains=q)
            | Q(user__username__icontains=q) | Q(user__first_name__icontains=q)
        )
    qs = qs.order_by("-created_at")[:200]

    return render(request, "access/ops/tokens_list.html", {
        "event": event, "tokens": qs, "status": status, "q": q,
        "category": category, "categories": ParticipantCategory.choices,
        "active_tab": "ops", "active_ops": "tokens",
    })


@ops_required
@require_POST
def tokens_create(request):
    """Single- oder Bulk-Token-Generator."""
    from lma_connect.plugins.people.models import ParticipantCategory

    event = Event.get_active(request)
    if event is None:
        messages.error(request, _("No active event"))
        return redirect("access:ops_tokens")
    try:
        count = int(request.POST.get("count") or "1")
    except ValueError:
        count = 1
    count = max(1, min(count, 1000))
    label = (request.POST.get("label") or "").strip()
    category = request.POST.get("category", "")
    if category not in dict(ParticipantCategory.choices):
        category = ParticipantCategory.DELEGATE
    created = []
    for _i in range(count):
        created.append(AccessToken.objects.create(event=event, label=label, category=category))
    messages.success(request, _("%(count)d token(s) created") % {"count": len(created)})
    if len(created) == 1:
        return redirect(reverse("access:ops_token_detail",
                                kwargs={"token_id": created[0].pk}))
    return redirect(f"{reverse('access:ops_tokens')}?status=open")


@ops_required
def token_detail(request, token_id: int):
    """A single token with its QR code and the available actions."""
    token = get_object_or_404(AccessToken, pk=token_id)
    qr_url = request.build_absolute_uri(token.get_redeem_url())
    return render(request, "access/ops/token_detail.html", {
        "event": Event.get_active(request), "token": token, "qr_url": qr_url,
        "active_tab": "ops", "active_ops": "tokens",
    })


@ops_required
def token_qr_image(request, token_id: int):
    """PNG QR code for a single token — embedded directly in the detail page."""
    token = get_object_or_404(AccessToken, pk=token_id)
    url = request.build_absolute_uri(token.get_redeem_url())
    return qr_png_response(url)


@ops_required
def token_print(request, token_id: int):
    """Print view for a single token: an A6 card, one-sided, with a large QR."""
    token = get_object_or_404(AccessToken, pk=token_id)
    qr_url = request.build_absolute_uri(token.get_redeem_url())
    return render(request, "access/ops/token_print.html", {
        "event": Event.get_active(request), "token": token, "qr_url": qr_url,
    })


@ops_required
@require_POST
def token_toggle_active(request, token_id: int):
    token = get_object_or_404(AccessToken, pk=token_id)
    token.is_active = not token.is_active
    token.save(update_fields=["is_active", "updated_at"])
    messages.success(request,
                     _("Token activated") if token.is_active else _("Token deactivated"))
    return redirect(reverse("access:ops_token_detail", kwargs={"token_id": token.pk}))


@ops_required
def users_list(request):
    """User list: everyone, with filters (category, social event) and search."""
    from lma_connect.plugins.people.models import ParticipantCategory, PersonProfile

    event = Event.get_active(request)
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    social = request.GET.get("social", "")  # "yes" / "no" / ""

    users = User.objects.all().annotate(
        n_tokens=Count("access_tokens", distinct=True),
        n_reviews=Count("abstract_reviews", distinct=True),
    ).order_by("username")

    if q:
        users = users.filter(
            Q(username__icontains=q) | Q(first_name__icontains=q)
            | Q(last_name__icontains=q) | Q(email__icontains=q)
        )
    if category:
        users = users.filter(event_profiles__category=category,
                             event_profiles__event=event)
    if social == "yes":
        users = users.filter(event_profiles__social_event_registered=True,
                             event_profiles__event=event)
    elif social == "no":
        users = users.exclude(event_profiles__social_event_registered=True,
                              event_profiles__event=event)

    # Attach the profile data (for the category column and the social flag)
    if event:
        profiles_by_user = {
            p.user_id: p for p in PersonProfile.objects.filter(event=event)
        }
    else:
        profiles_by_user = {}
    users_with_profile = []
    for u in users[:500]:
        prof = profiles_by_user.get(u.pk)
        u.profile = prof
        u.category_label = prof.get_category_display() if prof else "—"
        u.category_key = prof.category if prof else ""
        u.social_flag = prof.social_event_registered if prof else False
        users_with_profile.append(u)

    return render(request, "access/ops/users_list.html", {
        "event": event, "users": users_with_profile, "q": q,
        "category": category, "social": social,
        "categories": ParticipantCategory.choices,
        "total_count": User.objects.count(),
        "active_tab": "ops", "active_ops": "users",
    })


@ops_required
def user_detail(request, user_id: int):
    from lma_connect.plugins.people.models import ParticipantCategory, PersonProfile

    target = get_object_or_404(
        User.objects.prefetch_related("access_tokens", "groups", "abstract_reviews"),
        pk=user_id,
    )
    event = Event.get_active(request)
    profile = None
    if event:
        profile, _created = PersonProfile.objects.get_or_create(user=target, event=event)
    return render(request, "access/ops/user_detail.html", {
        "event": event, "target": target, "profile": profile,
        "target_protected": _is_protected_target(target),
        "categories": ParticipantCategory.choices,
        "active_tab": "ops", "active_ops": "users",
    })


@ops_required
@require_POST
def user_update_profile(request, user_id: int):
    """Ops only: set category and social_event_registered for the user in the
    currently active event."""
    from lma_connect.plugins.people.models import ParticipantCategory, PersonProfile

    target = get_object_or_404(User, pk=user_id)
    event = Event.get_active(request)
    if event is None:
        messages.error(request, _("No active event"))
        return redirect(reverse("access:ops_user_detail", kwargs={"user_id": target.pk}))
    profile, _created = PersonProfile.objects.get_or_create(user=target, event=event)
    cat = request.POST.get("category", "")
    if cat in dict(ParticipantCategory.choices):
        profile.category = cat
    profile.social_event_registered = bool(request.POST.get("social_event_registered"))
    profile.save(update_fields=["category", "social_event_registered", "updated_at"])
    messages.success(request, _("Profile updated"))
    return redirect(reverse("access:ops_user_detail", kwargs={"user_id": target.pk}))


@ops_required
@require_POST
def user_reset_password(request, user_id: int):
    """Set the password to a temporary random value. Ops reads it out to the
    attendee at the desk — it is never sent anywhere."""
    target = get_object_or_404(User, pk=user_id)
    if _is_protected_target(target):
        messages.error(request,
                       _("This account has elevated privileges (staff/admin) and "
                         "cannot be managed from the Ops frontend."))
        return redirect(reverse("access:ops_user_detail", kwargs={"user_id": target.pk}))
    new_pw = secrets.token_urlsafe(9)  # ~12 char readable
    target.set_password(new_pw)
    target.save(update_fields=["password"])
    messages.success(request,
                     _("Temporary password for %(user)s: %(pw)s "
                       "— give this to the user; they should change it after login.")
                     % {"user": target.username, "pw": new_pw})
    return redirect(reverse("access:ops_user_detail", kwargs={"user_id": target.pk}))


@ops_required
@require_POST
def user_unlock_axes(request, user_id: int):
    """Lift a django-axes lockout for a user."""
    target = get_object_or_404(User, pk=user_id)
    if _is_protected_target(target):
        messages.error(request,
                       _("This account has elevated privileges (staff/admin) and "
                         "cannot be managed from the Ops frontend."))
        return redirect(reverse("access:ops_user_detail", kwargs={"user_id": target.pk}))
    try:
        from axes.models import AccessAttempt
        # Delete every recorded attempt for this username
        n = AccessAttempt.objects.filter(username=target.username).delete()[0]
        messages.success(request,
                         _("Cleared %(n)d axes lockout entries for %(user)s")
                         % {"n": n, "user": target.username})
    except ImportError:
        messages.error(request, _("django-axes not installed"))
    return redirect(reverse("access:ops_user_detail", kwargs={"user_id": target.pk}))


@ops_required
@require_POST
def user_new_token(request, user_id: int):
    """Generate a new token and bind it to the user straight away — the
    "I lost my badge" case."""
    target = get_object_or_404(User, pk=user_id)
    if _is_protected_target(target):
        messages.error(request,
                       _("This account has elevated privileges (staff/admin) and "
                         "cannot be managed from the Ops frontend."))
        return redirect(reverse("access:ops_user_detail", kwargs={"user_id": target.pk}))
    event = Event.get_active(request)
    if event is None:
        messages.error(request, _("No active event"))
        return redirect(reverse("access:ops_user_detail", kwargs={"user_id": target.pk}))
    from lma_connect.plugins.people.models import ParticipantCategory, PersonProfile
    profile = PersonProfile.objects.filter(user=target, event=event).first()
    category = profile.category if profile else ParticipantCategory.DELEGATE
    token = AccessToken.objects.create(
        event=event, user=target, category=category,
        label=f"Replacement for {target.username}",
        redeemed_at=timezone.now(),
    )
    messages.success(request,
                     _("New token %(token)s created and linked to %(user)s")
                     % {"token": token.token, "user": target.username})
    return redirect(reverse("access:ops_token_detail", kwargs={"token_id": token.pk}))
