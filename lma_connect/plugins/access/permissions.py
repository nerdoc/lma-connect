"""Central role / permission helpers for the ops and organizer frontends.

The single definition of "is ops" and "is organizer staff". Those used to be
defined separately (and slightly differently) in `ops_views.py`, `qr/views.py`
and `access/context_processors.py`; all three import from here now.
"""

from django.contrib.auth.decorators import login_required, user_passes_test

OPS_GROUP_NAME = "Operations Team"


def is_ops(user) -> bool:
    """A member of the operations team (or a superuser)."""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=OPS_GROUP_NAME).exists()


def is_organizer(user) -> bool:
    """Organizer staff: Django staff/admin OR the operations team. Allowed to
    generate QR codes and print badge sheets."""
    return bool(
        getattr(user, "is_authenticated", False)
        and user.is_active
        and (user.is_staff or user.is_superuser or is_ops(user))
    )


def ops_required(view_func):
    """Decorator — verlangt Login + Mitgliedschaft in Operations Team (oder Superuser)."""
    return login_required(user_passes_test(is_ops, login_url="login")(view_func))


def organizer_required(view_func):
    """Decorator — verlangt Login + Organisations-Personal (Staff/Admin/Ops)."""
    return login_required(user_passes_test(is_organizer, login_url="login")(view_func))
