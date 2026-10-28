"""Tests for the deployment-facing parts of the central configuration.

These cover the settings that only take effect in production, which is
exactly where a mistake is most expensive and least visible: the suite
otherwise runs with DEBUG on and HTTPS off, so nothing else exercises them.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase
from django.urls import reverse

from config.env import db_ssl_options


BASE_DIR = Path(__file__).resolve().parent.parent


class HealthCheckTests(SimpleTestCase):
    """The liveness probe the hosting platform polls."""

    def test_health_check_returns_ok(self):
        response = self.client.get(reverse("healthz"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_health_check_needs_no_authentication(self):
        # Render polls it with no cookies at all; a redirect to a login page
        # would be reported as a failed health check and restart the service.
        response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 200)

    def test_health_check_rejects_other_methods(self):
        self.assertEqual(self.client.post("/healthz/").status_code, 405)


class DatabaseTlsOptionTests(SimpleTestCase):
    """Managed MySQL (Aiven) accepts only encrypted connections."""

    def test_ca_bundle_produces_a_verified_connection(self):
        self.assertEqual(
            db_ssl_options("/etc/secrets/aiven-ca.pem", False),
            {"ssl": {"ca": "/etc/secrets/aiven-ca.pem"}},
        )

    def test_ca_bundle_wins_over_the_requirement_flag(self):
        # Verifying the certificate is strictly stronger than merely
        # encrypting, so the bundle must take precedence.
        self.assertEqual(
            db_ssl_options("/etc/secrets/aiven-ca.pem", True),
            {"ssl": {"ca": "/etc/secrets/aiven-ca.pem"}},
        )

    def test_flag_alone_requires_tls_without_verification(self):
        self.assertEqual(db_ssl_options("", True), {"ssl_mode": "REQUIRED"})

    def test_no_tls_configuration_adds_nothing(self):
        self.assertEqual(db_ssl_options("", False), {})


class ProductionSettingsTests(SimpleTestCase):
    """Import config.settings in a production environment and inspect it.

    This runs in a subprocess on purpose. Reloading the settings module in
    this process would mutate the module object that django.conf.settings
    already wraps, corrupting every test that runs afterwards.
    """

    maxDiff = None

    PRODUCTION_ENV = {
        "DJANGO_SECRET_KEY": "test-only-production-key",
        "DJANGO_DEBUG": "false",
        "DJANGO_ALLOWED_HOSTS": "bookstore-api.onrender.com",
        "HTTPS_ENABLED": "true",
        "CSRF_TRUSTED_ORIGINS": "https://bookstore.vercel.app",
        "DB_NAME": "defaultdb",
        "DB_USER": "bookstore",
        "DB_PASSWORD": "not-a-real-password",
        "DB_HOST": "example.aivencloud.com",
        "DB_PORT": "22767",
        "DB_SSL_CA": "/etc/secrets/aiven-ca.pem",
        "DB_SSL_REQUIRED": "true",
        "DB_CONN_MAX_AGE": "60",
        # Render injects this; config/env.py must fold it into ALLOWED_HOSTS.
        "RENDER_EXTERNAL_HOSTNAME": "bookstore-api.onrender.com",
    }

    INSPECT = """
import json
import config.settings as s

