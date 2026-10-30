"""Central configuration for the Online Book Store backend.

This module is the single place that reads the environment (and the
optional ``.env`` file next to ``manage.py``) and turns it into typed,
validated values. Every other module — including ``config.settings`` —
imports its configuration from here instead of calling ``os.environ``
directly, so there is exactly one place that documents and validates
runtime configuration.

Environment variables
---------------------

==========================  ========================================  =====================
Variable                    Purpose                                   Default
==========================  ========================================  =====================
DJANGO_SECRET_KEY           Django signing key                        *required*
DJANGO_DEBUG                Enable development/debug mode             ``false``
DJANGO_ALLOWED_HOSTS        Comma-separated permitted hosts           ``localhost,127.0.0.1``
DB_NAME                     MySQL database name                       *required*
DB_USER                     MySQL user                                *required*
DB_PASSWORD                 MySQL password                            *required*
DB_HOST                     MySQL host                                ``localhost``
DB_PORT                     MySQL port                                ``3306``
DB_SSL_CA                   Path to the MySQL CA bundle (TLS)         *(empty)*
DB_SSL_REQUIRED             Require TLS, skip certificate check       ``false``
DB_CONN_MAX_AGE             Seconds a database connection is reused   ``0``
SESSION_COOKIE_AGE          Session inactivity timeout (seconds)      ``900``
FIREBASE_PROJECT_ID         Firebase project that issues ID tokens    *(empty)*
FIREBASE_TOKEN_LEEWAY       Clock-skew allowance when verifying (s)   ``30``
FIREBASE_PUBLIC_KEYS_URL    Where Google publishes the signing certs  Google's URL
REDIS_URL                   Redis cache connection URL                *(empty)*
CACHE_ENABLED               Serve API reads from the cache            ``true``
REDIS_TIMEOUT               Socket timeout for cache operations (s)   ``2``
THROTTLE_ENABLED            Enforce API rate limits                   ``true``
THROTTLE_READ_RATE          Reads per caller per minute                ``300``
THROTTLE_WRITE_RATE         Writes per caller per minute                ``60``
TRUSTED_PROXY_COUNT         Proxies in front of this service            ``0``
CSRF_TRUSTED_ORIGINS        Comma-separated trusted CSRF origins      the Vercel site
HTTPS_ENABLED               Terminate TLS in front of Django          ``false``
BACKUP_DIR                  Where order/inventory backups are kept    ``<backend>/backups``
BACKUP_RETENTION_DAYS       Days of backup artifacts to keep          ``14``
BACKUP_MAX_AGE_HOURS        Maximum accepted age of a good backup     ``24``
==========================  ========================================  =====================

Copy ``.env.example`` to ``.env`` and fill in the values for your machine.
``.env`` is git-ignored and must never be committed.
"""

from pathlib import Path

from dotenv import load_dotenv

import os
import tempfile

# backend/ — the directory that contains manage.py, requirements.txt and
# every Django app.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from the backend directory. Existing process environment
# variables always win over .env values (load_dotenv does not override).
load_dotenv(BASE_DIR / ".env")


class ImproperlyConfigured(Exception):
    """Raised when a required environment variable is missing."""


def env(key, default=None, required=False):
    """Return a raw string environment value.

    Raises :class:`ImproperlyConfigured` when ``required`` is true and the
    variable is missing or empty.
    """
    value = os.environ.get(key, default)
    if required and (value is None or str(value).strip() == ""):
        raise ImproperlyConfigured(
            f"Missing required environment variable: {key}. "
            "Copy backend/.env.example to backend/.env and fill in the values."
        )
    return value


def env_bool(key, default=False):
    """Return an environment value interpreted as a boolean."""
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(key, default):
    """Return an environment value interpreted as an integer."""
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ImproperlyConfigured(
            f"Environment variable {key} must be an integer, got {raw!r}."
        ) from exc


