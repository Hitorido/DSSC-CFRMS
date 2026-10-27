# Admin Analytics Dashboard Guide

## For System Administrators

This guide provides detailed instructions for managing and interpreting the analytics dashboard from an administrative perspective.

## Admin Dashboard Overview

The admin dashboard provides comprehensive system-wide visibility into facility usage and performance.

### Dashboard Sections

#### 1. Analytics Overview Card
Displays key system metrics:

```
Total Reservations: [count]
- Shows complete system booking volume
- Includes all statuses (approved, rejected, cancelled)

Average Occupancy %: [percentage]
- Calculates facility utilization across the system
- Based on facility capacity and reservation duration
- Target: 60-80% for healthy utilization

Peak Facility: [facility name]
- Most frequently booked facility in the system
- Indicates high-demand areas
- Use for capacity planning

Top-Booked Time Slot: [hour]
- Hour of the day with most bookings
- Helps plan maintenance windows
- Typically 2-5pm in academic settings
```

#### 2. Demand Forecast Chart
Interactive line chart showing historical and predicted demand:

- **Historical Data (6 months)**: Solid line showing actual reservation counts
- **Forecast Data (3 months forward)**: Dashed line showing predictions
- **Confidence Interval**: Shaded area showing prediction range
- **Legend**: Clearly distinguishes historical vs. forecasted data
- **Data Freshness**: Shows when forecast was last computed

**Using the Forecast:**
- Identify peak demand periods for planning
- Spot seasonal trends (e.g., higher demand in fall)
- Plan infrastructure changes for predicted high-demand months
- Schedule maintenance during forecasted low-demand periods

#### 3. System Reservations Calendar
Full-month view of all facility reservations:

- **Color-coded Days**: Same system as facility calendars
- **Hover Tooltips**: Shows all reservations and maintenance for the day
- **Navigation**: Move between months to view trends
- **System-wide View**: Combines all facilities into one calendar
- **Maintenance Display**: Distinguishes maintenance from reservations

**Planning with the Calendar:**
- Identify consistently busy periods across all facilities
- Spot gaps for facility upgrades or maintenance
- Validate that forecasts align with actual patterns
- Plan facility closures or maintenance windows

#### 4. Recommendations Section
Prioritized, actionable recommendations based on analytics:

Each recommendation card shows:
- **Title**: Short description of the recommendation
- **Description**: Detailed context and reasoning
- **Action**: Specific next step to take
- **Impact**: Expected benefit of implementation
- **Priority Badge**: HIGH, MEDIUM, or LOW

**Recommendation Types:**
1. **Capacity Expansion** (HIGH priority)
   - Triggered when: Facility occupancy >80%
   - Action: Review facility upgrade or additional facility
   - Impact: Reduced booking conflicts, improved service

2. **Maintenance Windows** (MEDIUM priority)
   - Triggered when: Low-occupancy hours identified
   - Action: Schedule maintenance during identified periods
   - Impact: Zero disruption to facility availability

3. **Extended Hours** (MEDIUM priority)
   - Triggered when: Peak days >70% weekday bookings
   - Action: Consider expanding facility hours on busy days
   - Impact: Increased accessibility, reduced wait times

4. **Equipment Maintenance** (HIGH priority)
   - Triggered when: Equipment usage >85%
   - Action: Schedule preventive maintenance checks
   - Impact: Reduced unexpected equipment downtime

5. **Seasonal Planning** (LOW priority)
   - Triggered when: Clear seasonal patterns detected
   - Action: Adjust staffing and resources seasonally
   - Impact: Better resource utilization, cost savings

**Managing Recommendations:**
- Implement HIGH priority recommendations immediately
- Plan MEDIUM priority recommendations in current quarter
- Consider LOW priority recommendations for long-term planning
- Track which recommendations have been implemented

#### 5. Data Freshness Indicator
Shows when analytics were last computed:
- "Last updated 5 minutes ago" indicates fresh data
- "Last updated 2 hours ago" indicates potentially stale data
- Admins can manually trigger cache refresh for immediate updates

#### 6. Synthetic Data Notice
If system shows "Displaying synthetic data for demonstration":
- System has insufficient operational data
- All analytics use generated test data
- Patterns are realistic but not actual
- Use for development and testing only
- Real operational data will replace this once sufficient reservations exist

