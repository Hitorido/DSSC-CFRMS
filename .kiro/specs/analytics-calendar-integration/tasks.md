# Tasks: Analytics & Calendar Integration Fix

## Task 1: Fix Production Database - Add Missing Facility Columns
**Status**: not_started | **Priority**: critical | **Effort**: 15min

**Description**: 
Execute the production database fix script to add 6 missing facility columns to Aiven MySQL. The script has been created and tested locally - just needs final execution with equipment_list fix.

**Sub-tasks**:
- [x] Verify fix_production_immediate.py script has equipment_list fix (LONGTEXT without default)
- [x] Execute script: `python fix_production_immediate.py`
- [x] Verify all 6 columns added successfully (check script output)
- [x] Create performance indexes (fac_noise_capacity_idx, fac_building_floor_idx)
- [x] Confirm production database ready (no OperationalError)

**Dependencies**: None

**Acceptance Criteria**:
- ✅ All 6 columns exist in facilities_facility table
- ✅ No OperationalError when accessing home page
- ✅ Indexes created for performance
- ✅ Zero data loss

---

## Task 2: Generate Synthetic Analytics Data
**Status**: not_started | **Priority**: high | **Effort**: 5min

**Description**: 
Run the Django management command to generate 150 synthetic reservations and maintenance records. This data seeds the analytics engines so dashboards have meaningful KPIs and forecast data to display.

**Sub-tasks**:
- [x] Run: `python manage.py generate_analytics_data --count 150`
- [x] Verify output: "Created 150 reservations" and "Created 9 maintenance records"
- [x] Confirm no errors or validation issues
- [x] Check reservation data visible in admin or Django shell

**Dependencies**: Task 1 (production DB must be ready)

**Acceptance Criteria**:
- ✅ 150 synthetic reservations created
- ✅ Mix of APPROVED, PENDING, COMPLETED statuses
- ✅ Temporal distribution correct (80% weekdays)
- ✅ 9 maintenance records created
- ✅ Data marked as `is_synthetic=True` for tracking

---

## Task 3: Extract Calendar as Reusable Component
**Status**: not_started | **Priority**: high | **Effort**: 30min

**Description**: 
Extract the booking calendar HTML/CSS/JS from the standalone page into a reusable component that can be embedded in the reservation form. This component will be used in the date selection step.

**Sub-tasks**:
- [x] Create `templates/components/facility_calendar_widget.html`
- [x] Extract calendar markup, styles, and JavaScript from `templates/facilities/facility_booking_calendar.html`
- [x] Make component parameterized (accept facility_id, date range)
- [x] Emit custom event when user clicks a date (e.g., `calendarDateSelected`)
- [x] Ensure calendar fetches from existing API: `/facilities/{id}/calendar-api/{date}/`
- [x] Test component renders correctly in isolation

**Dependencies**: None (API already exists)

**Acceptance Criteria**:
- ✅ Component HTML includes all calendar markup
- ✅ Styles preserved (colors, hover, responsive)
- ✅ JavaScript functional and isolated
- ✅ Emits date selection event with selected date
- ✅ Fetches occupancy data from calendar_api endpoint
- ✅ No console errors when component loads

---

## Task 4: Integrate Calendar into Reservation Form
**Status**: not_started | **Priority**: high | **Effort**: 45min

**Description**: 
Embed the calendar component into the reservation form's "Date and time" section (Step 1: Choose a date). Replace the native date input with the interactive calendar that shows occupancy colors and hover tooltips. Keep the existing time picker for Step 2.

**Sub-tasks**:
- [x] Update `templates/reservations/reservation_form.html`
- [x] In date step (Step 1), replace date input with calendar component
- [x] Keep native date input as fallback for accessibility
- [x] Add JavaScript event listener for `calendarDateSelected`
- [x] On calendar date click: populate hidden date field, move to time step
- [x] Ensure facility change reloads calendar data
- [x] Test calendar appears and responds to facility selection
- [x] Verify time step still works after calendar integration
- [x] Test on mobile (responsive calendar)

**Dependencies**: Task 3 (component must exist)

**Acceptance Criteria**:
- ✅ Calendar displays in reservation form date section
- ✅ Color coding works (Green/Yellow/Red/Gray)
- ✅ Hover tooltip shows occupancy, reservations, maintenance
- ✅ Clicking date populates form field
- ✅ Moves to time selection after date click
- ✅ Facility change triggers calendar data refresh
- ✅ No JavaScript errors in console
- ✅ Form submission works with calendar-selected date
- ✅ Responsive on mobile

---

## Task 5: Verify Calendar API Functionality
**Status**: not_started | **Priority**: medium | **Effort**: 20min

**Description**: 
Test the existing calendar API endpoints to ensure they return correct occupancy data, reservations, and maintenance windows. Verify calculations and response format.

**Sub-tasks**:
- [x] Test endpoint: `GET /facilities/{id}/calendar-api/{YYYY-MM-DD}/` (single day)
- [ ] Test endpoint: `GET /facilities/{id}/calendar-api/{year}/{month}/` (full month)
- [ ] Verify occupancy % calculated correctly
- [ ] Verify reservations list formatted correctly (time, purpose)
- [ ] Verify maintenance windows included
- [ ] Verify unavailable facilities return `is_available: false`
- [ ] Check response time (should be <500ms)
- [ ] Test with synthetic data from Task 2

