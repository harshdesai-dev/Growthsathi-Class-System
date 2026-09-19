from django.http import JsonResponse
from django.views.decorators.http import require_safe


@require_safe
def health(request):
    """Process liveness only; no database details or tenant data."""
    response = JsonResponse({"status": "ok"})
    response["Cache-Control"] = "no-store"
    return response
