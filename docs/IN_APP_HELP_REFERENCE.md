# In-App Help Text Reference

This document contains help text snippets that can be used for tooltips, info icons, and help sections throughout the application.

## Admin Dashboard

### Analytics Overview Card

**Title:** Analytics Overview

**Help Text:**
```
System-wide analytics summary showing key performance indicators. 
All metrics are updated hourly. Click on any metric for detailed breakdowns.
```

**Metric Tooltips:**

1. **Total Reservations**
   ```
   Total count of all reservations in the system, including:
   • Approved reservations (confirmed bookings)
   • Pending reservations (awaiting review)
   • Rejected reservations (for historical tracking)
   • Cancelled reservations (for trend analysis)
   
   This metric helps track overall system volume and usage patterns.
   ```

2. **Average Occupancy %**
   ```
   System-wide facility utilization rate, calculated as:
   (Total Reserved Hours) / (Total Available Hours) × 100%
   
   Healthy target: 60-80%
   • Below 60%: Facilities may be underutilized
   • 60-80%: Optimal utilization
   • Above 80%: Consider capacity expansion
   ```

3. **Peak Facility**
   ```
   The facility with the most reservations in the system.
   This identifies high-demand spaces and may indicate need for:
   • Additional capacity or similar facilities
   • Extended operating hours
   • Additional staff support
   ```

4. **Top-Booked Time Slot**
   ```
   The hour of the day with the highest booking volume.
   Typically 2-5 PM in academic settings.
   
   Use this to:
   • Schedule maintenance during off-peak hours
   • Understand peak demand times
   • Plan staff scheduling
   ```

### Demand Forecast Chart

**Title:** Demand Forecast (3 Months)

**Help Text:**
```
Historical demand (solid line) and predicted demand (dashed line) for the next 3 months.

Reading the chart:
• X-axis: Months (YYYY-MM format)
• Y-axis: Number of reservations
• Solid line: Actual historical data
• Dashed line: System prediction
• Shaded area: Confidence interval (upper/lower bounds)

Use this to:
• Plan facility capacity and staffing
• Schedule maintenance during low-demand periods
• Identify seasonal patterns
• Budget for resource needs
```

**Confidence Badge Help:**
```
Confidence percentage indicates prediction reliability:
• 85%+ confidence: High accuracy forecast
• 70-85% confidence: Good accuracy, some variation possible
• Below 70% confidence: Limited data, less reliable

Forecasts improve with more historical data (6+ months).
```

### System Reservations Calendar

**Title:** System Reservations Calendar

**Help Text:**
```
Month-wide view of all facility reservations and maintenance events across the system.

Legend:
🟢 Green: Low occupancy (0-33%)
🟡 Yellow: Medium occupancy (34-66%)
🔴 Red: High occupancy (67-100%)
⚫ Gray: Unavailable/Maintenance

Each day shows:
• Date number (e.g., "15")
• Total event count (e.g., "5 events")

Hover or click a day to see:
• All reservations (with facility, time, requester, status)
• All maintenance windows (with time and status)
• Occupancy percentage
```

### Recommendations Section

**Title:** Recommended Actions

**Help Text:**
```
Data-driven recommendations for facility and resource management.

Recommendations are generated from:
• Historical booking patterns
• Current and predicted demand
• Facility utilization rates
• Equipment usage patterns
• Maintenance schedules

Priority Levels:
🔴 HIGH - Immediate action recommended
🟡 MEDIUM - Plan for implementation
🟢 LOW - Consider for long-term planning

Each recommendation includes:
• Title: What to do
• Description: Why it matters
• Action: How to implement
• Impact: Expected benefit
```

**Recommendation Type Help:**

1. **Capacity Expansion**
   ```
   Triggered when: Facility occupancy > 80% consistently
   
   This means users are having difficulty finding available time slots.
   Consider:
   • Adding additional similar facilities
   • Extending facility hours
   • Scheduling maintenance during low-peak times
   
   Impact: Reduce booking conflicts, improve user satisfaction
   ```

