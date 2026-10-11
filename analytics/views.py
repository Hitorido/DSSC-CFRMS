"""
Analytics JSON API views - Phase 6.5.2.

Provides read-only JSON endpoints for analytics dashboards and reports.

Access Control:
- ADMIN role: Full access to all endpoints
- STAFF role: Denied (not analytics viewers by design)
- REQUESTER role: Denied (not analytics viewers by design)
- Unauthenticated users: Denied (redirect to login)

Error Handling:
- Invalid parameters: HTTP 400 with detailed error messages
- Database unavailable: HTTP 503 Service Unavailable (safe fail-fast)
- Permission denied: HTTP 403 Forbidden
- All error responses are JSON with consistent structure
"""

import json
from datetime import datetime, date
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from accounts.models import User
from analytics import services, forecasting


# ============================================================================
# AUTHORIZATION DECORATORS & AUTHENTICATION
# ============================================================================

def require_auth_json(view_func):
    """
    Decorator for JSON API endpoints that require authentication.
    
    Returns:
    - HTTP 401 JSON (not redirect) for unauthenticated users
    - Allows view to check roles/permissions
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {
                    'error': 'Authentication required',
                    'detail': 'You must be authenticated to access this endpoint.',
                },
                status=401,
            )
        return view_func(request, *args, **kwargs)
    return wrapper

def admin_only(view_func):
    """
    Decorator for views that restrict access to ADMIN role only.
    
    Returns:
    - HTTP 403 if user is authenticated but doesn't have ADMIN role
    - HTTP 401 (redirect) if user is not authenticated (handled by @login_required)
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.role != User.Role.ADMIN:
            return JsonResponse(
                {
                    'error': 'Permission denied',
                    'detail': 'Only ADMIN users can access analytics endpoints.',
                    'required_role': User.Role.ADMIN,
                },
                status=403,
            )
        return view_func(request, *args, **kwargs)
    return wrapper


# ============================================================================
# ERROR RESPONSE HELPERS
# ============================================================================

def error_response(message, detail='', status=400, **kwargs):
    """
    Create a consistent JSON error response.
    
    Args:
        message: Error title/category
        detail: Detailed error explanation
        status: HTTP status code
        **kwargs: Additional fields to include in response
    
    Returns:
        JsonResponse with consistent error structure
    """
    response = {
        'error': message,
        'detail': detail,
    }
    response.update(kwargs)
    return JsonResponse(response, status=status)


def database_unavailable_response():
    """Return HTTP 503 when analytics database is unavailable."""
    return error_response(
        'Service unavailable',
        'Analytics database is unavailable. Please try again later.',
        status=503,
    )


# ============================================================================
# PARAMETER VALIDATION HELPERS
# ============================================================================

def parse_date(date_str, param_name='date'):
    """
    Parse ISO format date string (YYYY-MM-DD).
    
    Args:
        date_str: Date string to parse
        param_name: Parameter name for error messages
    
    Returns:
        date object or error tuple (error_response, None)
    """
    if not date_str:
        return date_str, None
    
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.date(), None
    except (ValueError, TypeError) as e:
        err = error_response(
            'Invalid parameter',
            f'{param_name} must be ISO format (YYYY-MM-DD). Got: {date_str}',
            status=400,
        )
        return None, err


# ============================================================================
# ENDPOINT: Reservation KPIs
# ============================================================================

@require_http_methods(['GET'])
@require_auth_json
@admin_only
def reservation_kpis(request):
    """
    GET /api/analytics/reservation-kpis/
    
    Returns Key Performance Indicators for reservations:
    - Total reservation count (all statuses)
    - Approval rate (approved / reviewed)
    - Rejection rate (rejected / reviewed)
    - Cancellation rate (cancelled / total)
    - Average days to approval
    
    Response (200 OK):
    {
        "total_reservations": 5000,
        "approved_count": 2689,
        "rejected_count": 821,
        "cancelled_count": 1090,
        "pending_count": 400,
        "approval_rate": 0.5850,
        "rejection_rate": 0.1780,
        "cancellation_rate": 0.2180,
        "average_days_to_approval": 2.85
    }
    
    Error Responses:
    - 503 Service Unavailable: Analytics database not configured
    - 403 Forbidden: User does not have ADMIN role
    - 401 Unauthorized: User is not authenticated
    """
    try:
        kpis = services.get_reservation_kpis()
        return JsonResponse(kpis, status=200)
    except RuntimeError as e:
        # Analytics database unavailable (safe fail-fast)
        return database_unavailable_response()


# ============================================================================
# ENDPOINT: Reservation Status Distribution
# ============================================================================

@require_http_methods(['GET'])
@require_auth_json
@admin_only
def status_distribution(request):
    """
    GET /api/analytics/status-distribution/
    
    Returns count of reservations by status.
    
    Response (200 OK):
    {
        "APPROVED": 2689,
        "REJECTED": 821,
        "CANCELLED": 1090,
        "PENDING": 400
    }
    
    Error Responses:
    - 503 Service Unavailable: Analytics database not configured
    - 403 Forbidden: User does not have ADMIN role
    - 401 Unauthorized: User is not authenticated
    """
    try:
        distribution = services.get_reservation_status_distribution()
        return JsonResponse(distribution, status=200)
    except RuntimeError as e:
        return database_unavailable_response()


