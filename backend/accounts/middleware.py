"""Authentication middleware for Firebase ID tokens (JWTs).

This is where the API learns who is calling. The React app sends the
Firebase ID token as ``Authorization: Bearer <jwt>`` on every request;
this middleware verifies it, resolves the Django user behind the Firebase
uid, and assigns ``request.user``. From that point on every view,
decorator and query in the project works unchanged — ``login_required_api``,
``staff_required_api`` and the per-customer query scoping all just read
``request.user``.

Order matters. It is installed *after*
``django.contrib.auth.middleware.AuthenticationMiddleware``, so:

* a request with a bearer token is identified by the token, overriding
  whatever the session said;
* a request without one keeps the session user, which is what the Django
  admin site at ``/admin/`` runs on.

The session cookie is still created and used, but only as the key for a
*guest* cart and guest orders (see ``accounts/api_views.py``); it no
longer authenticates anybody on the JSON API.

A token that is present but unusable — expired, forged, issued for
another project — ends the request with 401 rather than quietly
continuing as an anonymous caller, so the frontend can tell "your sign-in
lapsed, refresh it" apart from "you are not signed in".
"""

from config.http import json_error

from .firebase import FirebaseAuthError, bearer_token, verify_id_token
from .services import identity_for_claims

# Session key under which the signed-in Firebase uid is remembered. The
# session itself no longer authenticates anybody; this records *whose*
# guest cart and guest orders the session holds, so they cannot follow one
# browser from one customer to the next.
SESSION_UID_KEY = "firebase_uid"


class FirebaseAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = bearer_token(request)

        if token is None:
            # No token: leave request.user as AuthenticationMiddleware set
            # it, and record that no Firebase identity was presented.
            request.firebase_claims = None
            request.firebase_identity = None
            return self.get_response(request)

        try:
            claims = verify_id_token(token)
        except FirebaseAuthError as exc:
            return json_error(str(exc), 401, code="invalid_token")

        identity = identity_for_claims(claims)

        if not identity.user.is_active:
            # An administrator has disabled this customer. Firebase still
            # issues them tokens, so the refusal has to happen here, and
            # 403 says plainly that signing in again will not help.
            return json_error(
                "This account has been disabled. Please contact support.",
                403,
                code="account_disabled",
            )

        session_uid = request.session.get(SESSION_UID_KEY, "")
        if session_uid and session_uid != identity.uid:
            # This browser's session belongs to a different customer who
            # never logged out. Dropping it here, rather than only in the
            # sign-in endpoint, means no request can reach a cart that is
            # not this customer's.
            request.session.flush()

        request.firebase_claims = claims
        request.firebase_identity = identity
        request.user = identity.user

        return self.get_response(request)

