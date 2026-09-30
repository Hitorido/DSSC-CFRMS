from django.urls import path
from . import views

app_name = 'reservations'

urlpatterns = [
    # Requester workflow
    path('my/', views.my_reservations_view, name='my_reservations'),
    path('create/', views.create_reservation_view, name='create_reservation'),
    path('report/', views.reservation_report_view, name='reservation_report'),
    path('<int:pk>/', views.reservation_detail_view, name='reservation_detail'),
    path('<int:pk>/cancel/', views.cancel_reservation_view, name='cancel_reservation'),

    # Staff / Admin workflow
    path('pending/', views.pending_reservations_view, name='pending_reservations'),
    path('<int:pk>/approve/', views.approve_reservation_view, name='approve_reservation'),
    path('<int:pk>/reject/', views.reject_reservation_view, name='reject_reservation'),
]
