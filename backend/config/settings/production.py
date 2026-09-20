"""Secure baseline, not a completed production deployment configuration."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import ALLOWED_HOSTS, SECRET_KEY

if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Production requires explicit DJANGO_ALLOWED_HOSTS.")
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("Production requires a strong DJANGO_SECRET_KEY.")

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
# Subdomain-wide HSTS/proxy trust must be configured with the hosting topology.
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True