from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.views.decorators.http import require_GET, require_http_methods
from urllib.parse import urlencode

from accounts.decorators import reservation_reviewer_required, requester_required
from accounts.models import User
from config.list_utils import build_search_q, filter_query_string, paginate_queryset
from facilities.models import Facility
from notifications.models import Notification
from .forms import ReservationAppealForm, ReservationForm
from .models import Reservation


def _get_reviewable_reservation(request, pk):
    """Return a student request while preventing reviewers from reviewing their own record."""
    reviewable = Reservation.objects.select_related(
        'requested_by', 'facility'
    ).exclude(requested_by__user_type=User.UserType.FACULTY)
    reservation = get_object_or_404(
        reviewable,
        pk=pk,
        requested_by__role=User.Role.REQUESTER,
    )
    if reservation.requested_by_id == request.user.pk:
        raise PermissionDenied('You cannot review your own reservation.')
    return reservation


@login_required
@requester_required
def my_reservations_view(request):
    """
    Shows only a student's own reservations.
    Hard-filtered to request.user to prevent IDOR vulnerabilities.

    Why requested_by=request.user and NOT /reservations/user/<user_id>/:
    The server-side session identity (request.user) is authoritative.
    Accepting a user_id from the URL or query string lets any requester
    forge the parameter to read another user's private reservation list.

    Backend-Frontend Contract:
    - Template: 'reservations/my_reservations.html'
    - Context:
        - reservations: current page of Reservation rows for request.user
        - page_obj / paginator / page_range_choices: pagination metadata
    """
    reservations = Reservation.objects.filter(
        requested_by=request.user
    ).select_related('facility')

    status = request.GET.get('status', '')
    reservation_date = request.GET.get('date', '')
    search = request.GET.get('search', '').strip()

    if status in dict(Reservation.Status.choices):
        reservations = reservations.filter(status=status)
    try:
        parsed_date = parse_date(reservation_date) if reservation_date else None
    except ValueError:
        parsed_date = None
    reservation_date = parsed_date.isoformat() if parsed_date else ''
    if parsed_date:
        reservations = reservations.filter(reservation_date=parsed_date)
    if search:
        reservations = reservations.filter(
            build_search_q(
                search,
                ['facility__name', 'facility__location', 'purpose'],
                date_fields=['reservation_date'],
            )
        )

    reservations = reservations.order_by('-reservation_date', '-start_time')

    # Summary counts ignore the text/date search so status chips stay meaningful,
    # but respect the status filter already applied above when aggregating.
    summary_qs = Reservation.objects.filter(requested_by=request.user)
    reservation_summary = summary_qs.aggregate(
        total=Count('pk'),
        pending=Count('pk', filter=Q(status=Reservation.Status.PENDING)),
        approved=Count('pk', filter=Q(status=Reservation.Status.APPROVED)),
        completed=Count('pk', filter=Q(status=Reservation.Status.COMPLETED)),
        rejected=Count('pk', filter=Q(status=Reservation.Status.REJECTED)),
        cancelled=Count('pk', filter=Q(status=Reservation.Status.CANCELLED)),
    )

    pagination = paginate_queryset(reservations, request.GET.get('page'))
    context = {
        'reservations': pagination['page_obj'],
        'reservation_summary': reservation_summary,
        'statuses': Reservation.Status.choices,
        'filters': {
            'status': status,
            'date': reservation_date,
            'search': search,
        },
        'filter_query': filter_query_string(request),
        **pagination,
    }
    return render(request, 'reservations/my_reservations.html', context)


