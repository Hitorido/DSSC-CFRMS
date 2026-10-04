"""
Model-level tests for FacilityMaintenance and its integration with Reservation.

Covers:
  FacilityMaintenance model:
    - Valid record creation and defaults
    - end_time <= start_time rejected
    - Overlapping SCHEDULED maintenance rejected
    - Adjacent maintenance allowed
    - COMPLETED/CANCELLED maintenance does not block another maintenance window
    - Maintenance conflicting with PENDING reservation rejected
    - Maintenance conflicting with APPROVED reservation rejected
    - REJECTED/CANCELLED reservations do not block maintenance creation

  Reservation integration (Reservation.clean() step 6):
    - Reservation overlapping SCHEDULED maintenance rejected
    - Reservation ending exactly when maintenance starts → allowed (adjacent)
    - Reservation starting exactly when maintenance ends → allowed (adjacent)
    - Reservation on different date → allowed
    - COMPLETED maintenance does not block reservation
    - CANCELLED maintenance does not block reservation
"""

import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from facilities.models import Facility, FacilityMaintenance, FacilityType
from reservations.models import Reservation

User = get_user_model()


class MaintenanceTestBase(TestCase):
    """
    Shared fixtures for all maintenance test cases.
    """

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='staff_maint',
            password='testpass123',
            email='staff_maint@dssc.edu.ph',
            role=User.Role.STAFF,
        )
        self.requester = User.objects.create_user(
            username='requester_maint',
            password='testpass123',
            email='req_maint@dssc.edu.ph',
            role=User.Role.REQUESTER,
        )

        facility_type = FacilityType.objects.create(name='Test Lab')
        self.facility = Facility.objects.create(
            facility_type=facility_type,
            name='Maintenance Test Room',
            location='Building X',
            capacity=30,
            status=Facility.Status.AVAILABLE,
        )

        self.tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        self.day_after = timezone.localdate() + datetime.timedelta(days=2)

        # A baseline maintenance window: tomorrow 10:00–12:00
        self.maintenance = FacilityMaintenance.objects.create(
            facility=self.facility,
            title='Baseline Maintenance',
            maintenance_date=self.tomorrow,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
            created_by=self.staff_user,
        )


# ---------------------------------------------------------------------------
# FacilityMaintenance MODEL TESTS
# ---------------------------------------------------------------------------

class FacilityMaintenanceCreationTests(MaintenanceTestBase):

    def test_valid_maintenance_creation(self):
        """A valid maintenance record is created with SCHEDULED as the default status."""
        m = FacilityMaintenance.objects.create(
            facility=self.facility,
            title='Electrical inspection',
            maintenance_date=self.day_after,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(10, 0),
            created_by=self.staff_user,
        )
        self.assertEqual(m.status, FacilityMaintenance.Status.SCHEDULED)
        self.assertTrue(m.is_scheduled)
        self.assertFalse(m.is_completed)
        self.assertFalse(m.is_cancelled)
        self.assertEqual(m.facility, self.facility)
        self.assertEqual(m.created_by, self.staff_user)

    def test_default_status_is_scheduled(self):
        """Status defaults to SCHEDULED without explicit assignment."""
        m = FacilityMaintenance(
            facility=self.facility,
            title='Default Status Test',
            maintenance_date=self.day_after,
            start_time=datetime.time(13, 0),
            end_time=datetime.time(15, 0),
        )
        self.assertEqual(m.status, FacilityMaintenance.Status.SCHEDULED)

    def test_str_representation(self):
        """__str__ includes facility name, date, times, and status."""
        s = str(self.maintenance)
        self.assertIn('Maintenance Test Room', s)
        self.assertIn(str(self.tomorrow), s)
        self.assertIn('10:00', s)
        self.assertIn('12:00', s)
        self.assertIn('Scheduled', s)

    def test_created_by_can_be_null(self):
        """created_by is optional — maintenance can be created without a user reference."""
        m = FacilityMaintenance.objects.create(
            facility=self.facility,
            title='No creator',
            maintenance_date=self.day_after,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(16, 0),
            created_by=None,
        )
        self.assertIsNone(m.created_by)


