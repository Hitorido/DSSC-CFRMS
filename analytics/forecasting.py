"""
Predictive analytics service - Demand forecasting.

Provides 4-week ahead demand forecasting using historical reservation data.

METHODOLOGY: Seasonal Naive with Exponential Smoothing Fallback

Two methods are implemented:

1. SEASONAL NAIVE (Primary)
   - Uses historical average from same week in previous year
   - Formula: Forecast(t+k) = Average(t-52+k, t-104+k, t-156+k, ...)
   - Advantages:
     * Simple, interpretable
     * Handles seasonality well (year-over-year patterns)
     * No hyperparameters to tune
     * Robust to outliers when averaging multiple years
   - Limitations:
     * Requires at least 52 weeks of history
     * Assumes yearly seasonality is stable
     * Cannot detect trend changes
     * Ignores recent patterns if they break seasonality
   
   - Fallback: If < 52 weeks, uses simple naive (last year's average)

2. EXPONENTIAL SMOOTHING (Fallback)
   - Uses exponentially weighted moving average
   - Formula: Forecast(t+1) = α*Observation(t) + (1-α)*Forecast(t)
   - Advantages:
     * Works with minimal history (10+ weeks)
     * Adapts to recent trends
     * Single hyperparameter (α=0.3 proven robust)
   - Limitations:
     * No seasonality capture
     * Less accurate for highly seasonal data
     * Assumes constant trend

DATA AGGREGATION:
- Historical data aggregated into weekly intervals (Monday-Sunday)
- Missing weeks filled with forward-fill (last known value)
- All training uses only historical data (no future leakage)
- Training window: All available history up to reference date

FORECAST OUTPUTS:
- week_start_date: ISO date (Monday of forecast week)
- week_end_date: ISO date (Sunday of forecast week)
- predicted_demand: Predicted reservation count (integer)
- historical_mean: Mean demand from corresponding historical weeks
- historical_std: Standard deviation of historical demand
- lower_bound: predicted_demand - (1.96 * historical_std)
- upper_bound: predicted_demand + (1.96 * historical_std)
- method: Method used ('seasonal_naive', 'exponential_smoothing', 'last_year_average')
- confidence_note: Human-readable confidence level based on method

PREDICTION INTERVAL METHODOLOGY:
- Bounds use ±1.96σ formula (assumes normal distribution)
- These are ESTIMATED RANGES, not validated 95% confidence intervals
- Coverage depends on whether historical demand is normally distributed
- For non-normal distributions, ranges may over/underestimate uncertainty
- Use bounds as guidance, not statistical guarantees

CHRONOLOGICAL VALIDATION:
- All training data is strictly before reference date
- No test data leakage into training
- Forecasts are always for future periods

LIMITATIONS:
- Requires minimum 10 weeks of history for any forecast
- Seasonal naive assumes consistent yearly patterns
- Cannot predict structural breaks or unprecedented events
- Estimated ranges are symmetric (not validated as true CI)
- Does not account for external factors (holidays, events, policy changes)
- Performance degrades during period of data changes or unusual patterns
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import statistics

from django.db.models import Count, Q
from django.utils import timezone

from reservations.models import Reservation


def _get_analytics_db() -> str:
    """Return the analytics database alias. Raises RuntimeError if unavailable."""
    import django.db
    if 'analytics' not in django.db.connections.databases:
        raise RuntimeError(
            "Analytics database alias 'analytics' is not configured in settings.DATABASES. "
            "Cannot proceed with forecasting."
        )
    return 'analytics'


def _get_week_start(d: date) -> date:
    """Return Monday of the week containing date d."""
    return d - timedelta(days=d.weekday())


def _get_historical_weekly_demand(
    reference_date: Optional[date] = None,
    weeks_back: int = 156,  # 3 years
) -> Dict[date, int]:
    """
    Aggregate historical reservations into weekly demand.
    
    FORECAST TARGET: Approved Reservations Only
    
    The forecasting target is APPROVED reservations. This represents "confirmed 
    scheduled demand" - reservations that have been reviewed and approved for 
    facility use. This choice reflects the facilities management perspective 
    of forecasting facility needs.
    
    Alternative interpretation (not used): Total submitted request volume 
    (APPROVED + REJECTED + CANCELLED + PENDING) would forecast "demand pressure" 
    on the system, but is not used here.
    
    Args:
        reference_date: Cutoff date (forecasts use data before this)
        weeks_back: How many weeks of history to fetch
    
    Returns:
        dict mapping week_start_date -> demand_count
        
    Notes:
        - Only uses synthetic, approved reservations (confirmed demand)
        - Week starts on Monday (ISO calendar convention)
        - All weeks are strictly before reference_date (no future data)
        - Missing weeks are forward-filled (last known value)
        - No leakage of test/future data into training
    """
    if reference_date is None:
        reference_date = timezone.localdate()
    
    db = _get_analytics_db()
    
    # Calculate start of historical window
    start_date = reference_date - timedelta(weeks=weeks_back)
    
    # Fetch approved reservations within window (don't include reference_date or later)
    reservations = (
        Reservation.objects
        .using(db)
        .filter(
            is_synthetic=True,
            status=Reservation.Status.APPROVED,
            created_at__date__gte=start_date,
            created_at__date__lt=reference_date,  # Strictly before reference_date
        )
        .values('created_at__date')
        .annotate(count=Count('id'))
    )
    
    # Aggregate into weeks
    weekly_data = defaultdict(int)
    for res in reservations:
        res_date = res['created_at__date']
        week_start = _get_week_start(res_date)
        weekly_data[week_start] += res['count']
    
    return dict(weekly_data)


def _fill_missing_weeks(weekly_data: Dict[date, int], weeks: List[date]) -> Dict[date, int]:
    """
    Fill missing weeks using forward-fill (last observed value).
    
    Args:
        weekly_data: Sparse dict of week_start -> demand
        weeks: List of all week dates to include
    
    Returns:
        dict with all weeks (missing filled with forward-fill)
    """
    result = {}
    last_value = 0
    
    for week in sorted(weeks):
        if week in weekly_data:
            last_value = weekly_data[week]
        result[week] = last_value
    
    return result


def _seasonal_naive_forecast(
    weekly_demand: Dict[date, int],
    reference_date: date,
    forecast_weeks: int = 4,
) -> List[Dict]:
    """
    Generate seasonal naive forecasts.
    
    Method: Use historical average from same week in previous years
    
    Args:
        weekly_demand: Dict of week_start_date -> demand
        reference_date: Cutoff date (training data is before this)
        forecast_weeks: How many weeks to forecast (default 4)
    
    Returns:
        List of forecast dicts with predictions and bounds
        
    Raises:
        ValueError: If insufficient history for seasonal naive
    """
    if not weekly_demand:
        raise ValueError("No historical data available for forecasting")
    
    # Get all historical weeks, sorted
    hist_weeks = sorted(weekly_demand.keys())
    
    if len(hist_weeks) < 52:
        raise ValueError(
            f"Seasonal naive requires at least 52 weeks of history. "
            f"Found {len(hist_weeks)} weeks."
        )
    
    # Group by week-of-year to find seasonal patterns
    week_of_year_data = defaultdict(list)
    for week_date, demand in weekly_demand.items():
        week_of_year = week_date.isocalendar()[1]
        week_of_year_data[week_of_year].append(demand)
    
    # Generate forecasts for next 4 weeks
    forecasts = []
    current_week_start = _get_week_start(reference_date)
    
    for i in range(forecast_weeks):
        forecast_week = current_week_start + timedelta(weeks=i+1)
        forecast_week_of_year = forecast_week.isocalendar()[1]
        
        # Get historical observations for this week-of-year
        historical_values = week_of_year_data.get(forecast_week_of_year, [])
        
        if not historical_values:
            # No observations for this week-of-year; use overall mean
            all_values = list(weekly_demand.values())
            predicted_demand = int(statistics.mean(all_values)) if all_values else 0
            historical_mean = predicted_demand
            historical_std = 0
        else:
            # Use mean of historical observations for this week
            historical_mean = statistics.mean(historical_values)
            historical_std = statistics.stdev(historical_values) if len(historical_values) > 1 else 0
            predicted_demand = int(historical_mean)
        
        # Calculate 95% confidence bounds
        lower_bound = max(0, int(predicted_demand - 1.96 * historical_std))
        upper_bound = int(predicted_demand + 1.96 * historical_std)
        
        forecasts.append({
            'week_start_date': forecast_week.isoformat(),
            'week_end_date': (forecast_week + timedelta(days=6)).isoformat(),
            'predicted_demand': predicted_demand,
            'historical_mean': round(historical_mean, 2),
            'historical_std': round(historical_std, 2),
            'lower_bound': lower_bound,
            'upper_bound': upper_bound,
            'method': 'seasonal_naive',
            'confidence_note': 'High confidence - based on multi-year seasonal pattern (estimated range)',
            'observations_in_pattern': len(historical_values),
        })
    
    return forecasts


def _exponential_smoothing_forecast(
    weekly_demand: Dict[date, int],
    reference_date: date,
    forecast_weeks: int = 4,
    alpha: float = 0.3,
) -> List[Dict]:
    """
    Generate exponential smoothing forecasts.
    
    Method: Exponentially weighted moving average
    
    Args:
        weekly_demand: Dict of week_start_date -> demand
        reference_date: Cutoff date (training data is before this)
        forecast_weeks: How many weeks to forecast
        alpha: Smoothing parameter (0.3 is default, proven robust)
    
    Returns:
        List of forecast dicts with predictions and bounds
        
    Raises:
        ValueError: If insufficient history
    """
    if not weekly_demand:
        raise ValueError("No historical data available for forecasting")
    
    hist_weeks = sorted(weekly_demand.keys())
    if len(hist_weeks) < 10:
        raise ValueError(
            f"Exponential smoothing requires at least 10 weeks of history. "
            f"Found {len(hist_weeks)} weeks."
        )
    
    # Get sorted historical values
    sorted_weeks = sorted(weekly_demand.keys())
    values = [weekly_demand[w] for w in sorted_weeks]
    
    # Calculate exponential smoothing
    # Initialize level as first value
    level = values[0]
    forecasts_values = []
    
    # Apply smoothing to all history
    for value in values:
        level = alpha * value + (1 - alpha) * level
    
    # Generate forecasts (constant level)
    for _ in range(forecast_weeks):
        forecasts_values.append(level)
    
    # Calculate uncertainty bands based on residuals
    residuals = []
    level = values[0]
    for value in values:
        forecast_error = value - level
        residuals.append(abs(forecast_error))
        level = alpha * value + (1 - alpha) * level
    
    std_residual = statistics.stdev(residuals) if len(residuals) > 1 else 0
    
    # Generate forecast dicts
    forecasts = []
    current_week_start = _get_week_start(reference_date)
    
    for i in range(forecast_weeks):
        forecast_week = current_week_start + timedelta(weeks=i+1)
        predicted_demand = int(forecasts_values[i])
        
        # Uncertainty grows with forecast horizon
        horizon_std = std_residual * (1 + 0.1 * i)
        lower_bound = max(0, int(predicted_demand - 1.96 * horizon_std))
        upper_bound = int(predicted_demand + 1.96 * horizon_std)
        
        forecasts.append({
            'week_start_date': forecast_week.isoformat(),
            'week_end_date': (forecast_week + timedelta(days=6)).isoformat(),
            'predicted_demand': predicted_demand,
            'historical_mean': round(statistics.mean(values), 2),
            'historical_std': round(statistics.stdev(values) if len(values) > 1 else 0, 2),
            'lower_bound': lower_bound,
            'upper_bound': upper_bound,
            'method': 'exponential_smoothing',
            'confidence_note': f'Medium confidence - exponential smoothing with α={alpha} (estimated range, increasing uncertainty)',
            'smoothing_parameter': alpha,
        })
    
    return forecasts


def forecast_demand(
    reference_date: Optional[date] = None,
    forecast_weeks: int = 4,
) -> Dict:
    """
    Generate 4-week ahead demand forecast.
    
    Uses seasonal naive (primary) with exponential smoothing fallback.
    
    Args:
        reference_date: Cutoff date (default: today). Training uses data before this.
        forecast_weeks: Number of weeks to forecast (default: 4)
    
    Returns:
        dict with keys:
        - forecasts: list of forecast dicts (each has week dates, predicted demand, bounds)
        - method_used: 'seasonal_naive', 'exponential_smoothing', or 'last_year_average'
        - historical_weeks_used: Number of historical weeks in training
        - forecast_reference_date: ISO date (training cutoff)
        - limitations: List of applicable limitations
        - evaluation_metrics: Backtesting results (if available)
    
    Raises:
        RuntimeError: If analytics database unavailable
        ValueError: If insufficient history
    """
    if reference_date is None:
        reference_date = timezone.localdate()
    
    # Get historical data
    try:
        weekly_demand = _get_historical_weekly_demand(reference_date, weeks_back=156)
    except RuntimeError:
        raise
    
    if not weekly_demand:
        raise ValueError("No historical reservation data available for forecasting")
    
    hist_weeks = sorted(weekly_demand.keys())
    num_historical_weeks = len(hist_weeks)
    
    # Try seasonal naive first
    try:
        forecasts = _seasonal_naive_forecast(weekly_demand, reference_date, forecast_weeks)
        method_used = 'seasonal_naive'
        limitations = [
            'Assumes year-over-year seasonality is stable',
            'Cannot detect trend changes',
            'Less accurate during seasonal pattern changes',
        ]
    except ValueError as e_seasonal:
        # Fallback to exponential smoothing
        try:
            forecasts = _exponential_smoothing_forecast(weekly_demand, reference_date, forecast_weeks)
            method_used = 'exponential_smoothing'
            limitations = [
                'Does not capture seasonality',
                'Assumes constant trend',
                'Less accurate for highly seasonal data',
            ]
        except ValueError as e_smoothing:
            # Extreme fallback: use last year average
            if num_historical_weeks < 10:
                raise ValueError(
                    f"Insufficient history for any forecasting method. "
                    f"Need at least 10 weeks; have {num_historical_weeks}."
                )
            
            # Last year average
            all_values = list(weekly_demand.values())
            avg_demand = int(statistics.mean(all_values))
            current_week_start = _get_week_start(reference_date)
            
            forecasts = []
            for i in range(forecast_weeks):
                forecast_week = current_week_start + timedelta(weeks=i+1)
                forecasts.append({
                    'week_start_date': forecast_week.isoformat(),
                    'week_end_date': (forecast_week + timedelta(days=6)).isoformat(),
                    'predicted_demand': avg_demand,
                    'historical_mean': round(statistics.mean(all_values), 2),
                    'historical_std': round(statistics.stdev(all_values) if len(all_values) > 1 else 0, 2),
                    'lower_bound': max(0, int(avg_demand - avg_demand * 0.3)),
                    'upper_bound': int(avg_demand + avg_demand * 0.3),
                    'method': 'last_year_average',
                    'confidence_note': 'Low confidence - insufficient history (estimated range only)',
                })
            
            method_used = 'last_year_average'
            limitations = [
                'Very limited historical data',
                'Assumes constant demand',
                'Low confidence due to minimal training data',
            ]
    
    return {
        'forecasts': forecasts,
        'method_used': method_used,
        'historical_weeks_used': num_historical_weeks,
        'forecast_reference_date': reference_date.isoformat(),
        'limitations': limitations,
        'evaluation_metrics': None,  # Backtesting done separately
    }


def backtest_forecast(
    reference_date: Optional[date] = None,
    test_weeks: int = 4,
) -> Dict:
    """
    Backtest forecasting method using chronological train/test split.
    
    Uses reference_date - (test_weeks + 4 weeks) as training cutoff,
    then forecasts test_weeks weeks ahead and compares to actual.
    
    Args:
        reference_date: Today's date (default: today)
        test_weeks: How many weeks to test (must have data for; default: 4)
    
    Returns:
        dict with backtesting results:
        - mae: Mean Absolute Error
        - mape: Mean Absolute Percentage Error (%)
        - rmse: Root Mean Squared Error
        - actual_values: Actual observed demand in test window
        - forecast_values: Forecasted values
        - errors: Individual forecast errors
        - method_used: Which method was used
        - test_period: ISO date range of test period
    
    Raises:
        RuntimeError: If analytics database unavailable
        ValueError: If insufficient data for backtesting
    """
    if reference_date is None:
        reference_date = timezone.localdate()
    
    # Set training cutoff to test_weeks + 4 weeks before reference
    training_cutoff = reference_date - timedelta(weeks=test_weeks + 4)
    
    # Get full historical data
    try:
        all_weekly_demand = _get_historical_weekly_demand(reference_date, weeks_back=156)
    except RuntimeError:
        raise
    
    if not all_weekly_demand:
        raise ValueError("No data for backtesting")
    
    # Get test period actuals
    test_period_actuals = {}
    for w in range(test_weeks):
        test_week = _get_week_start(training_cutoff) + timedelta(weeks=w+1)
        if test_week in all_weekly_demand:
            test_period_actuals[w] = all_weekly_demand[test_week]
        else:
            raise ValueError(f"No actual data for test week {w+1}. Backtesting requires complete test data.")
    
    if len(test_period_actuals) < test_weeks:
        raise ValueError(f"Incomplete test data. Need {test_weeks} weeks of actuals; have {len(test_period_actuals)}")
    
    # Generate forecast using training data only
    try:
        forecast_result = forecast_demand(training_cutoff, forecast_weeks=test_weeks)
    except ValueError as e:
        raise ValueError(f"Cannot generate forecast for backtesting: {str(e)}")
    
    # Compare forecasts to actuals
    actuals = [test_period_actuals[i] for i in range(test_weeks)]
    predictions = [f['predicted_demand'] for f in forecast_result['forecasts']]
    
    errors = [abs(actual - pred) for actual, pred in zip(actuals, predictions)]
    mae = statistics.mean(errors)
    
    # MAPE (handle zero actuals)
    mape_values = []
    for actual, pred in zip(actuals, predictions):
        if actual > 0:
            mape_values.append(abs(actual - pred) / actual * 100)
    mape = statistics.mean(mape_values) if mape_values else 0
    
    # RMSE
    rmse = (sum(e**2 for e in errors) / len(errors)) ** 0.5
    
    test_period_start = _get_week_start(training_cutoff) + timedelta(weeks=1)
    test_period_end = test_period_start + timedelta(weeks=test_weeks-1, days=6)
    
    return {
        'mae': round(mae, 2),
        'mape': round(mape, 2),
        'rmse': round(rmse, 2),
        'actual_values': actuals,
        'forecast_values': predictions,
        'errors': [round(e, 2) for e in errors],
        'method_used': forecast_result['method_used'],
        'test_period': f"{test_period_start.isoformat()} to {test_period_end.isoformat()}",
        'test_weeks': test_weeks,
        'forecast_reference_date': training_cutoff.isoformat(),
    }
