from django.urls import path

from . import views

app_name = "expo"

urlpatterns = [
    path("s/<slug:slug>/", views.booth_stop, name="booth_stop"),
    path("p/<slug:slug>/", views.poster_stop, name="poster_stop"),
]
