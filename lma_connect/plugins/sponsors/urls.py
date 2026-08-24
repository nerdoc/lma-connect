from django.urls import path

from . import views

app_name = "sponsors"

urlpatterns = [
    path("", views.sponsor_list, name="list"),
    path("<slug:slug>/", views.sponsor_detail, name="detail"),
]
