from django.urls import path
from . import views
from . import calendar_api

app_name = 'facilities'

urlpatterns = [
    path('create/', views.facility_create_view, name='facility_create'),
    # Facility list (all authenticated users)
    path('', views.facility_list_view, name='facility_list'),
    path('<int:pk>/', views.facility_detail_view, name='facility_detail'),
    
    # Facility booking calendar
    path('<int:pk>/calendar/', views.facility_calendar_view, name='facility_calendar'),

    # Calendar API endpoints
    path('<int:facility_id>/calendar-api/<str:date_str>/', calendar_api.facility_calendar_day, name='api_calendar_day'),
    path('<int:facility_id>/calendar-api/<int:year>/<int:month>/', calendar_api.facility_calendar_month, name='api_calendar_month'),

    # Maintenance management (STAFF / ADMIN only)
    path('maintenance/', views.maintenance_list_view, name='maintenance_list'),
    path('maintenance/create/', views.maintenance_create_view, name='maintenance_create'),
    path('maintenance/<int:pk>/', views.maintenance_detail_view, name='maintenance_detail'),
    path('maintenance/<int:pk>/complete/', views.maintenance_complete_view, name='maintenance_complete'),
    path('maintenance/<int:pk>/cancel/', views.maintenance_cancel_view, name='maintenance_cancel'),
]
