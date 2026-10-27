"""
Tests for the Calendar API full-month endpoint: GET /facilities/{id}/calendar-api/{year}/{month}/

Task 5: Verify Calendar API Functionality - Testing the full month endpoint.

This test suite verifies:
1. Endpoint returns valid JSON array with all days of month
2. All days in month included (28-31 days depending on month)
3. Each day has occupancy % (0-100)
4. Date format correct (day numbers for each day)
5. Response includes aggregated data for full month
6. Handles invalid month numbers gracefully
7. Works for past, present, and future months
8. Response time reasonable for full month data
9. Proper aggregation across multiple reservations
10. Correctly handles leap years
"""

import datetime
import json
import time
from decimal import Decimal
from dateutil import rrule

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from facilities.models import Facility, FacilityType, FacilityMaintenance
from reservations.models import Reservation

User = get_user_model()


class CalendarApiMonthEndpointTestCase(TestCase):
    """Test the GET /facilities/{id}/calendar-api/{year}/{month}/ endpoint."""

    def setUp(self):
        """Set up test data: facility, users, and reservations."""
        self.client = Client()
        
        self.facility_type = FacilityType.objects.create(
            name="Computer Laboratory"
        )
        
        self.facility = Facility.objects.create(
            name="IT ComLab 1",
            location="Admin Building, 2nd Floor",
            capacity=30,
            facility_type=self.facility_type,
            status=Facility.Status.AVAILABLE,
            hours_of_operation="8am-6pm",
        )
        
        self.requestor = User.objects.create_user(
            username="student_month",
            password="testpass123",
            email="student@test.com",
            role=User.Role.REQUESTER,
            user_type=User.UserType.STUDENT,
        )
        
        self.staff = User.objects.create_user(
            username="staff_month",
            password="testpass123",
            email="staff@test.com",
            role=User.Role.STAFF,
            user_type=User.UserType.STUDENT,
        )
        
        self.admin = User.objects.create_user(
            username="admin_month",
            password="testpass123",
            email="admin@test.com",
            role=User.Role.ADMIN,
            user_type=User.UserType.STUDENT,
        )

    def test_endpoint_requires_authentication(self):
        """Endpoint should require login."""
        year = 2024
        month = 12
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login', response.url)

    def test_endpoint_returns_valid_json(self):
        """Acceptance Criteria 1: API returns valid JSON with all days for month."""
        self.client.login(username="student_month", password="testpass123")
        
        year = 2024
        month = 12
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        # Should be valid JSON
        data = json.loads(response.content)
        self.assertIsInstance(data, dict)

    def test_endpoint_returns_required_fields(self):
        """Verify response contains all required fields."""
        self.client.login(username="student_month", password="testpass123")
        
        year = 2024
        month = 12
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        
        # Required top-level fields
        required_fields = [
            'year',
            'month',
            'facility_id',
            'facility_name',
            'is_available',
            'days',
        ]
        
        for field in required_fields:
            self.assertIn(field, data, f"Missing field: {field}")
        
        # days should be a dictionary
        self.assertIsInstance(data['days'], dict)

    def test_all_days_of_month_included(self):
        """Acceptance Criteria 2: Response includes all days in month (28-31 days)."""
        self.client.login(username="student_month", password="testpass123")
        
        # December 2024 has 31 days
        year = 2024
        month = 12
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        days = data['days']
        
        # Should have 31 days
        self.assertEqual(len(days), 31)
        
        # Days should be numbered 1-31
        for day_num in range(1, 32):
            self.assertIn(str(day_num), days, f"Missing day {day_num}")

    def test_february_leap_year(self):
        """Test February in a leap year (29 days)."""
        self.client.login(username="student_month", password="testpass123")
        
        # February 2024 is a leap year with 29 days
        year = 2024
        month = 2
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        days = data['days']
        
        # Should have 29 days
        self.assertEqual(len(days), 29)

    def test_february_non_leap_year(self):
        """Test February in a non-leap year (28 days)."""
        self.client.login(username="student_month", password="testpass123")
        
        # February 2023 is not a leap year with 28 days
        year = 2023
        month = 2
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        days = data['days']
        
        # Should have 28 days
        self.assertEqual(len(days), 28)

    def test_april_has_30_days(self):
        """Test April month (30 days)."""
        self.client.login(username="student_month", password="testpass123")
        
        year = 2024
        month = 4
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        days = data['days']
        
        # Should have 30 days
        self.assertEqual(len(days), 30)

    def test_each_day_has_occupancy_percentage(self):
        """Acceptance Criteria 3: Each day has occupancy % (0-100)."""
        self.client.login(username="student_month", password="testpass123")
        
        year = 2024
        month = 12
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        days = data['days']
        
        # Every day should have occupancy field
        for day_num in range(1, 32):
            day_data = days[str(day_num)]
            self.assertIn('occupancy', day_data, f"Missing occupancy for day {day_num}")
            
            # Occupancy should be an integer percentage
            occupancy = day_data['occupancy']
            self.assertIsInstance(occupancy, int)
            self.assertGreaterEqual(occupancy, 0)
            self.assertLessEqual(occupancy, 100)

    def test_each_day_has_reservation_count(self):
        """Each day should include reservation count."""
        self.client.login(username="student_month", password="testpass123")
        
        year = 2024
        month = 12
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        days = data['days']
        
        # Every day should have reservation count
        for day_num in range(1, 32):
            day_data = days[str(day_num)]
            self.assertIn('reservations', day_data, f"Missing reservations count for day {day_num}")
            self.assertIsInstance(day_data['reservations'], int)
            self.assertGreaterEqual(day_data['reservations'], 0)

    def test_each_day_has_maintenance_count(self):
        """Each day should include maintenance count."""
        self.client.login(username="student_month", password="testpass123")
        
        year = 2024
        month = 12
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        days = data['days']
        
        # Every day should have maintenance count
        for day_num in range(1, 32):
            day_data = days[str(day_num)]
            self.assertIn('maintenance', day_data, f"Missing maintenance count for day {day_num}")
            self.assertIsInstance(day_data['maintenance'], int)
            self.assertGreaterEqual(day_data['maintenance'], 0)

    def test_each_day_has_availability_status(self):
        """Each day should include availability status."""
        self.client.login(username="student_month", password="testpass123")
        
        year = 2024
        month = 12
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        days = data['days']
        
        # Every day should have is_available flag
        for day_num in range(1, 32):
            day_data = days[str(day_num)]
            self.assertIn('is_available', day_data, f"Missing is_available for day {day_num}")
            self.assertIsInstance(day_data['is_available'], bool)

    def test_occupancy_aggregation_single_reservation(self):
        """Test occupancy aggregation with single reservation."""
        self.client.login(username="student_month", password="testpass123")
        
        year = 2024
        month = 12
        day = 15
        date_obj = datetime.date(year, month, day)
        
        # Create a 2-hour reservation (20% occupancy for 8am-6pm = 10 hours)
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Lab Session",
            reservation_date=date_obj,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        day_data = data['days'][str(day)]
        
        # Occupancy should be 20%
        self.assertEqual(day_data['occupancy'], 20)
        self.assertEqual(day_data['reservations'], 1)

    def test_occupancy_aggregation_multiple_reservations(self):
        """Acceptance Criteria 8: Aggregation correctly across multiple reservations."""
        self.client.login(username="student_month", password="testpass123")
        
        year = 2024
        month = 12
        day = 15
        date_obj = datetime.date(year, month, day)
        
        # Create 3 reservations on the same day
        # Res 1: 2 hours (9-11am)
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Class 1",
            reservation_date=date_obj,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        # Res 2: 2 hours (12-2pm)
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Class 2",
            reservation_date=date_obj,
            start_time=datetime.time(12, 0),
            end_time=datetime.time(14, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        # Res 3: 2 hours (3-5pm)
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Class 3",
            reservation_date=date_obj,
            start_time=datetime.time(15, 0),
            end_time=datetime.time(17, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        day_data = data['days'][str(day)]
        
        # Total: 6 hours / 10 hours = 60% occupancy
        self.assertEqual(day_data['occupancy'], 60)
        self.assertEqual(day_data['reservations'], 3)

    def test_occupancy_aggregation_reservations_and_maintenance(self):
        """Test that occupancy includes both reservations and maintenance."""
        self.client.login(username="student_month", password="testpass123")
        
        year = 2024
        month = 12
        day = 15
        date_obj = datetime.date(year, month, day)
        
        # Create a 3-hour reservation
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Class",
            reservation_date=date_obj,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(12, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        # Create a 2-hour maintenance window
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Cleaning",
            maintenance_date=date_obj,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(16, 0),
            status=FacilityMaintenance.Status.SCHEDULED,
            created_by=self.admin,
        )
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        day_data = data['days'][str(day)]
        
        # Total: (3 + 2) hours / 10 hours = 50% occupancy
        self.assertEqual(day_data['occupancy'], 50)
        self.assertEqual(day_data['reservations'], 1)
        self.assertEqual(day_data['maintenance'], 1)

    def test_empty_month(self):
        """Test month with no reservations or maintenance."""
        self.client.login(username="student_month", password="testpass123")
        
        # December 2023 is in the past and has no reservations
        year = 2023
        month = 12
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        days = data['days']
        
        # All days should have 0% occupancy
        for day_num in range(1, 32):
            day_data = days[str(day_num)]
            self.assertEqual(day_data['occupancy'], 0)
            self.assertEqual(day_data['reservations'], 0)
            self.assertEqual(day_data['maintenance'], 0)

    def test_partially_filled_month(self):
        """Acceptance Criteria 5: Test month with partial bookings."""
        self.client.login(username="student_month", password="testpass123")
        
        year = 2024
        month = 12
        
        # Create reservations on 5 different days
        for day_num in [5, 10, 15, 20, 25]:
            date_obj = datetime.date(year, month, day_num)
            Reservation.objects.create(
                requested_by=self.requestor,
                facility=self.facility,
                purpose=f"Event on day {day_num}",
                reservation_date=date_obj,
                start_time=datetime.time(10, 0),
                end_time=datetime.time(12, 0),
                status=Reservation.Status.APPROVED,
                reviewed_by=self.staff,
                reviewed_at=timezone.now(),
            )
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        days = data['days']
        
        # Days with reservations should have 20% occupancy
        for day_num in [5, 10, 15, 20, 25]:
            self.assertEqual(days[str(day_num)]['occupancy'], 20)
            self.assertEqual(days[str(day_num)]['reservations'], 1)
        
        # Other days should have 0% occupancy
        for day_num in range(1, 32):
            if day_num not in [5, 10, 15, 20, 25]:
                self.assertEqual(days[str(day_num)]['occupancy'], 0)
                self.assertEqual(days[str(day_num)]['reservations'], 0)

    def test_fully_booked_month(self):
        """Test month where most days are fully booked."""
        self.client.login(username="student_month", password="testpass123")
        
        year = 2024
        month = 12
        
        # Create full-day reservations for every day in the month
        for day_num in range(1, 32):
            date_obj = datetime.date(year, month, day_num)
            Reservation.objects.create(
                requested_by=self.requestor,
                facility=self.facility,
                purpose=f"Full day {day_num}",
                reservation_date=date_obj,
                start_time=datetime.time(8, 0),
                end_time=datetime.time(18, 0),
                status=Reservation.Status.APPROVED,
                reviewed_by=self.staff,
                reviewed_at=timezone.now(),
            )
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        days = data['days']
        
        # All days should be 100% booked
        for day_num in range(1, 32):
            self.assertEqual(days[str(day_num)]['occupancy'], 100)
            self.assertEqual(days[str(day_num)]['reservations'], 1)

    def test_invalid_month_number_low(self):
        """Acceptance Criteria 6: Endpoint should handle invalid months gracefully."""
        self.client.login(username="student_month", password="testpass123")
        
        year = 2024
        month = 0  # Invalid month
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        # Should handle gracefully (400 or 404)
        self.assertIn(response.status_code, [400, 404])

    def test_invalid_month_number_high(self):
        """Test month number > 12."""
        self.client.login(username="student_month", password="testpass123")
        
        year = 2024
        month = 13  # Invalid month
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        # Should handle gracefully (400 or 404)
        self.assertIn(response.status_code, [400, 404])

    def test_invalid_facility_id(self):
        """Test with invalid facility ID."""
        self.client.login(username="student_month", password="testpass123")
        
        year = 2024
        month = 12
        invalid_facility_id = 99999
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[invalid_facility_id, year, month])
        )
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertIn('error', data)

    def test_past_month(self):
        """Acceptance Criteria 7: Endpoint works for past months."""
        self.client.login(username="student_month", password="testpass123")
        
        # Use a past month
        year = 2024
        month = 1
        
        # Create a past reservation
        date_obj = datetime.date(year, month, 15)
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Past event",
            reservation_date=date_obj,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
            status=Reservation.Status.COMPLETED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Should return the month data (completed reservations not counted)
        self.assertEqual(data['year'], year)
        self.assertEqual(data['month'], month)
        # COMPLETED reservations should NOT count toward occupancy
        self.assertEqual(data['days']['15']['occupancy'], 0)

    def test_future_month(self):
        """Acceptance Criteria 7: Endpoint works for future months."""
        self.client.login(username="student_month", password="testpass123")
        
        # Use a future month
        year = 2026
        month = 6
        
        # Create a future reservation
        date_obj = datetime.date(year, month, 15)
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Future event",
            reservation_date=date_obj,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Should return the month data
        self.assertEqual(data['year'], year)
        self.assertEqual(data['month'], month)
        # Future reservation should be counted
        self.assertEqual(data['days']['15']['occupancy'], 20)

    def test_response_time_acceptable(self):
        """Acceptance Criteria 8: Response time should be reasonable for full month."""
        self.client.login(username="student_month", password="testpass123")
        
        # Create 200+ reservations across the month to stress test
        year = 2024
        month = 12
        
        for day_num in range(1, 32):
            date_obj = datetime.date(year, month, day_num)
            # Create 6-7 reservations per day
            for i in range(6):
                start_hour = 8 + (i * 1)
                end_hour = start_hour + 1
                
                Reservation.objects.create(
                    requested_by=self.requestor,
                    facility=self.facility,
                    purpose=f"Event {i}",
                    reservation_date=date_obj,
                    start_time=datetime.time(start_hour, 0),
                    end_time=datetime.time(end_hour, 0),
                    status=Reservation.Status.APPROVED,
                    reviewed_by=self.staff,
                    reviewed_at=timezone.now(),
                )
        
        start_time = time.time()
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        elapsed_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        self.assertEqual(response.status_code, 200)
        # Response should be < 2 seconds for full month
        self.assertLess(elapsed_time, 2000, 
                       f"Response time {elapsed_time}ms exceeded 2000ms limit")

    def test_facility_unavailable_status(self):
        """Test that availability status is reflected for all days."""
        self.client.login(username="student_month", password="testpass123")
        
        # Change facility status to UNAVAILABLE
        self.facility.status = Facility.Status.UNAVAILABLE
        self.facility.save()
        
        year = 2024
        month = 12
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        
        # Top-level is_available should be False
        self.assertFalse(data['is_available'])
        
        # All days should reflect unavailable status
        for day_num in range(1, 32):
            self.assertFalse(data['days'][str(day_num)]['is_available'])

    def test_facility_maintenance_status(self):
        """Test facility in MAINTENANCE status."""
        self.client.login(username="student_month", password="testpass123")
        
        # Change facility status to MAINTENANCE
        self.facility.status = Facility.Status.MAINTENANCE
        self.facility.save()
        
        year = 2024
        month = 12
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        
        # Top-level is_available should be False
        self.assertFalse(data['is_available'])

    def test_only_pending_and_approved_counted(self):
        """Test that only PENDING and APPROVED reservations are counted."""
        self.client.login(username="student_month", password="testpass123")
        
        year = 2024
        month = 12
        day = 15
        date_obj = datetime.date(year, month, day)
        
        # APPROVED - should count
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Approved",
            reservation_date=date_obj,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        # PENDING - should count
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Pending",
            reservation_date=date_obj,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(11, 0),
            status=Reservation.Status.PENDING,
        )
        
        # REJECTED - should NOT count
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Rejected",
            reservation_date=date_obj,
            start_time=datetime.time(11, 0),
            end_time=datetime.time(12, 0),
            status=Reservation.Status.REJECTED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
            rejection_reason="Not available",
        )
        
        # CANCELLED - should NOT count
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Cancelled",
            reservation_date=date_obj,
            start_time=datetime.time(12, 0),
            end_time=datetime.time(13, 0),
            status=Reservation.Status.CANCELLED,
        )
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        day_data = data['days'][str(day)]
        
        # Should count only APPROVED and PENDING (2)
        self.assertEqual(day_data['reservations'], 2)
        # Occupancy: 2 hours / 10 hours = 20%
        self.assertEqual(day_data['occupancy'], 20)

    def test_only_scheduled_maintenance_counted(self):
        """Test that only SCHEDULED maintenance is counted."""
        self.client.login(username="student_month", password="testpass123")
        
        year = 2024
        month = 12
        day = 15
        date_obj = datetime.date(year, month, day)
        
        # SCHEDULED - should count
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Scheduled",
            maintenance_date=date_obj,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=FacilityMaintenance.Status.SCHEDULED,
            created_by=self.admin,
        )
        
        # COMPLETED - should NOT count
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Completed",
            maintenance_date=date_obj,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(11, 0),
            status=FacilityMaintenance.Status.COMPLETED,
            created_by=self.admin,
        )
        
        # CANCELLED - should NOT count
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Cancelled",
            maintenance_date=date_obj,
            start_time=datetime.time(11, 0),
            end_time=datetime.time(12, 0),
            status=FacilityMaintenance.Status.CANCELLED,
            created_by=self.admin,
        )
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        day_data = data['days'][str(day)]
        
        # Should count only SCHEDULED (1)
        self.assertEqual(day_data['maintenance'], 1)

    def test_response_metadata_accuracy(self):
        """Test that year and month in response match the request."""
        self.client.login(username="student_month", password="testpass123")
        
        year = 2025
        month = 3
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        
        self.assertEqual(data['year'], year)
        self.assertEqual(data['month'], month)
        self.assertEqual(data['facility_id'], self.facility.id)
        self.assertEqual(data['facility_name'], self.facility.name)

    def test_occupancy_calculation_edge_case_max(self):
        """Test occupancy capped at 100%."""
        self.client.login(username="student_month", password="testpass123")
        
        year = 2024
        month = 12
        day = 15
        date_obj = datetime.date(year, month, day)
        
        # Create overlapping reservations that exceed 100%
        for i in range(3):
            Reservation.objects.create(
                requested_by=self.requestor,
                facility=self.facility,
                purpose=f"Event {i}",
                reservation_date=date_obj,
                start_time=datetime.time(8, 0),
                end_time=datetime.time(18, 0),  # 10 hours = 100%
                status=Reservation.Status.APPROVED,
                reviewed_by=self.staff,
                reviewed_at=timezone.now(),
            )
        
        response = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, year, month])
        )
        
        data = json.loads(response.content)
        day_data = data['days'][str(day)]
        
        # Occupancy should be capped at 100%
        self.assertEqual(day_data['occupancy'], 100)

    def test_different_months_have_different_counts(self):
        """Test that response correctly reflects days in different months."""
        self.client.login(username="student_month", password="testpass123")
        
        # April 2024 has 30 days
        response_april = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, 2024, 4])
        )
        data_april = json.loads(response_april.content)
        
        # December 2024 has 31 days
        response_dec = self.client.get(
            reverse('facilities:api_calendar_month', 
                   args=[self.facility.id, 2024, 12])
        )
        data_dec = json.loads(response_dec.content)
        
        # April should have 30 days
        self.assertEqual(len(data_april['days']), 30)
        
        # December should have 31 days
        self.assertEqual(len(data_dec['days']), 31)
