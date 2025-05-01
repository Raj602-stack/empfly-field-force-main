from rest_framework.permissions import BasePermission


class IsTokenAuthenticated(BasePermission):
    """
    Allows access only to Token Authenticated users
    """

    def has_permission(self, request, view):
        if bool(request.auth) or bool(request.user and request.user.is_authenticated):
            return True
        return False
