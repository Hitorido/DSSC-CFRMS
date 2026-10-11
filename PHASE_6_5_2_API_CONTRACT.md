# Phase 6.5.2: Analytics JSON API Contract

**Date**: October 11, 2026  
**Status**: ✓ COMPLETE  
**Backend Implementation**: JSON API Endpoints  

---

## Overview

This document defines the contract for the analytics JSON API endpoints implemented in Phase 6.5.2. All endpoints are read-only, use consistent JSON responses, and require ADMIN role authentication.

**Base Path**: `/api/analytics/`

---

## Authentication & Authorization

### Access Control
- **ADMIN role**: ✅ Full access to all endpoints
- **STAFF role**: ❌ Denied (HTTP 403)
- **REQUESTER role**: ❌ Denied (HTTP 403)
- **Unauthenticated users**: ❌ Redirect to `/accounts/login/`

### Error Responses

**403 Forbidden (Insufficient Permissions)**:
```json
{
    "error": "Permission denied",
    "detail": "Only ADMIN users can access analytics endpoints.",
    "required_role": "ADMIN"
}
```

**503 Service Unavailable (Database Unavailable)**:
```json
{
    "error": "Service unavailable",
    "detail": "Analytics database is unavailable. Please try again later."
}
```

**400 Bad Request (Invalid Parameters)**:
```json
{
    "error": "Invalid parameter",
    "detail": "start_date must be ISO format (YYYY-MM-DD). Got: invalid-date"
}
```

---

## Endpoints

### 1. Reservation KPIs

**Endpoint**: `GET /api/analytics/reservation-kpis/`

**Description**: Returns key performance indicators for reservations including approval, rejection, and cancellation rates.

**Authentication**: Required (ADMIN)

**Query Parameters**: None

**Response (200 OK)**:
```json
{
    "total_reservations": 5000,
    "approved_count": 2689,
    "rejected_count": 821,
    "cancelled_count": 1090,
    "pending_count": 400,
    "approval_rate": 0.5850,
    "rejection_rate": 0.1780,
    "cancellation_rate": 0.2180,
    "average_days_to_approval": 2.85
}
```

**Metric Definitions**:
- `total_reservations`: Total count of all reservations (all statuses)
- `approved_count`: Number of approved reservations
- `rejected_count`: Number of rejected reservations
- `cancelled_count`: Number of cancelled reservations
- `pending_count`: Number of pending (awaiting review) reservations
- `approval_rate`: `approved / (approved + rejected + cancelled)` - Only counts REVIEWED requests
- `rejection_rate`: `rejected / (approved + rejected + cancelled)` - Only counts REVIEWED requests
- `cancellation_rate`: `cancelled / total` - Counts ALL requests including pending
- `average_days_to_approval`: Mean days from creation to approval (approved reservations only)

**Example cURL**:
```bash
curl -H "Authorization: Bearer <token>" \
  https://example.com/api/analytics/reservation-kpis/
```

---

### 2. Reservation Status Distribution

**Endpoint**: `GET /api/analytics/status-distribution/`

**Description**: Returns count of reservations grouped by status.

**Authentication**: Required (ADMIN)

**Query Parameters**: None

**Response (200 OK)**:
```json
{
    "APPROVED": 2689,
    "REJECTED": 821,
    "CANCELLED": 1090,
    "PENDING": 400
}
```

**Notes**:
- Returns empty object `{}` if no data exists
- Status values are the exact status choices from the Reservation model

**Example cURL**:
```bash
curl -H "Authorization: Bearer <token>" \
  https://example.com/api/analytics/status-distribution/
```

---

### 3. Monthly Reservation Trends

**Endpoint**: `GET /api/analytics/monthly-trends/`

**Description**: Returns monthly reservation trends with status breakdown for a date range.

**Authentication**: Required (ADMIN)

**Query Parameters**:
- `start_date` (optional): ISO format date string (YYYY-MM-DD). Default: 24 months ago
- `end_date` (optional): ISO format date string (YYYY-MM-DD). Default: today

**Validation Rules**:
- Both dates must be ISO format `YYYY-MM-DD` if provided
- `start_date` must be less than or equal to `end_date`
- Invalid format returns HTTP 400
- Invalid range returns HTTP 400

