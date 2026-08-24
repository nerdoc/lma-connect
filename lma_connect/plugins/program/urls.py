from django.urls import path

from . import views

app_name = "program"

urlpatterns = [
    path("", views.session_list, name="list"),
    # HTMX-Endpoints + ID-routes (must come before the catch-all <slug>!)
    path("polls/<int:poll_id>/vote/", views.poll_vote, name="poll_vote"),
    # Poll-Projektion (Chair-only): Vollbild-Ansicht + Live-Refresh-Partial
    path("polls/<int:poll_id>/project/", views.poll_project, name="poll_project"),
    path("polls/<int:poll_id>/project/results/", views.poll_project_results, name="poll_project_results"),
    path("polls/<int:poll_id>/toggle/", views.poll_toggle_active, name="poll_toggle_active"),
    path("questions/<int:question_id>/upvote/", views.question_upvote, name="question_upvote"),
    # Chair moderation — ID routes
    path("questions/<int:question_id>/chair-star/", views.chair_question_star, name="chair_question_star"),
    path("questions/<int:question_id>/chair-approve/", views.chair_question_approve, name="chair_question_approve"),
    path("questions/<int:question_id>/chair-answered/", views.chair_question_answered, name="chair_question_answered"),
    path("questions/<int:question_id>/chair-delete/", views.chair_question_delete, name="chair_question_delete"),
    # Slug routes
    path("<slug:slug>/questions/", views.question_create, name="question_create"),
    path("<slug:slug>/rate/", views.session_rate, name="session_rate"),
    path("<slug:slug>/chair/", views.chair_panel, name="chair_panel"),
    path("<slug:slug>/chair/add-question/", views.chair_question_add, name="chair_question_add"),
    path("<slug:slug>/chair/speaker/<int:speaker_id>/notes/", views.chair_speaker_notes, name="chair_speaker_notes"),
    # Beamer-Screen (Chair-gesteuerter Umschalter)
    path("<slug:slug>/screen/", views.session_screen, name="session_screen"),
    path("<slug:slug>/screen/content/", views.screen_content, name="screen_content"),
    path("<slug:slug>/screen/source/", views.screen_set_source, name="screen_set_source"),
    path("<slug:slug>/", views.session_detail, name="detail"),
]