## Analytics Computations

### How Analytics Are Calculated

#### Occupancy Percentage
```
Occupancy % = (Total Reserved Hours) / (Total Available Hours)

Example:
- Facility capacity: 50 people
- Available hours: 8am-6pm = 10 hours/day
- Total available person-hours: 50 × 10 = 500
- Reserved person-hours: 375
- Occupancy: 375/500 = 75%
```

#### Peak Hours
```
Analysis Method:
1. Count reservations by hour (0-23)
2. Identify top 3 hours with most bookings
3. Return with booking counts

Typical Result:
- 2pm: 120 bookings
- 3pm: 115 bookings
- 4pm: 105 bookings
```

#### Peak Days
```
Analysis Method:
1. Count reservations by day of week (Mon-Sun)
2. Return all 7 days ranked by booking count

Typical Pattern:
- Monday-Friday: 80% of bookings
- Saturday-Sunday: 20% of bookings
```

#### Demand Forecast
```
Forecast Method:
1. Analyze last 6 months of reservation data
2. Compute monthly trends and aggregates
3. Apply moving average or linear trend
4. Extrapolate 3 months forward
5. Return historical data + forecast + confidence intervals

Requirements:
- Minimum 4 weeks of data for forecast
- Better accuracy with 6+ months of data
- Seasonal patterns visible after 12 months of data
```

## Advanced Admin Functions

### Cache Management

Analytics are cached for 1 hour to optimize performance.

**View cache status:**
```bash
python manage.py shell
>>> from django.core.cache import cache
>>> cache.keys('analytics*')
```

**Manually flush analytics cache:**
```bash
python manage.py shell
>>> from analytics.utils import invalidate_analytics_cache
>>> invalidate_analytics_cache()
>>> print("Cache flushed - dashboard will update on next load")
```

**Manual Cache Flush Endpoint (Admin Only):**
```
POST /api/analytics/clear-cache/
Response: {"status": "success", "message": "Cache cleared"}
```

### Monitoring Analytics

#### Check Analytics Computation Time
Monitor dashboard load performance:
- Target: Dashboard renders in <2 seconds
- If slower: Check database indexes, review query performance

#### Verify Data Quality
```bash
# Check synthetic data count
python manage.py shell
>>> from reservations.models import Reservation
>>> Reservation.objects.filter(is_synthetic=True).count()

# Check data date range
>>> from django.db.models import Min, Max
>>> Reservation.objects.aggregate(Min('reservation_date'), Max('reservation_date'))
```

#### Monitor Forecast Accuracy
Track forecast vs. actual over time:
1. Record the 3-month forecast prediction
2. After 3 months, compare prediction vs. actual
3. Compute Mean Absolute Percentage Error (MAPE)
4. Adjust forecast parameters if MAPE >25%

### Database Indexes

Verify analytics-specific indexes exist:

```sql
-- Reservation indexes for analytics queries
SHOW INDEX FROM reservations_reservation WHERE Key_name LIKE '%facility%'
SHOW INDEX FROM reservations_reservation WHERE Key_name LIKE '%created%'

-- Facility indexes
SHOW INDEX FROM facilities_facility WHERE Key_name LIKE '%noise%'
SHOW INDEX FROM facilities_facility WHERE Key_name LIKE '%building%'
```

Expected indexes:
- `(facility, reservation_date, status)` - Calendar queries
- `(created_at)` - Date range queries
- `(noise_level, capacity)` - Facility analytics
- `(building_code, floor_number)` - Location-based queries

## Troubleshooting

### Dashboard Shows No Data

**Problem**: Analytics dashboard is empty or shows 0 values

**Solution**:
1. Verify reservations exist: `Reservation.objects.count()`
2. Check date range: Forecast requires last 6 months of data
3. Ensure date range is correct in filters
4. Manually flush cache: `invalidate_analytics_cache()`

### Forecast Appears Flat

**Problem**: Forecast line shows no variation

**Solution**:
1. Check historical data volume (need 6+ weeks minimum)
2. Verify seasonal patterns exist in data
3. Consider changing forecast period (3 vs. 6 months)
4. If synthetic data, patterns are intentionally flat - use real data for accuracy

### Recommendations Not Appearing