2. **Maintenance Windows**
   ```
   Triggered when: Low-occupancy time periods are identified
   
   This suggests times when maintenance can be performed with
   minimal disruption to facility availability.
   
   Consider scheduling routine maintenance during these windows:
   • Equipment checks and preventive maintenance
   • Deep cleaning
   • System upgrades
   
   Impact: Zero or minimal disruption to facility availability
   ```

3. **Extended Hours**
   ```
   Triggered when: Peak demand on specific days exceeds 70%
   
   This indicates demand is concentrated on specific days (e.g., Mon-Wed),
   suggesting opportunity to spread usage across week.
   
   Consider:
   • Extending hours on peak days
   • Marketing availability on off-peak days
   • Staggering events across the week
   
   Impact: Increased accessibility, reduced wait times
   ```

4. **Equipment Maintenance**
   ```
   Triggered when: Equipment usage exceeds 85% of operating hours
   
   This indicates equipment is under heavy use and at higher risk of failure.
   
   Recommended actions:
   • Schedule preventive maintenance checks
   • Monitor equipment condition more frequently
   • Prepare contingency equipment
   • Plan for potential downtime
   
   Impact: Reduce unexpected equipment failures and downtime
   ```

5. **Seasonal Planning**
   ```
   Triggered when: Clear seasonal patterns are detected
   
   Examples of seasonal patterns:
   • Higher demand in fall/spring semester
   • Lower demand during summer/winter breaks
   • Department-specific seasonal needs
   
   Use this to:
   • Plan staffing levels seasonally
   • Adjust facility hours for seasons
   • Allocate maintenance during low seasons
   • Budget for seasonal needs
   ```

---

## Staff Dashboard

### Today's Operations Card

**Title:** Today's Operations

**Help Text:**
```
Real-time overview of facility activity for today.

Shows:
• Total reservations scheduled for today
• Which facility has the most bookings
• Occupancy trend for the next 3 hours
```

**Metric Tooltips:**

1. **Reservations Today**
   ```
   Count of approved reservations for today.
   Click to view detailed reservation list.
   ```

2. **Busiest Facility**
   ```
   Which facility has the most reservations today.
   Use this to plan staffing and support where most needed.
   ```

3. **Next 3 Hours Preview**
   ```
   Occupancy bar chart for the next 3 hours.
   
   Each bar represents one hour:
   • Height shows occupancy percentage
   • Taller bars = more bookings
   • Lower bars = available time slots
   
   Use this to prepare for incoming demand and staffing needs.
   ```

### Assigned Facility Alerts

**Title:** Assigned Facility Alerts

**Help Text:**
```
Operational alerts for your assigned facilities.

Alert types:
🔴 HIGH (Red) - Immediate attention required
🟡 MEDIUM (Orange) - Plan action soon
🔵 LOW (Blue) - For information/planning

Common alerts:
• Fully booked hours today or tomorrow
• Scheduled maintenance starting soon
• Equipment requiring attention
• Capacity constraints
```

**Alert Interpretation:**

1. **Fully Booked Alert**
   ```
   Example: "Lab A fully booked 2-5pm today"
   
   This means all available time slots during this period are reserved.
   
   Actions:
   • Notify users of availability before/after peak hours
   • Prepare for higher facility traffic
   • Ensure additional staff support if needed
   ```

2. **Maintenance Alert**
   ```
   Example: "Equipment check scheduled Lab A 8-8:30am"
   
   This means facility will be partially or fully unavailable during this time.
   
   Actions:
   • Communicate maintenance window to users
   • Prepare alternative facilities if needed
   • Ensure maintenance team has access
   • Monitor for maintenance completion
   ```

3. **Equipment Alert**
   ```
   Example: "High usage detected in Lab equipment"
   
   This means equipment is under heavy use.
   
   Actions:
   • Increase monitoring frequency
   • Schedule preventive maintenance
   • Prepare backup equipment
   • Monitor for performance degradation
   ```

### Peak Hours This Week Chart

**Title:** Peak Hours This Week

