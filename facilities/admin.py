from django.contrib import admin
from .models import Facility, FacilityType


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