@login_required
@reservation_reviewer_required
def pending_reservations_view(request):
    """
    Lets staff, faculty, and admins review requests across all workflow states.

    select_related('facility', 'requested_by') prevents N+1 queries when
    the template iterates over reservations and accesses related objects.
    select_related issues a SQL JOIN so Django fetches all related data in
    a single query rather than one extra query per row.

    Backend-Frontend Contract:
    - Template: 'reservations/pending_reservations.html'
    - Context:
        - reservations: current page of status/search-filtered requests
        - page_obj / paginator / page_range_choices: pagination metadata
    """
    student_requests = Reservation.objects.filter(
        requested_by__role=User.Role.REQUESTER
    ).exclude(requested_by__user_type=User.UserType.FACULTY)
    reservations = student_requests.select_related('facility', 'requested_by')
    status = request.GET.get('status', Reservation.Status.PENDING)
    show_appeals = request.GET.get('show_appeals', '').lower() == 'true'
    search = request.GET.get('search', '').strip()

    if show_appeals:
        # Show only APPEAL status reservations (appellable requests being appealed)
        reservations = reservations.filter(status=Reservation.Status.APPEAL)
    elif status and status != 'ALL' and status in dict(Reservation.Status.choices):
        reservations = reservations.filter(status=status)
    elif status != 'ALL':
        status = Reservation.Status.PENDING
        reservations = reservations.filter(status=status)

    if search:
        reservations = reservations.filter(
            build_search_q(
                search,
                [
                    'facility__name',
                    'facility__location',
                    'purpose',
                    'requested_by__first_name',
                    'requested_by__last_name',
                    'requested_by__username',
                    'requested_by__department',
                ],
                date_fields=['reservation_date'],
            )
        )

    reservations = reservations.order_by('reservation_date', 'start_time')

    summary = student_requests.aggregate(
        total=Count('pk'),
        pending=Count('pk', filter=Q(status=Reservation.Status.PENDING)),
        approved=Count('pk', filter=Q(status=Reservation.Status.APPROVED)),
        completed=Count('pk', filter=Q(status=Reservation.Status.COMPLETED)),
        rejected=Count('pk', filter=Q(status=Reservation.Status.REJECTED)),
        appeal=Count('pk', filter=Q(status=Reservation.Status.APPEAL)),
        cancelled=Count('pk', filter=Q(status=Reservation.Status.CANCELLED)),
    )

    pagination = paginate_queryset(reservations, request.GET.get('page'))
    context = {
        'reservations': pagination['page_obj'],
        'summary': summary,
        'statuses': Reservation.Status.choices,
        'selected_status': status,
        'show_appeals': show_appeals,
        'filters': {
            'status': status,
            'search': search,
            'show_appeals': show_appeals,
        },
        'filter_query': filter_query_string(request),
        **pagination,
    }
    return render(request, 'reservations/pending_reservations.html', context)


@login_required
@reservation_reviewer_required
def reservation_report_view(request):
    """Display a filterable report of existing reservation records."""
    reservations = Reservation.objects.filter(
        requested_by__role=User.Role.REQUESTER
    ).exclude(requested_by__user_type=User.UserType.FACULTY).select_related(
        'requested_by', 'facility'
    )

    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    status = request.GET.get('status', '')
    facility_id = request.GET.get('facility', '')
    search = request.GET.get('search', '').strip()

    parsed_start_date = parse_date(start_date) if start_date else None
    parsed_end_date = parse_date(end_date) if end_date else None
    if parsed_start_date:
        reservations = reservations.filter(reservation_date__gte=parsed_start_date)
    if parsed_end_date:
        reservations = reservations.filter(reservation_date__lte=parsed_end_date)
    if status in dict(Reservation.Status.choices):
        reservations = reservations.filter(status=status)
    elif status:
        status = ''
    if facility_id:
        try:
            reservations = reservations.filter(facility_id=int(facility_id))
        except ValueError:
            facility_id = ''
    if search:
        reservations = reservations.filter(
            build_search_q(
                search,
                [
                    'facility__name',
                    'purpose',
                    'requested_by__first_name',
                    'requested_by__last_name',
                    'requested_by__username',
                ],
                date_fields=['reservation_date'],
            )
        )

    reservations = reservations.order_by('-reservation_date', '-start_time')

    summary = reservations.aggregate(
        total=Count('pk'),
        pending=Count('pk', filter=Q(status=Reservation.Status.PENDING)),
        approved=Count('pk', filter=Q(status=Reservation.Status.APPROVED)),
        completed=Count('pk', filter=Q(status=Reservation.Status.COMPLETED)),
        rejected=Count('pk', filter=Q(status=Reservation.Status.REJECTED)),
        cancelled=Count('pk', filter=Q(status=Reservation.Status.CANCELLED)),
    )

    pagination = paginate_queryset(reservations, request.GET.get('page'))
    context = {
        'reservations': pagination['page_obj'],
        'facilities': Facility.objects.all().order_by('name'),
        'statuses': Reservation.Status.choices,
        'filters': {
            'start_date': start_date,
            'end_date': end_date,
            'status': status,
            'facility': facility_id,
            'search': search,
        },
        'summary': summary,
        'filter_query': filter_query_string(request),
        **pagination,
    }
    return render(request, 'reservations/reservation_report.html', context)


