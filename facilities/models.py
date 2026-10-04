from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class FacilityType(models.Model):
    """
    Categorizes campus facilities (e.g., Classroom, Laboratory, Auditorium, Conference Room).
    Normalizes facility classification across DSSC campus.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text='Unique name of the facility category (e.g., Computer Laboratory, Auditorium).',
    )
    description = models.TextField(
        blank=True,
        default='',
        help_text='Optional summary of what this category encompasses.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Timestamp when this facility type was created.',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text='Timestamp when this facility type was last updated.',
    )

    class Meta:
        verbose_name = 'Facility Type'
        verbose_name_plural = 'Facility Types'
        ordering = ['name']

    def __str__(self):
        return self.name


class Facility(models.Model):
    """
    Represents a specific physical facility or venue at DSSC that can be reserved.
    """

    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        UNAVAILABLE = 'UNAVAILABLE', 'Unavailable'
        MAINTENANCE = 'MAINTENANCE', 'Under Maintenance'

    facility_type = models.ForeignKey(
        FacilityType,
        on_delete=models.PROTECT,
        related_name='facilities',
        help_text='Category of this facility. Protected from deletion if facilities exist.',
    )
    name = models.CharField(
        max_length=150,
        unique=True,
        help_text='Unique facility name or room identifier (e.g., IT ComLab 1, DSSC Gymnasium).',
    )
    location = models.CharField(
        max_length=200,
        help_text='Physical campus location (e.g., Admin Building 2nd Floor, Main Campus Ground).',
    )
    capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(1, message='Capacity must be at least 1 person.')],
        help_text='Maximum seating or occupant capacity. Must be at least 1.',
    )
    description = models.TextField(
        blank=True,
        default='',
        help_text='Details on amenities, equipment, projectors, or special usage policies.',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
        help_text='Current physical operational status (AVAILABLE, UNAVAILABLE, MAINTENANCE).',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Timestamp when this facility was registered.',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text='Timestamp when this facility details were last updated.',
    )

    class Meta:
        verbose_name = 'Facility'
        verbose_name_plural = 'Facilities'
        ordering = ['name']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(capacity__gt=0),
                name='facility_capacity_gt_zero',
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.location}) - Cap: {self.capacity}"

    @property
    def is_operational(self):
        """Returns True if the facility is physically available for reservations."""
        return self.status == self.Status.AVAILABLE


class FacilityMaintenance(models.Model):
    """
    Represents a scheduled maintenance window for a specific facility.

    Distinct from Facility.status (permanent operational gate):
    - Facility.status = MAINTENANCE  → facility is globally unavailable indefinitely
    - FacilityMaintenance (SCHEDULED) → facility is blocked only during a specific
      date/time window; the facility may still be reservable outside that window

    Both mechanisms coexist and are enforced independently:
    - Facility.status is checked in Reservation.clean() step 4
    - FacilityMaintenance is checked in Reservation.clean() step 6

    Lifecycle: SCHEDULED → COMPLETED or CANCELLED (both terminal)
    Only SCHEDULED records actively block reservation slots.
    """

    class Status(models.TextChoices):
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    # Only SCHEDULED records block reservation time slots.
    # COMPLETED and CANCELLED are historical records only.
    BLOCKING_STATUSES = [Status.SCHEDULED]

    facility = models.ForeignKey(
        Facility,
        on_delete=models.PROTECT,
        related_name='maintenance_records',
        help_text=(
            'Facility this maintenance window applies to. '
            'PROTECT: a facility cannot be deleted while maintenance records exist.'
        ),
    )
    title = models.CharField(
        max_length=200,
        help_text='Short description of the maintenance work (e.g. "Annual electrical inspection").',
    )
    description = models.TextField(
        blank=True,
        default='',
        help_text='Optional details about the maintenance scope, technicians, or notes.',
    )
    maintenance_date = models.DateField(
        help_text='Date on which the maintenance window occurs.',
    )
    start_time = models.TimeField(
        help_text='Start time of the maintenance window.',
    )
    end_time = models.TimeField(
        help_text='End time of the maintenance window (must be later than start time).',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
        help_text='Current lifecycle status of this maintenance record.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_maintenance_records',
        help_text=(
            'Staff or Admin who scheduled this maintenance. '
            'Retained as null if the user account is later deleted.'
        ),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Timestamp when this maintenance record was created.',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text='Timestamp when this maintenance record was last updated.',
    )

    class Meta:
        verbose_name = 'Facility Maintenance'
        verbose_name_plural = 'Facility Maintenance Records'
        ordering = ['-maintenance_date', '-start_time']
        constraints = [
            # Database-level guard: end_time must always be strictly after start_time.
            # Mirrors the equivalent constraint on the Reservation model.
            # Even if clean() is bypassed, the DB refuses the write.
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F('start_time')),
                name='maintenance_end_after_start',
            ),
        ]
        indexes = [
            # Composite index mirroring res_fac_date_status_idx on Reservation.
            # Supports the overlap query: facility_id = X AND maintenance_date = Y AND status = SCHEDULED
            models.Index(
                fields=['facility', 'maintenance_date', 'status'],
                name='maint_fac_date_status_idx',
            ),
        ]

    def __str__(self):
        return (
            f"Maintenance: {self.facility.name} on {self.maintenance_date} "
            f"({self.start_time.strftime('%H:%M')} \u2013 {self.end_time.strftime('%H:%M')}) "
            f"[{self.get_status_display()}]"
        )

    # ------------------------------------------------------------------
    # Status check convenience properties
    # ------------------------------------------------------------------

    @property
    def is_scheduled(self):
        """Returns True if this maintenance window is still scheduled (active)."""
        return self.status == self.Status.SCHEDULED

    @property
    def is_completed(self):
        """Returns True if this maintenance has been marked completed."""
        return self.status == self.Status.COMPLETED

    @property
    def is_cancelled(self):
        """Returns True if this maintenance window was cancelled."""
        return self.status == self.Status.CANCELLED

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self):
        """
        Validate maintenance record business rules before every save.

        Rules:
        1. Title must not be blank.
        2. end_time must be strictly after start_time.
        3. (Only when SCHEDULED) Must not overlap another SCHEDULED maintenance
           on the same facility and date.
        4. (Only when SCHEDULED) Must not conflict with an existing blocking
           reservation (PENDING or APPROVED) on the same facility and date.
           Policy: reject the maintenance creation; do NOT cancel the reservation.

        Deferred imports inside this method avoid a circular import:
        facilities.models is imported by reservations.models at module level,
        so facilities.models must NOT import from reservations.models at the
        top of the file — only inside a function body at call time.
        """
        super().clean()
        errors = {}

        # 1. Title validation
        if not self.title or not self.title.strip():
            errors['title'] = 'A title describing the maintenance work is required.'

        # 2. Time range: end_time must be strictly after start_time
        if self.start_time and self.end_time:
            if self.end_time <= self.start_time:
                errors['end_time'] = 'End time must be later than start time.'

        # 3 & 4. Scheduling conflicts — only relevant when status is SCHEDULED
        if self.status in self.BLOCKING_STATUSES:
            if self.facility_id and self.maintenance_date and self.start_time and self.end_time:

                # 3. Overlapping SCHEDULED maintenance on same facility/date
                overlapping_maintenance = FacilityMaintenance.objects.filter(
                    facility_id=self.facility_id,
                    maintenance_date=self.maintenance_date,
                    status=self.Status.SCHEDULED,
                    start_time__lt=self.end_time,
                    end_time__gt=self.start_time,
                )
                if self.pk:
                    overlapping_maintenance = overlapping_maintenance.exclude(pk=self.pk)

                if overlapping_maintenance.exists():
                    conflict = overlapping_maintenance.first()
                    errors['__all__'] = (
                        f'Overlaps with an existing scheduled maintenance window '
                        f'({conflict.start_time.strftime("%H:%M")} \u2013 '
                        f'{conflict.end_time.strftime("%H:%M")}).'
                    )

                # 4. Conflict with existing blocking reservations
                if '__all__' not in errors:
                    from reservations.models import Reservation
                    blocking_reservations = Reservation.objects.filter(
                        facility_id=self.facility_id,
                        reservation_date=self.maintenance_date,
                        status__in=Reservation.BLOCKING_STATUSES,
                        start_time__lt=self.end_time,
                        end_time__gt=self.start_time,
                    )
                    if blocking_reservations.exists():
                        conflict = blocking_reservations.first()
                        errors['__all__'] = (
                            f'Cannot schedule maintenance. An existing '
                            f'{conflict.get_status_display().lower()} reservation '
                            f'({conflict.start_time.strftime("%H:%M")} \u2013 '
                            f'{conflict.end_time.strftime("%H:%M")}) '
                            f'conflicts with this window.'
                        )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """
        Always run full_clean() before saving to the database.

        full_clean() calls:
          1. clean_fields()     — per-field validation (max_length, blank, etc.)
          2. clean()            — our custom business rules above
          3. validate_unique()  — uniqueness constraints
          4. validate_constraints() — model-level Meta constraints (CheckConstraint etc.)

        Mirrors the identical pattern on Reservation.save().
        """
        self.full_clean()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Lifecycle methods
    # ------------------------------------------------------------------

    def complete(self):
        """
        Mark this maintenance window as completed.
        Only valid when current status is SCHEDULED.
        """
        if self.status != self.Status.SCHEDULED:
            raise ValidationError('Only scheduled maintenance can be marked as completed.')
        self.status = self.Status.COMPLETED
        self.save()

    def cancel(self):
        """
        Cancel this scheduled maintenance window.
        Only valid when current status is SCHEDULED.
        """
        if self.status != self.Status.SCHEDULED:
            raise ValidationError('Only scheduled maintenance can be cancelled.')
        self.status = self.Status.CANCELLED
        self.save()
