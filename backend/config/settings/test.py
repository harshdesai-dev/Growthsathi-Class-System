"""Tests retain PostgreSQL configuration; no SQLite fallback."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import DATABASES

DEBUG = False
if DATABASES["default"]["TEST"]["NAME"] == DATABASES["default"]["NAME"]:
    raise ImproperlyConfigured("Test database must differ from the development database.")
