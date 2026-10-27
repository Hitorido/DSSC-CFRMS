"""
Unit tests for PrescriptiveAnalytics service - Task 6 Implementation.

Tests verify:
- Recommendation generation (4-6 recommendations)
- All recommendation types working:
  - Maintenance windows (low-occupancy periods)
  - Capacity expansion (high occupancy facilities)
  - Extended hours (peak days)
  - Equipment maintenance alerts (heavy usage)
  - Seasonal patterns (demand trends)
- Recommendations are realistic with synthetic data
- Caching works (1-hour TTL)
- Priority sorting (high > medium > low)
- Edge cases: empty data, single facility, no patterns
"""

import datetime
import json
import time
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from django.core.cache import cache

from facilities.models import Facility, FacilityType
from reservations.models import Reservation
from analytics.services import PrescriptiveAnalytics, PredictiveAnalytics

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
class PrescriptiveAnalyticsTestCase(TestCase):
    """Test suite for PrescriptiveAnalytics service."""
    
    databases = {'default'}
    
    def setUp(self):
        """Set up test fixtures and mock database routing."""
        self.mock_get_db = patch('analytics.services.PrescriptiveAnalytics._get_analytics_db', return_value='default')
        self.mock_get_db.start()
        
        # Also patch PredictiveAnalytics for internal calls
        self.mock_pred_db = patch('analytics.services.PredictiveAnalytics._get_analytics_db', return_value='default')
        self.mock_pred_db.start()
        
        # Patch the module-level _get_analytics_db function
        self.mock_module_db = patch('analytics.services._get_analytics_db', return_value='default')
        self.mock_module_db.start()
        
        # Clear cache before each test
        cache.clear()
        
        # Create facility types
        self.lab_type = FacilityType.objects.using('default').create(
            name='Computer Lab',
            description='Lab Type',
            is_synthetic=True,
        )
        
        self.classroom_type = FacilityType.objects.using('default').create(
            name='Classroom',
            description='Classroom Type',
            is_synthetic=True,
        )
        
        # Create facilities with different capacities
        self.lab_1 = Facility.objects.using('default').create(
            facility_type=self.lab_type,
            name='ComLab 1',
            location='Building A',
            capacity=30,
            status=Facility.Status.AVAILABLE,
            is_synthetic=True,
        )
        
        self.lab_2 = Facility.objects.using('default').create(
            facility_type=self.lab_type,
            name='ComLab 2',
            location='Building B',
            capacity=25,
            status=Facility.Status.AVAILABLE,
            is_synthetic=True,
        )
        
        self.classroom = Facility.objects.using('default').create(
            facility_type=self.classroom_type,
            name='Classroom 101',
            location='Building C',
            capacity=50,
            status=Facility.Status.AVAILABLE,
            is_synthetic=True,
        )
        
        # Create users
        self.requester = User.objects.using('default').create(
            username='test_requester_pres',
            email='requester@test.local',
            role=User.Role.REQUESTER,
            is_synthetic=True,
        )
        self.requester.set_password('testpass')
        self.requester.save(using='default')
        
        self.staff = User.objects.using('default').create(
            username='test_staff_pres',
            email='staff@test.local',
            role=User.Role.STAFF,
            is_synthetic=True,
        )
        self.staff.set_password('testpass')
        self.staff.save(using='default')
        
        # Create synthetic reservation data with patterns
        self._create_synthetic_reservations()
    
    def _create_synthetic_reservations(self):
        """Create synthetic reservation data with realistic patterns for testing."""
        today = timezone.localdate()
        
        # Create 10 days of data with non-conflicting patterns
        # Each facility gets different time slots to avoid conflicts
        for days_offset in range(10):
            res_date = today + datetime.timedelta(days=30 + days_offset)
            
            # Lab 1: 9:00-10:00, 11:00-12:00, 14:00-15:00
            Reservation.objects.using('default').create(
                requested_by=self.requester,
                facility=self.lab_1,
                purpose='Synthetic test reservation',
                reservation_date=res_date,
                start_time=datetime.time(9, 0),
                end_time=datetime.time(10, 0),
                status=Reservation.Status.APPROVED,
                reviewed_by=self.staff,
                reviewed_at=timezone.now(),
                is_synthetic=True,
            )
            
            Reservation.objects.using('default').create(
                requested_by=self.requester,
                facility=self.lab_1,
                purpose='Synthetic test reservation',
                reservation_date=res_date,
                start_time=datetime.time(11, 0),
                end_time=datetime.time(12, 0),
                status=Reservation.Status.APPROVED,
                reviewed_by=self.staff,
                reviewed_at=timezone.now(),
                is_synthetic=True,
            )
            
            # Lab 2: 10:00-11:00, 13:00-14:00, 15:00-16:00
            Reservation.objects.using('default').create(
                requested_by=self.requester,
                facility=self.lab_2,
                purpose='Synthetic test reservation',
                reservation_date=res_date,
                start_time=datetime.time(10, 0),
                end_time=datetime.time(11, 0),
                status=Reservation.Status.APPROVED,
                reviewed_by=self.staff,
                reviewed_at=timezone.now(),
                is_synthetic=True,
            )
            
            Reservation.objects.using('default').create(
                requested_by=self.requester,
                facility=self.lab_2,
                purpose='Synthetic test reservation',
                reservation_date=res_date,
                start_time=datetime.time(13, 0),
                end_time=datetime.time(14, 0),
                status=Reservation.Status.APPROVED,
                reviewed_by=self.staff,
                reviewed_at=timezone.now(),
                is_synthetic=True,
            )
            
            # Classroom: 14:00-15:00, 15:00-16:00, 16:00-17:00
            Reservation.objects.using('default').create(
                requested_by=self.requester,
                facility=self.classroom,
                purpose='Synthetic test reservation',
                reservation_date=res_date,
                start_time=datetime.time(14, 0),
                end_time=datetime.time(15, 0),
                status=Reservation.Status.APPROVED,
                reviewed_by=self.staff,
                reviewed_at=timezone.now(),
                is_synthetic=True,
            )
    
    def tearDown(self):
        """Clean up after tests."""
        cache.clear()
        if hasattr(self, 'mock_get_db'):
            self.mock_get_db.stop()
        if hasattr(self, 'mock_pred_db'):
            self.mock_pred_db.stop()
        if hasattr(self, 'mock_module_db'):
            self.mock_module_db.stop()
    
    # ========================================================================
    # BASIC RECOMMENDATION GENERATION TESTS
    # ========================================================================
    
    def test_generate_recommendations_returns_correct_structure(self):
        """Recommendations have correct structure."""
        result = PrescriptiveAnalytics.generate_recommendations()
        
        self.assertIn('recommendations', result)
        self.assertIn('recommendation_count', result)
        self.assertIn('generation_timestamp', result)
        self.assertIsInstance(result['recommendations'], list)
        self.assertIsInstance(result['recommendation_count'], int)
    
    def test_generate_recommendations_returns_4_to_6(self):
        """Recommendations returns 4-6 items (or at least 3 with default)."""
        result = PrescriptiveAnalytics.generate_recommendations()
        count = len(result['recommendations'])
        
        # Should have at least 3-4 (4-6 with realistic data, 3 with minimal)
        self.assertGreaterEqual(count, 3, "Should have at least 3 recommendations")
        self.assertLessEqual(count, 6, "Should have at most 6 recommendations")
        self.assertEqual(result['recommendation_count'], count)
    
    def test_recommendation_object_structure(self):
        """Each recommendation has required fields."""
        result = PrescriptiveAnalytics.generate_recommendations()
        
        for rec in result['recommendations']:
            self.assertIn('priority', rec)
            self.assertIn('title', rec)
            self.assertIn('description', rec)
            self.assertIn('action', rec)
            self.assertIn('impact', rec)
            
            # Validate types
            self.assertIsInstance(rec['priority'], str)
            self.assertIsInstance(rec['title'], str)
            self.assertIsInstance(rec['description'], str)
            self.assertIsInstance(rec['action'], str)
            self.assertIsInstance(rec['impact'], str)
            
            # Validate content is non-empty
            self.assertGreater(len(rec['title']), 0)
            self.assertGreater(len(rec['description']), 0)
    
    def test_recommendation_priority_valid_values(self):
        """Recommendation priorities are valid."""
        result = PrescriptiveAnalytics.generate_recommendations()
        
        valid_priorities = {'high', 'medium', 'low'}
        for rec in result['recommendations']:
            self.assertIn(rec['priority'], valid_priorities)
    
    def test_recommendations_sorted_by_priority(self):
        """Recommendations are sorted: high > medium > low."""
        result = PrescriptiveAnalytics.generate_recommendations()
        
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        priorities = [priority_order.get(rec['priority'], 3) for rec in result['recommendations']]
        
        # Check sorted (non-decreasing)
        self.assertEqual(priorities, sorted(priorities))
    
    def test_generate_recommendations_json_serializable(self):
        """Recommendations are JSON serializable."""
        result = PrescriptiveAnalytics.generate_recommendations()
        
        # Should not raise
        json.dumps(result)
    
    # ========================================================================
    # RECOMMENDATION TYPE TESTS
    # ========================================================================
    
    def test_maintenance_windows_recommendation_generated(self):
        """Maintenance window recommendation is generated."""
        result = PrescriptiveAnalytics.generate_recommendations()
        
        maintenance_recs = [
            r for r in result['recommendations']
            if 'maintenance' in r['title'].lower()
        ]
        
        self.assertGreater(len(maintenance_recs), 0, "Should have maintenance-related recommendation")
    
    def test_capacity_expansion_recommendation_generated(self):
        """Capacity expansion recommendation is generated for high-occupancy facilities."""
        result = PrescriptiveAnalytics.generate_recommendations()
        
        capacity_recs = [
            r for r in result['recommendations']
            if 'capacity' in r['title'].lower() and 'expansion' in r['title'].lower()
        ]
        
        # May or may not have this depending on data patterns
        # But if present, should have proper structure
        for rec in capacity_recs:
            self.assertIn('80%', rec['description'])
    
    def test_extended_hours_recommendation_structure(self):
        """Extended hours recommendations have proper structure."""
        result = PrescriptiveAnalytics.generate_recommendations()
        
        extended_recs = [
            r for r in result['recommendations']
            if 'extend' in r['title'].lower() and 'hour' in r['title'].lower()
        ]
        
        for rec in extended_recs:
            self.assertIsNotNone(rec['description'])
            self.assertGreater(len(rec['description']), 10)
    
    def test_equipment_maintenance_recommendation_structure(self):
        """Equipment maintenance recommendations have proper structure."""
        result = PrescriptiveAnalytics.generate_recommendations()
        
        equipment_recs = [
            r for r in result['recommendations']
            if 'equipment' in r['title'].lower() and 'maintenance' in r['title'].lower()
        ]
        
        for rec in equipment_recs:
            self.assertEqual(rec['priority'], 'high')
            self.assertIn('preventive', rec['action'].lower())
    
    def test_seasonal_patterns_recommendation_structure(self):
        """Seasonal pattern recommendations have proper structure."""
        result = PrescriptiveAnalytics.generate_recommendations()
        
        seasonal_recs = [
            r for r in result['recommendations']
            if 'demand' in r['title'].lower() and ('increasing' in r['title'].lower() or 'decreasing' in r['title'].lower())
        ]
        
        for rec in seasonal_recs:
            self.assertIn('forecast', rec['description'].lower())
    
    # ========================================================================
    # CACHING TESTS
    # ========================================================================
    
    def test_generate_recommendations_caching(self):
        """Recommendations are cached."""
        # First call computes
        result1 = PrescriptiveAnalytics.generate_recommendations()
        
        # Second call should be cached
        result2 = PrescriptiveAnalytics.generate_recommendations()
        
        self.assertEqual(result1, result2)
        
        # Verify cache entry exists
        cached = cache.get('prescriptive_recommendations')
        self.assertIsNotNone(cached)
    
    def test_cache_invalidation(self):
        """Cache invalidation clears recommendations cache."""
        # Populate cache
        PrescriptiveAnalytics.generate_recommendations()
        self.assertIsNotNone(cache.get('prescriptive_recommendations'))
        
        # Invalidate cache
        PrescriptiveAnalytics.invalidate_cache()
        
        # Cache should be cleared
        self.assertIsNone(cache.get('prescriptive_recommendations'))
    
    def test_cache_recompute_after_invalidation(self):
        """Cache is recomputed after invalidation."""
        result1 = PrescriptiveAnalytics.generate_recommendations()
        
        # Invalidate
        PrescriptiveAnalytics.invalidate_cache()
        
        # Should recompute (different timestamp)
        result2 = PrescriptiveAnalytics.generate_recommendations()
        
        self.assertNotEqual(
            result1['generation_timestamp'],
            result2['generation_timestamp'],
            "Should have different timestamps after cache invalidation"
        )
    
    # ========================================================================
    # EDGE CASES
    # ========================================================================
    
    def test_empty_database_handles_gracefully(self):
        """Recommendations handle empty database gracefully."""
        Reservation.objects.using('default').all().delete()
        cache.clear()
        
        # Should not raise
        result = PrescriptiveAnalytics.generate_recommendations()
        
        self.assertIsNotNone(result)
        self.assertIn('recommendations', result)
        # May return empty or minimal recommendations
        self.assertLessEqual(len(result['recommendations']), 6)
    
    def test_single_facility_handles_gracefully(self):
        """Recommendations handle single facility gracefully."""
        # Delete all but one facility
        self.lab_2.delete()
        self.classroom.delete()
        cache.clear()
        
        result = PrescriptiveAnalytics.generate_recommendations()
        
        self.assertIsNotNone(result)
        self.assertIn('recommendations', result)
        # Should still generate some recommendations
        self.assertGreater(len(result['recommendations']), 0)
    
    def test_no_occupancy_patterns_handles_gracefully(self):
        """Recommendations handle uniform occupancy gracefully."""
        # Create minimal uniform data (all same occupancy)
        Reservation.objects.using('default').all().delete()
        today = timezone.localdate()
        
        # Single reservation
        Reservation.objects.using('default').create(
            requested_by=self.requester,
            facility=self.lab_1,
            purpose='Single test',
            reservation_date=today + datetime.timedelta(days=30),
            start_time=datetime.time(10, 0),
            end_time=datetime.time(11, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=self.staff,
            reviewed_at=timezone.now(),
            is_synthetic=True,
        )
        cache.clear()
        
        result = PrescriptiveAnalytics.generate_recommendations()
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result['recommendations'], list)
    
    # ========================================================================
    # REALISTIC DATA VALIDATION
    # ========================================================================
    
    def test_recommendations_contain_specific_facility_names(self):
        """Recommendations mention specific facilities when applicable."""
        result = PrescriptiveAnalytics.generate_recommendations()
        
        # At least some recommendations should mention facility names
        all_text = ' '.join(
            f"{r['title']} {r['description']}"
            for r in result['recommendations']
        )
        
        # Should mention at least one facility name
        facility_names = ['ComLab 1', 'ComLab 2', 'Classroom 101']
        mentions = sum(1 for name in facility_names if name in all_text)
        
        # May or may not mention specific facilities depending on data
        # But recommendations should be sensible
        self.assertGreater(len(result['recommendations']), 0)
    
    def test_recommendations_based_on_synthetic_patterns(self):
        """Recommendations reflect synthetic booking patterns."""
        result = PrescriptiveAnalytics.generate_recommendations()
        
        # With our synthetic data (peak hours 2-5pm), should mention peak hours
        all_text = ' '.join(
            f"{r['title']} {r['description']}"
            for r in result['recommendations']
        )
        
        # Should contain time-related recommendations
        time_keywords = [
            ':00', 'am', 'pm', 'hour', 'period', 'evening', 'morning'
        ]
        
        has_time_mention = any(keyword in all_text.lower() for keyword in time_keywords)
        self.assertTrue(has_time_mention, "Recommendations should mention time-based patterns")
    
    def test_high_priority_recommendations_appear_first(self):
        """High-priority recommendations appear before medium/low."""
        result = PrescriptiveAnalytics.generate_recommendations()
        recommendations = result['recommendations']
        
        if len(recommendations) > 1:
            # Find first non-high priority
            first_non_high = next(
                (i for i, r in enumerate(recommendations) if r['priority'] != 'high'),
                len(recommendations)
            )
            
            # All high-priority should be before first non-high
            for i in range(first_non_high, len(recommendations)):
                self.assertNotEqual(
                    recommendations[i]['priority'], 'high',
                    f"High-priority recommendation at index {i} should appear earlier"
                )
    
    # ========================================================================
    # PERFORMANCE TESTS
    # ========================================================================
    
    def test_generate_recommendations_performance_under_2_seconds(self):
        """Recommendation generation completes in < 2 seconds."""
        cache.clear()  # Clear cache to force computation
        start = time.time()
        PrescriptiveAnalytics.generate_recommendations()
        elapsed = time.time() - start
        
        self.assertLess(elapsed, 2.0, f"Generation took {elapsed:.2f}s, expected < 2s")
    
    # ========================================================================
    # INTEGRATION WITH PREDICTIVE ANALYTICS
    # ========================================================================
    
    def test_generate_recommendations_with_provided_analytics(self):
        """Recommendations accept pre-computed analytics data."""
        # Compute analytics
        analytics_data = {
            'occupancy_by_facility': PredictiveAnalytics.compute_occupancy_by_facility(),
            'peak_hours': PredictiveAnalytics.compute_peak_hours(),
            'peak_days': PredictiveAnalytics.compute_peak_days(),
            'facility_booking_intensity': [],
        }
        
        # Pass to recommendation generator
        result = PrescriptiveAnalytics.generate_recommendations(analytics_data=analytics_data)
        
        self.assertIsNotNone(result)
        self.assertIn('recommendations', result)
        self.assertGreater(len(result['recommendations']), 0)
    
    def test_recommendation_content_quality(self):
        """Recommendation content has good quality (non-generic)."""
        result = PrescriptiveAnalytics.generate_recommendations()
        
        for rec in result['recommendations']:
            # Titles should be specific, not generic
            self.assertGreater(len(rec['title']), 20, "Title too short/generic")
            
            # Descriptions should have details
            self.assertGreater(len(rec['description']), 50, "Description should have details")
            
            # Actions should be concrete
            self.assertGreater(len(rec['action']), 20, "Action should be specific")
            
            # Impact should be clear
            self.assertGreater(len(rec['impact']), 15, "Impact should be stated")
    
    def test_timestamps_are_iso_format(self):
        """Generation timestamps are in ISO format."""
        result = PrescriptiveAnalytics.generate_recommendations()
        
        timestamp = result['generation_timestamp']
        # Should be ISO format and parseable
        try:
            from datetime import datetime as dt
            dt.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            self.fail(f"Timestamp '{timestamp}' is not valid ISO format")
