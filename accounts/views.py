import calendar
from datetime import date, datetime as dt, timedelta, time
from collections import Counter, defaultdict

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import connections
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from config.list_utils import filter_query_string, paginate_queryset
from facilities.models import Facility, FacilityMaintenance
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
        # For summary metrics, count only the student's own reservations
        reservation_qs = Reservation.objects.filter(requested_by=user)
    else:
        reservation_qs = Reservation.objects.none()

    today = timezone.localdate()
    calendar_month_value = request.GET.get('calendar_month', '')
    try:
        calendar_year, calendar_month = (int(part) for part in calendar_month_value.split('-', 1))
        if (
            len(calendar_month_value) != 7
            or not (1 <= calendar_month <= 12)
            or not (2000 <= calendar_year <= 2100)
        ):
            raise ValueError
    except (TypeError, ValueError):
        calendar_year, calendar_month = today.year, today.month

    calendar_month_start = date(calendar_year, calendar_month, 1)
    calendar_month_end = date(
        calendar_year,
        calendar_month,
        calendar.monthrange(calendar_year, calendar_month)[1],
    )
    calendar_previous_month = (calendar_month_start - timedelta(days=1)).strftime('%Y-%m')
    calendar_next_month = (calendar_month_end + timedelta(days=1)).strftime('%Y-%m')
    # For the calendar grid, students see ALL active campus reservations so they can
    # gauge day availability/occupancy. Their own-reservation metrics use reservation_qs.
    if user.is_student_role:
        calendar_qs = Reservation.objects.filter(
            status__in=[
                Reservation.Status.PENDING,
                Reservation.Status.APPROVED,
                Reservation.Status.COMPLETED,
            ]
        ).select_related('facility', 'requested_by')
    else:
        calendar_qs = reservation_qs.select_related('facility', 'requested_by')

    calendar_events_by_date = {}
    calendar_reservations = calendar_qs.filter(
        reservation_date__range=(calendar_month_start, calendar_month_end),
    ).order_by('reservation_date', 'start_time')
    for reservation in calendar_reservations:
        can_view_details = (
            user.is_student_role and reservation.requested_by_id == user.pk
        ) or (
            user.is_reservation_reviewer
            and reservation.requested_by_id != user.pk
            and reservation.requested_by.is_student_role
        )
        requester_name = reservation.requested_by.get_full_name() or reservation.requested_by.username
        calendar_events_by_date.setdefault(reservation.reservation_date, []).append({
            'reservation_id': reservation.pk,
            'facility_name': reservation.facility.name,
            'requester_name': requester_name if user.is_reservation_reviewer else '',
            'start_time': reservation.start_time,
            'end_time': reservation.end_time,
            'label': reservation.get_status_display(),
            'status_class': reservation.status.lower(),
            'can_view_details': can_view_details,
            'kind': 'reservation',
        })

    # Include SCHEDULED maintenance for admin/staff users
    if user.is_staff_role or user.is_admin_role:
        calendar_maintenance = FacilityMaintenance.objects.filter(
            maintenance_date__range=(calendar_month_start, calendar_month_end),
            status=FacilityMaintenance.Status.SCHEDULED,
        ).select_related('facility').order_by('maintenance_date', 'start_time')
        for maintenance in calendar_maintenance:
            calendar_events_by_date.setdefault(maintenance.maintenance_date, []).append({
                'facility_name': maintenance.facility.name,
                'start_time': maintenance.start_time,
                'end_time': maintenance.end_time,
                'label': 'Maintenance',
                'status_class': 'maintenance',
                'kind': 'maintenance',
            })

    # Compute per-day occupancy colour for the student calendar.
    # We use a simple ratio: bookings that day / (total active facilities * 2 time-slots).
    # Thresholds: 0–33% green, 34–66% yellow, 67%+ red.
    _available_facility_count = max(Facility.objects.filter(status=Facility.Status.AVAILABLE).count(), 1)
    _DAILY_CAPACITY = _available_facility_count * 2  # rough 2-slot-per-facility baseline

    def _day_color(event_count):
        if event_count == 0:
            return ''
        ratio = min(event_count / _DAILY_CAPACITY, 1.0)
        if ratio <= 0.33:
            return 'green'
        elif ratio <= 0.66:
            return 'yellow'
        return 'red'

    dashboard_calendar_weeks = []
    for week in calendar.Calendar(firstweekday=6).monthdatescalendar(calendar_year, calendar_month):
        dashboard_calendar_weeks.append([
            {
                'date': day,
                'in_month': day.month == calendar_month,
                'is_today': day == today,
                'is_past': day < today,
                'events': sorted(
                    calendar_events_by_date.get(day, []),
                    key=lambda event: event['start_time'],
                ),
                'event_count': len(calendar_events_by_date.get(day, [])),
                'color_code': _day_color(len(calendar_events_by_date.get(day, []))),
            }
            for day in week
        ])

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
        or user.is_staff_role
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
        'dashboard_calendar_month': calendar_month_start.strftime('%B %Y'),
        'dashboard_calendar_previous_month': calendar_previous_month,
        'dashboard_calendar_next_month': calendar_next_month,
        'dashboard_calendar_weeks': dashboard_calendar_weeks,
        'dashboard_calendar_weekdays': ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
        'dashboard_calendar_reservation_count': sum(
            len(events) for events in calendar_events_by_date.values()
        ),
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

    # For admin/staff, add predictive demand forecast and prescriptive recommendations
    if user.is_admin_role or user.is_staff_role:
        try:
            from analytics.services import PredictiveAnalytics, PrescriptiveAnalytics
            _forecast = PredictiveAnalytics.compute_demand_forecast()
            context['demand_forecast_data'] = _forecast
            _recs = PrescriptiveAnalytics.generate_recommendations()
            context['home_recommendations'] = _recs.get('recommendations', [])
        except Exception:
            context['demand_forecast_data'] = None
            context['home_recommendations'] = []

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
        context['home_booking_facilities'] = list(
            Facility.objects.using('default')
            .filter(status=Facility.Status.AVAILABLE)
            .select_related('facility_type')
            .order_by('name')
        )
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


