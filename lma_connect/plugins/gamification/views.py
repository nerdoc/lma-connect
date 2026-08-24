from django.shortcuts import render

from lma_connect.plugins.core.models import Event

from . import services


def leaderboard(request):
    event = Event.get_active(request)
    rows = services.leaderboard(event, limit=25) if event else []
    # Mark the current user's row if signed in.
    my_pk = request.user.pk if request.user.is_authenticated else None
    return render(request, "gamification/leaderboard.html", {
        "event": event,
        "rows": rows,
        "my_pk": my_pk,
        "active_tab": "more",
    })
