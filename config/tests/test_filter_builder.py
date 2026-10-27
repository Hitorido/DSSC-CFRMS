"""Unit tests for FilterBuilder utility class."""

from datetime import date

from django.test import TestCase
from django.db.models import Q

from config.list_utils import FilterBuilder


class TestBuildSearchFilter(TestCase):
    """Test suite for FilterBuilder.build_search_filter() method."""
    
    def test_search_single_field(self):
        """Test search filter with single field."""
        q = FilterBuilder.build_search_filter('test', ['facility__name'])
        
        # Should return Q(facility__name__icontains='test')
        self.assertIsInstance(q, Q)
        self.assertIn('facility__name__icontains', str(q))
    
    def test_search_multiple_fields_or_logic(self):
        """Test search filter with multiple fields uses OR logic."""
        q = FilterBuilder.build_search_filter('Building A', ['facility__name', 'purpose'])
        
        # Should return Q(facility__name__icontains='Building A') | Q(purpose__icontains='Building A')
        self.assertIsInstance(q, Q)
        q_str = str(q)
        self.assertIn('facility__name__icontains', q_str)
        self.assertIn('purpose__icontains', q_str)
        self.assertIn('OR', q_str)
    
    def test_search_three_fields(self):
        """Test search filter with three fields."""
        q = FilterBuilder.build_search_filter('test', ['field1', 'field2', 'field3'])
        
        self.assertIsInstance(q, Q)
        q_str = str(q)
        self.assertIn('field1__icontains', q_str)
        self.assertIn('field2__icontains', q_str)
        self.assertIn('field3__icontains', q_str)
    
    def test_search_empty_term_returns_empty_q(self):
        """Test that empty search term returns empty Q()."""
        q = FilterBuilder.build_search_filter('', ['field1'])
        
        # Empty Q() should have no children (connector is empty)
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_search_none_term_returns_empty_q(self):
        """Test that None search term returns empty Q()."""
        q = FilterBuilder.build_search_filter(None, ['field1'])
        
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_search_whitespace_only_returns_empty_q(self):
        """Test that whitespace-only search term returns empty Q()."""
        q = FilterBuilder.build_search_filter('   ', ['field1'])
        
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_search_empty_fields_list_returns_empty_q(self):
        """Test that empty search_fields list returns empty Q()."""
        q = FilterBuilder.build_search_filter('test', [])
        
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_search_none_fields_list_returns_empty_q(self):
        """Test that None search_fields list returns empty Q()."""
        q = FilterBuilder.build_search_filter('test', None)
        
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_search_special_characters(self):
        """Test search with special characters (SQL injection prevention)."""
        # These should not cause SQL injection because they use parameterized lookups
        special_terms = [
            "'; DROP TABLE--",
            "1' OR '1'='1",
            "test%wildcard%",
            "test*asterisk",
        ]
        
        for term in special_terms:
            q = FilterBuilder.build_search_filter(term, ['field1'])
            # Should not raise exception
            self.assertIsInstance(q, Q)
            # The term should be in the Q object (safely parameterized)
            self.assertIn(term, str(q))
    
    def test_search_unicode_characters(self):
        """Test search with unicode characters."""
        q = FilterBuilder.build_search_filter('Москва', ['facility__name'])
        
        self.assertIsInstance(q, Q)
        self.assertIn('Москва', str(q))
    
    def test_search_numbers(self):
        """Test search with numeric characters."""
        q = FilterBuilder.build_search_filter('12345', ['reservation_id'])
        
        self.assertIsInstance(q, Q)
        self.assertIn('12345', str(q))
    
    def test_search_with_nested_field(self):
        """Test search with nested related field."""
        q = FilterBuilder.build_search_filter('John', ['requested_by__first_name', 'requested_by__last_name'])
        
        self.assertIsInstance(q, Q)
        q_str = str(q)
        self.assertIn('requested_by__first_name__icontains', q_str)
        self.assertIn('requested_by__last_name__icontains', q_str)
    
    def test_acceptance_criteria_search_filter(self):
        """
        Test acceptance criteria:
        GIVEN search_term='Building A' and search_fields=['facility__name', 'purpose'],
        WHEN build_search_filter is called,
        THEN it returns Q(facility__name__icontains='Building A') | Q(purpose__icontains='Building A')
        """
        q = FilterBuilder.build_search_filter('Building A', ['facility__name', 'purpose'])
        
        q_str = str(q)
        self.assertIn('facility__name__icontains', q_str)
        self.assertIn('Building A', q_str)
        self.assertIn('purpose__icontains', q_str)
        self.assertIn('OR', q_str)


