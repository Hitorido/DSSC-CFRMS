from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone
from datetime import time, timedelta

from .models import Facility, FacilityType
from reservations.models import Reservation
from accounts.models import User


class FacilityModelTestCase(TestCase):
    """
    Focused test suite validating FacilityType and Facility models,
    their relationships, constraints, status defaults, and deletion protection.
    """

    def setUp(self):
        self.facility_type = FacilityType.objects.create(
            name='Computer Laboratory',
            description='Rooms equipped with desktop workstations and internet access.',
        )

    def test_facility_type_creation_and_str(self):
        """Verify FacilityType creation and __str__ representation."""
        self.assertEqual(str(self.facility_type), 'Computer Laboratory')
        self.assertEqual(self.facility_type.facilities.count(), 0)

    def test_facility_creation_with_relationship(self):
        """Verify Facility creation and relationship to FacilityType."""
        facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='IT ComLab 1',
            location='IT Building 2nd Floor',
            capacity=40,
        )
        self.assertEqual(facility.facility_type, self.facility_type)
        self.assertEqual(facility.status, Facility.Status.AVAILABLE)
        self.assertTrue(facility.is_operational)
        self.assertIn('IT ComLab 1', str(facility))
        self.assertIn('40', str(facility))

    def test_reverse_relationship_using_related_name(self):
        """Verify reverse querying facilities from FacilityType via related_name='facilities'."""
        f1 = Facility.objects.create(
            facility_type=self.facility_type,
            name='IT ComLab 1',
            location='IT Building 2nd Floor',
            capacity=40,
        )
        f2 = Facility.objects.create(
            facility_type=self.facility_type,
            name='IT ComLab 2',
            location='IT Building 2nd Floor',
            capacity=35,
        )
        related_facilities = self.facility_type.facilities.all()
        self.assertEqual(related_facilities.count(), 2)
        self.assertIn(f1, related_facilities)
        self.assertIn(f2, related_facilities)

    def test_on_delete_protect_prevents_category_deletion_when_facilities_exist(self):
        """Verify models.PROTECT raises ProtectedError when deleting a referenced FacilityType."""
        Facility.objects.create(
            facility_type=self.facility_type,
            name='IT ComLab 1',
            location='IT Building 2nd Floor',
            capacity=40,
        )
        with self.assertRaises(ProtectedError):
            self.facility_type.delete()

    def test_facility_name_must_be_unique(self):
        """Verify duplicate facility name raises IntegrityError at database layer."""
        Facility.objects.create(
            facility_type=self.facility_type,
            name='DSSC Gymnasium',
            location='Main Campus',
            capacity=1000,
        )
        with self.assertRaises(IntegrityError):
            Facility.objects.create(
                facility_type=self.facility_type,
                name='DSSC Gymnasium',
                location='Somewhere Else',
                capacity=500,
            )

    def test_positive_capacity_rule_via_model_validation(self):
        """
        Verify Django model validation (full_clean) rejects capacity <= 0.
        Note: Model.objects.create() does not automatically invoke full_clean(),
        so full_clean() is explicitly called to test validation logic.
        """
        facility_zero = Facility(
            facility_type=self.facility_type,
            name='Invalid Zero Cap Room',
            location='Building A',
            capacity=0,
        )
        with self.assertRaises(ValidationError):
            facility_zero.full_clean()

    def test_positive_capacity_rule_via_database_constraint(self):
        """
        Verify the database CheckConstraint (facility_capacity_gt_zero)
        rejects capacity <= 0 even if full_clean() is bypassed during direct create.
        """
        with self.assertRaises(IntegrityError):
            Facility.objects.create(
                facility_type=self.facility_type,
                name='Direct DB Bypass Zero Room',
                location='Building B',
                capacity=0,
            )


