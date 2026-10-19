# ☁️ Cloud Database Setup Guide for Collaborators

**Complete guide for accessing Aiven Cloud MySQL database (no local database needed).**

---

## Overview

The DSSC CFRMS system uses **Aiven Cloud MySQL** as the production database. All collaborators connect to the same cloud instance — no local database setup required.

**Benefits:**
- ✅ Single source of truth for all data
- ✅ Real-time collaboration (all see same data)
- ✅ No local database maintenance
- ✅ Automatic backups & security
- ✅ Same environment for dev & testing

---

## Quick Start (5 minutes)

### 1. Get Credentials from Team Lead

Request access from **team-lead@example.com**:

```
Subject: CFRMS Aiven Database Access Request

Hi [Team Lead],

I need access to the CFRMS Aiven Cloud MySQL database.

Name: [Your Name]
GitHub: [Your Username]
Role: [Developer/QA/etc]

Thanks,
[Your Name]
```

**You'll receive:**
- `ANALYTICS_DB_PASSWORD`
- `ANALYTICS_DB_HOST`
- `ca.pem` file (TLS certificate)

### 2. Add Credentials to `.env`

```env
# Aiven Cloud MySQL (Provided by Team Lead)
ANALYTICS_DB_NAME=dssc_analytics
ANALYTICS_DB_USER=avnadmin
ANALYTICS_DB_PASSWORD=<paste-password-here>
ANALYTICS_DB_HOST=mysql-xxxx.i.aivencloud.com
ANALYTICS_DB_PORT=16332
ANALYTICS_DB_SSL_CA=C:/path/to/ca.pem
```

### 3. Test Connection

```bash
# Run Django shell
python manage.py shell

# Test database connection
>>> from django.db import connections
>>> connections['analytics'].ensure_connection()
# Should return without error

# Verify you can query
>>> from reservations.models import Reservation
>>> Reservation.objects.using('analytics').count()
# Should return a number (e.g., 5000)
```

### 4. Done! ✅

Your development environment is ready. All data is shared with your team.

---

## Detailed Connection Guide

### Prerequisites

1. **Aiven Account Access**
   - Provided by team lead
   - Use Aiven console at https://console.aiven.io

2. **TLS Certificate (ca.pem)**
   - Download from Aiven console
   - Save to your project directory
   - Add path to `.env`

3. **Credentials**
   - Username: `avnadmin`
   - Password: (from team lead)
   - Host: `mysql-xxxx.i.aivencloud.com`
   - Port: `16332`

### Connection Methods

#### Method 1: Django ORM (Recommended for Development)

```python
# In your Django code
from reservations.models import Reservation

# Query the cloud database
reservations = Reservation.objects.using('analytics').all()

# Create, update, delete (if permissions allow)
reservation = Reservation.objects.using('analytics').create(
    facility_id=1,
    requested_by_id=1,
    reservation_date='2026-10-15',
    status='PENDING'
)
```

#### Method 2: Django Shell

```bash
python manage.py shell
```

```python
# Connect to analytics database
from django.db import connections
conn = connections['analytics']

# Test connection
conn.ensure_connection()  # Should succeed

# Query
from facilities.models import Facility
facilities = Facility.objects.using('analytics').all()
print(f"Found {facilities.count()} facilities")
```

#### Method 3: MySQL CLI

```bash
# Connect directly (requires ca.pem)
mysql --host=mysql-xxxx.i.aivencloud.com \
      --port=16332 \
      --user=avnadmin \
      --password \
      --ssl-ca=/path/to/ca.pem \
      dssc_analytics
```

#### Method 4: GUI Tool (MySQL Workbench, DataGrip)

**Connection Settings:**
- Hostname: `mysql-xxxx.i.aivencloud.com`
- Port: `16332`
- Username: `avnadmin`
- Password: (from `.env`)
- Database: `dssc_analytics`
- SSL Mode: `REQUIRED`
- CA Certificate: `/path/to/ca.pem`

---

## Database Structure

### Tables

All data is stored in these tables:

