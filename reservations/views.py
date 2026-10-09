from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from accounts.decorators import requester_required, staff_or_admin_required
from facilities.models import Facility
from notifications.models import Notification
from .forms import ReservationForm
from .models import Reservation


@login_required
@requester_required
def my_reservations_view(request):
    """
    Shows only the reservations submitted by the currently authenticated user.
    Hard-filtered to request.user to prevent IDOR vulnerabilities.

    Why requested_by=request.user and NOT /reservations/user/<user_id>/:
    The server-side session identity (request.user) is authoritative.
    Accepting a user_id from the URL or query string lets any requester
    forge the parameter to read another user's private reservation list.

    Backend-Frontend Contract:
    - Template: 'reservations/my_reservations.html'
    - Context:
        - reservations: QuerySet[Reservation] filtered to request.user,
                        ordered by -reservation_date, -start_time,
                        with facility pre-fetched via select_related
    """
    reservations = Reservation.objects.filter(
        requested_by=request.user
    ).select_related('facility')

    status = request.GET.get('status', '')
    reservation_date = request.GET.get('date', '')
    if status in dict(Reservation.Status.choices):
        reservations = reservations.filter(status=status)
    parsed_date = parse_date(reservation_date) if reservation_date else None
    if parsed_date:
        reservations = reservations.filter(reservation_date=parsed_date)

    reservations = reservations.order_by('-reservation_date', '-start_time')

    context = {
        'reservations': reservations,
        'statuses': Reservation.Status.choices,
        'filters': {
            'status': status,
            'date': reservation_date,
        },
    }
    return render(request, 'reservations/my_reservations.html', context)


@login_required
@staff_or_admin_required
def pending_reservations_view(request):
    """
    Shows pending reservation requests awaiting review by Staff or Admin.

    select_related('facility', 'requested_by') prevents N+1 queries when
    the template iterates over reservations and accesses related objects.
    select_related issues a SQL JOIN so Django fetches all related data in
    a single query rather than one extra query per row.

    Backend-Frontend Contract:
    - Template: 'reservations/pending_reservations.html'
    - Context:
        - reservations: QuerySet[Reservation] where status==PENDING,
                        ordered by reservation_date, start_time (oldest first),
                        with facility and requested_by pre-fetched
    """
    reservations = Reservation.objects.filter(
        status=Reservation.Status.PENDING
    ).select_related('facility', 'requested_by').order_by('reservation_date', 'start_time')

    context = {
        'reservations': reservations,
    }
    return render(request, 'reservations/pending_reservations.html', context)


@login_required
@staff_or_admin_required
def reservation_report_view(request):
    """Display a filterable report of existing reservation records."""
    reservations = Reservation.objects.select_related(
        'requested_by', 'facility'
    )

    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    status = request.GET.get('status', '')
    facility_id = request.GET.get('facility', '')

    parsed_start_date = parse_date(start_date) if start_date else None
    parsed_end_date = parse_date(end_date) if end_date else None
    if parsed_start_date:
        reservations = reservations.filter(reservation_date__gte=parsed_start_date)
    if parsed_end_date:
        reservations = reservations.filter(reservation_date__lte=parsed_end_date)
    if status:
        reservations = reservations.filter(status=status)
    if facility_id:
        try:
            reservations = reservations.filter(facility_id=int(facility_id))
        except ValueError:
            pass

    summary = reservations.aggregate(
        total=Count('pk'),
        pending=Count('pk', filter=Q(status=Reservation.Status.PENDING)),
        approved=Count('pk', filter=Q(status=Reservation.Status.APPROVED)),
        rejected=Count('pk', filter=Q(status=Reservation.Status.REJECTED)),
        cancelled=Count('pk', filter=Q(status=Reservation.Status.CANCELLED)),
    )

    context = {
        'reservations': reservations,
        'facilities': Facility.objects.all(),
        'statuses': Reservation.Status.choices,
        'filters': {
            'start_date': start_date,
            'end_date': end_date,
            'status': status,
            'facility': facility_id,
        },
        'summary': summary,
    }
    return render(request, 'reservations/reservation_report.html', context)


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
    if request.method == 'POST':
        form = ReservationForm(request.POST)
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
        form = ReservationForm()

    return render(request, 'reservations/reservation_form.html', {'form': form})


@login_required
def reservation_detail_view(request, pk):
    """
    Displays the full details of a single reservation.

    Object-level authorization:
    - REQUESTER: may only view their OWN reservations.
      Attempting to access another user's reservation returns 403,
      not 404, because 404 would obscure a security boundary with a
      "not found" lie. The resource exists; the requester simply has
      no right to it.
    - STAFF: may view any reservation (needed for operational workflow).
    - ADMIN: may view any reservation.

    Backend-Frontend Contract:
    - Template: 'reservations/reservation_detail.html'
    - Context:
        - reservation: single Reservation instance with facility and
                       requested_by pre-fetched
    """
    reservation = get_object_or_404(
        Reservation.objects.select_related('facility', 'requested_by', 'reviewed_by'),
        pk=pk,
    )

    user = request.user
    if user.is_requester_role:
        if reservation.requested_by != user:
            raise PermissionDenied(
                'You do not have permission to view this reservation.'
            )
    # STAFF and ADMIN reach here without restriction

    return render(request, 'reservations/reservation_detail.html', {'reservation': reservation})


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
      REJECTED and CANCELLED reservations cannot be cancelled again.
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
@staff_or_admin_required
def approve_reservation_view(request, pk):
    """
    Allows STAFF or ADMIN to approve a PENDING reservation.

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

    reservation = get_object_or_404(Reservation, pk=pk)

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
@staff_or_admin_required
def reject_reservation_view(request, pk):
    """
    Allows STAFF or ADMIN to reject a PENDING reservation with a mandatory reason.

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

    reservation = get_object_or_404(Reservation, pk=pk)
    reason = request.POST.get('reason', '').strip()

    if not reason:
        messages.error(request, 'A rejection reason is required.')
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
                    f'{reservation.reservation_date} was rejected. '
                    f'Reason: {reservation.rejection_reason}'
                ),
            )
        messages.success(
            request,
            f'Reservation #{reservation.pk} has been rejected.'
        )
        return redirect('reservations:pending_reservations')
    except ValidationError as exc:
        messages.error(request, exc.message)
        return redirect('reservations:reservation_detail', pk=pk)
