# Requirements Document: Facility Analytics, Enhanced Calendars & Predictive Analytics

## Introduction

This enhancement brings comprehensive analytics and improved calendar views to the DSSC CFRMS, enabling requestors to see facility availability at a glance, staff/admins to monitor system-wide activity, and data-driven recommendations for facility management. The system uses mock data for realistic analytics showcase without requiring real historical data.

## Glossary

- **System**: DSSC CFRMS (Facility Reservation Management System)
- **Requestor**: Student or faculty member requesting facility reservations
- **Reviewer**: Staff, faculty, or admin who reviews and approves/declines reservations
- **Admin**: System administrator with full management capabilities
- **Facility Availability**: Color-coded indicator (green/yellow/red) showing how booked a facility is on a given day
- **Predictive Analytics**: Forecasts of future demand patterns, equipment risk, and occupancy trends
- **Prescriptive Analytics**: Actionable recommendations based on historical patterns and predictions
- **Mock Data**: Synthetic data generated to showcase analytics without real data
- **Occupancy Rate**: Percentage of available time slots booked on a facility for a given day
- **Peak Hours**: Times of day when facility bookings are highest
- **Equipment Risk**: Predicted probability of equipment failure based on usage patterns

## Requirements

### Requirement 1: Color-Coded Facility Availability on Booking Calendar

**User Story:** As a requestor, I want to see color-coded availability indicators on the facility booking calendar so I can quickly identify which facilities are packed, partially available, or open on any given day.

#### Acceptance Criteria

1. WHEN the "Book a Facility" view displays a calendar, THE System SHALL color-code each day per facility based on occupancy:
   - GREEN (Low occupancy): 0-33% of available time slots are booked
   - YELLOW (Medium occupancy): 34-66% of available time slots are booked
   - RED (High occupancy): 67-100% of available time slots are booked
2. WHEN a requestor hovers over a day number in the calendar, THE System SHALL display a tooltip showing all reservations scheduled for that day and facility
3. WHEN the tooltip is displayed, THE System SHALL show: facility name, reservation times, requester names (if visible), and reservation status
4. WHEN no reservations exist for a day, THE System SHALL display the color-code as GREEN and show "No reservations" in the tooltip
5. WHEN a facility's status is not AVAILABLE, THE System SHALL display it with a GRAY indicator regardless of reservation count

### Requirement 2: Enhance Tooltips with Maintenance Information

**User Story:** As a staff or admin user, I want hover tooltips on calendar days to show both reservations AND maintenance records so I have complete visibility of facility occupancy and downtime.

#### Acceptance Criteria

1. WHEN a user hovers over a day in any reservation calendar (requestor or admin/staff), THE System SHALL display a tooltip showing:
   - All reservations for that day (times, requesters, status)
   - All maintenance windows for that day (times, titles, status)
2. WHEN both reservations and maintenance exist on a day, THE System SHALL clearly distinguish them (e.g., different icons, colors, or sections)
3. WHEN no reservations or maintenance exist for a day, THE System SHALL display "No events" in the tooltip
4. WHEN hovering, maintenance records marked as SCHEDULED SHALL be highlighted differently from COMPLETED or CANCELLED
5. WHEN tooltip shows maintenance, THE System SHALL include: maintenance title, times, and status

### Requirement 3: Predictive Analytics - Demand Forecasting

**User Story:** As an admin or staff member, I want to see predicted demand trends so I can plan facility maintenance and understand peak usage periods.

#### Acceptance Criteria

1. WHEN a staff or admin views their dashboard, THE System SHALL display "Predictive Analytics" charts including:
   - Monthly demand forecast (next 3 months)
   - Peak hour predictions (busiest times of day)
   - Facility-specific demand trends
2. WHEN viewing demand forecasts, THE System SHALL show:
   - Historical booking volume (last 6 months of synthetic data)
   - Predicted booking volume (next 3 months extrapolated)
   - Confidence intervals or uncertainty ranges
   - Trend direction (increasing, stable, decreasing)
3. WHEN demand is predicted to be high, THE System SHALL highlight facilities at risk of over-booking
4. WHEN the system detects seasonal patterns, THE System SHALL note them (e.g., "Peak demand on Mondays and Tuesdays")

### Requirement 4: Prescriptive Analytics - Actionable Recommendations

**User Story:** As an admin or staff member, I want system-generated recommendations so I can make data-driven facility management decisions.

#### Acceptance Criteria

1. WHEN viewing the analytics dashboard, THE System SHALL display "Recommendations" section with suggestions such as:
   - "Schedule maintenance during low-occupancy periods (e.g., Fridays 5-7pm)"
   - "Consider adding capacity to [Facility Name] — occupancy is 85%+ on most days"
   - "Peak demand for [Facility Type] is 2-5pm — consider extending availability"
   - "Equipment in [Facility] is used 90%+ of operating hours — prioritize maintenance checks"
2. WHEN a recommendation is displayed, THE System SHALL include:
   - A priority level (high, medium, low)
   - The data basis for the recommendation
   - Suggested action steps
   - Projected impact if implemented
3. WHEN users click on a recommendation, THE System SHALL provide detailed analysis and historical context

### Requirement 5: Enhanced Facility Model with Equipment & Capacity Details

**User Story:** As a developer, I want the facility model to capture rich details so that analytics can provide sophisticated insights about equipment usage and capacity planning.

