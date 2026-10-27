"""Shared helpers for paginated, filterable list views."""

from urllib.parse import urlencode

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.utils.dateparse import parse_date

PAGE_SIZE = 100


class PaginationMixin:
    """
    Mixin for DRY pagination handling across all list views.
    
    Provides a single method get_page_context() that handles pagination logic,
    validation, and edge cases.
    """
    
    paginate_by = 100
    
    def get_page_context(self, queryset, page_number=None):
        """
        Generic pagination handler for Django QuerySets.
        
        Accepts a QuerySet and page number, returning pagination metadata and
        the paginated result set. Handles validation and edge cases gracefully.
        
        Args:
            queryset: Django QuerySet to paginate
            page_number: Optional page number (int, str, or None)
                        String page numbers are converted to int
                        Invalid values default to page 1
                        Out of range values return the last available page
        
        Returns:
            dict with keys:
                - 'page': Page object (django.core.paginator.Page)
                - 'paginator': Paginator object (django.core.paginator.Paginator)
                - 'is_paginated': Boolean indicating if there are multiple pages
                - 'has_previous': Boolean indicating if previous page exists
                - 'has_next': Boolean indicating if next page exists
                - 'start_index': 1-based start index of current page records
                - 'end_index': 1-based end index of current page records
        
        Preconditions:
            - queryset must be a valid Django QuerySet (not a list or tuple)
            - queryset must not already be sliced
        
        Postconditions:
            - Returns dict with all specified keys
            - Invalid page_number defaults to page 1
            - Out of range page_number returns last page
            - Page object contains page.object_list with correct records
            - start_index and end_index are 1-based inclusive bounds
        """
        # Create paginator with configured page size
        paginator = Paginator(queryset, self.paginate_by)
        
        # Handle page_number validation
        # Convert page_number to int if it's a string
        if isinstance(page_number, str):
            if not page_number.strip():
                page_number = 1
            else:
                try:
                    page_number = int(page_number)
                except ValueError:
                    # Non-numeric page numbers default to page 1
                    page_number = 1
        elif page_number is None:
            page_number = 1
        elif isinstance(page_number, float):
            # Convert float to int
            page_number = int(page_number)
        
        # Validate page number is positive
        if not isinstance(page_number, int) or page_number < 1:
            page_number = 1
        
        # Get the page object using get_page for graceful handling
        try:
            page_obj = paginator.page(page_number)
        except (EmptyPage, PageNotAnInteger):
            # For out of range, use last page
            page_obj = paginator.page(paginator.num_pages) if paginator.num_pages > 0 else paginator.page(1)
        
        return {
            'page': page_obj,
            'paginator': paginator,
            'is_paginated': page_obj.has_other_pages(),
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next(),
            'start_index': page_obj.start_index(),
            'end_index': page_obj.end_index(),
        }


def build_search_q(search_term, fields, *, date_fields=None, include_pk=True):
    """
    Build an OR Q() across text fields (icontains).

    When include_pk is True and the term is numeric, also match primary key.
    Date-looking terms also match exact values on date_fields.
    """
    term = (search_term or '').strip()
    if not term:
        return Q()

    query = Q()
    for field in fields:
        query |= Q(**{f'{field}__icontains': term})

    if include_pk and term.isdigit():
        query |= Q(pk=int(term))

    parsed = parse_date(term)
    if parsed is not None:
        for field in (date_fields or ()):
            query |= Q(**{field: parsed})

    return query


def paginate_queryset(queryset, page_number, per_page=PAGE_SIZE):
    """
    Paginate a queryset and build range labels like 1-100, 101-200.
    """
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(page_number)

    page_range_choices = []
    for num in paginator.page_range:
        start = (num - 1) * per_page + 1
        end = min(num * per_page, paginator.count)
        page_range_choices.append({'page': num, 'label': f'{start}-{end}'})

    return {
        'page_obj': page_obj,
        'paginator': paginator,
        'page_range_choices': page_range_choices,
        'is_paginated': page_obj.has_other_pages(),
    }


def filter_query_string(request, *exclude_keys):
    """Preserve current GET filters for pagination links (drops page by default)."""
    params = {}
    excluded = {'page', *exclude_keys}
    for key, value in request.GET.items():
        if key in excluded or value in (None, ''):
            continue
        params[key] = value
    return urlencode(params)