@require_GET
@login_required
@requester_required
def facility_availability_view(request):
    """Return blocking reservations and maintenance for one facility/date."""
    facility_value = request.GET.get('facility', '')
    target_date = parse_date(request.GET.get('date', ''))
    if not facility_value.isdecimal() or len(facility_value) > 18 or target_date is None:
        return JsonResponse({'error': 'Choose a valid facility and date.'}, status=400)

    try:
        facility = Facility.objects.using('default').get(pk=int(facility_value))
    except Facility.DoesNotExist:
        return JsonResponse({'error': 'The selected facility could not be found.'}, status=404)

    requested_start = parse_time(request.GET.get('start_time', ''))
    requested_end = parse_time(request.GET.get('end_time', ''))
    can_check_requested_time = bool(
        requested_start and requested_end and requested_start < requested_end
    )

    events = []
    reservation_status_labels = dict(Reservation.Status.choices)
    reservations = Reservation.objects.using('default').filter(
        facility_id=facility.pk,
        reservation_date=target_date,
        status__in=Reservation.BLOCKING_STATUSES,
    ).order_by('start_time', 'end_time')
    editing_value = request.GET.get('reservation', '')
    if editing_value:
        if not editing_value.isdecimal() or len(editing_value) > 18:
            return JsonResponse({'error': 'Choose a valid reservation to edit.'}, status=400)
        editing_reservation = get_object_or_404(
            Reservation.objects.using('default'),
            pk=int(editing_value),
            requested_by=request.user,
        )
        if not editing_reservation.can_edit:
            return JsonResponse({'error': 'This reservation can no longer be edited.'}, status=403)
        reservations = reservations.exclude(pk=editing_reservation.pk)
    for reservation in reservations:
        conflicts_requested_time = (
            can_check_requested_time
            and requested_start < reservation.end_time
            and requested_end > reservation.start_time
        )
        events.append({
            'kind': 'reservation',
            'label': f"{reservation_status_labels[reservation.status]} reservation",
            'start_time': reservation.start_time.strftime('%H:%M'),
            'end_time': reservation.end_time.strftime('%H:%M'),
            'conflicts_requested_time': conflicts_requested_time,
        })

    from facilities.models import FacilityMaintenance

    maintenance_records = FacilityMaintenance.objects.using('default').filter(
        facility_id=facility.pk,
        maintenance_date=target_date,
        status=FacilityMaintenance.Status.SCHEDULED,
    ).order_by('start_time', 'end_time')
    for maintenance in maintenance_records:
        conflicts_requested_time = (
            can_check_requested_time
            and requested_start < maintenance.end_time
            and requested_end > maintenance.start_time
        )
        events.append({
            'kind': 'maintenance',
            'label': 'Scheduled maintenance',
            'start_time': maintenance.start_time.strftime('%H:%M'),
            'end_time': maintenance.end_time.strftime('%H:%M'),
            'conflicts_requested_time': conflicts_requested_time,
        })

    events.sort(key=lambda event: (event['start_time'], event['end_time']))
    calendar_url = reverse('facilities:facility_detail', args=[facility.pk])
    calendar_url += '?' + urlencode({
        'month': target_date.strftime('%Y-%m'),
        'date': target_date.isoformat(),
    })
    calendar_url += f'#facility-calendar-day-{target_date.isoformat()}'

    selected_time_conflict = None
    if can_check_requested_time:
        selected_time_conflict = any(
            event['conflicts_requested_time'] for event in events
        )

    return JsonResponse({
        'facility_name': facility.name,
        'facility_available': facility.status == Facility.Status.AVAILABLE,
        'facility_status': facility.get_status_display(),
        'date': target_date.isoformat(),
        'events': events,
        'selected_time_conflict': selected_time_conflict,
        'calendar_url': calendar_url,
    })


