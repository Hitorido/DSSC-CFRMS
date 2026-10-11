from django.conf import settings
from django.conf.urls.static import static
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
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