class FacilityEnhancedDetailsTestCase(TestCase):
    """Test new facility details fields and backward compatibility."""

    def setUp(self):
        self.facility_type = FacilityType.objects.create(
            name='Computer Laboratory',
        )

    def test_new_fields_creation_with_defaults(self):
        """Verify new fields are created with correct defaults."""
        facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='IT ComLab 1',
            location='IT Building 2nd Floor',
            capacity=40,
        )
        # Verify all new fields have correct defaults
        self.assertEqual(facility.equipment_list, '')
        self.assertEqual(facility.hours_of_operation, '8am-6pm')
        self.assertEqual(facility.noise_level, 'low')
        self.assertIsNone(facility.floor_number)
        self.assertEqual(facility.building_code, '')
        self.assertTrue(facility.has_wheelchair_access)

    def test_new_fields_can_be_set(self):
        """Verify new fields can be set and retrieved."""
        facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='Conference Room A',
            location='Admin Building',
            capacity=20,
            equipment_list='Projector, Whiteboard, A/C',
            hours_of_operation='8am-6pm weekdays, 9am-5pm weekends',
            noise_level='medium',
            floor_number=2,
            building_code='ADMIN',
            has_wheelchair_access=True,
        )
        self.assertEqual(facility.equipment_list, 'Projector, Whiteboard, A/C')
        self.assertEqual(facility.hours_of_operation, '8am-6pm weekdays, 9am-5pm weekends')
        self.assertEqual(facility.noise_level, 'medium')
        self.assertEqual(facility.floor_number, 2)
        self.assertEqual(facility.building_code, 'ADMIN')
        self.assertTrue(facility.has_wheelchair_access)

    def test_noise_level_choices(self):
        """Verify noise_level field accepts all valid choices."""
        valid_noise_levels = ['silent', 'low', 'medium', 'high']
        for i, level in enumerate(valid_noise_levels):
            facility = Facility.objects.create(
                facility_type=self.facility_type,
                name=f'Test Facility {i}',
                location='Test Location',
                capacity=30,
                noise_level=level,
            )
            self.assertEqual(facility.noise_level, level)

    def test_wheelchair_access_false(self):
        """Verify has_wheelchair_access can be set to False."""
        facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='Basement Lab',
            location='Science Building B1',
            capacity=25,
            has_wheelchair_access=False,
        )
        self.assertFalse(facility.has_wheelchair_access)

    def test_backward_compatibility_existing_facility_without_new_fields(self):
        """Verify facilities created without new fields still work."""
        # This simulates loading existing facilities from before the migration
        facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='Legacy Facility',
            location='Old Building',
            capacity=50,
            # Not setting any new fields
        )
        # Should not raise any errors
        self.assertIsNotNone(facility)
        self.assertEqual(facility.equipment_list, '')
        self.assertEqual(facility.noise_level, 'low')

    def test_optional_fields_can_be_blank(self):
        """Verify new fields are truly optional (blank=True)."""
        facility = Facility(
            facility_type=self.facility_type,
            name='Minimal Facility',
            location='Test',
            capacity=10,
            equipment_list='',
            building_code='',
            floor_number=None,
        )
        # Should validate successfully
        facility.full_clean()
        facility.save()
        self.assertEqual(facility.equipment_list, '')
        self.assertIsNone(facility.floor_number)


