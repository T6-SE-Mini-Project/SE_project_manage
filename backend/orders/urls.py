from django.urls import path

from . import views

urlpatterns = [
    path("", views.order_collection, name="order_collection"),
    path("availability/", views.order_availability, name="order_availability"),
    path("<int:pk>/", views.order_detail, name="order_detail"),
]
