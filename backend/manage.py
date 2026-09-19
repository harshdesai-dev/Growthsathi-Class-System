#!/usr/bin/env python
"""Django management entry point."""

import os
import sys
from pathlib import Path

from django.core.management import execute_from_command_line
from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    execute_from_command_line(sys.argv)
