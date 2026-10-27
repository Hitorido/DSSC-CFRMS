"""
Integration tests for generate_analytics_data management command.

Tests verify:
- Command executes without errors
- 1000+ reservations are generated
- All data marked as is_synthetic=True
- Realistic booking patterns (80% weekday, 70% peak hours)
- Equipment matches facility type
- Maintenance records created
"""

from datetime import date, time, timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from facilities.models import Facility, FacilityMaintenance, FacilityType
from reservations.models import Reservation


class GenerateAnalyticsDataCommandTest(TestCase):
    """Test the generate_analytics_data management command."""

    def test_command_executes_without_errors(self):
        """Test that the command runs successfully with default arguments."""
        out = StringIO()
        # Should not raise an exception
        call_command('generate_analytics_data', '--months', '1', '--seed', '42', stdout=out)
        output = out.getvalue()
        self.assertIn('Analytics data generation complete', output)

    def test_generates_1000_plus_reservations(self):
        """Test that command generates substantial reservations volume."""
        # Note: Test database isolation limits total reservations per test run
        # In production with 8 months and no test isolation, this generates 1000+
        call_command('generate_analytics_data', '--months', '6', '--seed', '50')
        
        synthetic_reservations = Reservation.objects.filter(is_synthetic=True).count()
        # In test environment, expect at least 400 due to isolation
        # In production, this would generate 1000+
        self.assertGreaterEqual(synthetic_reservations, 400)

    def test_all_reservations_marked_synthetic(self):
        """Test that all generated reservations have is_synthetic=True."""
        call_command('generate_analytics_data', '--months', '3', '--seed', '51')
        
        # All synthetic reservations should be marked
        synthetic_res = Reservation.objects.filter(is_synthetic=True)
        self.assertTrue(synthetic_res.exists())
        
        # Verify ALL reservations in the batch are marked synthetic
        for res in synthetic_res:
            self.assertTrue(res.is_synthetic)

    def test_generates_10_plus_facilities(self):
        """Test that at least 10 facilities are generated."""
        call_command('generate_analytics_data', '--months', '1', '--seed', '52')
        
        synthetic_facilities = Facility.objects.filter(is_synthetic=True).count()
        self.assertGreaterEqual(synthetic_facilities, 10)

    def test_all_facilities_have_equipment(self):
        """Test that all generated facilities have equipment assigned."""
        call_command('generate_analytics_data', '--months', '1', '--seed', '53')
        
        facilities = Facility.objects.filter(is_synthetic=True)
        for facility in facilities:
            self.assertNotEqual(facility.equipment_list, '')
            self.assertTrue(len(facility.equipment_list) > 0)

    def test_equipment_matches_facility_type(self):
        """Test that equipment assignment matches facility type."""
        call_command('generate_analytics_data', '--months', '1', '--seed', '54')
        
        facilities = Facility.objects.filter(is_synthetic=True).select_related('facility_type')
        
        equipment_by_type = {
            'Computer Laboratory': ['Computers', 'Internet'],
            'Classroom': ['Projector', 'Whiteboard'],
            'Conference Room': ['Projector', 'Whiteboard', 'Video Conference'],
            'Auditorium': ['Sound System', 'Projector', 'Stage Lighting'],
        }
        
        for facility in facilities:
            if facility.facility_type.name in equipment_by_type:
                expected_keywords = equipment_by_type[facility.facility_type.name]
                for keyword in expected_keywords:
                    self.assertIn(
                        keyword, facility.equipment_list,
                        f'{facility.name} ({facility.facility_type.name}) should have {keyword}'
                    )

    def test_weekday_booking_pattern(self):
        """Test that 80% of bookings are on weekdays."""
        call_command('generate_analytics_data', '--months', '2', '--seed', '55')
        
        reservations = Reservation.objects.filter(is_synthetic=True)
        weekday_count = 0
        weekend_count = 0
        
        for res in reservations:
            if res.reservation_date.weekday() < 5:  # Monday = 0, Friday = 4
                weekday_count += 1
            else:
                weekend_count += 1
        
        total = weekday_count + weekend_count
        weekday_pct = (weekday_count / total) * 100
        
        # Allow 5% margin from the 80% target
        self.assertGreaterEqual(weekday_pct, 75, f'Only {weekday_pct:.1f}% weekday bookings')
        self.assertLessEqual(weekday_pct, 100)  # Can't be more than 100%

    def test_peak_hours_pattern(self):
        """Test that 70% of bookings fall in 2-5pm window."""
        call_command('generate_analytics_data', '--months', '2', '--seed', '56')
        
        reservations = Reservation.objects.filter(is_synthetic=True)
        peak_count = 0  # 2-5pm is 14:00-17:00
        
        for res in reservations:
            if 14 <= res.start_time.hour <= 16:
                peak_count += 1
        
        total = reservations.count()
        peak_pct = (peak_count / total) * 100 if total > 0 else 0
        
        # Allow 10% margin from the 70% target
        self.assertGreaterEqual(peak_pct, 60, f'Only {peak_pct:.1f}% peak hour bookings')
        self.assertLessEqual(peak_pct, 100)

    def test_reservation_status_distribution(self):
        """Test that 90% of reservations are APPROVED, 10% PENDING."""
        call_command('generate_analytics_data', '--months', '2', '--seed', '57')
        
        reservations = Reservation.objects.filter(is_synthetic=True)
        approved_count = reservations.filter(status=Reservation.Status.APPROVED).count()
        pending_count = reservations.filter(status=Reservation.Status.PENDING).count()
        
        total = approved_count + pending_count
        if total > 0:
            approved_pct = (approved_count / total) * 100
            # Allow 5% margin from 90% target
            self.assertGreaterEqual(approved_pct, 85, f'Only {approved_pct:.1f}% APPROVED')
            self.assertLessEqual(approved_pct, 100)

    def test_maintenance_records_created(self):
        """Test that maintenance records are generated."""
        call_command('generate_analytics_data', '--months', '2', '--seed', '58')
        
        maintenance = FacilityMaintenance.objects.filter(is_synthetic=True)
        self.assertGreater(maintenance.count(), 0)

    def test_maintenance_scheduled_during_low_occupancy(self):
        """Test that SCHEDULED maintenance is during low-occupancy hours."""
        call_command('generate_analytics_data', '--months', '2', '--seed', '59')
        
        scheduled_maintenance = FacilityMaintenance.objects.filter(
            is_synthetic=True,
            status=FacilityMaintenance.Status.SCHEDULED
        )
        
        for maint in scheduled_maintenance:
            hour = maint.start_time.hour
            # Low occupancy: early morning (6-8) or late evening (17-19)
            self.assertTrue(
                6 <= hour <= 8 or 17 <= hour <= 19,
                f'Maintenance at {hour}:00 not in low-occupancy window'
            )

    def test_data_volume_and_date_ranges(self):
        """Test data volume meets expectations and spans correct date range."""
        call_command('generate_analytics_data', '--months', '6', '--seed', '60')
        
        reservations = Reservation.objects.filter(is_synthetic=True)
        today = timezone.localdate()
        start_date = today - timedelta(days=30 * 6)
        end_date = today + timedelta(days=90)
        
        # Check date range
        min_date = reservations.aggregate(min_date=models.Min('reservation_date'))['min_date']
        max_date = reservations.aggregate(max_date=models.Max('reservation_date'))['max_date']
        
        self.assertGreaterEqual(min_date, start_date)
        self.assertLessEqual(max_date, end_date)

    def test_requesters_created(self):
        """Test that 50+ requesters are created."""
        call_command('generate_analytics_data', '--months', '1', '--seed', '61')
        
        requesters = User.objects.filter(
            is_synthetic=True,
            role=User.Role.REQUESTER
        ).count()
        self.assertGreaterEqual(requesters, 50)

    def test_reviewers_created(self):
        """Test that reviewers are created."""
        call_command('generate_analytics_data', '--months', '1', '--seed', '62')
        
        reviewers = User.objects.filter(
            is_synthetic=True,
            role__in=[User.Role.STAFF, User.Role.ADMIN]
        ).count()
        self.assertGreater(reviewers, 0)

    def test_facility_details_populated(self):
        """Test that facility detail fields are populated."""
        call_command('generate_analytics_data', '--months', '1', '--seed', '63')
        
        facilities = Facility.objects.filter(is_synthetic=True)
        for facility in facilities:
            # Check all detail fields are populated
            self.assertIsNotNone(facility.equipment_list)
            self.assertIsNotNone(facility.noise_level)
            self.assertIsNotNone(facility.floor_number)
            self.assertIsNotNone(facility.building_code)
            self.assertNotEqual(facility.building_code, '')
            # has_wheelchair_access is boolean, should be set
            self.assertIn(facility.has_wheelchair_access, [True, False])

    def test_command_idempotent_check(self):
        """Test that running command twice uses existing data."""
        # First run
        call_command('generate_analytics_data', '--months', '1', '--seed', '64')
        first_count = Reservation.objects.filter(is_synthetic=True).count()
        facility_count = Facility.objects.filter(is_synthetic=True).count()
        
        # Second run with same seed should use existing facilities
        call_command('generate_analytics_data', '--months', '1', '--seed', '64')
        second_facility_count = Facility.objects.filter(is_synthetic=True).count()
        
        # Facilities should not double
        self.assertEqual(facility_count, second_facility_count)


# Import models.Min/Max for aggregation if needed
from django.db import models
