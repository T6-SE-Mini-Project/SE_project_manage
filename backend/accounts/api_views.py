"""JSON authentication endpoints for the React frontend.

Identity comes from Firebase. The browser signs in with the Firebase SDK
(email/password or Google), and
``accounts.middleware.FirebaseAuthenticationMiddleware`` verifies the ID
token on every request, so there is no password to post here and no
Django session to establish:

===========================  =================================================
``GET  /api/auth/session/``  The login check. Reports who the token
                             identifies, or ``{authenticated: false}``.
``POST /api/auth/signin/``   Called once, right after a Firebase sign-in:
                             links the Firebase uid to a Django user and
                             hands the guest cart and guest orders over.
``POST /api/auth/logout/``   Forgets the browser session. The Firebase
                             sign-out itself happens in the browser.
===========================  =================================================

The session cookie survives this change, but only as the key for a
*guest* cart and guest orders (``cart.models.Cart.session_key``,
``orders.models.Order.session_key``). It no longer authenticates anyone.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from cart.services import reassign_cart_session
from config.http import json_error
from orders.services import claim_session_orders

from .middleware import SESSION_UID_KEY
from .serializers import serialize_user
from .services import record_sign_in


def _identity(request):
    """The Firebase identity the middleware resolved, or ``None``."""
    return getattr(request, "firebase_identity", None)


@require_GET
def session_detail(request):
    """Report who is signed in, for the frontend's auth state."""
    if not request.user.is_authenticated:
        return JsonResponse({"authenticated": False, "user": None})

    return JsonResponse(
        {
            "authenticated": True,
            "user": serialize_user(request.user, _identity(request)),
        }
    )


@require_POST
def session_create(request):
    """Register a Firebase sign-in and keep the customer's guest work.

    The middleware has already verified the token and, on a first
    sign-in, created the Django user. What is left is the handover that
    the old password login did: the cart and any orders placed as a guest
    in this browser session belong to the customer now.
    """
    identity = _identity(request)

    if identity is None:
        return json_error(
            "A Firebase sign-in token is required.",
            401,
            code="token_required",
        )

    previous_uid = request.session.get(SESSION_UID_KEY, "")
    previous_session_key = request.session.session_key

    if previous_uid and previous_uid != identity.uid:
        # A different customer used this browser and did not log out.
        # Their guest cart must not follow the new one, so the session is
        # discarded rather than carried over. (The middleware does the
        # same, so this is belt and braces for a session written since.)
        request.session.flush()
        previous_session_key = None
    else:
        # Cycle the key for the same reason django.contrib.auth.login()
        # does: a session id that an attacker fixed before sign-in must
        # not survive it.
        request.session.cycle_key()

    request.session[SESSION_UID_KEY] = identity.uid

    if previous_session_key:
        reassign_cart_session(
            previous_session_key,
            request.session.session_key,
            identity.user,
        )
        claim_session_orders(
            previous_session_key,
            request.session.session_key,
            identity.user,
        )

    record_sign_in(identity)

    return JsonResponse(
        {
            "authenticated": True,
            "user": serialize_user(identity.user, identity),
        }
    )


@require_POST
def session_delete(request):
    """Forget this browser's session.

    Signing out of Firebase happens in the browser, which is what stops
    the SDK sending an ID token. This endpoint drops the session that
    keyed the cart, so the next customer on this browser does not inherit
    it.
    """
    request.session.flush()
    return JsonResponse({"authenticated": False, "user": None})
