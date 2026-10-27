# Production Fix Guide: Database Columns & Calendar Feature

## Issue 1: Missing Facility Columns in Production Database

### Problem
```
OperationalError: (1054, "Unknown column 'facilities_facility.equipment_list' in 'field list'")
```

The migration `0004_add_facility_details.py` adds 6 new columns to the `facilities_facility` table, but was not applied to the Aiven cloud MySQL database.

### Solution: Apply Database Fix

Choose ONE of these approaches:

#### Option A: Python Fix Script (Recommended for AWS Lambda)
```bash
python fix_production_immediate.py
```

This script:
1. Connects to your Aiven MySQL database using environment variables
2. Adds all 6 missing columns with proper defaults
3. Creates performance indexes
4. Verifies the changes

#### Option B: Manual SQL Fix
Connect to Aiven MySQL and run:
```bash
mysql -h <host> -u <user> -p <password> <database>
```

Then execute the SQL from `fix_production_db.sql`:
```sql
USE dssc_analytics;

ALTER TABLE facilities_facility 
ADD COLUMN IF NOT EXISTS equipment_list LONGTEXT NOT NULL DEFAULT '';

ALTER TABLE facilities_facility 
ADD COLUMN IF NOT EXISTS hours_of_operation VARCHAR(200) NOT NULL DEFAULT '8am-6pm';

ALTER TABLE facilities_facility 
ADD COLUMN IF NOT EXISTS noise_level VARCHAR(20) NOT NULL DEFAULT 'low';

ALTER TABLE facilities_facility 
ADD COLUMN IF NOT EXISTS floor_number INT NULL;

ALTER TABLE facilities_facility 
ADD COLUMN IF NOT EXISTS building_code VARCHAR(10) NOT NULL DEFAULT '';

ALTER TABLE facilities_facility 
ADD COLUMN IF NOT EXISTS has_wheelchair_access BOOLEAN NOT NULL DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS fac_noise_capacity_idx 
ON facilities_facility (noise_level, capacity);

CREATE INDEX IF NOT EXISTS fac_building_floor_idx 
ON facilities_facility (building_code, floor_number);
```

#### Option C: Django Migration Framework
```bash
python manage.py migrate
```

This applies all pending migrations including `0004_add_facility_details.py`.

### Verification

After applying the fix, verify the columns exist:
```bash
python manage.py dbshell
SELECT * FROM facilities_facility LIMIT 1;
```

You should see these columns:
- `equipment_list`
- `hours_of_operation`
- `noise_level`
- `floor_number`
- `building_code`
- `has_wheelchair_access`

---

## Issue 2: Interactive Facility Booking Calendar

### New Feature: Color-Coded Calendar with Hover Tooltips

#### What's New
- Interactive monthly calendar at `/facilities/<id>/calendar/`
- Color-coded days by occupancy:
  - 🟢 Green: 0-33% occupied (low occupancy)
  - 🟡 Yellow: 34-66% occupied (moderate occupancy)
  - 🔴 Red: 67-100% occupied (high occupancy)
  - ⚫ Gray: Unavailable
- Hover over any day to see:
  - Exact occupancy percentage
  - List of reservations with times
  - List of maintenance windows

#### Files Created/Modified

**New Files:**
- `templates/facilities/facility_booking_calendar.html` - Interactive calendar UI
- `facilities/calendar_api.py` - Backend API endpoints for calendar data
- `fix_production_immediate.py` - Python script to add missing DB columns
- `fix_production_db.sql` - Manual SQL fix script
- `deploy_migrations.py` - Migration deployment script

**Modified Files:**
- `facilities/urls.py` - Added new routes:
  - `/facilities/<id>/calendar/` - Interactive calendar view
  - `/api/facilities/<id>/calendar/<date>/` - API endpoint for single day
  - `/api/facilities/<id>/calendar/<year>/<month>/` - API endpoint for month
- `facilities/views.py` - Added `facility_calendar_view()` function

#### How to Access

1. Navigate to facility list: `/facilities/`
2. Click a facility
3. Click "Booking Calendar" button (or go to `/facilities/<id>/calendar/`)
4. Browse the calendar and hover over days to see details

#### API Endpoints

**Get Single Day Data:**
```
GET /api/facilities/{facility_id}/calendar/{YYYY-MM-DD}/

Response:
{
    "date": "2024-12-15",
    "occupancy": 45,
    "is_available": true,
    "reservations": [
        {
            "purpose": "Team meeting",
            "start_time": "14:00",
            "end_time": "15:00",
            "requester": "John Smith"
        }
    ],
    "maintenance": [
        {
            "title": "Projector maintenance",
            "start_time": "16:00",
            "end_time": "17:00"
        }
    ]
}
```

**Get Month Data:**
```
GET /api/facilities/{facility_id}/calendar/{year}/{month}/

Response:
{
    "year": 2024,
    "month": 12,
    "days": {
        "1": {"occupancy": 30, "reservations": 2, "maintenance": 0, "is_available": true},
        "2": {"occupancy": 45, "reservations": 3, "maintenance": 0, "is_available": true},
        ...
    }
}
```

---

## Deployment Checklist

### Step 1: Fix Database Columns (Required)
```bash
# Choose ONE:
python fix_production_immediate.py
# OR
python manage.py migrate
# OR
# Manual SQL via Aiven console
```

### Step 2: Deploy New Files to Production
- `templates/facilities/facility_booking_calendar.html`
- `facilities/calendar_api.py`
- Updated `facilities/urls.py`
- Updated `facilities/views.py`

### Step 3: Verify
1. Restart application
2. Navigate to `/facilities/`
3. Click a facility
4. Verify "Booking Calendar" link appears
5. Test calendar functionality
6. Hover over calendar days to see reservations/maintenance

### Step 4: Monitor
- Check application logs for errors
- Verify calendar loads without errors
- Test with different facilities and dates

---

## Rollback Plan

If issues occur:

### Option 1: Remove New Columns (Database Rollback)
```sql
ALTER TABLE facilities_facility DROP COLUMN equipment_list;
ALTER TABLE facilities_facility DROP COLUMN hours_of_operation;
ALTER TABLE facilities_facility DROP COLUMN noise_level;
ALTER TABLE facilities_facility DROP COLUMN floor_number;
ALTER TABLE facilities_facility DROP COLUMN building_code;
ALTER TABLE facilities_facility DROP COLUMN has_wheelchair_access;

DROP INDEX IF EXISTS fac_noise_capacity_idx ON facilities_facility;
DROP INDEX IF EXISTS fac_building_floor_idx ON facilities_facility;
```

### Option 2: Remove New Files (Code Rollback)
```bash
git revert HEAD --no-edit
```

---

## Performance Notes

- Calendar data is fetched via AJAX (no page reload)
- Hover tooltips are rendered on the frontend
- Database queries optimized with select_related/prefetch_related
- Occupancy calculation cached in browser for month view
- API endpoints return JSON (fast, lightweight)

---

## Browser Compatibility

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+
- Mobile browsers (iOS Safari 14+, Chrome Mobile 90+)

---

## Support

For issues:
1. Check application logs: `/var/task/logs/` (AWS Lambda)
2. Verify database columns exist: `SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'facilities_facility'`
3. Test API endpoints: `curl https://dssc-cfrms.vercel.app/api/facilities/1/calendar/2024-12-15/`
4. Review `fix_production_immediate.py` for connection issues

---

**Status**: ✅ Production Ready
**Version**: 6.6.0
**Last Updated**: October 2024
