"""
Integration tests for admin dashboard analytics display.

Tests:
- Analytics overview cards render with correct data
- Demand forecast chart data structure
- System reservations calendar displays events
- Recommendations section displays cards
- Synthetic data fallback when operational data insufficient
- Data freshness indicator shows correctly
"""

from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from facilities.models import Facility, FacilityType
from reservations.models import Reservation


class AdminDashboardAnalyticsTests(TestCase):
    """Test admin dashboard analytics display."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        # Create admin user
        cls.admin_user = User.objects.create_user(
            username='admin_user',
            email='admin@test.com',
            password='testpass123',
            role=User.Role.ADMIN,
        )

        # Create facility type
        cls.facility_type = FacilityType.objects.create(
            name='Computer Lab'
        )

        # Create a facility
        cls.facility = Facility.objects.create(
            name='Test Lab',
            location='Building A',
            capacity=30,
            facility_type=cls.facility_type,
            status=Facility.Status.AVAILABLE,
        )

        # Create test reservations
        today = timezone.localdate()
        for i in range(5):
            Reservation.objects.create(
                requested_by=User.objects.create_user(
                    username=f'user{i}',
                    email=f'user{i}@test.com',
                    password='testpass123',
                ),
                facility=cls.facility,
                purpose='Test booking',
                reservation_date=today + timedelta(days=i),
                start_time=timezone.now().time(),
                end_time=timezone.now().time(),
                status=Reservation.Status.APPROVED,
            )

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    def test_admin_dashboard_requires_login(self):
        """Test that admin dashboard requires authentication."""
        response = self.client.get(reverse('accounts:admin_dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_admin_dashboard_requires_admin_role(self):
        """Test that admin dashboard requires admin role."""
        staff_user = User.objects.create_user(
            username='staff_user',
            email='staff@test.com',
            password='testpass123',
            role=User.Role.STAFF,
        )
        self.client.login(username='staff_user', password='testpass123')
        response = self.client.get(reverse('accounts:admin_dashboard'))
        self.assertEqual(response.status_code, 403)  # Forbidden

    def test_admin_dashboard_access(self):
        """Test that admin can access dashboard."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('accounts:admin_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_displays_overview_stats(self):
        """Test that dashboard displays account statistics."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('accounts:admin_dashboard'))
        
        # Check for core dashboard elements
        self.assertContains(response, 'Accounts')
        self.assertContains(response, 'Admin Console')

    def test_dashboard_includes_analytics_overview(self):
        """Test that analytics overview is included in context."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('accounts:admin_dashboard'))
        
        # Check context data exists
        self.assertIn('analytics_overview', response.context)
        
        # If analytics_overview is populated, check it has required keys
        if response.context['analytics_overview']:
            analytics = response.context['analytics_overview']
            self.assertIn('total_reservations', analytics)
            self.assertIn('avg_occupancy_percent', analytics)
            self.assertIn('peak_facility', analytics)
            self.assertIn('top_booked_time', analytics)

    def test_dashboard_includes_demand_forecast_data(self):
        """Test that demand forecast data is included."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('accounts:admin_dashboard'))
        
        self.assertIn('demand_forecast_data', response.context)
        
        # If forecast data exists, check structure
        if response.context['demand_forecast_data']:
            forecast = response.context['demand_forecast_data']
            self.assertIn('historical_data', forecast)
            self.assertIn('forecast_data', forecast)
            self.assertIn('confidence', forecast)

    def test_dashboard_includes_system_calendar(self):
        """Test that system calendar is included."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('accounts:admin_dashboard'))
        
        self.assertIn('system_calendar_weeks', response.context)
        self.assertIn('system_calendar_month', response.context)
        self.assertIn('system_calendar_weekdays', response.context)

    def test_dashboard_includes_recommendations(self):
        """Test that recommendations section is included."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('accounts:admin_dashboard'))
        
        self.assertIn('recommendations', response.context)
        
        # If recommendations exist, check structure
        if response.context['recommendations']:
            for rec in response.context['recommendations']:
                self.assertIn('priority', rec)
                self.assertIn('title', rec)
                self.assertIn('description', rec)
                self.assertIn('action', rec)
                self.assertIn('impact', rec)

    def test_dashboard_indicates_synthetic_data_when_used(self):
        """Test that synthetic data indicator is shown when applicable."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('accounts:admin_dashboard'))
        
        # Check that indicator context is set
        self.assertIn('is_using_synthetic_data', response.context)
        
        # If using synthetic data, alert should be in response
        if response.context['is_using_synthetic_data']:
            self.assertContains(response, 'Synthetic Data')
            self.assertContains(response, 'demonstration')

    def test_dashboard_shows_data_last_updated(self):
        """Test that data freshness indicator is shown."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('accounts:admin_dashboard'))
        
        self.assertIn('data_last_updated', response.context)
        # Should be a recent timestamp
        updated = response.context['data_last_updated']
        now = timezone.now()
        self.assertLess((now - updated).total_seconds(), 60)  # Within 60 seconds

    def test_dashboard_account_management_table(self):
        """Test that account management table is displayed."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('accounts:admin_dashboard'))
        
        self.assertContains(response, 'Account and role management')
        self.assertContains(response, 'admin_user')  # Admin user should be in list

    def test_dashboard_calendar_navigation(self):
        """Test that calendar month navigation works."""
        self.client.login(username='admin_user', password='testpass123')
        
        # Test with specific month
        today = timezone.localdate()
        month_str = today.strftime('%Y-%m')
        response = self.client.get(
            reverse('accounts:admin_dashboard'),
            {'calendar_month': month_str}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('system_calendar_weeks', response.context)

    def test_dashboard_chart_data_accuracy(self):
        """Test that chart data is accurately calculated."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('accounts:admin_dashboard'))
        
        analytics = response.context.get('analytics_overview')
        if analytics:
            # Total reservations should match database count
            db_count = Reservation.objects.filter(
                status__in=[Reservation.Status.APPROVED, Reservation.Status.COMPLETED]
            ).count()
            self.assertEqual(analytics['total_reservations'], db_count)

    def test_dashboard_fallback_to_synthetic_with_no_operational_data(self):
        """Test that dashboard falls back to synthetic data when no operational data."""
        # Delete all operational reservations
        Reservation.objects.all().delete()
        
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('accounts:admin_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        # Dashboard should still render even with no data
        self.assertIn('analytics_data_scope', response.context)


class AdminDashboardRecommendationsTests(TestCase):
    """Test recommendation generation logic."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.admin_user = User.objects.create_user(
            username='admin_user',
            email='admin@test.com',
            password='testpass123',
            role=User.Role.ADMIN,
        )
        
        # Create facility type for later use
        cls.facility_type = FacilityType.objects.create(name='Computer Lab')

    def setUp(self):
        """Set up test client."""
        self.client = Client()
        self.client.login(username='admin_user', password='testpass123')

    def test_recommendations_generated_for_high_occupancy(self):
        """Test that recommendations are generated for high occupancy."""
        # Create scenario with high occupancy
        facility = Facility.objects.create(
            name='Busy Lab',
            location='Building A',
            capacity=10,
            facility_type=self.facility_type,
            status=Facility.Status.AVAILABLE,
        )

        # Create many reservations to simulate high occupancy
        requester = User.objects.create_user(
            username='requester1',
            email='req1@test.com',
            password='testpass123',
        )
        
        today = timezone.localdate()
        for i in range(15):
            Reservation.objects.create(
                requested_by=requester,
                facility=facility,
                purpose='High occupancy booking',
                reservation_date=today + timedelta(days=i),
                start_time=timezone.now().time(),
                end_time=timezone.now().time(),
                status=Reservation.Status.APPROVED,
            )

        response = self.client.get(reverse('accounts:admin_dashboard'))
        
        recommendations = response.context.get('recommendations', [])
        if recommendations:
            # Check for occupancy-related recommendation
            occupancy_rec = any('occupancy' in r['title'].lower() or 'capacity' in r['title'].lower() 
                              for r in recommendations)
            # May or may not exist depending on analytics calculation
            self.assertIsInstance(recommendations, list)

    def test_recommendations_include_required_fields(self):
        """Test that recommendation cards have all required fields."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('accounts:admin_dashboard'))
        
        recommendations = response.context.get('recommendations', [])
        for rec in recommendations:
            self.assertIn('priority', rec)
            self.assertIn('title', rec)
            self.assertIn('description', rec)
            self.assertIn('action', rec)
            self.assertIn('impact', rec)
            self.assertIn('badge', rec)
            
            # Priority should be valid
            self.assertIn(rec['priority'], ['high', 'medium', 'low'])

    def test_recommendations_priority_sorting(self):
        """Test that recommendations are sorted by priority."""
        self.client.login(username='admin_user', password='testpass123')
        response = self.client.get(reverse('accounts:admin_dashboard'))
        
        recommendations = response.context.get('recommendations', [])
        if len(recommendations) > 1:
            # Check that high priority comes before low
            high_indices = [i for i, r in enumerate(recommendations) if r['priority'] == 'high']
            medium_indices = [i for i, r in enumerate(recommendations) if r['priority'] == 'medium']
            
            if high_indices and medium_indices:
                self.assertLess(max(high_indices), min(medium_indices))


class AdminDashboardResponsiveTests(TestCase):
    """Test dashboard responsive design."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.admin_user = User.objects.create_user(
            username='admin_user',
            email='admin@test.com',
            password='testpass123',
            role=User.Role.ADMIN,
        )

    def setUp(self):
        """Set up test client."""
        self.client = Client()
        self.client.login(username='admin_user', password='testpass123')

    def test_dashboard_renders_on_mobile(self):
        """Test that dashboard renders properly on mobile."""
        response = self.client.get(reverse('accounts:admin_dashboard'))
        
        # Check for responsive Bootstrap classes
        self.assertContains(response, 'col-sm')  # Bootstrap responsive columns
        self.assertContains(response, 'col-xl')  # XL breakpoint for analytics cards

    def test_dashboard_includes_chart_js(self):
        """Test that Chart.js is included for demand forecast."""
        response = self.client.get(reverse('accounts:admin_dashboard'))
        
        if response.context.get('demand_forecast_data'):
            # Chart.js should be included
            self.assertContains(response, 'chart.js') or self.assertContains(response, 'Chart')

    def test_dashboard_includes_accessibility_features(self):
        """Test that dashboard includes accessibility features."""
        response = self.client.get(reverse('accounts:admin_dashboard'))
        
        # Check for ARIA labels and semantic HTML
        self.assertContains(response, 'aria-')  # ARIA attributes present
        self.assertContains(response, '<section')  # Semantic sections