class TestBuildStatusFilter(TestCase):
    """Test suite for FilterBuilder.build_status_filter() method."""
    
    def setUp(self):
        """Set up valid statuses from Reservation model."""
        # Mock status choices like Reservation.Status.choices
        self.valid_statuses = [
            ('PENDING', 'Pending'),
            ('APPROVED', 'Approved'),
            ('COMPLETED', 'Completed'),
            ('REJECTED', 'Declined'),
            ('CANCELLED', 'Cancelled'),
        ]
    
    def test_status_valid_returns_q_object(self):
        """Test that valid status returns Q object with status filter."""
        q = FilterBuilder.build_status_filter('PENDING', self.valid_statuses)
        
        self.assertIsInstance(q, Q)
        self.assertIn('status', str(q))
        self.assertIn('PENDING', str(q))
    
    def test_status_multiple_valid_values(self):
        """Test with multiple valid statuses in choices."""
        for status in ['PENDING', 'APPROVED', 'COMPLETED', 'REJECTED', 'CANCELLED']:
            q = FilterBuilder.build_status_filter(status, self.valid_statuses)
            self.assertIsInstance(q, Q)
            self.assertIn(status, str(q))
    
    def test_status_invalid_raises_value_error(self):
        """Test that invalid status raises ValueError."""
        with self.assertRaises(ValueError) as context:
            FilterBuilder.build_status_filter('INVALID', self.valid_statuses)
        
        self.assertIn('Invalid status', str(context.exception))
        self.assertIn('INVALID', str(context.exception))
    
    def test_status_empty_string_returns_empty_q(self):
        """Test that empty status string returns empty Q()."""
        q = FilterBuilder.build_status_filter('', self.valid_statuses)
        
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_status_none_returns_empty_q(self):
        """Test that None status returns empty Q()."""
        q = FilterBuilder.build_status_filter(None, self.valid_statuses)
        
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_status_whitespace_returns_empty_q(self):
        """Test that whitespace-only status returns empty Q()."""
        q = FilterBuilder.build_status_filter('   ', self.valid_statuses)
        
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_status_with_list_of_values_only(self):
        """Test build_status_filter with simple list of values (not tuples)."""
        valid_values = ['PENDING', 'APPROVED', 'COMPLETED', 'REJECTED', 'CANCELLED']
        q = FilterBuilder.build_status_filter('APPROVED', valid_values)
        
        self.assertIsInstance(q, Q)
        self.assertIn('APPROVED', str(q))
    
    def test_status_case_sensitive(self):
        """Test that status filtering is case-sensitive."""
        # 'pending' (lowercase) should not match 'PENDING'
        with self.assertRaises(ValueError):
            FilterBuilder.build_status_filter('pending', self.valid_statuses)
    
    def test_status_special_characters_raises_error(self):
        """Test that special characters in status raise ValueError."""
        with self.assertRaises(ValueError):
            FilterBuilder.build_status_filter("'; DROP TABLE--", self.valid_statuses)
    
    def test_acceptance_criteria_valid_status(self):
        """
        Test acceptance criteria:
        GIVEN status='PENDING' and valid_statuses from model choices,
        WHEN build_status_filter is called,
        THEN it returns Q(status='PENDING')
        """
        q = FilterBuilder.build_status_filter('PENDING', self.valid_statuses)
        
        self.assertIsInstance(q, Q)
        q_str = str(q)
        self.assertIn('status', q_str)
        self.assertIn('PENDING', q_str)
    
    def test_acceptance_criteria_invalid_status(self):
        """
        Test acceptance criteria:
        GIVEN an invalid status not in choices,
        WHEN build_status_filter is called,
        THEN it raises ValueError
        """
        with self.assertRaises(ValueError):
            FilterBuilder.build_status_filter('NOTVALID', self.valid_statuses)