def env_list(key, default=(), separator=","):
    """Return a comma-separated environment value as a list of strings."""
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return list(default)
    return [item.strip() for item in raw.split(separator) if item.strip()]


# --- Security ---------------------------------------------------------------

# Generate a unique key locally (for example with
# ``python -c "from django.core.management.utils import get_random_secret_key; \
# print(get_random_secret_key())"``) and store it in .env as DJANGO_SECRET_KEY.
SECRET_KEY = env("DJANGO_SECRET_KEY", required=True)

# Development mode. Never enable in production; disabling it also turns on
# the production security settings in config.settings.
#
# The default is False so that a missing or misspelled DJANGO_DEBUG fails
# safe. Defaulting to True meant an unset variable silently served Django's
# debug pages in production, publishing the whole URL map and a traceback
# with local variables on any unhandled error. Local development sets
# DJANGO_DEBUG=true explicitly, as backend/.env.example does.
DEBUG = env_bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])

# Render publishes the service's public hostname as RENDER_EXTERNAL_HOSTNAME
# (for example "bookstore-api.onrender.com"). Appending it automatically means
# a deploy never fails with DisallowedHost because the hostname was not copied
# into DJANGO_ALLOWED_HOSTS by hand.
_platform_hostname = env("RENDER_EXTERNAL_HOSTNAME", default="")
if _platform_hostname and _platform_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_platform_hostname)


# --- MySQL database ----------------------------------------------------------

DB_NAME = env("DB_NAME", required=True)
DB_USER = env("DB_USER", required=True)
DB_PASSWORD = env("DB_PASSWORD", required=True)
DB_HOST = env("DB_HOST", default="localhost")
DB_PORT = env_int("DB_PORT", default=3306)

# Seconds Django keeps a database connection open for reuse. 0 (the default)
# opens a fresh connection per request, which is correct for local work. In
# production a small positive value removes a TCP+TLS handshake from every
# request; keep it well below the provider's idle timeout, and remember each
# gunicorn worker holds its own connection against the plan's connection limit.
DB_CONN_MAX_AGE = env_int("DB_CONN_MAX_AGE", default=0)

# Managed MySQL providers (Aiven, PlanetScale, RDS) accept only TLS
# connections. Point DB_SSL_CA at the provider's CA bundle for a *verified*
# connection; on Render, upload the bundle as a Secret File and use the path
# it is mounted at (for example /etc/secrets/aiven-ca.pem).
#
# DB_SSL_REQUIRED=true is the weaker fallback: the connection is encrypted but
# the server certificate is not verified, which leaves it open to an active
# man-in-the-middle. Prefer the CA bundle in production.
def ca_bundle_path(value):
    """Return a filesystem path for a CA bundle.

    ``value`` may be a path, or the certificate itself. A hosting
    dashboard is a text box, so pasting the PEM straight into the variable
    is the natural thing to do -- but libmysqlclient only accepts a
    filename and fails obscurely with
    ``(2026, 'TLS/SSL error: File name too long')`` when handed a
    certificate, because it tries to open the whole blob as a path.
    Accept both, and write inline PEM out to a file.

    Some dashboards also flatten newlines into a literal backslash-n, which
    makes the certificate unparseable; those are restored.
    """
    value = (value or "").strip()
    if not value:
        return ""
    if "-----BEGIN" not in value:
        # An ordinary path, for example a Render Secret File.
        return value

    pem = value if "\n" in value else value.replace("\\n", "\n")
    if not pem.endswith("\n"):
        pem += "\n"

    destination = Path(tempfile.gettempdir()) / "db-ssl-ca.pem"
    destination.write_text(pem)
    return str(destination)


DB_SSL_CA = ca_bundle_path(env("DB_SSL_CA", default=""))
DB_SSL_REQUIRED = env_bool("DB_SSL_REQUIRED", default=False)


