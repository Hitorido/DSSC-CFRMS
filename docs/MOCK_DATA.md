# Mock Data Generation Guide

## Overview

Mock (synthetic) data generation provides realistic test data for development, testing, and demonstration without affecting production data. This guide explains how to generate, use, and manage mock data.

## What is Mock Data?

Mock data is automatically generated test data that:
- ✅ Follows realistic booking patterns
- ✅ Has the same structure as real data
- ✅ Is clearly marked as synthetic (`is_synthetic=True`)
- ✅ Can be regenerated anytime without data loss
- ✅ Exists separately from operational data
- ✅ Allows system testing without real users

Example of synthetic data:
```
Reservation: Lab A, Oct 15, 2-3pm, John Smith (synthetic)
Facility: Lab A with 50 capacity, realistic equipment list, is_synthetic=True
User: Dr. Jane Doe, requester role, is_synthetic=True
```

## Generating Mock Data

### Quick Start (Default Settings)

Generate 10 facilities, 50 users, 1000 reservations:

```bash
python manage.py generate_analytics_data
```

### Custom Data Volume

Specify exact counts:

```bash
# Few facilities for quick testing
python manage.py generate_analytics_data --facilities 5 --users 20 --reservations 100

# Medium dataset for realistic testing
python manage.py generate_analytics_data --facilities 15 --users 50 --reservations 1000

# Large dataset for performance testing
python manage.py generate_analytics_data --facilities 30 --users 100 --reservations 5000

# Massive dataset for stress testing
python manage.py generate_analytics_data --facilities 50 --users 200 --reservations 10000
```

### Verbose Output

See detailed progress:

```bash
python manage.py generate_analytics_data --verbosity=2

# Output:
# Generating 10 facilities...
# - Lab A: 50 capacity, Computer Lab
# - Lab B: 40 capacity, Chemistry Lab
# ...
# Generating 50 synthetic users...
# - Dr. Jane Doe (Faculty)
# - John Smith (Student/Requester)
# ...
# Generating 1000 reservations (6 months historical + 3 months forward)
# - Week 1: 125 reservations
# - Week 2: 130 reservations
# ...
# ✓ Complete! Generated synthetic data marked with is_synthetic=True
```

### Generation Options

```bash
python manage.py generate_analytics_data \
  --facilities 20 \           # Number of facilities to create
  --users 50 \                # Number of synthetic users
  --reservations 1000 \       # Number of reservations to generate
  --months-back 6 \           # Historical months (default: 6)
  --months-forward 3 \        # Future months (default: 3)
  --clear-existing false \    # Keep existing synthetic data (default: false, clears it)
  --verbosity 2               # 0=silent, 1=normal, 2=verbose
```

## Generated Data Patterns

### Booking Patterns

The data generator creates realistic booking behavior:

```
Weekday vs. Weekend:
- Monday-Friday: 80% of all bookings (weekdays busier)
- Saturday-Sunday: 20% of all bookings

Time Distribution:
- 8am-12pm: 30% of daily bookings
- 12pm-2pm: 20% of daily bookings (lunch hours lower)
- 2pm-5pm: 40% of daily bookings (peak hours)
- 5pm-6pm: 10% of daily bookings

Booking Duration:
- Short bookings (1 hour): 40%
- Medium bookings (2 hours): 35%
- Long bookings (3+ hours): 25%

Reservation Status:
- Approved: 85% (successful bookings)
- Rejected: 10% (conflicts or policy violations)
- Cancelled: 5% (natural cancellation rate)
```

### Facility Details

Generated facilities have:
- **Name**: Realistic lab/room names (Lab A, Conference Room 1, etc.)
- **Capacity**: 20-150 people based on facility type
- **Equipment**: Lists realistic equipment for the facility type
- **Hours**: 8am-6pm (standard operating hours)
- **Accessibility**: 90% wheelchair accessible
- **Noise Level**: Varies by type (low for offices, high for workshops)
- **Building Code**: Campus building designations
- **Floor Number**: Realistic floor assignments

### User Details

