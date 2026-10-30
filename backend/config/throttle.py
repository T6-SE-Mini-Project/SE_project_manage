"""Rate limiting for the API, counted in Redis.

Every request is counted against the caller who made it, and a caller who
goes over their allowance for the current minute gets ``429`` with a
``Retry-After`` header. Two layers:

* :class:`RateLimitMiddleware` applies the blanket limits to every route —
  a generous one for reads and a tighter one for writes, because a write
  costs a transaction and a read usually costs a cached lookup.
* :func:`throttle` applies a much tighter limit to the handful of
  endpoints where *attempts* are the thing worth limiting rather than
  volume: signing in, paying for an order, submitting a review.

Who the caller is
-----------------

The Firebase uid when the request carries a valid token, and the client's
IP address otherwise. Keying by uid matters here: it cannot be spoofed,
it follows the customer across networks, and — because this deployment
proxies ``/api/*`` through Vercel — it is the only key that tells two
signed-in customers apart at all.

That proxying is also why ``TRUSTED_PROXY_COUNT`` exists. Every API
request reaches Django from Vercel's edge, so ``REMOTE_ADDR`` is Vercel,
not the customer: left unset, **all anonymous traffic shares one
bucket**. The real address is inside ``X-Forwarded-For``, which a client
can prepend anything it likes to, so the only safe way to read it is to
count back from the right by the number of proxies that are actually in
front of this service. In the Render + Vercel deployment that is
``TRUSTED_PROXY_COUNT=2``.

Counting
--------

A fixed window per minute: ``add`` the counter at 0 if it is absent, then
``incr`` it. Redis' ``INCR`` is atomic and keeps the expiry the ``add``
set, so concurrent requests cannot lose a count or leak a key. A fixed
window lets a caller spend their allowance at the end of one window and
again at the start of the next; that is a known and accepted property —
the limits here exist to stop abuse and runaway clients, not to shape
traffic to the request.

Counters live in the ``throttle`` cache, which is Redis when
``REDIS_URL`` is set and local memory otherwise. Local memory means the
limit applies **per worker process**, so a deployment that cares about
the limit should configure Redis; a limit per worker is still far better
than none.

Failure is an allowed request. If the store cannot be reached the request
goes through: a rate limiter that returns 429 because Redis is down turns
a cache outage into an outage.
"""

import time
from functools import wraps

from django.conf import settings
from django.core.cache import InvalidCacheBackendError, caches

from .http import json_error

#: Cache alias holding the counters. Separate from the response cache so
#: that a deployment without Redis still counts (per process) instead of
#: writing to the dummy backend and never limiting anything.
THROTTLE_CACHE = "throttle"

KEY_PREFIX = "obs:v1:rl"

#: Window every limit is expressed over.
WINDOW_SECONDS = 60

# --- Per-endpoint limits -----------------------------------------------------
#
# These are attempt limits, not volume limits, so they are small. They are
# per caller per minute, and they are deliberately well above what the UI
# can produce by itself: a customer who reaches one is either scripting or
# something has gone wrong.

#: Sign-ins, per *address* — see :data:`ADDRESS`. Firebase handles
#: credential stuffing before a token ever reaches us, but this endpoint
#: creates an account on first use, so it is the one that would be abused
#: to fill the customer table, and each of those attempts arrives with a
#: brand-new uid. Loose enough that a lecture hall behind one address can
#: all sign in at once.
RATE_SIGNIN = 30

#: Card payment attempts per account. The lowest limit in the project:
#: repeated attempts against a payment endpoint are how stolen card
#: numbers get tested, and a genuine customer retries a declined card a
#: handful of times at most.
#:
#: Per account rather than per address on purpose. Paying requires an
#: account, creating accounts is limited by RATE_SIGNIN per address, and
#: the two together bound what one source can attempt — while an address
#: limit here would make a whole school or office share ten attempts a
#: minute if TRUSTED_PROXY_COUNT were ever misconfigured.
RATE_PAYMENT = 10

#: Review submissions and edits, which are public text.
RATE_REVIEW = 10

#: Paths the blanket limits never apply to. The health check must answer
#: the platform even while a flood is in progress — a 429 there is read as
#: "this service is unhealthy" and gets the instance restarted, turning a
#: flood into an outage.
EXEMPT_PREFIXES = ("/healthz/", "/static/")


def throttling_enabled():
    """Whether limits are enforced in this deployment."""
    return getattr(settings, "THROTTLE_ENABLED", False)


#: Short alias, read on every request.
_enabled = throttling_enabled


def _store():
    """The cache holding the counters, or ``None`` when unavailable."""
    try:
        return caches[THROTTLE_CACHE]
    except InvalidCacheBackendError:
        return None


def client_ip(request):
    """The caller's IP address, as far as it can be trusted.

    With ``TRUSTED_PROXY_COUNT`` proxies in front of this service, the
    address they observed is that many entries from the right of
    ``X-Forwarded-For``; everything further left was supplied by the
    client and is worth nothing. With no trusted proxies the header is
    ignored entirely and ``REMOTE_ADDR`` is used.
    """
    trusted = getattr(settings, "TRUSTED_PROXY_COUNT", 0)
    remote_addr = request.META.get("REMOTE_ADDR", "") or "unknown"

    if trusted < 1:
        return remote_addr

    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    chain = [part.strip() for part in forwarded.split(",") if part.strip()]

    if len(chain) < trusted:
        # Fewer hops than configured: the request did not come through the
        # expected proxies, so trust only what the socket says.
        return remote_addr

    return chain[-trusted]


