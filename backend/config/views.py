from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET


@require_GET
@ensure_csrf_cookie
def csrf_token(request):
    return JsonResponse({"csrfToken": get_token(request)})


@require_GET
def healthz(request):
    """Liveness probe for the hosting platform's health check.

    Deliberately does not touch the database: Render restarts a service whose
    health check fails, and a brief database blip should not take the whole
    service down with it. Database reachability is surfaced by the API
    endpoints themselves.
    """
    return JsonResponse({"status": "ok"})
