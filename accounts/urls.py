from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from .forms import CFRMSPasswordChangeForm
from .views import admin_dashboard_view, profile_view, register_view, settings_view

app_name = 'accounts'

urlpatterns = [
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='accounts/login.html',
            redirect_authenticated_user=True,
        ),
        name='login',
    ),
    path(
        'logout/',
        auth_views.LogoutView.as_view(),
        name='logout',
    ),
    path(
        'register/',
        register_view,
        name='register',
    ),
    path('profile/', profile_view, name='profile'),
    path('settings/', settings_view, name='settings'),
    path('admin-console/', admin_dashboard_view, name='admin_dashboard'),
    path(
        'password/change/',
        auth_views.PasswordChangeView.as_view(
            form_class=CFRMSPasswordChangeForm,
            template_name='accounts/password_change.html',
            success_url=reverse_lazy('accounts:password_change_done'),
        ),
        name='password_change',
    ),
    path(
        'password/change/done/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='accounts/password_change_done.html',
        ),
        name='password_change_done',
    ),
]
