"""
Analytics cache utility module - Task 13.

Provides cache management functions for analytics features.
TTL: 1 hour for all analytics cache entries.

Cache Keys:
- forecast_{months}_{periods}: Demand forecast (parameterized)
- peak_hours: Peak hours analysis
- peak_days: Peak days analysis
- occupancy_by_facility: Occupancy calculations
- prescriptive_recommendations: Generated recommendations
- facility_analytics_dashboard: Full dashboard analytics
"""

from django.core.cache import cache


def invalidate_analytics_cache():
    """
    Invalidate all analytics cache entries.
    
    Called when:
    - Reservation status changes (created, approved, rejected, cancelled, completed)
    - Maintenance schedule changes
    - Manual cache flush (admin action)
    
    This ensures analytics dashboards reflect current data within the cache TTL
    window (1 hour default).
    """
    cache_keys = [
        # Forecast variants (different month/period combinations)
        'forecast_3_1',
        'forecast_3_3',
        'forecast_6_3',
        'forecast_12_6',
        
        # Peak analysis
        'peak_hours',
        'peak_days',
        
        # Occupancy analysis
        'occupancy_by_facility',
        
        # Recommendations
        'prescriptive_recommendations',
        
        # Dashboard analytics
        'facility_analytics_dashboard',
        'admin_dashboard_analytics',
        'staff_dashboard_analytics',
    ]
    
    for key in cache_keys:
        cache.delete(key)


def invalidate_specific_forecast(months: int = 6, periods: int = 3):
    """
    Invalidate a specific forecast cache entry.
    
    Args:
        months: Number of historical months (default 6)
        periods: Number of forecast periods (default 3)
    """
    cache_key = f'forecast_{months}_{periods}'
    cache.delete(cache_key)


def clear_all_caches():
    """
    Clear all analytics caches (used for testing or manual cache flush).
    WARNING: This clears all cache entries, not just analytics.
    Use invalidate_analytics_cache() for analytics-specific cache clearing.
    """
    cache.clear()


def get_cache_info(key: str):
    """
    Get information about a cache entry (debugging).
    
    Args:
        key: Cache key to check
        
    Returns:
        Cache value if exists, None otherwise
    """
    return cache.get(key, None)


def set_analytics_cache(key: str, value, ttl: int = 3600):
    """
    Set an analytics cache entry with standard TTL.
    
    Args:
        key: Cache key
        value: Value to cache
        ttl: Time-to-live in seconds (default 1 hour)
    """
    cache.set(key, value, ttl)
