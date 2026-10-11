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
        'facility_type',
        'location',
        'capacity',
        'status',
        'updated_at',
    )
    list_filter = ('facility_type', 'status')
    search_fields = ('name', 'location', 'description')
    ordering = ('name',)


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
