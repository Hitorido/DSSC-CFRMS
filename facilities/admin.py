from django.contrib import admin
from .models import Facility, FacilityMaintenance, FacilityType


@admin.register(FacilityType)
class FacilityTypeAdmin(admin.ModelAdmin):
    """Admin configuration for facility categories."""
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('name',)


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    """Admin configuration for individual campus facilities."""
    list_display = (
        'name',
        'capacity',
        'equipment_truncated',
        'status',
    )
    list_filter = ('facility_type', 'status', 'noise_level', 'has_wheelchair_access')
    search_fields = ('name', 'location', 'description', 'building_code')
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at', 'avg_reservation_duration_display')

    fieldsets = (
        ('Basic Information', {
            'fields': ('facility_type', 'name', 'location', 'status')
        }),
        ('Details', {
            'fields': ('capacity', 'description', 'noise_level', 'has_wheelchair_access')
        }),
        ('Equipment & Amenities', {
            'fields': ('equipment_list', 'hours_of_operation')
        }),
        ('Location', {
            'fields': ('floor_number', 'building_code')
        }),
        ('Computed Analytics', {
            'fields': ('avg_reservation_duration_display',),
            'description': 'Read-only values computed from reservation data'
        }),
        ('System', {
            'fields': ('created_at', 'updated_at', 'is_synthetic'),
            'classes': ('collapse',)
        }),
    )

    def equipment_truncated(self, obj):
        """Display truncated equipment list in list view."""
        if obj.equipment_list:
            text = obj.equipment_list[:50]
            if len(obj.equipment_list) > 50:
                text += '...'
            return text
        return '(none)'
    equipment_truncated.short_description = 'Equipment'

    def avg_reservation_duration_display(self, obj):
        """Display average reservation duration in admin."""
        duration = obj.avg_reservation_duration
        if duration is None:
            return '(no reservations)'
        hours = duration.total_seconds() / 3600
        minutes = (duration.total_seconds() % 3600) / 60
        if hours == 0:
            return f'{int(minutes)} minutes'
        elif minutes == 0:
            return f'{int(hours)} hours'
        else:
            return f'{int(hours)}h {int(minutes)}m'
    avg_reservation_duration_display.short_description = 'Avg Reservation Duration'
    avg_reservation_duration_display.allow_tags = True


@admin.register(FacilityMaintenance)
class FacilityMaintenanceAdmin(admin.ModelAdmin):
    """Admin configuration for facility maintenance windows."""
    list_display = (
        'pk',
        'facility',
        'title',
        'maintenance_date',
        'start_time',
        'end_time',
        'status',
        'created_by',
        'created_at',
    )
    list_filter = ('status', 'facility', 'maintenance_date')
    search_fields = ('title', 'description', 'facility__name')
    ordering = ('-maintenance_date', '-start_time')
    readonly_fields = ('created_by', 'created_at', 'updated_at')
    date_hierarchy = 'maintenance_date'

    def save_model(self, request, obj, form, change):
        """Assign created_by from the logged-in admin user on creation."""
        if not change and obj.created_by is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
