"""
URL routing for analytics JSON API endpoints - Phase 6.5.2.

All endpoints are under /api/analytics/ path.
All endpoints require ADMIN role authentication.
"""

from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Reservation KPIs endpoint
    path('reservation-kpis/', views.reservation_kpis, name='reservation-kpis'),
    
    # Status distribution endpoint
    path('status-distribution/', views.status_distribution, name='status-distribution'),
    
    # Monthly trends endpoint
    path('monthly-trends/', views.monthly_trends, name='monthly-trends'),
    
    # Facility demand endpoint
    path('facility-demand/', views.facility_demand, name='facility-demand'),
    
    # Peak booking periods endpoint
    path('peak-booking-periods/', views.peak_booking_periods, name='peak-booking-periods'),
    
    # Facility booking intensity endpoint
    path('facility-booking-intensity/', views.facility_booking_intensity, name='facility-booking-intensity'),
    
    # Demand forecasting endpoint (Phase 6.5.3)
    path('demand-forecast/', views.demand_forecast, name='demand-forecast'),
    
    # Peak hours analysis endpoint (Task 9)
    path('peak-hours/', views.peak_hours, name='peak-hours'),
    
    # Occupancy by facility endpoint (Task 9)
    path('occupancy-by-facility/', views.occupancy_by_facility, name='occupancy-by-facility'),
    
    # Recommendations endpoint (Task 9)
    path('recommendations/', views.recommendations, name='recommendations'),
    
    # System calendar endpoint (Task 9)
    path('system-calendar/', views.system_calendar, name='system-calendar'),
]
