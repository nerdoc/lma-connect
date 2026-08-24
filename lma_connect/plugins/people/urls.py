from django.urls import path

from . import views

app_name = "people"

urlpatterns = [
    path("", views.speaker_list, name="list"),
    path("<str:username>/", views.speaker_detail, name="detail"),
]
