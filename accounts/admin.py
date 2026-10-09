from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom UserAdmin to properly display CFRMS fields in Django Admin.
    """
    fieldsets = BaseUserAdmin.fieldsets + (
        ('CFRMS Information', {
            'fields': ('role', 'user_type', 'department'),
        }),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('CFRMS Information', {
            'fields': ('role', 'user_type', 'department'),
        }),
    )

    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'role',
        'user_type',
        'department',
        'is_active',
    )
    list_filter = ('role', 'user_type', 'is_active', 'is_staff')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'department')
