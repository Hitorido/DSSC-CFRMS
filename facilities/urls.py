from django.urls import path
from . import views

app_name = 'facilities'

urlpatterns = [
    path('create/', views.facility_create_view, name='facility_create'),
    path('', views.facility_list_view, name='facility_list'),
]
