"""
Analytics query service layer.

Provides read-only access to synthetic reservation data in the analytics database.
All functions use .using('analytics') and filter by is_synthetic=True.

Returns structured Python dictionaries suitable for JSON serialization.
"""

from datetime import date, datetime as dt, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import statistics

import django.db
from django.db.models import Count, Q, F, Sum, Case, When, FloatField
from django.db.models.functions import Extract
from django.utils import timezone
from django.core.cache import cache

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



class PredictiveAnalytics:
    """
    Service for predictive analytics computations on facility reservations.
    
    Provides methods to:
    - Forecast demand over future months using historical trends
    - Identify peak booking hours and days of week
    - Calculate facility occupancy rates
    
    All computations use synthetic reservation data and support caching.
    """
    
    # Cache TTL: 1 hour
    CACHE_TTL = 3600
    
    @staticmethod
    def _get_analytics_db() -> str:
        """Return the analytics database alias."""
        if 'analytics' not in django.db.connections.databases:
            raise RuntimeError(
                "Analytics database alias 'analytics' is not configured. "
                "Cannot proceed with predictive analytics."
            )
        return 'analytics'
    
    @classmethod
    def compute_demand_forecast(
        cls,
        months: int = 6,
        forecast_periods: int = 3
    ) -> Dict:
        """
        Compute demand forecast using historical reservation data.
        
        Analyzes historical reservations over the specified number of months,
        computes trends, and extrapolates forward to forecast future demand.
        
        Args:
            months: Number of historical months to analyze (default 6)
            forecast_periods: Number of months to forecast (default 3)
            
        Returns:
            dict with keys:
            - historical_data: list of {month: str, count: int}
            - forecast_data: list of {month: str, forecast: float}
            - confidence: float (0-1, confidence in forecast)
            
        Example:
            {
                'historical_data': [
                    {'month': '2024-01', 'count': 150},
                    {'month': '2024-02', 'count': 165},
                    ...
                ],
                'forecast_data': [
                    {'month': '2024-07', 'forecast': 185.5},
                    {'month': '2024-08', 'forecast': 192.3},
                    ...
                ],
                'confidence': 0.85
            }
        """
        cache_key = f'forecast_{months}_{forecast_periods}'
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        db = cls._get_analytics_db()
        today = timezone.localdate()
        # Query both past and future (system allows future reservations)
        end_date = today + timedelta(days=30 * months)
        start_date = today - timedelta(days=30 * months)
        
        # Query historical reservations grouped by month
        reservations = (
            Reservation.objects
            .using(db)
            .filter(
                is_synthetic=True,
                reservation_date__gte=start_date,
                reservation_date__lte=end_date,
                status__in=[Reservation.Status.APPROVED, Reservation.Status.COMPLETED]
            )
        )
        
        # Group by month
        monthly_counts = defaultdict(int)
        for res in reservations:
            month_key = res.reservation_date.strftime('%Y-%m')
            monthly_counts[month_key] += 1
        
        # Sort by month
        historical_data = [
            {'month': month, 'count': count}
            for month, count in sorted(monthly_counts.items())
        ]
        
        # Compute trend using simple linear regression or moving average
        if not historical_data:
            # No data available
            forecast_data = []
            confidence = 0.0
        else:
            counts = [item['count'] for item in historical_data]
            
            # Compute simple moving average trend
            if len(counts) >= 2:
                # Calculate trend (slope) using linear regression on month indices
                n = len(counts)
                x_values = list(range(n))
                sum_x = sum(x_values)
                sum_y = sum(counts)
                sum_xy = sum(x * y for x, y in zip(x_values, counts))
                sum_x2 = sum(x * x for x in x_values)
                
                # Linear regression: slope = (n*sum_xy - sum_x*sum_y) / (n*sum_x2 - sum_x^2)
                denominator = n * sum_x2 - sum_x * sum_x
                if denominator != 0:
                    slope = (n * sum_xy - sum_x * sum_y) / denominator
                    intercept = (sum_y - slope * sum_x) / n
                else:
                    slope = 0
                    intercept = sum_y / n
                
                # Calculate R-squared for confidence
                y_mean = sum_y / n
                ss_tot = sum((y - y_mean) ** 2 for y in counts)
                ss_res = sum((counts[i] - (intercept + slope * i)) ** 2 for i in range(n))
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
                confidence = max(0.0, min(1.0, r_squared))
            else:
                # Not enough data for trend
                slope = 0
                intercept = counts[0] if counts else 0
                confidence = 0.5
            
            # Generate forecast for next N months
            forecast_data = []
            last_month_str = historical_data[-1]['month'] if historical_data else today.strftime('%Y-%m')
            last_year, last_month = map(int, last_month_str.split('-'))
            
            for i in range(1, forecast_periods + 1):
                # Calculate next month
                next_month = last_month + i
                next_year = last_year
                while next_month > 12:
                    next_month -= 12
                    next_year += 1
                
                month_key = f'{next_year:04d}-{next_month:02d}'
                
                # Forecast using linear regression
                if len(counts) > 0:
                    forecast_index = len(counts) + i - 1
                    forecast_value = max(0.0, intercept + slope * forecast_index)
                else:
                    forecast_value = 0.0
                
                forecast_data.append({
                    'month': month_key,
                    'forecast': float(round(forecast_value, 1))
                })
        
        result = {
            'historical_data': historical_data,
            'forecast_data': forecast_data,
            'confidence': round(confidence, 2)
        }
        
        cache.set(cache_key, result, cls.CACHE_TTL)
        return result
    
    @classmethod
    def compute_peak_hours(cls, reservations: Optional[List] = None) -> Dict:
        """
        Analyze which hours have highest booking volume.
        
        Args:
            reservations: Optional list of Reservation objects to analyze.
                         If None, queries all synthetic reservations.
            
        Returns:
            dict with keys:
            - peak_hours: list of {hour: int, count: int} ordered by count descending
                         Top 3 peak hours are included
            - all_hours: dict {hour: count, ...} for all 24 hours
            
        Example:
            {
                'peak_hours': [
                    {'hour': 14, 'count': 120},
                    {'hour': 15, 'count': 115},
                    {'hour': 13, 'count': 108}
                ],
                'all_hours': {0: 5, 1: 2, ..., 23: 45}
            }
        """
        cache_key = 'peak_hours'
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        if reservations is None:
            db = cls._get_analytics_db()
            reservations = list(
                Reservation.objects
                .using(db)
                .filter(is_synthetic=True)
                .values_list('start_time', flat=True)
            )
        
        # Count bookings by hour
        hour_counts = {}
        for i in range(24):
            hour_counts[i] = 0
        
        for start_time in reservations:
            if start_time:
                hour = start_time.hour
                hour_counts[hour] += 1
        
        # Get top 3 peak hours
        sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
        peak_hours = [
            {'hour': hour, 'count': count}
            for hour, count in sorted_hours[:3]
            if count > 0  # Only include hours with bookings
        ]
        
        result = {
            'peak_hours': peak_hours,
            'all_hours': hour_counts
        }
        
        cache.set(cache_key, result, cls.CACHE_TTL)
        return result
    
    @classmethod
    def compute_peak_days(cls, reservations: Optional[List] = None) -> Dict:
        """
        Analyze which days of week have highest booking volume.
        
        Args:
            reservations: Optional list of Reservation objects to analyze.
                         If None, queries all synthetic reservations.
            
        Returns:
            dict with keys:
            - peak_days: list of {day: str, day_num: int, count: int} 
                        ordered by count descending
            - all_days: dict {day_num: count, ...} for all 7 days
                       0=Monday, 6=Sunday
            
        Example:
            {
                'peak_days': [
                    {'day': 'Monday', 'day_num': 0, 'count': 150},
                    {'day': 'Tuesday', 'day_num': 1, 'count': 145},
                    ...
                ],
                'all_days': {0: 150, 1: 145, ..., 6: 80}
            }
        """
        cache_key = 'peak_days'
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        if reservations is None:
            db = cls._get_analytics_db()
            reservations = list(
                Reservation.objects
                .using(db)
                .filter(is_synthetic=True)
                .values_list('reservation_date', flat=True)
            )
        
        # Count bookings by day of week (0=Monday, 6=Sunday)
        day_counts = {}
        for i in range(7):
            day_counts[i] = 0
        
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        for reservation_date in reservations:
            if reservation_date:
                day_of_week = reservation_date.weekday()  # 0=Monday, 6=Sunday
                day_counts[day_of_week] += 1
        
        # Get all days sorted by count
        sorted_days = sorted(day_counts.items(), key=lambda x: x[1], reverse=True)
        peak_days = [
            {
                'day': day_names[day_num],
                'day_num': day_num,
                'count': count
            }
            for day_num, count in sorted_days
        ]
        
        result = {
            'peak_days': peak_days,
            'all_days': day_counts
        }
        
        cache.set(cache_key, result, cls.CACHE_TTL)
        return result
    
    @classmethod
    def compute_occupancy_by_facility(
        cls,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict:
        """
        Calculate occupancy % for each facility over a date range.
        
        Occupancy is calculated as: approved_reservations / (days * operating_hours)
        
        Args:
            start_date: Start of date range (default: 30 days ago)
            end_date: End of date range (default: today)
            
        Returns:
            dict with keys:
            - facilities: list of {facility_id: int, facility_name: str, 
                                  occupancy: float, occupancy_percent: float,
                                  reservation_count: int, capacity: int}
                         sorted by occupancy descending (high to low)
            
        Example:
            {
                'facilities': [
                    {
                        'facility_id': 1,
                        'facility_name': 'ComLab 1',
                        'occupancy': 0.75,
                        'occupancy_percent': 75.0,
                        'reservation_count': 45,
                        'capacity': 30
                    },
                    ...
                ]
            }
        """
        if end_date is None:
            end_date = timezone.localdate()
        if start_date is None:
            start_date = end_date - timedelta(days=30)
        
        cache_key = f'occupancy_{start_date}_{end_date}'
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        db = cls._get_analytics_db()
        
        # Query all approved reservations in date range
        reservations = (
            Reservation.objects
            .using(db)
            .filter(
                is_synthetic=True,
                reservation_date__gte=start_date,
                reservation_date__lte=end_date,
                status=Reservation.Status.APPROVED
            )
            .select_related('facility')
        )
        
        # Group by facility
        facility_data = defaultdict(lambda: {'count': 0, 'facility': None})
        for res in reservations:
            facility_id = res.facility_id
            facility_data[facility_id]['count'] += 1
            if facility_data[facility_id]['facility'] is None:
                facility_data[facility_id]['facility'] = res.facility
        
        # Calculate occupancy for each facility
        # Occupancy = reservation_count / (capacity * num_days)
        # This assumes a reasonable estimate of max capacity-days
        num_days = (end_date - start_date).days + 1
        
        facilities = []
        for facility_id, data in facility_data.items():
            facility = data['facility']
            capacity = facility.capacity if facility else 1
            reservation_count = data['count']
            
            # Max possible reservations = capacity * days (assuming 8-hour operating day)
            max_possible = capacity * num_days
            occupancy = reservation_count / max_possible if max_possible > 0 else 0
            occupancy_percent = occupancy * 100
            
            facilities.append({
                'facility_id': facility_id,
                'facility_name': facility.name if facility else 'Unknown',
                'occupancy': round(occupancy, 4),
                'occupancy_percent': round(occupancy_percent, 1),
                'reservation_count': reservation_count,
                'capacity': capacity
            })
        
        # Sort by occupancy descending (high to low)
        facilities.sort(key=lambda x: x['occupancy'], reverse=True)
        
        result = {'facilities': facilities}
        cache.set(cache_key, result, cls.CACHE_TTL)
        return result
    
    @staticmethod
    def invalidate_cache():
        """Invalidate all predictive analytics cache entries."""
        cache.delete('forecast_6_3')
        cache.delete('peak_hours')
        cache.delete('peak_days')
        # Invalidate all occupancy caches (pattern-based deletion)
        # Note: Django cache doesn't support pattern-based deletion for all backends
        # This is a simple implementation; production should use Redis with pattern deletion


class PrescriptiveAnalytics:
    """
    Service for prescriptive analytics - generating actionable recommendations.
    
    Based on predictive analytics results (demand forecasts, peak hours, occupancy),
    generates 4-6 prioritized recommendations for facility management.
    
    Recommendations cover:
    - Capacity planning (high occupancy facilities)
    - Maintenance scheduling (low-occupancy periods)
    - Operating hours optimization (peak days)
    - Equipment maintenance alerts (heavy usage)
    - Seasonal trends
    """
    
    # Cache TTL: 1 hour (same as other analytics)
    CACHE_TTL = 3600
    
    @staticmethod
    def _get_analytics_db() -> str:
        """Return the analytics database alias."""
        if 'analytics' not in django.db.connections.databases:
            raise RuntimeError(
                "Analytics database alias 'analytics' is not configured. "
                "Cannot proceed with prescriptive analytics."
            )
        return 'analytics'
    
    @classmethod
    def generate_recommendations(cls, analytics_data: Optional[Dict] = None) -> Dict:
        """
        Generate 4-6 actionable recommendations based on predictive analytics.
        
        Analyzes occupancy, peak hours, peak days, and equipment usage to generate
        prioritized recommendations for facility management.
        
        Args:
            analytics_data: Optional pre-computed analytics dict with keys:
                           - occupancy_by_facility: from PredictiveAnalytics
                           - peak_hours: from PredictiveAnalytics
                           - peak_days: from PredictiveAnalytics
                           - demand_forecast: from PredictiveAnalytics
                           
                           If None, computes analytics internally.
        
        Returns:
            dict with keys:
            - recommendations: list of {priority: str, title: str, description: str,
                                       action: str, impact: str}
                              sorted by priority (high > medium > low)
                              contains 4-6 recommendations
            - recommendation_count: int (count of recommendations)
            - generation_timestamp: str (ISO format)
            
        Example:
            {
                'recommendations': [
                    {
                        'priority': 'high',
                        'title': 'Capacity expansion needed for ComLab 1',
                        'description': 'ComLab 1 has 85% occupancy over the last 30 days with 45 approved reservations...',
                        'action': 'Review facility expansion options or implement staggered scheduling',
                        'impact': 'Reduce booking conflicts and improve user satisfaction'
                    },
                    ...
                ],
                'recommendation_count': 5,
                'generation_timestamp': '2024-12-15T10:30:45Z'
            }
        """
        cache_key = 'prescriptive_recommendations'
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        # Compute analytics if not provided
        if analytics_data is None:
            analytics_data = cls._compute_analytics_data()
        
        recommendations = []
        
        # Generate recommendations from different angles
        recommendations.extend(cls._recommend_maintenance_windows(analytics_data))
        recommendations.extend(cls._recommend_capacity_expansion(analytics_data))
        recommendations.extend(cls._recommend_extended_hours(analytics_data))
        recommendations.extend(cls._recommend_equipment_maintenance(analytics_data))
        recommendations.extend(cls._recommend_seasonal_patterns(analytics_data))
        
        # Add a default operational recommendation if we have too few
        if len(recommendations) < 4:
            recommendations.append({
                'priority': 'low',
                'title': 'Monitor facility utilization trends',
                'description': 'Track booking patterns and occupancy metrics over time to identify emerging trends. '
                               'Regular monitoring helps anticipate future capacity needs and staffing requirements.',
                'action': 'Set up recurring analytics reviews (weekly or monthly); create trend tracking dashboard',
                'impact': 'Enable proactive planning and optimization based on data-driven insights'
            })
        
        # Sort by priority: high > medium > low
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        recommendations.sort(key=lambda r: (priority_order.get(r['priority'], 3), r['title']))
        
        # Limit to 4-6 recommendations
        # Prefer high/medium priority items
        high_medium = [r for r in recommendations if r['priority'] in ['high', 'medium']]
        low = [r for r in recommendations if r['priority'] == 'low']
        
        # Take up to 4-6 recommendations, prioritizing high/medium
        if len(high_medium) >= 4:
            recommendations = high_medium[:5] if len(high_medium) >= 5 else high_medium[:4]
        else:
            recommendations = high_medium + low[:max(0, 6 - len(high_medium))]
        
        # Ensure we have at least 4 if possible
        recommendations = recommendations[:6] if len(recommendations) > 6 else recommendations
        
        result = {
            'recommendations': recommendations,
            'recommendation_count': len(recommendations),
            'generation_timestamp': timezone.now().isoformat()
        }
        
        cache.set(cache_key, result, cls.CACHE_TTL)
        return result
    
    @classmethod
    def _compute_analytics_data(cls) -> Dict:
        """
        Compute required analytics data for recommendations.
        
        Returns:
            dict with keys:
            - occupancy_by_facility
            - peak_hours
            - peak_days
            - facility_booking_intensity
        """
        return {
            'occupancy_by_facility': PredictiveAnalytics.compute_occupancy_by_facility(),
            'peak_hours': PredictiveAnalytics.compute_peak_hours(),
            'peak_days': PredictiveAnalytics.compute_peak_days(),
            'facility_booking_intensity': get_facility_booking_intensity(),
        }
    
    @classmethod
    def _recommend_maintenance_windows(cls, analytics_data: Dict) -> List[Dict]:
        """
        Recommend maintenance windows during low-occupancy periods.
        
        Returns:
            list of recommendations
        """
        recommendations = []
        peak_hours = analytics_data.get('peak_hours', {}).get('peak_hours', [])
        all_hours = analytics_data.get('peak_hours', {}).get('all_hours', {})
        
        if peak_hours or all_hours:
            # Off-peak hours are those NOT in peak
            peak_hour_nums = {h['hour'] for h in peak_hours}
            off_peak_hours = sorted([h for h in range(24) if h not in peak_hour_nums])
            
            # If all_hours is empty or all peak_hours are empty, generate recommendation anyway
            if not off_peak_hours and all_hours:
                # All hours have some bookings - recommend off-business hours (early morning/late evening)
                off_peak_hours = [h for h in range(24) if all_hours.get(h, 0) == 0]
            
            if off_peak_hours:
                # Get evening/morning off-peak hours (better for users)
                evening_hours = [h for h in off_peak_hours if h >= 17 or h < 9]
                recommended_windows = evening_hours[:3] if evening_hours else off_peak_hours[:3]
                
                if recommended_windows:
                    time_strings = [f'{h}:00-{h+1}:00' for h in recommended_windows]
                    
                    recommendations.append({
                        'priority': 'high',
                        'title': 'Schedule maintenance during low-occupancy periods',
                        'description': f"Identified off-peak hours with minimal bookings: {', '.join(time_strings)}. "
                                       f"These are optimal windows for equipment maintenance and facility upkeep.",
                        'action': 'Create maintenance schedules for identified time slots; notify users in advance',
                        'impact': 'Minimize disruption to users and ensure facility is well-maintained'
                    })
        
        return recommendations
    
    @classmethod
    def _recommend_capacity_expansion(cls, analytics_data: Dict) -> List[Dict]:
        """
        Recommend capacity expansion for high-occupancy facilities.
        
        Returns:
            list of recommendations
        """
        recommendations = []
        occupancy_data = analytics_data.get('occupancy_by_facility', {}).get('facilities', [])
        
        high_occupancy_facilities = [
            f for f in occupancy_data
            if f['occupancy'] > 0.80
        ]
        
        if high_occupancy_facilities:
            facility_names = ', '.join([f['facility_name'] for f in high_occupancy_facilities[:3]])
            occupancy_pct = ', '.join([f"{f['occupancy_percent']:.0f}%" for f in high_occupancy_facilities[:3]])
            
            recommendations.append({
                'priority': 'high',
                'title': 'Consider capacity expansion for high-occupancy facilities',
                'description': f"The following facilities exceed 80% occupancy: {facility_names} "
                               f"({occupancy_pct}). High occupancy indicates strong demand but increases "
                               f"booking conflicts and may lead to scheduling bottlenecks.",
                'action': 'Review facility expansion options, add additional similar facilities, '
                          'or implement staggered scheduling for peak times',
                'impact': 'Reduce booking conflicts, improve user satisfaction, and accommodate growing demand'
            })
        
        return recommendations
    
    @classmethod
    def _recommend_extended_hours(cls, analytics_data: Dict) -> List[Dict]:
        """
        Recommend extended operating hours on peak days.
        
        Returns:
            list of recommendations
        """
        recommendations = []
        peak_days_data = analytics_data.get('peak_days', {}).get('peak_days', [])
        
        if peak_days_data:
            # Get top 2 busiest days
            top_days = peak_days_data[:2]
            day_names = ', '.join([d['day'] for d in top_days])
            
            if top_days[0]['count'] > (sum(d['count'] for d in peak_days_data) / 7) * 1.3:
                # Significant peak exists (>30% above average)
                recommendations.append({
                    'priority': 'medium',
                    'title': 'Extend operating hours on peak-demand days',
                    'description': f"Peak booking demand is concentrated on {day_names}. "
                                   f"These days show significantly higher reservation volumes, "
                                   f"suggesting unmet demand that could be accommodated with extended hours.",
                    'action': 'Review staffing capacity and consider extending availability on peak days; '
                              'communicate extended hours to users',
                    'impact': 'Better accommodate user demand, reduce scheduling conflicts, and improve utilization'
                })
        
        return recommendations
    
    @classmethod
    def _recommend_equipment_maintenance(cls, analytics_data: Dict) -> List[Dict]:
        """
        Recommend equipment maintenance alerts for heavily-used facilities.
        
        Returns:
            list of recommendations
        """
        recommendations = []
        intensity_data = analytics_data.get('facility_booking_intensity', [])
        
        # Facilities with >85% booking intensity (heavy usage)
        heavily_used = [f for f in intensity_data if f['booking_intensity'] > 0.85]
        
        for facility in heavily_used[:2]:  # Top 2 most heavily used
            recommendations.append({
                'priority': 'high',
                'title': f"Equipment maintenance alert for {facility['facility_name']}",
                'description': f"{facility['facility_name']} shows high usage intensity ({facility['booking_intensity']:.1f}x). "
                               f"With {facility['approved_reservations']} approved bookings against capacity of {facility['capacity']}, "
                               f"equipment is under heavy load and at increased risk of failure.",
                'action': 'Schedule preventive maintenance checks; inspect critical equipment for wear; '
                          'document maintenance history',
                'impact': 'Prevent unexpected equipment failures, reduce downtime, ensure user safety'
            })
        
        return recommendations
    
    @classmethod
    def _recommend_seasonal_patterns(cls, analytics_data: Dict) -> List[Dict]:
        """
        Recommend actions based on seasonal patterns.
        
        Returns:
            list of recommendations
        """
        recommendations = []
        forecast_data = analytics_data.get('demand_forecast', {}).get('forecast_data', [])
        historical_data = analytics_data.get('demand_forecast', {}).get('historical_data', [])
        
        if forecast_data and historical_data:
            # Check if demand is trending up/down
            if len(forecast_data) > 0 and len(historical_data) > 0:
                historical_avg = sum(h['count'] for h in historical_data) / len(historical_data) if historical_data else 0
                forecast_avg = sum(f['forecast'] for f in forecast_data) / len(forecast_data) if forecast_data else 0
                
                if forecast_avg > historical_avg * 1.1:
                    # Demand increasing
                    recommendations.append({
                        'priority': 'medium',
                        'title': 'Prepare for increasing demand',
                        'description': f"Forecast analysis indicates increasing demand over the next 3 months. "
                                       f"Current average: {historical_avg:.0f} reservations/month; "
                                       f"Forecast: {forecast_avg:.0f} reservations/month. "
                                       f"This upward trend suggests growing user needs.",
                        'action': 'Assess staffing levels, equipment capacity, and facility availability; '
                                 'consider proactive capacity planning',
                        'impact': 'Ensure system can handle growing demand; prevent service degradation'
                    })
                elif forecast_avg < historical_avg * 0.9:
                    # Demand decreasing
                    recommendations.append({
                        'priority': 'low',
                        'title': 'Note: Decreasing demand trend',
                        'description': f"Forecast analysis indicates slightly decreasing demand. "
                                       f"Current average: {historical_avg:.0f} reservations/month; "
                                       f"Forecast: {forecast_avg:.0f} reservations/month. "
                                       f"This may indicate changing user patterns or seasonal variation.",
                        'action': 'Monitor trend; consider adjusting staffing or conducting user surveys to understand causes',
                        'impact': 'Maintain system efficiency and staff satisfaction through informed planning'
                    })
        
        return recommendations
    
    @staticmethod
    def invalidate_cache():
        """Invalidate prescriptive analytics cache."""
        cache.delete('prescriptive_recommendations')