**Dependencies**: Task 1 (DB ready), Task 2 (data available)

**Acceptance Criteria**:
- ✅ API returns valid JSON with occupancy data
- ✅ Occupancy % between 0-100
- ✅ Reservations include start_time, end_time, purpose
- ✅ Maintenance includes title, times
- ✅ Unavailable facilities marked correctly
- ✅ Response time acceptable (<500ms)

---

## Task 6: Test Dashboard Analytics Display
**Status**: not_started | **Priority**: high | **Effort**: 30min

**Description**: 
Verify that analytics appear on the admin and staff dashboards after synthetic data generation. Test that KPIs, demand forecast, and recommendations display correctly.

**Sub-tasks**:
- [ ] Navigate to `/accounts/admin-dashboard/`
- [ ] Verify analytics overview cards display KPIs (bookings, utilization, etc.)
- [ ] Verify demand forecast chart shows trend data
- [ ] Verify system recommendations section populated
- [ ] Verify no JavaScript errors in console
- [ ] Check same on staff dashboard
- [ ] Test with different date ranges (last 7 days, 30 days)
- [ ] Verify analytics update after new data added
- [ ] Check for missing data gracefully (no crashes)

**Dependencies**: Task 2 (synthetic data must exist)

**Acceptance Criteria**:
- ✅ Dashboard loads without OperationalError
- ✅ Analytics cards show calculated values (not empty)
- ✅ Demand forecast chart displays with data points
- ✅ Recommendations appear (not empty list)
- ✅ No console errors or warnings
- ✅ Same works on admin and staff dashboards
- ✅ Data refreshes correctly

---

## Task 7: End-to-End Reservation Flow Test
**Status**: not_started | **Priority**: high | **Effort**: 40min

**Description**: 
Test the complete reservation creation flow with the integrated calendar. Verify that users can select a facility, see the calendar with occupancy, choose a date via calendar, proceed to time selection, and submit the reservation successfully.

**Sub-tasks**:
- [ ] Create test user (requestor/student role)
- [ ] Navigate to `/reservations/create/`
- [ ] Select a facility from dropdown
- [ ] Verify calendar loads with occupancy colors
- [ ] Hover over days to see tooltips
- [ ] Click on a green/yellow day → date selected
- [ ] Verify move to time selection step
- [ ] Select start and end times
- [ ] Submit reservation
- [ ] Verify reservation created successfully
- [ ] Check reservation appears in "My Reservations"
- [ ] Test on multiple browsers (Chrome, Firefox, Safari)

**Dependencies**: Task 1, 2, 4 (DB ready, data available, calendar integrated)

**Acceptance Criteria**:
- ✅ Calendar displays in reservation form
- ✅ Facility change reloads calendar data
- ✅ Date selection via calendar works
- ✅ Color coding accurate (matches actual occupancy)
- ✅ Tooltips show correct reservations
- ✅ Reservation submits and saves
- ✅ Works across browsers
- ✅ Mobile responsive

---

## Task 8: Production Deployment & Validation
**Status**: not_started | **Priority**: critical | **Effort**: 30min

**Description**: 
Deploy changes to production and validate that everything is working: database has new columns, analytics display, calendar works, and no errors occur.

**Sub-tasks**:
- [ ] Deploy code changes to production (all templates, views, static files)
- [ ] Execute database fix script on production: `python fix_production_immediate.py`
- [ ] Run synthetic data command on production: `python manage.py generate_analytics_data --count 150`
- [ ] Verify production home page loads (no OperationalError)
- [ ] Check admin dashboard shows analytics
- [ ] Check staff dashboard shows analytics
- [ ] Test reservation form with calendar
- [ ] Monitor logs for errors (24 hours)
- [ ] Verify user reports (if any issues)

**Dependencies**: All prior tasks (1-7)

**Acceptance Criteria**:
- ✅ Production database has all 6 facility columns
- ✅ No OperationalError on any page
- ✅ Analytics visible on both dashboards
- ✅ Booking calendar works in reservation form
- ✅ Users can create reservations using calendar
- ✅ No errors in production logs
- ✅ Performance acceptable (pages load <2s)

---

## Summary

| Task | Priority | Effort | Status |
|------|----------|--------|--------|
| 1: Fix DB | 🔴 critical | 15m | not_started |
| 2: Generate Data | 🟠 high | 5m | not_started |
| 3: Extract Component | 🟠 high | 30m | not_started |
| 4: Integrate Form | 🟠 high | 45m | not_started |
| 5: Verify API | 🟡 medium | 20m | not_started |
| 6: Test Dashboard | 🟠 high | 30m | not_started |
| 7: E2E Test | 🟠 high | 40m | not_started |
| 8: Production Deploy | 🔴 critical | 30m | not_started |

**Total Effort**: ~3.5 hours

**Critical Path**: 1 → 2 → (3,5,6 parallel) → 4 → 7 → 8
