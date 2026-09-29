from functools import wraps
from django.core.exceptions import PermissionDenied


def role_required(*allowed_roles):
    """
    Decorator for views that checks whether the user has one of the allowed CFRMS roles.

    Behavior:
    - If user is not authenticated: redirect to login (handled by @login_required).
    - If user is authenticated but does not hold an allowed role: raises PermissionDenied (HTTP 403 Forbidden).
    - Note: Django's `is_staff` alone does NOT grant access; only explicit CFRMS `user.role` is checked.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())

            if request.user.role not in allowed_roles:
                raise PermissionDenied("You do not have permission to access this resource.")

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def admin_required(view_func):
    """Decorator ensuring only users with CFRMS ADMIN role can access the view."""
    from .models import User
    return role_required(User.Role.ADMIN)(view_func)


def staff_or_admin_required(view_func):
    """Decorator ensuring only users with CFRMS STAFF or ADMIN role can access the view."""
    from .models import User
    return role_required(User.Role.STAFF, User.Role.ADMIN)(view_func)


def requester_required(view_func):
    """Decorator ensuring only users with CFRMS REQUESTER role can access the view."""
    from .models import User
    return role_required(User.Role.REQUESTER)(view_func)
