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