Generated users have:
- **Roles**: Mix of requesters, staff, faculty, and admins
- **Names**: Realistic faculty and student names
- **Affiliations**: Department assignments
- **Email**: Properly formatted email addresses
- **Status**: Active users ready to make reservations

## Data Volume and Performance

### Storage Requirements

| Data Volume | Database Size | Approx. Rows |
|-------------|--------------|--------------|
| Minimal (100 reservations) | 5 MB | 100 |
| Small (1,000 reservations) | 15 MB | 1,000 |
| Medium (5,000 reservations) | 50 MB | 5,000 |
| Large (10,000 reservations) | 100 MB | 10,000 |
| Massive (50,000 reservations) | 500 MB | 50,000 |

### Performance Targets

| Operation | Time | Notes |
|-----------|------|-------|
| Dashboard load | <2 sec | With 5000 reservations |
| Calendar view | <500 ms | One facility, one month |
| System calendar | <1 sec | All facilities |
| Forecast compute | <5 sec | Cached for 1 hour |
| API endpoint | <500 ms | All analytics endpoints |

### Recommended Volumes for Testing

- **Unit Tests**: 100-500 reservations (fast, isolated)
- **Integration Tests**: 1,000-2,000 reservations (realistic without slowdown)
- **Performance Tests**: 5,000+ reservations (stress testing)
- **Demo/Presentation**: 2,000-3,000 reservations (good variety)
- **Development**: 500-1,000 reservations (quick feedback loops)

## Using Mock Data

### Viewing Mock Data

**In Admin Interface:**
1. Go to `/admin`
2. View "Reservations" or "Facilities"
3. All synthetic records show `is_synthetic=True`

**Via Command Line:**
```bash
python manage.py shell

# Count synthetic reservations
>>> from reservations.models import Reservation
>>> Reservation.objects.filter(is_synthetic=True).count()
5000

# View date range
>>> from django.db.models import Min, Max
>>> Reservation.objects.filter(is_synthetic=True).aggregate(
...     Min('reservation_date'), Max('reservation_date')
... )
{'reservation_date__min': datetime.date(2024, 4, 1),
 'reservation_date__max': datetime.date(2024, 12, 31)}
```

### Filtering Mock Data

**Exclude synthetic data from production views:**

```python
# In views.py
from reservations.models import Reservation

# Get only real reservations
real_reservations = Reservation.objects.filter(is_synthetic=False)

# Or exclude synthetic in query results
all_but_synthetic = Reservation.objects.exclude(is_synthetic=True)
```

**In Admin:**
- Use filter: `is_synthetic = False` to see only real data
- Use filter: `is_synthetic = True` to audit synthetic data

### Testing with Mock Data

**Running Tests Against Mock Data:**

```bash
# All tests (includes mock data tests)
python manage.py test --keepdb

# Analytics tests (designed for mock data)
python manage.py test analytics --keepdb

# With coverage
coverage run --source='analytics' manage.py test --keepdb
coverage report
```

**Writing Tests That Use Mock Data:**

```python
# In test file
from reservations.models import Reservation
from django.test import TestCase

class AnalyticsTestCase(TestCase):
    def setUp(self):
        # Ensure synthetic data exists
        Reservation.objects.filter(is_synthetic=False).delete()
        # Generate test data if needed
        self.synthetic = Reservation.objects.filter(is_synthetic=True)
    
    def test_forecast_with_synthetic_data(self):
        # Tests will use existing synthetic data
        self.assertGreater(self.synthetic.count(), 100)
```

## Regenerating Mock Data

### Clear and Regenerate

```bash
# Delete existing synthetic data and generate new
python manage.py generate_analytics_data \
  --facilities 20 \
  --reservations 2000 \
  --clear-existing true
```

### Preserve and Add

```bash
# Add more synthetic data without clearing existing
python manage.py generate_analytics_data \
  --facilities 10 \
  --reservations 1000 \
  --clear-existing false
```

### Selective Deletion

Delete only synthetic data while preserving real data:

