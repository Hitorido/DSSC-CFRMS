# Analytics Documentation Index

Complete guide to all analytics and facility calendar documentation for the DSSC CFRMS system.

## Quick Navigation

| Document | Purpose | Audience | Read Time |
|----------|---------|----------|-----------|
| [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md) | System features overview and usage | All users | 15 min |
| [ADMIN_ANALYTICS.md](ADMIN_ANALYTICS.md) | Admin dashboard and configuration | Admins/Managers | 20 min |
| [MOCK_DATA.md](MOCK_DATA.md) | Test data generation guide | Developers/QA | 15 min |
| [FACILITY_CALENDAR_GUIDE.md](FACILITY_CALENDAR_GUIDE.md) | Calendar navigation and booking | Requestors/Staff | 10 min |
| [IN_APP_HELP_REFERENCE.md](IN_APP_HELP_REFERENCE.md) | Detailed help text reference | Developers/Content team | 30 min |

---

## Documentation Overview

### For End Users

**Start here if you want to:**
- Learn how to book facilities
- Understand color-coded availability
- Interpret occupancy percentages
- Find the best time to reserve

**Read:** [FACILITY_CALENDAR_GUIDE.md](FACILITY_CALENDAR_GUIDE.md)
- How to read calendar colors
- Using hover tooltips
- Finding available slots
- Tips for successful booking
- Common questions and answers

---

### For System Users (All Roles)

**Start here if you want to:**
- Understand analytics features
- Interpret charts and forecasts
- Understand recommendations
- Use APIs for data access

**Read:** [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md)
- Dashboard overview
- Facility booking calendar guide
- Demand forecasting explanation
- Recommendation types
- Chart interpretation
- Data freshness and caching
- Troubleshooting guide

---

### For Staff Members

**Start here if you want to:**
- Manage today's operations
- Respond to alerts
- Plan maintenance windows
- Review recommendations
- Monitor facility usage

**Section in:** [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md) → Staff Dashboard
- Today's operations metrics
- Facility alerts and notifications
- Peak hours analysis
- Equipment maintenance tracking
- Operational planning

---

### For Facility Managers & Admins

**Start here if you want to:**
- Monitor system-wide analytics
- Make capacity planning decisions
- Configure analytics settings
- Manage cache and data
- Interpret advanced metrics

**Read:** [ADMIN_ANALYTICS.md](ADMIN_ANALYTICS.md)
- Admin dashboard components
- Analytics computation methods
- Cache management
- Performance optimization
- Troubleshooting procedures
- Advanced configuration

**Secondary read:** [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md) → Admin Dashboard
- Dashboard metrics overview
- Demand forecast interpretation
- System calendar navigation
- Recommendation action items

---

### For Developers & QA

**For Development Setup:**
- See [CLOUD_DATABASE_SETUP.md](../CLOUD_DATABASE_SETUP.md)
- See [CONTRIBUTING.md](../CONTRIBUTING.md)

**For Testing Analytics:**
- See [MOCK_DATA.md](MOCK_DATA.md)
  - Data generation commands
  - Performance benchmarks
  - Data volume guidelines
  - Testing patterns

**For Understanding In-App Text:**
- See [IN_APP_HELP_REFERENCE.md](IN_APP_HELP_REFERENCE.md)
  - Dashboard help text
  - Tooltip content
  - Calendar legends
  - Alert definitions

---

## Feature Documentation Map

### Facility Booking Calendar

**What it is:** Visual, color-coded view of facility availability by day

