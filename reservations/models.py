from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from facilities.models import Facility


class Reservation(models.Model):
    """
    Core reservation model managing bookings of campus facilities.
    Includes conflict detection, status lifecycle, and review tracking.
    """

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        CANCELLED = 'CANCELLED', 'Cancelled'

    # The statuses that physically hold/block a time slot on the facility schedule
    BLOCKING_STATUSES = [Status.APPROVED, Status.PENDING]

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='requested_reservations',
        help_text='User who submitted the reservation request.',
    )
    facility = models.ForeignKey(
        Facility,
        on_delete=models.CASCADE,
        related_name='reservations',
        help_text='Facility being requested.',
    )
    purpose = models.CharField(
        max_length=255,
        help_text='Stated objective or event for this reservation.',
    )
    reservation_date = models.DateField(
        help_text='Date when the facility is to be used.',
    )
    start_time = models.TimeField(
        help_text='Start time of the reservation.',
    )
    end_time = models.TimeField(
        help_text='End time of the reservation (must be later than start time).',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text='Current reservation lifecycle status.',
    )

    # Reviewer tracking (optional until staff/admin action)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='reviewed_reservations',
        help_text='Staff or Admin who approved or rejected this reservation.',
    )
    reviewed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text='Timestamp when the reservation was approved or rejected.',
    )
    rejection_reason = models.TextField(
        blank=True,
        default='',
        help_text='Explanation provided by staff/admin if rejected.',
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Timestamp when the reservation request was submitted.',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text='Timestamp when this record was last modified.',
    )

    class Meta:
        verbose_name = 'Reservation'
        verbose_name_plural = 'Reservations'
        ordering = ['-reservation_date', '-start_time']
        constraints = [
            # In-row constraint: end_time must be strictly greater than start_time
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F('start_time')),
                name='reservation_end_after_start',
            ),
        ]
        indexes = [
            # Composite index supporting frequent conflict detection queries:
            # WHERE facility_id = X AND reservation_date = Y AND status IN (...)
            models.Index(
                fields=['facility', 'reservation_date', 'status'],
                name='res_fac_date_status_idx',
            ),
        ]

    def __str__(self):
        return (
            f"Reservation #{self.pk or 'New'}: {self.facility.name} on "
            f"{self.reservation_date} ({self.start_time.strftime('%H:%M')} - "
            f"{self.end_time.strftime('%H:%M')}) [{self.get_status_display()}]"
        )

    # Status check properties
    @property
    def is_pending(self):
        return self.status == self.Status.PENDING

    @property
    def is_approved(self):
        return self.status == self.Status.APPROVED

    @property
    def is_rejected(self):
        return self.status == self.Status.REJECTED

    @property
    def is_cancelled(self):
        return self.status == self.Status.CANCELLED

    def clean(self):
        """
        Validate business rules prior to saving.
        Called automatically by Django Forms and Admin.
        """
        super().clean()
        errors = {}

        # 1. Purpose validation
        if not self.purpose or not self.purpose.strip():
            errors['purpose'] = 'A specific purpose for the reservation must be provided.'

        # 2. Time range validation: end_time must be strictly after start_time
        if self.start_time and self.end_time:
            if self.end_time <= self.start_time:
                errors['end_time'] = 'End time must be later than start time.'

        # 3. Date validation: Cannot book a past date for a new reservation
        if self.reservation_date:
            today = timezone.localdate()
            if self._state.adding and self.reservation_date < today:
                errors['reservation_date'] = 'Reservation date cannot be in the past.'

        # 4. Facility operational status check: Facility must be AVAILABLE for new requests
        if self.facility_id:
            try:
                facility = self.facility
                if self._state.adding and facility.status != Facility.Status.AVAILABLE:
                    errors['facility'] = (
                        f'Cannot request reservation. Facility "{facility.name}" is currently '
                        f'{facility.get_status_display().lower()} for use.'
                    )
            except Facility.DoesNotExist:
                errors['facility'] = 'Selected facility does not exist.'

        # 5. Conflict detection: Check for overlapping bookings
        if self.facility_id and self.reservation_date and self.start_time and self.end_time:
            if self.status in self.BLOCKING_STATUSES:
                # Interval overlap: new_start < existing_end AND new_end > existing_start
                overlapping = Reservation.objects.filter(
                    facility=self.facility,
                    reservation_date=self.reservation_date,
                    status__in=self.BLOCKING_STATUSES,
                    start_time__lt=self.end_time,
                    end_time__gt=self.start_time,
                )
                if self.pk:
                    overlapping = overlapping.exclude(pk=self.pk)

                if overlapping.exists():
                    conflict = overlapping.first()
                    errors['__all__'] = (
                        f'Time slot conflicts with an existing {conflict.get_status_display().lower()} '
                        f'reservation ({conflict.start_time.strftime("%H:%M")} - '
                        f'{conflict.end_time.strftime("%H:%M")}).'
                    )

        # 6. Maintenance conflict detection
        #    Reject the reservation if its time slot overlaps a SCHEDULED maintenance window.
        #    COMPLETED and CANCELLED maintenance do not block — only SCHEDULED does.
        #    Adjacent slots (touching exactly at boundary) remain allowed, consistent with
        #    the existing reservation conflict policy (strict < and >).
        #
        #    Deferred import: facilities.models is imported by this module at the top level
        #    (via `from facilities.models import Facility`). Importing FacilityMaintenance
        #    here inside the function body avoids a circular import at module load time.
        if self.facility_id and self.reservation_date and self.start_time and self.end_time:
            if self.status in self.BLOCKING_STATUSES:
                if '__all__' not in errors:
                    from facilities.models import FacilityMaintenance
                    conflicting_maintenance = FacilityMaintenance.objects.filter(
                        facility_id=self.facility_id,
                        maintenance_date=self.reservation_date,
                        status=FacilityMaintenance.Status.SCHEDULED,
                        start_time__lt=self.end_time,
                        end_time__gt=self.start_time,
                    )
                    if conflicting_maintenance.exists():
                        m = conflicting_maintenance.first()
                        errors['__all__'] = (
                            f'The facility has scheduled maintenance during this time '
                            f'({m.start_time.strftime("%H:%M")} \u2013 '
                            f'{m.end_time.strftime("%H:%M")}). '
                            f'Please choose a different time slot.'
                        )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """
        Ensure model clean() validation is always enforced before saving to the database,
        even during direct ORM calls.
        """
        self.full_clean()
        super().save(*args, **kwargs)

    # Workflow methods
    def approve(self, reviewer):
        """
        Approve the pending reservation and record reviewer details.
        """
        if self.status != self.Status.PENDING:
            raise ValidationError('Only pending reservations can be approved.')
        self.status = self.Status.APPROVED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save()

    def reject(self, reviewer, reason):
        """
        Reject the pending reservation, record reviewer details and rejection reason.
        """
        if self.status != self.Status.PENDING:
            raise ValidationError('Only pending reservations can be rejected.')
        if not reason or not reason.strip():
            raise ValidationError('A rejection reason is required when rejecting a reservation.')
        self.status = self.Status.REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason.strip()
        self.save()

    def cancel(self):
        """
        Cancel an existing reservation (PENDING or APPROVED), releasing the time slot.
        """
        if self.status in [self.Status.REJECTED, self.Status.CANCELLED]:
            raise ValidationError('Cannot cancel a reservation that is already rejected or cancelled.')
        self.status = self.Status.CANCELLED
        self.save()
