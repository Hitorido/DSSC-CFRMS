# Implementation Plan: List Pagination and Filtering

## Overview

This implementation plan breaks down the pagination and filtering feature into 13 logical tasks following a phased approach. Utilities are built first (Phase 1), then integrated into views (Phase 2), followed by UI templating (Phase 3), and finally testing and documentation (Phase 4).

The feature spans multiple Django apps (reservations, facilities) and introduces shared utilities for pagination, filtering, and query optimization that reduce code duplication and ensure consistency.

## Tasks

- [x] 1. Create PaginationMixin Utility Class
  - Implement reusable pagination handler for all list views
  - Methods: get_page_context(queryset, page_number=None)
  - Returns dict with paginator, page_obj, is_paginated, has_prev, has_next, start_index, end_index
  - Handle edge cases: invalid page numbers default to 1 or last page
  - Unit tests: valid pages, invalid input, empty querysets
  - Add to config/utils.py or reservations/utils.py

- [x] 2. Create FilterBuilder Utility Class
  - Implement filter construction utilities for search and filtering
  - Methods: build_search_filter(search_term, search_fields) → Q object with OR logic
  - Methods: build_status_filter(status, valid_statuses) → Q object with validation
  - Methods: build_date_range_filter(start_date, end_date) → Q object with date parsing
  - Methods: build_facility_filter(facility_id) → Q object with FK validation
  - Unit tests: valid/invalid input, empty values, special characters (SQL injection prevention)
  - Add to config/utils.py or reservations/utils.py

- [x] 3. Create QueryOptimizer Utility Class
  - Implement query optimization helper for N+1 elimination
  - Methods: apply(queryset, model_name) → optimized QuerySet
  - Optimizations dict with select_related/prefetch_related per model
  - Reservation: select_related=['facility', 'requested_by', 'reviewed_by']
  - Integration tests: verify query count is exactly 2 (count + fetch), not N+1
  - Add to config/utils.py or reservations/utils.py

- [x] 4. Update my_reservations_view with Pagination and Filtering
  - Parse URL query params: page, search, status
  - Apply QueryOptimizer, FilterBuilder, get_page_context
  - Build filter_params string for template URL preservation
  - Update my_reservations.html: add search box, status filter, pagination controls, metadata
  - Integration tests: filters work, URL params preserved, search functionality
  - Edge cases: invalid page → last page, empty results → show message

- [x] 5. Update pending_reservations_view with Pagination and Filtering
  - Parse URL query params: page, search, status
  - Base queryset defaults to PENDING status (configurable)
  - Apply optimizations and filters
  - Update pending_reservations.html: add search, status filter, pagination
  - Search fields: reservation_date, facility name, requester name
  - Integration tests: filters work, search works, state preserved
  - Edge cases: invalid page, empty results

- [x] 6. Update reservation_report_view with Pagination and Filtering
  - Parse URL query params: page, search, status, start_date, end_date, facility_id
  - Support comprehensive filtering: status, date range, facility
  - Update reservation_report.html: collapsible filter panel, search, dropdowns, date inputs
  - Filter panel shows badge with active filter count
  - Integration tests: all filter combinations, URL preservation, pagination
  - Edge cases: invalid dates, empty results, all filters combined

- [x] 7. Implement Pagination and Filtering for maintenance_list_view
  - Parse URL query params: page, search
  - Apply QueryOptimizer (select_related=['facility'])
  - Search fields: facility name, maintenance_date
  - Update maintenance template: add search box, pagination controls, metadata
  - Integration tests: search works, pagination works, state preserved
  - Edge cases: invalid page, empty results

- [x] 8. Implement Pagination and Filtering for facility_list_view
  - Parse URL query params: page, search, status
  - Apply QueryOptimizer to base queryset
  - Search fields: facility name, building_name
  - Update facility template: add search box, status filter, pagination controls
  - Integration tests: search, status filter, pagination, combined filters
  - Edge cases: invalid page, empty results

- [x] 9. Add Template Helper for Filter State Preservation
  - Create Django template filter: urlencode_filters (alternative: Python context helper)
  - Accept dict of filters, filter empty values, URL-encode remaining
  - Example: {'status': 'PENDING', 'search': ''} → "status=PENDING"
  - Unit tests: empty values filtered, special characters encoded
  - Used in all pagination link URLs to preserve state

- [-] 10. Write Integration and Property-Based Tests for Pagination Feature
  - Integration tests: pagination, search, filters, combined filters across all views
  - Filter state preservation tests: navigate pages, verify filters in URL
  - Edge case tests: invalid pages, empty results, clearing filters
  - Property-based tests (hypothesis):
    - Property 1: Pagination preserves record ordering
    - Property 2: Filters reduce or maintain count
    - Property 3: Search consistency (idempotent)
    - Property 4: URL state round-trip (encode/decode restore filters)
    - Property 5: Query count bounded (max 2-3 queries, not N+1)
    - Property 6: Invalid pages handled gracefully
    - Property 7: Search resets pagination to page 1
    - Property 8: Empty results display message
  - Performance tests: verify < 1 second for 10,000 records with filters

