"""Review routes, mounted at /api/reviews/."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.review_collection, name="review_collection"),
    path("<int:pk>/", views.review_detail, name="review_detail"),
]
