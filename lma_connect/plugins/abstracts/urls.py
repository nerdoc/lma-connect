from django.urls import path

from . import views

app_name = "abstracts"

urlpatterns = [
    path("", views.abstract_list, name="list"),
    path("reviews/", views.review_list, name="review_list"),
    path("reviews/<int:review_id>/", views.review_detail, name="review_detail"),
    path("reviews/<int:review_id>/save/", views.review_save, name="review_save"),
    path("reviews/<int:review_id>/clear/", views.review_clear, name="review_clear"),
    path("<slug:slug>/", views.abstract_detail, name="detail"),
]
