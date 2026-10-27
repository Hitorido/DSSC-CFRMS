# 📚 DSSC Facility Reservation Management System

**Unified facility booking, analytics, and demand forecasting platform for De La Salle University.**

One system for facility reservations, real-time analytics, demand forecasting, and Power BI dashboards — all on Aiven Cloud MySQL.

```
Status: 6.6.0 Production Ready  |  Tests: 83/83 ✅  |  Coverage: 100%
Django 5.1  |  Python 3.x  |  ☁️ Aiven Cloud MySQL  |  Power BI Ready
```

## Overview

DSSC CFRMS is a production-ready facility management and analytics platform using cloud database infrastructure. All collaborators share the same Aiven Cloud MySQL instance — no local database setup needed. 

**What it does:**
- 📅 **Reservations**: Complete booking workflow with approval process
- 📊 **Analytics**: 7 real-time JSON API endpoints for KPI tracking  
- 🔮 **Forecasting**: 4-week demand predictions (Seasonal Naive + Exponential Smoothing)
- 📈 **Power BI**: 14 pre-written SQL queries for cloud dashboards
- 👥 **Access Control**: Role-based permissions (Admin, Staff, Requester)
- 🧪 **Tested**: 83 comprehensive tests covering all analytics
- ☁️ **Cloud-native**: All data on Aiven Cloud MySQL (shared, no local DB)

---

## Quick Start (No Local Database!)

### Prerequisites
```bash
✓ Python 3.x
✓ Virtual environment
✓ Git
✓ Aiven cloud credentials (from team lead)
```

### Installation (5 minutes)

```bash
# 1. Clone repository
git clone https://github.com/your-org/dssc-cfrms.git
cd dssc-cfrms

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Get cloud credentials from team lead
# Request: ANALYTICS_DB_PASSWORD, ANALYTICS_DB_HOST, ca.pem

# 5. Configure environment
cp .env.example .env
# Edit .env with cloud credentials (no local MySQL needed!)

# 6. Run migrations (connects to cloud database)
python manage.py migrate --database=analytics

# 7. Create superuser
python manage.py createsuperuser

# 8. Generate test data
python manage.py generate_synthetic_data --facilities 20 --users 50 --reservations 5000

# 9. Start server
python manage.py runserver
```

Visit `http://localhost:8000` to access the system.

**⚠️ No local MySQL installation needed!** Everything uses Aiven Cloud MySQL.

---

## Cloud Database Setup

### For Collaborators

**Complete cloud setup guide:** [`CLOUD_DATABASE_SETUP.md`](CLOUD_DATABASE_SETUP.md)

**Quick reference:**

```env
# Your .env file (get credentials from team lead)
ANALYTICS_DB_NAME=dssc_analytics
ANALYTICS_DB_USER=avnadmin
ANALYTICS_DB_PASSWORD=<from-team-lead>
ANALYTICS_DB_HOST=mysql-xxxx.i.aivencloud.com
ANALYTICS_DB_PORT=16332
ANALYTICS_DB_SSL_CA=/path/to/ca.pem
```

**Test connection:**
```bash
python manage.py shell
>>> from django.db import connections
>>> connections['analytics'].ensure_connection()
# Should succeed without error
```

**That's it!** You're connected to the shared cloud database.

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
- **Tracking**: Full history with timestamps
- **Shared Data**: All team members see same reservations

### 1.5️⃣ Analytics & Dashboards
- **Admin Dashboard**: System-wide analytics with demand forecast
- **Staff Dashboard**: Operational alerts and facility-specific insights
- **Facility Booking Calendar**: Color-coded occupancy with tooltips
- **Predictive Forecasting**: 3-month demand predictions
- **Prescriptive Recommendations**: Actionable insights (capacity, maintenance, hours)
- **Performance**: Dashboard loads <2 seconds, APIs respond <500ms

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

### 3️⃣ Demand Forecasting
Three statistical methods with automatic fallback:

| Method | Requires | Accuracy | Best For |
|--------|----------|----------|----------|
| **Seasonal Naive** | 52+ weeks | High ⭐⭐⭐ | Stable patterns |
| **Exponential Smoothing** | 10+ weeks | Medium ⭐⭐ | Trending data |
| **Last Year Average** | 10+ weeks | Low ⭐ | Limited history |

### 4️⃣ Power BI Integration
Backend-ready with:
- **14 SQL Queries**: Pre-optimized for Power BI
- **REST API**: Real-time forecasts & KPIs
- **TLS/SSL**: Secure cloud connection
- **Synthetic Data**: All analytics use test data

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
reviewed_by: FK  |  reviewed_at: datetime  |  is_synthetic: bool
```

**Notification** • User alerts
```python
type: str  |  recipient: FK  |  read: bool
```

---

## Testing

### Run Tests (Against Cloud Database)

```bash
# All tests (83 total)
python manage.py test --keepdb --noinput

# Analytics only
python manage.py test analytics --keepdb --noinput

# With coverage
coverage run --source='.' manage.py test --keepdb --noinput
coverage report
```

**Test Status**: ✅ All tests passing (302.511 seconds)

---

## Collaboration Workflow

### All Developers Share One Cloud Database

```
Developer A    Developer B    Developer C
    ↓              ↓              ↓
    └──────────────┬──────────────┘
              Aiven Cloud MySQL
           (Single Source of Truth)
```

### Development Process

```bash
# 1. Pull latest
git pull origin main

# 2. Create feature branch
git checkout -b feature/your-feature

# 3. Make changes (all against cloud DB)
# ...

# 4. Test against cloud database
python manage.py test --keepdb --noinput

# 5. Commit & push
git commit -m "[feature] Description"
git push origin feature/your-feature

