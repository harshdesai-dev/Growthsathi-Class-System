import hmac

from django.conf import settings

from .models import InstituteDomain


class TenantContextMiddleware:
    """
    Resolve GrowthSathi platform/institute context from a trusted hostname.

    Normal requests use Django's validated Host header.

    When requests arrive through the trusted Next.js/Vercel proxy, the
    original public frontend hostname may be supplied through
    X-GrowthSathi-Host. That hostname is trusted only when the accompanying
    X-GrowthSathi-Proxy-Secret matches PROXY_TENANT_SECRET.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.institute = None
        request.platform_context = False
        request.public_hostname = None

        if request.path.startswith("/api/"):
            # Default to Django's validated upstream host.
            hostname = (
                request.get_host()
                .split(":", 1)[0]
                .lower()
                .rstrip(".")
            )

            # The browser-facing hostname is forwarded by the trusted
            # Next.js proxy using private application-specific headers.
            forwarded_host = request.headers.get(
                "X-GrowthSathi-Host",
                "",
            )

            forwarded_secret = request.headers.get(
                "X-GrowthSathi-Proxy-Secret",
                "",
            )

            configured_secret = getattr(
                settings,
                "PROXY_TENANT_SECRET",
                "",
            )

            # Trust the forwarded hostname only when the shared proxy
            # secret is configured and matches securely.
            if (
                configured_secret
                and forwarded_secret
                and hmac.compare_digest(
                    forwarded_secret,
                    configured_secret,
                )
            ):
                candidate_hostname = (
                    forwarded_host
                    .split(":", 1)[0]
                    .strip()
                    .lower()
                    .rstrip(".")
                )

                if candidate_hostname:
                    hostname = candidate_hostname

            # Save the trusted public-facing hostname for code that needs
            # to generate links back to the frontend, such as password
            # recovery and account activation emails.
            request.public_hostname = hostname

            request.platform_context = (
                hostname in settings.PLATFORM_HOSTS
            )

            if not request.platform_context:
                domain = (
                    InstituteDomain.objects
                    .select_related("institute")
                    .filter(
                        hostname=hostname,
                        is_active=True,
                        is_verified=True,
                        institute__is_active=True,
                    )
                    .first()
                )

                if domain:
                    request.institute = domain.institute

        response = self.get_response(request)

        if request.path.startswith("/api/"):
            response["Cache-Control"] = "no-store, private"

        return response