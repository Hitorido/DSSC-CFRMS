from django.urls import path
from . import views

app_name = 'facilities'

urlpatterns = [
    # Facility list (all authenticated users)
    path('', views.facility_list_view, name='facility_list'),

    # Maintenance management (STAFF / ADMIN only)
    path('maintenance/', views.maintenance_list_view, name='maintenance_list'),
    path('maintenance/create/', views.maintenance_create_view, name='maintenance_create'),
    path('maintenance/<int:pk>/', views.maintenance_detail_view, name='maintenance_detail'),
    path('maintenance/<int:pk>/complete/', views.maintenance_complete_view, name='maintenance_complete'),
    path('maintenance/<int:pk>/cancel/', views.maintenance_cancel_view, name='maintenance_cancel'),
]
