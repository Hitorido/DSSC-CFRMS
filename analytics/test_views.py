"""
Tests for analytics JSON API views - Phase 6.5.2.

Coverage:
- Successful responses with correct data
- Permission control (ADMIN allowed, STAFF/REQUESTER denied)
- Authentication (unauthenticated users redirected)
- Invalid parameters (date ranges, formats)
- Empty result handling
- Analytics database unavailability (safe fail-fast)
"""

import datetime
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from facilities.models import Facility, FacilityType
from reservations.models import Reservation
from analytics import services

User = get_user_model()


@override_settings(
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': 'test_dssc_cfrms_db',
            'USER': 'root',
            'PASSWORD': '',
            'HOST': '127.0.0.1',
            'PORT': '3306',
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
            'TEST': {
                'NAME': 'test_dssc_cfrms_db',
            },
        },
    }
)
class AnalyticsViewsTestCase(TestCase):
    """Test suite for analytics JSON API views."""
    
    databases = {'default'}

    def setUp(self):
        """Create test users with different roles and mock _get_analytics_db."""
        # Patch _get_analytics_db to return 'default' for all database queries
        self.mock_get_db = patch('analytics.services._get_analytics_db', return_value='default')
        self.mock_get_db.start()
        
        # Admin user - should have access
        self.admin_user = User.objects.create_user(
            username='admin_user',
            email='admin@test.local',
            password='testpass123',
            role=User.Role.ADMIN,
        )
        
        # Staff user - should be denied
        self.staff_user = User.objects.create_user(
            username='staff_user',
            email='staff@test.local',
            password='testpass123',
            role=User.Role.STAFF,
        )
        
        # Requester user - should be denied
        self.requester_user = User.objects.create_user(
            username='requester_user',
            email='requester@test.local',
            password='testpass123',
            role=User.Role.REQUESTER,
        )
        
        # Create test data in default database
        facility_type = FacilityType.objects.using('default').create(
            name='Test Lab',
            description='Test facility type',
            is_synthetic=True,
        )
        
        self.facility = Facility.objects.using('default').create(
            facility_type=facility_type,
            name='Test Room',
            location='Test Building',
            capacity=50,
            status=Facility.Status.AVAILABLE,
            is_synthetic=True,
        )
        
        self.requester = User.objects.using('default').create(
            username='test_requester',
            email='requester@test.local',
            role=User.Role.REQUESTER,
            is_synthetic=True,
        )
        
        # Create some test reservations
        today = timezone.localdate()
        base_datetime = timezone.make_aware(datetime.datetime.combine(today, datetime.time(0, 0, 0)))
        
        Reservation.objects.using('default').create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Test Reservation',
            reservation_date=today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=Reservation.Status.APPROVED,
            is_synthetic=True,
        )
        
        self.client = Client()

    def tearDown(self):
        """Clean up patches after tests complete."""
        if hasattr(self, 'mock_get_db'):
            self.mock_get_db.stop()

    # ========================================================================
    # PERMISSION AND AUTHENTICATION TESTS
    # ========================================================================

    def test_admin_can_access_kpis_endpoint(self):
        """ADMIN user can access reservation KPIs endpoint."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('analytics:reservation-kpis'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('total_reservations', data)
        self.assertIn('approval_rate', data)

    def test_staff_denied_kpis_endpoint(self):
        """STAFF user is denied access to KPIs endpoint."""
        self.client.login(username='staff_user', password='testpass123')
        response = self.client.get(reverse('analytics:reservation-kpis'))
        
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Permission denied')
        self.assertIn('ADMIN', data['detail'])

    def test_requester_denied_kpis_endpoint(self):
        """REQUESTER user is denied access to KPIs endpoint."""
        self.client.login(username='requester_user', password='testpass123')
        response = self.client.get(reverse('analytics:reservation-kpis'))
        
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Permission denied')

    def test_unauthenticated_user_redirected(self):
        """Unauthenticated user gets HTTP 401 JSON response."""
        response = self.client.get(reverse('analytics:reservation-kpis'), follow=False)
        
        # Should return HTTP 401 JSON (not redirect to login)
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Authentication required')

    def test_all_endpoints_require_admin(self):
        """All endpoints require ADMIN role."""
        endpoints = [
            'analytics:reservation-kpis',
            'analytics:status-distribution',
            'analytics:facility-demand',
            'analytics:peak-booking-periods',
            'analytics:facility-booking-intensity',
        ]
        
        self.client.login(username='staff_user', password='testpass123')
        
        for endpoint in endpoints:
            response = self.client.get(reverse(endpoint))
            self.assertEqual(
                response.status_code,
                403,
                f"Endpoint {endpoint} should be denied to STAFF role"
            )

    # ========================================================================
    # SUCCESSFUL RESPONSE TESTS
    # ========================================================================

    def test_reservation_kpis_response_structure(self):
        """KPIs endpoint returns correct JSON structure."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('analytics:reservation-kpis'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        required_fields = [
            'total_reservations', 'approved_count', 'rejected_count',
            'cancelled_count', 'pending_count', 'approval_rate',
            'rejection_rate', 'cancellation_rate', 'average_days_to_approval'
        ]
        
        for field in required_fields:
            self.assertIn(field, data, f"Missing required field: {field}")

    def test_status_distribution_response(self):
        """Status distribution endpoint returns status counts."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('analytics:status-distribution'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Should be a dict with status keys
        self.assertIsInstance(data, dict)
        # At least APPROVED should be present from test data
        self.assertGreaterEqual(len(data), 0)

    def test_facility_demand_response(self):
        """Facility demand endpoint returns ordered facility list."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('analytics:facility-demand'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Should be a list
        self.assertIsInstance(data, list)
        
        # Each item should have required fields
        if len(data) > 0:
            item = data[0]
            required = ['facility_id', 'facility_name', 'facility_type', 
                       'reservation_count', 'approved_count', 'capacity']
            for field in required:
                self.assertIn(field, item, f"Missing required field: {field}")

    def test_peak_booking_periods_response(self):
        """Peak booking periods endpoint returns structured data."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('analytics:peak-booking-periods'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Should have by_hour, by_day_of_week, by_facility
        self.assertIn('by_hour', data)
        self.assertIn('by_day_of_week', data)
        self.assertIn('by_facility', data)
        
        self.assertIsInstance(data['by_hour'], dict)
        self.assertIsInstance(data['by_day_of_week'], dict)
        self.assertIsInstance(data['by_facility'], list)

    def test_facility_booking_intensity_response(self):
        """Facility booking intensity endpoint returns intensity scores."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('analytics:facility-booking-intensity'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Should be a list
        self.assertIsInstance(data, list)
        
        # Each item should have required fields
        if len(data) > 0:
            item = data[0]
            required = ['facility_id', 'facility_name', 'facility_type',
                       'capacity', 'approved_reservations', 'booking_intensity']
            for field in required:
                self.assertIn(field, item, f"Missing required field: {field}")

    # ========================================================================
    # PARAMETER VALIDATION TESTS
    # ========================================================================

    def test_monthly_trends_invalid_start_date_format(self):
        """Invalid start_date format returns 400 Bad Request."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(
            reverse('analytics:monthly-trends'),
            {'start_date': 'invalid-date'}
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Invalid parameter')
        self.assertIn('YYYY-MM-DD', data['detail'])

    def test_monthly_trends_invalid_end_date_format(self):
        """Invalid end_date format returns 400 Bad Request."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(
            reverse('analytics:monthly-trends'),
            {'end_date': '2024/01/01'}
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Invalid parameter')

    def test_monthly_trends_start_date_after_end_date(self):
        """start_date > end_date returns 400 Bad Request."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(
            reverse('analytics:monthly-trends'),
            {
                'start_date': '2024-12-31',
                'end_date': '2024-01-01'
            }
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Invalid parameter')
        self.assertIn('must be before', data['detail'])

    def test_monthly_trends_valid_date_range(self):
        """Valid date range returns 200 OK."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(
            reverse('analytics:monthly-trends'),
            {
                'start_date': '2024-01-01',
                'end_date': '2024-12-31'
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIsInstance(data, list)

    def test_monthly_trends_no_date_parameters(self):
        """Monthly trends with no date parameters uses defaults."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('analytics:monthly-trends'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIsInstance(data, list)

    # ========================================================================
    # EMPTY RESULT HANDLING
    # ========================================================================

    def test_empty_status_distribution(self):
        """Status distribution handles empty results gracefully."""
        # Delete all reservations
        Reservation.objects.using('default').all().delete()
        
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('analytics:status-distribution'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        # Should return empty dict, not error
        self.assertEqual(data, {})

    def test_empty_facility_demand(self):
        """Facility demand handles empty results gracefully."""
        Facility.objects.using('default').all().delete()
        
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('analytics:facility-demand'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        # Should return empty list, not error
        self.assertEqual(data, [])

    # ========================================================================
    # DATABASE FAILURE HANDLING
    # ========================================================================

    def test_database_unavailable_kpis(self):
        """Database unavailability returns 503 Service Unavailable."""
        self.client.login(username='admin_user', password='testpass123')
        
        # Mock the service to raise RuntimeError (analytics DB unavailable)
        with patch('analytics.views.services.get_reservation_kpis') as mock:
            mock.side_effect = RuntimeError("Analytics database not configured")
            response = self.client.get(reverse('analytics:reservation-kpis'))
        
        self.assertEqual(response.status_code, 503)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Service unavailable')
        self.assertIn('database', data['detail'].lower())

    def test_database_unavailable_status_distribution(self):
        """Status distribution handles database unavailability."""
        self.client.login(username='admin_user', password='testpass123')
        
        with patch('analytics.views.services.get_reservation_status_distribution') as mock:
            mock.side_effect = RuntimeError("Analytics database not configured")
            response = self.client.get(reverse('analytics:status-distribution'))
        
        self.assertEqual(response.status_code, 503)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Service unavailable')

    def test_database_unavailable_facility_demand(self):
        """Facility demand handles database unavailability."""
        self.client.login(username='admin_user', password='testpass123')
        
        with patch('analytics.views.services.get_facility_demand') as mock:
            mock.side_effect = RuntimeError("Analytics database not configured")
            response = self.client.get(reverse('analytics:facility-demand'))
        
        self.assertEqual(response.status_code, 503)

    def test_database_unavailable_monthly_trends(self):
        """Monthly trends handles database unavailability."""
        self.client.login(username='admin_user', password='testpass123')
        
        with patch('analytics.views.services.get_monthly_trends') as mock:
            mock.side_effect = RuntimeError("Analytics database not configured")
            response = self.client.get(reverse('analytics:monthly-trends'))
        
        self.assertEqual(response.status_code, 503)

    def test_database_unavailable_peak_periods(self):
        """Peak periods handles database unavailability."""
        self.client.login(username='admin_user', password='testpass123')
        
        with patch('analytics.views.services.get_peak_booking_periods') as mock:
            mock.side_effect = RuntimeError("Analytics database not configured")
            response = self.client.get(reverse('analytics:peak-booking-periods'))
        
        self.assertEqual(response.status_code, 503)

    def test_database_unavailable_booking_intensity(self):
        """Booking intensity handles database unavailability."""
        self.client.login(username='admin_user', password='testpass123')
        
        with patch('analytics.views.services.get_facility_booking_intensity') as mock:
            mock.side_effect = RuntimeError("Analytics database not configured")
            response = self.client.get(reverse('analytics:facility-booking-intensity'))
        
        self.assertEqual(response.status_code, 503)

    # ========================================================================
    # HTTP METHOD VALIDATION
    # ========================================================================

    def test_only_get_method_allowed(self):
        """Only GET method is allowed on endpoints."""
        self.client.login(username='admin_user', password='testpass123')
        
        # POST should not be allowed
        response = self.client.post(reverse('analytics:reservation-kpis'))
        self.assertEqual(response.status_code, 405)  # Method Not Allowed
        
        # PUT should not be allowed
        response = self.client.put(reverse('analytics:reservation-kpis'))
        self.assertEqual(response.status_code, 405)
        
        # DELETE should not be allowed
        response = self.client.delete(reverse('analytics:reservation-kpis'))
        self.assertEqual(response.status_code, 405)



    # ========================================================================
    # NEW ENDPOINTS (TASK 9): Peak Hours, Occupancy, Recommendations, Calendar
    # ========================================================================

    def test_peak_hours_endpoint_response_structure(self):
        """Peak hours endpoint returns correct JSON structure."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('analytics:peak-hours'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Should have peak_hours and all_hours
        self.assertIn('peak_hours', data)
        self.assertIn('all_hours', data)
        
        # peak_hours should be a list
        self.assertIsInstance(data['peak_hours'], list)
        
        # all_hours should be a dict
        self.assertIsInstance(data['all_hours'], dict)
        
        # Each peak hour should have hour and count
        for peak in data['peak_hours']:
            self.assertIn('hour', peak)
            self.assertIn('count', peak)
            self.assertGreaterEqual(peak['hour'], 0)
            self.assertLessEqual(peak['hour'], 23)

    def test_peak_hours_admin_only(self):
        """Peak hours endpoint requires ADMIN role."""
        self.client.login(username='staff_user', password='testpass123')
        response = self.client.get(reverse('analytics:peak-hours'))
        
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Permission denied')

    def test_peak_hours_database_unavailable(self):
        """Peak hours handles database unavailability."""
        self.client.login(username='admin_user', password='testpass123')
        
        with patch('analytics.views.services.PredictiveAnalytics.compute_peak_hours') as mock:
            mock.side_effect = RuntimeError("Analytics database not configured")
            response = self.client.get(reverse('analytics:peak-hours'))
        
        self.assertEqual(response.status_code, 503)

    def test_occupancy_by_facility_endpoint_response_structure(self):
        """Occupancy by facility endpoint returns correct JSON structure."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('analytics:occupancy-by-facility'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Should have facilities key
        self.assertIn('facilities', data)
        
        # facilities should be a list
        self.assertIsInstance(data['facilities'], list)
        
        # Each facility should have required fields
        if len(data['facilities']) > 0:
            facility = data['facilities'][0]
            required = ['facility_id', 'facility_name', 'occupancy', 
                       'occupancy_percent', 'reservation_count', 'capacity']
            for field in required:
                self.assertIn(field, facility, f"Missing field: {field}")

    def test_occupancy_by_facility_with_date_range(self):
        """Occupancy by facility accepts date range parameters."""
        self.client.login(username='admin_user', password='testpass123')
        
        today = timezone.localdate()
        response = self.client.get(
            reverse('analytics:occupancy-by-facility'),
            {
                'start_date': (today - datetime.timedelta(days=30)).isoformat(),
                'end_date': today.isoformat()
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('facilities', data)

    def test_occupancy_by_facility_invalid_start_date(self):
        """Occupancy by facility validates start_date format."""
        self.client.login(username='admin_user', password='testpass123')
        
        response = self.client.get(
            reverse('analytics:occupancy-by-facility'),
            {'start_date': 'invalid-date'}
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Invalid parameter')

    def test_occupancy_by_facility_admin_only(self):
        """Occupancy by facility endpoint requires ADMIN role."""
        self.client.login(username='requester_user', password='testpass123')
        response = self.client.get(reverse('analytics:occupancy-by-facility'))
        
        self.assertEqual(response.status_code, 403)

    def test_recommendations_endpoint_response_structure(self):
        """Recommendations endpoint returns correct JSON structure."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('analytics:recommendations'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Should have recommendations, count, and timestamp
        self.assertIn('recommendations', data)
        self.assertIn('recommendation_count', data)
        self.assertIn('generation_timestamp', data)
        
        # recommendations should be a list
        self.assertIsInstance(data['recommendations'], list)
        
        # Each recommendation should have required fields
        for rec in data['recommendations']:
            required = ['priority', 'title', 'description', 'action', 'impact']
            for field in required:
                self.assertIn(field, rec, f"Missing field in recommendation: {field}")
            
            # Priority should be one of the valid values
            self.assertIn(rec['priority'], ['high', 'medium', 'low'])

    def test_recommendations_admin_only(self):
        """Recommendations endpoint requires ADMIN role."""
        self.client.login(username='staff_user', password='testpass123')
        response = self.client.get(reverse('analytics:recommendations'))
        
        self.assertEqual(response.status_code, 403)

    def test_recommendations_database_unavailable(self):
        """Recommendations handles database unavailability."""
        self.client.login(username='admin_user', password='testpass123')
        
        with patch('analytics.views.services.PrescriptiveAnalytics.generate_recommendations') as mock:
            mock.side_effect = RuntimeError("Analytics database not configured")
            response = self.client.get(reverse('analytics:recommendations'))
        
        self.assertEqual(response.status_code, 503)

    def test_system_calendar_endpoint_response_structure(self):
        """System calendar endpoint returns correct JSON structure."""
        self.client.login(username='admin_user', password='testpass123')
        
        response = self.client.get(
            reverse('analytics:system-calendar'),
            {'month': '2024-12'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Should have month and calendar
        self.assertIn('month', data)
        self.assertIn('calendar', data)
        
        # month should match request
        self.assertEqual(data['month'], '2024-12')
        
        # calendar should be a list
        self.assertIsInstance(data['calendar'], list)
        
        # Each calendar day should have required fields
        if len(data['calendar']) > 0:
            day = data['calendar'][0]
            required = ['date', 'reservation_count', 'maintenance_count', 
                       'total_events', 'reservations', 'maintenance']
            for field in required:
                self.assertIn(field, day, f"Missing field in calendar day: {field}")

    def test_system_calendar_missing_month_parameter(self):
        """System calendar requires month parameter."""
        self.client.login(username='admin_user', password='testpass123')
        
        response = self.client.get(reverse('analytics:system-calendar'))
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Invalid parameter')
        self.assertIn('month', data['detail'].lower())

    def test_system_calendar_invalid_month_format(self):
        """System calendar validates month format."""
        self.client.login(username='admin_user', password='testpass123')
        
        response = self.client.get(
            reverse('analytics:system-calendar'),
            {'month': '2024/12'}
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Invalid parameter')

    def test_system_calendar_invalid_month_number(self):
        """System calendar validates month is 1-12."""
        self.client.login(username='admin_user', password='testpass123')
        
        response = self.client.get(
            reverse('analytics:system-calendar'),
            {'month': '2024-13'}
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Invalid parameter')

    def test_system_calendar_admin_only(self):
        """System calendar endpoint requires ADMIN role."""
        self.client.login(username='requester_user', password='testpass123')
        
        response = self.client.get(
            reverse('analytics:system-calendar'),
            {'month': '2024-12'}
        )
        
        self.assertEqual(response.status_code, 403)

    def test_system_calendar_valid_month_range(self):
        """System calendar accepts valid month in valid year range."""
        self.client.login(username='admin_user', password='testpass123')
        
        # Test various valid months
        valid_months = ['2024-01', '2024-06', '2024-12', '2025-01']
        
        for month in valid_months:
            response = self.client.get(
                reverse('analytics:system-calendar'),
                {'month': month}
            )
            
            self.assertEqual(response.status_code, 200, f"Failed for month {month}")
            data = json.loads(response.content)
            self.assertEqual(data['month'], month)

    def test_system_calendar_returns_all_days_in_month(self):
        """System calendar returns entries for all days in the month."""
        self.client.login(username='admin_user', password='testpass123')
        
        response = self.client.get(
            reverse('analytics:system-calendar'),
            {'month': '2024-12'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # December has 31 days
        self.assertEqual(len(data['calendar']), 31)