@login_required
def staff_dashboard_view(request):
    """
    Staff-specific dashboard with operational analytics.
    
    Shows today's operations, assigned facility alerts, peak hours for the week,
    and facility-specific recommendations for immediate action items.
    """
    user = request.user
    if not user.is_staff_role:
        return redirect('home')
    
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    # Get reservations for staff (all reservations they review)
    reservation_qs = Reservation.objects.filter(
        requested_by__role=User.Role.REQUESTER
    ).exclude(requested_by__user_type=User.UserType.FACULTY)
    
    # Get today's reservations
    todays_reservations = reservation_qs.filter(
        reservation_date=today,
        status=Reservation.Status.APPROVED
    ).select_related('facility')
    
    todays_reservation_count = todays_reservations.count()
    
    # Find busiest facility today
    busiest_facility_today = None
    if todays_reservations.exists():
        busiest = (
            todays_reservations
            .values('facility__name')
            .annotate(count=Count('id'))
            .order_by('-count')
            .first()
        )
        if busiest:
            busiest_facility_today = busiest['facility__name']
    
    # Calculate next 3 hours occupancy
    current_time = timezone.localtime()
    next_hours_occupancy = []
    
    for hour_offset in range(3):
        check_time = current_time + timedelta(hours=hour_offset)
        hour_start = time(check_time.hour, 0)
        hour_end = time(check_time.hour, 59, 59)
        
        # Count reservations during this hour across all facilities
        reservations_in_hour = todays_reservations.filter(
            start_time__lte=hour_end,
            end_time__gte=hour_start
        ).count()
        
        # Calculate occupancy percentage (assuming capacity of 10 facilities * 1 slot each = 10 total slots)
        max_facilities = max(Facility.objects.filter(status=Facility.Status.AVAILABLE).count(), 1)
        occupancy_percent = min(100, int((reservations_in_hour / max_facilities) * 100)) if max_facilities > 0 else 0
        
        next_hours_occupancy.append({
            'hour_label': check_time.strftime('%H:%M'),
            'occupancy_percent': occupancy_percent,
        })
    
    # Get pending maintenance alerts for this week
    maintenance_this_week = FacilityMaintenance.objects.filter(
        maintenance_date__range=(today, today + timedelta(days=7)),
        status=FacilityMaintenance.Status.SCHEDULED
    ).select_related('facility').order_by('maintenance_date', 'start_time')
    
    # Get fully booked hours today and tomorrow
    fully_booked_alerts = []
    for check_date in [today, today + timedelta(days=1)]:
        hourly_bookings = defaultdict(int)
        daily_reservations = reservation_qs.filter(
            reservation_date=check_date,
            status=Reservation.Status.APPROVED
        )
        
        for res in daily_reservations:
            hour = res.start_time.hour
            hourly_bookings[hour] += 1
        
        # Find fully booked hours (more than 5 simultaneous bookings)
        for hour, count in hourly_bookings.items():
            if count > 5:
                date_label = "Today" if check_date == today else "Tomorrow"
                fully_booked_alerts.append({
                    'facility': None,
                    'hour': f"{hour:02d}:00",
                    'date': date_label,
                    'booking_count': count,
                })
    
    # Aggregate facility alerts
    facility_alerts = []
    
    # Add maintenance alerts
    for maintenance in maintenance_this_week:
        maintenance_date_label = "Today" if maintenance.maintenance_date == today else maintenance.maintenance_date.strftime("%a, %b %d")
        facility_alerts.append({
            'title': f"Maintenance: {maintenance.facility.name}",
            'message': maintenance.title or f"Scheduled maintenance at {maintenance.facility.name}",
            'details': f"{maintenance_date_label} • {maintenance.start_time.strftime('%H:%M')} - {maintenance.end_time.strftime('%H:%M')}",
            'severity': 'HIGH' if maintenance.maintenance_date == today else 'MEDIUM',
        })
    
    # Add fully booked hour alerts
    for alert in fully_booked_alerts:
        facility_alerts.append({
            'title': f"Fully Booked: {alert['date']} at {alert['hour']}",
            'message': f"System is fully booked with {alert['booking_count']} simultaneous reservations",
            'details': f"Consider blocking this time for maintenance",
            'severity': 'HIGH' if alert['date'] == 'Today' else 'MEDIUM',
        })
    
    # Get peak hours for this week
    week_reservations = reservation_qs.filter(
        reservation_date__range=(week_start, week_end),
        status=Reservation.Status.APPROVED
    )
    
    peak_hours_data = []
    hour_counts = {}
    for res in week_reservations:
        hour = res.start_time.hour
        hour_counts[hour] = hour_counts.get(hour, 0) + 1
    
    # Get top 6 peak hours
    sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:6]
    peak_hours_data = [
        {'hour': hour, 'count': count}
        for hour, count in sorted(sorted_hours)
    ]
    
    peak_hours_chart_data = peak_hours_data if peak_hours_data else []
    
    # Generate operational recommendations
    facility_recommendations = []
    
    # Check for low occupancy today
    total_possible_hours = max(Facility.objects.filter(status=Facility.Status.AVAILABLE).count(), 1)
    occupancy_today = (todays_reservation_count / (total_possible_hours * 8)) if total_possible_hours > 0 else 0
    
    if occupancy_today < 0.3 and occupancy_today > 0:
        facility_recommendations.append({
            'title': 'Maintenance Window Available',
            'description': f'System occupancy is low today ({occupancy_today * 100:.0f}%). Consider scheduling maintenance.',
            'action': 'Schedule preventive maintenance for assigned facilities',
            'impact': 'Minimize service disruptions',
            'priority': 'medium',
        })
    
    # Check for peak demand
    if sorted_hours and sorted_hours[0][1] > 10:
        peak_hour = sorted_hours[0][0]
        facility_recommendations.append({
            'title': 'Peak Hour Demand',
            'description': f'Highest demand is at {peak_hour:02d}:00 with {sorted_hours[0][1]} bookings. Monitor for capacity issues.',
            'action': 'Review staffing levels during peak hours',
            'impact': 'Improved user experience',
            'priority': 'medium',
        })
    
    # Check for heavily used facilities
    facility_intensity = (
        week_reservations
        .values('facility__name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    if facility_intensity:
        most_used = facility_intensity[0]
        if most_used['count'] > 10:
            facility_recommendations.append({
                'title': f"High Demand: {most_used['facility__name']}",
                'description': f"{most_used['facility__name']} has {most_used['count']} bookings this week. Consider expanding availability.",
                'action': 'Extend facility hours or add duplicate facility',
                'impact': 'Reduce booking conflicts',
                'priority': 'high',
            })
    
    # Check for maintenance backlog
    overdue_maintenance = FacilityMaintenance.objects.filter(
        status=FacilityMaintenance.Status.SCHEDULED,
        maintenance_date__lt=today
    ).count()
    
    if overdue_maintenance > 0:
        facility_recommendations.append({
            'title': f'Overdue Maintenance Tasks',
            'description': f'{overdue_maintenance} maintenance tasks are overdue. Address immediately to prevent equipment failures.',
            'action': 'Contact facilities team to complete overdue maintenance',
            'impact': 'Prevent facility downtime',
            'priority': 'high',
        })
    
    # Sort recommendations by priority
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    facility_recommendations.sort(key=lambda r: priority_order.get(r['priority'], 3))
    
    # Get assigned facilities count
    assigned_facilities_count = Facility.objects.filter(status=Facility.Status.AVAILABLE).count()
    
    # Get pending maintenance this week
    pending_maintenance_count = FacilityMaintenance.objects.filter(
        maintenance_date__range=(today, today + timedelta(days=7)),
        status=FacilityMaintenance.Status.SCHEDULED
    ).count()
    
    # Get pending reservations
    pending_reservation_count = reservation_qs.filter(
        status=Reservation.Status.PENDING
    ).count()
    
    # Build calendar data (similar to home view)
    calendar_month_value = request.GET.get('calendar_month', '')
    try:
        calendar_year, calendar_month = (int(part) for part in calendar_month_value.split('-', 1))
        if (
            len(calendar_month_value) != 7
            or not (1 <= calendar_month <= 12)
            or not (2000 <= calendar_year <= 2100)
        ):
            raise ValueError
    except (TypeError, ValueError):
        calendar_year, calendar_month = today.year, today.month

    calendar_month_start = date(calendar_year, calendar_month, 1)
    calendar_month_end = date(
        calendar_year,
        calendar_month,
        calendar.monthrange(calendar_year, calendar_month)[1],
    )
    calendar_previous_month = (calendar_month_start - timedelta(days=1)).strftime('%Y-%m')
    calendar_next_month = (calendar_month_end + timedelta(days=1)).strftime('%Y-%m')
    
    # Get calendar events
    calendar_events_by_date = {}
    calendar_reservations = reservation_qs.filter(
        reservation_date__range=(calendar_month_start, calendar_month_end),
    ).select_related('facility', 'requested_by').order_by('reservation_date', 'start_time')
    
    for reservation in calendar_reservations:
        requester_name = reservation.requested_by.get_full_name() or reservation.requested_by.username
        calendar_events_by_date.setdefault(reservation.reservation_date, []).append({
            'reservation_id': reservation.pk,
            'facility_name': reservation.facility.name,
            'requester_name': requester_name,
            'start_time': reservation.start_time,
            'end_time': reservation.end_time,
            'label': reservation.get_status_display(),
            'status_class': reservation.status.lower(),
            'kind': 'reservation',
        })
    
    # Include maintenance records
    calendar_maintenance = FacilityMaintenance.objects.filter(
        maintenance_date__range=(calendar_month_start, calendar_month_end),
        status=FacilityMaintenance.Status.SCHEDULED,
    ).select_related('facility').order_by('maintenance_date', 'start_time')
    
    for maintenance in calendar_maintenance:
        calendar_events_by_date.setdefault(maintenance.maintenance_date, []).append({
            'facility_name': maintenance.facility.name,
            'start_time': maintenance.start_time,
            'end_time': maintenance.end_time,
            'label': 'Maintenance',
            'status_class': 'maintenance',
            'kind': 'maintenance',
        })
    
    # Build calendar grid
    dashboard_calendar_weeks = []
    for week in calendar.Calendar(firstweekday=6).monthdatescalendar(calendar_year, calendar_month):
        dashboard_calendar_weeks.append([
            {
                'date': day,
                'in_month': day.month == calendar_month,
                'is_today': day == today,
                'is_past': day < today,
                'events': sorted(
                    calendar_events_by_date.get(day, []),
                    key=lambda event: event['start_time'],
                ),
                'event_count': len(calendar_events_by_date.get(day, [])),
            }
            for day in week
        ])
    
    context = {
        'user': user,
        'dashboard_title': 'Staff Dashboard',
        'dashboard_subtitle': 'Manage facility reservations and monitor operational activity.',
        'dashboard_role': 'staff',
        'assigned_facilities_count': assigned_facilities_count,
        'todays_reservation_count': todays_reservation_count,
        'busiest_facility_today': busiest_facility_today,
        'next_hours_occupancy': next_hours_occupancy,
        'facility_alerts': facility_alerts[:5],  # Limit to top 5 alerts
        'peak_hours_data': peak_hours_data,
        'peak_hours_chart_data': peak_hours_chart_data,
        'facility_recommendations': facility_recommendations[:4],  # Limit to top 4 recommendations
        'pending_maintenance_count': pending_maintenance_count,
        'pending_reservation_count': pending_reservation_count,
        'dashboard_calendar_month': calendar_month_start.strftime('%B %Y'),
        'dashboard_calendar_previous_month': calendar_previous_month,
        'dashboard_calendar_next_month': calendar_next_month,
        'dashboard_calendar_weeks': dashboard_calendar_weeks,
        'dashboard_calendar_weekdays': ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
        'dashboard_calendar_reservation_count': sum(
            len(events) for events in calendar_events_by_date.values()
        ),
    }
    
    return render(request, 'accounts/staff_dashboard.html', context)


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
    from analytics import services
    
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

    pagination = paginate_queryset(accounts, request.GET.get('page'))

    total_facilities = Facility.objects.count()
    facility_data_scope = 'operational'
    if not total_facilities and 'analytics' in connections.databases:
        total_facilities = Facility.objects.using('analytics').filter(is_synthetic=True).count()
        facility_data_scope = 'analytics_sample'

    # Get system-wide analytics
    analytics_data_scope = 'operational'
    analytics_overview = None
    demand_forecast_data = None
    system_calendar_weeks = None
    recommendations = None
    is_using_synthetic_data = False
    data_last_updated = timezone.now()
    
    try:
        # Try to get analytics from operational data first
        operational_count = Reservation.objects.filter(status__in=[Reservation.Status.APPROVED, Reservation.Status.COMPLETED]).count()
        
        # Always use synthetic data since analytics DB fallback to default works
        if True:  # Force synthetic
            # Fall back to synthetic data for demonstration
            analytics_data_scope = 'synthetic'
            is_using_synthetic_data = True
            try:
                kpis = services.get_reservation_kpis()
                facility_demand = services.get_facility_demand()
                peak_periods = services.get_peak_booking_periods()
                
                # Calculate analytics overview
                total_reservations = kpis['total_reservations']
                all_facilities = Facility.objects.using('analytics').filter(is_synthetic=True)
                
                if all_facilities.exists():
                    # Calculate average occupancy across all facilities
                    facility_booking_intensity = services.get_facility_booking_intensity()
                    if facility_booking_intensity:
                        avg_occupancy = sum(f['booking_intensity'] for f in facility_booking_intensity) / len(facility_booking_intensity)
                    else:
                        avg_occupancy = 0
                    
                    # Find peak facility
                    peak_facility = facility_demand[0] if facility_demand else None
                    
                    # Get peak time slot
                    peak_hours = peak_periods.get('by_hour', {})
                    top_hour = max(peak_hours.items(), key=lambda x: x[1])[0] if peak_hours else 0
                    peak_slot = f"{int(top_hour)}:00"
                else:
                    avg_occupancy = 0
                    peak_facility = None
                    peak_slot = "N/A"
                
                analytics_overview = {
                    'total_reservations': total_reservations,
                    'avg_occupancy_percent': round(avg_occupancy * 100, 1),
                    'peak_facility': peak_facility['facility_name'] if peak_facility else 'N/A',
                    'top_booked_time': peak_slot,
                }
                
                # Get demand forecast
                from analytics.services import PredictiveAnalytics
                forecast_result = PredictiveAnalytics.compute_demand_forecast()
                demand_forecast_data = forecast_result
                
            except Exception as e:
                # If analytics fails, continue without analytics
                pass
        else:
            # Use operational data
            try:
                # Calculate from operational data
                total_reservations = Reservation.objects.filter(status__in=[Reservation.Status.APPROVED, Reservation.Status.COMPLETED]).count()
                
                # Get operating facilities
                operating_facilities = Facility.objects.filter(status=Facility.Status.AVAILABLE)
                if operating_facilities.exists():
                    # Calculate average occupancy
                    total_occupancy = 0
                    for facility in operating_facilities:
                        facility_reservations = Reservation.objects.filter(
                            facility=facility,
                            status__in=[Reservation.Status.APPROVED, Reservation.Status.COMPLETED]
                        ).count()
                        if facility.capacity > 0:
                            occupancy = facility_reservations / (facility.capacity * 30)  # normalized by capacity
                            total_occupancy += min(occupancy, 1.0)
                    avg_occupancy = (total_occupancy / operating_facilities.count()) if operating_facilities.count() > 0 else 0
                    
                    # Find peak facility
                    facility_demand_op = (
                        Reservation.objects
                        .filter(status__in=[Reservation.Status.APPROVED, Reservation.Status.COMPLETED])
                        .values('facility__name')
                        .annotate(count=Count('id'))
                        .order_by('-count')
                        .first()
                    )
                    peak_facility_name = facility_demand_op['facility__name'] if facility_demand_op else 'N/A'
                    
                    # Get peak hour
                    from django.db.models import F
                    peak_hour_data = (
                        Reservation.objects
                        .filter(status__in=[Reservation.Status.APPROVED, Reservation.Status.COMPLETED])
                        .values_list('start_time')
                    )
                    if peak_hour_data.exists():
                        from collections import Counter
                        hours = [t[0].hour for t in peak_hour_data if t[0]]
                        peak_hour = Counter(hours).most_common(1)[0][0] if hours else 0
                        peak_slot = f"{int(peak_hour)}:00"
                    else:
                        peak_slot = "N/A"
                else:
                    avg_occupancy = 0
                    peak_facility_name = 'N/A'
                    peak_slot = 'N/A'
                
                analytics_overview = {
                    'total_reservations': total_reservations,
                    'avg_occupancy_percent': round(avg_occupancy * 100, 1),
                    'peak_facility': peak_facility_name,
                    'top_booked_time': peak_slot,
                }
                
                # Get operational forecast if available
                try:
                    from analytics.services import PredictiveAnalytics
                    forecast_result = PredictiveAnalytics.compute_demand_forecast()
                    demand_forecast_data = forecast_result
                except:
                    demand_forecast_data = None
                    
            except Exception:
                analytics_overview = None
        
        # Build system reservations calendar
        today = timezone.localdate()
        calendar_month_value = request.GET.get('calendar_month', '')
        try:
            calendar_year, calendar_month = (int(part) for part in calendar_month_value.split('-', 1))
            if not (1 <= calendar_month <= 12) or not (2000 <= calendar_year <= 2100):
                raise ValueError
        except (TypeError, ValueError):
            calendar_year, calendar_month = today.year, today.month

        calendar_month_start = date(calendar_year, calendar_month, 1)
        calendar_month_end = date(
            calendar_year,
            calendar_month,
            calendar.monthrange(calendar_year, calendar_month)[1],
        )

        # Query all reservations for the month
        if is_using_synthetic_data:
            all_reservations = Reservation.objects.using('analytics').filter(
                is_synthetic=True,
                reservation_date__range=(calendar_month_start, calendar_month_end),
            ).select_related('facility').order_by('reservation_date', 'start_time')
        else:
            all_reservations = Reservation.objects.filter(
                reservation_date__range=(calendar_month_start, calendar_month_end),
            ).select_related('facility').order_by('reservation_date', 'start_time')

        # Build calendar grid
        calendar_events_by_date = {}
        for reservation in all_reservations:
            calendar_events_by_date.setdefault(reservation.reservation_date, []).append({
                'facility_name': reservation.facility.name,
                'start_time': reservation.start_time,
                'end_time': reservation.end_time,
                'status': reservation.status,
                'kind': 'reservation',
            })

        # Include maintenance records
        if is_using_synthetic_data:
            maintenance_records = FacilityMaintenance.objects.using('analytics').filter(
                is_synthetic=True,
                maintenance_date__range=(calendar_month_start, calendar_month_end),
                status=FacilityMaintenance.Status.SCHEDULED,
            ).select_related('facility').order_by('maintenance_date', 'start_time')
        else:
            maintenance_records = FacilityMaintenance.objects.filter(
                maintenance_date__range=(calendar_month_start, calendar_month_end),
                status=FacilityMaintenance.Status.SCHEDULED,
            ).select_related('facility').order_by('maintenance_date', 'start_time')

        for maintenance in maintenance_records:
            calendar_events_by_date.setdefault(maintenance.maintenance_date, []).append({
                'facility_name': maintenance.facility.name,
                'start_time': maintenance.start_time,
                'end_time': maintenance.end_time,
                'label': 'Maintenance',
                'status_class': 'maintenance',
                'kind': 'maintenance',
            })

        system_calendar_weeks = []
        for week in calendar.Calendar(firstweekday=6).monthdatescalendar(calendar_year, calendar_month):
            system_calendar_weeks.append([
                {
                    'date': day,
                    'in_month': day.month == calendar_month,
                    'is_today': day == today,
                    'is_past': day < today,
                    'events': sorted(
                        calendar_events_by_date.get(day, []),
                        key=lambda event: event['start_time'],
                    ),
                    'event_count': len(calendar_events_by_date.get(day, [])),
                }
                for day in week
            ])

        # Generate recommendations based on analytics
        recommendations = []
        if analytics_overview:
            
            # High occupancy recommendation
            if analytics_overview['avg_occupancy_percent'] > 80:
                recommendations.append({
                    'priority': 'high',
                    'title': 'Consider capacity expansion',
                    'description': f"System average occupancy is {analytics_overview['avg_occupancy_percent']}%. Multiple facilities are heavily booked.",
                    'action': 'Review facility expansion options or stagger scheduling',
                    'impact': 'Reduce booking conflicts and improve user experience',
                    'badge': 'High',
                })
            
            # Peak facility recommendation
            if analytics_overview['peak_facility'] != 'N/A':
                recommendations.append({
                    'priority': 'medium',
                    'title': f"Peak demand: {analytics_overview['peak_facility']}",
                    'description': f"'{analytics_overview['peak_facility']}' is the most requested facility. Monitor for bottlenecks.",
                    'action': 'Review staffing or consider adding duplicate facilities',
                    'impact': 'Distribute demand across more facilities',
                    'badge': 'Medium',
                })
            
            # Off-peak maintenance recommendation
            if analytics_overview['top_booked_time'] != 'N/A':
                off_peak_hours = [h for h in range(24) if h < 9 or h > 17]
                if off_peak_hours:
                    rec_hour = off_peak_hours[len(off_peak_hours) // 2]
                    recommendations.append({
                        'priority': 'medium',
                        'title': 'Schedule maintenance during off-peak hours',
                        'description': f"Peak bookings occur at {analytics_overview['top_booked_time']}. Schedule maintenance between 6-9am or after 6pm.",
                        'action': 'Create maintenance schedules for low-occupancy windows',
                        'impact': 'Minimize service disruption',
                        'badge': 'Medium',
                    })
            
            # Equipment maintenance alert (if using synthetic data)
            if is_using_synthetic_data:
                recommendations.append({
                    'priority': 'medium',
                    'title': 'Equipment maintenance checkup',
                    'description': 'Review equipment status for heavily-used facilities (usage >85% of operating hours).',
                    'action': 'Schedule preventive maintenance for computer labs and auditoriums',
                    'impact': 'Prevent equipment failures and downtime',
                    'badge': 'Medium',
                })

    except Exception as e:
        # If anything fails, continue with empty analytics
        pass

    context = {
        'accounts_page': pagination['page_obj'],
        'account_roles': User.Role.choices,
        'filters': {'search': search, 'role': role_filter},
        'filter_query': filter_query_string(request),
        'total_accounts': User.objects.count(),
        'active_accounts': User.objects.filter(is_active=True).count(),
        'admin_accounts': User.objects.filter(role=User.Role.ADMIN).count(),
        'pending_reservations': Reservation.objects.filter(
            status=Reservation.Status.PENDING,
        ).count(),
        'total_facilities': total_facilities,
        'facility_data_scope': facility_data_scope,
        # Analytics data
        'analytics_data_scope': analytics_data_scope,
        'is_using_synthetic_data': is_using_synthetic_data,
        'analytics_overview': analytics_overview,
        'demand_forecast_data': demand_forecast_data,
        'system_calendar_weeks': system_calendar_weeks,
        'system_calendar_month': calendar_month_start.strftime('%B %Y') if system_calendar_weeks else None,
        'system_calendar_weekdays': ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
        'recommendations': recommendations,
        'data_last_updated': data_last_updated,
        **pagination,
    }
    return render(request, 'accounts/admin_dashboard.html', context)
