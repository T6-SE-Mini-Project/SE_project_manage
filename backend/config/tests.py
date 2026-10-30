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
        # Upstash's TCP endpoint is TLS-only, hence rediss://.
        "REDIS_URL": "rediss://default:not-a-real-password@example.upstash.io:6379",
        # browser -> Vercel -> Render, so the client address is the second
        # entry from the right of X-Forwarded-For.
        "TRUSTED_PROXY_COUNT": "2",
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
    "cache_backend": s.CACHES["default"]["BACKEND"],
    "cache_location": s.CACHES["default"].get("LOCATION"),
    "cache_options": s.CACHES["default"].get("OPTIONS", {}),
    "cache_enabled": s.CACHE_ENABLED,
    "throttle_cache": s.CACHES.get("throttle", {}).get("BACKEND"),
    "throttle_enabled": s.THROTTLE_ENABLED,
    "throttle_read_rate": s.THROTTLE_READ_RATE,
    "throttle_write_rate": s.THROTTLE_WRITE_RATE,
    "trusted_proxy_count": s.TRUSTED_PROXY_COUNT,
    "middleware": list(s.MIDDLEWARE),
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

    def test_deployed_frontend_origin_is_trusted_by_default(self):
        # A fresh deploy has no CSRF_TRUSTED_ORIGINS in the dashboard (the
        # blueprint leaves it unset), and without a trusted origin every
        # POST -- register, login, checkout -- fails with 403. The deployed
        # site origins are public, so they are defaults rather than another
        # value someone has to remember to paste in.
        settings = self.load_settings(CSRF_TRUSTED_ORIGINS="")

        self.assertIn(
            "https://online-book-store-theta-seven.vercel.app",
            settings["csrf_trusted_origins"],
        )

    def test_redis_url_configures_the_cache(self):
        settings = self.load_settings()

        self.assertEqual(
            settings["cache_backend"],
            "django.core.cache.backends.redis.RedisCache",
        )
        self.assertTrue(settings["cache_location"].startswith("rediss://"))
        self.assertTrue(settings["cache_enabled"])

    def test_cache_connections_time_out(self):
        # Upstash is a network hop away. Without both timeouts a struggling
        # cache holds every request open instead of degrading to a miss,
        # which is the one way a cache can take the API down with it.
        options = self.load_settings()["cache_options"]

        self.assertEqual(options["socket_connect_timeout"], 2)
        self.assertEqual(options["socket_timeout"], 2)
        self.assertTrue(options["retry_on_timeout"])

    def test_without_a_redis_url_nothing_is_cached(self):
        # A per-process cache would be wrong here: each gunicorn worker
        # would keep its own copy and invalidation in one would not reach
        # the others, so an unconfigured deployment reads from MySQL.
        settings = self.load_settings(REDIS_URL="")

        self.assertEqual(
            settings["cache_backend"],
            "django.core.cache.backends.dummy.DummyCache",
        )
        self.assertFalse(settings["cache_enabled"])

    def test_caching_can_be_switched_off_with_the_url_left_in_place(self):
        settings = self.load_settings(CACHE_ENABLED="false")

        self.assertFalse(settings["cache_enabled"])
        # The connection stays configured, so turning it back on needs no
        # secret to be pasted again.
        self.assertEqual(
            settings["cache_backend"],
            "django.core.cache.backends.redis.RedisCache",
        )

    def test_rate_limiting_is_on_in_production(self):
        settings = self.load_settings()

        self.assertTrue(settings["throttle_enabled"])
        self.assertEqual(settings["throttle_read_rate"], 300)
        self.assertEqual(settings["throttle_write_rate"], 60)
        self.assertIn(
            "config.throttle.RateLimitMiddleware", settings["middleware"]
        )

    def test_rate_limiting_is_on_even_without_a_cache(self):
        # The counters fall back to each worker's memory rather than the
        # dummy backend: a limit per process still limits, while a dummy
        # backend would silently count nothing and look like it worked.
        settings = self.load_settings(REDIS_URL="")

        self.assertTrue(settings["throttle_enabled"])
        self.assertEqual(
            settings["throttle_cache"],
            "django.core.cache.backends.locmem.LocMemCache",
        )

    def test_the_counter_store_uses_redis_when_configured(self):
        self.assertEqual(
            self.load_settings()["throttle_cache"],
            "django.core.cache.backends.redis.RedisCache",
        )

    def test_the_deployment_knows_how_many_proxies_are_in_front_of_it(self):
        # At 0, REMOTE_ADDR is Vercel's edge and every anonymous caller
        # shares one rate-limit bucket; too high and a client can spoof
        # X-Forwarded-For and never be limited. This deployment is
        # browser -> Vercel -> Render.
        self.assertEqual(self.load_settings()["trusted_proxy_count"], 2)

    def test_rate_limiting_runs_after_authentication(self):
        # Order is load-bearing: a signed-in caller must be counted by
        # their Firebase uid, not lumped in with everybody else behind the
        # Vercel proxy.
        middleware = self.load_settings()["middleware"]

        self.assertGreater(
            middleware.index("config.throttle.RateLimitMiddleware"),
            middleware.index(
                "accounts.middleware.FirebaseAuthenticationMiddleware"
            ),
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
