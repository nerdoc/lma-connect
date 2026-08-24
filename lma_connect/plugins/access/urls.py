from django.urls import path

from . import ops_views, views

app_name = "access"

urlpatterns = [
    path("t/<str:token>/", views.redeem, name="redeem"),
    path("me/", views.me, name="me"),

    # Operations Team frontend
    path("ops/", ops_views.dashboard, name="ops_dashboard"),
    path("ops/abstracts/", ops_views.abstracts_results, name="ops_abstracts"),
    path("ops/abstracts/<int:abstract_id>/", ops_views.abstract_results_detail, name="ops_abstract_detail"),
    path("ops/abstracts/<int:abstract_id>/toggle-publish/", ops_views.abstract_toggle_publish,
         name="ops_abstract_toggle_publish"),
    path("ops/stars/", ops_views.abstract_star_ranking, name="ops_abstract_stars"),
    path("ops/stars/<int:abstract_id>/audience-award/", ops_views.abstract_set_audience_award,
         name="ops_abstract_audience_award"),
    path("ops/tokens/", ops_views.tokens_list, name="ops_tokens"),
    path("ops/tokens/create/", ops_views.tokens_create, name="ops_tokens_create"),
    path("ops/tokens/<int:token_id>/", ops_views.token_detail, name="ops_token_detail"),
    path("ops/tokens/<int:token_id>/qr.png", ops_views.token_qr_image, name="ops_token_qr"),
    path("ops/tokens/<int:token_id>/print/", ops_views.token_print, name="ops_token_print"),
    path("ops/tokens/<int:token_id>/toggle/", ops_views.token_toggle_active, name="ops_token_toggle"),
    path("ops/users/", ops_views.users_list, name="ops_users"),
    path("ops/users/<int:user_id>/", ops_views.user_detail, name="ops_user_detail"),
    path("ops/users/<int:user_id>/update-profile/", ops_views.user_update_profile, name="ops_user_update_profile"),
    path("ops/users/<int:user_id>/reset-password/", ops_views.user_reset_password, name="ops_user_reset_pw"),
    path("ops/users/<int:user_id>/unlock/", ops_views.user_unlock_axes, name="ops_user_unlock"),
    path("ops/users/<int:user_id>/new-token/", ops_views.user_new_token, name="ops_user_new_token"),
]
