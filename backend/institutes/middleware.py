from django.conf import settings

from .models import InstituteDomain


class TenantContextMiddleware:
    """Use validated Host, never payload tenant IDs or untrusted forwarded headers."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.institute = None
        request.platform_context = False
        if request.path.startswith("/api/"):
            hostname = request.get_host().split(":", 1)[0].lower().rstrip(".")
            request.platform_context = hostname in settings.PLATFORM_HOSTS
            if not request.platform_context:
                domain = (
                    InstituteDomain.objects.select_related("institute")
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
