# Phase 6.6: Power BI Data Model Specification

**Status**: Backend Integration Design (No Deployment)  
**Date**: October 12, 2026  
**Scope**: Read-only Power BI data interface for analytics dashboard

---

## Overview

This document specifies the Power BI-compatible data model for analytics dashboards. All data is sourced from the Aiven Cloud MySQL analytics database (read-only), with forecasting outputs integrated via Python API.

---

## Core Data Tables

### Table 1: `reservations_reservation` (Source)

**Purpose**: Core reservation facts  
**Row Count**: ~5,000 (synthetic test data)  
**Refresh**: Real-time or batch (depends on Power BI schedule)

**Columns** (all from analytics DB):

| Column | Type | Description | Notes |
|--------|------|-------------|-------|
| `id` | INT | Primary key | Unique identifier |
| `requested_by_id` | INT | Foreign key to user | Who submitted |
| `facility_id` | INT | Foreign key to facility | Which facility |
| `purpose` | VARCHAR(255) | Reservation purpose | Event description |
| `reservation_date` | DATE | Booking date | When facility used |
| `start_time` | TIME | Start time | Booking window |
| `end_time` | TIME | End time | Booking window |
| `status` | VARCHAR(20) | Status enum | PENDING/APPROVED/REJECTED/CANCELLED |
| `reviewed_by_id` | INT (NULL) | Foreign key to reviewer | Staff who approved/rejected |
| `reviewed_at` | DATETIME (NULL) | Review timestamp | When action taken |
| `rejection_reason` | TEXT | Rejection notes | If rejected |
| `is_synthetic` | BOOLEAN | Flag | Always TRUE for analytics |
| `created_at` | DATETIME | Request timestamp | Submission time |
| `updated_at` | DATETIME | Update timestamp | Last modified |

**Calculated Columns** (Power BI DAX):

- `Days_to_Approval`: IF(Status="APPROVED", DATEDIFF([created_at], [reviewed_at], DAY), BLANK())
- `Is_Approved`: IF(Status="APPROVED", 1, 0)
- `Is_Pending`: IF(Status="PENDING", 1, 0)
- `Is_Rejected`: IF(Status="REJECTED", 1, 0)
- `Is_Cancelled`: IF(Status="CANCELLED", 1, 0)
- `Week_Start`: (Date from reservation_date, ISO week)
- `Month_Year`: TEXT(reservation_date, "YYYY-MM")

---

### Table 2: `facilities_facility` (Source)

**Purpose**: Facility master data  
**Row Count**: ~20-50 (depending on synthetic data)  
**Refresh**: Daily or on-demand

**Columns**:

| Column | Type | Description | Notes |
|--------|------|-------------|-------|
| `id` | INT | Primary key | Unique identifier |
| `facility_type_id` | INT | Foreign key | Facility category |
| `name` | VARCHAR(150) | Facility name | Unique display name |
| `location` | VARCHAR(200) | Campus location | Building/floor |
| `capacity` | INT | Seating capacity | Max occupants |
| `description` | TEXT | Amenities/notes | Equipment details |
| `status` | VARCHAR(20) | Operational status | AVAILABLE/UNAVAILABLE/MAINTENANCE |
| `is_synthetic` | BOOLEAN | Flag | Always TRUE for analytics |
| `created_at` | DATETIME | Creation timestamp | When added |
| `updated_at` | DATETIME | Update timestamp | Last modified |

---

### Table 3: `facilities_facilitytype` (Dimension)

**Purpose**: Facility categories  
**Row Count**: ~5-10  
**Refresh**: Daily or on-demand

**Columns**:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT | Primary key |
| `name` | VARCHAR(100) | Category name (e.g., "Computer Lab", "Auditorium") |
| `description` | TEXT | Category description |
| `is_synthetic` | BOOLEAN | Flag |
| `created_at` | DATETIME | Creation timestamp |
| `updated_at` | DATETIME | Update timestamp |

---

### Table 4: `accounts_user` (Dimension)

**Purpose**: User reference (requesters and reviewers)  
**Row Count**: ~10-50  
**Refresh**: Daily

**Columns**:

| Column | Type | Description | Notes |
|--------|------|-------------|-------|
| `id` | INT | Primary key | User ID |
| `username` | VARCHAR(150) | Login name | Unique identifier |
| `email` | VARCHAR(254) | Email address | User contact |
| `role` | VARCHAR(20) | Role enum | ADMIN/STAFF/REQUESTER |
| `is_synthetic` | BOOLEAN | Flag | Synthetic user |
| `created_at` | DATETIME | Creation timestamp | When added |

---

## Calculated Measures

### KPI Measures (Power BI DAX)

