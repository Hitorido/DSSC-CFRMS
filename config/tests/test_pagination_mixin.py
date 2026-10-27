"""Unit tests for PaginationMixin class."""

from django.test import TestCase
from django.core.paginator import Paginator

from config.list_utils import PaginationMixin


class TestPaginationMixin(TestCase):
    """Test suite for PaginationMixin.get_page_context() method."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mixin = PaginationMixin()
        self.mixin.paginate_by = 100
        
        # Create a mock queryset with 250 items
        self.queryset = list(range(1, 251))
    
    def test_valid_page_number_returns_correct_records(self):
        """Test that valid page number returns correct records."""
        context = self.mixin.get_page_context(self.queryset, page_number=2)
        
        # Page 2 should contain records 101-200
        self.assertEqual(context['page'].number, 2)
        self.assertEqual(context['start_index'], 101)
        self.assertEqual(context['end_index'], 200)
        self.assertTrue(context['has_previous'])
        self.assertTrue(context['has_next'])
    
    def test_page_one_returns_first_records(self):
        """Test that page 1 returns records 1-100."""
        context = self.mixin.get_page_context(self.queryset, page_number=1)
        
        self.assertEqual(context['page'].number, 1)
        self.assertEqual(context['start_index'], 1)
        self.assertEqual(context['end_index'], 100)
        self.assertFalse(context['has_previous'])
        self.assertTrue(context['has_next'])
    
    def test_last_page_returns_correct_records(self):
        """Test that last page returns correct records."""
        context = self.mixin.get_page_context(self.queryset, page_number=3)
        
        # Page 3 should contain records 201-250
        self.assertEqual(context['page'].number, 3)
        self.assertEqual(context['start_index'], 201)
        self.assertEqual(context['end_index'], 250)
        self.assertTrue(context['has_previous'])
        self.assertFalse(context['has_next'])
    
    def test_invalid_string_page_defaults_to_page_one(self):
        """Test that invalid string page number defaults to page 1."""
        context = self.mixin.get_page_context(self.queryset, page_number='invalid')
        
        # Should default to page 1
        self.assertEqual(context['page'].number, 1)
        self.assertEqual(context['start_index'], 1)
        self.assertEqual(context['end_index'], 100)
    
    def test_numeric_string_page_is_converted(self):
        """Test that numeric string page number is converted to int."""
        context = self.mixin.get_page_context(self.queryset, page_number='2')
        
        self.assertEqual(context['page'].number, 2)
        self.assertEqual(context['start_index'], 101)
        self.assertEqual(context['end_index'], 200)
    
    def test_out_of_range_page_returns_last_page(self):
        """Test that out of range page number returns last page."""
        context = self.mixin.get_page_context(self.queryset, page_number=999)
        
        # Should return last page (page 3)
        self.assertEqual(context['page'].number, 3)
        self.assertEqual(context['start_index'], 201)
        self.assertEqual(context['end_index'], 250)
        self.assertFalse(context['has_next'])
    
    def test_negative_page_number_defaults_to_page_one(self):
        """Test that negative page number defaults to page 1."""
        context = self.mixin.get_page_context(self.queryset, page_number=-1)
        
        self.assertEqual(context['page'].number, 1)
        self.assertEqual(context['start_index'], 1)
    
    def test_zero_page_number_defaults_to_page_one(self):
        """Test that zero page number defaults to page 1."""
        context = self.mixin.get_page_context(self.queryset, page_number=0)
        
        self.assertEqual(context['page'].number, 1)
        self.assertEqual(context['start_index'], 1)
    
    def test_none_page_number_defaults_to_page_one(self):
        """Test that None page number defaults to page 1."""
        context = self.mixin.get_page_context(self.queryset, page_number=None)
        
        self.assertEqual(context['page'].number, 1)
        self.assertEqual(context['start_index'], 1)
    
    def test_empty_string_page_defaults_to_page_one(self):
        """Test that empty string page number defaults to page 1."""
        context = self.mixin.get_page_context(self.queryset, page_number='')
        
        self.assertEqual(context['page'].number, 1)
        self.assertEqual(context['start_index'], 1)
    
    def test_whitespace_only_page_defaults_to_page_one(self):
        """Test that whitespace-only page number defaults to page 1."""
        context = self.mixin.get_page_context(self.queryset, page_number='   ')
        
        self.assertEqual(context['page'].number, 1)
    
    def test_is_paginated_true_for_multiple_pages(self):
        """Test that is_paginated is True when multiple pages exist."""
        context = self.mixin.get_page_context(self.queryset, page_number=1)
        
        self.assertTrue(context['is_paginated'])
    
    def test_is_paginated_false_for_single_page(self):
        """Test that is_paginated is False when only one page exists."""
        small_queryset = list(range(1, 51))
        context = self.mixin.get_page_context(small_queryset, page_number=1)
        
        self.assertFalse(context['is_paginated'])
    
    def test_context_contains_all_required_keys(self):
        """Test that returned context contains all required keys."""
        context = self.mixin.get_page_context(self.queryset, page_number=1)
        
        required_keys = {
            'page', 'paginator', 'is_paginated', 
            'has_previous', 'has_next', 'start_index', 'end_index'
        }
        self.assertEqual(set(context.keys()), required_keys)
    
    def test_empty_queryset_returns_page_one(self):
        """Test that empty queryset is handled gracefully."""
        empty_queryset = []
        context = self.mixin.get_page_context(empty_queryset, page_number=1)
        
        self.assertEqual(context['page'].number, 1)
        self.assertFalse(context['is_paginated'])
        self.assertFalse(context['has_previous'])
        self.assertFalse(context['has_next'])
        self.assertEqual(context['paginator'].count, 0)
    
    def test_empty_queryset_with_invalid_page_returns_page_one(self):
        """Test that empty queryset with invalid page returns page 1."""
        empty_queryset = []
        context = self.mixin.get_page_context(empty_queryset, page_number=999)
        
        self.assertEqual(context['page'].number, 1)
        self.assertFalse(context['is_paginated'])
    
    def test_single_record_queryset(self):
        """Test queryset with single record."""
        single_queryset = [1]
        context = self.mixin.get_page_context(single_queryset, page_number=1)
        
        self.assertEqual(context['page'].number, 1)
        self.assertEqual(context['start_index'], 1)
        self.assertEqual(context['end_index'], 1)
        self.assertFalse(context['is_paginated'])
    
    def test_exact_page_size_queryset(self):
        """Test queryset with exactly page_size records."""
        exact_queryset = list(range(1, 101))
        context = self.mixin.get_page_context(exact_queryset, page_number=1)
        
        self.assertEqual(context['page'].number, 1)
        self.assertEqual(context['start_index'], 1)
        self.assertEqual(context['end_index'], 100)
        self.assertFalse(context['is_paginated'])  # Only one page needed
    
    def test_one_over_page_size_queryset(self):
        """Test queryset with one more than page_size records."""
        over_queryset = list(range(1, 102))
        context = self.mixin.get_page_context(over_queryset, page_number=1)
        
        self.assertTrue(context['is_paginated'])
        self.assertEqual(context['paginator'].num_pages, 2)
    
    def test_float_page_number_converted_to_int(self):
        """Test that float page number is converted to int."""
        context = self.mixin.get_page_context(self.queryset, page_number=2.7)
        
        # Should treat as page 2 (int conversion)
        self.assertEqual(context['page'].number, 2)
    
    def test_paginator_object_accessible(self):
        """Test that paginator object is accessible from context."""
        context = self.mixin.get_page_context(self.queryset, page_number=1)
        
        self.assertIsNotNone(context['paginator'])
        self.assertEqual(context['paginator'].count, 250)
        self.assertEqual(context['paginator'].num_pages, 3)
        self.assertEqual(context['paginator'].per_page, 100)
    
    def test_page_object_accessible(self):
        """Test that page object is accessible from context."""
        context = self.mixin.get_page_context(self.queryset, page_number=2)
        
        page_obj = context['page']
        self.assertIsNotNone(page_obj)
        self.assertEqual(page_obj.number, 2)
        self.assertEqual(len(page_obj.object_list), 100)
    
    def test_multiple_pages_all_accessible(self):
        """Test that all pages are accessible."""
        # Test pages 1, 2, 3
        for page_num in [1, 2, 3]:
            context = self.mixin.get_page_context(self.queryset, page_number=page_num)
            self.assertEqual(context['page'].number, page_num)
        
        # Page 4 doesn't exist, should return last page
        context = self.mixin.get_page_context(self.queryset, page_number=4)
        self.assertEqual(context['page'].number, 3)
    
    def test_acceptance_criteria_page_2_of_250_records(self):
        """
        Test acceptance criteria:
        GIVEN a QuerySet with 250 records and page_number=2,
        WHEN get_page_context is called,
        THEN it returns page 2 with records 101-200
        """
        queryset = list(range(1, 251))
        context = self.mixin.get_page_context(queryset, page_number=2)
        
        self.assertEqual(context['page'].number, 2)
        self.assertEqual(context['start_index'], 101)
        self.assertEqual(context['end_index'], 200)
        self.assertEqual(len(context['page'].object_list), 100)
    
    def test_acceptance_criteria_invalid_page_999(self):
        """
        Test acceptance criteria:
        GIVEN an invalid page number like 999,
        WHEN get_page_context is called,
        THEN it returns the last available page without error
        """
        queryset = list(range(1, 251))
        context = self.mixin.get_page_context(queryset, page_number=999)
        
        # Should return last page (page 3)
        self.assertEqual(context['page'].number, 3)
        # No error should be raised
        self.assertIsNotNone(context['page'].object_list)
    
    def test_acceptance_criteria_invalid_page_string(self):
        """
        Test acceptance criteria:
        GIVEN page_number='invalid',
        WHEN get_page_context is called,
        THEN it defaults to page 1
        """
        queryset = list(range(1, 251))
        context = self.mixin.get_page_context(queryset, page_number='invalid')
        
        self.assertEqual(context['page'].number, 1)
        self.assertEqual(context['start_index'], 1)
        self.assertEqual(context['end_index'], 100)


class TestPaginationMixinQuerySetCompatibility(TestCase):
    """Test PaginationMixin with real Django QuerySets."""
    
    def setUp(self):
        """Set up test fixtures."""
        from django.contrib.auth.models import User
        
        self.mixin = PaginationMixin()
        self.mixin.paginate_by = 10  # Small page size for testing
        
        # Create test users for queryset
        for i in range(1, 26):
            User.objects.create(username=f'user{i}', email=f'user{i}@example.com')
    
    def test_with_django_queryset(self):
        """Test PaginationMixin with real Django QuerySet."""
        from django.contrib.auth.models import User
        
        queryset = User.objects.all()
        context = self.mixin.get_page_context(queryset, page_number=1)
        
        self.assertEqual(context['page'].number, 1)
        self.assertEqual(context['start_index'], 1)
        self.assertEqual(context['end_index'], 10)
        self.assertTrue(context['is_paginated'])
    
    def test_queryset_pagination_consistency(self):
        """Test that QuerySet pagination is consistent."""
        from django.contrib.auth.models import User
        
        queryset = User.objects.all().order_by('id')
        
        # Get page 1
        context1 = self.mixin.get_page_context(queryset, page_number=1)
        records_page1 = list(context1['page'].object_list)
        
        # Get page 2
        context2 = self.mixin.get_page_context(queryset, page_number=2)
        records_page2 = list(context2['page'].object_list)
        
        # Records should be different
        self.assertNotEqual(records_page1[0].id, records_page2[0].id)
        
        # Total records
        total = context1['paginator'].count
        self.assertEqual(total, 25)
