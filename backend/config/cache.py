"""Response caching for the JSON API, backed by Redis.

The catalogue is read far more often than it changes, and every read
otherwise costs a MySQL round trip from Render to Aiven. This module
caches whole JSON responses in Redis (Upstash in production, over TLS)
and is the only place that talks to the cache.

How a cached response is keyed
------------------------------

Three things go into the key, and each one is there to prevent a specific
way of serving the wrong bytes to somebody:

* **The view and its arguments**, including the query string, so
  ``?category=Fiction`` and ``?category=History`` are different entries.
* **The scope.** ``SHARED`` entries are the same for everybody who is
  allowed to see them. ``PER_CALLER`` entries belong to one caller and
  are keyed by their account *and* their session key — an order list
  contains the orders on the account plus guest orders from this browser
  session, so both decide what the answer is. A caller with neither is
  not cached at all, rather than sharing an entry with every other
  anonymous visitor.
* **A version token per namespace** (``books``, ``orders``, …). The view
  declares the namespaces its answer depends on; a write calls
  :func:`invalidate`, which replaces those tokens, and every key built
  from the old token becomes unreachable in one operation. Deleting the
  entries themselves would mean enumerating keys, which Redis cannot do
  cheaply and Upstash discourages.

A missing version token is treated as a *new* token rather than a
default, so an evicted token invalidates its namespace instead of
resurrecting entries cached under it. Upstash evicts under memory
pressure, and stale-but-reachable is the one outcome worth engineering
against.

Failure is a cache miss
-----------------------

Every cache operation is wrapped: a Redis timeout, a dropped connection
or a serialization error degrades to a miss and the view runs as usual.
A cache that is down must slow the API, never break it.

What is not cached
------------------

``GET /api/auth/session/`` (the login check), ``GET /api/csrf/`` and
``/healthz/``. The first must reflect a disabled account or a dropped
token on the very next request; the second issues a token that must be
fresh; the third exists to say whether *this* process is alive, which a
cached answer cannot.
"""

import hashlib
import time
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse

# --- Namespaces --------------------------------------------------------------
#
# One per body of data a response can depend on. Keep the list short: a
# namespace is invalidated as a whole, so a finer split only helps if
# something writes to one part often and the other rarely.
BOOKS = "books"
REVIEWS = "reviews"
CART = "cart"
ORDERS = "orders"
CUSTOMERS = "customers"
BACKUPS = "backups"


# --- Scopes ------------------------------------------------------------------

#: One entry serves every caller allowed to see it.
SHARED = "shared"

#: One entry per caller (account plus browser session).
PER_CALLER = "caller"


# --- Time to live ------------------------------------------------------------
#
# Invalidation is what keeps these answers correct; the TTL is the safety
# net for a write path that forgets to invalidate (the Django admin, a
# management command) and the cap on how long an evicted version token can
# matter. So they are short, and shorter the closer the data is to a
# decision about money or stock.
TTL_CATEGORIES = 600  # The category list changes only when a book does.
TTL_BOOK_DETAIL = 120
TTL_BOOK_LIST = 60  # Search and filter results: the busiest read there is.
TTL_REVIEWS = 60
TTL_ORDER_HISTORY = 30
TTL_ORDER_DETAIL = 60
TTL_CART = 30
TTL_AVAILABILITY = 15  # Read immediately before payment; keep it tight.
TTL_ADMIN = 30  # Administrators watch orders arrive; stay close to live.
TTL_REPORTS = 120  # Aggregates over every paid order, worth more caching.
TTL_BACKUPS = 60

#: Key prefix, so a Redis database shared with something else cannot
#: collide, and so a format change here cannot read old entries.
KEY_PREFIX = "obs:v1"


def _enabled():
    """Whether caching is switched on for this deployment."""
    return getattr(settings, "CACHE_ENABLED", False)


