"""Settings used only for local automated tests.

This module never connects to the development MySQL database. It is used
explicitly with ``--settings=config.settings_test`` so the test runner creates
an isolated in-memory SQLite database instead.
"""

import os

# config.settings requires these environment variables at import time. These
# values are placeholders and are never used because DATABASES is overridden.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-a-secret")
os.environ.setdefault("DB_NAME", "test_online_book_store")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.setdefault("DB_PORT", "3306")

from .settings import *  # noqa: E402,F401,F403


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("TEST_SQLITE_NAME", ":memory:"),
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
