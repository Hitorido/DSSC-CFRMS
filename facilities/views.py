import calendar
from datetime import date, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import connections, transaction
from django.db.models import Q
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from accounts.decorators import admin_required, staff_or_admin_required
from accounts.models import User
from config.list_utils import build_search_q, filter_query_string, paginate_queryset
from .forms import FacilityCreateForm, FacilityMaintenanceForm
from .models import Facility, FacilityMaintenance, FacilityType


@login_required
def facility_list_view(request):
    """
    Authenticated list of campus facilities.

    Backend-Frontend Contract:
    - Template: 'facilities/facility_list.html'
    - Context:
        - facilities: QuerySet of all Facility records, ordered by name,
                      with facility_type pre-fetched via select_related
    """
    facilities = Facility.objects.select_related('facility_type').all()
    facility_data_scope = 'operational'
    if not facilities.exists() and 'analytics' in connections.databases:
        sample_facilities = Facility.objects.using('analytics').filter(is_synthetic=True)
        if sample_facilities.exists():
            facilities = sample_facilities.select_related('facility_type')
            facility_data_scope = 'analytics_sample'

    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '')
    facility_type = request.GET.get('facility_type', '')
    try:
        selected_date = parse_date(request.GET.get('date', ''))
    except ValueError:
        selected_date = None
    if selected_date and not 2000 <= selected_date.year <= 2100:
        selected_date = None
    facility_calendar_suffix = ''
    if selected_date:
        facility_calendar_suffix = '?' + urlencode({
            'month': selected_date.strftime('%Y-%m'),
            'date': selected_date.isoformat(),
        }) + f'#facility-calendar-day-{selected_date.isoformat()}'

    if search:
        facilities = facilities.filter(
            Q(name__icontains=search)
            | Q(location__icontains=search)
            | Q(facility_type__name__icontains=search)
        )
    if status in dict(Facility.Status.choices):
        facilities = facilities.filter(status=status)
    if facility_type:
        try:
            facilities = facilities.filter(facility_type_id=int(facility_type))
        except (TypeError, ValueError):
            facilities = facilities.none()

    facilities = facilities.order_by('name')
    facility_types = FacilityType.objects.all()
    if facility_data_scope == 'analytics_sample':
        facility_types = FacilityType.objects.using('analytics').filter(is_synthetic=True)

    pagination = paginate_queryset(facilities, request.GET.get('page'))
    context = {
        'facilities': pagination['page_obj'],
        'facility_statuses': Facility.Status.choices,
        'facility_types': facility_types,
        'facility_data_scope': facility_data_scope,
        'selected_date': selected_date,
        'facility_calendar_suffix': facility_calendar_suffix,
        'filters': {
            'search': search,
            'status': status,
            'facility_type': facility_type,
        },
        'filter_query': filter_query_string(request),
        **pagination,
    }
    return render(request, 'facilities/facility_list.html', context)


