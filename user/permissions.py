# user/permissions.py
from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'ADMIN'

class IsManager(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'MANAGER'

class IsCashier(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'CASHIER'

class IsAdminOrManager(BasePermission):
    """
    Custom permission: Only Admin or Manager can register users.
    """

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and (request.user.role == "ADMIN" or request.user.role == "MANAGER")
        )

class CanAccessInventoryPage(BasePermission):
    """Check if user can access the inventory management page (not just view products)"""
    
    def has_permission(self, request, view):
        # Allow access to inventory page only for ADMIN/MANAGER
        return request.user.is_authenticated and request.user.role in ['ADMIN', 'MANAGER']