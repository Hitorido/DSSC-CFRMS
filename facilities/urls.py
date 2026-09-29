from django.urls import path
from . import views

app_name = 'facilities'

urlpatterns = [
    path('', views.facility_list_view, name='facility_list'),
]