```dax
-- Approval Metrics
Total_Reservations = COUNTA(reservations_reservation[id])
Approved_Count = CALCULATE(COUNTA(reservations_reservation[id]), 
    reservations_reservation[status]="APPROVED")
Rejected_Count = CALCULATE(COUNTA(reservations_reservation[id]), 
    reservations_reservation[status]="REJECTED")
Cancelled_Count = CALCULATE(COUNTA(reservations_reservation[id]), 
    reservations_reservation[status]="CANCELLED")
Pending_Count = CALCULATE(COUNTA(reservations_reservation[id]), 
    reservations_reservation[status]="PENDING")

-- Rate Metrics
Approval_Rate = 
    VAR ReviewedTotal = [Approved_Count] + [Rejected_Count] + [Cancelled_Count]
    RETURN IF(ReviewedTotal=0, 0, [Approved_Count]/ReviewedTotal)

Rejection_Rate = 
    VAR ReviewedTotal = [Approved_Count] + [Rejected_Count] + [Cancelled_Count]
    RETURN IF(ReviewedTotal=0, 0, [Rejected_Count]/ReviewedTotal)

Cancellation_Rate = 
    RETURN IF([Total_Reservations]=0, 0, [Cancelled_Count]/[Total_Reservations])

-- Time Metrics
Avg_Days_to_Approval = 
    CALCULATE(AVERAGE(reservations_reservation[Days_to_Approval]),
        reservations_reservation[status]="APPROVED")
```

---

## Data Relationships

### Foreign Keys (Join Paths)

```
reservations_reservation.requested_by_id → accounts_user.id
reservations_reservation.facility_id → facilities_facility.id
reservations_reservation.reviewed_by_id → accounts_user.id
facilities_facility.facility_type_id → facilities_facilitytype.id
```

### Relationship Cardinality

| From | To | Cardinality | Active |
|------|-----|-------------|--------|
| reservations_reservation | accounts_user (requester) | Many-to-One | Yes |
| reservations_reservation | facilities_facility | Many-to-One | Yes |
| facilities_facility | facilities_facilitytype | Many-to-One | Yes |
| reservations_reservation | accounts_user (reviewer) | Many-to-One | No* |

*Reviewer relationship marked inactive to avoid ambiguity; filter by reviewed_by_id when needed.

---

## Analytics Views Required

### View 1: Reservation Status Distribution

**Source**: `reservations_reservation`  
**Output**: Status summary by month

**Expected Output**:
```
Month     | PENDING | APPROVED | REJECTED | CANCELLED
----------+---------+----------+----------+-----------
2026-09   |    42   |   248    |    65    |    89
2026-10   |    38   |   256    |    58    |    95
```

---

### View 2: Monthly Reservation Trends

**Source**: `reservations_reservation`  
**Output**: Monthly reservation details

**Expected Output**:
```
Month     | Total | Approved | Rejected | Cancelled | Avg_Days_to_Approval
----------+-------+----------+----------+-----------+--------------------
2026-09   |  444  |   248    |    65    |    89     |      2.34
2026-10   |  447  |   256    |    58    |    95     |      2.41
```

---

### View 3: Facility Demand

**Source**: `reservations_reservation` + `facilities_facility`  
**Output**: Demand by facility

**Expected Output**:
```
Facility_ID | Facility_Name     | Type          | Capacity | Reservation_Count | Approved_Count
------------+-------------------+---------------+----------+-------------------+---------------
1           | IT ComLab 1       | Computer Lab  |    50    |       245         |      145
2           | Main Auditorium   | Auditorium    |   200    |       189         |      112
```

---

### View 4: Peak Booking Periods

**Source**: `reservations_reservation`  
**Output**: Booking intensity by hour and day

**Expected Output**:
```
Hour | Mon | Tue | Wed | Thu | Fri | Sat | Sun
-----+-----+-----+-----+-----+-----+-----+-----
9    |  24 |  28 |  25 |  26 |  31 |   5 |   3
10   |  26 |  29 |  27 |  28 |  34 |   7 |   4
11   |  23 |  25 |  22 |  24 |  28 |   6 |   3
```

---

### View 5: Facility Booking Intensity

**Source**: `reservations_reservation` + `facilities_facility`  
**Output**: Booking intensity metric (approved reservations / capacity)

**Expected Output**:
```
Facility_ID | Facility_Name     | Capacity | Approved_Reservations | Booking_Intensity
------------+-------------------+----------+---------------------+------------------
1           | IT ComLab 1       |    50    |       245            |      4.90
2           | Main Auditorium   |   200    |       189            |      0.95
```

---

### View 6: Reservation KPIs

**Source**: `reservations_reservation`  
**Output**: Aggregate KPI metrics

