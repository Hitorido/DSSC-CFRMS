"""
Tests for the color-coded facility booking calendar feature (Task 3).

Tests occupancy calculation, color-coding logic, and tooltip functionality.
"""

import datetime
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from facilities.models import Facility, FacilityType, FacilityMaintenance
from reservations.models import Reservation

User = get_user_model()


class OccupancyColorCodeTestCase(TestCase):
    """Test occupancy percentage calculations and color-coding logic."""

    def setUp(self):
        """Set up test facilities and users."""
        self.facility_type = FacilityType.objects.create(
            name="Computer Lab"
        )
        self.facility = Facility.objects.create(
            name="ComLab 1",
            location="Building A",
            capacity=30,
            facility_type=self.facility_type,
            status=Facility.Status.AVAILABLE,
        )
        
        self.student = User.objects.create_user(
            username="student1",
            password="testpass123",
            email="student1@test.com",
            role=User.Role.REQUESTER,
            user_type=User.UserType.STUDENT,
        )
        
        self.staff = User.objects.create_user(
            username="staff1",
            password="testpass123",
            email="staff1@test.com",
            role=User.Role.STAFF,
            user_type=User.UserType.STUDENT,  # Staff still has a user_type
        )

    def test_occupancy_color_green_0_33_percent(self):
        """Test that 0-33% occupancy maps to GREEN color."""
        from facilities.views import _compute_occupancy_color
        
        # 0% should be green
        self.assertEqual(_compute_occupancy_color(0), 'green')
        # 33% should be green
        self.assertEqual(_compute_occupancy_color(33), 'green')
        # 32% should be green
        self.assertEqual(_compute_occupancy_color(32), 'green')

    def test_occupancy_color_yellow_34_66_percent(self):
        """Test that 34-66% occupancy maps to YELLOW color."""
        from facilities.views import _compute_occupancy_color
        
        # 34% should be yellow
        self.assertEqual(_compute_occupancy_color(34), 'yellow')
        # 50% should be yellow
        self.assertEqual(_compute_occupancy_color(50), 'yellow')
        # 66% should be yellow
        self.assertEqual(_compute_occupancy_color(66), 'yellow')

    def test_occupancy_color_red_67_100_percent(self):
        """Test that 67-100% occupancy maps to RED color."""
        from facilities.views import _compute_occupancy_color
        
        # 67% should be red
        self.assertEqual(_compute_occupancy_color(67), 'red')
        # 85% should be red
        self.assertEqual(_compute_occupancy_color(85), 'red')
        # 100% should be red
        self.assertEqual(_compute_occupancy_color(100), 'red')

    def test_occupancy_color_gray_unavailable(self):
        """Test that None (unavailable) maps to GRAY color."""
        from facilities.views import _compute_occupancy_color
        
        self.assertEqual(_compute_occupancy_color(None), 'gray')

    def test_calculate_daily_occupancy_no_reservations(self):
        """Test occupancy calculation for a day with no reservations."""
        from facilities.views import _calculate_daily_occupancy
        
        test_date = datetime.date.today()
        result = _calculate_daily_occupancy(test_date, {}, self.facility)
        
        occupancy_percent, reservation_count = result
        self.assertEqual(occupancy_percent, 0)
        self.assertEqual(reservation_count, 0)

    def test_calculate_daily_occupancy_single_reservation(self):
        """Test occupancy calculation for a day with one reservation."""
        from facilities.views import _calculate_daily_occupancy
        
        test_date = datetime.date.today()
        
        # Create a 2-hour reservation (120 minutes)
        # Operating day is 10 hours (600 minutes)
        # Occupancy = 120/600 = 20%
        reservations_by_date = {
            test_date: [
                {
                    'start_time': datetime.time(9, 0),
                    'end_time': datetime.time(11, 0),
                }
            ]
        }
        
        result = _calculate_daily_occupancy(test_date, reservations_by_date, self.facility)
        occupancy_percent, reservation_count = result
        
        self.assertEqual(occupancy_percent, 20)
        self.assertEqual(reservation_count, 1)

    def test_calculate_daily_occupancy_multiple_reservations(self):
        """Test occupancy calculation for a day with multiple reservations."""
        from facilities.views import _calculate_daily_occupancy
        
        test_date = datetime.date.today()
        
        # Create two 2-hour reservations (240 minutes total)
        # Operating day is 10 hours (600 minutes)
        # Occupancy = 240/600 = 40%
        reservations_by_date = {
            test_date: [
                {
                    'start_time': datetime.time(9, 0),
                    'end_time': datetime.time(11, 0),
                },
                {
                    'start_time': datetime.time(14, 0),
                    'end_time': datetime.time(16, 0),
                }
            ]
        }
        
        result = _calculate_daily_occupancy(test_date, reservations_by_date, self.facility)
        occupancy_percent, reservation_count = result
        
        self.assertEqual(occupancy_percent, 40)
        self.assertEqual(reservation_count, 2)

    def test_calculate_daily_occupancy_full_day(self):
        """Test occupancy calculation for a fully booked day."""
        from facilities.views import _calculate_daily_occupancy
        
        test_date = datetime.date.today()
        
        # Create one 10-hour reservation (600 minutes)
        # Operating day is 10 hours (600 minutes)
        # Occupancy = 600/600 = 100%
        reservations_by_date = {
            test_date: [
                {
                    'start_time': datetime.time(8, 0),
                    'end_time': datetime.time(18, 0),
                }
            ]
        }
        
        result = _calculate_daily_occupancy(test_date, reservations_by_date, self.facility)
        occupancy_percent, reservation_count = result
        
        self.assertEqual(occupancy_percent, 100)
        self.assertEqual(reservation_count, 1)

    def test_calculate_daily_occupancy_capped_at_100(self):
        """Test that occupancy never exceeds 100%."""
        from facilities.views import _calculate_daily_occupancy
        
        test_date = datetime.date.today()
        
        # Create overlapping reservations that exceed 10 hours
        reservations_by_date = {
            test_date: [
                {
                    'start_time': datetime.time(8, 0),
                    'end_time': datetime.time(18, 0),
                },
                {
                    'start_time': datetime.time(10, 0),
                    'end_time': datetime.time(16, 0),
                }
            ]
        }
        
        result = _calculate_daily_occupancy(test_date, reservations_by_date, self.facility)
        occupancy_percent, reservation_count = result
        
        # Should be capped at 100, not 200
        self.assertEqual(occupancy_percent, 100)
        self.assertEqual(reservation_count, 2)


