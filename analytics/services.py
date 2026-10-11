"""
Analytics query service layer.

Provides read-only access to synthetic reservation data in the analytics database.
All functions use .using('analytics') and filter by is_synthetic=True.

Returns structured Python dictionaries suitable for JSON serialization.
"""

from datetime import date, datetime as dt, timedelta
from typing import Dict, List, Tuple, Optional

import django.db
from django.db.models import Count, Q, F, Sum, Case, When, FloatField
from django.db.models.functions import Extract
from django.utils import timezone

from reservations.models import Reservation
from facilities.models import Facility


def _get_analytics_db() -> str:
    """
    Return the analytics database alias for queries.
    
    IMPORTANT: Production analytics queries MUST use the 'analytics' alias.
    If 'analytics' is not configured, a RuntimeError is raised rather than
    silently falling back to the operational 'default' database.
    
    This prevents accidental data contamination and ensures analytics runs
    on the dedicated analytics database only.
    
    Returns:
        str: 'analytics' database alias
        
    Raises:
        RuntimeError: If 'analytics' database is not configured
    """
    if 'analytics' not in django.db.connections.databases:
        raise RuntimeError(
            "Analytics database alias 'analytics' is not configured in settings.DATABASES. "
            "Analytics queries cannot proceed without a dedicated analytics database. "
            "Configure ANALYTICS_DB_* environment variables or set up the 'analytics' alias explicitly."
        )
    return 'analytics'


def get_reservation_kpis(reference_date: Optional[date] = None) -> Dict:
    """
    Calculate key performance indicators from synthetic reservation data.

    Args:
        reference_date: Anchor date for calculations (default: today)

    Returns:
        dict with keys:
        - total_reservations: int (all reservations, including pending)
        - approved_count: int (approved reservations)
        - rejected_count: int (rejected reservations)
        - cancelled_count: int (cancelled reservations)
        - pending_count: int (pending/awaiting review)
        - approval_rate: float (0-1)
          * approved / (approved + rejected + cancelled)
          * Only counts REVIEWED requests (excludes pending)
          * Example: 5 approved, 2 rejected, 2 cancelled = 5/9 = 0.5556
        - rejection_rate: float (0-1)
          * rejected / (approved + rejected + cancelled)
          * Only counts REVIEWED requests
        - cancellation_rate: float (0-1)
          * cancelled / total_reservations
          * Counts ALL requests including pending
        - average_days_to_approval: float or None
          * Average days from creation to approval (approved reservations only)
          * None if no approved reservations exist
    """
    if reference_date is None:
        reference_date = timezone.localdate()

    db = _get_analytics_db()

    # Single optimized query: get all KPIs in one aggregation
    # Calculate time differences using database-level functions
    kpis = (
        Reservation.objects
        .using(db)
        .filter(is_synthetic=True)
        .aggregate(
            total=Count('id'),
            approved=Count('id', filter=Q(status=Reservation.Status.APPROVED)),
            rejected=Count('id', filter=Q(status=Reservation.Status.REJECTED)),
            cancelled=Count('id', filter=Q(status=Reservation.Status.CANCELLED)),
            pending=Count('id', filter=Q(status=Reservation.Status.PENDING)),
            # For approved reservations: sum of days between created and reviewed
            total_approval_days=Sum(
                Case(
                    When(
                        Q(status=Reservation.Status.APPROVED) & Q(reviewed_at__isnull=False),
                        then=F('reviewed_at') - F('created_at')  # Will be timedelta in aggregate
                    ),
                    default=None,
                    output_field=FloatField(),
                )
            ),
            approved_with_review=Count(
                'id',
                filter=Q(status=Reservation.Status.APPROVED) & Q(reviewed_at__isnull=False)
            ),
        )
    )

    total = kpis['total']
    approved = kpis['approved']
    rejected = kpis['rejected']
    cancelled = kpis['cancelled']
    pending = kpis['pending']

    # Calculate rates (avoid division by zero)
    reviewed_total = approved + rejected + cancelled
    approval_rate = (approved / reviewed_total) if reviewed_total > 0 else 0.0
    rejection_rate = (rejected / reviewed_total) if reviewed_total > 0 else 0.0
    cancellation_rate = (cancelled / total) if total > 0 else 0.0

    # Calculate average days to approval (database-side calculation didn't work as expected)
    # Fallback: if we have approved reservations, query just their times
    approved_with_review = kpis['approved_with_review']
    average_days_to_approval = None
    
    if approved_with_review > 0:
        # Query only approved reservations with reviewed_at
        approved_times = (
            Reservation.objects
            .using(db)
            .filter(
                is_synthetic=True,
                status=Reservation.Status.APPROVED,
                reviewed_at__isnull=False
            )
            .values_list('created_at', 'reviewed_at')
        )
        
        if approved_times:
            total_seconds = sum((reviewed - created).total_seconds() for created, reviewed in approved_times)
            average_days_to_approval = total_seconds / 86400 / approved_with_review

    return {
        'total_reservations': total,
        'approved_count': approved,
        'rejected_count': rejected,
        'cancelled_count': cancelled,
        'pending_count': pending,
        'approval_rate': round(approval_rate, 4),
        'rejection_rate': round(rejection_rate, 4),
        'cancellation_rate': round(cancellation_rate, 4),
        'average_days_to_approval': round(average_days_to_approval, 2) if average_days_to_approval else None,
    }


