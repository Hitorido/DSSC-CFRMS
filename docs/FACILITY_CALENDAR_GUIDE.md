# Facility Booking Calendar Guide

## Overview

The Facility Booking Calendar provides a visual, color-coded view of facility availability and helps you quickly identify when a facility is available for reservation. This guide explains how to read and use the calendar.

## Accessing the Calendar

### For Requestors (Students/Faculty)
1. Go to **Facilities** on the main menu
2. Click on any facility to view its detail page
3. The **"Reservations & Availability"** calendar is displayed below the facility details

### For Staff/Admins
1. Go to **Facilities** to view all facilities
2. Click on a specific facility to view its calendar
3. **Admin Console** also shows a system-wide calendar of all reservations

## Understanding the Calendar Colors

The calendar uses color-coding to show how busy each day is:

### Color Key
- **🟢 GREEN (0-33%)** - Low occupancy, plenty of availability
  - Good time to request a reservation
  - Most time slots likely available
  
- **🟡 YELLOW (34-66%)** - Medium occupancy, some availability
  - Some time slots available
  - May have limited peak hour availability
  
- **🔴 RED (67-100%)** - High occupancy, limited availability
  - Few time slots available
  - Peak hours likely fully booked
  - Early morning/evening times may still be open
  
- **⚫ GRAY** - Unavailable or Under Maintenance
  - Facility is closed for maintenance
  - No reservations can be made
  - Check facility details for maintenance timeline

## Using Hover Tooltips

### What to Look For
When you hover your mouse over any day in the calendar, a **tooltip** appears showing:

1. **Reservations for that day**
   - Time slots (e.g., "2:00 PM - 3:00 PM")
   - Requester name (if you have permission to see it)
   - Reservation status (e.g., "Approved", "Pending")

2. **Maintenance windows** (if scheduled)
   - Maintenance task name
   - Time slot for the maintenance
   - Maintenance status (e.g., "Scheduled", "Completed")

### Tooltip Example

```
Tuesday, November 15

RESERVATIONS (3):
• 10:00 AM - 11:00 AM  |  John Smith  |  Approved
• 2:00 PM - 3:00 PM    |  Pending Review
• 3:00 PM - 4:00 PM    |  Jane Doe  |  Approved

MAINTENANCE (1):
• Equipment Check (Scheduled)
  8:00 AM - 8:30 AM
```

## How Occupancy is Calculated

Occupancy percentage is calculated as:

```
Occupancy % = (Total Reserved Hours) / (Total Available Hours)
```

**Example:**
- Facility capacity: 50 people
- Operating hours: 8 AM - 6 PM (10 hours)
- Total available: 50 × 10 = 500 person-hours per day
- Reserved person-hours: 375
- **Occupancy: 75% (RED)**

## Making a Reservation

### For Requestors

1. **Find an available day**
   - Look for GREEN days (best availability)
   - YELLOW days can work if your desired time isn't booked
   - Avoid RED days unless booking early morning/evening

2. **Check the tooltip**
   - Hover over the day to see which times are available
   - Find a gap in the schedule

3. **Request the facility**
   - Click "Request this facility" button on the facility detail page
   - Select your desired date and time
   - Complete the reservation request form

4. **Track your reservation**
   - Your request enters "Pending Review" status
   - Staff/admin will review and approve/reject
   - You'll receive a notification once reviewed

## Daily Patterns

Most facilities follow typical daily patterns:

### Typical Booking Distribution
- **8 AM - 12 PM**: 30% of daily bookings (lighter occupancy)
- **12 PM - 2 PM**: 20% of bookings (lunch hour, usually quieter)
- **2 PM - 5 PM**: 40% of bookings (peak hours, busiest times)
- **5 PM - 6 PM**: 10% of bookings (evening, lighter)

### Weekly Patterns
- **Monday - Friday**: 80% of all bookings (weekdays busier)
- **Saturday - Sunday**: 20% of bookings (weekends lighter)

**Tip**: If a facility is RED on a busy Friday, try requesting it for a quiet time like 8-9 AM, or look for an open Saturday slot.

## Calendar Navigation

### Moving Between Months
- Click **Previous** arrow (←) to view past months (reference only)
- Click **Next** arrow (→) to view future months (where you can book)

### Current Day Indicator
- Today's date is highlighted with a **blue border** on the calendar
- You can only make new reservations from today onward

## Tips for Finding Availability

