from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from accounts.decorators import requester_required, staff_or_admin_required
from .models import Reservation


@login_required
@requester_required
def my_reservations_view(request):
    """
    Shows only the reservations submitted by the currently authenticated user.
    Hard-filtered to request.user to prevent IDOR vulnerabilities.

    Backend-Frontend Contract:
    - Template: 'reservations/my_reservations.html'
    - Context:
        - reservations: QuerySet of Reservation records where requested_by == request.user
    """
    reservations = Reservation.objects.filter(
        requested_by=request.user
    ).select_related('facility').order_by('-reservation_date', '-start_time')

    context = {
        'reservations': reservations,
    }
    return render(request, 'reservations/my_reservations.html', context)


@login_required
@staff_or_admin_required
def pending_reservations_view(request):
    """
    Shows pending reservation requests awaiting review by Staff or Admin.

    Backend-Frontend Contract:
    - Template: 'reservations/pending_reservations.html'
    - Context:
        - reservations: QuerySet of Reservation records where status == Status.PENDING
    """
    reservations = Reservation.objects.filter(
        status=Reservation.Status.PENDING
    ).select_related('facility', 'requested_by').order_by('reservation_date', 'start_time')

    context = {
        'reservations': reservations,
    }
    return render(request, 'reservations/pending_reservations.html', context)