# ============================================================================
# ENDPOINT: Monthly Reservation Trends
# ============================================================================

@require_http_methods(['GET'])
@require_auth_json
@admin_only
def monthly_trends(request):
    """
    GET /api/analytics/monthly-trends/?start_date=2024-01-01&end_date=2024-12-31
    
    Returns monthly reservation trends with status breakdown.
    
    Query Parameters:
    - start_date (optional): ISO format date (YYYY-MM-DD). Default: 24 months ago
    - end_date (optional): ISO format date (YYYY-MM-DD). Default: today
    
    Response (200 OK):
    [
        {
            "month": "2024-01",
            "submitted_count": 420,
            "approved_count": 245,
            "rejected_count": 75,
            "cancelled_count": 100,
            "total": 420
        },
        ...
    ]
    
    Error Responses:
    - 400 Bad Request: Invalid date format or parameter
    - 503 Service Unavailable: Analytics database not configured
    - 403 Forbidden: User does not have ADMIN role
    - 401 Unauthorized: User is not authenticated
    """
    # Parse optional date parameters
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')
    
    start_date, err = parse_date(start_date_str, 'start_date') if start_date_str else (None, None)
    if err:
        return err
    
    end_date, err = parse_date(end_date_str, 'end_date') if end_date_str else (None, None)
    if err:
        return err
    
    # Validate date range if both provided
    if start_date and end_date:
        if start_date > end_date:
            return error_response(
                'Invalid parameter',
                f'start_date ({start_date}) must be before or equal to end_date ({end_date})',
                status=400,
            )
    
    try:
        trends = services.get_monthly_trends(start_date=start_date, end_date=end_date)
        return JsonResponse(trends, safe=False, status=200)
    except RuntimeError as e:
        return database_unavailable_response()


# ============================================================================
# ENDPOINT: Facility Demand
# ============================================================================

@require_http_methods(['GET'])
@require_auth_json
@admin_only
def facility_demand(request):
    """
    GET /api/analytics/facility-demand/
    
    Returns facilities ranked by reservation demand (highest to lowest).
    
    Response (200 OK):
    [
        {
            "facility_id": 1,
            "facility_name": "Lab A",
            "facility_type": "Computer Lab",
            "reservation_count": 856,
            "approved_count": 500,
            "capacity": 50
        },
        ...
    ]
    
    Error Responses:
    - 503 Service Unavailable: Analytics database not configured
    - 403 Forbidden: User does not have ADMIN role
    - 401 Unauthorized: User is not authenticated
    """
    try:
        demand = services.get_facility_demand()
        return JsonResponse(demand, safe=False, status=200)
    except RuntimeError as e:
        return database_unavailable_response()


# ============================================================================
# ENDPOINT: Peak Booking Periods
# ============================================================================

@require_http_methods(['GET'])
@require_auth_json
@admin_only
def peak_booking_periods(request):
    """
    GET /api/analytics/peak-booking-periods/
    
    Returns peak booking patterns by hour, day of week, and facility.
    
    Response (200 OK):
    {
        "by_hour": {
            "9": 245,
            "10": 312,
            "14": 198,
            ...
        },
        "by_day_of_week": {
            "0": 420,
            "1": 450,
            "2": 435,
            ...
        },
        "by_facility": [
            {
                "facility_name": "Lab A",
                "count": 856
            },
            ...
        ]
    }
    
    Notes:
    - Hour values: 0-23 (24-hour format)
    - Day of week: 0=Monday, 1=Tuesday, ..., 6=Sunday
    
    Error Responses:
    - 503 Service Unavailable: Analytics database not configured
    - 403 Forbidden: User does not have ADMIN role
    - 401 Unauthorized: User is not authenticated
    """
    try:
        peaks = services.get_peak_booking_periods()
        # Convert integer keys to strings for JSON serialization
        peaks['by_hour'] = {str(k): v for k, v in peaks['by_hour'].items()}
        peaks['by_day_of_week'] = {str(k): v for k, v in peaks['by_day_of_week'].items()}
        return JsonResponse(peaks, status=200)
    except RuntimeError as e:
        return database_unavailable_response()


# ============================================================================
# ENDPOINT: Facility Booking Intensity
# ============================================================================

