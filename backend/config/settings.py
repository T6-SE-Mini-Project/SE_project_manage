
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
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    }
}


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
        SECURE_SSL_REDIRECT = True
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True
        SECURE_HSTS_SECONDS = 31536000
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
