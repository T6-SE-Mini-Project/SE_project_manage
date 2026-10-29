"""JSON authentication routes, mounted at /api/auth/."""

from django.urls import path

from . import api_views

urlpatterns = [
    path("session/", api_views.session_detail, name="api_session_detail"),
    path("signin/", api_views.session_create, name="api_signin"),
    path("logout/", api_views.session_delete, name="api_logout"),
]