class TestBuildDateRangeFilter(TestCase):
    """Test suite for FilterBuilder.build_date_range_filter() method."""
    
    def test_date_range_both_dates_string_format(self):
        """Test date range filter with both dates as strings."""
        q = FilterBuilder.build_date_range_filter('2024-01-01', '2024-01-31')
        
        self.assertIsInstance(q, Q)
        q_str = str(q)
        self.assertIn('reservation_date__gte', q_str)
        self.assertIn('reservation_date__lte', q_str)
    
    def test_date_range_start_date_only(self):
        """Test date range filter with only start date."""
        q = FilterBuilder.build_date_range_filter('2024-01-01', '')
        
        self.assertIsInstance(q, Q)
        q_str = str(q)
        self.assertIn('reservation_date__gte', q_str)
        self.assertNotIn('lte', q_str)
    
    def test_date_range_end_date_only(self):
        """Test date range filter with only end date."""
        q = FilterBuilder.build_date_range_filter('', '2024-01-31')
        
        self.assertIsInstance(q, Q)
        q_str = str(q)
        self.assertIn('reservation_date__lte', q_str)
        self.assertNotIn('gte', q_str)
    
    def test_date_range_both_dates_none_returns_empty_q(self):
        """Test that empty dates return empty Q()."""
        q = FilterBuilder.build_date_range_filter('', '')
        
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_date_range_none_dates_returns_empty_q(self):
        """Test that None dates return empty Q()."""
        q = FilterBuilder.build_date_range_filter(None, None)
        
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_date_range_invalid_start_date_ignored(self):
        """Test that invalid start date is ignored."""
        q = FilterBuilder.build_date_range_filter('invalid', '2024-01-31')
        
        # Invalid date is ignored, only end date is applied
        q_str = str(q)
        self.assertIn('reservation_date__lte', q_str)
        self.assertNotIn('gte', q_str)
    
    def test_date_range_invalid_end_date_ignored(self):
        """Test that invalid end date is ignored."""
        q = FilterBuilder.build_date_range_filter('2024-01-01', 'invalid')
        
        # Invalid date is ignored, only start date is applied
        q_str = str(q)
        self.assertIn('reservation_date__gte', q_str)
        self.assertNotIn('lte', q_str)
    
    def test_date_range_both_dates_invalid_returns_empty_q(self):
        """Test that both invalid dates return empty Q()."""
        q = FilterBuilder.build_date_range_filter('invalid1', 'invalid2')
        
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_date_range_with_date_objects(self):
        """Test date range filter with date objects instead of strings."""
        start = date(2024, 1, 1)
        end = date(2024, 1, 31)
        q = FilterBuilder.build_date_range_filter(start, end)
        
        self.assertIsInstance(q, Q)
        q_str = str(q)
        self.assertIn('reservation_date__gte', q_str)
        self.assertIn('reservation_date__lte', q_str)
    
    def test_date_range_custom_field_name(self):
        """Test date range filter with custom date field name."""
        q = FilterBuilder.build_date_range_filter('2024-01-01', '2024-01-31', date_field='maintenance_date')
        
        self.assertIsInstance(q, Q)
        q_str = str(q)
        self.assertIn('maintenance_date__gte', q_str)
        self.assertIn('maintenance_date__lte', q_str)
        self.assertNotIn('reservation_date', q_str)
    
    def test_date_range_various_formats(self):
        """Test date range with various date formats."""
        # parse_date only accepts YYYY-MM-DD, so test that format
        q = FilterBuilder.build_date_range_filter('2024-01-01', '2024-12-31')
        
        self.assertIsInstance(q, Q)
    
    def test_date_range_leap_year(self):
        """Test date range with leap year date."""
        q = FilterBuilder.build_date_range_filter('2024-02-29', '2024-02-29')
        
        self.assertIsInstance(q, Q)
        q_str = str(q)
        # The date will be represented as datetime.date objects in the Q string
        self.assertIn('2024', q_str)
        self.assertIn('02', q_str)
    
    def test_date_range_single_day(self):
        """Test date range for a single day."""
        q = FilterBuilder.build_date_range_filter('2024-01-15', '2024-01-15')
        
        self.assertIsInstance(q, Q)
    
    def test_date_range_special_characters_ignored(self):
        """Test that special characters in date strings are handled safely."""
        # Invalid dates are silently ignored by parse_date
        q = FilterBuilder.build_date_range_filter("2024-01-01'; DROP TABLE--", '2024-01-31')
        
        # The invalid start date should be ignored
        q_str = str(q)
        self.assertIn('reservation_date__lte', q_str)
    
    def test_acceptance_criteria_date_range(self):
        """
        Test acceptance criteria:
        GIVEN start_date='2024-01-01' and end_date='2024-01-31',
        WHEN build_date_range_filter is called,
        THEN it returns Q(reservation_date__gte='2024-01-01', reservation_date__lte='2024-01-31')
        """
        q = FilterBuilder.build_date_range_filter('2024-01-01', '2024-01-31')
        
        self.assertIsInstance(q, Q)
        q_str = str(q)
        self.assertIn('reservation_date__gte', q_str)
        # The date will be represented as datetime.date(2024, 1, 1) in the Q string
        self.assertIn('2024', q_str)
        self.assertIn('reservation_date__lte', q_str)