@login_required
@requester_required
def create_reservation_view(request):
    """
    Allows an authenticated REQUESTER to submit a new reservation request.

    GET:  Display blank ReservationForm.
    POST: Validate and save the reservation.

    Security:
    - requested_by is ALWAYS assigned from request.user (server-side session).
    - It is NEVER read from POST data; this prevents ownership forgery.
    - form.save(commit=False) returns an unsaved instance so we can inject
      requested_by before the database write.
    - All business rule validation (time range, past date, facility status,
      conflict detection) runs inside Reservation.clean() via model.save().

    POST/Redirect/GET:
    - On success, redirect to my_reservations to prevent duplicate submission
      on browser refresh.

    Backend-Frontend Contract:
    - Template: 'reservations/reservation_form.html'
    - Context:
        - form: ReservationForm (bound on POST with errors, unbound on GET)
    """
    bookable_facilities = Facility.objects.using('default').filter(
        status=Facility.Status.AVAILABLE,
    )
    has_bookable_facilities = bookable_facilities.exists()

    if request.method == 'POST':
        form = ReservationForm(
            request.POST,
            facility_queryset=bookable_facilities,
        )
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.requested_by = request.user
            try:
                reservation.save()
                messages.success(
                    request,
                    'Your reservation request has been submitted and is pending review.'
                )
                return redirect('reservations:my_reservations')
            except ValidationError as exc:
                # model.save() calls full_clean(); surface any remaining errors
                # back onto the form so the template can display them.
                form.add_error(None, exc)
    else:
        initial = {}
        selected_facility = request.GET.get('facility', '')
        if selected_facility.isdecimal() and len(selected_facility) <= 18:
            initial['facility'] = int(selected_facility)
        try:
            selected_date = parse_date(request.GET.get('date', ''))
        except ValueError:
            selected_date = None
        if selected_date and 2000 <= selected_date.year <= 2100 and selected_date >= timezone.localdate():
            initial['reservation_date'] = selected_date.isoformat()
        form = ReservationForm(
            initial=initial,
            facility_queryset=bookable_facilities,
        )

    return render(request, 'reservations/reservation_form.html', {
        'form': form,
        'has_bookable_facilities': has_bookable_facilities,
    })


