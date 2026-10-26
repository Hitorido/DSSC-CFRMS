from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from config.list_utils import filter_query_string, paginate_queryset
from .models import Notification


@login_required
def notification_list_view(request):
    """
    Display all notifications belonging to the currently authenticated user,
    newest first. All authenticated users (any role) may access this view.

    Security: QuerySet is always scoped to request.user — the user identity
    comes from the server-side session, never from URL parameters or POST data.

    Backend-Frontend Contract:
    - Template: 'notifications/notification_list.html'
    - Context:
        - notifications: current page of Notification rows for request.user
        - page_obj / paginator / page_range_choices: pagination metadata
    """
    notifications = (
        Notification.objects
        .filter(recipient=request.user)
        .select_related('reservation', 'reservation__facility', 'reservation__requested_by')
        .order_by('-created_at')
    )
    search = request.GET.get('search', '').strip()
    if search:
        notifications = notifications.filter(
            Q(message__icontains=search)
            | Q(reservation__facility__name__icontains=search)
        )

    pagination = paginate_queryset(notifications, request.GET.get('page'))
    return render(request, 'notifications/notification_list.html', {
        'notifications': pagination['page_obj'],
        'filters': {'search': search},
        'filter_query': filter_query_string(request),
        **pagination,
    })


@login_required
def mark_notification_read_view(request, pk):
    """
    Mark a single notification as read.

    POST-only: GET returns 405. State changes must not be triggered by link
    pre-fetching or browser navigation.

    Object-level ownership: only the recipient may mark their own notification
    as read. Any attempt to act on another user's notification returns 403.
    This prevents IDOR — a user cannot mark someone else's notification read
    by guessing or enumerating notification PKs in the URL.

    Backend-Frontend Contract:
    - No dedicated template; POSTs from notification_list.
    - On success: redirect to notification_list.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    notification = get_object_or_404(Notification, pk=pk)

    if notification.recipient != request.user:
        raise PermissionDenied('You can only manage your own notifications.')

    notification.is_read = True
    notification.save()

    return redirect('notifications:notification_list')


@login_required
def mark_all_notifications_read_view(request):
    """
    Mark all of the current user's unread notifications as read in one action.

    POST-only: GET returns 405.

    Security: update is always scoped to recipient=request.user. The
    QuerySet never touches another user's notifications regardless of what
    is in the POST body.

    Backend-Frontend Contract:
    - No dedicated template; POSTs from notification_list.
    - On success: redirect to notification_list.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).update(is_read=True)

    return redirect('notifications:notification_list')