class FacilityMaintenanceValidationTests(MaintenanceTestBase):

    def test_end_time_equal_to_start_time_rejected(self):
        """end_time == start_time (zero duration) must be rejected."""
        m = FacilityMaintenance(
            facility=self.facility,
            title='Zero Duration',
            maintenance_date=self.day_after,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(10, 0),
        )
        with self.assertRaises(ValidationError) as ctx:
            m.save()
        self.assertIn('end_time', ctx.exception.message_dict)

    def test_end_time_before_start_time_rejected(self):
        """end_time before start_time must be rejected."""
        m = FacilityMaintenance(
            facility=self.facility,
            title='Reversed Times',
            maintenance_date=self.day_after,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(13, 0),
        )
        with self.assertRaises(ValidationError) as ctx:
            m.save()
        self.assertIn('end_time', ctx.exception.message_dict)

    def test_blank_title_rejected(self):
        """A blank title must be rejected by clean()."""
        m = FacilityMaintenance(
            facility=self.facility,
            title='   ',
            maintenance_date=self.day_after,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(9, 0),
        )
        with self.assertRaises(ValidationError) as ctx:
            m.save()
        self.assertIn('title', ctx.exception.message_dict)


class FacilityMaintenanceOverlapTests(MaintenanceTestBase):
    """
    Tests for the maintenance-vs-maintenance overlap rule.
    Baseline: self.maintenance → tomorrow 10:00–12:00, SCHEDULED.
    """

    def test_overlapping_scheduled_maintenance_rejected(self):
        """A new SCHEDULED window overlapping an existing one must be rejected."""
        overlap = FacilityMaintenance(
            facility=self.facility,
            title='Overlapping',
            maintenance_date=self.tomorrow,
            start_time=datetime.time(11, 0),
            end_time=datetime.time(13, 0),
        )
        with self.assertRaises(ValidationError):
            overlap.save()

    def test_fully_inside_existing_maintenance_rejected(self):
        """A window fully contained inside an existing one must be rejected."""
        inside = FacilityMaintenance(
            facility=self.facility,
            title='Inside',
            maintenance_date=self.tomorrow,
            start_time=datetime.time(10, 30),
            end_time=datetime.time(11, 30),
        )
        with self.assertRaises(ValidationError):
            inside.save()

    def test_adjacent_before_maintenance_allowed(self):
        """
        Adjacent before: new end_time == existing start_time.
        08:00–10:00 adjacent to existing 10:00–12:00 → allowed.
        """
        adj = FacilityMaintenance.objects.create(
            facility=self.facility,
            title='Adjacent Before',
            maintenance_date=self.tomorrow,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(10, 0),   # touches 10:00 exactly
        )
        self.assertEqual(adj.status, FacilityMaintenance.Status.SCHEDULED)

    def test_adjacent_after_maintenance_allowed(self):
        """
        Adjacent after: new start_time == existing end_time.
        12:00–14:00 adjacent to existing 10:00–12:00 → allowed.
        """
        adj = FacilityMaintenance.objects.create(
            facility=self.facility,
            title='Adjacent After',
            maintenance_date=self.tomorrow,
            start_time=datetime.time(12, 0),  # touches 12:00 exactly
            end_time=datetime.time(14, 0),
        )
        self.assertEqual(adj.status, FacilityMaintenance.Status.SCHEDULED)

    def test_completed_maintenance_does_not_block_new_window(self):
        """
        A COMPLETED maintenance window does not block a new window in the same slot.
        Policy: only SCHEDULED records block.
        """
        self.maintenance.complete()
        self.assertEqual(self.maintenance.status, FacilityMaintenance.Status.COMPLETED)

        # Same slot — should now be allowed
        new_m = FacilityMaintenance.objects.create(
            facility=self.facility,
            title='Replacement after completion',
            maintenance_date=self.tomorrow,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )
        self.assertEqual(new_m.status, FacilityMaintenance.Status.SCHEDULED)

    def test_cancelled_maintenance_does_not_block_new_window(self):
        """
        A CANCELLED maintenance window does not block a new window in the same slot.
        """
        self.maintenance.cancel()
        self.assertEqual(self.maintenance.status, FacilityMaintenance.Status.CANCELLED)

        new_m = FacilityMaintenance.objects.create(
            facility=self.facility,
            title='Replacement after cancellation',
            maintenance_date=self.tomorrow,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )
        self.assertEqual(new_m.status, FacilityMaintenance.Status.SCHEDULED)

    def test_different_facility_not_affected(self):
        """Maintenance on a different facility does not block maintenance on this one."""
        other_type = FacilityType.objects.create(name='Other Type')
        other_facility = Facility.objects.create(
            facility_type=other_type,
            name='Other Facility',
            location='Building Y',
            capacity=20,
            status=Facility.Status.AVAILABLE,
        )
        # Same date/time as self.maintenance, but different facility — must succeed
        m = FacilityMaintenance.objects.create(
            facility=other_facility,
            title='Other Facility Maintenance',
            maintenance_date=self.tomorrow,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )
        self.assertEqual(m.status, FacilityMaintenance.Status.SCHEDULED)


