from django.urls import path, re_path

from . import views

app_name = "qr"

urlpatterns = [
    path("", views.free, name="free"),
    path("print/", views.print_sheet, name="print"),
    re_path(r"^(?P<path>.+)/?$", views.image, name="image"),
]
