
from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.register, name="register"),
    path(
        "register/success/",
        views.register_success,
        name="register_success",
    ),
    path("login/", views.customer_login, name="customer_login"),
    path("login/success/", views.login_success, name="login_success"),
]