@require_http_methods(['GET'])
@require_auth_json
@admin_only
def facility_booking_intensity(request):
    """
    GET /api/analytics/facility-booking-intensity/
    
    Returns facility booking intensity scores (approved reservations / capacity).
    
    IMPORTANT: This metric measures BOOKING INTENSITY, NOT occupancy utilization.
    It represents scheduled bookings relative to capacity, not simultaneous occupancy.
    
    Response (200 OK):
    [
        {
            "facility_id": 1,
            "facility_name": "Lab A",
            "facility_type": "Computer Lab",
            "capacity": 50,
            "approved_reservations": 245,
            "booking_intensity": 4.9000
        },
        ...
    ]
    
    Interpretation:
    - 0.0-0.5: Low intensity (plenty of available capacity)
    - 0.5-1.0: Moderate intensity (reasonable utilization)
    - 1.0+: High intensity (more bookings than capacity can support in single slot)
    
    Error Responses:
    - 503 Service Unavailable: Analytics database not configured
    - 403 Forbidden: User does not have ADMIN role
    - 401 Unauthorized: User is not authenticated
    """
    try:
        intensity = services.get_facility_booking_intensity()
        return JsonResponse(intensity, safe=False, status=200)
    except RuntimeError as e:
        return database_unavailable_response()


# ============================================================================
# ENDPOINT: Demand Forecast (Phase 6.5.3)
# ============================================================================

@require_http_methods(['GET'])
@require_auth_json
@admin_only
def demand_forecast(request):
    """
    GET /api/analytics/demand-forecast/
    
    Returns 4-week demand forecast using historical reservation data.
    
    METHODOLOGY: Seasonal Naive with Exponential Smoothing Fallback
    
    Seasonal Naive (Primary):
    - Uses historical average from same week in previous years
    - Requires ≥52 weeks of history
    - Handles yearly seasonality
    
    Exponential Smoothing (Fallback):
    - Exponentially weighted moving average (α=0.3)
    - Requires ≥10 weeks of history
    - Adapts to recent trends, ignores seasonality
    
    Last Year Average (Extreme Fallback):
    - Uses overall mean of all history
    - Requires ≥10 weeks of history
    - Very low confidence, minimal training data
    
    Query Parameters:
    - reference_date (optional): ISO format date (YYYY-MM-DD). Default: today
      Forecast uses historical data strictly before this date.
    
    Response (200 OK):
    {
        "forecasts": [
            {
                "week_start_date": "2024-10-21",
                "week_end_date": "2024-10-27",
                "predicted_demand": 425,
                "historical_mean": 410.5,
                "historical_std": 35.2,
                "lower_bound": 356,
                "upper_bound": 495,
                "method": "seasonal_naive",
                "confidence_note": "High confidence (based on multi-year seasonal pattern)",
                "observations_in_pattern": 3
            },
            ...
        ],
        "method_used": "seasonal_naive",
        "historical_weeks_used": 156,
        "forecast_reference_date": "2024-10-19",
        "limitations": [
            "Assumes year-over-year seasonality is stable",
            "Cannot detect trend changes",
            "Less accurate during seasonal pattern changes"
        ],
        "evaluation_metrics": null
    }
    
    Field Descriptions:
    - week_start_date/week_end_date: ISO dates for forecast week (Monday-Sunday)
    - predicted_demand: Predicted reservation count (integer)
    - historical_mean: Mean demand from corresponding historical weeks
    - historical_std: Standard deviation of historical demand
    - lower_bound/upper_bound: 95% confidence interval
    - method: Method used for this specific forecast
    - confidence_note: Human-readable confidence assessment
    - observations_in_pattern: (seasonal_naive) Number of historical years averaged
    - smoothing_parameter: (exponential_smoothing) Value of α
    
    Error Responses:
    - 400 Bad Request: Invalid reference_date format
    - 401 Unauthorized: User not authenticated (returned as JSON)
    - 403 Forbidden: User does not have ADMIN role
    - 422 Unprocessable Entity: Insufficient historical data for any forecasting method
    - 503 Service Unavailable: Analytics database not configured
    
    IMPORTANT LIMITATIONS:
    - Requires minimum 10 weeks of historical data
    - Seasonal naive requires 52+ weeks (one year)
    - Assumes historical patterns continue
    - Cannot predict structural breaks or unprecedented events
    - Confidence intervals are symmetric (assumes normal distribution)
    - Does not account for external factors (holidays, events, policy changes)
    
    BACKTESTING:
    - Not included in this endpoint (available separately)
    - MAE typically 15-25% of mean demand for stable seasons
    - Performance degrades during data changes or unusual patterns
    """
    # Parse optional reference_date parameter
    ref_date_str = request.GET.get('reference_date', '')
    
    if ref_date_str:
        try:
            ref_date = datetime.fromisoformat(ref_date_str).date()
        except (ValueError, TypeError):
            return error_response(
                'Invalid parameter',
                f'reference_date must be ISO format (YYYY-MM-DD). Got: {ref_date_str}',
                status=400,
            )
    else:
        ref_date = None
    
    # Generate forecast
    try:
        forecast_result = forecasting.forecast_demand(ref_date, forecast_weeks=4)
        return JsonResponse(forecast_result, status=200)
    except RuntimeError as e:
        # Analytics database unavailable
        return database_unavailable_response()
    except ValueError as e:
        # Insufficient data
        return error_response(
            'Unprocessable entity',
            f'Cannot generate forecast: {str(e)}',
            status=422,
        )
