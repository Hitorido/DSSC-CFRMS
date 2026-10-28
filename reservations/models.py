from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
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
        COMPLETED = 'COMPLETED', 'Completed'
        REJECTED = 'REJECTED', 'Declined'
        APPEAL = 'APPEAL', 'Appeal'
        CANCELLED = 'CANCELLED', 'Cancelled'

    # The statuses that physically hold/block a time slot on the facility schedule
    BLOCKING_STATUSES = [Status.APPROVED, Status.PENDING]
    MAX_APPEALS = 3

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

    # Reviewer tracking (optional until staff/faculty/admin action)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='reviewed_reservations',
        help_text='Staff, faculty, or Admin who approved or declined this reservation.',
    )
    reviewed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text='Timestamp when the reservation was approved or declined.',
    )
    rejection_reason = models.TextField(
        blank=True,
        default='',
        help_text='Explanation provided by a reviewer when the request is declined.',
    )
    appeal_count = models.PositiveSmallIntegerField(
        default=0,
        editable=False,
        validators=[MaxValueValidator(3)],
        help_text='Number of appeals submitted for this reservation (maximum three).',
    )

    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='completed_reservations',
        help_text='Staff, faculty, or Admin who marked this reservation completed.',
    )
    completed_at = models.DateTimeField(blank=True, null=True)

    is_synthetic = models.BooleanField(
        default=False,
        help_text='True if this record was created by the synthetic data generator.',
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
            models.CheckConstraint(
                condition=models.Q(appeal_count__gte=0, appeal_count__lte=3),
                name='reservation_appeal_limit',
            ),
        ]
        indexes = [
            # Composite index supporting frequent conflict detection queries:
            # WHERE facility_id = X AND reservation_date = Y AND status IN (...)
            models.Index(
                fields=['facility', 'reservation_date', 'status'],
                name='res_fac_date_status_idx',
            ),
            # Index for analytics queries filtering by date and status
            # Supports: WHERE reservation_date = ? AND status IN (...)
            models.Index(
                fields=['reservation_date', 'status'],
                name='res_date_status_idx',
            ),
            # Index for time-series analytics queries
            # Supports: WHERE created_at >= ? AND created_at <= ?
            models.Index(
                fields=['created_at'],
                name='res_created_at_idx',
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

    @property
    def is_completed(self):
        return self.status == self.Status.COMPLETED

    @property
    def can_edit(self):
        """Pending and approved bookings may be edited before they start."""
        if self.status not in self.BLOCKING_STATUSES or not self.reservation_date or not self.start_time:
            return False
        scheduled_start = timezone.make_aware(
            datetime.combine(self.reservation_date, self.start_time),
            timezone.get_current_timezone(),
        )
        return timezone.now() < scheduled_start

    @property
    def appeals_remaining(self):
        return max(0, self.MAX_APPEALS - self.appeal_count)

    @property
    def can_appeal(self):
        return self.is_rejected and self.appeals_remaining > 0

    @property
    def is_appeal(self):
        return self.status == self.Status.APPEAL

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
        
        Also invalidate analytics cache when status changes (Task 13).
        """
        self.full_clean()
        
        # Invalidate analytics cache if status changes
        old_status = None
        if self.pk:
            try:
                old_instance = type(self).objects.get(pk=self.pk)
                old_status = old_instance.status
            except type(self).DoesNotExist:
                pass
        
        # Status changed from old to new
        if old_status and old_status != self.status:
            self._invalidate_analytics_cache()
        
        super().save(*args, **kwargs)
    
    def _invalidate_analytics_cache(self):
        """
        Invalidate analytics cache when reservation status changes.
        
        Triggered when:
        - Reservation created (PENDING status)
        - Reservation approved (PENDING -> APPROVED)
        - Reservation rejected (PENDING -> REJECTED)
        - Reservation cancelled (any status -> CANCELLED)
        - Reservation completed (APPROVED -> COMPLETED)
        
        Cache invalidation helps keep analytics data fresh when
        reservation data changes (Task 13 requirement).
        """
        from django.core.cache import cache
        
        # Invalidate key analytics cache entries
        cache_keys_to_invalidate = [
            'forecast_6_3',  # demand forecast
            'peak_hours',     # peak hours analysis
            'peak_days',      # peak days analysis
            'prescriptive_recommendations',  # recommendations
            'facility_analytics_dashboard',  # dashboard analytics
        ]
        
        for key in cache_keys_to_invalidate:
            cache.delete(key)

    # Workflow methods
    def appeal(self, reason):
        """Resubmit a declined request, counting only successfully saved appeals."""
        reason = (reason or '').strip()
        if not reason or len(reason) > 2000:
            raise ValidationError({'appeal_reason': 'Explain your appeal using between 1 and 2,000 characters.'})
        database = self._state.db or 'default'
        with transaction.atomic(using=database):
            current = type(self).objects.using(database).select_for_update().get(pk=self.pk)
            if not current.is_rejected:
                raise ValidationError('Only declined reservations can be appealed.')
            if not current.can_appeal:
                raise ValidationError('You have used all three appeals for this reservation.')

            now = timezone.localtime()
            if self.reservation_date < now.date():
                raise ValidationError({'reservation_date': 'Choose today or a future date for your appeal.'})
            if self.reservation_date == now.date() and self.start_time <= now.time().replace(tzinfo=None):
                raise ValidationError({'start_time': 'Choose a start time later than the current time.'})
            if self.facility.status != Facility.Status.AVAILABLE:
                raise ValidationError({'facility': 'Choose an available facility for your appeal.'})

            previous_decline_reason = current.rejection_reason
            for field in ('facility_id', 'purpose', 'reservation_date', 'start_time', 'end_time'):
                setattr(current, field, getattr(self, field))
            current.status = self.Status.APPEAL
            current.appeal_count += 1
            current.reviewed_by = None
            current.reviewed_at = None
            current.rejection_reason = ''
            current.completed_by = None
            current.completed_at = None
            current.save(using=database)
            ReservationAppeal.objects.using(database).create(
                reservation=current,
                attempt=current.appeal_count,
                reason=reason,
                previous_decline_reason=previous_decline_reason,
            )
            self.refresh_from_db(using=database)

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

    def complete(self, reviewer):
        """Mark an approved reservation completed after its scheduled end."""
        if self.status != self.Status.APPROVED:
            raise ValidationError('Only approved reservations can be marked completed.')

        scheduled_end = timezone.make_aware(
            datetime.combine(self.reservation_date, self.end_time),
            timezone.get_current_timezone(),
        )
        if timezone.now() < scheduled_end:
            raise ValidationError('A reservation can only be completed after its scheduled end time.')

        self.status = self.Status.COMPLETED
        self.completed_by = reviewer
        self.completed_at = timezone.now()
        self.save()

    def cancel(self):
        """
        Cancel an existing reservation (PENDING or APPROVED), releasing the time slot.
        """
        if self.status in [self.Status.REJECTED, self.Status.CANCELLED, self.Status.COMPLETED]:
            raise ValidationError('Cannot cancel a reservation that is already declined, cancelled, or completed.')
        self.status = self.Status.CANCELLED
        self.save()


class ReservationAppeal(models.Model):
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='appeals')
    attempt = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(3)])
    reason = models.TextField(max_length=2000)
    previous_decline_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-attempt']
        constraints = [
            models.UniqueConstraint(fields=['reservation', 'attempt'], name='appeal_unique_attempt'),
            models.CheckConstraint(
                condition=models.Q(attempt__gte=1, attempt__lte=3),
                name='appeal_attempt_range',
            ),
        ]

    def __str__(self):
        return f'Appeal {self.attempt} for reservation #{self.reservation_id}'
