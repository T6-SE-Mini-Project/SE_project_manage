"""Shared helpers for the JSON API views.

Every API app in this project returns JSON (never HTML) and is consumed
by the React frontend, so request parsing and the authorization checks
live here instead of being repeated in each ``views.py``.
"""

import json
from functools import wraps

from django.http import JsonResponse


def json_error(message, status, **extra):
    """Return a JSON error response in the shape the frontend expects.

    The frontend's ``ApiError`` reads the ``error`` key, so every failure
    response in the API uses it.
    """
    return JsonResponse({"error": message, **extra}, status=status)


def read_json(request):
    """Parse a JSON request body.

    Returns ``(data, error_response)``. Exactly one of the two is
    non-``None``, so callers can do::

        data, error = read_json(request)
        if error is not None:
            return error
    """
    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, json_error("Invalid JSON body.", 400)

    if not isinstance(data, dict):
        return None, json_error("JSON body must be an object.", 400)

    return data, None


def login_required_api(view):
    """Reject anonymous callers with 401 instead of an HTML redirect.

    ``django.contrib.auth.decorators.login_required`` redirects to the
    login page, which a fetch() caller cannot use.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return json_error(
                "You must be logged in to perform this action.",
                401,
            )
        return view(request, *args, **kwargs)

    return wrapper


def staff_required_api(view):
    """Restrict a view to administrators (``is_staff``).

    Anonymous callers get 401 so the frontend can send them to the login
    page; authenticated customers get 403 because logging in again would
    not help. This is the single gate for every administrator-only
    operation (issues #12 and #24).
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return json_error(
                "You must be logged in as an administrator.",
                401,
            )
        if not request.user.is_staff:
            return json_error(
                "Administrator privileges are required for this operation.",
                403,
            )
        return view(request, *args, **kwargs)

    return wrapper