def db_ssl_options(ca_path, ssl_required):
    """Return the DATABASES OPTIONS entries that configure TLS.

    A CA bundle wins over the bare requirement flag, because it gives the
    strictly stronger guarantee: the connection is encrypted *and* the
    server certificate is verified.
    """
    if ca_path:
        return {"ssl": {"ca": ca_path}}
    if ssl_required:
        # mysqlclient forwards ssl_mode to libmysqlclient: encrypt the
        # connection, but do not verify the server certificate.
        return {"ssl_mode": "REQUIRED"}
    return {}


DB_SSL_OPTIONS = db_ssl_options(DB_SSL_CA, DB_SSL_REQUIRED)


# --- Sessions ----------------------------------------------------------------

# Inactivity timeout (seconds) after which a session expires.
SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE", default=900)


# --- Firebase authentication --------------------------------------------------

# The Firebase project whose ID tokens this API accepts. Every token is a
# JWT signed by Google for exactly one project, and the project id is both
# the token's audience and the tail of its issuer, so this value is what
# stops a token minted for somebody else's Firebase project from being
# accepted here. accounts/firebase.py refuses to verify anything while it
# is empty, rather than falling back to an unchecked audience.
#
# It is the same value the browser bundle uses as VITE_FIREBASE_PROJECT_ID,
# and it is not a secret: a project id is public. No service-account JSON is
# needed, because tokens are verified against Google's *public* signing
# certificates (see FIREBASE_PUBLIC_KEYS_URL).
FIREBASE_PROJECT_ID = env("FIREBASE_PROJECT_ID", default="").strip()

# Seconds of clock skew tolerated on a token's "exp", "iat" and "auth_time"
# claims. Render's clock and Google's differ by milliseconds in practice, but
# a container whose clock drifts a few seconds would otherwise reject every
# freshly minted token. Keep it small: it is the window by which an expired
# token is still accepted.
FIREBASE_TOKEN_LEEWAY = env_int("FIREBASE_TOKEN_LEEWAY", default=30)

# Where Google publishes the x509 certificates that sign Firebase ID tokens.
# The keys rotate roughly daily; the response's Cache-Control header says how
# long they may be cached, which accounts/firebase.py honours. Overridable so
# a test can point it at a local fixture.
FIREBASE_PUBLIC_KEYS_URL = env(
    "FIREBASE_PUBLIC_KEYS_URL",
    default=(
        "https://www.googleapis.com/robot/v1/metadata/x509/"
        "securetoken@system.gserviceaccount.com"
    ),
)


# --- Redis cache (Upstash) ----------------------------------------------------

# Connection URL for the Redis instance that caches API responses
# (config/cache.py). Upstash gives two endpoints per database; this is the
# **TCP** one, and it is TLS-only, so the URL starts with rediss://
#
#   rediss://default:<password>@<endpoint>.upstash.io:6379
#
# Leave it empty to run without a cache: CACHES then uses Django's dummy
# backend and every read goes to MySQL, which is the right default for
# local work and what the test suite uses. Caching is opt-in by configuring
# this, so nothing silently caches with a per-process store that several
# gunicorn workers would each keep their own copy of.
#
# The URL contains the password, so it is a SECRET: it belongs in the
# hosting dashboard, never in a committed file.
REDIS_URL = env("REDIS_URL", default="").strip()

# Kill switch. False stops the API serving reads from the cache while
# leaving REDIS_URL configured, which is what to reach for first if cached
# data is ever suspected of being stale.
CACHE_ENABLED = env_bool("CACHE_ENABLED", default=True) and bool(REDIS_URL)

# Seconds to wait for Upstash before giving up on a cache operation. A
# cache miss costs one database query; a slow cache would otherwise cost
# every request its own stall, so this is deliberately impatient.
REDIS_TIMEOUT = env_int("REDIS_TIMEOUT", default=2)


# --- Rate limiting -----------------------------------------------------------

# Whether the API enforces per-caller rate limits (config/throttle.py).
# On by default, because the endpoints worth limiting -- sign-in, which
# creates accounts, and payment, which takes card numbers -- are reachable
# by anyone who can reach the site. The counters live in Redis when
# REDIS_URL is set and in each worker's memory otherwise, which still
# limits, just per process.
THROTTLE_ENABLED = env_bool("THROTTLE_ENABLED", default=True)