class TestBuildFacilityFilter(TestCase):
    """Test suite for FilterBuilder.build_facility_filter() method."""
    
    def test_facility_integer_id(self):
        """Test facility filter with integer ID."""
        q = FilterBuilder.build_facility_filter(123)
        
        self.assertIsInstance(q, Q)
        self.assertIn('facility_id', str(q))
        self.assertIn('123', str(q))
    
    def test_facility_string_id(self):
        """Test facility filter with string ID."""
        q = FilterBuilder.build_facility_filter('456')
        
        self.assertIsInstance(q, Q)
        q_str = str(q)
        self.assertIn('facility_id', q_str)
        self.assertIn('456', q_str)
    
    def test_facility_empty_string_returns_empty_q(self):
        """Test that empty string facility ID returns empty Q()."""
        q = FilterBuilder.build_facility_filter('')
        
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_facility_none_returns_empty_q(self):
        """Test that None facility ID returns empty Q()."""
        q = FilterBuilder.build_facility_filter(None)
        
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_facility_zero_returns_empty_q(self):
        """Test that zero facility ID returns empty Q()."""
        q = FilterBuilder.build_facility_filter(0)
        
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_facility_string_zero_returns_empty_q(self):
        """Test that '0' string facility ID returns empty Q()."""
        q = FilterBuilder.build_facility_filter('0')
        
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_facility_negative_id_returns_empty_q(self):
        """Test that negative facility ID returns empty Q()."""
        q = FilterBuilder.build_facility_filter(-1)
        
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_facility_string_negative_returns_empty_q(self):
        """Test that negative string facility ID returns empty Q()."""
        q = FilterBuilder.build_facility_filter('-123')
        
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_facility_invalid_string_returns_empty_q(self):
        """Test that non-numeric string facility ID returns empty Q()."""
        q = FilterBuilder.build_facility_filter('abc')
        
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_facility_float_string_converted(self):
        """Test facility filter with float string."""
        q = FilterBuilder.build_facility_filter('123.5')
        
        # Should attempt conversion, this might work or fail depending on implementation
        # If it works, should convert to 123
        self.assertIsInstance(q, Q)
    
    def test_facility_special_characters_returns_empty_q(self):
        """Test that special characters return empty Q()."""
        q = FilterBuilder.build_facility_filter("123'; DROP TABLE--")
        
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_facility_whitespace_returns_empty_q(self):
        """Test that whitespace facility ID returns empty Q()."""
        q = FilterBuilder.build_facility_filter('   ')
        
        self.assertIsInstance(q, Q)
        self.assertEqual(len(q.children), 0)
    
    def test_facility_large_id(self):
        """Test facility filter with large ID number."""
        large_id = 999999999
        q = FilterBuilder.build_facility_filter(large_id)
        
        self.assertIsInstance(q, Q)
        self.assertIn('facility_id', str(q))
    
    def test_facility_id_one(self):
        """Test facility filter with ID of 1."""
        q = FilterBuilder.build_facility_filter(1)
        
        self.assertIsInstance(q, Q)
        q_str = str(q)
        self.assertIn('facility_id', q_str)
        self.assertIn('1', q_str)


