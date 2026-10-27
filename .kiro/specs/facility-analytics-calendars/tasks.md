# Implementation Plan: Facility Analytics, Enhanced Calendars & Predictive Analytics

## Overview

This implementation plan delivers comprehensive facility analytics and calendar enhancements across requestor, staff, and admin dashboards. It follows a phased approach: database enhancements, mock data generation, feature implementation, and testing.

## Tasks

- [x] 1. Extend Facility Model with Enhanced Details
  - Add fields: equipment_list, hours_of_operation, noise_level, floor_number, building_code, has_wheelchair_access
  - Create database migration
  - Update Facility admin to allow editing new fields
  - Add computed property: avg_reservation_duration
  - Ensure backward compatibility (all new fields optional)
  - Validate input (equipment_list non-empty if critical)
  - Write unit tests for new fields and validation
  - Test that existing facilities work without new fields

- [x] 2. Generate Enhanced Mock Data with Realistic Patterns
  - Create management command: generate_analytics_data
  - Generate 6 months backward + 3 months forward synthetic reservations
  - Implement realistic booking patterns:
    - 80% weekday bookings, 20% weekend
    - Peak hours 2-5pm (70% of bookings)
    - Natural cancellation rate (~10%)
    - Equipment-dependent variation
  - Assign equipment realistically to facility types
  - Mark all records with is_synthetic=True
  - Generate 10+ synthetic facilities with varied attributes
  - Create 50+ synthetic requesters for realistic requester names
  - Write integration tests validating data patterns
  - Test data volume and performance (1000+ reservations)

- [x] 3. Implement Color-Coded Facility Booking Calendar
  - Create facility booking view: GET /facilities/<id>/book-calendar/
  - Compute daily occupancy % for facility
  - Map to colors: GREEN (0-33%), YELLOW (34-66%), RED (67-100%), GRAY (unavailable)
  - Build calendar grid with color-coded days
  - Implement hover tooltip showing day's reservations
  - Display tooltip with: time slots, requester (if visible), status
  - Template: facilities/book_calendar.html with calendar grid
  - Style with Bootstrap cards and custom CSS
  - Add previous/next month navigation
  - Write integration tests for color-coding logic
  - Write UI tests for tooltip display
  - Test edge cases: no reservations, fully booked day, unavailable facility

- [x] 4. Enhance Tooltips to Include Maintenance Records
  - Update tooltip rendering to show BOTH reservations and maintenance
  - Query FacilityMaintenance records for the day in addition to Reservations
  - Display maintenance records with: title, times, status
  - Visually distinguish maintenance from reservations (icon, color, section header)
  - Highlight SCHEDULED maintenance differently from COMPLETED/CANCELLED
  - Apply to both requestor booking calendar and admin/staff calendars
  - Template logic: include maintenance data in calendar context
  - JavaScript: render maintenance items in tooltip alongside reservations
  - Test with days having both reservations and maintenance
  - Test with days having only maintenance, only reservations, neither

- [x] 5. Implement Predictive Analytics Engine
  - Create analytics service: analytics.services.PredictiveAnalytics
  - Method: compute_demand_forecast(months=6, forecast_periods=3)
    - Analyze historical reservations (last 6 months)
    - Compute monthly trends and aggregates
    - Apply simple linear trend or moving average
    - Extrapolate 3 months forward
    - Returns: historical_data, forecast_data, confidence
  - Method: compute_peak_hours(reservations)
    - Analyze which hours have highest booking volume
    - Return top 3 peak hours with booking counts
  - Method: compute_peak_days(reservations)
    - Analyze which days of week have highest bookings
    - Return all 7 days ranked by booking count
  - Method: compute_occupancy_by_facility(date_range)
    - Calculate occupancy % for each facility over range
    - Return facilities sorted by occupancy (high to low)
  - Caching: Use Django cache with 1-hour TTL
  - Write unit tests for each method
  - Test with synthetic data (verify forecast trends)
  - Verify cache invalidation logic
  - Test performance (compute analytics < 5 seconds)

- [x] 6. Implement Prescriptive Analytics Engine
  - Create recommendations service: analytics.services.PrescriptiveAnalytics
  - Method: generate_recommendations(analytics_data)
    - Based on predictive analytics, generate 4-6 recommendations
    - Recommendation object: {priority, title, description, action, impact}
  - Recommendation logic:
    - High occupancy facilities (>80%): suggest capacity expansion
    - Low-occupancy hours: suggest maintenance windows
    - Peak days: suggest extended hours
    - Heavy equipment usage (>85%): suggest maintenance alerts
    - Seasonal patterns: note trends in UI
  - Prioritize recommendations: high > medium > low
  - Cache recommendations with analytics (1-hour TTL)
  - Write unit tests for each recommendation type
  - Test with synthetic data (verify realistic recommendations)
  - Test edge cases: empty data, single facility, no patterns