# Requests per caller per minute. A caller is a Firebase uid when the
# request carries a token, and an IP address otherwise.
#
# Reads are generous: one page of the catalogue makes several, and most of
# them are answered from the cache. Writes are not, because each one costs
# a transaction and nothing a customer does by hand needs more.
THROTTLE_READ_RATE = env_int("THROTTLE_READ_RATE", default=300)
THROTTLE_WRITE_RATE = env_int("THROTTLE_WRITE_RATE", default=60)

# How many proxies sit in front of this service. This decides which entry
# of X-Forwarded-For is believed, and getting it wrong breaks rate
# limiting in one of two ways:
#
#   too low  -- every anonymous caller behind the proxy shares one bucket,
#               so one busy visitor can rate-limit everybody;
#   too high -- the client's own X-Forwarded-For value is believed, so a
#               caller can rotate fake addresses and never be limited.
#
# 0 ignores the header and uses the socket address, which is right for
# local work and for Docker Compose. The deployed stack is
# browser -> Vercel -> Render, so production sets 2. Count the hops from
# the service outwards, not the other way round.
TRUSTED_PROXY_COUNT = env_int("TRUSTED_PROXY_COUNT", default=0)


# --- Deployment / HTTPS --------------------------------------------------------

# Comma-separated list of origins that Django may trust for CSRF-protected
# cross-origin requests, for example "https://bookstore.example.com". Only
# needed when the React app is served from a different origin than the API.
#
# This deployment always is: the browser loads the Vercel site and every
# /api/* call is rewritten to this service on Vercel's side, so a POST arrives
# with the *site's* Origin header while Host is the Render hostname. Django
# compares the two and rejects the request with
#
#   Origin checking failed - https://<site> does not match any trusted origins
#
# until the site origin is listed here. The production site URLs are public,
# not secrets, so they are defaults: a fresh deploy of this repo can register
# and log users in without a dashboard round-trip. Setting the environment
# variable still wins, which is what a custom domain needs.
DEFAULT_CSRF_TRUSTED_ORIGINS = [
    # Vercel's stable production alias for the `online-book-store` project.
    "https://online-book-store-theta-seven.vercel.app",
    # Per-team alias Vercel assigns to the same production deployment.
    "https://online-book-store-puneethv333s-projects.vercel.app",
]
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS", DEFAULT_CSRF_TRUSTED_ORIGINS
)

# Set to true when the deployment terminates TLS in front of Django (for
# example behind a reverse proxy or load balancer). Enabling it turns on the
# HTTPS-only production security settings in config.settings.
HTTPS_ENABLED = env_bool("HTTPS_ENABLED", default=False)


# --- Backups (issue #18, OBS-NF-006) ------------------------------------------

# Directory that ``manage.py backup_data`` writes order and inventory
# backups into. Point this at a mounted volume in production so the
# backups outlive the container.
#
# A relative value is resolved against BASE_DIR (the backend directory),
# not the current working directory, so "BACKUP_DIR=backups" always means
# backend/backups no matter where manage.py is run from.
def _backup_dir():
    configured = Path(env("BACKUP_DIR", default="backups"))
    return configured if configured.is_absolute() else BASE_DIR / configured


BACKUP_DIR = _backup_dir()

# How many days of backup artifacts to keep on disk. The BackupRun
# execution records are kept regardless, so the schedule stays auditable
# after old artifacts are rotated away.
BACKUP_RETENTION_DAYS = env_int("BACKUP_RETENTION_DAYS", default=14)

# OBS-NF-006 requires a backup at least once every 24 hours;
# ``manage.py verify_backups`` fails when the newest successful backup is
# older than this.
BACKUP_MAX_AGE_HOURS = env_int("BACKUP_MAX_AGE_HOURS", default=24)
