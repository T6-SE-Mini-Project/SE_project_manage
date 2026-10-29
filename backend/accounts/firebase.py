"""Verification of Firebase ID tokens.

The React app signs customers in with Firebase (email/password or Google)
and sends the resulting **ID token** — an RS256 JWT minted by Google — as
``Authorization: Bearer <token>`` on every API call.
``accounts.middleware.FirebaseAuthenticationMiddleware`` calls
:func:`verify_id_token` here, and only a token that passes every check
below is allowed to identify a caller.

Why this and not the Firebase Admin SDK
---------------------------------------

Firebase ID tokens are signed with Google's *public* certificates, so
verifying one needs nothing secret: the certificates are fetched over
HTTPS and the project id pins the audience. That keeps the deployment to
a single public environment variable (``FIREBASE_PROJECT_ID``) with no
service-account JSON to mount as a secret file, rotate, or leak — and it
keeps ``requirements.txt`` to PyJWT instead of the Admin SDK's gRPC and
Cloud API dependency tree.

What is checked, and why each check matters
-------------------------------------------

================  ===========================================================
Claim / header    Rejected unless
================  ===========================================================
``alg``           ``RS256``. Refusing anything else is what stops the
                  classic "alg: none" and HMAC-confusion forgeries.
``kid``           Names one of Google's current signing certificates.
``iss``           ``https://securetoken.google.com/<project id>``.
``aud``           The project id — a token minted for a *different*
                  Firebase project is signed by the same Google key, so
                  the audience is the only thing that rejects it.
``exp``/``iat``   Within ``FIREBASE_TOKEN_LEEWAY`` seconds of now.
``sub``           Non-empty; it is the Firebase uid stored in the database.
``auth_time``     Not in the future: the user really has signed in.
================  ===========================================================

Every failure raises :class:`FirebaseAuthError` with a message safe to
return to the browser; the caller turns that into a 401.
"""

import json
import threading
import time
import urllib.error
import urllib.request

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.x509 import load_pem_x509_certificate

from config import env

ISSUER_PREFIX = "https://securetoken.google.com/"

# Fallback cache lifetime for Google's certificates when the response
# carries no usable Cache-Control header. The keys rotate daily, so an
# hour is cautious without hammering the endpoint.
DEFAULT_CACHE_SECONDS = 3600

# Floor on how often the certificates may be refetched. Without it an
# unknown "kid" in a forged token would let a caller drive one outbound
# HTTPS request per request.
MIN_REFETCH_SECONDS = 60


class FirebaseAuthError(Exception):
    """An ID token could not be verified. The message is user-facing."""


class _PublicKeyCache:
    """Google's token-signing certificates, fetched once and cached.

    Shared by every request in a worker process, so the certificates are
    fetched roughly once a day rather than once a request. A lock keeps
    concurrent requests from each starting their own fetch on a cold
    cache.
    """

    def __init__(self):
        self._keys = {}
        self._expires_at = 0.0
        self._last_fetch = 0.0
        self._lock = threading.Lock()

    def get(self, kid):
        """Return the public key for ``kid``, refetching when unknown."""
        key = self._lookup(kid)
        if key is not None:
            return key

        # An unknown kid means either the keys have just rotated or the
        # token is forged. Refetch, but not more often than
        # MIN_REFETCH_SECONDS, so the latter cannot be used as a lever.
        with self._lock:
            key = self._lookup(kid)
            if key is not None:
                return key
            if time.monotonic() - self._last_fetch < MIN_REFETCH_SECONDS:
                raise FirebaseAuthError("The sign-in token is not recognized.")
            self._refresh()

        key = self._lookup(kid)
        if key is None:
            raise FirebaseAuthError("The sign-in token is not recognized.")
        return key

    def _lookup(self, kid):
        if time.monotonic() >= self._expires_at:
            return None
        return self._keys.get(kid)

    def _refresh(self):
        certificates, max_age = _fetch_certificates()

        keys = {}
        for kid, pem in certificates.items():
            try:
                certificate = load_pem_x509_certificate(
                    pem.encode(), default_backend()
                )
            except ValueError:
                # One unparseable certificate must not discard the rest.
                continue
            keys[kid] = certificate.public_key()

        if not keys:
            raise FirebaseAuthError(
                "Sign-in is temporarily unavailable. Please try again."
            )

        self._keys = keys
        self._expires_at = time.monotonic() + max_age
        self._last_fetch = time.monotonic()

    def clear(self):
        """Drop the cached keys. Used by the tests."""
        with self._lock:
            self._keys = {}
            self._expires_at = 0.0
            self._last_fetch = 0.0