@login_required
def facility_detail_view(request, pk):
    """Show facility information and a month-by-month reservation calendar."""
    data_alias = 'default'
    facility_data_scope = 'operational'
    try:
        facility = Facility.objects.using(data_alias).select_related(
            'facility_type',
        ).get(pk=pk)
    except Facility.DoesNotExist:
        # Keep detail links usable when the list is showing analytics-only
        # sample facilities because the operational database has no catalog.
        if 'analytics' not in connections.databases:
            raise Http404('Facility not found.')
        try:
            facility = Facility.objects.using('analytics').filter(
                is_synthetic=True,
            ).select_related('facility_type').get(pk=pk)
        except Facility.DoesNotExist:
            raise Http404('Facility not found.')
        data_alias = 'analytics'
        facility_data_scope = 'analytics_sample'

    today = timezone.localdate()
    try:
        selected_date = parse_date(request.GET.get('date', ''))
    except ValueError:
        selected_date = None
    if selected_date and not 2000 <= selected_date.year <= 2100:
        selected_date = None
    month_value = request.GET.get('month', '')
    try:
        year, month = (int(part) for part in month_value.split('-', 1))
        if len(month_value) != 7 or not (1 <= month <= 12) or not (2000 <= year <= 2100):
            raise ValueError
    except (TypeError, ValueError):
        calendar_date = selected_date or today
        year, month = calendar_date.year, calendar_date.month

    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    if selected_date and (selected_date.year != year or selected_date.month != month):
        selected_date = None
    previous_month = (month_start - timedelta(days=1)).strftime('%Y-%m')
    next_month = (month_end + timedelta(days=1)).strftime('%Y-%m')

    # Import locally to avoid coupling facilities.models to reservations.models.
    from reservations.models import Reservation

    reservations = list(
        Reservation.objects.using(data_alias)
        .filter(
            facility_id=facility.pk,
            reservation_date__range=(month_start, month_end),
        )
        .exclude(status__in=[Reservation.Status.REJECTED, Reservation.Status.CANCELLED])
        .order_by('reservation_date', 'start_time')
        .values(
            'pk', 'requested_by_id', 'requested_by__role', 'requested_by__user_type',
            'reservation_date', 'start_time', 'end_time', 'status',
        )
    )
    maintenance_records = list(
        FacilityMaintenance.objects.using(data_alias)
        .filter(
            facility_id=facility.pk,
            maintenance_date__range=(month_start, month_end),
            status=FacilityMaintenance.Status.SCHEDULED,
        )
        .order_by('maintenance_date', 'start_time')
        .values('maintenance_date', 'start_time', 'end_time')
    )

    events_by_date = {}
    status_labels = dict(Reservation.Status.choices)
    for reservation in reservations:
        is_blocking = reservation['status'] in Reservation.BLOCKING_STATUSES
        requester_is_student = (
            reservation['requested_by__role'] == User.Role.REQUESTER
            and reservation['requested_by__user_type'] != User.UserType.FACULTY
        )
        can_view_details = (
            facility_data_scope != 'analytics_sample'
            and (
                (
                    request.user.is_reservation_reviewer
                    and reservation['requested_by_id'] != request.user.pk
                    and requester_is_student
                )
                or (
                    request.user.is_student_role
                    and reservation['requested_by_id'] == request.user.pk
                )
            )
        )
        events_by_date.setdefault(reservation['reservation_date'], []).append({
            'reservation_id': reservation['pk'],
            'kind': 'reservation',
            'label': status_labels.get(reservation['status'], reservation['status'].title()),
            'status_class': reservation['status'].lower(),
            'start_time': reservation['start_time'],
            'end_time': reservation['end_time'],
            'blocks_availability': is_blocking,
            'can_view_details': can_view_details,
        })
    for maintenance in maintenance_records:
        events_by_date.setdefault(maintenance['maintenance_date'], []).append({
            'kind': 'maintenance',
            'label': 'Maintenance',
            'status_class': 'maintenance',
            'start_time': maintenance['start_time'],
            'end_time': maintenance['end_time'],
            'blocks_availability': True,
        })

    can_request_reservation = (
        request.user.is_student_role
        and facility_data_scope == 'operational'
        and facility.status == Facility.Status.AVAILABLE
    )
    reservation_form_url = reverse('reservations:create_reservation')
    request_facility_params = {'facility': facility.pk}
    if selected_date and selected_date >= today:
        request_facility_params['date'] = selected_date.isoformat()
    request_facility_url = reservation_form_url + '?' + urlencode(request_facility_params)

    calendar_weeks = []
    for week in calendar.Calendar(firstweekday=6).monthdatescalendar(year, month):
        calendar_week = []
        for day in week:
            day_events = sorted(
                events_by_date.get(day, []),
                key=lambda event: event['start_time'],
            )
            if day.month != month:
                availability_label = ''
            elif day < today:
                availability_label = 'Past date'
            elif facility.status != Facility.Status.AVAILABLE:
                availability_label = facility.get_status_display()
            elif any(event['blocks_availability'] for event in day_events):
                availability_label = 'Limited'
            else:
                availability_label = 'No conflicts'
            booking_url = ''
            if can_request_reservation and day.month == month and day >= today and not day_events:
                booking_url = reservation_form_url + '?' + urlencode({
                    'facility': facility.pk,
                    'date': day.isoformat(),
                })
            calendar_week.append({
                'date': day,
                'in_month': day.month == month,
                'is_today': day == today,
                'is_past': day < today,
                'is_selected_date': day == selected_date,
                'events': day_events,
                'availability_label': availability_label,
                'booking_url': booking_url,
            })
        calendar_weeks.append(calendar_week)

    now = timezone.localtime()
    local_time = now.time().replace(tzinfo=None)
    under_scheduled_maintenance_now = FacilityMaintenance.objects.using(data_alias).filter(
        facility_id=facility.pk,
        maintenance_date=today,
        status=FacilityMaintenance.Status.SCHEDULED,
        start_time__lte=local_time,
        end_time__gt=local_time,
    ).exists()

    return render(request, 'facilities/facility_detail.html', {
        'facility': facility,
        'facility_data_scope': facility_data_scope,
        'selected_date': selected_date,
        'can_request_reservation': can_request_reservation,
        'request_facility_url': request_facility_url,
        'month_label': month_start.strftime('%B %Y'),
        'previous_month': previous_month,
        'next_month': next_month,
        'weekdays': ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
        'calendar_weeks': calendar_weeks,
        'reservation_count': len(reservations),
        'maintenance_count': len(maintenance_records),
        'under_scheduled_maintenance_now': under_scheduled_maintenance_now,
    })


@admin_required
@transaction.atomic
def facility_create_view(request):
    form = FacilityCreateForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        facility = form.save()
        messages.success(request, f'{facility.name} has been added to campus facilities.')
        return redirect('facilities:facility_list')

    return render(request, 'facilities/facility_form.html', {
        'form': form,
        'facility_types': form.facility_types,
    })


# ---------------------------------------------------------------------------
# Maintenance Management — STAFF / ADMIN only
# ---------------------------------------------------------------------------