class QueryOptimizer:
    """
    Applies select_related() and prefetch_related() to QuerySets to eliminate N+1 query problems.
    
    Provides a single apply() method that takes a QuerySet and model name, then applies
    the appropriate optimizations for that model. Returns the optimized QuerySet.
    
    Preconditions:
    - queryset must be a valid Django QuerySet for the appropriate model
    - model_name must match one of the supported models (e.g., 'RESERVATION', 'FACILITY', 'MAINTENANCE')
    - The relationships defined in OPTIMIZATIONS must exist on the model
    
    Postconditions:
    - Returns the same QuerySet with select_related/prefetch_related applied
    - Does not slice or filter the QuerySet
    - QuerySet remains chainable for further filtering/ordering
    """
    
    # Define optimizations per model
    # These dictionaries map model names to their select_related and prefetch_related fields
    OPTIMIZATIONS = {
        'RESERVATION': {
            'select_related': ['facility', 'requested_by', 'reviewed_by'],
            'prefetch_related': []
        },
        'FACILITY': {
            'select_related': [],
            'prefetch_related': []
        },
        'MAINTENANCE': {
            'select_related': ['facility'],
            'prefetch_related': []
        }
    }
    
    @staticmethod
    def apply(queryset, model_name):
        """
        Apply optimizations to a QuerySet based on the model type.
        
        Args:
            queryset: Django QuerySet to optimize (must not be sliced)
            model_name: String identifying the model ('RESERVATION', 'FACILITY', 'MAINTENANCE')
        
        Returns:
            Optimized QuerySet with select_related/prefetch_related applied
            
        Raises:
            ValueError: If model_name is not in OPTIMIZATIONS dict
            
        Example:
            >>> from reservations.models import Reservation
            >>> qs = Reservation.objects.all()
            >>> optimized = QueryOptimizer.apply(qs, 'RESERVATION')
            >>> # Now each access to reservation.facility or reservation.requested_by
            >>> # will not trigger additional database queries
        """
        # Validate model name
        if model_name not in QueryOptimizer.OPTIMIZATIONS:
            raise ValueError(
                f"Unknown model: {model_name}. Must be one of: {list(QueryOptimizer.OPTIMIZATIONS.keys())}"
            )
        
        optimizations = QueryOptimizer.OPTIMIZATIONS[model_name]
        
        # Apply select_related for forward foreign keys
        select_related_fields = optimizations.get('select_related', [])
        if select_related_fields:
            queryset = queryset.select_related(*select_related_fields)
        
        # Apply prefetch_related for reverse relationships
        prefetch_related_fields = optimizations.get('prefetch_related', [])
        if prefetch_related_fields:
            queryset = queryset.prefetch_related(*prefetch_related_fields)
        
        return queryset