class FacilityBookingCalendarViewTestCase(TestCase):
    """Test facility booking calendar view renders correctly."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        
        self.facility_type = FacilityType.objects.create(
            name="Classroom"
        )
        self.facility = Facility.objects.create(
            name="Room 101",
            location="Building B",
            capacity=40,
            facility_type=self.facility_type,
            status=Facility.Status.AVAILABLE,
        )
        
        self.student = User.objects.create_user(
            username="student2",
            password="testpass123",
            email="student2@test.com",
            role=User.Role.REQUESTER,
            user_type=User.UserType.STUDENT,
        )
        
        self.staff = User.objects.create_user(
            username="staff2",
            password="testpass123",
            email="staff2@test.com",
            role=User.Role.STAFF,
            user_type=User.UserType.STUDENT,
        )

    def test_facility_detail_view_accessible(self):
        """Test that facility detail view loads without errors."""
        self.client.login(username="student2", password="testpass123")
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('calendar_weeks', response.context)

    def test_facility_calendar_has_occupancy_data(self):
        """Test that calendar context includes occupancy percentages."""
        self.client.login(username="student2", password="testpass123")
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        calendar_weeks = response.context['calendar_weeks']
        
        # Check that each day has occupancy_percent and color_code
        for week in calendar_weeks:
            for day in week:
                self.assertIn('occupancy_percent', day)
                self.assertIn('color_code', day)

    def test_facility_calendar_color_green_with_no_reservations(self):
        """Test that days with no reservations are GREEN."""
        self.client.login(username="student2", password="testpass123")
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        calendar_weeks = response.context['calendar_weeks']
        today = timezone.localdate()
        
        # Find today's entry
        for week in calendar_weeks:
            for day in week:
                if day['date'] == today and day['in_month']:
                    # Today should be green (no reservations)
                    self.assertEqual(day['color_code'], 'green')
                    self.assertEqual(day['occupancy_percent'], 0)
                    break

    def test_facility_calendar_has_tooltip_data(self):
        """Test that calendar renders tooltip content."""
        self.client.login(username="student2", password="testpass123")
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        # Check that the response contains tooltip HTML elements
        self.assertIn('facility-calendar-tooltip', response.content.decode())
        self.assertIn('tooltip-header', response.content.decode())
        self.assertIn('tooltip-content', response.content.decode())

    def test_facility_calendar_with_reservations_shows_color(self):
        """Test that days with reservations show appropriate colors."""
        self.client.login(username="student2", password="testpass123")
        
        # Create a reservation for today
        today = timezone.localdate()
        reservation = Reservation.objects.create(
            requested_by=self.student,
            facility=self.facility,
            purpose="Study session",
            reservation_date=today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 30),  # 1.5 hours = 90 minutes
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        calendar_weeks = response.context['calendar_weeks']
        
        # Find today's entry
        for week in calendar_weeks:
            for day in week:
                if day['date'] == today and day['in_month']:
                    # Occupancy should be 15% (90/600)
                    self.assertEqual(day['occupancy_percent'], 15)
                    # 15% should be green
                    self.assertEqual(day['color_code'], 'green')
                    break

    def test_facility_calendar_unavailable_facility_is_gray(self):
        """Test that UNAVAILABLE facility shows GRAY for all days."""
        self.client.login(username="student2", password="testpass123")
        
        # Change facility status to UNAVAILABLE
        self.facility.status = Facility.Status.UNAVAILABLE
        self.facility.save()
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        calendar_weeks = response.context['calendar_weeks']
        today = timezone.localdate()
        
        # Find today's entry
        for week in calendar_weeks:
            for day in week:
                if day['date'] == today and day['in_month']:
                    # Should be gray when facility is unavailable
                    self.assertEqual(day['color_code'], 'gray')
                    break

    def test_facility_calendar_past_dates_are_gray(self):
        """Test that past dates are shown as GRAY."""
        self.client.login(username="student2", password="testpass123")
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        calendar_weeks = response.context['calendar_weeks']
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        
        # Find yesterday's entry
        for week in calendar_weeks:
            for day in week:
                if day['date'] == yesterday:
                    # Past dates should be gray
                    self.assertEqual(day['color_code'], 'gray')
                    break


class CalendarTooltipEdgeCasesTestCase(TestCase):
    """Test edge cases for calendar tooltip display."""

    def setUp(self):
        """Set up test data."""
        self.facility_type = FacilityType.objects.create(
            name="Auditorium"
        )
        self.facility = Facility.objects.create(
            name="Main Hall",
            location="Building C",
            capacity=200,
            facility_type=self.facility_type,
            status=Facility.Status.AVAILABLE,
        )
        
        self.student = User.objects.create_user(
            username="student3",
            password="testpass123",
            email="student3@test.com",
            role=User.Role.REQUESTER,
            user_type=User.UserType.STUDENT,
        )
        
        self.staff = User.objects.create_user(
            username="staff3",
            password="testpass123",
            email="staff3@test.com",
            role=User.Role.STAFF,
            user_type=User.UserType.STUDENT,
        )
        
        self.client = Client()

    def test_tooltip_no_reservations(self):
        """Test tooltip displays correctly when no reservations exist."""
        self.client.login(username="student3", password="testpass123")
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        # Check that tooltip shows "No reservations or maintenance scheduled"
        self.assertIn('No reservations or maintenance scheduled', response.content.decode())

    def test_tooltip_multiple_reservations(self):
        """Test tooltip displays multiple reservations for same day."""
        self.client.login(username="student3", password="testpass123")
        
        today = timezone.localdate()
        
        # Create two reservations
        # First: 9:00-10:30 = 90 minutes
        # Second: 14:00-16:00 = 120 minutes
        # Total: 210 minutes / 600 minutes = 35%
        Reservation.objects.create(
            requested_by=self.student,
            facility=self.facility,
            purpose="Morning class",
            reservation_date=today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 30),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        Reservation.objects.create(
            requested_by=self.student,
            facility=self.facility,
            purpose="Afternoon event",
            reservation_date=today,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(16, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        calendar_weeks = response.context['calendar_weeks']
        
        # Find today's entry
        for week in calendar_weeks:
            for day in week:
                if day['date'] == today and day['in_month']:
                    # Should have 2 events
                    self.assertEqual(len(day['events']), 2)
                    # Occupancy should be 35% (210 minutes / 600 minutes)
                    self.assertEqual(day['occupancy_percent'], 35)
                    break

    def test_tooltip_fully_booked_day_is_red(self):
        """Test that fully booked day (67%+ occupancy) shows RED."""
        self.client.login(username="student3", password="testpass123")
        
        today = timezone.localdate()
        
        # Create a 7-hour reservation (420 minutes)
        # Occupancy = 420/600 = 70%
        Reservation.objects.create(
            requested_by=self.student,
            facility=self.facility,
            purpose="All-day event",
            reservation_date=today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(16, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        calendar_weeks = response.context['calendar_weeks']
        
        # Find today's entry
        for week in calendar_weeks:
            for day in week:
                if day['date'] == today and day['in_month']:
                    # Should be red (70% occupancy)
                    self.assertEqual(day['color_code'], 'red')
                    self.assertEqual(day['occupancy_percent'], 70)
                    break


class MaintenanceInTooltipTestCase(TestCase):
    """Test Task 4: Tooltips show both reservations and maintenance records."""

    def setUp(self):
        """Set up test data with facility, maintenance records, and reservations."""
        self.facility_type = FacilityType.objects.create(
            name="Computer Lab"
        )
        self.facility = Facility.objects.create(
            name="ComLab 2",
            location="Building D",
            capacity=25,
            facility_type=self.facility_type,
            status=Facility.Status.AVAILABLE,
        )
        
        self.student = User.objects.create_user(
            username="student_maintenance",
            password="testpass123",
            email="student_maintenance@test.com",
            role=User.Role.REQUESTER,
            user_type=User.UserType.STUDENT,
        )
        
        self.staff = User.objects.create_user(
            username="staff_maintenance",
            password="testpass123",
            email="staff_maintenance@test.com",
            role=User.Role.STAFF,
            user_type=User.UserType.STUDENT,
        )
        
        self.admin = User.objects.create_user(
            username="admin_maintenance",
            password="testpass123",
            email="admin_maintenance@test.com",
            role=User.Role.ADMIN,
            user_type=User.UserType.STUDENT,
        )
        
        self.client = Client()

    def test_tooltip_with_maintenance_only(self):
        """Test tooltip displays maintenance record when no reservations exist."""
        self.client.login(username="student_maintenance", password="testpass123")
        
        today = timezone.localdate()
        
        # Create a SCHEDULED maintenance record
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Hardware inspection",
            description="Annual inspection of lab equipment",
            maintenance_date=today,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
            status=FacilityMaintenance.Status.SCHEDULED,
            created_by=self.admin,
        )
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        calendar_weeks = response.context['calendar_weeks']
        
        # Find today's entry
        for week in calendar_weeks:
            for day in week:
                if day['date'] == today and day['in_month']:
                    # Should have 1 event (the maintenance)
                    self.assertEqual(len(day['events']), 1)
                    event = day['events'][0]
                    # Event should be marked as maintenance
                    self.assertEqual(event['kind'], 'maintenance')
                    self.assertEqual(event['label'], 'Maintenance')
                    self.assertEqual(event['status_class'], 'maintenance')
                    break

    def test_tooltip_with_both_reservations_and_maintenance(self):
        """Test tooltip displays both reservations and maintenance together."""
        self.client.login(username="student_maintenance", password="testpass123")
        
        today = timezone.localdate()
        
        # Create a reservation
        Reservation.objects.create(
            requested_by=self.student,
            facility=self.facility,
            purpose="Lab work",
            reservation_date=today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        # Create a maintenance record
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Software update",
            description="Update lab management software",
            maintenance_date=today,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(15, 30),
            status=FacilityMaintenance.Status.SCHEDULED,
            created_by=self.admin,
        )
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        calendar_weeks = response.context['calendar_weeks']
        
        # Find today's entry
        for week in calendar_weeks:
            for day in week:
                if day['date'] == today and day['in_month']:
                    # Should have 2 events
                    self.assertEqual(len(day['events']), 2)
                    
                    # First event should be reservation
                    self.assertEqual(day['events'][0]['kind'], 'reservation')
                    self.assertIn('approved', day['events'][0]['status_class'])
                    
                    # Second event should be maintenance
                    self.assertEqual(day['events'][1]['kind'], 'maintenance')
                    self.assertEqual(day['events'][1]['status_class'], 'maintenance')
                    break

    def test_tooltip_maintenance_visually_distinguished(self):
        """Test that maintenance events are visually distinguished in tooltip."""
        self.client.login(username="student_maintenance", password="testpass123")
        
        today = timezone.localdate()
        
        # Create a maintenance record
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Cooling system maintenance",
            description="Check A/C units",
            maintenance_date=today,
            start_time=datetime.time(11, 0),
            end_time=datetime.time(12, 30),
            status=FacilityMaintenance.Status.SCHEDULED,
            created_by=self.admin,
        )
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        content = response.content.decode()
        
        # Check that maintenance is rendered with specific icon and styling
        # The template uses bi-tools icon for maintenance
        self.assertIn('bi-tools', content)
        # Check for maintenance event class
        self.assertIn('event-maintenance', content)

    def test_tooltip_scheduled_maintenance_shown(self):
        """Test that SCHEDULED maintenance is shown in tooltip."""
        self.client.login(username="student_maintenance", password="testpass123")
        
        today = timezone.localdate()
        
        # Create a SCHEDULED maintenance record
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Scheduled service",
            maintenance_date=today,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(9, 0),
            status=FacilityMaintenance.Status.SCHEDULED,
            created_by=self.admin,
        )
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        calendar_weeks = response.context['calendar_weeks']
        
        # Find today's entry
        for week in calendar_weeks:
            for day in week:
                if day['date'] == today and day['in_month']:
                    # Should have the scheduled maintenance event
                    self.assertEqual(len(day['events']), 1)
                    self.assertEqual(day['events'][0]['kind'], 'maintenance')
                    break

    def test_tooltip_completed_maintenance_not_shown(self):
        """Test that COMPLETED maintenance is NOT shown in tooltip."""
        self.client.login(username="student_maintenance", password="testpass123")
        
        today = timezone.localdate()
        
        # Create a COMPLETED maintenance record
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Completed maintenance",
            maintenance_date=today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=FacilityMaintenance.Status.COMPLETED,
            created_by=self.admin,
        )
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        calendar_weeks = response.context['calendar_weeks']
        
        # Find today's entry
        for week in calendar_weeks:
            for day in week:
                if day['date'] == today and day['in_month']:
                    # Should have no events (completed maintenance not shown)
                    self.assertEqual(len(day['events']), 0)
                    break

    def test_tooltip_cancelled_maintenance_not_shown(self):
        """Test that CANCELLED maintenance is NOT shown in tooltip."""
        self.client.login(username="student_maintenance", password="testpass123")
        
        today = timezone.localdate()
        
        # Create a CANCELLED maintenance record
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Cancelled maintenance",
            maintenance_date=today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=FacilityMaintenance.Status.CANCELLED,
            created_by=self.admin,
        )
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        calendar_weeks = response.context['calendar_weeks']
        
        # Find today's entry
        for week in calendar_weeks:
            for day in week:
                if day['date'] == today and day['in_month']:
                    # Should have no events (cancelled maintenance not shown)
                    self.assertEqual(len(day['events']), 0)
                    break

    def test_tooltip_no_events_message(self):
        """Test that 'No events' message shows when neither reservations nor maintenance exist."""
        self.client.login(username="student_maintenance", password="testpass123")
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        content = response.content.decode()
        
        # Check that the "No reservations or maintenance scheduled" message appears
        self.assertIn('No reservations or maintenance scheduled', content)

    def test_admin_calendar_shows_maintenance(self):
        """Test that admin staff can see maintenance in calendar tooltips."""
        self.client.login(username="staff_maintenance", password="testpass123")
        
        today = timezone.localdate()
        
        # Create maintenance
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Staff visible maintenance",
            maintenance_date=today,
            start_time=datetime.time(15, 0),
            end_time=datetime.time(16, 30),
            status=FacilityMaintenance.Status.SCHEDULED,
            created_by=self.admin,
        )
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        calendar_weeks = response.context['calendar_weeks']
        
        # Find today's entry
        for week in calendar_weeks:
            for day in week:
                if day['date'] == today and day['in_month']:
                    # Staff should see the maintenance event
                    self.assertEqual(len(day['events']), 1)
                    self.assertEqual(day['events'][0]['kind'], 'maintenance')
                    break

    def test_maintenance_blocks_availability(self):
        """Test that SCHEDULED maintenance blocks time slots (blocks_availability flag)."""
        self.client.login(username="student_maintenance", password="testpass123")
        
        today = timezone.localdate()
        
        # Create a SCHEDULED maintenance record
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Blocking maintenance",
            maintenance_date=today,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(11, 0),
            status=FacilityMaintenance.Status.SCHEDULED,
            created_by=self.admin,
        )
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        calendar_weeks = response.context['calendar_weeks']
        
        # Find today's entry
        for week in calendar_weeks:
            for day in week:
                if day['date'] == today and day['in_month']:
                    # Check that the event has blocks_availability flag set
                    self.assertEqual(len(day['events']), 1)
                    event = day['events'][0]
                    self.assertTrue(event['blocks_availability'])
                    # Availability should show "Limited"
                    self.assertEqual(day['availability_label'], 'Limited')
                    break

    def test_multiple_maintenance_windows_same_day(self):
        """Test tooltip with multiple maintenance windows on same day."""
        self.client.login(username="student_maintenance", password="testpass123")
        
        today = timezone.localdate()
        
        # Create first maintenance window
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Morning maintenance",
            maintenance_date=today,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(9, 0),
            status=FacilityMaintenance.Status.SCHEDULED,
            created_by=self.admin,
        )
        
        # Create second maintenance window
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Afternoon maintenance",
            maintenance_date=today,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(15, 30),
            status=FacilityMaintenance.Status.SCHEDULED,
            created_by=self.admin,
        )
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        calendar_weeks = response.context['calendar_weeks']
        
        # Find today's entry
        for week in calendar_weeks:
            for day in week:
                if day['date'] == today and day['in_month']:
                    # Should have 2 maintenance events
                    self.assertEqual(len(day['events']), 2)
                    # Both should be maintenance
                    for event in day['events']:
                        self.assertEqual(event['kind'], 'maintenance')
                    break

    def test_maintenance_times_displayed_in_tooltip(self):
        """Test that maintenance times are displayed correctly in tooltip."""
        self.client.login(username="student_maintenance", password="testpass123")
        
        today = timezone.localdate()
        
        # Create maintenance with specific times
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Timed maintenance",
            maintenance_date=today,
            start_time=datetime.time(13, 30),
            end_time=datetime.time(14, 45),
            status=FacilityMaintenance.Status.SCHEDULED,
            created_by=self.admin,
        )
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        calendar_weeks = response.context['calendar_weeks']
        
        # Find today's entry
        for week in calendar_weeks:
            for day in week:
                if day['date'] == today and day['in_month']:
                    event = day['events'][0]
                    # Check times are correctly set
                    self.assertEqual(event['start_time'], datetime.time(13, 30))
                    self.assertEqual(event['end_time'], datetime.time(14, 45))
                    break

    def test_maintenance_and_reservation_same_day_sorted(self):
        """Test that events are sorted by time when maintenance and reservations exist."""
        self.client.login(username="student_maintenance", password="testpass123")
        
        today = timezone.localdate()
        
        # Create maintenance at 9:00-10:00
        FacilityMaintenance.objects.create(
            facility=self.facility,
            title="Morning maintenance",
            maintenance_date=today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=FacilityMaintenance.Status.SCHEDULED,
            created_by=self.admin,
        )
        
        # Create reservation at 14:00-15:00
        Reservation.objects.create(
            requested_by=self.student,
            facility=self.facility,
            purpose="Afternoon work",
            reservation_date=today,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(15, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
        )
        
        response = self.client.get(
            reverse('facilities:facility_detail', args=[self.facility.pk])
        )
        
        calendar_weeks = response.context['calendar_weeks']
        
        # Find today's entry
        for week in calendar_weeks:
            for day in week:
                if day['date'] == today and day['in_month']:
                    # Should have 2 events, sorted by start time
                    self.assertEqual(len(day['events']), 2)
                    # Maintenance (9:00) should come before reservation (14:00)
                    self.assertEqual(day['events'][0]['start_time'], datetime.time(9, 0))
                    self.assertEqual(day['events'][1]['start_time'], datetime.time(14, 0))
                    break
