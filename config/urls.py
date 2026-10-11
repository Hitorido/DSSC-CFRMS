from django.contrib import admin
from django.urls import include, path

from accounts.views import home_view

urlpatterns = [
    path('admin/', admin.site.urls),

    # Application Landing / Dashboard
    path('', home_view, name='home'),

    # Application Modules
    path('', include('accounts.urls')),
    path('facilities/', include('facilities.urls')),
    path('reservations/', include('reservations.urls')),
    path('notifications/', include('notifications.urls')),
    
    # Analytics JSON API (Phase 6.5.2)
    path('api/analytics/', include('analytics.urls')),
]
