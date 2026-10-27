"""
Facility Booking Calendar API endpoints.

Provides day-level data for calendar display including:
- Occupancy percentage
- List of reservations
- List of maintenance windows
- Facility availability status
"""

from datetime import datetime, timedelta, time as dtime
from decimal import Decimal

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q, Count
from django.contrib.auth.decorators import login_required

from facilities.models import Facility, FacilityMaintenance
from reservations.models import Reservation


@login_required
@require_http_methods(["GET"])
def facility_calendar_day(request, facility_id, date_str):
    """
    Get calendar data for a specific day at a facility.
    
    Returns occupancy percentage, list of reservations, and maintenance windows.
    
    Args:
        facility_id: ID of the facility
        date_str: Date in YYYY-MM-DD format
        
    Response:
        {
            "date": "2024-12-15",
            "facility_id": 1,
            "occupancy": 45,  # percentage
            "is_available": true,
            "reservations": [
                {
                    "id": 1,
                    "purpose": "Team meeting",
                    "start_time": "14:00",
                    "end_time": "15:00",
                    "status": "APPROVED"
                }
            ],
            "maintenance": [
                {
                    "id": 1,
                    "title": "Projector maintenance",
                    "start_time": "16:00",
                    "end_time": "17:00",
                    "status": "SCHEDULED"
                }
            ]
        }
    """
    try:
        # Parse date
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
    
    try:
        facility = Facility.objects.get(id=facility_id)
    except Facility.DoesNotExist:
        return JsonResponse({'error': 'Facility not found'}, status=404)
    
    # Check if facility is available
    is_available = facility.status == Facility.Status.AVAILABLE
    
    # Get reservations for this day
    reservations = Reservation.objects.filter(
        facility=facility,
        reservation_date=date_obj,
        status__in=[Reservation.Status.PENDING, Reservation.Status.APPROVED]
    ).order_by('start_time').values(
        'id', 'purpose', 'start_time', 'end_time', 'status',
        'requested_by__first_name', 'requested_by__last_name'
    )
    
    # Get maintenance windows for this day
    maintenance = FacilityMaintenance.objects.filter(
        facility=facility,
        maintenance_date=date_obj,
        status=FacilityMaintenance.Status.SCHEDULED
    ).order_by('start_time').values(
        'id', 'title', 'start_time', 'end_time', 'status'
    )
    
    # Calculate occupancy percentage
    # Occupancy = (total reserved minutes) / (operating hours in minutes) * 100
    occupancy = calculate_occupancy(facility, date_obj, list(reservations), list(maintenance))
    
    # Format response
    reservations_data = []
    for res in reservations:
        reservations_data.append({
            'id': res['id'],
            'purpose': res['purpose'],
            'start_time': res['start_time'].strftime('%H:%M') if res['start_time'] else '',
            'end_time': res['end_time'].strftime('%H:%M') if res['end_time'] else '',
            'status': res['status'],
            'requester': f"{res['requested_by__first_name']} {res['requested_by__last_name']}".strip()
        })
    
    maintenance_data = []
    for maint in maintenance:
        maintenance_data.append({
            'id': maint['id'],
            'title': maint['title'],
            'start_time': maint['start_time'].strftime('%H:%M') if maint['start_time'] else '',
            'end_time': maint['end_time'].strftime('%H:%M') if maint['end_time'] else '',
            'status': maint['status']
        })
    
    response_data = {
        'date': date_str,
        'facility_id': facility_id,
        'facility_name': facility.name,
        'occupancy': occupancy,
        'is_available': is_available,
        'status': facility.status,
        'reservations': reservations_data,
        'maintenance': maintenance_data,
        'total_reservations': len(reservations_data),
        'total_maintenance': len(maintenance_data)
    }
    
    return JsonResponse(response_data)


