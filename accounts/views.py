from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone

from facilities.models import Facility
from reservations.models import Reservation

from .forms import ProfileForm, RegisterForm
from .models import User


@login_required
def home_view(request):
    """
    Authenticated landing page with role-specific dashboard data.

    Backend-Frontend Contract:
    - Template: 'home.html'
    - Context:
        - user: request.user (accounts.User instance with username, role, department, etc.)
    """
    facility_summary = Facility.objects.aggregate(
        total=Count('pk'),
        available=Count('pk', filter=Q(status=Facility.Status.AVAILABLE)),
    )
    user = request.user
    if user.is_staff_role or user.is_admin_role:
        reservation_qs = Reservation.objects.all()
    else:
        reservation_qs = Reservation.objects.filter(requested_by=user)

    today = timezone.localdate()
    reservation_summary = reservation_qs.aggregate(
        total=Count('pk'),
        pending=Count('pk', filter=Q(status=Reservation.Status.PENDING)),
        approved=Count('pk', filter=Q(status=Reservation.Status.APPROVED)),
    )
    context = {
        'user': user,
        'facility_summary': facility_summary,
        'total_facilities': facility_summary['total'],
        'total_reservations': reservation_summary['total'],
        'pending_reservations': reservation_summary['pending'],
        'approved_reservations': reservation_summary['approved'],
        'todays_reservations': reservation_qs.filter(reservation_date=today).count(),
        'dashboard_title': 'Dashboard',
        'dashboard_subtitle': 'Your campus spaces, all in one place.',
        'dashboard_role': 'requester',
    }

    if user.is_student_role:
        context.update({
            'dashboard_title': 'Student Dashboard',
            'dashboard_subtitle': 'Find a campus space and keep track of your bookings.',
            'dashboard_role': 'student',
        })
    elif user.is_faculty_role:
        context.update({
            'dashboard_title': 'Faculty Dashboard',
            'dashboard_subtitle': 'Plan and manage your campus facility reservations.',
            'dashboard_role': 'faculty',
        })
    elif user.is_staff_role:
        context.update({
            'dashboard_title': 'Staff Dashboard',
            'dashboard_subtitle': 'Review reservation requests and coordinate campus bookings.',
            'dashboard_role': 'staff',
        })
    elif user.is_admin_role:
        context.update({
            'dashboard_title': 'Admin Dashboard',
            'dashboard_subtitle': 'Monitor users, facilities, and reservation activity.',
            'dashboard_role': 'admin',
        })

    if user.is_requester_role:
        user_reservations = reservation_qs
        local_now = timezone.localtime()
        context['reservation_summary'] = reservation_summary
        context['upcoming_reservations'] = user_reservations.filter(
            Q(reservation_date__gt=local_now.date())
            | Q(reservation_date=local_now.date(), end_time__gte=local_now.time()),
            status__in=[Reservation.Status.PENDING, Reservation.Status.APPROVED],
        ).select_related('facility').order_by('reservation_date', 'start_time')[:3]
    elif user.is_staff_role:
        context['pending_reservation_count'] = reservation_summary['pending']
        context['today_booking_count'] = reservation_qs.filter(
            reservation_date=timezone.localdate(),
            status=Reservation.Status.APPROVED,
        ).count()
    elif user.is_admin_role:
        context['system_reservation_summary'] = reservation_summary
        context['pending_reservation_count'] = context['system_reservation_summary']['pending']
        context['active_account_count'] = User.objects.filter(is_active=True).count()

    return render(request, 'home.html', context)


def register_view(request):
    """
    Public self-registration for REQUESTER accounts.

    New accounts are always created with role=REQUESTER.
    Role elevation (STAFF / ADMIN) is handled by an Admin via /admin/.

    GET:  Display blank RegisterForm.
    POST: Validate, save, log the user in, redirect to home.
    """
    # Already logged-in users have no reason to register again
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


@login_required
def profile_view(request):
    """View and update the current user's personal profile details."""
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated.')
            return redirect('accounts:profile')
    else:
        form = ProfileForm(instance=request.user)

    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def settings_view(request):
    """Display account and appearance preferences."""
    return render(request, 'accounts/settings.html')