```sql
-- Users & Auth
accounts_user
accounts_user_groups

-- Facilities
facilities_facility
facilities_facilitytype
facilities_facilitymaintenance

-- Reservations
reservations_reservation

-- Notifications
notifications_notification

-- System
django_migrations
django_sessions
auth_group
auth_permission
```

### View Current Schema

```bash
# Show all tables
python manage.py dbshell
> SHOW TABLES;

# Show table structure
> DESCRIBE accounts_user;
> DESCRIBE reservations_reservation;

# Count records
> SELECT COUNT(*) FROM reservations_reservation;
```

---

## Verification Checklist

Before starting development, verify:

- [ ] `.env` file has all `ANALYTICS_DB_*` variables
- [ ] `ca.pem` file exists at specified path
- [ ] Can connect to database: `python manage.py shell`
- [ ] Can query data: `Reservation.objects.using('analytics').count()`
- [ ] Can run migrations: `python manage.py migrate --database=analytics`
- [ ] Can run tests: `python manage.py test --keepdb --noinput`

```bash
# Run all checks at once
python manage.py shell << 'EOF'
from django.db import connections
from reservations.models import Reservation
from facilities.models import Facility

# Test 1: Connection
try:
    connections['analytics'].ensure_connection()
    print("✓ Database connection OK")
except Exception as e:
    print(f"✗ Connection failed: {e}")

# Test 2: Query data
try:
    count = Reservation.objects.using('analytics').count()
    print(f"✓ Can query data ({count} reservations)")
except Exception as e:
    print(f"✗ Query failed: {e}")

# Test 3: Model access
try:
    facility = Facility.objects.using('analytics').first()
    print(f"✓ Can access models ({facility.name if facility else 'empty'})")
except Exception as e:
    print(f"✗ Model access failed: {e}")

print("\nAll checks complete!")
EOF
```

---

## Environment Variables Explained

| Variable | Example | Purpose |
|---|---|---|
| `ANALYTICS_DB_NAME` | `dssc_analytics` | Cloud database name |
| `ANALYTICS_DB_USER` | `avnadmin` | Database username |
| `ANALYTICS_DB_PASSWORD` | `Av*** (long password) | Database password |
| `ANALYTICS_DB_HOST` | `mysql-xxxx.i.aivencloud.com` | Cloud server hostname |
| `ANALYTICS_DB_PORT` | `16332` | Cloud server port |
| `ANALYTICS_DB_SSL_CA` | `C:/path/to/ca.pem` | TLS certificate path |

### Finding These Values

**In Aiven Console:**
1. Log in to https://console.aiven.io
2. Select your MySQL service
3. Go to **Connection Information**
4. Copy: Hostname, Port, User, Password
5. Go to **CA Certificate**
6. Download: `ca.pem`

---

## Common Issues

### Issue 1: "Connection refused"

**Cause:** Wrong hostname or port

**Solution:**
```bash
# Verify Aiven console shows correct host
# Double-check .env values
# Test connectivity
ping mysql-xxxx.i.aivencloud.com
```

### Issue 2: "SSL connection error"

**Cause:** Missing or incorrect certificate

**Solution:**
```bash
# Verify ca.pem exists
ls -la /path/to/ca.pem

# Verify path in .env
grep ANALYTICS_DB_SSL_CA .env

# Test with MySQL CLI
mysql --host=mysql-xxxx.i.aivencloud.com \
      --user=avnadmin \
      --password \
      --ssl-ca=/path/to/ca.pem \
      dssc_analytics -e "SELECT 1"
```

### Issue 3: "Authentication failed"

**Cause:** Wrong password or username

**Solution:**
```bash
# Verify credentials in .env
grep ANALYTICS_DB_USER .env
grep ANALYTICS_DB_PASSWORD .env

# Test with MySQL CLI
mysql --host=mysql-xxxx.i.aivencloud.com \
      --user=avnadmin \
      --password=<your-password> \
      dssc_analytics -e "SELECT 1"
```

### Issue 4: "getaddrinfo failed" or "Can't connect to MySQL server"

**Cause:** DNS resolution failure — machine cannot resolve Aiven hostname

**Solution:**

```bash
# 1. Verify hostname is correct in .env
grep ANALYTICS_DB_HOST .env
# Should show: ANALYTICS_DB_HOST=mysql-xxxx.i.aivencloud.com

