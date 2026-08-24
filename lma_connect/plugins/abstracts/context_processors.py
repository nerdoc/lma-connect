"""Global context — exposes review-counts (open / total) for the logged-in
user, used by the topbar to show the Reviews entry-point with badge."""

from django.db.models import Count, Q

from .models import AbstractReview


def review_counts(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"my_reviews_total": 0, "my_reviews_open": 0}
    # Both numbers in ONE query — this runs on every request a reviewer makes.
    agg = AbstractReview.objects.filter(reviewer=user).aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(score__isnull=True)),
    )
    return {
        "my_reviews_total": agg["total"],
        "my_reviews_open": agg["open"],
    }
