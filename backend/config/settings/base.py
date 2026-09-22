"""Shared foundation settings. Domain and authentication models come later."""

import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR.parent / ".env", override=False)


def env_list(name: str) -> list[str]:
    return [
        value.strip()
        for value in os.getenv(name, "").split(",")
        if value.strip()
    ]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "Set DJANGO_SECRET_KEY in the environment or local .env."
    )


DEBUG = False

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")


INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "storages",
    "institutes",
    "accounts",
    "audit",
    "academics",
    "timetable",
    "attendance",
    "fees",
    "materials",
    "exams",
    "announcements",
    "notifications",
]


AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "accounts.backends.TenantBackend",
]

# Username uniqueness is intentionally scoped to each institute.
# TenantBackend authenticates users using the verified institute context.
SILENCED_SYSTEM_CHECKS = [
    "auth.W004",
]

PLATFORM_HOSTS = env_list("PLATFORM_HOSTS")

# Shared secret used only between the trusted Next.js proxy and Django.
# Never hardcode the actual secret in source control.
PROXY_TENANT_SECRET = os.getenv("PROXY_TENANT_SECRET", "")


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
        "OPTIONS": {"min_length": 12},
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        )
    },
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "institutes.middleware.TenantContextMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "config.urls"
TEMPLATES = []
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("PGDATABASE", "growthsathi_class_dev"),
        "USER": os.getenv("PGUSER", ""),
        "PASSWORD": os.getenv("PGPASSWORD", ""),
        "HOST": os.getenv("PGHOST", "127.0.0.1"),
        "PORT": os.getenv("PGPORT", "5432"),
        "CONN_MAX_AGE": 0,
        "OPTIONS": {
            "sslmode": os.getenv("PGSSLMODE", "prefer"),
            "connect_timeout": 5,
        },
        "TEST": {
            "NAME": os.getenv(
                "PGTESTDATABASE",
                "growthsathi_class_test",
            )
        },
    }
}


LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / ".local" / "static"

# Used for local development when R2 credentials aren't configured.
MEDIA_ROOT = BASE_DIR / ".local" / "private-media"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

X_FRAME_OPTIONS = "DENY"


REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "common.api.api_exception_handler",
    "DEFAULT_PAGINATION_CLASS": (
        "rest_framework.pagination.PageNumberPagination"
    ),
    "PAGE_SIZE": 30,
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.SearchFilter",
        "common.filtering.ModuleFilters",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.CookieJWTAuthentication"
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "accounts.permissions.ActiveTenantUser"
    ],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer"
    ],
}


# Host-only cookies deliberately omit a Domain attribute.
ACCESS_COOKIE_NAME = "gs_access"
REFRESH_COOKIE_NAME = "gs_refresh"


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "CHECK_REVOKE_TOKEN": True,
}


PASSWORD_RESET_TIMEOUT = 3600


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.filebased.EmailBackend",
)

EMAIL_FILE_PATH = BASE_DIR / ".local" / "emails"

EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    "no-reply@example.invalid",
)

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "")
BREVO_SENDER_NAME = os.getenv(
    "BREVO_SENDER_NAME",
    "GrowthSathi",
)


# ---------------------------------------------------------------------------
# Private media storage — Cloudflare R2
# ---------------------------------------------------------------------------

R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "")
R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL", "")
R2_REGION = os.getenv("R2_REGION", "auto")

_r2_required_values = {
    "R2_ACCESS_KEY_ID": R2_ACCESS_KEY_ID,
    "R2_SECRET_ACCESS_KEY": R2_SECRET_ACCESS_KEY,
    "R2_BUCKET_NAME": R2_BUCKET_NAME,
    "R2_ENDPOINT_URL": R2_ENDPOINT_URL,
}

_r2_configured_values = [
    bool(value)
    for value in _r2_required_values.values()
]

# Do not silently fall back to ephemeral local storage if only some of the
# production R2 variables have been configured.
if any(_r2_configured_values) and not all(_r2_configured_values):
    missing = [
        name
        for name, value in _r2_required_values.items()
        if not value
    ]

    raise ImproperlyConfigured(
        "Incomplete R2 configuration. Missing: "
        + ", ".join(missing)
    )


# If all R2 credentials exist, Django stores uploaded media in the
# private Cloudflare R2 bucket.
#
# If none exist (normal local development), Django uses MEDIA_ROOT.
if all(_r2_configured_values):
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "access_key": R2_ACCESS_KEY_ID,
                "secret_key": R2_SECRET_ACCESS_KEY,
                "bucket_name": R2_BUCKET_NAME,
                "endpoint_url": R2_ENDPOINT_URL,
                "region_name": R2_REGION,

                # Keep every uploaded object private.
                "default_acl": None,

                # Signed URLs remain enabled if .url is needed later.
                "querystring_auth": True,

                # Never silently replace an existing object.
                "file_overwrite": False,

                "signature_version": "s3v4",
            },
        },
        "staticfiles": {
            "BACKEND": (
                "django.contrib.staticfiles.storage."
                "StaticFilesStorage"
            ),
        },
    }


# Maximum incoming request body size: 12 MiB.
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024


# Django validates the real upstream Railway host normally.
# The original public frontend hostname is forwarded separately by the
# trusted Next.js proxy using application-specific headers protected by
# PROXY_TENANT_SECRET.
USE_X_FORWARDED_HOST = False
