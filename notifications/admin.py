from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin configuration for Notification records."""
    list_display = ('pk', 'recipient', 'reservation', 'is_read', 'created_at')
    list_filter = ('is_read',)
    search_fields = ('recipient__username', 'message')
    ordering = ('-created_at',)
    readonly_fields = ('recipient', 'reservation', 'created_at')
