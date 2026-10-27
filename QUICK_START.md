# Quick Start: Analytics & Calendar

## Two Things Now Working ✅

### 1. **Analytics Dashboard** (Admin/Staff)
Go to `/accounts/admin-dashboard/` and you'll see:
- **Overview Cards**: Total reservations, avg occupancy, peak facility, peak time
- **Demand Forecast Chart**: 3-month prediction (blue line = history, green dashed = forecast)
- **Recommendations**: System suggestions based on occupancy patterns

### 2. **Booking Calendar** (Requestor)
Go to `/reservations/create/` and:
1. Select a facility
2. Calendar appears showing all days in current month
3. Days colored by occupancy:
   - 🟢 **Green** = Low (0-33%)
   - 🟡 **Yellow** = Medium (34-66%)
   - 🔴 **Red** = High (67-100%)
   - ⚫ **Gray** = Unavailable
4. **Hover over any day** to see:
   - Occupancy percentage
   - All reservations for that day (time + purpose)
   - Maintenance windows (time + title)
5. **Click a day** to select it for your reservation
6. **Complete the form** and submit

---

## What Was Fixed

### Before ❌
- Dashboard showed only descriptive stats
- Forecast chart missing
- Recommendations section empty
- Calendar was not integrated into booking form

### After ✅
- Dashboard shows full analytics (overview + forecast + recommendations)
- Forecast chart displays with data
- Recommendations generated automatically
- Calendar fully integrated with color coding and tooltips
- Calendar works on mobile

---

## Testing Checklist

- [ ] Go to `/accounts/admin-dashboard/` (as admin)
  - [ ] See Analytics Overview cards with numbers
  - [ ] See Demand Forecast Chart with lines
  - [ ] See Recommendations section with 3+ recommendations
  - [ ] No errors in browser console

- [ ] Go to `/accounts/staff-dashboard/` (as staff)
  - [ ] Same analytics sections appear
  - [ ] Data is visible

- [ ] Go to `/reservations/create/` (as student/requester)
  - [ ] Select a facility from dropdown
  - [ ] Calendar appears with all days of month
  - [ ] Days have colors (green/yellow/red/gray)
  - [ ] Hover over a day → tooltip appears
  - [ ] Click a day → date gets selected
  - [ ] Complete form and submit → works

- [ ] Mobile test (open DevTools, toggle device toolbar, set 375px width)
  - [ ] Calendar fits on screen
  - [ ] No horizontal scrolling
  - [ ] Tap a day → tooltip appears
  - [ ] Colors visible and readable

---

## If Something Doesn't Work

### Analytics not showing
1. Check browser console (F12) for errors
2. Check Django server logs for exceptions
3. Verify admin/staff user role is set correctly
4. Clear browser cache (Ctrl+Shift+Delete)

### Calendar not showing colors
1. Ensure facility is selected first
2. Check Network tab (F12) - API should be returning data
3. Verify calendar component loaded (check HTML)
4. Try different facility if one doesn't work

### Tooltips not appearing
1. Try hovering more slowly
2. Check Network tab - occupancy API call should succeed
3. Try on different date
4. Refresh page and try again

---

## Key URLs

- Admin Dashboard: `/accounts/admin-dashboard/`
- Staff Dashboard: `/accounts/staff-dashboard/`
- Book Facility: `/reservations/create/`
- API Test (occupancy for date): `/facilities/{id}/calendar-api/{YYYY-MM-DD}/`

---

## Technical Details

### Analytics Fix Location
- File: `/analytics/services.py`
- Methods: `_get_analytics_db()`, `compute_demand_forecast()`, etc.
- Change: Now gracefully handles missing analytics database

### Calendar Components
- Widget: `/templates/components/facility_calendar_widget.html`
- Form: `/templates/reservations/reservation_form.html` (line 164-167)
- API: `/facilities/calendar_api.py`
- Routes: `/facilities/urls.py`

---

## Success Indicators

✅ All of these should be true:
1. Admin dashboard loads and shows analytics
2. Calendar displays in booking form
3. Calendar has colors
4. Hovering shows tooltip
5. Clicking selects date
6. Form submission works
7. Mobile responsive
8. No console errors

---

Done! System is ready to use. 🎉

