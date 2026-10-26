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
SESSION_COOKIE_AGE          Session inactivity timeout (seconds)      ``900``
CSRF_TRUSTED_ORIGINS        Comma-separated trusted CSRF origins      *(empty)*
HTTPS_ENABLED               Terminate TLS in front of Django          ``false``
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


# --- MySQL database ----------------------------------------------------------

DB_NAME = env("DB_NAME", required=True)
DB_USER = env("DB_USER", required=True)
DB_PASSWORD = env("DB_PASSWORD", required=True)
DB_HOST = env("DB_HOST", default="localhost")
DB_PORT = env_int("DB_PORT", default=3306)


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

