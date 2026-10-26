from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from .views import csrf_token

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/csrf/", csrf_token, name="csrf_token"),
    path("api/books/", include("books.urls")),
    path("api/cart/", include("cart.urls")),
    path("api/orders/", include("orders.urls")),
    path("api/payments/", include("payments.urls")),
    path("", RedirectView.as_view(pattern_name="register", permanent=False)),
    path("", include("accounts.urls")),
]
