# Design: Analytics & Calendar Integration Fix

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                  Reservation Form                        │
│                                                           │
│  Facility Select → [New] Calendar in Date Section       │
│                   └─→ Occupancy by Day (colors)        │
│                       └─→ Hover → Tooltip              │
│                           ├─ Reservations list        │
│                           └─ Maintenance list         │
└─────────────────────────────────────────────────────────┘
                         ↓
         /facilities/{id}/calendar-api/{date}/
                         ↓
        ┌────────────────────────────────────────┐
        │    Calendar API (facilities app)       │
        │                                        │
        │ - GET single day: occupancy data      │
        │ - Fetch reservations & maintenance    │
        │ - Calculate occupancy %               │
        └────────────────────────────────────────┘
                         ↓
        ┌────────────────────────────────────────┐
        │    Admin/Staff Dashboard               │
        │                                        │
        │ Analytics Section ← Populate with:    │
        │ - KPI Cards (bookings, utilization)  │
        │ - Demand Forecast Chart              │
        │ - Recommendations                     │
        └────────────────────────────────────────┘
                         ↓
        ┌────────────────────────────────────────┐
        │    Production Database (Aiven MySQL)   │
        │                                        │
        │ facilities_facility table:            │
        │ ✅ equipment_list (added)             │
        │ ✅ hours_of_operation (added)         │
        │ ✅ noise_level (added)                │
        │ ✅ floor_number (added)               │
        │ ✅ building_code (added)              │
        │ ✅ has_wheelchair_access (added)      │
        └────────────────────────────────────────┘
```

## Implementation Strategy

### Phase 1: Fix Production Database
**Objective:** Add missing facility columns safely to Aiven MySQL

**Approach:**
1. Use updated `fix_production_immediate.py` script
   - Handles TEXT column (equipment_list) without default value
   - Creates indexes without IF NOT EXISTS syntax (MySQL compatibility)
2. Verify all 6 columns created successfully
3. No Django migrations needed on production (already applied locally)

**Files to Update:**
- `fix_production_immediate.py` - Already created, needs final execution

### Phase 2: Generate Analytics Data
**Objective:** Seed production/staging with synthetic reservation data

**Approach:**
1. Run Django management command: `python manage.py generate_analytics_data --count 150`
   - Creates 150 realistic reservations
   - Temporal distribution: 80% weekdays, 20% weekends
   - Peak hours: 70% chance 2-5pm
   - Mixed status: 70% APPROVED, 20% PENDING, 10% COMPLETED
   - Includes 9 maintenance records

**Expected Output:**
- ✅ Created 150 reservations
- ✅ Created 9 maintenance records
- Analytics engines have data to process
- Dashboard KPIs can be calculated

**Files to Update:**
- `accounts/management/commands/generate_analytics_data.py` - Already correct, just needs execution

### Phase 3: Integrate Calendar into Reservation Form
**Objective:** Embed color-coded booking calendar into date selection section

**Current State:**
- Calendar exists standalone at `templates/facilities/facility_booking_calendar.html`
- Reservation form has custom date/time picker at `templates/reservations/reservation_form.html`
- Calendar API exists at `facilities/calendar_api.py`

**New State:**
- Embed calendar into reservation form's date step (step 1)
- Keep time picker for step 2 (unchanged)
- Calendar shows occupancy colors with hover tooltips
- Clicking calendar date populates date field and moves to time step

**Implementation:**
1. Create new component: `templates/components/facility_calendar_widget.html`
   - Reusable calendar HTML + CSS + JS
   - Takes facility_id as parameter
   - Emits date selection event

2. Update `templates/reservations/reservation_form.html`
   - Replace date input with calendar widget in date step
   - Add JavaScript to handle calendar date selection → form field update

3. Calendar API already handles:
   - Single day occupancy: `GET /facilities/{id}/calendar-api/{YYYY-MM-DD}/`
   - Returns: occupancy %, reservations, maintenance

4. Styling:
   - Use Bootstrap + existing color scheme
   - Color-coded days: Green (0-33%), Yellow (34-66%), Red (67-100%), Gray (unavailable)
   - Hover tooltips with reservation/maintenance details

**Files to Create/Update:**
- `templates/components/facility_calendar_widget.html` - New calendar component
- `templates/reservations/reservation_form.html` - Embed calendar, integrate logic
- `static/js/facility-calendar-widget.js` - Calendar JavaScript (if needed)

### Phase 4: Dashboard Analytics Display
**Objective:** Ensure analytics render on admin/staff dashboards

**Current Implementation:**
- `accounts/views.py::admin_dashboard_view()` calculates analytics
- `templates/accounts/admin_dashboard.html` has sections for analytics
- Services exist: `analytics.services.get_demand_forecast()`, `get_recommendations()`

**Verification Steps:**
1. Check that analytics services return data (not empty lists)
2. Verify template renders analytics sections
3. Ensure synthetic data meets minimum thresholds (100+ reservations)
4. Check for silent failures in analytics calculations

**Files to Verify:**
- `accounts/views.py` - analytics view logic
- `templates/accounts/admin_dashboard.html` - template sections
- `analytics/services.py` - analytics service calls

## Data Flow

### Booking Calendar Flow
```
User selects facility
    ↓
