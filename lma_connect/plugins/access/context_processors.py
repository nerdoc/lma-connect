"""Global context — exposes `is_ops` flag so the topbar can show the
Operations-Team wrench icon only to authorised users."""

from .permissions import is_ops as user_is_ops


def is_ops(request):
    """Context-processor (registriert in settings.TEMPLATES als `…context_processors.is_ops`).
    Uses the central role check from `access.permissions`."""
    return {"is_ops": user_is_ops(getattr(request, "user", None))}
