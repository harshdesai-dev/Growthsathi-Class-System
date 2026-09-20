from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import Throttled

from .models import AccessAttempt, normalize_username


def limit_access(request, purpose, username=""):
    context = str(getattr(request, "institute", None) and request.institute.pk)
    ip = request.META.get("REMOTE_ADDR", "")  # Never trust arbitrary forwarded headers.
    keys = [
        (f"{purpose}:ip:{ip}", 100),
        (f"{purpose}:account:{context}:{normalize_username(username)}", 10),
    ]
    for identity, limit in keys:
        key = salted_hmac("access-throttle", identity, algorithm="sha256").hexdigest()
        with transaction.atomic():
            now = timezone.now()
            AccessAttempt.objects.get_or_create(key=key, defaults={"window_start": now})
            attempt = AccessAttempt.objects.select_for_update().get(pk=key)
            if now - attempt.window_start >= timedelta(minutes=15):
                attempt.window_start, attempt.count = now, 0
            if attempt.count >= limit:
                raise Throttled(wait=900)
            attempt.count += 1
            attempt.save()
