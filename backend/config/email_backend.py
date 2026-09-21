import json
from email.utils import parseaddr
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class BrevoAPIEmailBackend(BaseEmailBackend):
    API_URL = "https://api.brevo.com/v3/smtp/email"

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        api_key = getattr(settings, "BREVO_API_KEY", "")
        if not api_key:
            if self.fail_silently:
                return 0
            raise RuntimeError("BREVO_API_KEY is not configured")

        sent_count = 0

        for message in email_messages:
            try:
                sender_name, sender_email = parseaddr(
                    message.from_email or settings.DEFAULT_FROM_EMAIL
                )

                if not sender_email:
                    sender_email = getattr(settings, "BREVO_SENDER_EMAIL", "")

                if not sender_name:
                    sender_name = getattr(
                        settings, "BREVO_SENDER_NAME", "GrowthSathi"
                    )

                payload = {
                    "sender": {
                        "name": sender_name,
                        "email": sender_email,
                    },
                    "to": [{"email": address} for address in message.to],
                    "subject": message.subject,
                    "textContent": message.body,
                }

                if message.cc:
                    payload["cc"] = [{"email": address} for address in message.cc]

                if message.bcc:
                    payload["bcc"] = [{"email": address} for address in message.bcc]

                request = Request(
                    self.API_URL,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "accept": "application/json",
                        "api-key": api_key,
                        "content-type": "application/json",
                    },
                    method="POST",
                )

                with urlopen(request, timeout=15) as response:
                    if 200 <= response.status < 300:
                        sent_count += 1

            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                if self.fail_silently:
                    continue
                raise RuntimeError(f"Brevo email API failed: {exc}") from exc

        return sent_count