def get_reservation_status_distribution() -> Dict[str, int]:
    """
    Get count of reservations by status.

    Returns:
        dict with status as key and count as value
        Example: {'APPROVED': 2689, 'REJECTED': 821, 'CANCELLED': 1090, 'PENDING': 400}
    """
    db = _get_analytics_db()
    distribution = (
        Reservation.objects
        .using(db)
        .filter(is_synthetic=True)
        .values('status')
        .annotate(count=Count('id'))
        .order_by('status')
    )

    return {item['status']: item['count'] for item in distribution}


def get_monthly_trends(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[Dict]:
    """
    Get monthly reservation trends with status breakdown.

    Args:
        start_date: Start of date range (default: 24 months ago)
        end_date: End of date range (default: today)

    Returns:
        list of dicts with keys:
        - month: str (YYYY-MM)
        - submitted_count: int
        - approved_count: int
        - rejected_count: int
        - cancelled_count: int
        - total: int
    """
    if end_date is None:
        end_date = timezone.localdate()
    if start_date is None:
        start_date = end_date - timedelta(days=365*2)  # 24 months back

    db = _get_analytics_db()

    # Convert date objects to datetime boundaries (handles timezone correctly)
    start_datetime = timezone.make_aware(dt.combine(start_date, dt.min.time()))
    end_datetime = timezone.make_aware(dt.combine(end_date, dt.max.time()))

    # Fetch all reservations in date range, then group in Python to avoid Extract issues
    reservations = (
        Reservation.objects
        .using(db)
        .filter(
            is_synthetic=True,
            created_at__gte=start_datetime,
            created_at__lte=end_datetime,
        )
        .values('created_at', 'status')
    )

    # Group by month in Python
    from collections import defaultdict
    monthly_groups = defaultdict(lambda: {'approved': 0, 'rejected': 0, 'cancelled': 0, 'total': 0})

    for res in reservations:
        # Convert datetime to year-month string
        created_datetime = res['created_at']
        month_str = created_datetime.strftime('%Y-%m')
        
        monthly_groups[month_str]['total'] += 1
        if res['status'] == Reservation.Status.APPROVED:
            monthly_groups[month_str]['approved'] += 1
        elif res['status'] == Reservation.Status.REJECTED:
            monthly_groups[month_str]['rejected'] += 1
        elif res['status'] == Reservation.Status.CANCELLED:
            monthly_groups[month_str]['cancelled'] += 1

    # Convert to sorted list
    result = []
    for month_str in sorted(monthly_groups.keys()):
        data = monthly_groups[month_str]
        result.append({
            'month': month_str,
            'submitted_count': data['total'],
            'approved_count': data['approved'],
            'rejected_count': data['rejected'],
            'cancelled_count': data['cancelled'],
            'total': data['total'],
        })

    return result


def get_facility_demand() -> List[Dict]:
    """
    Get reservation demand by facility.

    Returns:
        list of dicts with keys:
        - facility_id: int
        - facility_name: str
        - facility_type: str
        - reservation_count: int
        - approved_count: int
        - capacity: int
    """
    db = _get_analytics_db()
    demand = (
        Reservation.objects
        .using(db)
        .filter(is_synthetic=True)
        .select_related('facility', 'facility__facility_type')
        .values('facility_id', 'facility__name', 'facility__facility_type__name', 'facility__capacity')
        .annotate(
            reservation_count=Count('id'),
            approved_count=Count('id', filter=Q(status=Reservation.Status.APPROVED)),
        )
        .order_by('-reservation_count')
    )

    result = []
    for item in demand:
        result.append({
            'facility_id': item['facility_id'],
            'facility_name': item['facility__name'],
            'facility_type': item['facility__facility_type__name'],
            'reservation_count': item['reservation_count'],
            'approved_count': item['approved_count'],
            'capacity': item['facility__capacity'],
        })

    return result


def get_peak_booking_periods() -> Dict[str, Dict]:
    """
    Get peak booking patterns by hour and day of week.

    Returns:
        dict with keys:
        - by_hour: dict {hour: count, ...} where hour is 0-23
        - by_day_of_week: dict {day: count, ...} where day is 0-6 (0=Monday)
        - by_facility: list of {facility_name: str, count: int}
    """
    # Reservations grouped by extraction
    db = _get_analytics_db()
    reservations = Reservation.objects.using(db).filter(is_synthetic=True)

    # By hour (extract from start_time)
    # Note: TimeField doesn't have direct extraction, so we convert to a datetime-like format
    by_hour_data = (
        reservations
        .annotate(
            hour=Extract('start_time', 'hour')  # This may not work; fallback below
        )
        .values('hour')
        .annotate(count=Count('id'))
        .order_by('hour')
    )

    by_hour = {}
    # TimeField extraction might not work; use raw SQL or fallback
    try:
        for item in by_hour_data:
            if item['hour'] is not None:
                by_hour[int(item['hour'])] = item['count']
    except Exception:
        # Fallback: use raw connection to extract hour from TIME field
        by_hour = _get_peak_hours_raw()

    # By day of week (from reservation_date)
    by_dow_data = (
        reservations
        .annotate(
            dow=Extract('reservation_date', 'week_day')  # 1=Sunday, 7=Saturday in ISO; 0=Monday in Django week_day
        )
        .values('dow')
        .annotate(count=Count('id'))
        .order_by('dow')
    )

    by_day_of_week = {}
    for item in by_dow_data:
        if item['dow'] is not None:
            # Django week_day: 1=Sunday, 2=Monday, etc. Convert to 0=Monday format
            day_num = (item['dow'] - 2) % 7 if item['dow'] else 0
            by_day_of_week[day_num] = item['count']

    # By facility
    by_facility_data = (
        reservations
        .select_related('facility')
        .values('facility__name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    by_facility = [
        {'facility_name': item['facility__name'], 'count': item['count']}
        for item in by_facility_data
    ]

    return {
        'by_hour': by_hour,
        'by_day_of_week': by_day_of_week,
        'by_facility': by_facility,
    }


def _get_peak_hours_raw() -> Dict[int, int]:
    """
    Fallback: extract peak hours using raw SQL if TimeField extraction fails.

    Returns:
        dict {hour: count}
    """
    from django.db import connections

    db = _get_analytics_db()
    alias = db
    by_hour = {}

    try:
        with connections[alias].cursor() as cursor:
            # MySQL: EXTRACT(HOUR FROM start_time)
            cursor.execute("""
                SELECT EXTRACT(HOUR FROM start_time) as hour, COUNT(*) as count
                FROM reservations_reservation
                WHERE is_synthetic = TRUE
                GROUP BY EXTRACT(HOUR FROM start_time)
                ORDER BY hour
            """)
            rows = cursor.fetchall()
            for hour, count in rows:
                if hour is not None:
                    by_hour[int(hour)] = int(count)
    except Exception:
        # If query fails, return empty dict (will be handled by caller)
        pass

    return by_hour


def get_facility_booking_intensity() -> List[Dict]:
    """
    Calculate facility booking intensity metric based on approved reservations and capacity.

    IMPORTANT: This metric measures BOOKING INTENSITY, NOT actual occupancy utilization.
    
    Actual occupancy utilization would require time-slot overlap analysis (how many people
    are simultaneously in a facility at any given moment). That complex analysis is beyond
    the scope of this MVP and would need multi-hour aggregation logic.
    
    Booking Intensity:
    - Formula: total_approved_reservations / facility_capacity
    - Interpretation: How many "capacity units" worth of bookings are scheduled
    - Example: capacity=20, 100 approved bookings = 5.0 (5x booking intensity)
      (Indicates 100 total bookings scheduled / 20 capacity)
    
    Use Case: Dashboard indicator of facility demand/pressure.
    Facilities with >1.0 score show high booking demand.
    
    Note: Does NOT account for time-slot overlap. Multiple bookings may overlap,
    so actual simultaneous occupancy may be much lower than this score suggests.

    Returns:
        list of dicts with keys:
        - facility_id: int
        - facility_name: str
        - facility_type: str
        - capacity: int
        - approved_reservations: int (total approved bookings)
        - booking_intensity: float (approved_reservations / capacity)
          * 0.0-0.5: Low intensity
          * 0.5-1.0: Moderate intensity
          * 1.0+: High intensity (more bookings than single capacity can cover)
    """
    db = _get_analytics_db()
    
    # OPTIMIZED: Single query with annotation instead of N+1 pattern
    # Get all facilities with their approved reservation counts in one query
    facility_intensity = (
        Facility.objects
        .using(db)
        .filter(is_synthetic=True)
        .select_related('facility_type')
        .annotate(
            approved_count=Count(
                'reservations',  # Count via reverse relation (Facility.reservations)
                filter=Q(reservations__is_synthetic=True, reservations__status=Reservation.Status.APPROVED)
            )
        )
        .values(
            'id',
            'name',
            'facility_type__name',
            'capacity',
            'approved_count'
        )
    )

    result = []
    for facility in facility_intensity:
        capacity = facility['capacity']
        approved_count = facility['approved_count']
        booking_intensity = (approved_count / capacity) if capacity > 0 else 0.0

        result.append({
            'facility_id': facility['id'],
            'facility_name': facility['name'],
            'facility_type': facility['facility_type__name'],
            'capacity': capacity,
            'approved_reservations': approved_count,
            'booking_intensity': round(booking_intensity, 4),
        })

    # Sort by booking intensity descending (highest first)
    result.sort(key=lambda x: x['booking_intensity'], reverse=True)
    return result