- [x] 7. Update Admin Dashboard Template with Analytics Display
  - Add "Analytics Overview" card showing:
    - Total reservations (system-wide)
    - Avg occupancy % (all facilities)
    - Peak facility (highest bookings)
    - Top-booked time slot
  - Add "Demand Forecast" section with Chart.js visualization:
    - Line chart: historical vs forecast
    - X-axis: months, Y-axis: reservation count
    - Clearly distinguish historical (solid) vs forecast (dashed)
  - Add "System Reservations Calendar" section (from Task 4)
  - Add "Recommendations" section with prioritized cards
  - Each recommendation shows: title, description, action, impact, priority badge
  - Include data-freshness indicator ("Last updated 5 minutes ago")
  - Add note if using synthetic data: "Displaying synthetic data for demonstration"
  - Template: accounts/admin_dashboard.html (extend home.html)
  - Write integration tests for dashboard rendering
  - Test chart data accuracy
  - Test data switching (synthetic when no operational data)

- [x] 8. Update Staff Dashboard Template with Analytics Display
  - Add "Today's Operations" card showing:
    - Today's reservation count
    - Busiest facility (today)
    - Next 3 hours occupancy preview
  - Add "Assigned Facility Alerts" section:
    - Equipment maintenance due
    - Fully booked hours (today/tomorrow)
    - Upcoming maintenance windows
  - Add "Peak Hours This Week" mini-chart
  - Add "Facility-Specific Recommendations" (filtered to assigned facilities)
  - Focus on operational (today/tomorrow/this week) vs strategic trends
  - Template: accounts/staff_dashboard.html (extend home.html)
  - Write integration tests for staff-specific data
  - Test role-based data filtering (only relevant facilities)

- [x] 9. Create Analytics API Endpoints
  - Endpoint: GET /api/analytics/demand-forecast/
    - Returns: {historical: [...], forecast: [...], confidence: [...]}
    - Query params: ?months=6&facility_id=5 (optional filters)
  - Endpoint: GET /api/analytics/peak-hours/
    - Returns: [{hour: 14, count: 120}, {hour: 15, count: 115}, ...]
  - Endpoint: GET /api/analytics/occupancy-by-facility/
    - Returns: [{facility: 'Lab 1', occupancy: 0.85}, ...]
  - Endpoint: GET /api/analytics/recommendations/
    - Returns: [{priority, title, description, ...}, ...]
  - Endpoint: GET /api/analytics/system-calendar/?month=2024-12
    - Returns: calendar data for system-wide view
  - All endpoints require authentication (staff/admin role check)
  - Write API tests for each endpoint
  - Test permission checks
  - Test response formats and data accuracy

- [x] 10. Migrate Facility Data to Add New Fields
  - Create Django migration: facilities/migrations/000X_add_facility_details.py
  - Migration adds: equipment_list, hours_of_operation, noise_level, floor_number, building_code, has_wheelchair_access
  - Set reasonable defaults:
    - equipment_list: '' (empty)
    - hours_of_operation: '8am-6pm' (default hours)
    - noise_level: 'low' (conservative default)
    - floor_number: NULL (optional)
    - building_code: '' (empty)
    - has_wheelchair_access: True (assume accessible by default)
  - Test migration on real schema
  - Verify no data loss (backward compatible)
  - Test rollback/forward-again scenarios

- [x] 11. Update Facility Admin Interface
  - Update FacilityAdmin to include new fields in fieldsets:
    - Fieldset "Details": name, location, capacity, facility_type
    - Fieldset "Equipment & Amenities": equipment_list, noise_level, has_wheelchair_access
    - Fieldset "Location": floor_number, building_code, hours_of_operation
    - Fieldset "Status": status, is_synthetic
  - Add help text for each field
  - Add read-only avg_reservation_duration (computed display)
  - Add list_display to show: name, capacity, equipment (truncated), status
  - Test admin CRUD operations
  - Test form validation
  - Test that old facilities display correctly (backward compatible)