class FilterBuilder:
    """
    Constructs complex Django Q() objects for search and filter operations.
    
    Provides utility methods to build Q objects with proper validation for:
    - Multi-field search with OR logic
    - Status filtering with validation against model choices
    - Date range filtering with date parsing
    - Facility filtering with FK validation
    """
    
    @staticmethod
    def build_search_filter(search_term, search_fields):
        """
        Create Q() object for OR logic across multiple fields.
        
        Constructs a Q object that searches for the search_term across multiple
        fields using case-insensitive substring matching (icontains).
        
        Args:
            search_term: String to search for. If empty or None, returns empty Q().
            search_fields: List of model field names to search across.
                          Field names follow Django ORM convention (e.g., 'facility__name').
        
        Returns:
            django.db.models.Q object representing OR logic.
            Empty Q() if search_term is empty or search_fields is empty.
        
        Preconditions:
            - search_term should be a string or None
            - search_fields should be a list of valid model field names
            - All field names must follow Django ORM conventions
        
        Postconditions:
            - Returns Q object representing: Q(field1__icontains=term) | Q(field2__icontains=term) | ...
            - Search is case-insensitive (icontains)
            - Empty search_term returns empty Q()
            - Empty search_fields returns empty Q()
        
        Example:
            >>> q = FilterBuilder.build_search_filter('Building A', ['facility__name', 'purpose'])
            >>> # Returns: Q(facility__name__icontains='Building A') | Q(purpose__icontains='Building A')
        """
        search_term = (search_term or '').strip()
        if not search_term or not search_fields:
            return Q()
        
        query = Q()
        for field in search_fields:
            query |= Q(**{f'{field}__icontains': search_term})
        
        return query
    
    @staticmethod
    def build_status_filter(status, valid_statuses):
        """
        Create Q() object for status filtering with validation.
        
        Validates the provided status against valid_statuses before filtering.
        This prevents invalid statuses from being applied to queries.
        
        Args:
            status: Status value to filter by. If empty or None, returns empty Q().
            valid_statuses: List or tuple of valid status choices. Typically from
                          Model.Status.choices or similar enumeration.
                          Can be a list of tuples (value, label) or just values.
        
        Returns:
            django.db.models.Q object: Q(status=status) if valid, empty Q() if invalid.
        
        Raises:
            ValueError: If status is not empty and not in valid_statuses.
        
        Preconditions:
            - status should be a string or None
            - valid_statuses should be a list/tuple of valid choice values
        
        Postconditions:
            - Returns Q(status=status) if status is in valid_statuses
            - Returns empty Q() if status is empty/None
            - Raises ValueError if status is provided but not in valid_statuses
        
        Example:
            >>> valid = ['PENDING', 'APPROVED', 'REJECTED']
            >>> q = FilterBuilder.build_status_filter('PENDING', valid)
            >>> # Returns: Q(status='PENDING')
            
            >>> q = FilterBuilder.build_status_filter('', valid)
            >>> # Returns: Q()
            
            >>> q = FilterBuilder.build_status_filter('INVALID', valid)
            >>> # Raises ValueError
        """
        status = (status or '').strip()
        if not status:
            return Q()
        
        # Extract status values from choices if they're (value, label) tuples
        if valid_statuses and isinstance(valid_statuses[0], (list, tuple)):
            valid_values = [choice[0] for choice in valid_statuses]
        else:
            valid_values = list(valid_statuses)
        
        if status not in valid_values:
            raise ValueError(f"Invalid status: {status}. Must be one of: {valid_values}")
        
        return Q(status=status)
    
    @staticmethod
    def build_date_range_filter(start_date, end_date, date_field='reservation_date'):
        """
        Create Q() object for date range filtering with date parsing.
        
        Parses start_date and end_date strings to datetime.date objects,
        then constructs a Q object filtering records within the date range.
        
        Args:
            start_date: Date string (YYYY-MM-DD format) or date object.
                       If empty or None, no lower bound is applied.
            end_date: Date string (YYYY-MM-DD format) or date object.
                     If empty or None, no upper bound is applied.
            date_field: Name of the date field to filter on (default: 'reservation_date').
        
        Returns:
            django.db.models.Q object for date range filtering.
            Returns empty Q() if both dates are empty.
        
        Preconditions:
            - start_date and end_date should be strings (YYYY-MM-DD) or date objects
            - If strings, must be parseable by parse_date()
            - date_field must be a valid model field name
        
        Postconditions:
            - If only start_date provided: Q(field__gte=start_date)
            - If only end_date provided: Q(field__lte=end_date)
            - If both provided: Q(field__gte=start_date, field__lte=end_date)
            - Invalid date strings are ignored (date parsing returns None)
            - Returns empty Q() if both dates parse to None
        
        Example:
            >>> q = FilterBuilder.build_date_range_filter('2024-01-01', '2024-01-31')
            >>> # Returns: Q(reservation_date__gte=date(2024,1,1), reservation_date__lte=date(2024,1,31))
            
            >>> q = FilterBuilder.build_date_range_filter('2024-01-01', '')
            >>> # Returns: Q(reservation_date__gte=date(2024,1,1))
        """
        # Parse start_date if provided
        parsed_start = None
        if start_date:
            if isinstance(start_date, str):
                parsed_start = parse_date(start_date)
            else:
                parsed_start = start_date
        
        # Parse end_date if provided
        parsed_end = None
        if end_date:
            if isinstance(end_date, str):
                parsed_end = parse_date(end_date)
            else:
                parsed_end = end_date
        
        # Build query with parsed dates - only include non-empty conditions
        conditions = []
        if parsed_start:
            conditions.append(Q(**{f'{date_field}__gte': parsed_start}))
        if parsed_end:
            conditions.append(Q(**{f'{date_field}__lte': parsed_end}))
        
        # If no conditions, return empty Q()
        if not conditions:
            return Q()
        
        # Combine all conditions with AND
        query = conditions[0]
        for condition in conditions[1:]:
            query &= condition
        
        return query
    
    @staticmethod
    def build_facility_filter(facility_id):
        """
        Create Q() object for facility filtering with FK validation.
        
        Constructs a Q object to filter by facility_id. The facility_id is
        not validated against the database in this method; callers should
        validate that the facility exists if stricter validation is needed.
        
        Args:
            facility_id: Facility ID (typically an int) to filter by.
                        If empty, None, or '0', returns empty Q().
                        Can be a string or int.
        
        Returns:
            django.db.models.Q object: Q(facility_id=facility_id) if valid.
                                      Empty Q() if facility_id is empty/None/'0'.
        
        Preconditions:
            - facility_id should be convertible to int (string or int type)
            - No database validation is performed
        
        Postconditions:
            - Returns Q(facility_id=facility_id) if facility_id is non-empty and > 0
            - Returns empty Q() if facility_id is None, empty string, or '0'
            - Invalid numeric strings are treated as empty (return empty Q())
        
        Example:
            >>> q = FilterBuilder.build_facility_filter(123)
            >>> # Returns: Q(facility_id=123)
            
            >>> q = FilterBuilder.build_facility_filter('456')
            >>> # Returns: Q(facility_id=456)
            
            >>> q = FilterBuilder.build_facility_filter('')
            >>> # Returns: Q()
        """
        # Handle None and empty string
        if not facility_id:
            return Q()
        
        # Convert string to int if needed
        try:
            fac_id = int(facility_id)
            if fac_id <= 0:
                return Q()
            return Q(facility_id=fac_id)
        except (ValueError, TypeError):
            # Invalid facility_id format
            return Q()