@login_required
@staff_or_admin_required
def maintenance_list_view(request):
    """
    List all maintenance records, ordered by date descending.

    Backend-Frontend Contract:
    - Template: 'facilities/maintenance_list.html'
    - Context:
        - maintenance_records: current page of FacilityMaintenance rows
        - page_obj / paginator / page_range_choices: pagination metadata
    """
    maintenance_records = (
        FacilityMaintenance.objects
        .select_related('facility', 'created_by')
        .order_by('-maintenance_date', '-start_time')
    )

    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '')
    if search:
        maintenance_records = maintenance_records.filter(
            build_search_q(
                search,
                ['facility__name', 'facility__location', 'title'],
                date_fields=['maintenance_date'],
            )
        )
    if status in dict(FacilityMaintenance.Status.choices):
        maintenance_records = maintenance_records.filter(status=status)

    pagination = paginate_queryset(maintenance_records, request.GET.get('page'))
    return render(request, 'facilities/maintenance_list.html', {
        'maintenance_records': pagination['page_obj'],
        'maintenance_statuses': FacilityMaintenance.Status.choices,
        'filters': {
            'search': search,
            'status': status,
        },
        'filter_query': filter_query_string(request),
        **pagination,
    })


@login_required
@staff_or_admin_required
def maintenance_create_view(request):
    """
    Allow STAFF / ADMIN to schedule a new facility maintenance window.

    GET:  Display blank FacilityMaintenanceForm.
    POST: Validate and save the maintenance record.

    Security:
    - created_by is ALWAYS assigned from request.user (server-side session).
    - status is NOT a form field; it defaults to SCHEDULED via the model.
    - form.save(commit=False) lets us inject created_by before the DB write.
    - All business-rule validation (time range, overlap with reservations,
      overlap with other maintenance) runs in FacilityMaintenance.clean()
      via model.save(). ValidationError is surfaced to the form.

    Backend-Frontend Contract:
    - Template: 'facilities/maintenance_form.html'
    - Context:
        - form: FacilityMaintenanceForm
    """
    if request.method == 'POST':
        form = FacilityMaintenanceForm(request.POST)
        if form.is_valid():
            maintenance = form.save(commit=False)
            maintenance.created_by = request.user
            try:
                maintenance.save()
                messages.success(
                    request,
                    f'Maintenance scheduled for {maintenance.facility.name} '
                    f'on {maintenance.maintenance_date}.'
                )
                return redirect('facilities:maintenance_detail', pk=maintenance.pk)
            except ValidationError as exc:
                form.add_error(None, exc)
    else:
        form = FacilityMaintenanceForm()

    return render(request, 'facilities/maintenance_form.html', {'form': form})


@login_required
@staff_or_admin_required
def maintenance_detail_view(request, pk):
    """
    Display full details of a single maintenance record.

    All STAFF and ADMIN users may view any maintenance record.

    Backend-Frontend Contract:
    - Template: 'facilities/maintenance_detail.html'
    - Context:
        - maintenance: FacilityMaintenance instance with facility and
                       created_by pre-fetched
    """
    maintenance = get_object_or_404(
        FacilityMaintenance.objects.select_related('facility', 'created_by'),
        pk=pk,
    )
    return render(request, 'facilities/maintenance_detail.html', {
        'maintenance': maintenance,
    })


@login_required
@staff_or_admin_required
def maintenance_complete_view(request, pk):
    """
    Mark a SCHEDULED maintenance window as COMPLETED.

    POST-only: GET returns 405. State-changing actions must not be triggered
    by link pre-fetching or GET navigation.

    Delegates entirely to FacilityMaintenance.complete(), which owns the
    lifecycle rule (only SCHEDULED → COMPLETED is valid). The view does not
    set status directly.

    Backend-Frontend Contract:
    - No dedicated template; POSTs from maintenance_detail.
    - On success: redirect to maintenance_detail with success message.
    - On invalid transition: redirect to maintenance_detail with error message.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    maintenance = get_object_or_404(FacilityMaintenance, pk=pk)

    try:
        maintenance.complete()
        messages.success(
            request,
            f'Maintenance #{maintenance.pk} marked as completed.'
        )
    except ValidationError as exc:
        messages.error(request, exc.message)

    return redirect('facilities:maintenance_detail', pk=pk)


@login_required
@staff_or_admin_required
def maintenance_cancel_view(request, pk):
    """
    Cancel a SCHEDULED maintenance window.

    POST-only: GET returns 405.

    Delegates entirely to FacilityMaintenance.cancel(), which owns the
    lifecycle rule (only SCHEDULED → CANCELLED is valid).

    Backend-Frontend Contract:
    - No dedicated template; POSTs from maintenance_detail.
    - On success: redirect to maintenance_list with success message.
    - On invalid transition: redirect to maintenance_detail with error message.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    maintenance = get_object_or_404(FacilityMaintenance, pk=pk)

    try:
        maintenance.cancel()
        messages.success(
            request,
            f'Maintenance #{maintenance.pk} has been cancelled.'
        )
        return redirect('facilities:maintenance_list')
    except ValidationError as exc:
        messages.error(request, exc.message)
        return redirect('facilities:maintenance_detail', pk=pk)