# 2. Test DNS resolution
ping mysql-xxxx.i.aivencloud.com
# If fails: DNS resolution issue

# 3. Check network connectivity
# - Verify internet connection
# - Check firewall rules (may block port 16332)
# - If on corporate network: check with IT about Aiven IP whitelisting
# - If on VPN: disconnect and try again
# - Try on mobile hotspot to rule out network-specific issues

# 4. Test with specific IP (if DNS fails)
# Contact team lead for IP address, try:
mysql --host=<aiven-ip-address> \
      --port=16332 \
      --user=avnadmin \
      --password \
      --ssl-ca=/path/to/ca.pem \
      dssc_analytics -e "SELECT 1"

# 5. Verify ca.pem certificate path is correct
ls -la /path/to/ca.pem
# File should exist and be readable

# 6. Try with verbose output
python manage.py shell
>>> from django.db import connections
>>> conn = connections['analytics']
>>> import pymysql.cursors
>>> conn.ensure_connection()  # Shows detailed error if fails
```

**If still failing:**
- Check with team lead if Aiven service is running
- Request new ca.pem certificate
- Try connecting from a different network (coffee shop, home, different computer)
- Contact Aiven support if service appears down

---

### Issue 5: "ModuleNotFoundError: No module named 'django'"

**Cause:** Virtual environment not activated

**Solution:**
```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux

# Verify activation (should show (.venv) prefix)
```

### Issue 6: "No such table"

**Cause:** Migrations not run

**Solution:**
```bash
# Run migrations
python manage.py migrate --database=analytics

# Verify tables exist
python manage.py shell
> from django.db import connections
> conn = connections['analytics']
> conn.cursor().execute("SHOW TABLES")
```

---

## Working with Cloud Data

### Development Workflow

```bash
# 1. Pull latest code
git pull origin main

# 2. Activate environment
source .venv/bin/activate

# 3. Run migrations (if any)
python manage.py migrate --database=analytics

# 4. Run tests
python manage.py test --keepdb --noinput

# 5. Start development
python manage.py runserver

# 6. Make changes
# ... edit files ...

# 7. Test changes
python manage.py test --keepdb --noinput

# 8. Commit
git add .
git commit -m "[feature] Your change"
git push origin feature/your-feature
```

### Querying Cloud Data

```python
# In Python or Django shell
from reservations.models import Reservation
from facilities.models import Facility

# Read operations
all_reservations = Reservation.objects.using('analytics').all()
pending = Reservation.objects.using('analytics').filter(status='PENDING')

# Count
count = Reservation.objects.using('analytics').count()

# Create (if allowed)
new_res = Reservation.objects.using('analytics').create(
    facility_id=1,
    requested_by_id=1,
    reservation_date='2026-10-15',
    status='PENDING'
)

# Update (if allowed)
res = Reservation.objects.using('analytics').get(id=1)
res.status = 'APPROVED'
res.save(using='analytics')

# Delete (if allowed)
res.delete(using='analytics')
```

### Analytics Queries

```python
# KPI calculations (from Phase 6.5)
from analytics.services import get_reservation_kpis

kpis = get_reservation_kpis()
print(kpis)
# Output:
# {
#   'total_reservations': 5000,
#   'approved_count': 2689,
#   'approval_rate': 0.585,
#   'average_days_to_approval': 2.85
# }
```

---

## Best Practices

### DO ✅

- ✅ Use `.using('analytics')` to query cloud database
- ✅ Keep credentials in `.env` (never in code)
- ✅ Test before pushing changes
- ✅ Use migrations for schema changes
- ✅ Pull latest before starting work
- ✅ Communicate with team about large data changes

### DO NOT ❌

- ❌ Commit `.env` file to Git
- ❌ Share database credentials in chat/email
- ❌ Hardcode database connection strings
- ❌ Run migrations without testing
- ❌ Delete production data without backup
- ❌ Make schema changes without team approval

---

## Performance Tips

### Query Optimization

```python
# GOOD: Single database query
facilities = Facility.objects.using('analytics').all()

