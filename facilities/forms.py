from django import forms

from .models import Facility, FacilityType


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
        fields = ('name', 'location', 'capacity', 'status', 'description')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
        labels = {
            'name': 'Facility name',
            'location': 'Location',
            'capacity': 'Capacity',
            'status': 'Availability',
            'description': 'Description',
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
