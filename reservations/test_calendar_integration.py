"""
Test suite for calendar integration into reservation form (Task 4).

Validates:
1. Calendar component renders in reservation form date step
2. Calendar fetches occupancy data from calendar API
3. Calendar events are properly displayed with color coding
4. Calendar date selection populates the hidden date field
5. Date selection moves user to time step
6. Facility change reloads calendar data
7. Form submission works with calendar-selected date
8. Mobile responsiveness (responsive calendar)
9. Native date input fallback for accessibility
"""

import datetime
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from facilities.models import Facility, FacilityType, FacilityMaintenance
from reservations.models import Reservation

User = get_user_model()


class CalendarIntegrationTestCase(TestCase):
    """Test calendar integration into reservation form."""

    def setUp(self):
        """Set up test data."""
        # Create a test user
        self.user = User.objects.create_user(
            username='test_requester',
            email='test@dssc.edu.ph',
            password='testpassword123',
            role=User.Role.REQUESTER,
        )

        # Create facility type
        self.facility_type = FacilityType.objects.create(
            name='Test Facility Type',
            description='For testing calendar integration',
        )

        # Create test facilities
        self.facility1 = Facility.objects.create(
            facility_type=self.facility_type,
            name='Test Facility 1',
            location='Building A',
            capacity=100,
            status=Facility.Status.AVAILABLE,
            hours_of_operation='8am-6pm',
        )

        self.facility2 = Facility.objects.create(
            facility_type=self.facility_type,
            name='Test Facility 2',
            location='Building B',
            capacity=50,
            status=Facility.Status.AVAILABLE,
            hours_of_operation='9am-5pm',
        )

        # Create some test reservations for today/tomorrow
        self.tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        self.today = timezone.localdate()

        self.reservation1 = Reservation.objects.create(
            requested_by=self.user,
            facility=self.facility1,
            purpose='Team Meeting',
            reservation_date=self.tomorrow,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
            status=Reservation.Status.APPROVED,
        )

        self.reservation2 = Reservation.objects.create(
            requested_by=self.user,
            facility=self.facility1,
            purpose='Project Review',
            reservation_date=self.tomorrow,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(15, 30),
            status=Reservation.Status.APPROVED,
        )

        # Create maintenance record
        self.maintenance = FacilityMaintenance.objects.create(
            facility=self.facility1,
            title='Equipment Calibration',
            maintenance_date=self.tomorrow,
            start_time=datetime.time(16, 0),
            end_time=datetime.time(17, 0),
            status=FacilityMaintenance.Status.SCHEDULED,
        )

        self.client = Client()

    def test_calendar_component_renders_in_form(self):
        """Test that calendar component is included in reservation form."""
        self.client.login(username='test_requester', password='testpassword123')

        response = self.client.get(reverse('reservations:create_reservation'))

        self.assertEqual(response.status_code, 200)
        # Check for calendar component
        self.assertIn(b'facility-calendar-widget', response.content)
        self.assertIn(b'facility_calendar_widget.html', response.content)
        # Check for calendar container
        self.assertIn(b'facilityCalendarContainer', response.content)

    def test_calendar_component_has_initial_facility(self):
        """Test that calendar component receives facility_id when facility is selected."""
        self.client.login(username='test_requester', password='testpassword123')

        # Request form with facility pre-selected via query parameter
        response = self.client.get(
            reverse('reservations:create_reservation'),
            {'facility': self.facility1.id}
        )

        self.assertEqual(response.status_code, 200)
        # Check that the form has the facility selected
        self.assertIn(
            f'value="{self.facility1.id}"'.encode(),
            response.content
        )

    def test_calendar_api_returns_occupancy_data(self):
        """Test that calendar API returns correct occupancy data."""
        self.client.login(username='test_requester', password='testpassword123')

        # Call calendar API
        response = self.client.get(
            reverse(
                'facilities:api_calendar_day',
                kwargs={
                    'facility_id': self.facility1.id,
                    'date_str': self.tomorrow.isoformat(),
                }
            )
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify response structure
        self.assertIn('occupancy', data)
        self.assertIn('reservations', data)
        self.assertIn('maintenance', data)
        self.assertIn('is_available', data)
        self.assertIn('date', data)

        # Verify reservations data
        self.assertEqual(len(data['reservations']), 2)
        self.assertEqual(data['reservations'][0]['purpose'], 'Team Meeting')
        self.assertEqual(data['reservations'][1]['purpose'], 'Project Review')

        # Verify maintenance data
        self.assertEqual(len(data['maintenance']), 1)
        self.assertEqual(data['maintenance'][0]['title'], 'Equipment Calibration')

        # Verify occupancy percentage
        # Should be between 0 and 100
        self.assertGreaterEqual(data['occupancy'], 0)
        self.assertLessEqual(data['occupancy'], 100)

    def test_calendar_api_filters_by_status(self):
        """Test that calendar API only includes PENDING and APPROVED reservations."""
        # Create rejected reservation
        rejected_res = Reservation.objects.create(
            requested_by=self.user,
            facility=self.facility1,
            purpose='Rejected Meeting',
            reservation_date=self.tomorrow,
            start_time=datetime.time(13, 0),
            end_time=datetime.time(14, 0),
            status=Reservation.Status.REJECTED,
        )

        self.client.login(username='test_requester', password='testpassword123')

        response = self.client.get(
            reverse(
                'facilities:api_calendar_day',
                kwargs={
                    'facility_id': self.facility1.id,
                    'date_str': self.tomorrow.isoformat(),
                }
            )
        )

        data = response.json()
        # Should only have 2 reservations (not the rejected one)
        self.assertEqual(len(data['reservations']), 2)

    def test_calendar_api_handles_unavailable_facility(self):
        """Test that calendar API marks unavailable facilities correctly."""
        self.client.login(username='test_requester', password='testpassword123')

        # Create unavailable facility
        unavailable = Facility.objects.create(
            facility_type=self.facility_type,
            name='Unavailable Facility',
            location='Building C',
            capacity=50,
            status=Facility.Status.UNAVAILABLE,
        )

        response = self.client.get(
            reverse(
                'facilities:api_calendar_day',
                kwargs={
                    'facility_id': unavailable.id,
                    'date_str': self.tomorrow.isoformat(),
                }
            )
        )

        data = response.json()
        self.assertFalse(data['is_available'])
        self.assertEqual(data['status'], Facility.Status.UNAVAILABLE)

    def test_native_date_input_fallback(self):
        """Test that native date input is present as accessibility fallback."""
        self.client.login(username='test_requester', password='testpassword123')

        response = self.client.get(reverse('reservations:create_reservation'))

        # Check for native date input
        self.assertIn(b'type="date"', response.content)
        self.assertIn(b'id_reservation_date', response.content)
        # Should be marked as fallback/accessibility
        self.assertIn(b'reservation-calendar-native', response.content)

    def test_form_has_hidden_date_field(self):
        """Test that form has the hidden date field for calendar to populate."""
        self.client.login(username='test_requester', password='testpassword123')

        response = self.client.get(reverse('reservations:create_reservation'))

        # Check for the date field
        self.assertIn(b'name="reservation_date"', response.content)

    def test_calendar_event_handling_javascript(self):
        """Test that calendar event handling JavaScript is present."""
        self.client.login(username='test_requester', password='testpassword123')

        response = self.client.get(reverse('reservations:create_reservation'))

        content = response.content.decode('utf-8')

        # Check for calendar event listener
        self.assertIn('calendarDateSelected', content)
        # Check for date field update logic
        self.assertIn('dateInput.value', content)
        # Check for step transition logic
        self.assertIn('showTimeStep', content)

    def test_facility_change_event_handler(self):
        """Test that facility change triggers calendar refresh."""
        self.client.login(username='test_requester', password='testpassword123')

        response = self.client.get(reverse('reservations:create_reservation'))

        content = response.content.decode('utf-8')

        # Check for facility change listener
        self.assertIn('facilitySelect.addEventListener', content)
        self.assertIn('facilityChanged', content)
        self.assertIn('facilityCalendarContainer', content)

    def test_calendar_api_month_endpoint(self):
        """Test that calendar month API endpoint works."""
        self.client.login(username='test_requester', password='testpassword123')

        today = timezone.localdate()
        response = self.client.get(
            reverse(
                'facilities:api_calendar_month',
                kwargs={
                    'facility_id': self.facility1.id,
                    'year': today.year,
                    'month': today.month,
                }
            )
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify structure
        self.assertIn('year', data)
        self.assertIn('month', data)
        self.assertIn('days', data)
        self.assertIn('facility_id', data)

        # Verify days data
        for day_num, day_data in data['days'].items():
            self.assertIn('occupancy', day_data)
            self.assertIn('reservations', day_data)
            self.assertIn('maintenance', day_data)

    def test_calendar_component_renders_styles(self):
        """Test that calendar component includes styling."""
        self.client.login(username='test_requester', password='testpassword123')

        response = self.client.get(reverse('reservations:create_reservation'))

        content = response.content.decode('utf-8')

        # Check for calendar CSS classes
        self.assertIn('facility-calendar-widget', content)
        self.assertIn('calendar-month-nav', content)
        self.assertIn('calendar-grid', content)
        self.assertIn('day-available-low', content)
        self.assertIn('day-available-moderate', content)
        self.assertIn('day-available-high', content)
        self.assertIn('day-unavailable', content)

    def test_calendar_component_has_legend(self):
        """Test that calendar component includes color legend."""
        self.client.login(username='test_requester', password='testpassword123')

        response = self.client.get(reverse('reservations:create_reservation'))

        content = response.content.decode('utf-8')

        # Check for legend
        self.assertIn('calendar-legend', content)
        self.assertIn('0-33% occupied', content)
        self.assertIn('34-66% occupied', content)
        self.assertIn('67-100% occupied', content)
        self.assertIn('Unavailable', content)

    def test_form_submission_with_calendar_selected_date(self):
        """Test that form submission works with calendar-selected date."""
        self.client.login(username='test_requester', password='testpassword123')

        # Submit form with calendar-selected date
        future_date = timezone.localdate() + datetime.timedelta(days=5)

        response = self.client.post(
            reverse('reservations:create_reservation'),
            {
                'facility': self.facility1.id,
                'purpose': 'Calendar Integration Test',
                'reservation_date': future_date.isoformat(),
                'start_time': '10:00',
                'end_time': '12:00',
            }
        )

        # Should redirect to my_reservations on success
        self.assertEqual(response.status_code, 302)
        self.assertIn('my_reservations', response.url)

        # Verify reservation was created
        reservation = Reservation.objects.filter(
            requested_by=self.user,
            facility=self.facility1,
            purpose='Calendar Integration Test'
        ).first()

        self.assertIsNotNone(reservation)
        self.assertEqual(reservation.reservation_date, future_date)
        self.assertEqual(str(reservation.start_time), '10:00:00')
        self.assertEqual(str(reservation.end_time), '12:00:00')

    def test_calendar_preserves_form_state(self):
        """Test that calendar integration doesn't break existing form state."""
        self.client.login(username='test_requester', password='testpassword123')

        # Load form with initial values
        future_date = timezone.localdate() + datetime.timedelta(days=3)

        response = self.client.get(
            reverse('reservations:create_reservation'),
            {
                'facility': self.facility1.id,
                'date': future_date.isoformat(),
            }
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Check that facility is selected
        self.assertIn(f'value="{self.facility1.id}"', content)
        # Check that date is in the form
        self.assertIn(future_date.isoformat(), content)

    def test_calendar_api_requires_authentication(self):
        """Test that calendar API requires authentication."""
        response = self.client.get(
            reverse(
                'facilities:api_calendar_day',
                kwargs={
                    'facility_id': self.facility1.id,
                    'date_str': self.tomorrow.isoformat(),
                }
            )
        )

        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_calendar_component_has_navigation(self):
        """Test that calendar component has month navigation."""
        self.client.login(username='test_requester', password='testpassword123')

        response = self.client.get(reverse('reservations:create_reservation'))

        content = response.content.decode('utf-8')

        # Check for navigation elements
        self.assertIn('data-action="prev-month"', content)
        self.assertIn('data-action="next-month"', content)
        self.assertIn('calendar-month-title', content)

    def test_calendar_component_has_weekday_headers(self):
        """Test that calendar component includes weekday headers."""
        self.client.login(username='test_requester', password='testpassword123')

        response = self.client.get(reverse('reservations:create_reservation'))

        content = response.content.decode('utf-8')

        # Check for weekday headers
        weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
        for day in weekdays:
            self.assertIn(day, content)

    def test_calendar_component_tooltip_structure(self):
        """Test that calendar component has tooltip elements."""
        self.client.login(username='test_requester', password='testpassword123')

        response = self.client.get(reverse('reservations:create_reservation'))

        content = response.content.decode('utf-8')

        # Check for tooltip structure
        self.assertIn('calendar-tooltip', content)
        self.assertIn('tooltip-occupancy', content)
        self.assertIn('tooltip-section', content)


class CalendarResponsiveTestCase(TestCase):
    """Test calendar responsiveness."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='test_requester',
            email='test@dssc.edu.ph',
            password='testpassword123',
            role=User.Role.REQUESTER,
        )

        self.facility_type = FacilityType.objects.create(
            name='Test Facility Type',
        )

        self.facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='Test Facility',
            location='Building A',
            capacity=100,
            status=Facility.Status.AVAILABLE,
        )

        self.client = Client()

    def test_calendar_has_mobile_styles(self):
        """Test that calendar has mobile responsiveness styles."""
        self.client.login(username='test_requester', password='testpassword123')

        response = self.client.get(reverse('reservations:create_reservation'))

        content = response.content.decode('utf-8')

        # Check for media queries and responsive classes
        self.assertIn('@media', content)
        self.assertIn('max-width', content)

    def test_calendar_uses_flexible_grid(self):
        """Test that calendar uses flexible grid for responsiveness."""
        self.client.login(username='test_requester', password='testpassword123')

        response = self.client.get(reverse('reservations:create_reservation'))

        content = response.content.decode('utf-8')

        # Check for grid-based layout
        self.assertIn('display: grid', content)
        self.assertIn('grid-template-columns: repeat(7, 1fr)', content)
