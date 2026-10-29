
"""
Django settings for the Online Book Store project.
Django version: 5.2.18

All runtime values come from the central configuration module
``config.env`` (which loads backend/.env). See backend/.env.example for
the available variables.
"""

from . import env


# Security settings
# Generate a unique key locally and place it in .env as DJANGO_SECRET_KEY.
SECRET_KEY = env.SECRET_KEY

# Development settings (disable DEBUG in production)
DEBUG = env.DEBUG

ALLOWED_HOSTS = env.ALLOWED_HOSTS


# Installed applications
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Online Book Store applications
    "accounts",
    "books",
    "cart",
    "orders",
    "payments",
    "reviews",
    # Administrator API (catalogue, orders, customers, sales reports)
    "administration",
    # Operational tasks: scheduled order and inventory backups
    "operations",
]


# Middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Identifies API callers from their Firebase ID token, after Django's
    # own middleware has resolved any session user. A bearer token wins
    # over the session; without one the session still signs in the Django
    # admin site. See accounts/middleware.py.
    "accounts.middleware.FirebaseAuthenticationMiddleware",
    # Per-caller rate limits. After the Firebase middleware on purpose: a
    # signed-in caller is then counted by their uid instead of sharing a
    # bucket with everybody else behind the Vercel proxy. See
    # config/throttle.py.
    "config.throttle.RateLimitMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# URL configuration
ROOT_URLCONF = "config.urls"


# Templates configuration
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# WSGI application
WSGI_APPLICATION = "config.wsgi.application"


# MySQL database configuration
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env.DB_NAME,
        "USER": env.DB_USER,
        "PASSWORD": env.DB_PASSWORD,
        "HOST": env.DB_HOST,
        "PORT": env.DB_PORT,
        # Reuse connections in production; 0 locally. See config/env.py.
        "CONN_MAX_AGE": env.DB_CONN_MAX_AGE,
        "OPTIONS": {
            "charset": "utf8mb4",
            # TLS settings for the managed database, empty when unset.
            **env.DB_SSL_OPTIONS,
        },
    }
}


# Cache
#
# Redis when REDIS_URL is set (Upstash in production, over TLS), and
# Django's dummy backend otherwise, so an unconfigured deployment reads
# from MySQL instead of from a per-worker cache that cannot be invalidated
# across workers. config/cache.py is the only module that uses it.
#
# The "throttle" alias holds the rate-limit counters. It falls back to
# local memory rather than the dummy backend, because a limit counted per
# worker process still limits, while a dummy backend silently counts
# nothing at all.
if env.REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": env.REDIS_URL,
            "OPTIONS": {
                # Forwarded to redis.ConnectionPool.from_url. The two
                # timeouts are what stop a struggling cache from holding
                # requests open; config/cache.py turns the resulting
                # errors into cache misses.
                "socket_connect_timeout": env.REDIS_TIMEOUT,
                "socket_timeout": env.REDIS_TIMEOUT,
                "retry_on_timeout": True,
                # Upstash drops idle connections; this re-checks one
                # before it is handed to a request.
                "health_check_interval": 30,
                # Each gunicorn worker holds its own pool, so keep the
                # total within the plan's connection limit.
                "max_connections": 16,
            },
        },
    }
    CACHES["throttle"] = {
        **CACHES["default"],
        # Counters are small and short-lived; keeping them in their own
        # Redis database keeps a cache flush from clearing them and makes
        # them easy to inspect.
        "KEY_PREFIX": "throttle",
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        },
        "throttle": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "obs-throttle",
        },
    }

# Read by config/cache.py on every cached view. Setting CACHE_ENABLED=false
# turns response caching off without removing REDIS_URL.
CACHE_ENABLED = env.CACHE_ENABLED


# Rate limiting, read by config/throttle.py. See config/env.py for what
# TRUSTED_PROXY_COUNT does and why it has to match the deployment.
THROTTLE_ENABLED = env.THROTTLE_ENABLED
THROTTLE_READ_RATE = env.THROTTLE_READ_RATE
THROTTLE_WRITE_RATE = env.THROTTLE_WRITE_RATE
TRUSTED_PROXY_COUNT = env.TRUSTED_PROXY_COUNT


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files
STATIC_URL = "static/"
STATIC_ROOT = env.BASE_DIR / "staticfiles"

# In production gunicorn has no web server in front of it, so WhiteNoise
# (already in MIDDLEWARE) serves the collected static files. The compressed
# manifest backend fingerprints every filename so the files can be cached
# indefinitely, and it pre-compresses them. It requires
# "manage.py collectstatic" to have run first; the container entrypoint does
# that on every start, before gunicorn binds the port.
if not DEBUG:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

CSRF_TRUSTED_ORIGINS = env.CSRF_TRUSTED_ORIGINS


# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Order and inventory backups (issue #18). See config/env.py.
BACKUP_DIR = env.BACKUP_DIR
BACKUP_RETENTION_DAYS = env.BACKUP_RETENTION_DAYS
BACKUP_MAX_AGE_HOURS = env.BACKUP_MAX_AGE_HOURS


# Session security: expire after SESSION_COOKIE_AGE seconds of inactivity
# (configured in config/env.py).
SESSION_COOKIE_AGE = env.SESSION_COOKIE_AGE
SESSION_SAVE_EVERY_REQUEST = True


# Production security settings
if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    if env.HTTPS_ENABLED:
        # Render, Vercel and every other managed platform terminate TLS at
        # their edge and forward plain HTTP with "X-Forwarded-Proto: https".
        # Without trusting that header Django considers every request
        # insecure, and SECURE_SSL_REDIRECT below would redirect to HTTPS in
        # an endless loop. Only safe because the platform's proxy always
        # overwrites the header on inbound requests.
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
        SECURE_SSL_REDIRECT = True
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True
        SECURE_HSTS_SECONDS = 31536000
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
