"""Permission classes for the REST API.

The HTML views enforce roles through core.views.auth.role_required, but the
API originally used a bare IsAuthenticated everywhere, so any registered
participant could create problems, edit other people's accounts or write their
own contest scores. These classes mirror the role model the site already uses.
"""
from rest_framework import permissions

from .models import UserProfile

PRIVILEGED_ROLES = ('setter', 'admin')


def get_role(user):
    """Return the user's profile role, or None if there isn't one."""
    if user is None or not user.is_authenticated:
        return None
    try:
        return user.userprofile.role
    except (UserProfile.DoesNotExist, AttributeError):
        return None


def is_setter_or_admin(user):
    """True for Django staff and for setter/admin profile roles."""
    if user is None or not user.is_authenticated:
        return False
    return bool(user.is_staff or get_role(user) in PRIVILEGED_ROLES)


class IsSetterOrAdminOrReadOnly(permissions.BasePermission):
    """Anyone may read; only setters and admins may write.

    Used for problems, contests and contest metadata, which are authored
    content rather than user-generated submissions.
    """

    message = 'Only problem setters and admins can modify this resource.'

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return is_setter_or_admin(request.user)


class IsSelfOrStaff(permissions.BasePermission):
    """Object-level write access limited to the account's owner or staff."""

    message = 'You can only modify your own account.'

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_staff:
            return True
        # obj is either a User or something carrying a .user attribute.
        owner = obj if hasattr(obj, 'username') else getattr(obj, 'user', None)
        return owner == request.user
