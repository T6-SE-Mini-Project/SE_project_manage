from django.urls import path

from . import views

urlpatterns = [
    path("", views.book_list, name="book_list"),
    path("categories/", views.book_categories, name="book_categories"),
    path("<int:pk>/", views.book_detail, name="book_detail"),
]