def calculate_occupancy(facility, date_obj, reservations, maintenance):
    """
    Calculate facility occupancy percentage for a day.
    
    Occupancy = (total reserved/maintenance minutes) / (operating hours in minutes) * 100
    
    Args:
        facility: Facility object
        date_obj: Date object
        reservations: QuerySet of reservations
        maintenance: QuerySet of maintenance windows
        
    Returns:
        Occupancy percentage (0-100)
    """
    # Parse operating hours (default to 8am-6pm)
    hours_str = facility.hours_of_operation or '8am-6pm'
    
    try:
        # Simple parsing: assume format like "8am-6pm"
        start_str, end_str = hours_str.split('-')
        
        # Parse start time
        start_str = start_str.strip().lower()
        if 'am' in start_str:
            start_hour = int(start_str.replace('am', ''))
        elif 'pm' in start_str:
            start_hour = int(start_str.replace('pm', '')) + 12
        else:
            start_hour = 8
        
        # Parse end time
        end_str = end_str.strip().lower()
        if 'am' in end_str:
            end_hour = int(end_str.replace('am', ''))
        elif 'pm' in end_str:
            end_hour = int(end_str.replace('pm', '')) + 12
        else:
            end_hour = 18
        
        # Operating hours in minutes
        if end_hour < start_hour:  # e.g., 2pm-8am (overnight)
            operating_minutes = (24 - start_hour + end_hour) * 60
        else:
            operating_minutes = (end_hour - start_hour) * 60
    except:
        # Default to 10 hours (8am-6pm = 10 hours = 600 minutes)
        operating_minutes = 600
    
    # Calculate reserved minutes
    reserved_minutes = 0
    
    # Add reservation time
    for res in reservations:
        if res['start_time'] and res['end_time']:
            start = datetime.combine(date_obj, res['start_time'])
            end = datetime.combine(date_obj, res['end_time'])
            duration = (end - start).total_seconds() / 60
            reserved_minutes += max(0, duration)
    
    # Add maintenance time
    for maint in maintenance:
        if maint['start_time'] and maint['end_time']:
            start = datetime.combine(date_obj, maint['start_time'])
            end = datetime.combine(date_obj, maint['end_time'])
            duration = (end - start).total_seconds() / 60
            reserved_minutes += max(0, duration)
    
    # Calculate occupancy percentage
    if operating_minutes > 0:
        occupancy = min(100, int((reserved_minutes / operating_minutes) * 100))
    else:
        occupancy = 0
    
    return occupancy


@login_required
@require_http_methods(["GET"])
def facility_calendar_month(request, facility_id, year, month):
    """
    Get calendar data for an entire month at a facility.
    
    Returns occupancy percentage for each day of the month.
    
    Response:
        {
            "year": 2024,
            "month": 12,
            "facility_id": 1,
            "days": {
                "1": {"occupancy": 30, "reservations": 2, "maintenance": 0, "is_available": true},
                "2": {"occupancy": 45, "reservations": 3, "maintenance": 0, "is_available": true},
                ...
            }
        }
    """
    try:
        facility = Facility.objects.get(id=facility_id)
    except Facility.DoesNotExist:
        return JsonResponse({'error': 'Facility not found'}, status=404)
    
    # Validate month
    if month < 1 or month > 12:
        return JsonResponse({'error': 'Invalid month. Must be 1-12'}, status=400)
    
    # Get first and last day of month
    from datetime import date
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    
    # Check if facility is available
    is_available = facility.status == Facility.Status.AVAILABLE
    
    # Get all reservations for the month (optimized query)
    month_reservations = list(Reservation.objects.filter(
        facility=facility,
        reservation_date__range=[first_day, last_day],
        status__in=[Reservation.Status.PENDING, Reservation.Status.APPROVED]
    ).values('reservation_date', 'start_time', 'end_time'))
    
    # Get all maintenance for the month (optimized query)
    month_maintenance = list(FacilityMaintenance.objects.filter(
        facility=facility,
        maintenance_date__range=[first_day, last_day],
        status=FacilityMaintenance.Status.SCHEDULED
    ).values('maintenance_date', 'start_time', 'end_time'))
    
    # Create lookup dictionaries for O(1) access
    res_by_date = {}
    for res in month_reservations:
        date_key = res['reservation_date']
        if date_key not in res_by_date:
            res_by_date[date_key] = []
        res_by_date[date_key].append(res)
    
    maint_by_date = {}
    for maint in month_maintenance:
        date_key = maint['maintenance_date']
        if date_key not in maint_by_date:
            maint_by_date[date_key] = []
        maint_by_date[date_key].append(maint)
    
    # Group by day
    days_data = {}
    current_day = first_day
    while current_day <= last_day:
        day_num = current_day.day
        
        # Get reservations and maintenance for this day
        day_reservations = res_by_date.get(current_day, [])
        day_maintenance = maint_by_date.get(current_day, [])
        
        # Calculate occupancy
        occupancy = calculate_occupancy(facility, current_day, day_reservations, day_maintenance)
        
        days_data[str(day_num)] = {
            'occupancy': occupancy,
            'reservations': len(day_reservations),
            'maintenance': len(day_maintenance),
            'is_available': is_available
        }
        
        current_day += timedelta(days=1)
    
    response_data = {
        'year': year,
        'month': month,
        'facility_id': facility_id,
        'facility_name': facility.name,
        'is_available': is_available,
        'days': days_data
    }
    
    return JsonResponse(response_data)
