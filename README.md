# 📚 DSSC Facility Reservation Management System

**Unified facility booking, analytics, and demand forecasting platform for De La Salle University.**

One system for facility reservations, real-time analytics, demand forecasting, and Power BI dashboards.

```
status: 6.6.0 Production Ready  |  tests: 83/83 ✅  |  coverage: 100% Analytics
Django 5.1  |  Python 3.x  |  MySQL 8.0 + Aiven Cloud  |  Power BI Ready
```

## Overview

DSSC CFRMS is a complete facility management and analytics platform. Reserve facilities, track utilization, and forecast demand with integrated statistical methods. Backend-ready for Power BI dashboards via secure Aiven Cloud MySQL connection.

**What it does:**
- 📅 **Reservations**: Complete booking workflow with approval process
- 📊 **Analytics**: 7 real-time JSON API endpoints for KPI tracking
- 🔮 **Forecasting**: 4-week demand predictions (Seasonal Naive + Exponential Smoothing)
- 📈 **Power BI**: 14 pre-written SQL queries for cloud dashboards
- 👥 **Access Control**: Role-based permissions (Admin, Staff, Requester)
- 🧪 **Tested**: 83 comprehensive tests covering all analytics

---

## Quick Start

### Prerequisites
```bash
Python 3.x  |  MySQL 8.0  |  Virtual environment
```

### Installation

```bash
# 1. Clone repository
git clone https://github.com/your-org/dssc-cfrms.git
cd dssc-cfrms

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 5. Run migrations
python manage.py migrate

# 6. Create superuser
python manage.py createsuperuser

# 7. Start development server
python manage.py runserver
```

Visit `http://localhost:8000` to access the system.

---

## Project Structure

```
dssc-cfrms/
├── 📁 accounts/              User auth & roles
├── 📁 facilities/            Facility management
├── 📁 reservations/          Booking system
├── 📁 notifications/         Email & alerts
├── 📁 analytics/             API endpoints & forecasting
│   ├── views.py              7 JSON endpoints
│   ├── services.py           KPI calculations
│   ├── forecasting.py        Demand forecasting engine
│   └── tests/                83 comprehensive tests
├── 📁 config/                Django settings
├── 📁 templates/             HTML templates
├── 📁 static/                CSS, JS, images
├── 📁 certs/                 TLS certificates (Aiven)
└── requirements.txt          Dependencies
```

---

## Core Features

### 1️⃣ Reservation System
- **Status Flow**: PENDING → APPROVED / REJECTED / CANCELLED
- **Workflow**: Request → Review → Approve
- **Tracking**: Created/updated timestamps, reviewer info
- **Synthetic Data**: Test data with `is_synthetic` flag

### 2️⃣ Analytics API
Seven read-only endpoints (ADMIN access required):

```bash
GET /api/analytics/reservation-kpis/           # Approval rates, metrics
GET /api/analytics/status-distribution/        # Status breakdown
GET /api/analytics/monthly-trends/             # Monthly trends
GET /api/analytics/facility-demand/            # Facility rankings
GET /api/analytics/peak-booking-periods/       # Hour/day patterns
GET /api/analytics/facility-booking-intensity/ # Bookings per capacity
GET /api/analytics/demand-forecast/            # 4-week forecast
```

All return JSON with HTTP 401 (unauthenticated) and 403 (unauthorized) responses.

### 3️⃣ Demand Forecasting
Three statistical methods with automatic fallback:

| Method | Requires | Accuracy | Confidence |
|--------|----------|----------|-----------|
| **Seasonal Naive** | 52+ weeks | High | ⭐⭐⭐ |
| **Exponential Smoothing** | 10+ weeks | Medium | ⭐⭐ |
| **Last Year Average** | 10+ weeks | Low | ⭐ |

Bounds are **estimated ranges** (±1.96σ), not validated confidence intervals.

### 4️⃣ Power BI Integration
Backend-ready with:
- **14 SQL Queries**: Pre-optimized for Power BI
- **REST API**: Real-time forecasts & KPIs
- **TLS/SSL**: Secure Aiven cloud connection
- **Read-only User**: Dedicated analytics account
- **Synthetic Data**: All analytics use test data

See [`PHASE_6_6_CONNECTION_SETUP.md`](PHASE_6_6_CONNECTION_SETUP.md) for setup.

---

## Database Models

### Core Entities

**User** • Authentication & roles (ADMIN, STAFF, REQUESTER)
```python
role: str  |  created_at: datetime  |  is_synthetic: bool
```

**Facility** • Building spaces & resources
```python
name: str  |  capacity: int  |  status: str  |  facility_type: FK
```

**Reservation** • Booking records
```python
status: str  |  facility: FK  |  requested_by: FK
reservation_date: date  |  start_time: time  |  end_time: time
reviewed_by: FK  |  reviewed_at: datetime
```

**Notification** • User alerts
```python
type: str  |  recipient: FK  |  read: bool
```

---

## Testing