**Help Text:**
```
Bar chart showing booking volume by hour of day for the week.

Reading the chart:
• X-axis: Hour of day (0-23 in 24-hour format, or displayed as AM/PM)
• Y-axis: Number of bookings
• Bar height: Relative booking volume

Use this to:
• Identify peak hours for staffing decisions
• Plan maintenance around off-peak hours
• Understand user booking patterns
• Prepare for high-demand periods
```

### Operational Recommendations

**Title:** Operational Recommendations

**Help Text:**
```
Facility-specific recommendations focused on immediate operations
(today, tomorrow, this week) rather than long-term planning.

Recommendations may include:
• Today's capacity constraints
• Upcoming maintenance windows
• Equipment requiring attention
• Staff scheduling suggestions
• User communication needs

Click a recommendation for detailed action steps.
```

---

## Facility Booking Calendar

### Color Legend

**Interactive Legend with Tooltips:**

1. **Green (0-33%)**
   ```
   Low occupancy - Plenty of available time slots
   
   Booking opportunities:
   • Most time slots are likely available
   • Good day to request a reservation
   • May include peak and off-peak hours
   ```

2. **Yellow (34-66%)**
   ```
   Medium occupancy - Some availability remains
   
   Booking opportunities:
   • Some time slots are available
   • Peak hours may be booked
   • Early morning/evening often available
   • Call ahead to confirm preferred time
   ```

3. **Red (67-100%)**
   ```
   High occupancy - Limited availability
   
   Booking opportunities:
   • Few available time slots remain
   • Peak hours are likely fully booked
   • Early morning (8-9am) may still be open
   • Evening (5-6pm) may still be open
   • Consider alternative dates if possible
   ```

4. **Gray**
   ```
   Unavailable - Facility closed or under maintenance
   
   Status indicators:
   • Full day maintenance scheduled
   • Facility temporarily closed
   • Check adjacent days when facility reopens
   • Contact facility administrator for more info
   ```

### Occupancy Information

**Occupancy % Explanation:**
```
Occupancy = (Reserved Hours) / (Available Hours) × 100%

Example for a room with 50-person capacity, 8am-6pm:
• Total capacity: 50 people × 10 hours = 500 person-hours
• Reserved: 375 person-hours
• Occupancy: 75% (RED)

This doesn't mean the facility is 75% physically full,
but rather 75% of available person-hours are booked.

A RED day may still have availability:
• In off-peak hours (before 8am, after 5pm)
• With different group sizes
• On different days
```

### Tooltip Information

**Reservation Information:**
```
When hovering over a calendar day:

RESERVATIONS section shows:
• Time slot (e.g., "2:00 PM - 3:00 PM")
• Requester name (if you have permission)
• Status (Approved, Pending, etc.)
• Duration and group size (if visible)
```

**Maintenance Information:**
```
When hovering over a calendar day:

MAINTENANCE section shows:
• Maintenance task title
• Time window (e.g., "8:00 AM - 8:30 AM")
• Status (Scheduled, In Progress, Completed)
• Notes or description (if available)

Maintenance doesn't necessarily block entire day—
check specific time slots in tooltip.
```

---

## Prediction & Analytics Features

### Forecast Interpretation

**What forecasts mean:**
```
FORECAST: A statistical prediction of future demand based on:
• Historical booking patterns (last 6 months)
• Identified trends (increasing, decreasing, stable)
• Seasonal patterns (if 12+ months of data)
• Confidence interval (range of likely values)

NOT a guarantee, but an educated prediction to help planning.
```

**Forecast Accuracy:**
```
Accuracy improves with:
✓ More historical data (6+ months minimum)
✓ Consistent booking patterns
✓ Fewer external disruptions
✓ Seasonal data (12+ months for patterns)

Accuracy is lower when:
✗ Recent facility changes (new capacity, hours, equipment)
✗ Major event or disruption in booking patterns
✗ Limited historical data (less than 6 weeks)
✗ Significant staffing or policy changes
```

### Confidence Intervals