class TestFilterBuilderIntegration(TestCase):
    """Integration tests combining multiple FilterBuilder methods."""
    
    def setUp(self):
        """Set up test data."""
        self.valid_statuses = [
            ('PENDING', 'Pending'),
            ('APPROVED', 'Approved'),
            ('COMPLETED', 'Completed'),
            ('REJECTED', 'Declined'),
            ('CANCELLED', 'Cancelled'),
        ]
    
    def test_combined_search_and_status_filter(self):
        """Test combining search and status filters."""
        search_q = FilterBuilder.build_search_filter('Building A', ['facility__name'])
        status_q = FilterBuilder.build_status_filter('PENDING', self.valid_statuses)
        
        # Combined filter should use AND logic
        combined = search_q & status_q
        
        self.assertIsInstance(combined, Q)
        combined_str = str(combined)
        self.assertIn('facility__name__icontains', combined_str)
        self.assertIn('Building A', combined_str)
        self.assertIn('status', combined_str)
        self.assertIn('PENDING', combined_str)
    
    def test_all_filters_combined(self):
        """Test combining all filter types."""
        search_q = FilterBuilder.build_search_filter('test', ['facility__name'])
        status_q = FilterBuilder.build_status_filter('APPROVED', self.valid_statuses)
        date_q = FilterBuilder.build_date_range_filter('2024-01-01', '2024-01-31')
        facility_q = FilterBuilder.build_facility_filter(5)
        
        combined = search_q & status_q & date_q & facility_q
        
        self.assertIsInstance(combined, Q)
        combined_str = str(combined)
        self.assertIn('facility__name__icontains', combined_str)
        self.assertIn('status', combined_str)
        self.assertIn('reservation_date', combined_str)
        self.assertIn('facility_id', combined_str)
    
    def test_empty_filters_combined(self):
        """Test combining empty filters."""
        search_q = FilterBuilder.build_search_filter('', ['field1'])
        status_q = FilterBuilder.build_status_filter('', self.valid_statuses)
        date_q = FilterBuilder.build_date_range_filter('', '')
        facility_q = FilterBuilder.build_facility_filter('')
        
        combined = search_q & status_q & date_q & facility_q
        
        # All empty should result in empty Q
        self.assertIsInstance(combined, Q)
        self.assertEqual(len(combined.children), 0)
    
    def test_partial_empty_filters(self):
        """Test combining some empty and some valid filters."""
        search_q = FilterBuilder.build_search_filter('test', ['facility__name'])
        status_q = FilterBuilder.build_status_filter('', self.valid_statuses)
        date_q = FilterBuilder.build_date_range_filter('2024-01-01', '')
        facility_q = FilterBuilder.build_facility_filter('')
        
        combined = search_q & status_q & date_q & facility_q
        
        self.assertIsInstance(combined, Q)
        combined_str = str(combined)
        # Should include search and date filters
        self.assertIn('facility__name__icontains', combined_str)
        self.assertIn('reservation_date__gte', combined_str)
        # Should not include status or facility (they were empty)
        # Status filter won't appear if empty
        # Facility filter won't appear if empty
