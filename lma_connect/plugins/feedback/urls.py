from django.urls import path

from . import views

app_name = "feedback"

urlpatterns = [
    path("", views.survey_list, name="list"),
    path("<slug:slug>/", views.survey_detail, name="detail"),
    path("<slug:slug>/submit/", views.survey_submit, name="submit"),
]