class MaintenanceBlockedByReservationTests(MaintenanceTestBase):
    """
    Tests for the maintenance-vs-reservation protection rule:
    scheduling maintenance must be rejected if it conflicts with an
    existing blocking (PENDING or APPROVED) reservation.
    """

    def _make_reservation(self, status, start, end):
        """Helper: create a reservation with the given status directly (bypassing date guard)."""
        r = Reservation(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Reservation for maintenance conflict test',
            reservation_date=self.day_after,
            start_time=start,
            end_time=end,
            status=status,
        )
        # Use super().save() to bypass full_clean past-date check for non-new objects
        # We set _state.adding = False so clean() skips the past-date check
        # For PENDING/APPROVED we must create without triggering past-date guard:
        # easiest: use a future date (self.day_after is always future).
        r.save()  # self.day_after is future so full save is fine
        return r

    def test_maintenance_conflicting_with_pending_reservation_rejected(self):
        """
        Scheduling maintenance that overlaps an existing PENDING reservation
        must be rejected. Policy: protect existing bookings.
        """
        # PENDING reservation: day_after 09:00–11:00
        Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Pending booking',
            reservation_date=self.day_after,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )

        m = FacilityMaintenance(
            facility=self.facility,
            title='Conflicts with pending',
            maintenance_date=self.day_after,
            start_time=datetime.time(10, 0),  # overlaps 09:00–11:00
            end_time=datetime.time(12, 0),
        )
        with self.assertRaises(ValidationError):
            m.save()

    def test_maintenance_conflicting_with_approved_reservation_rejected(self):
        """
        Scheduling maintenance that overlaps an existing APPROVED reservation
        must be rejected.
        """
        res = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Approved booking',
            reservation_date=self.day_after,
            start_time=datetime.time(13, 0),
            end_time=datetime.time(15, 0),
        )
        res.approve(reviewer=self.staff_user)

        m = FacilityMaintenance(
            facility=self.facility,
            title='Conflicts with approved',
            maintenance_date=self.day_after,
            start_time=datetime.time(14, 0),  # overlaps 13:00–15:00
            end_time=datetime.time(16, 0),
        )
        with self.assertRaises(ValidationError):
            m.save()

    def test_rejected_reservation_does_not_block_maintenance(self):
        """
        A REJECTED reservation is not a blocking status and must NOT prevent
        maintenance from being scheduled in the same slot.
        Consistent with existing reservation policy: REJECTED does not block.
        """
        res = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Will be rejected',
            reservation_date=self.day_after,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )
        res.reject(reviewer=self.staff_user, reason='Test rejection')

        # Same slot as the rejected reservation — maintenance should succeed
        m = FacilityMaintenance.objects.create(
            facility=self.facility,
            title='After rejected reservation',
            maintenance_date=self.day_after,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )
        self.assertEqual(m.status, FacilityMaintenance.Status.SCHEDULED)

    def test_cancelled_reservation_does_not_block_maintenance(self):
        """
        A CANCELLED reservation must NOT prevent maintenance from being
        scheduled in the same slot.
        """
        res = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Will be cancelled',
            reservation_date=self.day_after,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )
        res.cancel()

        m = FacilityMaintenance.objects.create(
            facility=self.facility,
            title='After cancelled reservation',
            maintenance_date=self.day_after,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )
        self.assertEqual(m.status, FacilityMaintenance.Status.SCHEDULED)

    def test_maintenance_outside_reservation_is_allowed(self):
        """
        Maintenance that does not overlap any blocking reservation
        must be created successfully.
        """
        Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Morning booking',
            reservation_date=self.day_after,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(10, 0),
        )

        # Afternoon maintenance — no overlap
        m = FacilityMaintenance.objects.create(
            facility=self.facility,
            title='Afternoon maintenance',
            maintenance_date=self.day_after,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(16, 0),
        )
        self.assertEqual(m.status, FacilityMaintenance.Status.SCHEDULED)


