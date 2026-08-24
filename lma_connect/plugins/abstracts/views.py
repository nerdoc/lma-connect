from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from lma_connect.plugins.core.models import Event

from .models import STARS_PER_USER, Abstract, AbstractReview
from .services import has_voted, stars_left


def abstract_list(request):
    event = Event.get_active(request)
    abstracts = []
    categories = []
    published_count = 0
    selected_cat = request.GET.get("cat", "")
    selected_type = request.GET.get("type", "")
    awards_only = request.GET.get("awards") == "1"
    q = request.GET.get("q", "").strip()
    if event:
        qs = (
            event.abstracts.filter(is_published=True)
            .select_related("category")
            .prefetch_related("authors")
        )
        if selected_cat:
            qs = qs.filter(category__slug=selected_cat)
        if selected_type:
            qs = qs.filter(type=selected_type)
        if awards_only:
            qs = qs.filter(award__isnull=False)
        if q:
            qs = qs.filter(title__icontains=q) | qs.filter(abstract_text__icontains=q) | qs.filter(keywords__icontains=q)
        # Award winners first, then by type/poster_id/title
        from django.db.models import Case, IntegerField, When
        qs = qs.select_related("award").annotate(
            has_award=Case(
                When(award__isnull=True, then=1),
                default=0,
                output_field=IntegerField(),
            )
        ).order_by("has_award", "type", "poster_id", "title")
        abstracts = qs
        categories = event.abstract_categories.order_by("order")
        # Headline count = accepted/published abstracts, unaffected by the
        # active filters — never the raw submission count.
        published_count = event.abstracts.filter(is_published=True).count()
    return render(request, "abstracts/list.html", {
        "event": event,
        "abstracts": abstracts,
        "published_count": published_count,
        "categories": categories,
        "selected_cat": selected_cat,
        "selected_type": selected_type,
        "awards_only": awards_only,
        "q": q,
        "active_tab": "abstracts",
    })


def abstract_detail(request, slug):
    event = Event.get_active(request)
    abstract = get_object_or_404(
        Abstract.objects.select_related("category", "event")
        .prefetch_related("authors", "references"),
        slug=slug, is_published=True,
    )
    return render(request, "abstracts/detail.html", {
        "event": event, "abstract": abstract, "active_tab": "abstracts",
        # Voting happens at the poster via QR only, so all this page shows
        # is how much of the reader's own star budget is left.
        "stars_total": STARS_PER_USER,
        "stars_left": stars_left(request.user, event),
        "user_star_given": has_voted(request.user, abstract),
    })


@login_required
def review_list(request):
    """Reviewer-Übersicht: zugewiesene Abstracts, getrennt nach offen / erledigt."""
    event = Event.get_active(request)
    qs = (
        AbstractReview.objects
        .filter(reviewer=request.user)
        .select_related("abstract", "abstract__category")
        .prefetch_related("abstract__authors", "abstract__tags")
        .order_by("abstract__poster_id", "abstract__title")
    )
    open_reviews = [r for r in qs if r.score is None]
    done_reviews = [r for r in qs if r.score is not None]
    return render(request, "abstracts/review_list.html", {
        "event": event,
        "open_reviews": open_reviews,
        "done_reviews": done_reviews,
        "total": len(open_reviews) + len(done_reviews),
        "active_tab": "reviews",
    })


@login_required
def review_detail(request, review_id: int):
    """Detail page for one review — the slider a reviewer scores with."""
    review = get_object_or_404(
        AbstractReview.objects.select_related("abstract", "abstract__category")
        .prefetch_related("abstract__authors", "abstract__tags"),
        pk=review_id, reviewer=request.user,
    )
    event = Event.get_active(request)
    # Row navigation (previous/next within the reviewer's own list)
    user_reviews = list(
        AbstractReview.objects.filter(reviewer=request.user)
        .order_by("abstract__poster_id", "abstract__title")
        .values_list("pk", flat=True)
    )
    try:
        idx = user_reviews.index(review.pk)
        prev_id = user_reviews[idx - 1] if idx > 0 else None
        next_id = user_reviews[idx + 1] if idx + 1 < len(user_reviews) else None
    except ValueError:
        prev_id = next_id = None
    return render(request, "abstracts/review_detail.html", {
        "event": event,
        "review": review,
        "abstract": review.abstract,
        "prev_id": prev_id,
        "next_id": next_id,
        "active_tab": "reviews",
    })


@login_required
@require_POST
def review_save(request, review_id: int):
    """HTMX-Endpoint: Score + optionalen Kommentar speichern. Rendert Status-Snippet."""
    review = get_object_or_404(
        AbstractReview, pk=review_id, reviewer=request.user)
    raw = request.POST.get("score", "").strip()
    if raw:
        try:
            score = int(raw)
        except ValueError:
            return HttpResponseBadRequest(_("Score must be between 1 and 6"))
        if not 1 <= score <= 6:
            return HttpResponseBadRequest(_("Score must be between 1 and 6"))
        review.score = score
        if review.submitted_at is None:
            review.submitted_at = timezone.now()
    review.comment = request.POST.get("comment", "").strip()
    review.save()
    return render(request, "abstracts/_review_status.html", {"review": review})


@login_required
@require_POST
def review_clear(request, review_id: int):
    """Clear the score — marks the review as still open."""
    review = get_object_or_404(
        AbstractReview, pk=review_id, reviewer=request.user)
    review.score = None
    review.submitted_at = None
    review.save()
    return render(request, "abstracts/_review_status.html", {"review": review})