### Strategy 1: Peak Hours Avoidance
If a facility shows RED on a particular day:
1. Hover to see which hours are booked
2. Look for gaps (likely 8-9 AM, 12-1 PM, or 5-6 PM)
3. Try requesting those off-peak times

### Strategy 2: Day-of-Week Shopping
If your preferred facility is RED on Monday-Wednesday:
1. Check if the same facility is GREEN on Thursday-Friday
2. Many facilities have lighter loads mid-week vs. end-of-week

### Strategy 3: Check Maintenance Windows
1. Look for GRAY days (maintenance scheduled)
2. Avoid requesting time slots during maintenance
3. Adjacent days typically open up after maintenance completes

## Legend Interpretation

The calendar legend shows:
```
🟢 Low occupancy (0-33%)     ← Good time to book
🟡 Medium occupancy (34-66%) ← Some slots available  
🔴 High occupancy (67-100%)  ← Very limited slots
⚫ Unavailable               ← Facility closed
```

## Data Interpretation for Staff/Admins

### What the Colors Mean for Planning

**GREEN Facilities**: 
- Underutilized
- Maintenance windows can be scheduled
- Consider marketing/promoting to drive usage

**YELLOW Facilities**:
- Well-balanced utilization
- Good resource efficiency
- Normal operations

**RED Facilities**:
- High demand, consider capacity expansion
- May need additional facility of same type
- Good candidate for extended hours

**GRAY Days**:
- Scheduled maintenance is working
- Plan for maintenance during RED periods to minimize disruption

## Common Questions

### Q: Why does the occupancy change when I check different hours?
**A:** Occupancy is calculated per calendar day, showing total usage. If you hover, you'll see the specific times that are booked.

### Q: Can I book a facility that shows RED?
**A:** Yes, if there are still available time slots. Hover to check specific times—RED indicates overall busyness, not a total lockout.

### Q: What if I need the facility but it's RED all week?
**A:** Contact your facility administrator. They may:
- Allocate additional resources
- Suggest an alternative facility
- Note the demand for future capacity planning

### Q: How are maintenance times shown?
**A:** Maintenance windows appear in the tooltip and may affect the color of a day:
- If maintenance is brief (30 min - 1 hour), the day might still show YELLOW/RED
- If the facility is closed all day for maintenance, the day shows GRAY

### Q: Can I see past reservations?
**A:** Yes, the calendar can display past months for reference (using Previous arrow). These show historical booking patterns but don't allow new reservations.

## Tips for Optimal Use

1. **Plan ahead**: Check calendar 2-3 weeks in advance
2. **Be flexible**: If your top choice is RED, try alternative times or days
3. **Use peak hour patterns**: Book during typical off-peak times for more availability
4. **Check maintenance schedule**: Facilities under maintenance won't show availability
5. **Monitor emails**: You'll receive notifications when requests are approved/rejected

## Troubleshooting

| Issue | What It Means |
|-------|--------------|
| Calendar shows no days | Try a different month or facility |
| All days are GRAY | Facility is under extensive maintenance |
| Tooltip shows "No reservations" but day is RED | Maintenance or extended facility closure |
| Can't click a date to book | Date is in the past or facility unavailable |

## For Facility Managers

When interpreting facility calendars for management decisions:

### Monitor These Metrics
1. **Overall occupancy trend**: Is it rising, steady, or declining?
2. **Peak vs. off-peak**: Which hours are consistently overbooked?
3. **Weekly patterns**: Any days significantly underutilized?
4. **Maintenance impact**: Does occupancy recover after maintenance?

### Use Data for Planning
- **RED facilities**: Plan capacity expansion or additional staff
- **YELLOW facilities**: Model for sustainable utilization
- **GREEN facilities**: Review demand drivers and marketing
- **Maintenance patterns**: Verify maintenance windows minimize disruption

## Next Steps

- **Create a reservation**: Find an available day and request the facility
- **Check recommendations**: Visit your admin/staff dashboard for data-driven suggestions
- **Review analytics**: Use the Admin Analytics guide to understand facility demand patterns
- **Contact support**: Email your facility administrator with questions

---

## Additional Resources

- **User Guide**: See [ANALYTICS_GUIDE.md](ANALYTICS_GUIDE.md) for system-wide analytics
- **Admin Guide**: See [ADMIN_ANALYTICS.md](ADMIN_ANALYTICS.md) for facility management insights
- **Mock Data**: See [MOCK_DATA.md](MOCK_DATA.md) to understand test data patterns