**Response (200 OK)**:
```json
[
    {
        "month": "2024-10",
        "submitted_count": 420,
        "approved_count": 245,
        "rejected_count": 75,
        "cancelled_count": 100,
        "total": 420
    },
    {
        "month": "2024-11",
        "submitted_count": 385,
        "approved_count": 220,
        "rejected_count": 65,
        "cancelled_count": 100,
        "total": 385
    }
]
```

**Notes**:
- Returns empty array `[]` if no data exists for date range
- Months are sorted chronologically (oldest to newest)
- `submitted_count` and `total` are always equal
- Month format is `YYYY-MM` (e.g., "2024-10")

**Example cURL**:
```bash
curl -H "Authorization: Bearer <token>" \
  "https://example.com/api/analytics/monthly-trends/?start_date=2024-01-01&end_date=2024-12-31"
```

---

### 4. Facility Demand

**Endpoint**: `GET /api/analytics/facility-demand/`

**Description**: Returns facilities ranked by reservation demand (highest to lowest).

**Authentication**: Required (ADMIN)

**Query Parameters**: None

**Response (200 OK)**:
```json
[
    {
        "facility_id": 1,
        "facility_name": "Computer Lab A",
        "facility_type": "Computer Lab",
        "reservation_count": 856,
        "approved_count": 500,
        "capacity": 50
    },
    {
        "facility_id": 2,
        "facility_name": "Physics Lab",
        "facility_type": "Science Lab",
        "reservation_count": 745,
        "approved_count": 425,
        "capacity": 30
    }
]
```

**Notes**:
- Sorted by `reservation_count` in descending order (highest demand first)
- `reservation_count` includes ALL reservation statuses (approved, rejected, cancelled, pending)
- `approved_count` includes only APPROVED reservations
- Returns empty array `[]` if no facilities exist

**Example cURL**:
```bash
curl -H "Authorization: Bearer <token>" \
  https://example.com/api/analytics/facility-demand/
```

---

### 5. Peak Booking Periods

**Endpoint**: `GET /api/analytics/peak-booking-periods/`

**Description**: Returns peak booking patterns by hour, day of week, and facility.

**Authentication**: Required (ADMIN)

**Query Parameters**: None

**Response (200 OK)**:
```json
{
    "by_hour": {
        "9": 245,
        "10": 312,
        "14": 198,
        "15": 225
    },
    "by_day_of_week": {
        "0": 420,
        "1": 450,
        "2": 435,
        "3": 410,
        "4": 425,
        "5": 380,
        "6": 295
    },
    "by_facility": [
        {
            "facility_name": "Computer Lab A",
            "count": 856
        },
        {
            "facility_name": "Physics Lab",
            "count": 745
        }
    ]
}
```

**Notes**:
- `by_hour`: Keys are hour numbers (0-23, 24-hour format) as strings. Values are booking counts.
- `by_day_of_week`: Keys are day numbers (0=Monday, 1=Tuesday, ..., 6=Sunday) as strings. Values are booking counts.
- `by_facility`: List of facilities with booking counts, ordered by count descending
- Empty periods are omitted (not included in response)
- All counts represent reservation requests (all statuses)

**Example cURL**:
```bash
curl -H "Authorization: Bearer <token>" \
  https://example.com/api/analytics/peak-booking-periods/
```

---

### 6. Facility Booking Intensity

**Endpoint**: `GET /api/analytics/facility-booking-intensity/`

**Description**: Returns facility booking intensity scores. **Measures booking intensity (total bookings / capacity), NOT occupancy utilization (simultaneous occupancy).**

**Authentication**: Required (ADMIN)

**Query Parameters**: None

**Response (200 OK)**:
```json
[
    {
        "facility_id": 1,
        "facility_name": "Computer Lab A",
        "facility_type": "Computer Lab",
        "capacity": 50,
        "approved_reservations": 245,
        "booking_intensity": 4.9000
    },
    {
        "facility_id": 2,
        "facility_name": "Physics Lab",
        "facility_type": "Science Lab",
        "capacity": 30,
        "approved_reservations": 89,
        "booking_intensity": 2.9667
    }
]
```

**Metric Definition**:
- `booking_intensity = approved_reservations / capacity`
- Measures how many "capacity units" worth of bookings are scheduled
- Does NOT account for time-slot overlap or simultaneous occupancy
- Interpretation:
  - **0.0-0.5**: Low intensity (plenty of capacity available)
  - **0.5-1.0**: Moderate intensity (reasonable utilization)
  - **1.0+**: High intensity (more scheduled bookings than single capacity can support)

