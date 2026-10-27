from django import forms
from .models import Facility, FacilityMaintenance, FacilityType


class FacilityCreateForm(forms.ModelForm):
    facility_type_name = forms.CharField(
        label='Facility type',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'list': 'facilityTypeSuggestions',
            'placeholder': 'Choose or enter a type',
        }),
        help_text='Choose a suggested type or enter a new one.',
    )

    class Meta:
        model = Facility
        fields = (
            'name', 'location', 'capacity', 'status', 'description',
            'equipment_list', 'hours_of_operation', 'noise_level',
            'floor_number', 'building_code', 'has_wheelchair_access'
        )
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'equipment_list': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Comma-separated list (e.g., Projector, Whiteboard, A/C)'
            }),
            'hours_of_operation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 8am-6pm weekdays, 9am-5pm weekends'
            }),
            'noise_level': forms.Select(attrs={'class': 'form-select'}),
            'floor_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'building_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., ADMIN, SCI, MAIN'
            }),
            'has_wheelchair_access': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'Facility name',
            'location': 'Location',
            'capacity': 'Capacity',
            'status': 'Availability',
            'description': 'Description',
            'equipment_list': 'Equipment',
            'hours_of_operation': 'Hours of operation',
            'noise_level': 'Noise level',
            'floor_number': 'Floor number',
            'building_code': 'Building code',
            'has_wheelchair_access': 'Wheelchair accessible',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.facility_types = FacilityType.objects.order_by('name')

    def clean_facility_type_name(self):
        return self.cleaned_data['facility_type_name'].strip()

    def save(self, commit=True):
        facility = super().save(commit=False)
        type_name = self.cleaned_data['facility_type_name']
        facility.facility_type = FacilityType.objects.filter(name__iexact=type_name).first()
        if facility.facility_type is None:
            facility.facility_type = FacilityType.objects.create(name=type_name)
        if commit:
            facility.save()
        return facility


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
