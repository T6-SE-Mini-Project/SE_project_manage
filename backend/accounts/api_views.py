"""JSON authentication endpoints for the React frontend.

The template-based registration and login pages in ``accounts/views.py``
stay as they are; these endpoints expose the same behaviour over JSON so
the React app can establish a Django session. They are needed by every
feature that must know who the customer is: order history (issue #10),
book reviews (issue #11) and the administrator screens (issues #12 and
#24).

Authentication uses Django's session cookie plus the CSRF token issued
by ``/api/csrf/``; no token scheme is introduced.
"""

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from cart.services import reassign_cart_session
from config.http import json_error, read_json
from orders.services import claim_session_orders

from .forms import CustomerRegistrationForm
from .serializers import first_form_error, serialize_form_errors, serialize_user


@require_GET
def session_detail(request):
    """Report who is signed in, for the frontend's auth state."""
    if not request.user.is_authenticated:
        return JsonResponse({"authenticated": False, "user": None})

    return JsonResponse(
        {
            "authenticated": True,
            "user": serialize_user(request.user),
        }
    )


@require_POST
def session_create(request):
    """Log a customer in and keep their guest cart."""
    data, error_response = read_json(request)
    if error_response is not None:
        return error_response

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if not username or not password:
        return json_error("Username and password are required.", 400)

    # AuthenticationForm applies the project's authentication backends and
    # the inactive-account check, so the JSON endpoint behaves exactly
    # like the login page.
    form = AuthenticationForm(
        request,
        data={"username": username, "password": password},
    )

    if not form.is_valid():
        return json_error(
            first_form_error(form),
            401,
            errors=serialize_form_errors(form),
        )

    # login() cycles the session key, and the cart and orders are keyed by
    # it, so remember the old key and move the cart across.
    previous_session_key = request.session.session_key

    login(request, form.get_user())

    reassign_cart_session(
        previous_session_key,
        request.session.session_key,
        request.user,
    )
    claim_session_orders(
        previous_session_key,
        request.session.session_key,
        request.user,
    )

    return JsonResponse(
        {
            "authenticated": True,
            "user": serialize_user(request.user),
        }
    )


@require_POST
def session_delete(request):
    """Log the current customer out."""
    logout(request)
    return JsonResponse({"authenticated": False, "user": None})


@require_POST
def account_create(request):
    """Register a customer and sign them in.

    Reuses ``CustomerRegistrationForm`` so password validation, the
    confirmation field and the unique-email rule behave identically to
    the registration page.
    """
    data, error_response = read_json(request)
    if error_response is not None:
        return error_response

    form = CustomerRegistrationForm(
        data={
            "username": str(data.get("username", "")).strip(),
            "email": str(data.get("email", "")).strip(),
            "password1": str(data.get("password1", "")),
            "password2": str(data.get("password2", "")),
        }
    )

    if not form.is_valid():
        return json_error(
            first_form_error(form),
            400,
            errors=serialize_form_errors(form),
        )

    user = form.save()

    previous_session_key = request.session.session_key

    # Authenticate so the configured backend is attached to the session.
    authenticated = authenticate(
        request,
        username=form.cleaned_data["username"],
        password=form.cleaned_data["password1"],
    )
    login(request, authenticated if authenticated is not None else user)

    reassign_cart_session(
        previous_session_key,
        request.session.session_key,
        request.user,
    )
    claim_session_orders(
        previous_session_key,
        request.session.session_key,
        request.user,
    )

    return JsonResponse(
        {
            "authenticated": True,
            "user": serialize_user(request.user),
        },
        status=201,
    )