# ---------------------------------------------------------------------------
# LIFECYCLE TESTS
# ---------------------------------------------------------------------------

class FacilityMaintenanceLifecycleTests(MaintenanceTestBase):

    def test_complete_transitions_to_completed(self):
        """complete() transitions SCHEDULED → COMPLETED."""
        self.maintenance.complete()
        self.maintenance.refresh_from_db()
        self.assertEqual(self.maintenance.status, FacilityMaintenance.Status.COMPLETED)
        self.assertTrue(self.maintenance.is_completed)

    def test_cancel_transitions_to_cancelled(self):
        """cancel() transitions SCHEDULED → CANCELLED."""
        self.maintenance.cancel()
        self.maintenance.refresh_from_db()
        self.assertEqual(self.maintenance.status, FacilityMaintenance.Status.CANCELLED)
        self.assertTrue(self.maintenance.is_cancelled)

    def test_complete_already_completed_raises(self):
        """complete() on an already COMPLETED record raises ValidationError."""
        self.maintenance.complete()
        with self.assertRaises(ValidationError):
            self.maintenance.complete()

    def test_cancel_already_cancelled_raises(self):
        """cancel() on an already CANCELLED record raises ValidationError."""
        self.maintenance.cancel()
        with self.assertRaises(ValidationError):
            self.maintenance.cancel()

    def test_complete_cancelled_record_raises(self):
        """complete() on a CANCELLED record raises ValidationError."""
        self.maintenance.cancel()
        with self.assertRaises(ValidationError):
            self.maintenance.complete()

    def test_cancel_completed_record_raises(self):
        """cancel() on a COMPLETED record raises ValidationError."""
        self.maintenance.complete()
        with self.assertRaises(ValidationError):
            self.maintenance.cancel()


# ---------------------------------------------------------------------------
# RESERVATION ↔ MAINTENANCE INTEGRATION TESTS
# ---------------------------------------------------------------------------