# BAD: N+1 queries (avoid)
for facility in Facility.objects.using('analytics').all():
    print(facility.reservations.count())  # Database hit per facility

# BETTER: Use select_related() or prefetch_related()
from django.db.models import Prefetch
facilities = Facility.objects.using('analytics').prefetch_related('reservations')
for facility in facilities:
    print(facility.reservations.count())  # No additional queries
```

### Connection Pooling

Django automatically pools connections. No special setup needed.

### Caching

```python
# Use Django cache for repeated queries
from django.core.cache import cache

facilities = cache.get('facilities')
if facilities is None:
    facilities = Facility.objects.using('analytics').all()
    cache.set('facilities', facilities, 300)  # Cache for 5 minutes
```

---

## Monitoring & Debugging

### Check Connection Status

```bash
python manage.py shell
```

```python
from django.db import connections
conn = connections['analytics']

# Check if connected
print(f"Connected: {conn.connection is not None}")

# Get connection info
print(f"Host: {conn.settings_dict['HOST']}")
print(f"Database: {conn.settings_dict['NAME']}")

# Check query count
from django.test.utils import CaptureQueriesContext
with CaptureQueriesContext(conn) as ctx:
    # Your code here
    pass
print(f"Queries executed: {len(ctx)}")
```

### Monitor in Aiven Console

1. Go to https://console.aiven.io
2. Select your MySQL service
3. Go to **Monitoring** tab
4. View:
   - Query count
   - CPU usage
   - Memory usage
   - Network traffic

---

## Backup & Recovery

Aiven automatically backs up your data:
- Daily backups retained for 30 days
- Automated failover if primary fails
- No action needed from developers

**To request a manual backup or restore:**
- Contact team lead
- Provide backup timestamp
- Team lead restores via Aiven console

---

## Team Collaboration

### Shared Development

All collaborators see the same cloud data:

```
Developer A                Developer B
   │                          │
   └─── Aiven Cloud MySQL ───┘
        (Single source of truth)
```

### Avoiding Conflicts

1. **Pull latest before starting**
   ```bash
   git pull origin main
   ```

2. **Create feature branch**
   ```bash
   git checkout -b feature/your-feature
   ```

3. **Test against cloud database**
   ```bash
   python manage.py test --keepdb --noinput
   ```

4. **Commit & push**
   ```bash
   git commit -m "[feature] Description"
   git push origin feature/your-feature
   ```

5. **Create pull request**
   - Link to issue
   - Describe changes
   - Request review

---

## Troubleshooting Checklist

| Problem | Check | Solution |
|---|---|---|
| Can't connect | `.env` values | Copy from Aiven console |
| SSL error | `ca.pem` path | Download new certificate |
| Auth failed | Password | Request new from team lead |
| No tables | Migrations | Run `python manage.py migrate` |
| No data | Database state | Check Aiven console |
| Slow queries | N+1 queries | Use `select_related()` / `prefetch_related()` |
| Test failures | Database state | Run with `--keepdb` flag |

---

## Support & Questions

### Getting Help

1. **Check this guide first**
2. **Review error messages carefully**
3. **Test with MySQL CLI**: `mysql --host=... --user=... --password`
4. **Check Aiven console** for service status
5. **Ask team lead** for credential issues

### Report Issues

Include:
- Error message (exact text)
- `.env` values (WITHOUT password)
- Steps to reproduce
- What you've already tried

---

## Quick Reference

### Most Common Commands

```bash
# Connect to cloud database
python manage.py shell

# Run migrations
python manage.py migrate --database=analytics

# Run tests
python manage.py test --keepdb --noinput

# Query data
python manage.py shell
> from reservations.models import Reservation
> Reservation.objects.using('analytics').count()

# Verify connection
mysql --host=mysql-xxxx.i.aivencloud.com \
      --user=avnadmin \
      --password \
      --ssl-ca=/path/to/ca.pem \
      dssc_analytics -e "SELECT 1"
```

---

**Version**: 1.0  
**Last Updated**: October 12, 2026  
**For**: DSSC CFRMS v6.6.0 (Cloud Database Only)

Questions? Contact: team-lead@example.com