@login_required
@requester_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def edit_reservation_view(request, pk):
    """Update an owner's upcoming booking and send changes back for review."""
    reservations = Reservation.objects.using('default').select_related('facility')
    if request.method == 'POST':
        reservations = reservations.select_for_update()
    reservation = get_object_or_404(reservations, pk=pk)
    if reservation.requested_by_id != request.user.pk:
        raise PermissionDenied('You can only edit your own reservations.')
    if not reservation.can_edit:
        messages.error(request, 'Only pending or approved reservations that have not started can be edited.')
        return redirect('reservations:reservation_detail', pk=pk)

    was_approved = reservation.is_approved
    current_facility_unavailable = reservation.facility.status != Facility.Status.AVAILABLE
    bookable_facilities = Facility.objects.using('default').filter(status=Facility.Status.AVAILABLE)
    has_bookable_facilities = bookable_facilities.exists()
    initial = {
        'reservation_date': reservation.reservation_date.isoformat(),
        'start_time': reservation.start_time.strftime('%H:%M'),
        'end_time': reservation.end_time.strftime('%H:%M'),
    }
    form = ReservationForm(
        request.POST if request.method == 'POST' else None,
        instance=reservation,
        initial=initial,
        facility_queryset=bookable_facilities,
    )
    if request.method == 'POST' and form.is_valid():
        if not form.has_changed():
            messages.info(request, 'No changes were made to your reservation.')
            return redirect('reservations:reservation_detail', pk=pk)
        updated = form.save(commit=False)
        updated.status = Reservation.Status.PENDING
        updated.reviewed_by = None
        updated.reviewed_at = None
        updated.rejection_reason = ''
        updated.completed_by = None
        updated.completed_at = None
        try:
            updated.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Your reservation has been updated and is pending review.')
            return redirect('reservations:reservation_detail', pk=pk)

    return render(request, 'reservations/reservation_form.html', {
        'form': form,
        'reservation': reservation,
        'is_edit': True,
        'was_approved': was_approved,
        'current_facility_unavailable': current_facility_unavailable,
        'has_bookable_facilities': has_bookable_facilities,
    })


@login_required
@requester_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def appeal_reservation_view(request, pk):
    """Let an owner correct and appeal a declined request up to three times."""
    reservations = Reservation.objects.using('default').select_related('facility')
    if request.method == 'POST':
        reservations = reservations.select_for_update()
    reservation = get_object_or_404(reservations, pk=pk)
    if reservation.requested_by_id != request.user.pk:
        raise PermissionDenied('You can only appeal your own reservations.')
    if not reservation.can_appeal:
        message = (
            'You have used all three appeals for this reservation.'
            if reservation.is_rejected else 'Only declined reservations can be appealed.'
        )
        messages.error(request, message)
        return redirect('reservations:reservation_detail', pk=pk)

    appeal_number = reservation.appeal_count + 1
    previous_decline_reason = reservation.rejection_reason
    current_facility_unavailable = reservation.facility.status != Facility.Status.AVAILABLE
    bookable_facilities = Facility.objects.using('default').filter(status=Facility.Status.AVAILABLE)
    form = ReservationAppealForm(
        request.POST if request.method == 'POST' else None,
        instance=reservation,
        initial={
            'reservation_date': reservation.reservation_date.isoformat(),
            'start_time': reservation.start_time.strftime('%H:%M'),
            'end_time': reservation.end_time.strftime('%H:%M'),
        },
        facility_queryset=bookable_facilities,
    )
    if request.method == 'POST' and form.is_valid():
        try:
            reservation.appeal(form.cleaned_data['appeal_reason'])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            # Create notification for staff/admins when appeal submitted
            from notifications.models import Notification
            Notification.objects.create(
                recipient_id=None,  # Broadcast to all staff
                reservation=reservation,
                message=(
                    f'Appeal #{reservation.appeal_count} submitted for Reservation #{reservation.pk} '
                    f'by {reservation.requested_by.get_full_name() or reservation.requested_by.username}. '
                    f'Facility: {reservation.facility.name}. Date: {reservation.reservation_date}.'
                ),
            )
            messages.success(
                request,
                f'Appeal {reservation.appeal_count} of {Reservation.MAX_APPEALS} submitted. '
                'Your reservation is pending review.',
            )
            return redirect('reservations:reservation_detail', pk=pk)

    return render(request, 'reservations/reservation_form.html', {
        'form': form,
        'reservation': reservation,
        'is_appeal': True,
        'appeal_number': appeal_number,
        'previous_decline_reason': previous_decline_reason,
        'current_facility_unavailable': current_facility_unavailable,
        'has_bookable_facilities': bookable_facilities.exists(),
    })


