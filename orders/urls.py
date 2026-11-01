from django.urls import path

from . import views

urlpatterns = [
    path(
        "billing-addresses/",
        views.billing_address_list,
        name="billing_address_list",
    ),
    path("checkout/", views.checkout, name="checkout"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
]
