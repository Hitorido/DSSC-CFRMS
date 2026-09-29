from django.urls import path
from . import views

app_name = 'reservations'

urlpatterns = [
    path('my/', views.my_reservations_view, name='my_reservations'),
    path('pending/', views.pending_reservations_view, name='pending_reservations'),
]
