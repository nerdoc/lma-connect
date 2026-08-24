from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, render

from lma_connect.plugins.core.models import Event

from .models import PersonProfile

User = get_user_model()


def speaker_list(request):
    event = Event.get_active(request)
    speakers = []
    if event:
        speakers = (
            PersonProfile.objects.filter(event=event, profile_public=True,
                                         speaker__isnull=False)
            .select_related("user", "speaker")
            .order_by("-speaker__is_keynote", "user__last_name")
        )
    return render(request, "people/speaker_list.html", {
        "event": event, "speakers": speakers, "active_tab": "program",
    })


def speaker_detail(request, username: str):
    event = Event.get_active(request)
    user = get_object_or_404(User, username=username)
    profile = get_object_or_404(
        PersonProfile.objects.select_related("user", "speaker"),
        user=user, event=event, profile_public=True,
    )
    sessions = []
    if hasattr(profile, "speaker"):
        sessions = list(
            profile.speaker.session_assignments.filter(session__is_published=True)
            .select_related("session", "session__track", "session__room")
            .order_by("session__starts_at")
        )
    return render(request, "people/speaker_detail.html", {
        "event": event, "profile": profile, "sessions": sessions,
        "active_tab": "program",
    })