#### Acceptance Criteria

1. THE System SHALL extend the Facility model with additional fields:
   - `equipment_list` (TextField): Comma-separated list of equipment (projector, whiteboard, A/C, etc.)
   - `hours_of_operation` (CharField): e.g., "8am-6pm weekdays, 9am-5pm weekends"
   - `noise_level` (CharField): e.g., "silent", "low", "medium", "high" — for recommendation filtering
   - `floor_number` (IntegerField): Building floor location
   - `building_code` (CharField): Building identifier
   - `has_wheelchair_access` (BooleanField): Accessibility indicator
   - `avg_reservation_duration` (DurationField): Computed dynamically from reservations
2. WHEN a new facility is created or edited, THE System SHALL:
   - Allow entry of all enhanced detail fields
   - Validate equipment list (non-empty if needed)
   - Preserve backward compatibility (all new fields are optional)
3. WHEN displaying facility details to requestors, THE System SHALL highlight relevant attributes (capacity, equipment, accessibility)
4. WHEN analytics are generated, THE System SHALL use enhanced details to create facility-specific recommendations

### Requirement 6: Improve Mock Data for Analytics Showcase

**User Story:** As a developer, I want realistic mock data so that analytics features can be demonstrated effectively without waiting for real usage history to accumulate.

#### Acceptance Criteria

1. THE System SHALL generate synthetic reservation data with realistic patterns:
   - Peak booking times: Monday-Thursday 2-5pm, off-peak: Friday evenings, weekends
   - Varying facility popularity based on capacity and equipment
   - Seasonal variations (more bookings on weekdays, fewer on weekends)
   - Equipment-dependent bookings (computer labs busier than conference rooms)
   - Natural "no-show" patterns (5-10% cancellation rate)
2. THE System SHALL generate synthetic data with date ranges spanning at least 6 months backward (for historical trends) and 3 months forward (for forecast validation)
3. THE System SHALL assign equipment realistically:
   - Computer labs: projectors, A/C, computers
   - Classrooms: projectors, whiteboards
   - Auditoriums: sound system, projectors, lighting
   - Conference rooms: projectors, whiteboards
4. WHEN synthetic data is generated, THE System SHALL mark all records with `is_synthetic=True` for easy filtering
5. WHEN operational data volume grows, synthetic data SHALL not interfere with real analytics (isolated or separate database)

### Requirement 7: Predictive & Prescriptive Analytics Display on Admin Dashboard

**User Story:** As an admin, I want to see predictive and prescriptive analytics prominently on my dashboard so I can stay informed of facility trends and act on recommendations.

#### Acceptance Criteria

1. WHEN an admin accesses their dashboard, THE System SHALL display:
   - "Analytics Overview" card with key metrics (total reservations, occupancy %, peak facility)
   - "Demand Forecast" chart (next 3 months)
   - "Equipment Alerts" section highlighting at-risk equipment
   - "Facility Recommendations" list (prioritized)
2. WHEN viewing analytics on the dashboard, THE System SHALL update data automatically (cache for up to 1 hour)
3. WHEN analytics data is limited (< 100 reservations), THE System SHALL note "Limited historical data — displaying synthetic examples" and use mock data
4. WHEN a recommendation is clicked, THE System SHALL drill down to detailed analysis

### Requirement 8: Predictive & Prescriptive Analytics Display on Staff Dashboard

**User Story:** As a staff member, I want to see facility-specific analytics so I can manage day-to-day operations and identify immediate action items.

#### Acceptance Criteria

1. WHEN a staff member accesses their dashboard, THE System SHALL display:
   - Assigned facility quick stats (today's bookings, occupancy rate, upcoming maintenance)
   - Peak hours for their facilities
   - Equipment maintenance alerts
   - Recommended actions (e.g., "Facility is fully booked tomorrow — mark maintenance as cannot proceed")
2. WHEN staff view their facility analytics, THE System SHALL focus on immediate operational concerns (today/tomorrow/this week)
3. WHEN equipment maintenance is due, THE System SHALL recommend low-occupancy time windows for maintenance

### Requirement 9: Maintain All Existing Functionality

**User Story:** As a user, I want the system to keep all existing features working while new enhancements are added.

#### Acceptance Criteria

1. WHEN existing reservation workflows are executed, THE System SHALL function identically (no behavior change)
2. WHEN existing calendar views are accessed, THE System SHALL display content correctly (existing requestor calendar unchanged)
3. WHEN existing views are accessed (my_reservations, pending_reservations, etc.), THE System SHALL continue to work without errors
4. WHEN the database is migrated, THE System SHALL preserve all existing data and relationships
5. WHEN existing API endpoints are called, THE System SHALL return identical responses (backward compatible)

---

## Implementation Notes

- **Mock Data Separation**: Synthetic data should be identifiable via `is_synthetic=True` flag and ideally stored separately or clearly tagged for analytics-only use
- **Performance**: Analytics queries should be optimized with indexes on (facility, reservation_date, status) and cached appropriately
- **Backward Compatibility**: All new facility fields are optional to maintain compatibility with existing data
- **Two-Database Architecture**: System supports both operational (default) and analytics (synthetic) databases; dashboards intelligently switch based on data availability
- **Data-Driven Design**: All analytics defaults to synthetic data when operational data is insufficient
