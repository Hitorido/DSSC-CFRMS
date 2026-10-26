from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list_view, name='notification_list'),
    path('<int:pk>/read/', views.mark_notification_read_view, name='mark_read'),
    path('read-all/', views.mark_all_notifications_read_view, name='mark_all_read'),
]