**Problem**: Recommendations section is empty

**Solution**:
1. Verify sufficient reservation data exists
2. Ensure facilities have realistic occupancy patterns
3. Check that facility details are complete (capacity, type, etc.)
4. Flush cache and reload: `invalidate_analytics_cache()`

### Performance Issues

**Problem**: Dashboard loads slowly (>5 seconds)

**Solution**:
1. Check database connection: `python manage.py dbshell`
2. Verify indexes: `SHOW INDEX FROM reservations_reservation`
3. Monitor query execution: Django Debug Toolbar
4. Consider reducing forecast period or data range
5. Check server resources (CPU, memory, disk)

### Synthetic Data Not Generating

**Problem**: Mock data command fails

**Solution**:
```bash
# Generate with verbose output
python manage.py generate_analytics_data --verbosity=2

# Specify custom data volume
python manage.py generate_analytics_data --facilities 20 --reservations 1000

# Check existing synthetic data
python manage.py shell
>>> from reservations.models import Reservation
>>> Reservation.objects.filter(is_synthetic=True).count()
```

## Best Practices for Admins

### 1. Regular Monitoring
- Check dashboard daily for system health
- Review recommendations weekly
- Verify forecast accuracy monthly
- Monitor cache hit rates

### 2. Data Management
- Regenerate synthetic data quarterly for testing
- Keep operational data separate from test data
- Archive old reservation data for historical analysis
- Maintain database backups before major changes

### 3. Performance Optimization
- Keep database indexes up-to-date
- Monitor query performance trends
- Scale database if sustained >100 bookings/day
- Consider read replicas for analytics queries

### 4. User Communication
- Educate staff on how to interpret recommendations
- Provide quarterly reports on facility usage trends
- Highlight seasonal patterns and upcoming changes
- Document implemented recommendations and their impact

### 5. Data Quality
- Periodically audit facility details (capacity, equipment)
- Verify reservation data accuracy
- Monitor for data entry errors in facility information
- Ensure maintenance records are up-to-date

## API Integration for Admins

All analytics endpoints require admin authentication:

```bash
# Example: Get recommendations via API
curl http://localhost:8000/api/analytics/recommendations/ \
  -H "Cookie: sessionid=your-admin-session"

# Response: JSON array of recommendations
{
  "recommendations": [
    {
      "priority": "HIGH",
      "title": "Expand Lab Capacity",
      "description": "Lab A shows >80% occupancy",
      "action": "Review capacity expansion options",
      "impact": "Reduce booking conflicts by estimated 30%"
    }
  ]
}
```

Available endpoints:
- `GET /api/analytics/demand-forecast/`
- `GET /api/analytics/peak-hours/`
- `GET /api/analytics/occupancy-by-facility/`
- `GET /api/analytics/recommendations/`
- `GET /api/analytics/system-calendar/?month=2024-12`
- `POST /api/analytics/clear-cache/` (flush cache)

## Configuration

### Forecast Parameters

Edit `config/settings.py` to customize:

```python
# Forecast months to analyze
ANALYTICS_FORECAST_HISTORY_MONTHS = 6

# Forecast periods to project
ANALYTICS_FORECAST_PERIODS = 3

# Cache TTL (seconds)
ANALYTICS_CACHE_TTL = 3600

# Min data points for forecast
ANALYTICS_MIN_DATA_POINTS = 20
```

### Recommendation Thresholds

```python
# Edit analytics/services.py to adjust triggers

OCCUPANCY_THRESHOLD_HIGH = 0.80  # 80% for capacity expansion
EQUIPMENT_USAGE_THRESHOLD = 0.85  # 85% for maintenance alert
PEAK_DAY_THRESHOLD = 0.70  # 70% weekday for extended hours
```

## Support & Escalation

For analytics issues:
1. Check troubleshooting section above
2. Review logs: `tail -f /var/log/dssc-cfrms/analytics.log`
3. Contact development team with:
   - Dashboard screenshot
   - Specific metric or issue
   - Steps to reproduce
   - Data volume (# of reservations)

## Next Steps

1. Review current recommendations and plan implementation
2. Set up weekly monitoring schedule
3. Document facility utilization baselines
4. Plan quarterly analytics reviews with stakeholders
5. Configure custom forecast parameters if needed

