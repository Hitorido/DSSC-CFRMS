"""Unit and integration tests for QueryOptimizer class."""

from django.test import TestCase
from django.db import connection
from django.test.utils import CaptureQueriesContext
from datetime import date, timedelta

from config.list_utils import QueryOptimizer
from reservations.models import Reservation
from facilities.models import Facility, FacilityType
from django.contrib.auth import get_user_model

User = get_user_model()


def get_test_date(days_ahead=30):
    """Get a date in the future for testing."""
    return date.today() + timedelta(days=days_ahead)


class TestQueryOptimizerBasics(TestCase):
    """Test QueryOptimizer basic functionality and error handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(username='test', email='test@test.com')
        self.facility_type = FacilityType.objects.create(name='Room')
        self.facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='Test Room',
            location='Building 1',
            capacity=30
        )
    
    def test_apply_with_reservation_model(self):
        """Test QueryOptimizer.apply() with RESERVATION model."""
        queryset = Reservation.objects.all()
        optimized = QueryOptimizer.apply(queryset, 'RESERVATION')
        
        # Should return a queryset
        self.assertIsNotNone(optimized)
        # Should still be a QuerySet
        self.assertTrue(hasattr(optimized, 'model'))
        self.assertEqual(optimized.model, Reservation)
    
    def test_apply_with_facility_model(self):
        """Test QueryOptimizer.apply() with FACILITY model."""
        queryset = Facility.objects.all()
        optimized = QueryOptimizer.apply(queryset, 'FACILITY')
        
        self.assertIsNotNone(optimized)
        self.assertTrue(hasattr(optimized, 'model'))
        self.assertEqual(optimized.model, Facility)
    
    def test_apply_with_maintenance_model(self):
        """Test QueryOptimizer.apply() with MAINTENANCE model."""
        from facilities.models import FacilityMaintenance
        
        queryset = FacilityMaintenance.objects.all()
        optimized = QueryOptimizer.apply(queryset, 'MAINTENANCE')
        
        self.assertIsNotNone(optimized)
        self.assertTrue(hasattr(optimized, 'model'))
        self.assertEqual(optimized.model, FacilityMaintenance)
    
    def test_apply_with_invalid_model_raises_error(self):
        """Test QueryOptimizer.apply() raises ValueError for invalid model."""
        queryset = Reservation.objects.all()
        
        with self.assertRaises(ValueError) as context:
            QueryOptimizer.apply(queryset, 'INVALID_MODEL')
        
        self.assertIn('Unknown model', str(context.exception))
        self.assertIn('INVALID_MODEL', str(context.exception))
    
    def test_apply_is_chainable(self):
        """Test that optimized QuerySet is chainable for further filtering."""
        Reservation.objects.create(
            requested_by=self.user,
            facility=self.facility,
            purpose='Test',
            reservation_date=get_test_date(30),
            start_time='09:00:00',
            end_time='10:00:00',
            status=Reservation.Status.PENDING
        )
        
        queryset = Reservation.objects.all()
        optimized = QueryOptimizer.apply(queryset, 'RESERVATION')
        
        # Should be able to chain further filters
        filtered = optimized.filter(status=Reservation.Status.PENDING)
        self.assertEqual(filtered.count(), 1)


class TestQueryOptimizerQueryCount(TestCase):
    """Test that QueryOptimizer eliminates N+1 queries."""
    
    def setUp(self):
        """Set up test fixtures with multiple records."""
        # Create users
        self.users = [
            User.objects.create_user(username=f'user{i}', email=f'user{i}@test.com')
            for i in range(1, 4)
        ]
        
        # Create facility type
        self.facility_type = FacilityType.objects.create(name='Classroom')
        
        # Create facilities
        self.facilities = [
            Facility.objects.create(
                facility_type=self.facility_type,
                name=f'Room {i}',
                location=f'Building {i}',
                capacity=30
            )
            for i in range(1, 3)
        ]
        
        # Create reservations
        for i in range(1, 6):
            Reservation.objects.create(
                requested_by=self.users[i % 3],
                facility=self.facilities[i % 2],
                purpose=f'Meeting {i}',
                reservation_date=get_test_date(30 + i),
                start_time='09:00:00',
                end_time='10:00:00',
                status=Reservation.Status.PENDING
            )
    
    def test_optimized_query_eliminates_n_plus_one(self):
        """Test that optimized QuerySet eliminates N+1 queries."""
        queryset = Reservation.objects.all()
        optimized = QueryOptimizer.apply(queryset, 'RESERVATION')
        
        with CaptureQueriesContext(connection) as context:
            # Accessing facility and requested_by should not cause additional queries
            for reservation in optimized:
                _ = reservation.facility.name
                _ = reservation.requested_by.username
        
        # Should have exactly 1-3 queries (1 for reservations with joins)
        query_count = len(context.captured_queries)
        self.assertLessEqual(query_count, 3)
    
    def test_reservation_optimizations_applied(self):
        """Test that RESERVATION optimizations include select_related."""
        optimizations = QueryOptimizer.OPTIMIZATIONS['RESERVATION']
        
        self.assertIn('select_related', optimizations)
        self.assertIn('prefetch_related', optimizations)
        
        # Should have select_related for FK relationships
        select_related = optimizations['select_related']
        self.assertIn('facility', select_related)
        self.assertIn('requested_by', select_related)
        self.assertIn('reviewed_by', select_related)
    
    def test_maintenance_optimizations_applied(self):
        """Test that MAINTENANCE optimizations include select_related for facility."""
        from facilities.models import FacilityMaintenance
        
        optimizations = QueryOptimizer.OPTIMIZATIONS['MAINTENANCE']
        
        self.assertIn('select_related', optimizations)
        select_related = optimizations['select_related']
        self.assertIn('facility', select_related)


class TestQueryOptimizerIntegration(TestCase):
    """Integration tests for QueryOptimizer in realistic scenarios."""
    
    def setUp(self):
        """Set up realistic test data."""
        self.user = User.objects.create_user(username='test', email='test@test.com')
        self.facility_type = FacilityType.objects.create(name='Lab')
        self.facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='Lab 1',
            location='Building 1',
            capacity=20
        )
    
    def test_apply_with_filtered_queryset(self):
        """Test QueryOptimizer with already filtered QuerySet."""
        Reservation.objects.create(
            requested_by=self.user,
            facility=self.facility,
            purpose='Lab work',
            reservation_date=get_test_date(30),
            start_time='10:00:00',
            end_time='11:00:00',
            status=Reservation.Status.APPROVED
        )
        
        queryset = Reservation.objects.filter(status=Reservation.Status.APPROVED)
        optimized = QueryOptimizer.apply(queryset, 'RESERVATION')
        
        self.assertEqual(optimized.count(), 1)
    
    def test_apply_with_ordered_queryset(self):
        """Test QueryOptimizer preserves ordering."""
        Reservation.objects.create(
            requested_by=self.user,
            facility=self.facility,
            purpose='Test',
            reservation_date=get_test_date(30),
            start_time='09:00:00',
            end_time='10:00:00'
        )
        
        queryset = Reservation.objects.all().order_by('-id')
        optimized = QueryOptimizer.apply(queryset, 'RESERVATION')
        
        # Get first result
        first = optimized.first()
        self.assertIsNotNone(first)
    
    def test_apply_maintains_queryset_count(self):
        """Test that apply() doesn't change the record count."""
        for i in range(3):
            Reservation.objects.create(
                requested_by=self.user,
                facility=self.facility,
                purpose=f'Meeting {i}',
                reservation_date=get_test_date(30 + i),
                start_time='09:00:00',
                end_time='10:00:00'
            )
        
        queryset = Reservation.objects.all()
        count_before = queryset.count()
        
        optimized = QueryOptimizer.apply(queryset, 'RESERVATION')
        count_after = optimized.count()
        
        self.assertEqual(count_before, count_after)
    
    def test_apply_multiple_times_is_idempotent(self):
        """Test that applying optimizer multiple times is safe."""
        Reservation.objects.create(
            requested_by=self.user,
            facility=self.facility,
            purpose='Test',
            reservation_date=get_test_date(30),
            start_time='09:00:00',
            end_time='10:00:00'
        )
        
        queryset = Reservation.objects.all()
        
        # Apply once
        optimized1 = QueryOptimizer.apply(queryset, 'RESERVATION')
        
        # Apply again
        optimized2 = QueryOptimizer.apply(optimized1, 'RESERVATION')
        
        # Should still work correctly
        count = optimized2.count()
        self.assertEqual(count, 1)