### Run Tests
```bash
# All tests (83 total)
python manage.py test --keepdb --noinput

# Analytics only
python manage.py test analytics --keepdb --noinput
```

### Test Coverage
- ✅ 83 tests, all passing
- ✅ 100% analytics coverage
- ✅ N+1 query detection
- ✅ API auth/authorization
- ✅ Forecast algorithms
- ✅ SQL aggregations

**Execution Time**: 302.511 seconds

---

## Configuration

### Environment Variables

```env
# Debug
DEBUG=True
SECRET_KEY=your-secret-key

# Local MySQL
DB_NAME=dssc_cfrms_db
DB_USER=root
DB_PASSWORD=password
DB_HOST=127.0.0.1

# Aiven Analytics (Optional)
ANALYTICS_DB_NAME=dssc_analytics
ANALYTICS_DB_USER=avnadmin
ANALYTICS_DB_PASSWORD=aiven-password
ANALYTICS_DB_HOST=mysql-xxxx.i.aivencloud.com
ANALYTICS_DB_PORT=16332
ANALYTICS_DB_SSL_CA=/path/to/ca.pem
```

### Django Settings

| Setting | Value | Notes |
|---------|-------|-------|
| Framework | Django 5.1.15 | LTS version |
| Database | MySQL 8.0 | Local + cloud |
| Timezone | Asia/Manila | UTC storage |
| Auth | Session-based | Development |

---

## API Reference

### Endpoints Overview

#### GET /api/analytics/reservation-kpis/
```json
{
  "total_reservations": 5000,
  "approved_count": 2689,
  "approval_rate": 0.585,
  "average_days_to_approval": 2.85
}
```

#### GET /api/analytics/demand-forecast/
```json
{
  "forecasts": [
    {
      "week_start_date": "2026-10-21",
      "predicted_demand": 425,
      "lower_bound": 356,
      "upper_bound": 495,
      "method": "seasonal_naive",
      "confidence_note": "High confidence (estimated range)"
    }
  ],
  "method_used": "seasonal_naive",
  "historical_weeks_used": 156
}
```

### Authentication

All endpoints require:
- ✅ Valid Django session (authenticated user)
- ✅ ADMIN role
- ✅ Returns HTTP 401 JSON if unauthenticated
- ✅ Returns HTTP 403 JSON if unauthorized

---

## Forecasting Engine

### Algorithm: Seasonal Naive + Exponential Smoothing

```
Historical Data (156 weeks)
        ↓
    Weekly Aggregation
        ↓
    ├─ Try: Seasonal Naive (52+ weeks) ✓
    │   └─ Use same week average from previous years
    │
    ├─ Fallback: Exponential Smoothing (10+ weeks)
    │   └─ α=0.3, weighted moving average
    │
    └─ Extreme: Last Year Average (10+ weeks)
        └─ Use overall mean
        
        ↓
    Generate 4-week forecast with bounds
```

### Confidence Bounds

Bounds use ±1.96σ formula (assumes normal distribution):
- **Not** validated 95% confidence intervals
- **Estimated ranges** based on historical variance
- Coverage depends on distribution shape

---

## Power BI Integration

### Setup (7 Steps)

1. **Get Aiven credentials** from console
2. **Download CA certificate** (TLS)
3. **Create read-only user** (optional)
4. **Configure Power BI connection**
5. **Import base tables** (4 tables)
6. **Add SQL queries** (14 queries)
7. **Publish dashboards**

**Full guide**: [`PHASE_6_6_CONNECTION_SETUP.md`](PHASE_6_6_CONNECTION_SETUP.md)

### Pre-written SQL Queries

| Query | Purpose | Rows |
|-------|---------|------|
| Q1 | Base reservations | ~5,000 |
| Q2-4 | Dimensions (facilities, users) | 20-50 |
| Q5-14 | Aggregations (trends, demand, KPIs) | 1-50 |

All queries include `WHERE is_synthetic=TRUE` filtering.

---

## Architecture

### Database Strategy

```
┌─────────────────────────────────────────┐
│ Django Application                      │
│ ├─ Transactional (default)              │
│ └─ Analytics (read-only, separate)      │
└──────────┬──────────────────┬───────────┘
           │                  │
     ┌─────▼──────┐     ┌────▼──────────────┐
     │ Local MySQL│     │ Aiven Cloud MySQL │
     │ (OLTP)     │     │ (OLAP, TLS)       │
     │ 127.0.0.1  │     │ dssc_analytics    │
     └────────────┘     └───────────────────┘
                              │
                              ▼
                        ┌──────────────┐
                        │   Power BI   │
                        │  Dashboards  │
                        └──────────────┘
```

### Query Optimization

- ✅ No N+1 queries (all use `.annotate()`)
- ✅ Database aggregation (MySQL handles heavy lifting)
- ✅ Connection pooling (Django ORM)
- ✅ Response time: <1 second (median)

---

## Data Management

### Generate Synthetic Test Data

