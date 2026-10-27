from django import forms
from django.utils import timezone
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

    def clean(self):
        cleaned_data = super().clean()
        if self.instance.pk:
            reservation_date = cleaned_data.get('reservation_date')
            start_time = cleaned_data.get('start_time')
            now = timezone.localtime()
            if reservation_date and reservation_date < now.date():
                self.add_error('reservation_date', 'Choose today or a future date.')
            elif reservation_date == now.date() and start_time and start_time <= now.time().replace(tzinfo=None):
                self.add_error('start_time', 'Choose a start time later than the current time.')
        return cleaned_data

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


class ReservationAppealForm(ReservationForm):
    appeal_reason = forms.CharField(
        label='Reason for appeal',
        max_length=2000,
        strip=True,
        widget=forms.Textarea(attrs={'rows': 4}),
        help_text='Explain why the declined reservation should be reconsidered.',
    )

    class Meta(ReservationForm.Meta):
        fields = ReservationForm.Meta.fields + ['appeal_reason']