print(json.dumps({
    "debug": s.DEBUG,
    "allowed_hosts": s.ALLOWED_HOSTS,
    "csrf_trusted_origins": s.CSRF_TRUSTED_ORIGINS,
    "proxy_ssl_header": list(getattr(s, "SECURE_PROXY_SSL_HEADER", []) or []),
    "ssl_redirect": getattr(s, "SECURE_SSL_REDIRECT", False),
    "session_cookie_secure": getattr(s, "SESSION_COOKIE_SECURE", False),
    "csrf_cookie_secure": getattr(s, "CSRF_COOKIE_SECURE", False),
    "hsts_seconds": getattr(s, "SECURE_HSTS_SECONDS", 0),
    "nosniff": getattr(s, "SECURE_CONTENT_TYPE_NOSNIFF", False),
    "staticfiles_backend": getattr(s, "STORAGES", {}).get(
        "staticfiles", {}
    ).get("BACKEND"),
    "db_options": s.DATABASES["default"]["OPTIONS"],
    "db_conn_max_age": s.DATABASES["default"]["CONN_MAX_AGE"],
}))
"""

    @classmethod
    def load_settings(cls, **overrides):
        """Return config.settings as a dict, imported under a given env."""
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(BASE_DIR),
            # Keep the module from writing .pyc files into the repo.
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        environment.update(cls.PRODUCTION_ENV)
        environment.update(overrides)

        result = subprocess.run(
            [sys.executable, "-c", cls.INSPECT],
            cwd=str(BASE_DIR),
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(
                "importing config.settings failed:\n" + result.stderr
            )
        return json.loads(result.stdout)

    def test_production_import_turns_debug_off(self):
        self.assertFalse(self.load_settings()["debug"])

    def test_https_deployment_trusts_the_proxy_protocol_header(self):
        # Without this, Django sees Render's forwarded HTTP request as
        # insecure and SECURE_SSL_REDIRECT bounces it to HTTPS forever.
        # This assertion is the regression guard for that redirect loop.
        settings = self.load_settings()

        self.assertEqual(
            settings["proxy_ssl_header"],
            ["HTTP_X_FORWARDED_PROTO", "https"],
        )
        self.assertTrue(settings["ssl_redirect"])

    def test_https_deployment_secures_the_cookies(self):
        settings = self.load_settings()

        self.assertTrue(settings["session_cookie_secure"])
        self.assertTrue(settings["csrf_cookie_secure"])
        self.assertEqual(settings["hsts_seconds"], 31536000)
        self.assertTrue(settings["nosniff"])

    def test_browser_origin_is_trusted_for_csrf(self):
        # The browser talks to the Vercel origin, so that is the origin
        # Django must trust, not the Render hostname.
        settings = self.load_settings()

        self.assertEqual(
            settings["csrf_trusted_origins"],
            ["https://bookstore.vercel.app"],
        )

    def test_platform_hostname_is_added_to_allowed_hosts(self):
        settings = self.load_settings(
            DJANGO_ALLOWED_HOSTS="bookstore.example.com",
            RENDER_EXTERNAL_HOSTNAME="bookstore-api.onrender.com",
        )

        self.assertEqual(
            settings["allowed_hosts"],
            ["bookstore.example.com", "bookstore-api.onrender.com"],
        )

    def test_platform_hostname_is_not_duplicated(self):
        settings = self.load_settings(
            DJANGO_ALLOWED_HOSTS="bookstore-api.onrender.com",
            RENDER_EXTERNAL_HOSTNAME="bookstore-api.onrender.com",
        )

        self.assertEqual(settings["allowed_hosts"], ["bookstore-api.onrender.com"])

    def test_database_uses_verified_tls_and_connection_reuse(self):
        settings = self.load_settings()

        self.assertEqual(
            settings["db_options"],
            {
                "charset": "utf8mb4",
                "ssl": {"ca": "/etc/secrets/aiven-ca.pem"},
            },
        )
        self.assertEqual(settings["db_conn_max_age"], 60)

    def test_static_files_use_the_whitenoise_manifest_backend(self):
        self.assertEqual(
            self.load_settings()["staticfiles_backend"],
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )

    def test_missing_debug_variable_fails_safe(self):
        # A deployment that leaves DJANGO_DEBUG empty must not serve
        # Django's debug pages. This happened in production once: the
        # variable defaulted to True, publishing the whole URL map and
        # tracebacks, and leaving the session and CSRF cookies without
        # Secure.
        #
        # An empty value is used rather than removing the variable, because
        # env_bool treats empty and absent identically, and a truly absent
        # variable would be filled from backend/.env on a developer machine
        # while being genuinely absent in CI and on Render.
        settings = self.load_settings(DJANGO_DEBUG="")

        self.assertFalse(settings["debug"])
        self.assertTrue(settings["session_cookie_secure"])
        self.assertTrue(settings["csrf_cookie_secure"])

    def test_debug_deployment_keeps_the_development_defaults(self):
        # The flip side: with DEBUG on, none of the HTTPS-only settings
        # should appear, or local development breaks.
        settings = self.load_settings(DJANGO_DEBUG="true")

        self.assertTrue(settings["debug"])
        self.assertEqual(settings["proxy_ssl_header"], [])
        self.assertFalse(settings["ssl_redirect"])
        self.assertIsNone(settings["staticfiles_backend"])
