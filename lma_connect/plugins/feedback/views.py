from django.contrib import messages
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from lma_connect.plugins.core.models import Event
from lma_connect.plugins.core.utils import client_ip

from .models import EventSurvey, SurveyAnswer, SurveyChoice, SurveyResponse

# Cap anonymous submissions per IP as well: a session key alone is trivially
# bypassed by clearing cookies or opening a private window, which would make
# ballot stuffing free. Best effort — LocMemCache is process-local; move to
# Redis or a file cache in a multi-worker setup.
_ANON_IP_MAX = 3          # anonymous submissions per IP and survey
_ANON_IP_WINDOW = 3600    # window in seconds


def _submitted_key(survey) -> str:
    """Session key marking that this survey was already submitted
    anonymously in this browser session — stops casual double voting."""
    return f"fb_submitted_{survey.pk}"


def survey_list(request):
    event = Event.get_active(request)
    surveys = []
    if event:
        surveys = event.surveys.filter(is_published=True).order_by("-created_at")
    return render(request, "feedback/list.html", {
        "event": event, "surveys": surveys, "active_tab": "feedback",
    })


def survey_detail(request, slug):
    event = Event.get_active(request)
    survey = get_object_or_404(
        EventSurvey.objects.prefetch_related("questions__choices"),
        slug=slug, is_published=True,
    )
    questions = survey.questions.order_by("order")

    user = request.user if request.user.is_authenticated else None
    already_submitted = (
        user is not None
        and SurveyResponse.objects.filter(
            survey=survey, user=user, submitted_at__isnull=False
        ).exists()
    ) or (user is None and request.session.get(_submitted_key(survey)))
    return render(request, "feedback/detail.html", {
        "event": event,
        "survey": survey,
        "questions": questions,
        "already_submitted": already_submitted,
        "active_tab": "feedback",
    })


@require_POST
def survey_submit(request, slug):
    """Persistiert SurveyResponse + 1×SurveyAnswer pro Frage (Multi-Choice = N)."""
    survey = get_object_or_404(
        EventSurvey.objects.prefetch_related("questions__choices"),
        slug=slug, is_published=True,
    )
    user = request.user if request.user.is_authenticated else None
    if user is None and not survey.allow_anonymous:
        messages.error(request, _("Sign-in required."))
        return redirect("feedback:detail", slug=slug)

    # Anonymous submission: allow one per browser session. Signed-in users
    # are already bounded by the one-response constraint (get_or_create).
    if user is None and request.session.get(_submitted_key(survey)):
        messages.info(request, _("You have already submitted this survey."))
        return redirect("feedback:detail", slug=slug)

    # Additional per-IP cap against ballot stuffing via fresh sessions.
    ip_key = None
    if user is None:
        ip_key = f"fb_ip:{survey.pk}:{client_ip(request)}"
        if (cache.get(ip_key) or 0) >= _ANON_IP_MAX:
            messages.info(request, _("Too many submissions from your network for this survey."))
            return redirect("feedback:detail", slug=slug)

    with transaction.atomic():
        # At most one response per user (a constraint on the model).
        # Anonymous submissions always create a new row.
        if user is not None:
            response, _created = SurveyResponse.objects.get_or_create(
                survey=survey, user=user,
                defaults={"submitted_at": timezone.now()},
            )
            # Clear the previous answers — users may submit again
            response.answers.all().delete()
            response.submitted_at = timezone.now()
            response.save(update_fields=["submitted_at"])
        else:
            response = SurveyResponse.objects.create(
                survey=survey, user=None, submitted_at=timezone.now(),
            )

        for q in survey.questions.all():
            field = f"q_{q.id}"
            if q.type == "yes_no":
                raw = request.POST.get(field)
                if raw in {"yes", "no"}:
                    SurveyAnswer.objects.create(
                        response=response, question=q,
                        value_bool=(raw == "yes"),
                    )
            elif q.type == "likert_5":
                raw = request.POST.get(field)
                if raw:
                    try:
                        v = int(raw)
                        if 1 <= v <= 5:
                            SurveyAnswer.objects.create(
                                response=response, question=q, value_int=v,
                            )
                    except ValueError:
                        pass
            elif q.type == "open_text":
                raw = (request.POST.get(field) or "").strip()
                if raw:
                    SurveyAnswer.objects.create(
                        response=response, question=q, value_text=raw[:8000],
                    )
            elif q.type == "single_choice":
                raw = request.POST.get(field)
                if raw:
                    choice = SurveyChoice.objects.filter(id=raw, question=q).first()
                    if choice:
                        SurveyAnswer.objects.create(
                            response=response, question=q, choice=choice,
                        )
            elif q.type == "multi_choice":
                raw_ids = request.POST.getlist(field)
                valid = SurveyChoice.objects.filter(id__in=raw_ids, question=q)
                for c in valid:
                    SurveyAnswer.objects.create(
                        response=response, question=q, choice=c,
                    )

    if user is None:
        request.session[_submitted_key(survey)] = True
        if ip_key is not None:
            cache.set(ip_key, (cache.get(ip_key) or 0) + 1, _ANON_IP_WINDOW)

    messages.success(request, _("Thanks for your feedback!"))
    return redirect("feedback:detail", slug=slug)