- [x] 12. Implement Facility Booking Calendar with Tooltips
  - View: reservations.views.book_facility_calendar_view
    - GET /facilities/<id>/book/calendar/ 
    - Load facility, validate user role
    - Query reservations AND maintenance for month
    - Compute occupancy per day (only reservations, not maintenance)
    - Return calendar context with color-coding
  - Template: reservations/facility_calendar.html
    - Display calendar grid with color-coded days (based on reservation occupancy)
    - Include tooltip data for both reservations and maintenance
    - Implement hover tooltips (JavaScript)
    - Show previous/next month navigation
    - Include facility details (capacity, equipment, accessibility)
  - CSS: Bootstrap + custom styling for colors
  - JavaScript: Tooltip rendering on hover, distinguish reservations vs maintenance
  - Write integration tests
  - Test with mock data (verify colors and tooltip content)
  - Test navigation and tooltip rendering with maintenance records

- [x] 13. Implement Analytics Caching & Cache Invalidation
  - Create cache keys: ANALYTICS_DEMAND_FORECAST, ANALYTICS_RECOMMENDATIONS, etc.
  - TTL: 1 hour for all analytics
  - Cache invalidation triggers:
    - When reservation status changes (created, approved, rejected)
    - Nightly refresh at midnight
    - Manual flush endpoint for admins
  - Implement: Use Django cache framework (Redis or database)
  - Add cache utility: analytics.utils.invalidate_analytics_cache()
  - Call cache invalidation in Reservation.save() when status changes
  - Write tests for cache hit/miss
  - Test TTL expiration
  - Test manual cache flush

- [x] 14. Write Comprehensive Tests for Analytics Features
  - Unit tests (analytics/tests/test_predictive.py):
    - Test demand forecast computation
    - Test peak hours detection
    - Test occupancy calculations
  - Unit tests (analytics/tests/test_prescriptive.py):
    - Test each recommendation type generation
    - Test priority sorting
  - Integration tests (accounts/tests/test_analytics_dashboard.py):
    - Test dashboard rendering with real data
    - Test synthetic data fallback
    - Test chart data accuracy
  - Integration tests (reservations/tests/test_facility_calendar.py):
    - Test color-coding logic
    - Test tooltip data
  - API tests (analytics/tests/test_api.py):
    - Test all endpoints
    - Test permission checks
  - Property-based tests (using hypothesis):
    - Property 1: Occupancy % always in [0, 1]
    - Property 2: Forecast never negative
    - Property 3: Peak hours always in [0, 23]
  - Performance tests (analytics/tests/test_performance.py):
    - Forecast computation < 5 seconds
    - Dashboard render < 2 seconds
    - Calendar load < 500ms
  - Test coverage target: >= 85% for analytics module

- [x] 15. Update Existing Views to Maintain Backward Compatibility
  - Verify home_view works with new facility fields
  - Verify existing reservation workflows unchanged
  - Verify my_reservations view unchanged
  - Verify pending_reservations view unchanged
  - Verify facility list view still works
  - Run full regression test suite
  - Manual testing: create reservation, approve, complete
  - Test across all user roles (requestor, staff, faculty, admin)

- [x] 16. Documentation & User Guide
  - Create docs/ANALYTICS_GUIDE.md:
    - Overview of analytics features
    - How to interpret charts and recommendations
    - How to use facility booking calendar
  - Create docs/ADMIN_ANALYTICS.md:
    - Admin guide to analytics dashboard
    - How to interpret recommendations
    - How to flush cache
  - Create docs/MOCK_DATA.md:
    - How to generate mock data
    - Data volume and performance implications
    - How to regenerate if needed
  - Update README.md with analytics feature description
  - Add in-app help text / tooltips
  - Create short video walkthrough (optional)

- [x] 17. Performance Optimization & Database Indexes
  - Add indexes: (facility, reservation_date, status), (reservation_date, status), (created_at)
  - Add indexes: (noise_level, capacity), (building_code, floor_number) on Facility
  - Run EXPLAIN ANALYZE on key analytics queries
  - Benchmark with 5000+ reservations
  - Optimize queries using select_related, prefetch_related
  - Profile analytics computation (identify bottlenecks)
  - Optimize if any query exceeds target SLA
  - Write performance regression tests
  - Monitor in production for slow queries

- [x] 18. Deployment & Final Validation
  - Run full test suite (target: all tests pass)
  - Test database migrations on staging
  - Manual testing of all features
  - Verify no breaking changes to existing features
  - Load test with synthetic data (5000+ reservations)
  - Check responsive design on mobile/tablet
  - Verify accessibility (WCAG compliance check)
  - Security review: verify permission checks, input validation
  - Deploy to production
  - Monitor error logs and performance metrics
  - Document deployment notes and known issues

