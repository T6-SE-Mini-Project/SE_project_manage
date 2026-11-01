from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from accounts.views import session_status
from .views import csrf_token

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/csrf/", csrf_token, name="csrf_token"),
    path("api/auth/session/", session_status, name="session_status"),
    path("api/books/", include("books.urls")),
    path("api/cart/", include("cart.urls")),
    path("api/", include("orders.urls")),
    path("", RedirectView.as_view(pattern_name="register", permanent=False)),
    path("", include("accounts.urls")),
]
