# Analytics Features Guide

## Overview

The DSSC CFRMS Analytics Suite provides real-time insights into facility usage, demand patterns, and predictive forecasting. This guide explains how to use and interpret the analytics features.

## Core Analytics Components

### 1. Dashboard Analytics

The system provides role-based analytics dashboards:

#### Admin Dashboard
Displays system-wide analytics including:
- **Total Reservations**: Complete count of all reservations in the system
- **Average Occupancy**: System-wide facility occupancy percentage
- **Peak Facility**: Most frequently booked facility
- **Top-Booked Time Slot**: Hour with highest booking volume

#### Staff Dashboard
Displays operational analytics for assigned facilities:
- **Today's Operations**: Reservation count and busiest facility for today
- **Next 3 Hours Occupancy**: Real-time preview of facility availability
- **Assigned Facility Alerts**: Maintenance schedules and fully booked hours
- **Peak Hours This Week**: Mini-chart showing busy periods

### 2. Facility Booking Calendar

The color-coded facility booking calendar provides visual occupancy status:

#### Color Coding
- **GREEN (0-33%)**: Low occupancy, facility is available
- **YELLOW (34-66%)**: Moderate occupancy, some availability remains
- **RED (67-100%)**: High occupancy, limited availability
- **GRAY**: Facility unavailable or maintenance scheduled

#### Using the Calendar
1. Navigate to a facility's booking page
2. View the current month's calendar with color-coded days
3. Hover over any day to see reservations and maintenance records
4. Use previous/next navigation to explore other months
5. Tooltips show:
   - Time slots booked
   - Requester names (if visible to your role)
   - Reservation status
   - Maintenance windows and details

### 3. Demand Forecasting

The system uses advanced statistical methods to predict future facility demand:

#### How Forecasting Works
- **Historical Analysis**: Examines 6 months of past reservation data
- **Trend Detection**: Identifies patterns in booking behavior
- **Forward Projection**: Extrapolates 3 months into the future
- **Confidence Intervals**: Provides upper/lower bounds on predictions

#### Forecast Interpretation
- Solid lines represent historical data
- Dashed lines represent forecast projections
- Wider bands indicate lower confidence in the forecast
- X-axis shows months, Y-axis shows reservation count

#### Using Forecasts
- Plan capacity expansion for high-demand periods
- Schedule maintenance during predicted low-demand windows
- Allocate resources based on expected peak periods
- Identify seasonal patterns and trends

### 4. Recommendations

The system generates prioritized, actionable recommendations based on analytics:

#### Recommendation Priority Levels
- **HIGH**: Immediate action recommended (e.g., >80% facility occupancy)
- **MEDIUM**: Plan for implementation (e.g., seasonal patterns detected)
- **LOW**: Consider for future planning

#### Types of Recommendations
1. **Capacity Expansion**: High-occupancy facilities (>80%)
   - Action: Review facility upgrade options
   - Impact: Increased availability for high-demand periods

2. **Maintenance Scheduling**: Low-occupancy hours identified
   - Action: Schedule maintenance during off-peak times
   - Impact: Minimized disruption to facility availability

3. **Extended Hours**: Peak days identified (>70% weekday bookings)
   - Action: Consider extending facility hours on busy days
   - Impact: Reduced booking conflicts

4. **Equipment Maintenance**: Heavy equipment usage (>85%)
   - Action: Schedule equipment maintenance checks
   - Impact: Reduced equipment downtime

5. **Seasonal Planning**: Seasonal patterns detected
   - Action: Adjust staffing and resources seasonally
   - Impact: Better resource allocation

### 5. Analytics API Endpoints

For developers and Power BI integration:

```
GET /api/analytics/demand-forecast/
  Query params: ?months=6&facility_id=5
  Returns: historical data, forecast, confidence intervals

GET /api/analytics/peak-hours/
  Returns: Top 3 peak hours with booking counts

GET /api/analytics/occupancy-by-facility/
  Returns: All facilities ranked by occupancy percentage

GET /api/analytics/recommendations/
  Returns: Prioritized recommendations

GET /api/analytics/system-calendar/?month=2024-12
  Returns: System-wide calendar data
```

## Interpreting Charts

### Demand Forecast Chart
- **X-axis**: Month (YYYY-MM format)
- **Y-axis**: Expected reservation count
- **Solid Line**: Historical monthly bookings (accurate data)
- **Dashed Line**: Forecasted bookings (prediction)
- **Shaded Area**: Confidence interval (upper/lower bounds)

### Peak Hours Chart
- Shows which hours of the day are busiest
- Top 3 hours are highlighted
- Helps identify when to schedule maintenance or extend hours

### Occupancy Chart
- Ranks all facilities by current occupancy percentage
- Helps identify capacity constraints
- Guides resource allocation decisions

## Working with Synthetic Data

Some systems may display synthetic (test) data, clearly marked as "Displaying synthetic data for demonstration."

Synthetic data:
- Follows realistic booking patterns
- Has the same structure as operational data
- Allows system testing without production data
- Can be regenerated anytime without data loss

To generate new synthetic data:
```bash
python manage.py generate_analytics_data
```

## Data Freshness

Analytics dashboards include a "Last updated" timestamp indicating when data was last computed. 

- Standard refresh: Every 1 hour (cached)
- Manual refresh: Available to admins via cache flush endpoint
- Real-time APIs: Refresh on-demand

## Tips for Using Analytics

### For Facility Managers
1. Monitor occupancy trends monthly
2. Plan maintenance during predicted low-demand periods
3. Use recommendations to improve facility utilization
4. Review seasonal patterns for staffing decisions

### For System Administrators
1. Monitor system-wide demand patterns
2. Watch for outlier facilities (very high/low usage)
3. Use forecast data to plan infrastructure changes
4. Track recommendation implementation impact

### For Operations Staff
1. Check today's operations card each morning
2. Monitor busiest facility alerts
3. Plan activities around peak hours
4. Review next 3 hours to prepare for coming demand

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Calendar shows no data | Verify reservations exist, check date range |
| Forecast appears flat | Need at least 6 weeks of historical data |
| Recommendations are generic | System may lack sufficient patterns in data |
| Dashboard loading slow | Try refreshing after 1 minute (cache update) |
| Numbers seem incorrect | Verify date filters and facility selection |

## Performance Notes

- Dashboard loads in <2 seconds
- Calendar loads in <500ms
- Forecast computation takes <5 seconds (results cached)
- API endpoints respond in <500ms

## Data Privacy

- Requestors see only their own reservations in tooltips
- Staff see all reservations for assigned facilities
- Admins see system-wide data
- All permission checks enforced in views and APIs

## Next Steps

- Review your facility's occupancy trends
- Implement high-priority recommendations
- Schedule maintenance during low-occupancy periods
- Monitor forecast accuracy over time

For questions or issues, contact your system administrator.