def _namespace_tokens(namespaces):
    """Return the current version token of each namespace.

    Missing tokens are created, which is why this is the only place that
    writes them: a namespace whose token was evicted gets a fresh one and
    so starts empty, rather than inheriting entries cached under the old
    token.
    """
    keys = {name: f"{KEY_PREFIX}:ns:{name}" for name in sorted(namespaces)}

    try:
        found = cache.get_many(list(keys.values()))
    except Exception:
        return None

    missing = {}
    tokens = []

    for name, key in keys.items():
        token = found.get(key)
        if token is None:
            token = _new_token()
            missing[key] = token
        tokens.append(f"{name}={token}")

    if missing:
        try:
            # timeout=None: a version token must outlive the entries that
            # were keyed with it, or those entries become unreachable
            # early. That only costs a cache miss, but there is no reason
            # to expire it at all.
            cache.set_many(missing, timeout=None)
        except Exception:
            return None

    return tokens


def _new_token():
    """A value no previous key can have been built from."""
    return str(time.time_ns())


def invalidate(*namespaces):
    """Make every entry cached from these namespaces unreachable.

    Call it from the write that changed the data, naming what it changed
    — the same discipline as the frontend's ``invalidateQueries``. One
    Redis write per namespace, whatever the number of cached entries.
    """
    if not _enabled() or not namespaces:
        return

    try:
        cache.set_many(
            {
                f"{KEY_PREFIX}:ns:{name}": _new_token()
                for name in namespaces
            },
            timeout=None,
        )
    except Exception:
        # The data is already written; failing the request because the
        # cache could not be told would be the wrong trade. The entries
        # expire on their TTL.
        pass


def _scope_token(request, scope):
    """Return the caller part of the key, or ``None`` not to cache."""
    if scope == SHARED:
        return "shared"

    user = getattr(request, "user", None)
    session_key = getattr(request, "session", None)
    session_key = session_key.session_key if session_key is not None else None

    if user is not None and user.is_authenticated:
        # Both matter: an order history is the account's orders plus this
        # browser's guest orders.
        return f"u{user.pk}:s{session_key or ''}"

    if not session_key:
        # A visitor with no session yet. Every one of them would share a
        # single key, so cache nothing instead and let the view create
        # the session it needs.
        return None

    return f"anon:s{session_key}"


def _response_key(request, view_name, namespaces, scope, args, kwargs):
    """The cache key for this request, or ``None`` not to cache it."""
    scope_token = _scope_token(request, scope)
    if scope_token is None:
        return None

    tokens = _namespace_tokens(namespaces)
    if tokens is None:
        return None

    # The path already carries the view's positional arguments, but
    # kwargs are included as well so a route change cannot silently make
    # two different views share a key.
    parts = [
        view_name,
        scope_token,
        ",".join(tokens),
        request.get_full_path(),
        repr(args),
        repr(sorted(kwargs.items())),
    ]
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()

    # The view name stays readable so entries can be recognized in
    # redis-cli; the digest carries the rest.
    return f"{KEY_PREFIX}:json:{view_name}:{digest}"


def cached_json(ttl, *, namespaces, scope=SHARED):
    """Cache a JSON view's ``200`` responses in Redis.

    ``namespaces`` are the bodies of data the answer depends on, and
    ``scope`` says who may be served the same bytes (see the module
    docstring). Apply it *inside* the authorization decorators, so a
    401 or 403 is never cached and never served:

        @require_GET
        @staff_required_api
        @cached_json(TTL_ADMIN, namespaces=[ORDERS])
        def order_collection(request):
            ...

    Anything other than a ``200 application/json`` response — a 404 for
    an unknown book, a 400 for a bad filter — is passed straight through,
    so an error is never cached in place of an answer.
    """

    def decorate(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method != "GET" or not _enabled():
                return view(request, *args, **kwargs)

            key = _response_key(
                request, view.__name__, namespaces, scope, args, kwargs
            )
            if key is None:
                return view(request, *args, **kwargs)

            try:
                hit = cache.get(key)
            except Exception:
                hit = None

            if hit is not None:
                response = HttpResponse(
                    hit, content_type="application/json"
                )
                response["X-Cache"] = "HIT"
                return response

            response = view(request, *args, **kwargs)

            if response.status_code == 200 and response.get(
                "Content-Type", ""
            ).startswith("application/json"):
                try:
                    cache.set(key, response.content, timeout=ttl)
                except Exception:
                    pass

            response["X-Cache"] = "MISS"
            return response

        return wrapper

    return decorate
