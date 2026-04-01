from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    path("onboarding/", views.onboarding, name="onboarding"),
    path("explore/", views.explore, name="explore"),
    path("library/", views.library, name="library"),
    path("content/<int:content_id>/", views.content_detail, name="content_detail"),
    path("interact/<int:content_id>/<str:action>/", views.interact, name="interact"),
]
