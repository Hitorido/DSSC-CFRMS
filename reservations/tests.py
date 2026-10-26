import datetime
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from facilities.models import Facility, FacilityType
from .models import Reservation

User = get_user_model()


class ReservationModelTestCase(TestCase):
    """
    Comprehensive test suite for Reservation model validation,
    conflict detection, lifecycle status transitions, and review tracking.
    """

    def setUp(self):
        # Create Requester, Staff, and Admin users
        self.requester = User.objects.create_user(
            username='student1',
            email='student1@dssc.edu.ph',
            password='testpassword123',
            role=User.Role.REQUESTER,
        )
        self.staff_reviewer = User.objects.create_user(
            username='staff1',
            email='staff1@dssc.edu.ph',
            password='testpassword123',
            role=User.Role.STAFF,
        )

        # Create Facility Type and Facilities
        self.facility_type = FacilityType.objects.create(
            name='Auditorium',
            description='Large capacity hall.',
        )
        self.available_facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='DSSC Gymnasium',
            location='Main Campus',
            capacity=1000,
            status=Facility.Status.AVAILABLE,
        )
        self.unavailable_facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='Lecture Hall A',
            location='Building A',
            capacity=80,
            status=Facility.Status.UNAVAILABLE,
        )
        self.maintenance_facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='Audio Visual Room',
            location='Library 2nd Floor',
            capacity=50,
            status=Facility.Status.MAINTENANCE,
        )

        # Reference dates and times
        self.tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        self.time_1000 = datetime.time(10, 0)
        self.time_1200 = datetime.time(12, 0)

    # 1. Creation and default status
    def test_valid_reservation_creation(self):
        """Verify valid reservation creation defaults to PENDING status."""
        res = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='General Assembly',
            reservation_date=self.tomorrow,
            start_time=self.time_1000,
            end_time=self.time_1200,
        )
        self.assertEqual(res.status, Reservation.Status.PENDING)
        self.assertTrue(res.is_pending)
        self.assertFalse(res.is_approved)
        self.assertIsNone(res.reviewed_by)
        self.assertIsNone(res.reviewed_at)
        self.assertEqual(res.rejection_reason, '')

    # 2. Foreign Key relationships
    def test_relationships_to_user_and_facility(self):
        """Verify reverse foreign key queries from User and Facility."""
        res = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Student Meeting',
            reservation_date=self.tomorrow,
            start_time=self.time_1000,
            end_time=self.time_1200,
        )
        self.assertIn(res, self.requester.requested_reservations.all())
        self.assertIn(res, self.available_facility.reservations.all())

    # 3. Time validation
    def test_end_before_start_rejected(self):
        """End time earlier than start time must be rejected."""
        res = Reservation(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Invalid Times',
            reservation_date=self.tomorrow,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(13, 0),
        )
        with self.assertRaises(ValidationError) as ctx:
            res.save()
        self.assertIn('end_time', ctx.exception.message_dict)

    def test_equal_start_end_rejected(self):
        """Equal start time and end time (zero duration) must be rejected."""
        res = Reservation(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Zero Duration',
            reservation_date=self.tomorrow,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(14, 0),
        )
        with self.assertRaises(ValidationError) as ctx:
            res.save()
        self.assertIn('end_time', ctx.exception.message_dict)

    # 4. Date validation
    def test_past_reservation_date_rejected(self):
        """Reservation date in the past must be rejected for a new request."""
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        res = Reservation(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Past Event',
            reservation_date=yesterday,
            start_time=self.time_1000,
            end_time=self.time_1200,
        )
        with self.assertRaises(ValidationError) as ctx:
            res.save()
        self.assertIn('reservation_date', ctx.exception.message_dict)

    # 5. Facility operational status validation
    def test_unavailable_facility_rejected(self):
        """Cannot request booking on a physically UNAVAILABLE facility."""
        res = Reservation(
            requested_by=self.requester,
            facility=self.unavailable_facility,
            purpose='Class Discussion',
            reservation_date=self.tomorrow,
            start_time=self.time_1000,
            end_time=self.time_1200,
        )
        with self.assertRaises(ValidationError) as ctx:
            res.save()
        self.assertIn('facility', ctx.exception.message_dict)

    def test_maintenance_facility_rejected(self):
        """Cannot request booking on a facility undergoing MAINTENANCE."""
        res = Reservation(
            requested_by=self.requester,
            facility=self.maintenance_facility,
            purpose='Film Showing',
            reservation_date=self.tomorrow,
            start_time=self.time_1000,
            end_time=self.time_1200,
        )
        with self.assertRaises(ValidationError) as ctx:
            res.save()
        self.assertIn('facility', ctx.exception.message_dict)

    # 6. Conflict Detection — Overlap Scenarios
    def test_overlapping_reservations_rejected(self):
        """
        Setup existing reservation: 10:00 -> 12:00.
        Test partial overlap: 11:00 -> 13:00 (new_start < existing_end AND new_end > existing_start).
        """
        Reservation.objects.create(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Morning Event',
            reservation_date=self.tomorrow,
            start_time=self.time_1000,
            end_time=self.time_1200,
        )

        overlap_res = Reservation(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Overlapping Event',
            reservation_date=self.tomorrow,
            start_time=datetime.time(11, 0),
            end_time=datetime.time(13, 0),
        )
        with self.assertRaises(ValidationError):
            overlap_res.save()

    def test_reservation_fully_inside_existing_rejected(self):
        """Existing: 10:00 -> 12:00. Proposed: 10:30 -> 11:30 (inside)."""
        Reservation.objects.create(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Morning Event',
            reservation_date=self.tomorrow,
            start_time=self.time_1000,
            end_time=self.time_1200,
        )

        inside_res = Reservation(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Inner Event',
            reservation_date=self.tomorrow,
            start_time=datetime.time(10, 30),
            end_time=datetime.time(11, 30),
        )
        with self.assertRaises(ValidationError):
            inside_res.save()

    def test_reservation_surrounding_existing_rejected(self):
        """Existing: 10:00 -> 12:00. Proposed: 09:00 -> 13:00 (surrounds)."""
        Reservation.objects.create(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Morning Event',
            reservation_date=self.tomorrow,
            start_time=self.time_1000,
            end_time=self.time_1200,
        )

        surround_res = Reservation(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Big Event',
            reservation_date=self.tomorrow,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(13, 0),
        )
        with self.assertRaises(ValidationError):
            surround_res.save()

    def test_adjacent_reservations_allowed(self):
        """
        Existing: 10:00 -> 12:00.
        Allowed: 08:00 -> 10:00 (adjacent before).
        Allowed: 12:00 -> 14:00 (adjacent after).
        """
        Reservation.objects.create(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Midday Event',
            reservation_date=self.tomorrow,
            start_time=self.time_1000,
            end_time=self.time_1200,
        )

        # Adjacent before: finishes exactly when existing begins
        before_res = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Early Event',
            reservation_date=self.tomorrow,
            start_time=datetime.time(8, 0),
            end_time=self.time_1000,
        )
        self.assertEqual(before_res.status, Reservation.Status.PENDING)

        # Adjacent after: starts exactly when existing finishes
        after_res = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Afternoon Event',
            reservation_date=self.tomorrow,
            start_time=self.time_1200,
            end_time=datetime.time(14, 0),
        )
        self.assertEqual(after_res.status, Reservation.Status.PENDING)

    # 7. Status blocking policy verification
    def test_pending_reservation_blocks_overlapping_request(self):
        """
        Verifies policy: PENDING holds the slot so duplicate pending
        requests are prevented.
        """
        pending = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Pending Hold',
            reservation_date=self.tomorrow,
            start_time=self.time_1000,
            end_time=self.time_1200,
        )
        self.assertEqual(pending.status, Reservation.Status.PENDING)

        new_request = Reservation(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Second Requester Overlap',
            reservation_date=self.tomorrow,
            start_time=datetime.time(10, 30),
            end_time=datetime.time(11, 30),
        )
        with self.assertRaises(ValidationError):
            new_request.save()

    def test_rejected_reservation_does_not_block_slot(self):
        """A REJECTED reservation frees the slot so another booking can take it."""
        res = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Will be rejected',
            reservation_date=self.tomorrow,
            start_time=self.time_1000,
            end_time=self.time_1200,
        )
        res.reject(reviewer=self.staff_reviewer, reason='Conflict with college activity')
        self.assertEqual(res.status, Reservation.Status.REJECTED)

        # Now creating an overlapping reservation MUST succeed
        replacement = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='New Requester for same slot',
            reservation_date=self.tomorrow,
            start_time=self.time_1000,
            end_time=self.time_1200,
        )
        self.assertEqual(replacement.status, Reservation.Status.PENDING)

    def test_cancelled_reservation_does_not_block_slot(self):
        """A CANCELLED reservation releases the slot."""
        res = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Will cancel',
            reservation_date=self.tomorrow,
            start_time=self.time_1000,
            end_time=self.time_1200,
        )
        res.cancel()
        self.assertEqual(res.status, Reservation.Status.CANCELLED)

        # Now creating an overlapping reservation MUST succeed
        replacement = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Replacement Booking',
            reservation_date=self.tomorrow,
            start_time=self.time_1000,
            end_time=self.time_1200,
        )
        self.assertEqual(replacement.status, Reservation.Status.PENDING)

    # 8. Approval and Rejection review lifecycle
    def test_approve_records_reviewer_and_timestamp(self):
        """Approving a reservation records reviewed_by, reviewed_at, and sets APPROVED."""
        res = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Pending Request',
            reservation_date=self.tomorrow,
            start_time=self.time_1000,
            end_time=self.time_1200,
        )
        res.approve(reviewer=self.staff_reviewer)
        self.assertEqual(res.status, Reservation.Status.APPROVED)
        self.assertEqual(res.reviewed_by, self.staff_reviewer)
        self.assertIsNotNone(res.reviewed_at)

    def test_reject_records_reason_and_reviewer(self):
        """Rejecting a reservation requires and records rejection_reason and reviewer."""
        res = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Pending Request',
            reservation_date=self.tomorrow,
            start_time=self.time_1000,
            end_time=self.time_1200,
        )
        res.reject(reviewer=self.staff_reviewer, reason='Facility needed for official college accreditation.')
        self.assertEqual(res.status, Reservation.Status.REJECTED)
        self.assertEqual(res.reviewed_by, self.staff_reviewer)
        self.assertEqual(res.rejection_reason, 'Facility needed for official college accreditation.')

    def test_reject_without_reason_rejected(self):
        """Rejecting without providing a reason raises ValidationError."""
        res = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.available_facility,
            purpose='Pending Request',
            reservation_date=self.tomorrow,
            start_time=self.time_1000,
            end_time=self.time_1200,
        )
        with self.assertRaises(ValidationError):
            res.reject(reviewer=self.staff_reviewer, reason='')
