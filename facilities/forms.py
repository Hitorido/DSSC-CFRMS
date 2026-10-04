from django import forms
from .models import FacilityMaintenance


class FacilityMaintenanceForm(forms.ModelForm):
    """
    ModelForm for STAFF/ADMIN-submitted maintenance window requests.

    Only exposes fields the scheduler is allowed to fill in.
    Server-controlled fields (created_by, status, created_at, updated_at)
    are intentionally excluded.

    created_by is assigned in the view from request.user, never from
    form data, preventing ownership forgery.
    status defaults to SCHEDULED via the model field default; it is never
    submitted by the browser.
    """

    class Meta:
        model = FacilityMaintenance
        fields = [
            'facility',
            'title',
            'description',
            'maintenance_date',
            'start_time',
            'end_time',
        ]
        widgets = {
            'maintenance_date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'facility': 'Facility',
            'title': 'Maintenance Title',
            'description': 'Description (optional)',
            'maintenance_date': 'Date',
            'start_time': 'Start Time',
            'end_time': 'End Time',
        }
