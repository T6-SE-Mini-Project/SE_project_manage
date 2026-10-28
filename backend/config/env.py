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
DJANGO_DEBUG                Enable development/debug mode             ``true``
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
CSRF_TRUSTED_ORIGINS        Comma-separated trusted CSRF origins      *(empty)*
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
DEBUG = env_bool("DJANGO_DEBUG", default=True)

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
DB_SSL_CA = env("DB_SSL_CA", default="")
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


# --- Deployment / HTTPS --------------------------------------------------------

# Comma-separated list of origins that Django may trust for CSRF-protected
# cross-origin requests, for example "https://bookstore.example.com". Only
# needed when the React app is served from a different origin than the API.
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", [])

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
