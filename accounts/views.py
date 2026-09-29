from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from facilities.models import Facility
from reservations.models import Reservation


@login_required
def home_view(request):
    """
    Authenticated landing view / basic KPI dashboard.

    Backend-Frontend Contract:
    - Template: 'home.html'
    - Context:
        - user: request.user (accounts.User instance)
        - total_facilities: Total count of facilities registered in the system
        - total_reservations: Total count of reservations (system-wide for STAFF/ADMIN, own for REQUESTER)
        - pending_reservations: Count of pending reservations (system-wide for STAFF/ADMIN, own for REQUESTER)
        - approved_reservations: Count of approved reservations (system-wide for STAFF/ADMIN, own for REQUESTER)
        - todays_reservations: Count of reservations for today (system-wide for STAFF/ADMIN, own for REQUESTER)
    """
    user = request.user

    if user.is_staff_role or user.is_admin_role:
        reservation_qs = Reservation.objects.all()
    else:
        reservation_qs = Reservation.objects.filter(requested_by=user)

    today = timezone.localdate()

    context = {
        'user': user,
        'total_facilities': Facility.objects.count(),
        'total_reservations': reservation_qs.count(),
        'pending_reservations': reservation_qs.filter(status=Reservation.Status.PENDING).count(),
        'approved_reservations': reservation_qs.filter(status=Reservation.Status.APPROVED).count(),
        'todays_reservations': reservation_qs.filter(reservation_date=today).count(),
    }
    return render(request, 'home.html', context)