**Notes**:
- Sorted by `booking_intensity` in descending order (highest first)
- Includes only APPROVED reservations in calculation
- Returns empty array `[]` if no facilities exist
- `booking_intensity` values are rounded to 4 decimal places

**Important**: This metric is NOT actual occupancy utilization. Multiple bookings may overlap in time, so actual simultaneous occupancy could be much lower than this score suggests. To calculate true occupancy utilization, time-slot overlap analysis would be required (not included in Phase 6.5.2 MVP).

**Example cURL**:
```bash
curl -H "Authorization: Bearer <token>" \
  https://example.com/api/analytics/facility-booking-intensity/
```

---

## Common Patterns

### Authentication
All endpoints require the user to be authenticated with ADMIN role. Frontend should include authentication token/session and handle:
- **401/Redirect to Login**: Unauthenticated requests are redirected to `/accounts/login/`
- **403 Forbidden**: Authenticated users without ADMIN role receive HTTP 403

### Error Handling
All error responses follow consistent JSON structure:
```json
{
    "error": "Error category",
    "detail": "Detailed explanation of the error"
}
```

Additional fields may be included for specific error types (e.g., `required_role` for 403).

### Date Parameters
- Format: ISO 8601 date format `YYYY-MM-DD` (e.g., "2024-10-15")
- Parameters: `start_date`, `end_date` (query string)
- Validation: Invalid format → 400 Bad Request
- Logic: If provided, dates define filtering range. If omitted, sensible defaults apply.

### Empty Results
- Endpoints return empty collections rather than errors when no data exists
- Empty responses:
  - Status distribution: `{}`
  - Facility lists: `[]`
  - Monthly trends: `[]`

### JSON Serialization
- All responses are valid JSON
- Numeric values: integers and floats as appropriate
- Date/time values: ISO format strings (YYYY-MM or YYYY-MM-DD)
- All keys use snake_case

---

## HTTP Methods

- **Allowed**: `GET`
- **Not Allowed**: `POST`, `PUT`, `PATCH`, `DELETE`
- Requests using unsupported methods receive HTTP 405 Method Not Allowed

---

## Implementation Notes

### Database Safety
- All endpoints are read-only (SELECT queries only)
- No data is written to any database
- Analytics database ('analytics' alias) is used exclusively
- If analytics database is unavailable, HTTP 503 is returned (safe fail-fast, never falls back to operational database)

### Performance Considerations
- Endpoints perform aggregation at the database level
- No N+1 queries or client-side aggregation
- Efficient for dashboard rendering

### Security
- Authentication required on all endpoints
- Role-based access control (ADMIN only)
- No SQL injection vectors (Django ORM used)
- No sensitive data in error messages (no SQL, credentials, or internal details)
- CSRF protection applied (standard Django)

---

## Frontend Integration Checklist

For Phase 6.5.3 frontend implementation:

- [ ] Authenticate users and include session/token with requests
- [ ] Handle redirects to `/accounts/login/` for unauthenticated users
- [ ] Display HTTP 403 error when non-ADMIN users attempt access
- [ ] Catch HTTP 503 and display "service unavailable" message
- [ ] Validate date range inputs before sending (YYYY-MM-DD format)
- [ ] Display HTTP 400 errors with detailed messages if parameter validation fails
- [ ] Render KPI metrics on dashboard (gauge charts, percentages)
- [ ] Display status distribution as pie/donut chart
- [ ] Plot monthly trends as line/bar chart
- [ ] Render facility demand as table/bar chart
- [ ] Display peak hours as bar chart (hours 0-23)
- [ ] Display peak days as bar chart (Monday-Sunday)
- [ ] Render facility booking intensity as sorted list/bar chart
- [ ] Handle empty result sets gracefully (show "No data available" message)
- [ ] Add date range picker for monthly trends filtering
- [ ] Implement refresh/reload functionality

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2026-10-11 | 1.0 | Initial API contract for Phase 6.5.2 |

---

## Support & Maintenance

For issues or questions:
1. Check endpoint response for detailed error messages
2. Verify user has ADMIN role (`user.role == 'ADMIN'`)
3. Confirm analytics database is configured in Django settings
4. Review Django logs for any backend errors
5. Contact development team if issues persist
