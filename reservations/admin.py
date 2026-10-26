from django.contrib import admin
from .models import Reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    """Admin interface for managing and reviewing facility reservations."""
    list_display = (
        'id',
        'facility',
        'requested_by',
        'reservation_date',
        'start_time',
        'end_time',
        'status',
        'reviewed_by',
        'created_at',
    )
    list_filter = ('status', 'reservation_date', 'facility')
    search_fields = (
        'purpose',
        'facility__name',
        'requested_by__username',
        'requested_by__first_name',
        'requested_by__last_name',
    )
    date_hierarchy = 'reservation_date'
    ordering = ('-reservation_date', '-start_time')
    readonly_fields = ('created_at', 'updated_at')