#: Key a limit by *who* is calling: the Firebase uid, or the address when
#: there is no token. Right for limiting what one account may do.
CALLER = "caller"

#: Key a limit by the calling *address*, ignoring any token. Right when the
#: identity itself is what is being created or cycled: a caller who signs
#: up repeatedly presents a new uid every time, so a per-uid limit would
#: give each attempt its own fresh allowance and count nothing.
ADDRESS = "address"


def caller_key(request):
    """A stable identifier for whoever is making this request."""
    identity = getattr(request, "firebase_identity", None)
    if identity is not None:
        return f"uid:{identity.uid}"

    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        # A session user: the Django admin site, which has no Firebase uid.
        return f"user:{user.pk}"

    return f"ip:{client_ip(request)}"


def limit_key(request, by):
    """The identifier a limit of this kind is counted against."""
    if by == ADDRESS:
        return f"ip:{client_ip(request)}"
    return caller_key(request)


def consume(scope, caller, limit):
    """Count one request and report whether it is allowed.

    Returns ``(allowed, remaining, retry_after)``. ``retry_after`` is the
    seconds left in the current window, which is exactly how long the
    caller must wait for their allowance to reset.
    """
    store = _store()
    if store is None:
        return True, limit, 0

    now = time.time()
    window = int(now // WINDOW_SECONDS)
    key = f"{KEY_PREFIX}:{scope}:{caller}:{window}"
    retry_after = WINDOW_SECONDS - int(now % WINDOW_SECONDS)

    try:
        # add() only writes when the key is absent, so it cannot reset a
        # window that is already counting; incr() is then atomic and
        # inherits the expiry add() set. The extra second of timeout keeps
        # the key alive to the very end of its window.
        store.add(key, 0, timeout=WINDOW_SECONDS + 1)
        used = store.incr(key)
    except ValueError:
        # The key expired between add() and incr(): the window has just
        # rolled over, so this request is the first of the new one.
        used = 1
    except Exception:
        # The counter store is unreachable. Allow the request: refusing it
        # would turn a cache outage into an API outage.
        return True, limit, 0

    return used <= limit, max(limit - used, 0), retry_after


def too_many(retry_after, limit):
    """The 429 every refusal returns."""
    response = json_error(
        "Too many requests. Please slow down and try again shortly.",
        429,
        code="rate_limited",
    )
    # Retry-After is the standard way to say how long to wait, and the one
    # a well-behaved client or crawler actually reads.
    response["Retry-After"] = str(max(retry_after, 1))
    response["X-RateLimit-Limit"] = str(limit)
    response["X-RateLimit-Remaining"] = "0"
    return response


def throttle(limit, scope, by=CALLER):
    """Limit one endpoint to ``limit`` requests per minute.

    For endpoints where the attempt itself is what must be limited, on top
    of the blanket limit the middleware already applies:

        @require_POST
        @throttle(RATE_PAYMENT, scope="payment")
        def payment_create(request):
            ...

    ``by`` decides what the limit is counted against — :data:`CALLER` for
    what one account may do, :data:`ADDRESS` when the account itself is
    what the caller is creating. Apply it inside the authorization
    decorators, so an unauthorized caller is refused before being counted.
    """

    def decorate(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not _enabled():
                return view(request, *args, **kwargs)

            allowed, remaining, retry_after = consume(
                scope, limit_key(request, by), limit
            )

            if not allowed:
                return too_many(retry_after, limit)

            response = view(request, *args, **kwargs)
            response["X-RateLimit-Limit"] = str(limit)
            response["X-RateLimit-Remaining"] = str(remaining)
            return response

        return wrapper

    return decorate


class RateLimitMiddleware:
    """Apply the blanket per-caller limits to every request.

    Installed after the authentication middleware, so a signed-in caller
    is counted by their Firebase uid rather than sharing a bucket with
    everybody else behind the same proxy. The cost of that order is that a
    flood of requests carrying *invalid* tokens is refused by the
    authentication middleware before it is counted; those are rejected
    without touching the database, which is the expensive thing worth
    protecting.
    """

    #: Read requests are cheap and a page view makes several of them.
    SAFE_METHODS = frozenset(["GET", "HEAD", "OPTIONS"])

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not _enabled() or request.path.startswith(EXEMPT_PREFIXES):
            return self.get_response(request)

        if request.method in self.SAFE_METHODS:
            limit = settings.THROTTLE_READ_RATE
            scope = "read"
        else:
            # A write costs a transaction, and no legitimate client needs
            # to make many per minute.
            limit = settings.THROTTLE_WRITE_RATE
            scope = "write"

        allowed, remaining, retry_after = consume(
            scope, caller_key(request), limit
        )

        if not allowed:
            return too_many(retry_after, limit)

        response = self.get_response(request)
        response["X-RateLimit-Limit"] = str(limit)
        response["X-RateLimit-Remaining"] = str(remaining)
        return response