class FacilityComputedPropertyTestCase(TestCase):
    """Test avg_reservation_duration computed property."""

    def setUp(self):
        self.facility_type = FacilityType.objects.create(
            name='Conference Room',
        )
        self.facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='Conference Room 1',
            location='Admin Building',
            capacity=20,
        )
        # Create a test user for reservations
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            role='REQUESTER',
        )
        self.reviewer = User.objects.create_user(
            username='reviewer',
            password='testpass123',
            role='STAFF',
        )

    def test_avg_reservation_duration_no_reservations(self):
        """Verify avg_reservation_duration returns None when no reservations exist."""
        duration = self.facility.avg_reservation_duration
        self.assertIsNone(duration)

    def test_avg_reservation_duration_single_approved(self):
        """Verify avg_reservation_duration with single approved reservation."""
        today = timezone.localdate()
        Reservation.objects.create(
            requested_by=self.user,
            facility=self.facility,
            purpose='Test meeting',
            reservation_date=today,
            start_time=time(9, 0),
            end_time=time(10, 0),  # 1 hour
            status='APPROVED',
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )
        duration = self.facility.avg_reservation_duration
        self.assertIsNotNone(duration)
        self.assertEqual(duration.total_seconds(), 3600)  # 1 hour in seconds

    def test_avg_reservation_duration_multiple_approved(self):
        """Verify avg_reservation_duration with multiple approved reservations."""
        today = timezone.localdate()
        # Create 2 approved reservations: 1 hour and 3 hours
        Reservation.objects.create(
            requested_by=self.user,
            facility=self.facility,
            purpose='Meeting 1',
            reservation_date=today,
            start_time=time(9, 0),
            end_time=time(10, 0),  # 1 hour
            status='APPROVED',
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )
        Reservation.objects.create(
            requested_by=self.user,
            facility=self.facility,
            purpose='Meeting 2',
            reservation_date=today,
            start_time=time(14, 0),
            end_time=time(17, 0),  # 3 hours
            status='APPROVED',
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )
        duration = self.facility.avg_reservation_duration
        # Average: (1 + 3) / 2 = 2 hours
        self.assertEqual(duration.total_seconds(), 7200)  # 2 hours

    def test_avg_reservation_duration_completed_reservations(self):
        """Verify avg_reservation_duration includes COMPLETED reservations."""
        today = timezone.localdate()
        Reservation.objects.create(
            requested_by=self.user,
            facility=self.facility,
            purpose='Completed meeting',
            reservation_date=today,
            start_time=time(10, 0),
            end_time=time(11, 30),  # 1.5 hours
            status='COMPLETED',
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )
        duration = self.facility.avg_reservation_duration
        self.assertEqual(duration.total_seconds(), 5400)  # 1.5 hours

    def test_avg_reservation_duration_ignores_pending(self):
        """Verify avg_reservation_duration excludes PENDING reservations."""
        today = timezone.localdate()
        # Create approved and pending reservations
        Reservation.objects.create(
            requested_by=self.user,
            facility=self.facility,
            purpose='Approved meeting',
            reservation_date=today,
            start_time=time(9, 0),
            end_time=time(10, 0),  # 1 hour
            status='APPROVED',
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )
        Reservation.objects.create(
            requested_by=self.user,
            facility=self.facility,
            purpose='Pending meeting',
            reservation_date=today,
            start_time=time(11, 0),
            end_time=time(14, 0),  # 3 hours (should be ignored)
            status='PENDING',
        )
        duration = self.facility.avg_reservation_duration
        # Should only include the 1-hour approved reservation
        self.assertEqual(duration.total_seconds(), 3600)

    def test_avg_reservation_duration_ignores_declined_cancelled(self):
        """Verify avg_reservation_duration excludes REJECTED and CANCELLED reservations."""
        today = timezone.localdate()
        Reservation.objects.create(
            requested_by=self.user,
            facility=self.facility,
            purpose='Declined meeting',
            reservation_date=today,
            start_time=time(9, 0),
            end_time=time(10, 0),
            status='REJECTED',
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )
        Reservation.objects.create(
            requested_by=self.user,
            facility=self.facility,
            purpose='Cancelled meeting',
            reservation_date=today,
            start_time=time(11, 0),
            end_time=time(12, 0),
            status='CANCELLED',
        )
        duration = self.facility.avg_reservation_duration
        self.assertIsNone(duration)

    def test_avg_reservation_duration_partial_hour(self):
        """Verify avg_reservation_duration correctly handles partial hours."""
        today = timezone.localdate()
        Reservation.objects.create(
            requested_by=self.user,
            facility=self.facility,
            purpose='45-minute meeting',
            reservation_date=today,
            start_time=time(9, 0),
            end_time=time(9, 45),  # 45 minutes
            status='APPROVED',
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )
        duration = self.facility.avg_reservation_duration
        expected_seconds = 45 * 60  # 45 minutes
        self.assertEqual(duration.total_seconds(), expected_seconds)