@login_required
def reservation_detail_view(request, pk):
    """
    Displays the full details of a single reservation.

    Object-level authorization:
    - STUDENT REQUESTER: may only view their OWN reservations.
      Attempting to access another user's reservation returns 403,
      not 404, because 404 would obscure a security boundary with a
      "not found" lie. The resource exists; the requester simply has
      no right to it.
    - STAFF, FACULTY, and ADMIN: may view any reservation to review the workflow.

    Backend-Frontend Contract:
    - Template: 'reservations/reservation_detail.html'
    - Context:
        - reservation: single Reservation instance with facility and
                       requested_by pre-fetched
    """
    reservation = get_object_or_404(
        Reservation.objects.select_related(
            'facility', 'requested_by', 'reviewed_by', 'completed_by'
        ),
        pk=pk,
    )

    user = request.user
    if user.is_reservation_reviewer:
        if reservation.requested_by_id == user.pk or not reservation.requested_by.is_student_role:
            raise PermissionDenied('Reviewers can only access student reservation requests.')
    elif user.is_student_role:
        if reservation.requested_by != user:
            raise PermissionDenied(
                'You do not have permission to view this reservation.'
            )
    else:
        raise PermissionDenied('You do not have permission to view this reservation.')

    scheduled_end = timezone.make_aware(
        datetime.combine(reservation.reservation_date, reservation.end_time),
        timezone.get_current_timezone(),
    )
    return render(request, 'reservations/reservation_detail.html', {
        'reservation': reservation,
        'appeals': reservation.appeals.all(),
        'can_complete': (
            reservation.status == Reservation.Status.APPROVED
            and timezone.now() >= scheduled_end
        ),
    })


@login_required
@requester_required
def cancel_reservation_view(request, pk):
    """
    Allows a REQUESTER to cancel their own PENDING or APPROVED reservation.

    POST-only: GET requests return 405 Method Not Allowed.
    GET must not cancel because browsers pre-fetch links and search
    engine crawlers follow GET URLs, which would silently cancel reservations.

    Object-level ownership:
    - Ownership is verified from request.user (session), NEVER from POST data.
    - A REQUESTER cannot cancel another user's reservation.

    Lifecycle:
    - Delegates to Reservation.cancel(), which owns the transition rules:
      DECLINED, CANCELLED, and COMPLETED reservations cannot be cancelled again.
    - The view does not duplicate or override that logic.

    Backend-Frontend Contract:
    - No dedicated template; POSTs from reservation_detail or my_reservations.
    - On success: redirect to my_reservations with success message.
    - On invalid transition: redirect to detail with error message.
    """
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])

    reservation = get_object_or_404(Reservation, pk=pk)

    # Object-level authorization — server enforces ownership, not hidden HTML
    if reservation.requested_by != request.user:
        raise PermissionDenied('You can only cancel your own reservations.')

    try:
        reservation.cancel()
        messages.success(request, 'Your reservation has been cancelled.')
    except ValidationError as exc:
        messages.error(request, exc.message)

    return redirect('reservations:my_reservations')


@login_required
@reservation_reviewer_required
def approve_reservation_view(request, pk):
    """
    Allows STAFF, FACULTY, or ADMIN to approve a PENDING reservation.

    POST-only: GET requests return 405 Method Not Allowed.

    Lifecycle:
    - Delegates entirely to Reservation.approve(reviewer).
    - approve() validates status==PENDING, sets APPROVED, records
      reviewed_by and reviewed_at, then calls save().
    - save() calls full_clean(), which re-runs conflict detection.
      If approving this reservation now conflicts with another APPROVED
      reservation (race condition: two pending requests for the same
      slot), the ValidationError surfaces here and no transition occurs.

    Backend-Frontend Contract:
    - No dedicated template; POSTs from pending_reservations or detail.
    - On success: redirect to pending queue with success message.
    - On invalid transition: redirect to detail with error message.
    """
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])

    reservation = _get_reviewable_reservation(request, pk)

    try:
        with transaction.atomic():
            # Both the reservation status update and the notification
            # creation are wrapped in a single database transaction.
            # If notification creation raises a database exception,
            # the entire transaction rolls back and the reservation
            # remains PENDING — no partial writes survive.
            reservation.approve(reviewer=request.user)
            Notification.objects.create(
                recipient=reservation.requested_by,
                reservation=reservation,
                message=(
                    f'Your reservation for {reservation.facility.name} on '
                    f'{reservation.reservation_date} has been approved.'
                ),
            )
        messages.success(
            request,
            f'Reservation #{reservation.pk} has been approved.'
        )
        return redirect('reservations:pending_reservations')
    except ValidationError as exc:
        messages.error(request, exc.message)
        return redirect('reservations:reservation_detail', pk=pk)


