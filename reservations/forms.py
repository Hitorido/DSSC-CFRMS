from django import forms
from facilities.models import Facility
from .models import Reservation


class ReservationForm(forms.ModelForm):
    """
    ModelForm for REQUESTER-submitted reservation requests.

    Only exposes fields the requester is allowed to fill in.
    Server-controlled fields (requested_by, status, reviewed_by,
    reviewed_at, rejection_reason) are intentionally excluded.

    requested_by is assigned in the view from request.user, never
    from form data, preventing IDOR/ownership forgery.
    """

    def __init__(self, *args, facility_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Reservation.facility is stored in the primary database, so the
        # selectable facilities must come from that same database. Assign the
        # queryset per form instance so current records and status are always
        # used for both rendering and POST validation.
        if facility_queryset is None:
            facility_queryset = Facility.objects.using('default').filter(
                status=Facility.Status.AVAILABLE,
            )
        self.fields['facility'].queryset = facility_queryset.select_related(
            'facility_type',
        ).order_by('name')

    class Meta:
        model = Reservation
        fields = ['facility', 'purpose', 'reservation_date', 'start_time', 'end_time']
        widgets = {
            'reservation_date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }
        labels = {
            'facility': 'Facility',
            'purpose': 'Purpose / Event',
            'reservation_date': 'Date',
            'start_time': 'Start Time',
            'end_time': 'End Time',
        }