```bash
python manage.py generate_synthetic_data \
  --facilities 20 \
  --users 50 \
  --reservations 5000
```

Creates:
- 20 test facilities
- 50 test users (requesters, staff, admin)
- 5000 reservations across 3 years
- All marked with `is_synthetic=True`

### Production Use

- ⚠️ Never mix synthetic & production data
- ✅ Use `is_synthetic` flag to filter
- ✅ All API queries filter by synthetic flag
- ✅ Separate databases recommended

---

## Troubleshooting

### Connection Issues

**"Unable to connect to Aiven"**
```bash
# Test with MySQL CLI
mysql --host=mysql-xxxx.i.aivencloud.com \
      --user=avnadmin \
      --password \
      --ssl-ca=/path/to/ca.pem \
      dssc_analytics -e "SELECT 1"
```

**"Authentication required" (401)**
- ✓ User must be logged in to Django
- ✓ Session cookie must be valid
- ✓ Check browser cookies

**"Permission denied" (403)**
- ✓ User must have ADMIN role
- ✓ Check Django admin panel for role

### Test Issues

**"Test database already exists"**
```bash
python manage.py test --keepdb --noinput
# Or manually: DROP DATABASE IF EXISTS test_dssc_cfrms_db
```

**"Analytics database not configured"**
- Tests gracefully skip analytics if not configured
- Set ANALYTICS_DB_* env vars to enable

---

## Project Status

| Phase | Status | Details |
|-------|--------|---------|
| 6.5 | ✅ Complete | Analytics API, performance optimization |
| 6.6 | ✅ Complete | Power BI integration, forecasting |
| 6.6.1 | 🔄 In Progress | Power BI dashboard development |
| 6.6.2 | 📋 Planned | Power BI Service deployment |
| 6.7 | 📋 Planned | Forecast pre-calculation, versioning |
| 7.0 | 📋 Planned | Advanced ML models, anomaly detection |

---

## Documentation

### Setup & Configuration
- 📖 [`PHASE_6_6_CONNECTION_SETUP.md`](PHASE_6_6_CONNECTION_SETUP.md) — Power BI setup guide
- 📖 [`PHASE_6_6_FORECAST_INTEGRATION.md`](PHASE_6_6_FORECAST_INTEGRATION.md) — Forecasting guide

### API & Data
- 📖 [`PHASE_6_5_2_API_CONTRACT.md`](PHASE_6_5_2_API_CONTRACT.md) — API contracts
- 📖 [`PHASE_6_6_POWERBI_DATA_MODEL.md`](PHASE_6_6_POWERBI_DATA_MODEL.md) — Data model
- 📖 [`PHASE_6_6_SQL_QUERIES.sql`](PHASE_6_6_SQL_QUERIES.sql) — SQL queries

### Phase Reports
- 📊 [`PHASE_6_5_1_COMPLETION_REPORT.md`](PHASE_6_5_1_COMPLETION_REPORT.md)
- 📊 [`PHASE_6_5_2_COMPLETION_REPORT.md`](PHASE_6_5_2_COMPLETION_REPORT.md)
- 📊 [`PHASE_6_5_3_COMPLETION_REPORT.md`](PHASE_6_5_3_COMPLETION_REPORT.md)
- 📊 [`PHASE_6_5_4_OPTIMIZATION_RESULTS.md`](PHASE_6_5_4_OPTIMIZATION_RESULTS.md)
- 📊 [`PHASE_6_6_BACKEND_HANDOFF_REPORT.md`](PHASE_6_6_BACKEND_HANDOFF_REPORT.md)
- 📊 [`PHASE_6_6_FINAL_VALIDATION.md`](PHASE_6_6_FINAL_VALIDATION.md)

---

## Contributing

### Development
```bash
# Create feature branch
git checkout -b feature/your-feature

# Run tests
python manage.py test --keepdb --noinput

# Submit PR
# - Include test coverage
# - Follow PEP 8 style
# - Document complex algorithms
```

### Code Style
- 🐍 PEP 8 compliance
- 📝 Type hints (forecasting module)
- 📚 Docstrings for all functions
- 🧪 80% minimum coverage

---

## Support

### Issues & Questions
- 🐛 Report bugs with reproduction steps
- ❓ Ask questions in issues
- 📖 Check documentation first
- 🧪 Review test files for examples

### Common Errors
| Error | Solution |
|-------|----------|
| Database connection | Check credentials in .env |
| 401 Unauthorized | Login to Django admin |
| 403 Forbidden | Check user has ADMIN role |
| Test database exists | Use `--keepdb` flag |

---

## License

MIT License — See LICENSE file for details

## Authors

- **Development**: De La Salle University BSIS Program
- **Analytics**: Data Science and Systems Computing Center
- **Infrastructure**: University IT Department

---

**Version**: 6.6.0  
**Last Updated**: October 12, 2026  
**Status**: ✅ Production Ready

**Backend complete. Power BI dashboards in development.**