@login_required
@reservation_reviewer_required
def reject_reservation_view(request, pk):
    """
    Allows STAFF, FACULTY, or ADMIN to decline a PENDING reservation with a mandatory reason.

    POST-only: GET requests return 405 Method Not Allowed.

    The rejection reason is read from POST data: request.POST.get('reason').
    The Frontend Lead must include a <textarea name="reason"> in the form.

    Lifecycle:
    - Delegates to Reservation.reject(reviewer, reason).
    - reject() validates status==PENDING, validates reason is non-empty,
      sets REJECTED, stores all review data, then calls save().
    - The view checks for an empty reason before calling the model method
      to provide a clear user-facing message rather than a raw ValidationError.

    Backend-Frontend Contract:
    - No dedicated template; POSTs from pending_reservations or detail.
    - On success: redirect to pending queue with success message.
    - On missing reason or invalid transition: redirect to detail with error.
    """
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])

    reservation = _get_reviewable_reservation(request, pk)
    reason = request.POST.get('reason', '').strip()

    if not reason:
        messages.error(request, 'A decline reason is required.')
        return redirect('reservations:reservation_detail', pk=pk)

    try:
        with transaction.atomic():
            # Both the reservation status update and the notification
            # creation are wrapped in a single database transaction.
            # If notification creation raises a database exception,
            # the entire transaction rolls back and the reservation
            # remains PENDING — no partial writes survive.
            reservation.reject(reviewer=request.user, reason=reason)
            Notification.objects.create(
                recipient=reservation.requested_by,
                reservation=reservation,
                message=(
                    f'Your reservation for {reservation.facility.name} on '
                    f'{reservation.reservation_date} was declined. '
                    f'Reason: {reservation.rejection_reason}'
                ),
            )
        messages.success(
            request,
            f'Reservation #{reservation.pk} has been declined.'
        )
        return redirect('reservations:pending_reservations')
    except ValidationError as exc:
        messages.error(request, exc.message)
        return redirect('reservations:reservation_detail', pk=pk)


@login_required
@reservation_reviewer_required
def complete_reservation_view(request, pk):
    """Mark an approved reservation completed after its scheduled end time."""
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])

    reservation = _get_reviewable_reservation(request, pk)
    try:
        with transaction.atomic():
            reservation.complete(reviewer=request.user)
            Notification.objects.create(
                recipient=reservation.requested_by,
                reservation=reservation,
                message=(
                    f'Your reservation for {reservation.facility.name} on '
                    f'{reservation.reservation_date} has been marked completed.'
                ),
            )
        messages.success(request, f'Reservation #{reservation.pk} has been completed.')
    except ValidationError as exc:
        messages.error(request, exc.message)

    return redirect('reservations:reservation_detail', pk=pk)


@login_required
@require_GET
def get_calendar_widget(request):
    """
    AJAX endpoint to dynamically load the calendar widget for a facility.
    Returns the rendered HTML of facility_calendar_widget.html.
    
    Query params:
    - facility_id: ID of the facility (required)
    """
    facility_id = request.GET.get('facility_id')
    if not facility_id:
        return JsonResponse({'error': 'facility_id required'}, status=400)
    
    try:
        facility = Facility.objects.get(id=facility_id)
    except Facility.DoesNotExist:
        return JsonResponse({'error': 'Facility not found'}, status=404)
    
    # Render the calendar widget component
    context = {'facility_id': facility_id}
    return render(request, 'components/facility_calendar_widget.html', context, content_type='text/html')
