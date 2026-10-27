# Requirements: Analytics & Calendar Integration Fix

## Overview
Fix production issues where analytics data is not displaying on admin/staff dashboards and booking calendar colors/hover are not working in the reservation form.

## User Stories & Requirements

### 1. Analytics Dashboard Display
**As a** staff/admin user  
**I want** predictive and prescriptive analytics to display on my dashboard  
**So that** I can see demand forecasts and system recommendations  

**Acceptance Criteria:**
- Analytics overview cards show calculated KPIs (bookings, utilization, etc.)
- Demand forecast chart displays trend data
- System recommendations are populated and visible
- Synthetic data generates correctly to seed analytics engines
- Analytics work on both admin and staff dashboards

**Data Requirements:**
- Minimum 100 reservations for reliable analytics
- Mix of APPROVED, PENDING, and COMPLETED statuses
- Realistic temporal distribution (80% weekdays, 20% weekends)
- Peak hours (70% chance 2-5pm)

### 2. Production Database - Missing Columns
**As a** DevOps/System Admin  
**I want** all facility columns to exist in production database  
**So that** the application doesn't throw `OperationalError` on home page  

**Acceptance Criteria:**
- All 6 facility columns successfully added to Aiven MySQL
- Column: `equipment_list` (LONGTEXT, NULL)
- Column: `hours_of_operation` (VARCHAR 200, default "8am-6pm")
- Column: `noise_level` (VARCHAR 20, default "low")
- Column: `floor_number` (INT, NULL)
- Column: `building_code` (VARCHAR 10)
- Column: `has_wheelchair_access` (BOOLEAN, default TRUE)
- Performance indexes created for filtering/sorting
- Production database ready without data loss

### 3. Booking Calendar Integration
**As a** requestor/student user  
**I want** to see a color-coded calendar in the reservation form date selection  
**So that** I can see facility occupancy before choosing my time  

**Acceptance Criteria:**
- Calendar displays in "Date and time" section of reservation form
- Color coding by occupancy: 🟢 Green (0-33%), 🟡 Yellow (34-66%), 🔴 Red (67-100%), ⚫ Gray (unavailable)
- Hover tooltip shows:
  - Occupancy percentage
  - List of reservations (time + purpose)
  - List of maintenance windows
- Calendar updates when facility is selected
- Clicking a date in calendar populates the date field
- Works alongside existing date/time picker
- No breaking changes to existing reservation workflow

## Success Criteria
1. ✅ Analytics appear on `/accounts/admin-dashboard/` and staff dashboard
2. ✅ Demand forecast chart displays with data
3. ✅ Recommendations section populated
4. ✅ Production database has all 6 facility columns
5. ✅ No OperationalError on home page in production
6. ✅ Booking calendar embeds in reservation form with colors and hover
7. ✅ Calendar API returns correct occupancy data
8. ✅ All existing tests pass
9. ✅ Zero data loss during production update

## Non-Functional Requirements
- Database fix must be reversible or safe
- Calendar must not add significant load to analytics API
- No breaking changes to existing reservation or facility models
- Performance: Analytics dashboard loads in <2 seconds