def _fetch_certificates():
    """Return ``({kid: pem}, cache_seconds)`` from Google's endpoint."""
    try:
        with urllib.request.urlopen(
            env.FIREBASE_PUBLIC_KEYS_URL, timeout=10
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
            max_age = _cache_seconds(response.headers.get("Cache-Control", ""))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FirebaseAuthError(
            "Sign-in could not be verified right now. Please try again."
        ) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise FirebaseAuthError(
            "Sign-in could not be verified right now. Please try again."
        ) from exc

    if not isinstance(payload, dict):
        raise FirebaseAuthError(
            "Sign-in could not be verified right now. Please try again."
        )

    return payload, max_age


def _cache_seconds(cache_control):
    """Read ``max-age`` out of a Cache-Control header."""
    for directive in cache_control.split(","):
        name, _, value = directive.strip().partition("=")
        if name.lower() == "max-age":
            try:
                return max(int(value), MIN_REFETCH_SECONDS)
            except ValueError:
                break
    return DEFAULT_CACHE_SECONDS


public_keys = _PublicKeyCache()


def verify_id_token(token):
    """Return the verified claims of a Firebase ID token.

    Raises :class:`FirebaseAuthError` when the token is missing, damaged,
    expired, signed by the wrong key or minted for another project.
    """
    project_id = env.FIREBASE_PROJECT_ID
    if not project_id:
        # A misconfigured server must not accept tokens with an unchecked
        # audience, which is exactly what skipping this would do.
        raise FirebaseAuthError(
            "Authentication is not configured on the server."
        )

    if not token:
        raise FirebaseAuthError("A sign-in token is required.")

    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise FirebaseAuthError("The sign-in token is malformed.") from exc

    if header.get("alg") != "RS256":
        # Pinning the algorithm is also enforced by decode() below; doing
        # it here as well keeps an unexpected token from reaching the key
        # cache at all.
        raise FirebaseAuthError("The sign-in token uses an unsupported signature.")

    kid = header.get("kid")
    if not kid:
        raise FirebaseAuthError("The sign-in token is missing its key id.")

    key = public_keys.get(kid)

    try:
        claims = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            audience=project_id,
            issuer=f"{ISSUER_PREFIX}{project_id}",
            leeway=env.FIREBASE_TOKEN_LEEWAY,
            options={"require": ["exp", "iat", "aud", "iss", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        # The frontend refreshes ID tokens, so this is a stale request
        # rather than a lie; say so, so the UI can retry instead of
        # sending the customer back to the login page.
        raise FirebaseAuthError("Your sign-in has expired. Please try again.") from exc
    except jwt.InvalidAudienceError as exc:
        raise FirebaseAuthError(
            "The sign-in token was issued for a different application."
        ) from exc
    except jwt.PyJWTError as exc:
        raise FirebaseAuthError("The sign-in token is not valid.") from exc

    if not str(claims.get("sub", "")).strip():
        raise FirebaseAuthError("The sign-in token identifies no user.")

    auth_time = claims.get("auth_time")
    if auth_time is not None:
        try:
            signed_in_at = int(auth_time)
        except (TypeError, ValueError) as exc:
            raise FirebaseAuthError("The sign-in token is not valid.") from exc
        if signed_in_at > time.time() + env.FIREBASE_TOKEN_LEEWAY:
            raise FirebaseAuthError("The sign-in token is not valid yet.")

    return claims


def bearer_token(request):
    """Return the bearer token from the Authorization header, or ``None``.

    Anything that is not a well-formed ``Bearer`` header is treated as no
    token at all, so an unrelated authorization scheme does not make the
    whole request fail.
    """
    header = request.META.get("HTTP_AUTHORIZATION", "")
    scheme, _, value = header.partition(" ")

    if scheme.lower() != "bearer":
        return None

    token = value.strip()
    return token or None
