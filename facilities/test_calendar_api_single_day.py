"""
Tests for the Calendar API single-day endpoint: GET /facilities/{id}/calendar-api/{YYYY-MM-DD}/

Task 5: Verify Calendar API Functionality - Testing the single day endpoint.

This test suite verifies:
1. Endpoint returns valid JSON with occupancy data
2. Occupancy percentage is between 0-100
3. Reservations list includes: start_time, end_time, purpose
4. Maintenance list includes: title, start_time, end_time
5. Response includes occupancy % calculation
6. Response time < 500ms
7. Handles invalid facility IDs gracefully
8. Handles past dates
9. Handles dates with no bookings
"""

import datetime
import json
import time
from decimal import Decimal

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from facilities.models import Facility, FacilityType, FacilityMaintenance
from reservations.models import Reservation

User = get_user_model()


class CalendarApiSingleDayEndpointTestCase(TestCase):
    """Test the GET /facilities/{id}/calendar-api/{YYYY-MM-DD}/ endpoint."""

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
            username="student_api",
            password="testpass123",
            email="student@test.com",
            role=User.Role.REQUESTER,
            user_type=User.UserType.STUDENT,
        )
        
        self.staff = User.objects.create_user(
            username="staff_api",
            password="testpass123",
            email="staff@test.com",
            role=User.Role.STAFF,
            user_type=User.UserType.STUDENT,
        )
        
        self.admin = User.objects.create_user(
            username="admin_api",
            password="testpass123",
            email="admin@test.com",
            role=User.Role.ADMIN,
            user_type=User.UserType.STUDENT,
        )

    def test_endpoint_requires_authentication(self):
        """Acceptance Criteria: Endpoint should require login."""
        today = timezone.localdate()
        date_str = today.strftime('%Y-%m-%d')
        
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login', response.url)

    def test_endpoint_returns_valid_json(self):
        """Acceptance Criteria 1: API returns valid JSON with occupancy data."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        date_str = today.strftime('%Y-%m-%d')
        
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        # Should be valid JSON
        data = json.loads(response.content)
        self.assertIsInstance(data, dict)

    def test_endpoint_returns_required_fields(self):
        """Verify response contains all required fields."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        date_str = today.strftime('%Y-%m-%d')
        
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        data = json.loads(response.content)
        
        # Required fields
        required_fields = [
            'date',
            'facility_id',
            'facility_name',
            'occupancy',
            'is_available',
            'status',
            'reservations',
            'maintenance',
            'total_reservations',
            'total_maintenance',
        ]
        
        for field in required_fields:
            self.assertIn(field, data, f"Missing field: {field}")

    def test_occupancy_is_percentage_between_0_and_100(self):
        """Acceptance Criteria 2: Occupancy percentage should be between 0-100."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        date_str = today.strftime('%Y-%m-%d')
        
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        data = json.loads(response.content)
        occupancy = data['occupancy']
        
        # Occupancy should be an integer (percentage)
        self.assertIsInstance(occupancy, int)
        # Should be between 0 and 100
        self.assertGreaterEqual(occupancy, 0)
        self.assertLessEqual(occupancy, 100)

    def test_reservations_include_required_fields(self):
        """Acceptance Criteria 3: Reservations include start_time, end_time, purpose."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        
        # Create a test reservation
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Team Meeting",
            reservation_date=today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        date_str = today.strftime('%Y-%m-%d')
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        data = json.loads(response.content)
        
        # Should have 1 reservation
        self.assertEqual(len(data['reservations']), 1)
        
        reservation = data['reservations'][0]
        required_fields = ['start_time', 'end_time', 'purpose', 'id', 'status', 'requester']
        
        for field in required_fields:
            self.assertIn(field, reservation, f"Missing reservation field: {field}")
        
        # Verify field values
        self.assertEqual(reservation['start_time'], '09:00')
        self.assertEqual(reservation['end_time'], '10:00')
        self.assertEqual(reservation['purpose'], 'Team Meeting')
        self.assertEqual(reservation['status'], Reservation.Status.APPROVED)

    def test_maintenance_include_required_fields(self):
        """Acceptance Criteria 4: Maintenance includes title, start_time, end_time."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        
        # Create a maintenance record
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Projector Maintenance",
            description="Annual projector service",
            maintenance_date=today,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(15, 30),
            status=FacilityMaintenance.Status.SCHEDULED,
            created_by=self.admin,
        )
        
        date_str = today.strftime('%Y-%m-%d')
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        data = json.loads(response.content)
        
        # Should have 1 maintenance record
        self.assertEqual(len(data['maintenance']), 1)
        
        maintenance = data['maintenance'][0]
        required_fields = ['id', 'title', 'start_time', 'end_time', 'status']
        
        for field in required_fields:
            self.assertIn(field, maintenance, f"Missing maintenance field: {field}")
        
        # Verify field values
        self.assertEqual(maintenance['title'], 'Projector Maintenance')
        self.assertEqual(maintenance['start_time'], '14:00')
        self.assertEqual(maintenance['end_time'], '15:30')
        self.assertEqual(maintenance['status'], FacilityMaintenance.Status.SCHEDULED)

    def test_occupancy_calculation_no_bookings(self):
        """Acceptance Criteria 9: Endpoint should work with empty days (no reservations)."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        date_str = today.strftime('%Y-%m-%d')
        
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        data = json.loads(response.content)
        
        # No reservations or maintenance
        self.assertEqual(len(data['reservations']), 0)
        self.assertEqual(len(data['maintenance']), 0)
        # Occupancy should be 0%
        self.assertEqual(data['occupancy'], 0)
        # Total counts
        self.assertEqual(data['total_reservations'], 0)
        self.assertEqual(data['total_maintenance'], 0)

    def test_occupancy_calculation_low_occupancy(self):
        """Test occupancy calculation with low occupancy (20%)."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        
        # Create a 2-hour reservation
        # Operating day: 8am-6pm = 10 hours = 600 minutes
        # 2 hours = 120 minutes
        # Occupancy = 120/600 = 20%
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Lab Session",
            reservation_date=today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        date_str = today.strftime('%Y-%m-%d')
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        data = json.loads(response.content)
        
        # Occupancy should be 20%
        self.assertEqual(data['occupancy'], 20)

    def test_occupancy_calculation_medium_occupancy(self):
        """Test occupancy calculation with medium occupancy (50%)."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        
        # Create a 5-hour reservation
        # Operating day: 10 hours = 600 minutes
        # 5 hours = 300 minutes
        # Occupancy = 300/600 = 50%
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Workshop",
            reservation_date=today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(14, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        date_str = today.strftime('%Y-%m-%d')
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        data = json.loads(response.content)
        
        # Occupancy should be 50%
        self.assertEqual(data['occupancy'], 50)

    def test_occupancy_calculation_high_occupancy(self):
        """Test occupancy calculation with high occupancy (80%)."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        
        # Create an 8-hour reservation
        # Operating day: 10 hours = 600 minutes
        # 8 hours = 480 minutes
        # Occupancy = 480/600 = 80%
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Full Day Event",
            reservation_date=today,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(16, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        date_str = today.strftime('%Y-%m-%d')
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        data = json.loads(response.content)
        
        # Occupancy should be 80%
        self.assertEqual(data['occupancy'], 80)

    def test_occupancy_calculation_fully_booked(self):
        """Acceptance Criteria 8: Endpoint works with fully booked days."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        
        # Create a 10-hour reservation (full day)
        # Operating day: 10 hours = 600 minutes
        # 10 hours = 600 minutes
        # Occupancy = 600/600 = 100%
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Full Facility Booking",
            reservation_date=today,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(18, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        date_str = today.strftime('%Y-%m-%d')
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        data = json.loads(response.content)
        
        # Occupancy should be 100%
        self.assertEqual(data['occupancy'], 100)

    def test_occupancy_includes_both_reservations_and_maintenance(self):
        """Test that occupancy calculation includes both reservations and maintenance."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        
        # Create a 3-hour reservation (180 minutes)
        # 180 / 600 = 30%
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Class",
            reservation_date=today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(12, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        # Create a 2-hour maintenance window (120 minutes)
        # Total: (180 + 120) / 600 = 50%
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Cleaning",
            maintenance_date=today,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(16, 0),
            status=FacilityMaintenance.Status.SCHEDULED,
            created_by=self.admin,
        )
        
        date_str = today.strftime('%Y-%m-%d')
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        data = json.loads(response.content)
        
        # Occupancy should include both
        self.assertEqual(data['occupancy'], 50)
        self.assertEqual(data['total_reservations'], 1)
        self.assertEqual(data['total_maintenance'], 1)

    def test_response_time_acceptable(self):
        """Acceptance Criteria 6: Response time should be < 500ms."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        date_str = today.strftime('%Y-%m-%d')
        
        start_time = time.time()
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        elapsed_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        self.assertEqual(response.status_code, 200)
        # Response should be < 500ms
        self.assertLess(elapsed_time, 500, 
                       f"Response time {elapsed_time}ms exceeded 500ms limit")

    def test_invalid_facility_id_returns_404(self):
        """Acceptance Criteria 7: Endpoint should handle invalid facility IDs gracefully."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        date_str = today.strftime('%Y-%m-%d')
        invalid_facility_id = 99999
        
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[invalid_facility_id, date_str])
        )
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Facility not found')

    def test_invalid_date_format_returns_400(self):
        """Test that invalid date format returns 400 error."""
        self.client.login(username="student_api", password="testpass123")
        
        invalid_date = "2024/12/15"  # Wrong format
        
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, invalid_date])
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('error', data)
        self.assertIn('Invalid date format', data['error'])

    def test_handles_past_dates(self):
        """Acceptance Criteria 8: Endpoint should handle past dates."""
        self.client.login(username="student_api", password="testpass123")
        
        past_date = timezone.localdate() - datetime.timedelta(days=7)
        
        # Create a reservation in the past
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Past Event",
            reservation_date=past_date,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=Reservation.Status.COMPLETED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        date_str = past_date.strftime('%Y-%m-%d')
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        # Should still return 200 (past dates are valid)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        # But COMPLETED reservations should not be counted (only PENDING/APPROVED block time)
        self.assertEqual(len(data['reservations']), 0)

    def test_handles_future_dates(self):
        """Test that endpoint handles future dates correctly."""
        self.client.login(username="student_api", password="testpass123")
        
        future_date = timezone.localdate() + datetime.timedelta(days=30)
        
        # Create a future reservation
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Future Event",
            reservation_date=future_date,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        date_str = future_date.strftime('%Y-%m-%d')
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data['reservations']), 1)
        self.assertEqual(data['occupancy'], 20)  # 2 hours / 10 hours

    def test_only_pending_and_approved_reservations_counted(self):
        """Test that only PENDING and APPROVED reservations are shown."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        
        # Create reservations with different statuses
        # APPROVED - should be counted
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Approved",
            reservation_date=today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        # PENDING - should be counted
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Pending",
            reservation_date=today,
            start_time=datetime.time(11, 0),
            end_time=datetime.time(12, 0),
            status=Reservation.Status.PENDING,
        )
        
        # REJECTED - should NOT be counted
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Rejected",
            reservation_date=today,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(15, 0),
            status=Reservation.Status.REJECTED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
            rejection_reason="Not available",
        )
        
        # CANCELLED - should NOT be counted
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Cancelled",
            reservation_date=today,
            start_time=datetime.time(15, 0),
            end_time=datetime.time(16, 0),
            status=Reservation.Status.CANCELLED,
        )
        
        date_str = today.strftime('%Y-%m-%d')
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        data = json.loads(response.content)
        
        # Should only show APPROVED and PENDING (2 total)
        self.assertEqual(len(data['reservations']), 2)
        self.assertEqual(data['total_reservations'], 2)
        # Occupancy: 2 hours / 10 hours = 20%
        self.assertEqual(data['occupancy'], 20)

    def test_only_scheduled_maintenance_shown(self):
        """Test that only SCHEDULED maintenance is shown."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        
        # SCHEDULED - should be shown
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Scheduled",
            maintenance_date=today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=FacilityMaintenance.Status.SCHEDULED,
            created_by=self.admin,
        )
        
        # COMPLETED - should NOT be shown
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Completed",
            maintenance_date=today,
            start_time=datetime.time(11, 0),
            end_time=datetime.time(12, 0),
            status=FacilityMaintenance.Status.COMPLETED,
            created_by=self.admin,
        )
        
        # CANCELLED - should NOT be shown
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Cancelled",
            maintenance_date=today,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(15, 0),
            status=FacilityMaintenance.Status.CANCELLED,
            created_by=self.admin,
        )
        
        date_str = today.strftime('%Y-%m-%d')
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        data = json.loads(response.content)
        
        # Should only show SCHEDULED (1 total)
        self.assertEqual(len(data['maintenance']), 1)
        self.assertEqual(data['total_maintenance'], 1)
        self.assertEqual(data['maintenance'][0]['title'], 'Scheduled')

    def test_facility_unavailable_status(self):
        """Test response when facility status is UNAVAILABLE."""
        self.client.login(username="student_api", password="testpass123")
        
        # Change facility status to UNAVAILABLE
        self.facility.status = Facility.Status.UNAVAILABLE
        self.facility.save()
        
        today = timezone.localdate()
        date_str = today.strftime('%Y-%m-%d')
        
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        data = json.loads(response.content)
        
        # Should indicate facility is not available
        self.assertFalse(data['is_available'])
        self.assertEqual(data['status'], Facility.Status.UNAVAILABLE)

    def test_facility_maintenance_status(self):
        """Test response when facility status is MAINTENANCE."""
        self.client.login(username="student_api", password="testpass123")
        
        # Change facility status to MAINTENANCE
        self.facility.status = Facility.Status.MAINTENANCE
        self.facility.save()
        
        today = timezone.localdate()
        date_str = today.strftime('%Y-%m-%d')
        
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        data = json.loads(response.content)
        
        # Should indicate facility is not available
        self.assertFalse(data['is_available'])
        self.assertEqual(data['status'], Facility.Status.MAINTENANCE)

    def test_multiple_reservations_on_same_day(self):
        """Test endpoint with multiple reservations on the same day."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        
        # Create 5 reservations at different times
        for i in range(5):
            start_hour = 8 + (i * 2)
            end_hour = start_hour + 1
            
            Reservation.objects.create(
                requested_by=self.requestor,
                facility=self.facility,
                purpose=f"Event {i+1}",
                reservation_date=today,
                start_time=datetime.time(start_hour, 0),
                end_time=datetime.time(end_hour, 0),
                status=Reservation.Status.APPROVED,
                reviewed_by=self.staff,
                reviewed_at=timezone.now(),
            )
        
        date_str = today.strftime('%Y-%m-%d')
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        data = json.loads(response.content)
        
        # Should have 5 reservations
        self.assertEqual(len(data['reservations']), 5)
        self.assertEqual(data['total_reservations'], 5)
        # Occupancy: 5 hours / 10 hours = 50%
        self.assertEqual(data['occupancy'], 50)
        # Should be ordered by start_time
        for i in range(5):
            self.assertEqual(data['reservations'][i]['purpose'], f'Event {i+1}')

    def test_time_formatting_in_response(self):
        """Test that times are correctly formatted as HH:MM strings."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        
        # Create reservation with specific times
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Test",
            reservation_date=today,
            start_time=datetime.time(14, 30),
            end_time=datetime.time(16, 45),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        date_str = today.strftime('%Y-%m-%d')
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        data = json.loads(response.content)
        
        reservation = data['reservations'][0]
        # Times should be formatted as HH:MM
        self.assertEqual(reservation['start_time'], '14:30')
        self.assertEqual(reservation['end_time'], '16:45')

    def test_requester_name_in_response(self):
        """Test that requester name is included in reservation response."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        
        # Create a named requestor
        named_requestor = User.objects.create_user(
            username="john_doe",
            password="testpass123",
            email="john@test.com",
            first_name="John",
            last_name="Doe",
            role=User.Role.REQUESTER,
            user_type=User.UserType.STUDENT,
        )
        
        Reservation.objects.create(
            requested_by=named_requestor,
            facility=self.facility,
            purpose="Test",
            reservation_date=today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        date_str = today.strftime('%Y-%m-%d')
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        data = json.loads(response.content)
        
        reservation = data['reservations'][0]
        # Should contain requester name
        self.assertIn('requester', reservation)
        self.assertEqual(reservation['requester'], 'John Doe')

    def test_facility_details_in_response(self):
        """Test that facility details are included in response."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        date_str = today.strftime('%Y-%m-%d')
        
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        data = json.loads(response.content)
        
        # Check facility details
        self.assertEqual(data['facility_id'], self.facility.id)
        self.assertEqual(data['facility_name'], self.facility.name)
        self.assertTrue(data['is_available'])

    def test_edge_case_zero_duration_reservation(self):
        """Test handling of edge case: zero-duration reservations."""
        self.client.login(username="student_api", password="testpass123")
        
        today = timezone.localdate()
        
        # Create a zero-duration reservation (start_time == end_time)
        # This should be handled gracefully
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Zero duration",
            reservation_date=today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(9, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        date_str = today.strftime('%Y-%m-%d')
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        data = json.loads(response.content)
        
        # Should return 200 and handle gracefully
        self.assertEqual(response.status_code, 200)
        # Occupancy should be 0 (zero duration)
        self.assertEqual(data['occupancy'], 0)

    def test_iso_8601_date_format(self):
        """Test that endpoint accepts ISO 8601 date format (YYYY-MM-DD)."""
        self.client.login(username="student_api", password="testpass123")
        
        # Test with ISO 8601 format
        test_date = datetime.date(2024, 12, 25)
        date_str = test_date.strftime('%Y-%m-%d')
        
        response = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        
        # Should return 200
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        # Date should match
        self.assertEqual(data['date'], date_str)

    def test_different_facilities_isolated(self):
        """Test that different facilities return isolated data."""
        self.client.login(username="student_api", password="testpass123")
        
        # Create a second facility
        facility2 = Facility.objects.create(
            name="IT ComLab 2",
            location="Admin Building, 3rd Floor",
            capacity=25,
            facility_type=self.facility_type,
            status=Facility.Status.AVAILABLE,
            hours_of_operation="8am-6pm",
        )
        
        today = timezone.localdate()
        
        # Create reservation for facility1
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=self.facility,
            purpose="Facility 1 Event",
            reservation_date=today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        # Create reservation for facility2
        Reservation.objects.create(
            requested_by=self.requestor,
            facility=facility2,
            purpose="Facility 2 Event",
            reservation_date=today,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(16, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        date_str = today.strftime('%Y-%m-%d')
        
        # Get data for facility1
        response1 = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[self.facility.id, date_str])
        )
        data1 = json.loads(response1.content)
        
        # Get data for facility2
        response2 = self.client.get(
            reverse('facilities:api_calendar_day', 
                   args=[facility2.id, date_str])
        )
        data2 = json.loads(response2.content)
        
        # Data should be different
        self.assertEqual(len(data1['reservations']), 1)
        self.assertEqual(len(data2['reservations']), 1)
        self.assertEqual(data1['reservations'][0]['purpose'], 'Facility 1 Event')
        self.assertEqual(data2['reservations'][0]['purpose'], 'Facility 2 Event')
        self.assertEqual(data1['occupancy'], 10)  # 1 hour / 10 hours
        self.assertEqual(data2['occupancy'], 20)  # 2 hours / 10 hours
