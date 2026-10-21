from datetime import date

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connections
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from facilities.models import Facility
from reservations.models import Reservation

from .forms import ProfileForm, RegisterForm
from .decorators import admin_required
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
    facility_data_scope = 'operational'
    if not facility_summary['total'] and 'analytics' in connections.databases:
        facility_summary = Facility.objects.using('analytics').filter(
            is_synthetic=True,
        ).aggregate(
            total=Count('pk'),
            available=Count('pk', filter=Q(status=Facility.Status.AVAILABLE)),
        )
        facility_data_scope = 'analytics_sample'
    user = request.user
    if user.is_reservation_reviewer:
        reservation_qs = Reservation.objects.filter(
            requested_by__role=User.Role.REQUESTER
        ).exclude(requested_by__user_type=User.UserType.FACULTY)
    elif user.is_student_role:
        reservation_qs = Reservation.objects.filter(requested_by=user)
    else:
        reservation_qs = Reservation.objects.none()

    today = timezone.localdate()
    reservation_summary = reservation_qs.aggregate(
        total=Count('pk'),
        pending=Count('pk', filter=Q(status=Reservation.Status.PENDING)),
        approved=Count('pk', filter=Q(status=Reservation.Status.APPROVED)),
        completed=Count('pk', filter=Q(status=Reservation.Status.COMPLETED)),
    )

    show_dashboard_analytics = (
        user.is_faculty_role
        or user.is_unassigned_faculty_account
        or user.is_admin_role
    )

    context = {
        'user': user,
        'facility_summary': facility_summary,
        'facility_data_scope': facility_data_scope,
        'total_facilities': facility_summary['total'],
        'total_reservations': reservation_summary['total'],
        'pending_reservations': reservation_summary['pending'],
        'approved_reservations': reservation_summary['approved'],
        'todays_reservations': reservation_qs.filter(reservation_date=today).count(),
        'dashboard_title': 'Dashboard',
        'dashboard_subtitle': 'Your campus spaces, all in one place.',
        'dashboard_role': 'requester',
        'show_dashboard_analytics': show_dashboard_analytics,
    }

    if show_dashboard_analytics:
        # The Faculty and Admin dashboards can use synthetic analytics data
        # when operational reservation history is not available yet.
        chart_reservation_qs = reservation_qs
        chart_data_scope = 'operational'
        if (
            'analytics' in connections.databases
            and (user.is_admin_role or not chart_reservation_qs.exists())
        ):
            chart_reservation_qs = Reservation.objects.using('analytics').filter(
                is_synthetic=True,
            )
            chart_data_scope = 'synthetic'

        # Six calendar months of role-scoped activity for the dashboard charts.
        current_month = today.year * 12 + today.month - 1
        chart_months = []
        for months_ago in reversed(range(6)):
            month_index = current_month - months_ago
            chart_months.append(date(month_index // 12, month_index % 12 + 1, 1))
        next_month_index = current_month + 1
        next_month = date(next_month_index // 12, next_month_index % 12 + 1, 1)
        chart_start = chart_months[0]
        monthly_counts = {
            row['month'].strftime('%Y-%m'): row['total']
            for row in chart_reservation_qs.filter(
                reservation_date__gte=chart_start,
                reservation_date__lt=next_month,
            ).annotate(month=TruncMonth('reservation_date'))
                .values('month')
                .annotate(total=Count('pk'))
        }
        chart_status_counts = {
            row['status']: row['total']
            for row in chart_reservation_qs.values('status').annotate(total=Count('pk'))
        }
        chart_statuses = [
            {'label': label, 'total': chart_status_counts.get(value, 0)}
            for value, label in Reservation.Status.choices
        ]
        chart_facilities = list(
            chart_reservation_qs.filter(
                reservation_date__gte=chart_start,
                reservation_date__lt=next_month,
            ).values('facility__name')
            .annotate(total=Count('pk'))
            .order_by('-total', 'facility__name')[:5]
        )
        context.update({
            'chart_month_labels': [month.strftime('%b %Y') for month in chart_months],
            'chart_month_values': [
                monthly_counts.get(month.strftime('%Y-%m'), 0) for month in chart_months
            ],
            'chart_month_rows': [
                {
                    'label': month.strftime('%b %Y'),
                    'total': monthly_counts.get(month.strftime('%Y-%m'), 0),
                }
                for month in chart_months
            ],
            'chart_statuses': chart_statuses,
            'chart_facility_labels': [row['facility__name'] for row in chart_facilities],
            'chart_facility_values': [row['total'] for row in chart_facilities],
            'chart_facility_rows': [
                {'label': row['facility__name'], 'total': row['total']}
                for row in chart_facilities
            ],
            'chart_data_scope': chart_data_scope,
            'chart_has_status_data': any(row['total'] for row in chart_statuses),
            'chart_has_facility_data': bool(chart_facilities),
            'chart_has_month_data': any(monthly_counts.values()),
        })

    if user.is_student_role:
        context.update({
            'dashboard_title': 'Student Dashboard',
            'dashboard_subtitle': 'Find a campus space and keep track of your bookings.',
            'dashboard_role': 'student',
        })
    elif user.is_faculty_role:
        context.update({
            'dashboard_title': 'Faculty Dashboard',
            'dashboard_subtitle': 'Review student facility requests and track reservation decisions.',
            'dashboard_role': 'faculty',
        })
    elif user.is_unassigned_faculty_account:
        context.update({
            'dashboard_title': 'Faculty Dashboard',
            'dashboard_subtitle': 'An administrator must assign the Faculty role before you can review reservation requests.',
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

    if user.is_student_role:
        user_reservations = reservation_qs
        local_now = timezone.localtime()
        context['reservation_summary'] = reservation_summary
        context['upcoming_reservations'] = user_reservations.filter(
            Q(reservation_date__gt=local_now.date())
            | Q(reservation_date=local_now.date(), end_time__gte=local_now.time()),
            status__in=[Reservation.Status.PENDING, Reservation.Status.APPROVED],
        ).select_related('facility').order_by('reservation_date', 'start_time')[:3]
    elif user.is_staff_role or user.is_faculty_role:
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
    Public self-registration for student requester accounts.

    New accounts are always created with role=REQUESTER.
    Faculty, Staff, and Admin roles are assigned in the CFRMS Admin Console.

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


@login_required
@admin_required
def admin_dashboard_view(request):
    """CFRMS administration for app Admins without requiring Django is_staff."""
    search = request.GET.get('search', '').strip()
    role_filter = request.GET.get('role', '').strip()

    if request.method == 'POST':
        target = get_object_or_404(User, pk=request.POST.get('user_id'))
        requested_role = request.POST.get('role', '')
        valid_roles = dict(User.Role.choices)

        if target.pk == request.user.pk:
            messages.error(request, 'You cannot change your own account role here.')
        elif target.is_superuser:
            messages.error(request, 'Django superuser accounts are protected on this page.')
        elif requested_role not in valid_roles:
            messages.error(request, 'Choose a valid CFRMS role.')
        else:
            target.role = requested_role
            target.save(update_fields=['role'])
            messages.success(
                request,
                f'{target.get_username()} is now assigned the {target.get_role_display()} role.',
            )

        return redirect('accounts:admin_dashboard')

    accounts = User.objects.all().order_by('username')
    if search:
        accounts = accounts.filter(
            Q(username__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(department__icontains=search)
        )
    if role_filter in dict(User.Role.choices):
        accounts = accounts.filter(role=role_filter)
    account_page = Paginator(accounts, 20).get_page(request.GET.get('page'))

    total_facilities = Facility.objects.count()
    facility_data_scope = 'operational'
    if not total_facilities and 'analytics' in connections.databases:
        total_facilities = Facility.objects.using('analytics').filter(is_synthetic=True).count()
        facility_data_scope = 'analytics_sample'

    context = {
        'accounts_page': account_page,
        'account_roles': User.Role.choices,
        'filters': {'search': search, 'role': role_filter},
        'total_accounts': User.objects.count(),
        'active_accounts': User.objects.filter(is_active=True).count(),
        'admin_accounts': User.objects.filter(role=User.Role.ADMIN).count(),
        'pending_reservations': Reservation.objects.filter(
            status=Reservation.Status.PENDING,
        ).count(),
        'total_facilities': total_facilities,
        'facility_data_scope': facility_data_scope,
    }
    return render(request, 'accounts/admin_dashboard.html', context)
