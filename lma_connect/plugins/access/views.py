import os
import secrets

from django.contrib.auth import get_user_model, login
from django.core.cache import cache
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from lma_connect.plugins.core.utils import client_ip

from .models import AccessToken

User = get_user_model()


# Brute-force protection for tokens. Tokens are random URL-safe strings, so
# guessing one is expensive in theory — but it costs an attacker nothing but
# time. We count 404 attempts per IP and lock the IP out once it exceeds the
# quota within the window.
# Cache backend: LocMemCache by default, which is process-local. In
# multi-worker setups (gunicorn -w >1) move this to a file or Redis cache.
_TOKEN_WINDOW_SECONDS = int(os.environ.get("DJANGO_TOKEN_WINDOW_SECONDS", "60"))
_TOKEN_MAX_FAILS = int(os.environ.get("DJANGO_TOKEN_MAX_FAILS", "20"))
_TOKEN_LOCKOUT_SECONDS = int(os.environ.get("DJANGO_TOKEN_LOCKOUT_SECONDS", str(15 * 60)))


def _is_locked_out(ip: str) -> bool:
    return bool(cache.get(f"token_lockout:{ip}"))


def _record_invalid_token(ip: str) -> None:
    counter_key = f"token_fails:{ip}"
    fails = (cache.get(counter_key) or 0) + 1
    cache.set(counter_key, fails, _TOKEN_WINDOW_SECONDS)
    if fails >= _TOKEN_MAX_FAILS:
        cache.set(f"token_lockout:{ip}", True, _TOKEN_LOCKOUT_SECONDS)


@require_http_methods(["GET", "POST"])
def redeem(request, token: str):
    """Redeem a token. First use: nickname setup. Later uses: straight login."""
    ip = client_ip(request)
    if _is_locked_out(ip):
        return HttpResponse(
            "Too many invalid token attempts from your network. "
            "Please wait ~15 minutes and try again.",
            status=429,
            content_type="text/plain; charset=utf-8",
        )

    try:
        access = AccessToken.objects.get(token=token, is_active=True)
    except AccessToken.DoesNotExist:
        _record_invalid_token(ip)
        raise Http404("Token not found") from None

    # Already redeemed → log in and go home
    if access.user is not None:
        access.last_seen_at = timezone.now()
        access.save(update_fields=["last_seen_at", "updated_at"])
        access.user.backend = "django.contrib.auth.backends.ModelBackend"
        login(request, access.user)
        return redirect("core:home")

    # First redemption: pick a nickname
    if request.method == "POST":
        nickname = (request.POST.get("nickname") or "").strip()
        if 2 <= len(nickname) <= 60:
            # Eindeutigen User anlegen — username = nickname-slug + suffix falls Kollision
            base = "".join(c for c in nickname.lower().replace(" ", "_") if c.isalnum() or c == "_")[:20] or "user"
            username = base
            counter = 1
            while User.objects.filter(username=username).exists():
                counter += 1
                username = f"{base}_{counter}"
            user = User.objects.create_user(
                username=username,
                first_name=nickname[:30],
                password=secrets.token_urlsafe(32),  # never used to log in — the token is the credential
            )
            access.user = user
            access.redeemed_at = timezone.now()
            access.last_seen_at = timezone.now()
            access.save()
            # Carry the token's group/category straight into the event
            # profile, so the attendee is filed correctly from the first
            # second (delegate, speaker, industry …) without ops having to
            # follow up.
            from lma_connect.plugins.people.models import PersonProfile
            PersonProfile.objects.get_or_create(
                user=user, event=access.event,
                defaults={"category": access.category},
            )
            user.backend = "django.contrib.auth.backends.ModelBackend"
            login(request, user)
            return redirect("core:home")

    return render(request, "access/setup_nickname.html", {
        "access": access, "event": access.event,
    })


def me(request):
    """Profile page: nickname edit + gamification stats (score, badges, history)."""
    if not request.user.is_authenticated:
        return redirect("core:welcome")
    if request.method == "POST":
        new_name = (request.POST.get("nickname") or "").strip()
        if 2 <= len(new_name) <= 60:
            request.user.first_name = new_name[:30]
            request.user.save(update_fields=["first_name"])
            return redirect("access:me")

    # Gamification stats for the active event (if any)
    from lma_connect.plugins.core.models import Event
    from lma_connect.plugins.gamification import services as gam
    event = Event.get_active(request)
    stats = gam.user_stats(request.user, event) if event else None

    return render(request, "access/me.html", {
        "u": request.user, "event": event, "stats": stats,
    })