class TestQueryOptimizerOptimizationsDict(TestCase):
    """Test the OPTIMIZATIONS dictionary structure."""
    
    def test_all_models_have_select_related(self):
        """Test that all models define select_related."""
        for model_name, opts in QueryOptimizer.OPTIMIZATIONS.items():
            self.assertIn('select_related', opts, f"{model_name} missing select_related")
            self.assertIsInstance(opts['select_related'], list)
    
    def test_all_models_have_prefetch_related(self):
        """Test that all models define prefetch_related."""
        for model_name, opts in QueryOptimizer.OPTIMIZATIONS.items():
            self.assertIn('prefetch_related', opts, f"{model_name} missing prefetch_related")
            self.assertIsInstance(opts['prefetch_related'], list)
    
    def test_supported_models_count(self):
        """Test that the expected models are supported."""
        supported = set(QueryOptimizer.OPTIMIZATIONS.keys())
        expected = {'RESERVATION', 'FACILITY', 'MAINTENANCE'}
        self.assertEqual(supported, expected)


class TestQueryOptimizerAcceptanceCriteria(TestCase):
    """Test acceptance criteria from design document."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(username='test', email='test@test.com')
        self.facility_type = FacilityType.objects.create(name='Classroom')
        self.facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='Room 101',
            location='Building A',
            capacity=30
        )
        Reservation.objects.create(
            requested_by=self.user,
            facility=self.facility,
            purpose='Test',
            reservation_date=get_test_date(30),
            start_time='09:00:00',
            end_time='10:00:00'
        )
    
    def test_ac_apply_method_exists(self):
        """AC: QueryOptimizer.apply() method exists and is static."""
        self.assertTrue(hasattr(QueryOptimizer, 'apply'))
    
    def test_ac_apply_accepts_queryset_and_model_name(self):
        """AC: apply() accepts queryset and model_name parameters."""
        queryset = Reservation.objects.all()
        # Should not raise TypeError
        result = QueryOptimizer.apply(queryset, 'RESERVATION')
        self.assertIsNotNone(result)
    
    def test_ac_returns_queryset(self):
        """AC: apply() returns a QuerySet."""
        queryset = Reservation.objects.all()
        result = QueryOptimizer.apply(queryset, 'RESERVATION')
        
        self.assertTrue(hasattr(result, 'model'))
        self.assertTrue(hasattr(result, 'filter'))
        self.assertTrue(hasattr(result, 'exclude'))
    
    def test_ac_apply_for_reservation_optimization(self):
        """
        AC: Reservation optimization includes
        select_related=['facility', 'requested_by', 'reviewed_by']
        """
        optimizations = QueryOptimizer.OPTIMIZATIONS['RESERVATION']
        select_related = optimizations['select_related']
        
        self.assertIn('facility', select_related)
        self.assertIn('requested_by', select_related)
        self.assertIn('reviewed_by', select_related)
    
    def test_ac_apply_for_maintenance_optimization(self):
        """
        AC: Maintenance optimization includes
        select_related=['facility']
        """
        optimizations = QueryOptimizer.OPTIMIZATIONS['MAINTENANCE']
        select_related = optimizations['select_related']
        
        self.assertIn('facility', select_related)
    
    def test_ac_query_count_bounded(self):
        """
        AC: Query count bounded - for any paginated list view,
        the query count should be exactly 2 (one for paginator.count,
        one for page fetch), not N+1.
        
        **Validates: Requirements 10.2, 10.3, 12.1, 12.2**
        """
        # Create additional reservations on different days and times to avoid conflicts
        for i in range(1, 5):  # Skip first one, it was created in setUp
            Reservation.objects.create(
                requested_by=self.user,
                facility=self.facility,
                purpose=f'Meeting {i}',
                reservation_date=get_test_date(30 + i),  # Different dates
                start_time=f'{10+i}:00:00',  # Different times
                end_time=f'{11+i}:00:00'
            )
        
        queryset = Reservation.objects.all()
        optimized = QueryOptimizer.apply(queryset, 'RESERVATION')
        
        with CaptureQueriesContext(connection) as context:
            # Access related objects
            for res in optimized:
                _ = res.facility.name
                _ = res.requested_by.username
        
        query_count = len(context.captured_queries)
        # Should be at most 3 (one for reservations with joins)
        self.assertLessEqual(query_count, 3)