- [ ] 11. Update Reservation Templates with Pagination UI
  - my_reservations.html: search box, status filter, pagination, metadata, no-results message
  - pending_reservations.html: search box, status filter, pagination, metadata, no-results message
  - reservation_report.html: collapsible filter panel, search, status, dates, facility, pagination
  - Use Bootstrap 5 classes: .pagination, .page-item, .page-link, .collapse, data-bs-toggle
  - Ensure accessibility: semantic HTML, <nav>, ARIA labels
  - Ensure mobile responsiveness: filter panel collapses on small screens
  - Preserve filter params in all pagination links

- [ ] 12. Update Facility and Maintenance Templates with Pagination UI
  - maintenance_list.html: search box, pagination controls, metadata, no-results message
  - facility_list.html: search box, status filter, pagination controls, metadata, no-results message
  - Use Bootstrap 5 classes for consistent styling
  - Ensure accessibility and mobile responsiveness
  - Preserve filter state in pagination links

- [ ] 13. Documentation and Examples
  - Create docs/PAGINATION_FILTERING.md: overview, user guide, filter state, examples with screenshots
  - Create docs/DEVELOPERS_PAGINATION.md: architecture, how-to add pagination, API reference, pitfalls, performance tips
  - Create docs/TESTING_PAGINATION.md: testing approach, property-based testing, example tests, performance testing
  - Update README.md with link to pagination documentation

## Task Dependency Graph

```json
{
  "waves": [
    {
      "wave": 1,
      "title": "Utilities - Parallel Execution",
      "tasks": ["1", "2", "3"],
      "description": "Build shared pagination, filtering, and query optimization utilities"
    },
    {
      "wave": 2,
      "title": "View Integration",
      "tasks": ["4", "5", "6", "7", "8"],
      "description": "Integrate utilities into all list views (reservation, facility, maintenance)",
      "dependencies": ["1", "2", "3"]
    },
    {
      "wave": 3,
      "title": "UI and Templates",
      "tasks": ["9", "11", "12"],
      "description": "Add template helpers and update UI with pagination controls",
      "dependencies": ["4", "5", "6", "7", "8"]
    },
    {
      "wave": 4,
      "title": "Testing and Documentation",
      "tasks": ["10", "13"],
      "description": "Comprehensive testing and user/developer documentation",
      "dependencies": ["9", "11", "12"]
    }
  ],
  "taskDependencies": {
    "1": [],
    "2": [],
    "3": [],
    "4": ["1", "2", "3"],
    "5": ["1", "2", "3"],
    "6": ["1", "2", "3"],
    "7": ["1", "2", "3"],
    "8": ["1", "2", "3"],
    "9": [],
    "10": ["4", "5", "6", "7", "8"],
    "11": ["4", "5", "6"],
    "12": ["7", "8"],
    "13": ["10", "11", "12"]
  }
}
```

## Notes

### Implementation Strategy

1. **Build Utilities First**: Tasks 1-3 are independent and provide the foundation for all view changes. Can be developed and tested in isolation.

2. **Parallel View Implementation**: Tasks 4-8 are largely independent (each targets a different view). After Phase 1, these can be parallelized.

3. **Template and Testing**: Tasks 9-13 depend on earlier phases but can begin once views are ready.

4. **Incremental Integration**: Each task should be tested individually before moving to the next phase. Property-based tests in Task 10 provide comprehensive validation.

### Testing Approach

- **Unit Tests**: For utilities (Tasks 1-3) and template helpers (Task 9)
- **Integration Tests**: For each view (Tasks 4-8) testing filters, pagination, search
- **Property-Based Tests**: Comprehensive correctness properties (Task 10)
- **Performance Tests**: Verify SLA (< 1 second) for large datasets

### Performance Considerations

- **Query Optimization**: select_related/prefetch_related eliminate N+1 (Task 3)
- **Pagination**: LIMIT/OFFSET fetches only current page (Task 1)
- **Target SLA**: < 1 second response time for 10,000 records with filters applied
- **Query Count**: Exactly 2 queries per paginated view (count + page fetch)

### Security Considerations

- **Input Validation**: All filters validated against model choices
- **Parameterized Queries**: All ORM queries use parameterized lookups (safe from SQL injection)
- **Permission Decorators**: Each view maintains existing permission checks (@login_required, @permission_required)

### Estimated Effort

- Phase 1: 8-10 hours
- Phase 2: 20-25 hours
- Phase 3: 8-10 hours
- Phase 4: 5-8 hours
- **Total: 40-50 hours**

### Success Criteria

- [ ] All 13 tasks completed
- [ ] Property-based tests pass (correctness properties validated)
- [ ] Response time < 1 second for 10,000 records
- [ ] Query count exactly 2 (no N+1)
- [ ] Edge cases handled without errors
- [ ] UI is accessible and responsive
- [ ] Documentation is clear and complete
