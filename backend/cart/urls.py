from django.urls import path

from . import views

urlpatterns = [
    path("", views.cart_detail, name="cart_detail"),
    path("items/", views.cart_item_add, name="cart_item_add"),
    path(
        "items/<int:pk>/",
        views.cart_item_detail,
        name="cart_item_detail",
    ),
]