**Documentation:**
1. [FACILITY_CALENDAR_GUIDE.md](FACILITY_CALENDAR_GUIDE.md) ← **Start here**
2. [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md#3-facility-booking-calendar)
3. [IN_APP_HELP_REFERENCE.md](IN_APP_HELP_REFERENCE.md#facility-booking-calendar)

**Color Codes:**
```
🟢 GREEN  (0-33%)   — Low occupancy, book freely
🟡 YELLOW (34-66%)  — Medium occupancy, some slots available
🔴 RED    (67-100%) — High occupancy, few slots available
⚫ GRAY    —         — Unavailable/maintenance
```

**Key Features:**
- Calendar navigation (previous/next month)
- Hover tooltips showing reservations and maintenance
- Occupancy percentage calculation
- Day highlighting (today, past, future)

---

### Predictive Analytics

**What it is:** System predicts future facility demand based on historical data

**Documentation:**
1. [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md#3-demand-forecasting) ← **Start here**
2. [ADMIN_ANALYTICS.md](ADMIN_ANALYTICS.md#demand-forecast-chart-section)
3. [IN_APP_HELP_REFERENCE.md](IN_APP_HELP_REFERENCE.md#prediction--analytics-features)

**Key Metrics:**
- Monthly demand forecast (3 months forward)
- Peak hours (hourly booking distribution)
- Peak days (daily booking distribution)
- Confidence intervals and accuracy estimates

**Algorithms Used:**
- Linear regression for trends
- Moving averages for smoothing
- Seasonal decomposition for patterns
- Exponential smoothing for predictions

---

### Prescriptive Analytics

**What it is:** System generates actionable recommendations based on analytics

**Documentation:**
1. [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md#4-recommendations) ← **Start here**
2. [ADMIN_ANALYTICS.md](ADMIN_ANALYTICS.md#recommendation-types)
3. [IN_APP_HELP_REFERENCE.md](IN_APP_HELP_REFERENCE.md#recommendations-section)

**Recommendation Types:**
1. Capacity expansion (high occupancy)
2. Maintenance windows (low-occupancy hours)
3. Extended hours (peak days)
4. Equipment maintenance (heavy usage)
5. Seasonal planning (patterns detected)

**Priority Levels:**
- 🔴 HIGH — Immediate action
- 🟡 MEDIUM — Plan for implementation
- 🟢 LOW — Long-term consideration

---

### System-Wide Reservations Calendar

**What it is:** Admin/staff view showing all facility reservations for a month

**Documentation:**
1. [ADMIN_ANALYTICS.md](ADMIN_ANALYTICS.md#system-reservations-calendar-section)
2. [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md#3-facility-booking-calendar)
3. [IN_APP_HELP_REFERENCE.md](IN_APP_HELP_REFERENCE.md#system-reservations-calendar)

**Features:**
- Day-by-day view of all reservations
- Event count per day
- Drill-down to detailed view
- Maintenance visibility
- System-wide trend analysis

---

### Analytics API Endpoints

**What it is:** REST APIs for programmatic access to analytics data

**Documentation:**
1. [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md#5-analytics-api-endpoints) ← **Start here**
2. [ADMIN_ANALYTICS.md](ADMIN_ANALYTICS.md#api-integration-for-admins)

**Available Endpoints:**
```
GET /api/analytics/demand-forecast/
GET /api/analytics/peak-hours/
GET /api/analytics/occupancy-by-facility/
GET /api/analytics/recommendations/
GET /api/analytics/system-calendar/
POST /api/analytics/clear-cache/ (admin only)
```

**Authentication:** All endpoints require admin role

---

### Mock Data Generation

**What it is:** Realistic synthetic data for testing and demonstration

**Documentation:**
1. [MOCK_DATA.md](MOCK_DATA.md) ← **Start here**
2. [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md#working-with-synthetic-data)

**Generation Command:**
```bash
python manage.py generate_analytics_data --facilities 20 --reservations 2000
```

**Data Patterns:**
- Weekday vs. weekend distribution
- Peak hour clustering
- Realistic cancellation rates
- Equipment-dependent variations
- Seasonal patterns

---

### Data Freshness & Caching

**What it is:** System caches analytics for 1 hour to optimize performance

**Documentation:**
1. [IN_APP_HELP_REFERENCE.md](IN_APP_HELP_REFERENCE.md#data-freshness--caching)
2. [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md#data-freshness)
3. [ADMIN_ANALYTICS.md](ADMIN_ANALYTICS.md#cache-management)

**Cache Details:**
- TTL: 1 hour
- Manual refresh available (admin only)
- Automatic invalidation on data changes
- Last update timestamp visible on dashboard

---

## Common Tasks

### "I need to book a facility"
1. Read: [FACILITY_CALENDAR_GUIDE.md](FACILITY_CALENDAR_GUIDE.md)
2. Look for green/yellow days
3. Hover to check specific times
4. Click "Request this facility"

### "I need to understand why a facility is RED"
1. Read: [FACILITY_CALENDAR_GUIDE.md](FACILITY_CALENDAR_GUIDE.md#understanding-the-calendar-colors)
2. Hover over the day to see reservations
3. Check [IN_APP_HELP_REFERENCE.md](IN_APP_HELP_REFERENCE.md) for interpretation

### "I need to plan maintenance"
1. Read: [ADMIN_ANALYTICS.md](ADMIN_ANALYTICS.md)
2. Look for green/yellow recommendations for "Maintenance Windows"
3. Check system calendar for identified low-occupancy periods
4. Schedule maintenance during recommended hours

### "I need to understand demand forecast"
1. Read: [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md#3-demand-forecasting)
2. Review: [ADMIN_ANALYTICS.md](ADMIN_ANALYTICS.md#demand-forecast-chart-section)
3. Check: [IN_APP_HELP_REFERENCE.md](IN_APP_HELP_REFERENCE.md#prediction--analytics-features)

### "I need to generate test data"
1. Read: [MOCK_DATA.md](MOCK_DATA.md#generating-mock-data)
2. Run: `python manage.py generate_analytics_data`
3. Verify: `python manage.py shell` and check data

### "I need to troubleshoot analytics issues"
1. Check: [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md#troubleshooting)
2. Check: [ADMIN_ANALYTICS.md](ADMIN_ANALYTICS.md#troubleshooting)
3. Check: [MOCK_DATA.md](MOCK_DATA.md#troubleshooting)

---

## Performance Targets

All documented analytics features target these performance metrics:

| Operation | Target | Status |
|-----------|--------|--------|
| Facility calendar load | < 500ms | ✅ |
| System calendar load | < 1 second | ✅ |
| Admin dashboard render | < 2 seconds | ✅ |
| Forecast computation | < 5 seconds | ✅ (cached) |
| API endpoint response | < 500ms | ✅ |
| Database indexes | Optimized | ✅ |

See [ADMIN_ANALYTICS.md](ADMIN_ANALYTICS.md#database-indexes) for indexing strategy.

---

## Frequently Asked Questions

**Q: What's the difference between synthetic and real data?**
A: See [MOCK_DATA.md](MOCK_DATA.md#what-is-mock-data) and [IN_APP_HELP_REFERENCE.md](IN_APP_HELP_REFERENCE.md#synthetic-vs-real-data)

**Q: How often is analytics data updated?**
A: See [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md#data-freshness) - Updated hourly, cached for 1 hour

**Q: Why is the forecast flat or seems inaccurate?**
A: See [MOCK_DATA.md](MOCK_DATA.md#mock-data-not-visible-in-dashboard) troubleshooting

**Q: How do I interpret the color-coded calendar?**
A: See [FACILITY_CALENDAR_GUIDE.md](FACILITY_CALENDAR_GUIDE.md#understanding-the-calendar-colors)

**Q: What do recommendations mean and should I follow them?**
A: See [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md#4-recommendations) - Recommendations are suggestions, not directives

**Q: How is occupancy calculated?**
A: See [FACILITY_CALENDAR_GUIDE.md](FACILITY_CALENDAR_GUIDE.md#how-occupancy-is-calculated)

**Q: Can I access analytics data via API?**
A: Yes, see [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md#5-analytics-api-endpoints) for endpoints

**Q: How do I generate test data?**
A: See [MOCK_DATA.md](MOCK_DATA.md#generating-mock-data)

---

## Support & Resources

**For Requestors/Users:**
- [FACILITY_CALENDAR_GUIDE.md](FACILITY_CALENDAR_GUIDE.md)
- [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md)

**For Staff Members:**
- [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md)
- [IN_APP_HELP_REFERENCE.md](IN_APP_HELP_REFERENCE.md)

**For Facility Managers:**
- [ADMIN_ANALYTICS.md](ADMIN_ANALYTICS.md)
- [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md)

**For Developers:**
- [MOCK_DATA.md](MOCK_DATA.md)
- [IN_APP_HELP_REFERENCE.md](IN_APP_HELP_REFERENCE.md)
- [CLOUD_DATABASE_SETUP.md](../CLOUD_DATABASE_SETUP.md)
- [CONTRIBUTING.md](../CONTRIBUTING.md)

---

## Related Documentation

**Project Overview:**
- [README.md](../README.md)

**Setup & Configuration:**
- [CLOUD_DATABASE_SETUP.md](../CLOUD_DATABASE_SETUP.md)
- [CONTRIBUTING.md](../CONTRIBUTING.md)

**Performance & Optimization:**
- [PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md)
- [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)

**Database & Data:**
- [MOCK_DATA.md](MOCK_DATA.md)

---

## Document Versioning

| Document | Last Updated | Version | Status |
|----------|--------------|---------|--------|
| ANALYTICS_GUIDE.md | Oct 2026 | 2.0 | ✅ Current |
| ADMIN_ANALYTICS.md | Oct 2026 | 2.0 | ✅ Current |
| MOCK_DATA.md | Oct 2026 | 2.0 | ✅ Current |
| FACILITY_CALENDAR_GUIDE.md | Oct 2026 | 1.0 | ✅ Current |
| IN_APP_HELP_REFERENCE.md | Oct 2026 | 1.0 | ✅ Current |

---

## How to Use This Index

1. **First time?** Start with [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md) for overview
2. **Need specific help?** Use the table of contents above
3. **Implementing features?** See "Feature Documentation Map"
4. **Troubleshooting?** Use "Common Tasks" section
5. **Still stuck?** See "Support & Resources"

---

**Last Updated:** October 2026  
**Status:** Complete ✅