**Expected Output**:
```
Total_Reservations | Approved | Rejected | Cancelled | Pending | Approval_Rate | Rejection_Rate | Cancellation_Rate | Avg_Days_to_Approval
-------------------+----------+----------+-----------+---------+---------------+----------------+-------------------+---------------------
5000               |  2689    |    821   |   1090    |   400   |     0.5850    |     0.1780     |     0.2180        |        2.85
```

---

## Data Types Mapping

### Power BI Data Type Mapping

| SQL Type | Power BI Type | Format |
|----------|---------------|--------|
| INT | Whole Number | Default |
| VARCHAR/TEXT | Text | Default |
| DATE | Date | YYYY-MM-DD |
| DATETIME | Date/Time | YYYY-MM-DD HH:MM:SS |
| TIME | Text | HH:MM:SS (no native time) |
| BOOLEAN/TINYINT(1) | Text | "True"/"False" or 1/0 |
| DECIMAL/FLOAT | Decimal Number | Default |

**Special Handling**:
- `TIME` fields (start_time, end_time) → Import as TEXT, format HH:MM
- `DATETIME` fields → Set timezone to "Asia/Manila" in Power BI
- `BOOLEAN` (is_synthetic) → Import as Whole Number (0/1), create boolean calculation column

---

## Refresh Strategy

### Recommended Refresh Schedule

| Table | Frequency | Reason |
|-------|-----------|--------|
| reservations_reservation | Every 15-30 min | Real-time analytics |
| facilities_facility | Daily or on-demand | Master data (stable) |
| facilities_facilitytype | Daily or on-demand | Reference data (very stable) |
| accounts_user | Daily | Minimal changes |

**Note**: All refreshes are read-only queries against the analytics DB. No writes or modifications to the source database.

---

## Limitations & Considerations

### Data Completeness

- **Synthetic Data Only**: All tables filter `is_synthetic=TRUE`. Operational data excluded.
- **Historical Depth**: Current dataset ~2 years (2024-2026), suitable for trend analysis.
- **Update Latency**: DATETIME fields have timezone offset (+08:00 Manila time).

### Performance Considerations

- **Large Datasets**: reservations_reservation ~5,000 rows (manageable in Power BI)
- **Calculated Columns**: DAX calculations add processing time; precompute in SQL if bottleneck occurs.
- **Connection Pool**: Power BI maintains persistent connection; monitor Aiven connection limits.

### Security & Access

- **Read-Only**: All Power BI queries are SELECT statements only. No CREATE/ALTER/DROP operations possible.
- **Authentication**: Aiven database user (separate from Django user) with read-only role.
- **TLS/SSL**: Required for cloud connection; CA certificate configured in Power BI.
- **Credential Storage**: Power BI credentials encrypted at rest; rotated per security policy.

---

## Forecasting Integration

Forecasting is NOT directly available via SQL. See **PHASE_6_6_FORECAST_INTEGRATION.md** for API approach.

---

## Files Required for Power BI Setup

1. **Aiven CA Certificate** (`ca-cert.pem` or similar)
   - Download from Aiven console
   - Store securely; reference in Power BI TLS configuration

2. **SQL Query Scripts** (`PHASE_6_6_SQL_QUERIES.sql`)
   - Read-only SELECT statements for each view
   - Can be used directly in Power BI "SQL" data source

3. **Connection Guide** (`PHASE_6_6_CONNECTION_SETUP.md`)
   - Step-by-step Power BI connection instructions
   - TLS certificate import process
   - Least-privilege user creation (recommended, not implemented)

---

## Data Model Diagram (Conceptual)

```
┌─────────────────────────────────────┐
│    reservations_reservation         │
├─────────────────────────────────────┤
│  id (PK)                            │
│  requested_by_id (FK→User)          │
│  facility_id (FK→Facility)          │
│  purpose                            │
│  reservation_date                   │
│  start_time                         │
│  end_time                           │
│  status                             │
│  reviewed_by_id (FK→User)           │
│  reviewed_at                        │
│  is_synthetic                       │
│  created_at                         │
│  updated_at                         │
└─────────────────────────────────────┘
         │                   │
         ├─────────┬─────────┤
         │         │         │
         ▼         ▼         ▼
    ┌────────────────┐  ┌──────────────┐
    │ accounts_user  │  │ facilities_  │
    │ (Requester &   │  │ facility     │
    │  Reviewer)     │  │              │
    └────────────────┘  └──────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │ facilities_  │
                        │ facilitytype │
                        └──────────────┘
```

---

## Next Steps

1. ✅ Review this data model specification
2. ⏳ (Phase 6.6.2) Deploy SQL views if needed
3. ⏳ (Phase 6.6.3) Configure Power BI connection to Aiven
4. ⏳ (Phase 6.6.4) Build dashboards (not part of this backend work)
5. ⏳ (Phase 6.6.5) Integrate forecasting API outputs

---

**Status**: Ready for Review  
**Backend Integration Complete**: No live changes yet (documentation only)