**Understanding Confidence Levels:**
```
Confidence indicates prediction reliability:

85%+ Confidence:
  • Good historical data (6+ months)
  • Stable patterns identified
  • Lower risk of surprise demand changes
  
70-85% Confidence:
  • Moderate historical data
  • Some pattern variation
  • Reasonable for planning but verify assumptions
  
Below 70% Confidence:
  • Limited historical data
  • Less reliable for planning
  • Wait for more data if possible
  
No Confidence (N/A):
  • Insufficient data (less than 4 weeks)
  • Cannot make reliable prediction yet
  • Continue generating data
```

---

## Data Freshness & Caching

### Cache Update Timing

**Dashboard Data Freshness:**
```
Analytics data is cached for 1 hour to ensure performance:

• Fresh data (< 5 min old): Green indicator
• Recent data (5-30 min old): Yellow indicator  
• Potentially stale (> 30 min old): Orange indicator
• Very stale (> 1 hour old): Red indicator

Last update timestamp: Shows exact time data was refreshed

To refresh immediately:
(Admin only) Use the cache refresh button on admin dashboard
```

### Synthetic vs. Real Data

**Understanding Synthetic Data Notices:**
```
"Displaying synthetic data for demonstration"

This means:
• System has insufficient real operational data
• Using test/generated data for realistic examples
• Patterns are realistic but not actual
• All is clearly marked as test data

This is normal when:
✓ System is newly deployed
✓ Real data accumulation is ongoing
✓ Testing new features

Real operational data will replace synthetic when:
✓ System has 6+ weeks of real usage
✓ Sufficient patterns have formed
✓ Data volume is meaningful for analysis

The system automatically switches to real data when available.
```

---

## Mobile & Accessibility

### Small Screen Calendars

**On Mobile Devices:**
```
Calendar may display differently on smaller screens:
• May show fewer columns (stacked view)
• Tooltips may appear as expanded information
• Color legend remains visible
• Use horizontal scroll if needed

Tips:
• Rotate phone to landscape for wider view
• Tap day instead of hover for tooltip on mobile
• Zoom in if text is hard to read
• Use mobile-optimized view for easier interaction
```

### Keyboard Navigation

**For Users with Keyboards Only:**
```
Navigation methods:
• Tab: Move between calendar days
• Enter/Space: Activate day selection or view tooltip
• Arrow keys: Move between dates
• Escape: Close tooltip or dialog

Tooltips:
• Use Tab to navigate to element with tooltip
• Tooltip appears automatically when focused
• Use arrow keys to navigate within tooltip
• Escape to close and return to calendar
```

---

## Common Questions - Help Text

### "Why does occupancy seem high but times are available?"
```
Occupancy is calculated as total hours booked divided by total available hours.

Example: If peak hours (2-5pm) are fully booked but morning and evening
are empty, overall occupancy might still only be 50-60%.

Check the tooltip to see the specific available times.
```

### "The forecast seems flat—is it working?"
```
Flat forecasts can indicate:
• Stable, predictable usage patterns (normal and good)
• Limited historical data to show trends
• Recently deployed system with minimal history

The forecast will show more variation as:
• More historical data accumulates
• Seasonal patterns become visible
• Trends become apparent in data

This is normal. Forecasts improve over time.
```

### "How often is this data updated?"
```
Update frequencies:
• Reservations: Real-time when created/updated
• Dashboard analytics: Updated hourly (cached)
• Forecasts: Recomputed daily during maintenance window
• Calendar: Real-time for new reservations

See "Last updated" timestamp on dashboard for exact timing.
```

### "Can I trust this recommendation?"
```
Recommendations are based on:
✓ Statistical analysis of historical data
✓ Industry best practices
✓ System performance metrics
✓ User-defined thresholds

Recommendations should be:
• Considered as suggestions, not directives
• Evaluated based on local context
• Combined with staff expertise and knowledge
• Tested with small pilot if significant changes

They improve in relevance as:
• More data accumulates
• You provide feedback on effectiveness
• System learns your facility's patterns
```