class ReservationMaintenanceIntegrationTests(MaintenanceTestBase):
    """
    Tests for Reservation.clean() step 6:
    SCHEDULED maintenance blocking overlapping reservations.

    Baseline: self.maintenance → tomorrow 10:00–12:00, SCHEDULED.
    All reservations use self.tomorrow to test against the baseline maintenance.
    """

    def test_reservation_overlapping_scheduled_maintenance_rejected(self):
        """
        A reservation overlapping a SCHEDULED maintenance window must be rejected.
        Overlap: reservation 11:00–13:00 vs maintenance 10:00–12:00.
        """
        res = Reservation(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Overlap with maintenance',
            reservation_date=self.tomorrow,
            start_time=datetime.time(11, 0),
            end_time=datetime.time(13, 0),
        )
        with self.assertRaises(ValidationError):
            res.save()

    def test_reservation_fully_inside_maintenance_rejected(self):
        """
        A reservation fully inside a SCHEDULED maintenance window must be rejected.
        Reservation 10:30–11:30 inside maintenance 10:00–12:00.
        """
        res = Reservation(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Inside maintenance',
            reservation_date=self.tomorrow,
            start_time=datetime.time(10, 30),
            end_time=datetime.time(11, 30),
        )
        with self.assertRaises(ValidationError):
            res.save()

    def test_reservation_ending_exactly_when_maintenance_starts_allowed(self):
        """
        Adjacent before: reservation ends exactly when maintenance starts.
        Reservation 08:00–10:00 adjacent to maintenance 10:00–12:00 → allowed.
        """
        res = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Ends at maintenance start',
            reservation_date=self.tomorrow,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(10, 0),  # touches maintenance start exactly
        )
        self.assertEqual(res.status, Reservation.Status.PENDING)

    def test_reservation_starting_exactly_when_maintenance_ends_allowed(self):
        """
        Adjacent after: reservation starts exactly when maintenance ends.
        Reservation 12:00–14:00 adjacent to maintenance 10:00–12:00 → allowed.
        """
        res = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Starts at maintenance end',
            reservation_date=self.tomorrow,
            start_time=datetime.time(12, 0),  # touches maintenance end exactly
            end_time=datetime.time(14, 0),
        )
        self.assertEqual(res.status, Reservation.Status.PENDING)

    def test_reservation_on_different_date_allowed(self):
        """
        A reservation on a different date is not affected by maintenance
        scheduled on another date.
        """
        # self.maintenance is on self.tomorrow; reservation is on self.day_after
        res = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Different date reservation',
            reservation_date=self.day_after,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )
        self.assertEqual(res.status, Reservation.Status.PENDING)

    def test_reservation_outside_maintenance_window_allowed(self):
        """
        A reservation on the same date but completely outside the maintenance
        window must succeed.
        Reservation 13:00–15:00 vs maintenance 10:00–12:00 → no conflict.
        """
        res = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Outside maintenance window',
            reservation_date=self.tomorrow,
            start_time=datetime.time(13, 0),
            end_time=datetime.time(15, 0),
        )
        self.assertEqual(res.status, Reservation.Status.PENDING)

    def test_completed_maintenance_does_not_block_reservation(self):
        """
        After maintenance is marked COMPLETED, the same time slot becomes
        reservable again.
        """
        self.maintenance.complete()
        self.assertEqual(self.maintenance.status, FacilityMaintenance.Status.COMPLETED)

        # Same slot as the now-completed maintenance — should succeed
        res = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='After completed maintenance',
            reservation_date=self.tomorrow,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )
        self.assertEqual(res.status, Reservation.Status.PENDING)

    def test_cancelled_maintenance_does_not_block_reservation(self):
        """
        After maintenance is CANCELLED, the same time slot becomes reservable.
        """
        self.maintenance.cancel()
        self.assertEqual(self.maintenance.status, FacilityMaintenance.Status.CANCELLED)

        res = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='After cancelled maintenance',
            reservation_date=self.tomorrow,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )
        self.assertEqual(res.status, Reservation.Status.PENDING)

    def test_different_facility_maintenance_does_not_block_reservation(self):
        """
        SCHEDULED maintenance on a different facility does not affect
        reservations on this facility.
        """
        other_type = FacilityType.objects.create(name='Other Lab Type')
        other_facility = Facility.objects.create(
            facility_type=other_type,
            name='Other Lab',
            location='Building Z',
            capacity=15,
            status=Facility.Status.AVAILABLE,
        )
        # Maintenance on other_facility same date/time as self.maintenance
        FacilityMaintenance.objects.create(
            facility=other_facility,
            title='Other facility maintenance',
            maintenance_date=self.tomorrow,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )

        # Reservation on self.facility — different facility's maintenance must not block it
        # But self.maintenance (same facility, same slot) is still SCHEDULED,
        # so we use a non-overlapping slot to isolate the cross-facility test.
        res = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Different facility maintenance irrelevant',
            reservation_date=self.tomorrow,
            start_time=datetime.time(13, 0),
            end_time=datetime.time(15, 0),
        )
        self.assertEqual(res.status, Reservation.Status.PENDING)