Calendar widget loads (AJAX to calendar_api)
    ↓
For each day in month: GET /facilities/{id}/calendar-api/{date}/
    ↓
API returns: {occupancy: %, reservations: [], maintenance: [], is_available: bool}
    ↓
Day colored: Green/Yellow/Red/Gray based on occupancy
    ↓
User hovers → Tooltip shows occupancy + reservations + maintenance
    ↓
User clicks day → Date field updated → Move to time selection step
```

### Analytics Flow
```
Synthetic data generated (150 reservations)
    ↓
Analytics services calculate on next dashboard load
    ↓
get_demand_forecast() → Returns trend data for chart
    ↓
get_recommendations() → Returns facility-level or system-level suggestions
    ↓
Dashboard template renders:
  - KPI cards with calculated values
  - Forecast chart with trend data
  - Recommendations list
```

## Technical Decisions

### 1. Calendar Component Architecture
- **Option A**: Keep standalone page + embed iframe into form
  - ❌ Not viable - iframes add complexity
- **Option B**: Extract calendar as reusable component + integrate
  - ✅ Chosen - DRY, maintainable, fast

### 2. API for Calendar Data
- **Option A**: Fetch full month data on load
  - ❌ Network overhead, caching complexity
- **Option B**: Fetch data per day on demand (as user hovers/views)
  - ✅ Chosen - Matches existing calendar_api approach

### 3. Production Database Fix
- **Option A**: Run Django migrations on production
  - ❌ Risky - full migration framework
- **Option B**: Use direct Python script to add columns
  - ✅ Chosen - Already created, faster, reversible

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Production DB corruption | Use non-destructive ALTER TABLE, test on staging first |
| Analytics data insufficient | Generate 150 synthetic records (exceeds 100 minimum) |
| Calendar API performance | Existing indexes on reservations, caching in place |
| Reservation form breakage | Preserve all existing inputs/logic, only add visual layer |
| Silent failures in analytics | Add logging, test dashboard loads with synthetic data |

## Testing Strategy

1. **Unit Tests**: Analytics services return data with sample dataset
2. **Integration Tests**: Calendar API returns correct occupancy %
3. **UI Tests**: Calendar renders, hover works, date selection integrates
4. **End-to-End Tests**: Full flow: select facility → see calendar → pick date → complete reservation
5. **Dashboard Tests**: Analytics display correctly with synthetic data

## Rollback Plan

- **Database**: Column removal script (if needed)
- **Code**: Revert to last stable commit (all changes are additive, non-breaking)
- **Data**: Synthetic data easily removed (marked with `is_synthetic=True`)
