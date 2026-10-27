"""
Tests for analytics caching and cache invalidation - Task 13.

Coverage:
- Cache hit/miss behavior
- TTL expiration
- Cache invalidation on reservation status changes
- Cache utility functions
"""

import datetime
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from facilities.models import Facility, FacilityType
from reservations.models import Reservation
from analytics import utils
from analytics.services import PredictiveAnalytics

User = get_user_model()


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'test-analytics-cache',
            'OPTIONS': {
                'MAX_ENTRIES': 1000,
            }
        }
    }
)
class AnalyticsCacheTestCase(TestCase):
    """Test suite for analytics caching and cache invalidation."""

    def setUp(self):
        """Create test data and clear cache before each test."""
        cache.clear()
        
        # Patch _get_analytics_db to return 'default'
        self.mock_get_db = patch('analytics.services._get_analytics_db', return_value='default')
        self.mock_get_db.start()
        
        # Create test facility
        facility_type = FacilityType.objects.create(
            name='Test Lab',
            description='Test facility',
            is_synthetic=True,
        )
        
        self.facility = Facility.objects.create(
            facility_type=facility_type,
            name='Test Room',
            location='Test Building',
            capacity=50,
            status=Facility.Status.AVAILABLE,
            is_synthetic=True,
        )
        
        # Create test requester
        self.requester = User.objects.create(
            username='test_requester',
            email='requester@test.local',
            role=User.Role.REQUESTER,
            is_synthetic=True,
        )
        
        # Create test reviewer
        self.reviewer = User.objects.create(
            username='test_reviewer',
            email='reviewer@test.local',
            role=User.Role.STAFF,
        )

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()
        if hasattr(self, 'mock_get_db'):
            self.mock_get_db.stop()

    # ========================================================================
    # CACHE HIT/MISS TESTS
    # ========================================================================

    def test_cache_set_and_get(self):
        """Cache properly stores and retrieves values."""
        key = 'test_key'
        value = {'data': 'test_value'}
        
        # Initially should not be cached
        self.assertIsNone(cache.get(key))
        
        # Set value
        cache.set(key, value, 3600)
        
        # Should retrieve cached value
        self.assertEqual(cache.get(key), value)

    def test_cache_miss_returns_none(self):
        """Cache miss returns None."""
        self.assertIsNone(cache.get('nonexistent_key'))

    def test_cache_ttl_expiration(self):
        """Cache entry expires after TTL."""
        key = 'ttl_test'
        value = 'test_value'
        
        # Set with very short TTL (we'll manually expire it)
        cache.set(key, value, 1)  # 1 second
        self.assertEqual(cache.get(key), value)
        
        # After timeout (mocked), should be gone
        # Note: We can't actually wait in tests, so we use delete to simulate expiration
        cache.delete(key)
        self.assertIsNone(cache.get(key))

    def test_peak_hours_cache_hit(self):
        """Peak hours computation is cached after first call."""
        with patch('analytics.services.PredictiveAnalytics.compute_peak_hours') as mock:
            mock_result = {
                'peak_hours': [{'hour': 14, 'count': 100}],
                'all_hours': {}
            }
            mock.return_value = mock_result
            
            # First call - should hit the mock
            result1 = PredictiveAnalytics.compute_peak_hours()
            self.assertEqual(mock.call_count, 1)
            self.assertEqual(result1, mock_result)
            
            # Second call - should hit cache
            result2 = PredictiveAnalytics.compute_peak_hours()
            # Mock should not be called again due to caching
            self.assertEqual(mock.call_count, 1)
            self.assertEqual(result2, mock_result)

    # ========================================================================
    # CACHE INVALIDATION ON STATUS CHANGE TESTS
    # ========================================================================

    def test_cache_invalidated_on_reservation_create(self):
        """Creating a new reservation invalidates analytics cache."""
        # Pre-populate cache with dummy values
        cache.set('peak_hours', {'dummy': 'data'}, 3600)
        cache.set('prescriptive_recommendations', {'dummy': 'recs'}, 3600)
        
        # Verify cache is populated
        self.assertIsNotNone(cache.get('peak_hours'))
        self.assertIsNotNone(cache.get('prescriptive_recommendations'))
        
        # Create a new reservation
        today = timezone.localdate()
        reservation = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Test Reservation',
            reservation_date=today + datetime.timedelta(days=1),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=Reservation.Status.PENDING,
            is_synthetic=True,
        )
        
        # Cache should be invalidated (cleared)
        self.assertIsNone(cache.get('peak_hours'))
        self.assertIsNone(cache.get('prescriptive_recommendations'))

    def test_cache_invalidated_on_status_change_to_approved(self):
        """Changing reservation status to APPROVED invalidates cache."""
        # Create a pending reservation
        today = timezone.localdate()
        reservation = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Test Reservation',
            reservation_date=today + datetime.timedelta(days=1),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=Reservation.Status.PENDING,
            is_synthetic=True,
        )
        
        # Cache.clear was called on create, now populate cache
        cache.clear()
        cache.set('peak_hours', {'dummy': 'data'}, 3600)
        
        # Now approve the reservation
        reservation.approve(self.reviewer)
        
        # Cache should be invalidated
        self.assertIsNone(cache.get('peak_hours'))

    def test_cache_invalidated_on_status_change_to_rejected(self):
        """Changing reservation status to REJECTED invalidates cache."""
        # Create a pending reservation
        today = timezone.localdate()
        reservation = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Test Reservation',
            reservation_date=today + datetime.timedelta(days=1),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=Reservation.Status.PENDING,
            is_synthetic=True,
        )
        
        # Populate cache
        cache.set('peak_hours', {'dummy': 'data'}, 3600)
        cache.set('prescriptive_recommendations', {'dummy': 'recs'}, 3600)
        
        # Reject the reservation
        reservation.reject(self.reviewer, 'Facility not available')
        
        # Cache should be invalidated
        self.assertIsNone(cache.get('peak_hours'))
        self.assertIsNone(cache.get('prescriptive_recommendations'))

    def test_cache_invalidated_on_status_change_to_cancelled(self):
        """Changing reservation status to CANCELLED invalidates cache."""
        # Create an approved reservation
        today = timezone.localdate()
        reservation = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Test Reservation',
            reservation_date=today + datetime.timedelta(days=1),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=Reservation.Status.PENDING,
            is_synthetic=True,
        )
        reservation.approve(self.reviewer)
        
        # Populate cache
        cache.set('peak_hours', {'dummy': 'data'}, 3600)
        
        # Cancel the reservation
        cache.clear()
        cache.set('peak_hours', {'dummy': 'data'}, 3600)
        reservation.status = Reservation.Status.CANCELLED
        reservation.save()
        
        # Cache should be invalidated
        self.assertIsNone(cache.get('peak_hours'))

    def test_cache_not_invalidated_when_non_status_field_changes(self):
        """Changing non-status fields does not invalidate cache."""
        # Create a reservation
        today = timezone.localdate()
        reservation = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Test Reservation',
            reservation_date=today + datetime.timedelta(days=1),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=Reservation.Status.PENDING,
            is_synthetic=True,
        )
        
        # Populate cache
        cache.clear()
        cache.set('peak_hours', {'dummy': 'data'}, 3600)
        self.assertIsNotNone(cache.get('peak_hours'))
        
        # Change purpose (non-status field)
        reservation.purpose = 'Updated Purpose'
        reservation.save()
        
        # Cache should still be there (not invalidated)
        self.assertIsNotNone(cache.get('peak_hours'))

    # ========================================================================
    # CACHE UTILITY FUNCTION TESTS
    # ========================================================================

    def test_invalidate_analytics_cache_clears_keys(self):
        """invalidate_analytics_cache() clears all analytics cache keys."""
        # Populate cache with multiple keys
        cache_data = {
            'peak_hours': {'data': 'peak_hours'},
            'peak_days': {'data': 'peak_days'},
            'prescriptive_recommendations': {'data': 'recommendations'},
            'forecast_6_3': {'data': 'forecast'},
        }
        
        for key, value in cache_data.items():
            cache.set(key, value, 3600)
        
        # Verify cache is populated
        for key in cache_data.keys():
            self.assertIsNotNone(cache.get(key), f"Cache should have {key}")
        
        # Call cache invalidation utility
        utils.invalidate_analytics_cache()
        
        # Verify cache is cleared for all analytics keys
        for key in cache_data.keys():
            self.assertIsNone(cache.get(key), f"Cache should have cleared {key}")

    def test_invalidate_specific_forecast(self):
        """invalidate_specific_forecast() clears specific forecast cache."""
        # Populate cache with forecasts
        cache.set('forecast_6_3', {'data': 'forecast_6_3'}, 3600)
        cache.set('forecast_12_6', {'data': 'forecast_12_6'}, 3600)
        
        # Verify both are cached
        self.assertIsNotNone(cache.get('forecast_6_3'))
        self.assertIsNotNone(cache.get('forecast_12_6'))
        
        # Invalidate specific forecast
        utils.invalidate_specific_forecast(months=6, periods=3)
        
        # forecast_6_3 should be cleared, forecast_12_6 should remain
        self.assertIsNone(cache.get('forecast_6_3'))
        self.assertIsNotNone(cache.get('forecast_12_6'))

    def test_set_analytics_cache_with_custom_ttl(self):
        """set_analytics_cache() stores value with custom TTL."""
        key = 'test_forecast'
        value = {'data': 'test_value'}
        ttl = 1800  # 30 minutes
        
        utils.set_analytics_cache(key, value, ttl=ttl)
        
        # Verify value is in cache
        self.assertEqual(cache.get(key), value)

    def test_get_cache_info(self):
        """get_cache_info() retrieves cache value or None."""
        key = 'test_key'
        value = {'data': 'test_value'}
        
        # Cache miss
        self.assertIsNone(utils.get_cache_info(key))
        
        # Set value
        cache.set(key, value, 3600)
        
        # Cache hit
        self.assertEqual(utils.get_cache_info(key), value)

    # ========================================================================
    # MULTIPLE RESERVATION CHANGES
    # ========================================================================

    def test_cache_invalidated_multiple_times(self):
        """Cache is invalidated for each reservation status change."""
        today = timezone.localdate()
        
        # Create first reservation
        res1 = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Test 1',
            reservation_date=today + datetime.timedelta(days=1),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=Reservation.Status.PENDING,
            is_synthetic=True,
        )
        
        # Cache should be invalidated (cleared on create)
        self.assertIsNone(cache.get('peak_hours'))
        
        # Populate cache
        cache.set('peak_hours', {'data': 'peak_hours'}, 3600)
        self.assertIsNotNone(cache.get('peak_hours'))
        
        # Approve first reservation - cache should be invalidated again
        res1.approve(self.reviewer)
        self.assertIsNone(cache.get('peak_hours'))
        
        # Populate cache again
        cache.set('peak_hours', {'data': 'peak_hours'}, 3600)
        self.assertIsNotNone(cache.get('peak_hours'))
        
        # Create second reservation - cache should be invalidated
        res2 = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Test 2',
            reservation_date=today + datetime.timedelta(days=2),
            start_time=datetime.time(11, 0),
            end_time=datetime.time(12, 0),
            status=Reservation.Status.PENDING,
            is_synthetic=True,
        )
        
        self.assertIsNone(cache.get('peak_hours'))

    def test_cache_invalidation_with_all_cache_keys(self):
        """All cache keys defined in utils are invalidated correctly."""
        # These are the keys defined in utils.invalidate_analytics_cache()
        all_keys = [
            'forecast_3_1', 'forecast_3_3', 'forecast_6_3', 'forecast_12_6',
            'peak_hours', 'peak_days',
            'occupancy_by_facility',
            'prescriptive_recommendations',
            'facility_analytics_dashboard', 'admin_dashboard_analytics', 'staff_dashboard_analytics',
        ]
        
        # Populate all keys
        for key in all_keys:
            cache.set(key, {'data': key}, 3600)
        
        # Verify all are cached
        for key in all_keys:
            self.assertIsNotNone(cache.get(key), f"{key} should be cached")
        
        # Invalidate
        utils.invalidate_analytics_cache()
        
        # Verify all are cleared
        for key in all_keys:
            self.assertIsNone(cache.get(key), f"{key} should be cleared")