# 6. Create pull request
```

**All collaborators see the same data** in real-time.

---

## Configuration

### Environment Variables

```env
# Cloud Database (Required)
ANALYTICS_DB_NAME=dssc_analytics
ANALYTICS_DB_USER=avnadmin
ANALYTICS_DB_PASSWORD=<from-team-lead>
ANALYTICS_DB_HOST=mysql-xxxx.i.aivencloud.com
ANALYTICS_DB_PORT=16332
ANALYTICS_DB_SSL_CA=/path/to/ca.pem

# Django (Optional)
DEBUG=True
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=127.0.0.1,localhost
```

### Getting Cloud Credentials

**Email team lead:**
```
Subject: CFRMS Cloud Database Access Request

Hi [Team Lead],

I need Aiven MySQL credentials for the CFRMS project.

Name: [Your Name]
GitHub: [Your Username]

Thanks
```

**You'll receive:**
- Database password
- Cloud hostname
- CA certificate (ca.pem)

---

## API Reference

### Example: Demand Forecast

```bash
curl http://localhost:8000/api/analytics/demand-forecast/ \
  -H "Cookie: sessionid=your-session"
```

**Response:**
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

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Can't connect to cloud DB | Check `.env` credentials, verify `ca.pem` path |
| SSL error | Download new `ca.pem` from Aiven console |
| "No such table" | Run `python manage.py migrate --database=analytics` |
| Tests hanging | Use `--keepdb --noinput` flags |
| Need cloud password | Request from team lead |

**Full guide:** [`CONTRIBUTING.md`](CONTRIBUTING.md)

---

## Documentation

### Setup & Configuration
- 📖 [`CLOUD_DATABASE_SETUP.md`](CLOUD_DATABASE_SETUP.md) — Cloud database access guide
- 📖 [`CONTRIBUTING.md`](CONTRIBUTING.md) — Developer setup & workflow

### Analytics & Features
- 📖 [`docs/ANALYTICS_DOCUMENTATION_INDEX.md`](docs/ANALYTICS_DOCUMENTATION_INDEX.md) — **Start here** for complete analytics documentation guide
- 📖 [`docs/ANALYTICS_GUIDE.md`](docs/ANALYTICS_GUIDE.md) — User guide to analytics features
- 📖 [`docs/ADMIN_ANALYTICS.md`](docs/ADMIN_ANALYTICS.md) — Admin dashboard & configuration
- 📖 [`docs/MOCK_DATA.md`](docs/MOCK_DATA.md) — Generating and managing test data
- 📖 [`docs/FACILITY_CALENDAR_GUIDE.md`](docs/FACILITY_CALENDAR_GUIDE.md) — Facility booking calendar & color-coded availability
- 📖 [`docs/IN_APP_HELP_REFERENCE.md`](docs/IN_APP_HELP_REFERENCE.md) — In-app help text and tooltip reference

### Project Specifications (Phase Documentation)
- 📋 [`Group 4-Enterprise-System-Project.docx`](Group 4-Enterprise-System-Project.docx) — Complete project specifications
- 📋 Phase 1: Organizational Problem & System Specification
- 📋 Phase 2: System Design
- 📋 Phase 3: Platform Development
- 📋 Phase 4: Testing & Evaluation
- 📋 Phase 5: Enterprise System Presentation

### Technical Documentation
- 📖 [`PHASE_6_5_2_API_CONTRACT.md`](PHASE_6_5_2_API_CONTRACT.md) — API contracts
- 📖 [`PHASE_6_6_POWERBI_DATA_MODEL.md`](PHASE_6_6_POWERBI_DATA_MODEL.md) — Data model
- 📖 [`PHASE_6_6_SQL_QUERIES.sql`](PHASE_6_6_SQL_QUERIES.sql) — SQL queries

---

## Project Status

| Phase | Status | Completion Date |
|-------|--------|-----------------|
| Phase 1-5 | ✅ Complete | October 2026 |
| Phase 6.5: Analytics API | ✅ Complete | October 2026 |
| Phase 6.6: Power BI Integration | ✅ Complete | October 2026 |
| Phase 6.6: Cloud Database Migration | ✅ Complete | October 2026 |

**System is production-ready. All phases complete.**

---

## Team

**Group 4 - BSIS 3A**
- Gemver Harry Santos
- AJ Pantinople
- Robhie Angel Sevilleno
- Charlene Jane Resuelo
- Eduardo Saavedra
- Olegario Banac III

**Instructor:** Kaye Antoinette Panaligan  
**Organization:** Davao del Sur State College (DSSC)

---

## Security

### ✅ DO
- Keep credentials in `.env` only
- Never commit `.env` to Git
- Use TLS certificate for cloud connection
- Request access through team lead
- Report security issues privately

### ❌ DO NOT
- Share credentials in chat/email
- Hardcode connection strings
- Commit database passwords
- Skip TLS certificate validation
- Delete production data without backup

---

## Contributing

For contribution guidelines, see [`CONTRIBUTING.md`](CONTRIBUTING.md)

- 🔀 Create feature branches from main
- 🧪 Write tests for any code changes
- 📝 Follow PEP 8 style guide
- 🔒 Never commit credentials
- 📋 Reference issues in commits

---

## License

[Specify license - e.g., MIT, Apache 2.0]

---

**Version**: 6.6.0  
**Status**: ✅ Production Ready (Cloud-only)  
**Last Updated**: October 12, 2026

**All developers share one Aiven Cloud MySQL instance. No local database needed.**

For cloud setup, see [`CLOUD_DATABASE_SETUP.md`](CLOUD_DATABASE_SETUP.md)  
For developer setup, see [`CONTRIBUTING.md`](CONTRIBUTING.md)
