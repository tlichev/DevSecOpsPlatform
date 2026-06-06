from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminOrNetworkEngineer(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        role = getattr(request.user, "profile", None)
        if role is None:
            return False
        return role.role in ("admin", "network_engineer")


class IsAdminOnly(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_superuser or (
            hasattr(request.user, "profile") and request.user.profile.role == "admin"
        )


class ReadOnlyOrAbove(BasePermission):
    """Any authenticated user can read; mutations require network_engineer or admin."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        if request.user.is_superuser:
            return True
        role = getattr(getattr(request.user, "profile", None), "role", None)
        return role in ("admin", "network_engineer")