```bash
python manage.py shell

# Delete all synthetic reservations
>>> from reservations.models import Reservation
>>> Reservation.objects.filter(is_synthetic=True).delete()
(5000, {'reservations.Reservation': 5000})

# Delete all synthetic facilities
>>> from facilities.models import Facility
>>> Facility.objects.filter(is_synthetic=True).delete()
(20, {'facilities.Facility': 20})

# Delete all synthetic users
>>> from accounts.models import User
>>> User.objects.filter(is_synthetic=True).delete()
(50, {'accounts.User': 50})
```

## Working with Production Data

### Important Rules

⚠️ **DO NOT:**
- Mix synthetic and real data in production queries
- Export synthetic data as real data
- Delete real data (`is_synthetic=False`) by mistake
- Regenerate data without checking `is_synthetic=True` flag

✅ **DO:**
- Always filter by `is_synthetic=False` for real data
- Keep synthetic data separate in development/testing
- Regenerate synthetic data as needed for testing
- Verify all mock data has `is_synthetic=True` flag

### Migration to Production

When deploying analytics to production:

1. **Disable mock data generation** in production settings
2. **Filter out synthetic data** from all production queries
3. **Real data takes time** - expect 2-3 months for patterns to emerge
4. **Fallback gracefully** - analytics use synthetic data if insufficient real data
5. **Monitoring** - track when real data becomes sufficient

## Troubleshooting

### Generation Fails

**Problem**: "Error: Could not create synthetic data"

**Solution**:
```bash
# Check database connection
python manage.py dbshell

# Verify migrations are applied
python manage.py migrate --database=analytics

# Try again with verbose output
python manage.py generate_analytics_data --verbosity=2
```

### Mock Data Not Visible in Dashboard

**Problem**: Dashboard shows "No data" despite generating mock data

**Solution**:
```bash
# Verify mock data was created
python manage.py shell
>>> from reservations.models import Reservation
>>> Reservation.objects.filter(is_synthetic=True).count()
# Should be > 0

# Check date range covers current month
>>> from django.db.models import Min, Max
>>> Reservation.objects.filter(is_synthetic=True).aggregate(
...     Min('reservation_date'), Max('reservation_date')
... )
# Should include today's date

# Flush cache and reload dashboard
>>> from django.core.cache import cache
>>> cache.clear()
```

### Performance Degradation

**Problem**: System running slowly after generating large dataset

**Solution**:
- Reduce data volume: `python manage.py generate_analytics_data --reservations 1000`
- Verify database indexes exist: See ADMIN_ANALYTICS.md
- Check database server resources (CPU, memory, disk)
- Consider using read replicas for analytics queries

### Data Duplication

**Problem**: Running generation multiple times creates duplicates

**Solution**:
```bash
# Use --clear-existing flag
python manage.py generate_analytics_data --clear-existing true

# Or manually delete first
python manage.py shell
>>> from reservations.models import Reservation
>>> Reservation.objects.filter(is_synthetic=True).delete()
```

## Best Practices

### 1. Development Workflow
- Start with 100-500 mock reservations for quick feedback
- Increase to 1000-2000 for realistic testing
- Use 5000+ for performance benchmarking

### 2. Testing Automation
- Keep a stable mock dataset for regression tests
- Regenerate weekly to test generation process
- Version control test fixtures with known data

### 3. Performance Testing
- Use realistic data volume (match production scale)
- Monitor database query performance
- Profile analytics computation time
- Test cache invalidation under load

### 4. Documentation
- Document your chosen data volume for consistency
- Note generation parameters in test setup
- Document any custom data patterns
- Keep changelog of mock data updates

### 5. Cleanup
- Delete mock data when moving to production
- Archive test fixtures for reference
- Don't commit synthetic data to version control
- Preserve real data during migration

## Next Steps

1. Generate initial mock data for your environment
2. Review data patterns: `python manage.py shell`
3. Test dashboards and APIs with mock data
4. Adjust data volume based on performance
5. Set up regular regeneration schedule for testing

## Additional Resources

- **Main Guide**: See ANALYTICS_GUIDE.md for feature usage
- **Admin Guide**: See ADMIN_ANALYTICS.md for administration
- **Code**: `manage.py` command: `analytics/management/commands/generate_analytics_data.py`
- **Models**: `reservations/models.py`, `facilities/models.py`, `accounts/models.py`

