"""Signal receivers — award points when the underlying actions happen.

These import program/feedback models lazily inside the receiver bodies so
gamification can be loaded before/after those apps without ordering issues.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ScoreAction
from .services import award


@receiver(post_save, sender="lma_program.Question")
def _on_question(sender, instance, created, **kwargs):
    if not created or instance.asker_id is None:
        return
    award(instance.asker, instance.session.event, ScoreAction.QUESTION_ASKED,
          dedup_key=f"question:{instance.pk}")


@receiver(post_save, sender="lma_program.QuestionUpvote")
def _on_upvote(sender, instance, created, **kwargs):
    if not created:
        return
    # Dedup per (question, user) — NOT per PK: un-voting deletes the row, so
    # a repeated up-vote would get a fresh PK → a new key → double points.
    # This way toggling the up-vote farms nothing.
    award(instance.user, instance.question.session.event, ScoreAction.QUESTION_UPVOTED,
          dedup_key=f"upvote:{instance.question_id}:{instance.user_id}")


@receiver(post_save, sender="lma_program.LivePollResponse")
def _on_poll_response(sender, instance, created, **kwargs):
    # Only the first response per (user, poll) earns points — re-votes don't.
    if not created:
        return
    award(instance.user, instance.poll.session.event, ScoreAction.POLL_VOTED,
          dedup_key=f"poll:{instance.poll_id}:{instance.user_id}")


@receiver(post_save, sender="lma_program.SessionRating")
def _on_session_rating(sender, instance, created, **kwargs):
    # Award once per (session, user); model already enforces uniqueness, but
    # rating updates fire post_save again — dedup on the rating row.
    award(instance.user, instance.session.event, ScoreAction.SESSION_RATED,
          dedup_key=f"rating:{instance.pk}")


@receiver(post_save, sender="lma_feedback.SurveyResponse")
def _on_survey_response(sender, instance, created, **kwargs):
    if instance.user_id is None or instance.submitted_at is None:
        return
    award(instance.user, instance.survey.event, ScoreAction.SURVEY_SUBMITTED,
          dedup_key=f"survey:{instance.survey_id}:{instance.user_id}")


@receiver(post_save, sender="lma_abstracts.AbstractStarVote")
def _on_star_vote(sender, instance, created, **kwargs):
    # A star vote is final — the row is never updated, so `created` is the
    # only path that grants points. Dedup on (abstract, user) mirrors the
    # model's unique_together.
    if not created:
        return
    award(instance.user, instance.abstract.event, ScoreAction.ABSTRACT_STARRED,
          dedup_key=f"star:{instance.abstract_id}:{instance.user_id}")
