from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from .views import csrf_token, healthz

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthz, name="healthz"),
    path("api/csrf/", csrf_token, name="csrf_token"),
    path("api/auth/", include("accounts.api_urls")),
    path("api/books/", include("books.urls")),
    path("api/cart/", include("cart.urls")),
    path("api/orders/", include("orders.urls")),
    path("api/payments/", include("payments.urls")),
    path("api/reviews/", include("reviews.urls")),
    path("api/admin/", include("administration.urls")),
    # This service serves the JSON API and Django's admin site; the
    # customer-facing pages are the React app on its own origin. Someone
    # who opens the backend's root in a browser wants the admin site.
    path(
        "",
        RedirectView.as_view(url="/admin/", permanent=False),
        name="backend_root",
    ),
]