## Task Dependency Graph

```json
{
  "waves": [
    {
      "wave": 1,
      "title": "Data Model & Mock Data",
      "tasks": ["1", "2"],
      "description": "Extend Facility model and generate realistic mock data"
    },
    {
      "wave": 2,
      "title": "Analytics Engines",
      "tasks": ["5", "6", "13"],
      "description": "Build predictive and prescriptive analytics with caching",
      "dependencies": ["1", "2"]
    },
    {
      "wave": 3,
      "title": "Calendar & Tooltip Features",
      "tasks": ["3", "4", "12"],
      "description": "Implement facility calendars with rich tooltips showing reservations and maintenance",
      "dependencies": ["1", "2"]
    },
    {
      "wave": 4,
      "title": "Dashboard Integration",
      "tasks": ["7", "8"],
      "description": "Add analytics display to admin and staff dashboards",
      "dependencies": ["5", "6", "3"]
    },
    {
      "wave": 5,
      "title": "Backend Support",
      "tasks": ["9", "10", "11"],
      "description": "API, database migration, admin interface",
      "dependencies": ["1", "2"]
    },
    {
      "wave": 6,
      "title": "Testing & Optimization",
      "tasks": ["14", "15", "17"],
      "description": "Comprehensive testing and performance tuning",
      "dependencies": ["3", "7", "8", "9"]
    },
    {
      "wave": 7,
      "title": "Documentation & Deployment",
      "tasks": ["16", "18"],
      "description": "Final documentation and production deployment",
      "dependencies": ["14", "15", "17"]
    }
  ],
  "taskDependencies": {
    "1": [],
    "2": ["1"],
    "3": ["1", "2"],
    "4": ["1", "2"],
    "5": ["1", "2"],
    "6": ["5"],
    "7": ["5", "6", "3"],
    "8": ["5", "6", "3"],
    "9": ["5", "6"],
    "10": ["1"],
    "11": ["1", "10"],
    "12": ["3", "4"],
    "13": ["5", "6"],
    "14": ["3", "4", "5", "6", "7", "8", "9"],
    "15": ["3", "4", "7", "8"],
    "16": ["5", "6", "7", "8"],
    "17": ["14"],
    "18": ["14", "15", "17"]
  }
}
```

## Notes

### Implementation Strategy

1. **Phase 1 (Data)**: Extend models and generate mock data — foundation for everything else
2. **Phase 2 (Analytics)**: Build predictive/prescriptive engines — powers all features
3. **Phase 3 (UI)**: Implement calendars and dashboards — user-facing features
4. **Phase 4 (Support)**: APIs, migrations, admin — enabling infrastructure
5. **Phase 5 (Quality)**: Testing, optimization, docs — production readiness

### Testing Approach

- Unit tests for analytics algorithms (deterministic, testable)
- Integration tests for views and APIs
- Property-based tests for correctness properties
- Performance tests with 5000+ mock reservations
- Full regression suite to verify backward compatibility

### Performance Targets

- Facility calendar load: < 500ms
- System calendar load: < 1 second
- Analytics computation: < 5 seconds (cached, TTL 1 hour)
- Dashboard render: < 2 seconds total
- API responses: < 500ms

### Data Strategy

- Synthetic data clearly marked with `is_synthetic=True`
- Mock data optional (system works without it)
- Analytics intelligently falls back to synthetic when operational data insufficient
- Can regenerate mock data anytime without affecting real data

### Security & Permissions

- Requestors see only their own reservations in tooltips/calendars
- Staff see all reservations + assigned facility details
- Admins see everything + system-wide analytics
- All permission checks enforced in views and APIs
- Input validation on all user-provided parameters

### Backward Compatibility

- All new Facility fields optional (defaults provided)
- Existing views unmodified (only home_view extended)
- All existing workflows (create, approve, reject, complete) work identically
- Migration is non-destructive (additive only)
- Old data continues to work without new fields populated

### Success Criteria

- [x] All 18 tasks completed
- [x] Test suite passes (>85% coverage)
- [x] No breaking changes to existing features
- [x] Analytics computation meets SLA (<5 seconds)
- [x] Dashboard responsive and accessible
- [x] Documentation complete
- [x] Mock data generates realistically
- [x] Recommendations are actionable
- [x] Color-coding displays correctly
- [x] System-wide calendar shows all reservations
