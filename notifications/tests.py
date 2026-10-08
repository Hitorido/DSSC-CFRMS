"""
Notification model, integration, and security tests.

Covers:
  Model:
    - Notification can be created with required fields
    - is_read defaults to False
    - recipient reverse relationship (related_name='notifications') works
    - reservation FK is nullable
    - __str__ is correct

  Integration (reservation approve/reject → notification creation):
    - Approving a reservation creates exactly one notification
    - Approval notification belongs to the requester, not the reviewer
    - Approval notification message identifies facility and outcome
    - Rejecting a reservation creates exactly one notification
    - Rejection notification belongs to the requester, not the reviewer
    - Rejection notification message contains rejection reason and outcome
    - Reviewer does NOT receive a notification
    - Failed approval (already approved) creates no notification
    - Failed rejection (already rejected) creates no notification
    - Repeated invalid transition does not accumulate duplicate notifications
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from facilities.models import Facility, FacilityType
from notifications.models import Notification
from reservations.models import Reservation

User = get_user_model()


class NotificationModelTests(TestCase):
    """Basic model field and relationship tests."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='notif_user',
            password='testpass123',
            email='nu@dssc.edu.ph',
            role=User.Role.REQUESTER,
        )

        facility_type = FacilityType.objects.create(name='Notif Lab')
        self.facility = Facility.objects.create(
            facility_type=facility_type,
            name='Notif Test Room',
            location='Building N',
            capacity=20,
            status=Facility.Status.AVAILABLE,
        )
        self.tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        self.reservation = Reservation.objects.create(
            requested_by=self.user,
            facility=self.facility,
            purpose='Notif model test',
            reservation_date=self.tomorrow,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )

    def test_notification_can_be_created(self):
        """A Notification can be created with all required fields."""
        n = Notification.objects.create(
            recipient=self.user,
            reservation=self.reservation,
            message='Test notification message.',
        )
        self.assertIsNotNone(n.pk)
        self.assertEqual(n.recipient, self.user)
        self.assertEqual(n.reservation, self.reservation)
        self.assertEqual(n.message, 'Test notification message.')

    def test_is_read_defaults_to_false(self):
        """is_read must default to False on creation."""
        n = Notification.objects.create(
            recipient=self.user,
            message='Unread by default.',
        )
        self.assertFalse(n.is_read)

    def test_recipient_reverse_relationship(self):
        """
        related_name='notifications' allows user.notifications.all()
        and correctly returns notifications belonging to that user.
        """
        n = Notification.objects.create(
            recipient=self.user,
            message='Reverse relationship test.',
        )
        self.assertIn(n, self.user.notifications.all())

    def test_reservation_fk_is_nullable(self):
        """reservation may be None — a notification does not require a linked reservation."""
        n = Notification.objects.create(
            recipient=self.user,
            reservation=None,
            message='No reservation attached.',
        )
        self.assertIsNone(n.reservation)

    def test_str_representation_unread(self):
        """__str__ shows username, [unread], and truncated message."""
        n = Notification.objects.create(
            recipient=self.user,
            message='A notification message for str test.',
        )
        s = str(n)
        self.assertIn('notif_user', s)
        self.assertIn('unread', s)
        self.assertIn('A notification message', s)

    def test_str_representation_read(self):
        """__str__ shows [read] once is_read is True."""
        n = Notification.objects.create(
            recipient=self.user,
            message='Already read notification.',
            is_read=True,
        )
        self.assertIn('read', str(n))
        self.assertNotIn('unread', str(n))

    def test_ordering_newest_first(self):
        """Notifications are ordered by -created_at (newest first)."""
        n1 = Notification.objects.create(recipient=self.user, message='First')
        n2 = Notification.objects.create(recipient=self.user, message='Second')
        qs = list(Notification.objects.filter(recipient=self.user))
        # n2 was created later, so it should appear first
        self.assertEqual(qs[0], n2)
        self.assertEqual(qs[1], n1)


class NotificationIntegrationTests(TestCase):
    """
    Integration tests: reservation approve/reject views create the correct
    notifications via Notification.objects.create() in reservations/views.py.
    These tests exercise the full HTTP layer to confirm the integration is wired.
    """

    def setUp(self):
        self.client = Client()

        self.requester = User.objects.create_user(
            username='integ_requester',
            password='testpass123',
            email='ir@dssc.edu.ph',
            role=User.Role.REQUESTER,
        )
        self.staff_user = User.objects.create_user(
            username='integ_staff',
            password='testpass123',
            email='is@dssc.edu.ph',
            role=User.Role.STAFF,
        )

        facility_type = FacilityType.objects.create(name='Integ Lab')
        self.facility = Facility.objects.create(
            facility_type=facility_type,
            name='Integration Test Room',
            location='Building I',
            capacity=25,
            status=Facility.Status.AVAILABLE,
        )
        self.tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        self.reservation = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Integration test reservation',
            reservation_date=self.tomorrow,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )

    # -------------------------------------------------------------------
    # APPROVAL NOTIFICATIONS
    # -------------------------------------------------------------------

    def test_approving_reservation_creates_exactly_one_notification(self):
        """Approving a PENDING reservation creates exactly one Notification."""
        count_before = Notification.objects.count()
        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('reservations:approve_reservation', kwargs={'pk': self.reservation.pk})
        )
        self.assertEqual(Notification.objects.count(), count_before + 1)

    def test_approval_notification_belongs_to_requester(self):
        """The approval notification's recipient is the reservation's requester."""
        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('reservations:approve_reservation', kwargs={'pk': self.reservation.pk})
        )
        n = Notification.objects.filter(recipient=self.requester).first()
        self.assertIsNotNone(n)
        self.assertEqual(n.recipient, self.requester)

    def test_approval_notification_message_identifies_facility_and_outcome(self):
        """Approval notification message contains the facility name and 'approved'."""
        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('reservations:approve_reservation', kwargs={'pk': self.reservation.pk})
        )
        n = Notification.objects.filter(recipient=self.requester).first()
        self.assertIn('Integration Test Room', n.message)
        self.assertIn('approved', n.message.lower())

    def test_reviewer_does_not_receive_approval_notification(self):
        """The reviewing staff user must NOT receive the notification — only the requester does."""
        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('reservations:approve_reservation', kwargs={'pk': self.reservation.pk})
        )
        self.assertEqual(
            Notification.objects.filter(recipient=self.staff_user).count(), 0
        )

    # -------------------------------------------------------------------
    # REJECTION NOTIFICATIONS
    # -------------------------------------------------------------------

    def test_rejecting_reservation_creates_exactly_one_notification(self):
        """Rejecting a PENDING reservation creates exactly one Notification."""
        count_before = Notification.objects.count()
        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('reservations:reject_reservation', kwargs={'pk': self.reservation.pk}),
            {'reason': 'Facility reserved for accreditation.'},
        )
        self.assertEqual(Notification.objects.count(), count_before + 1)

    def test_rejection_notification_belongs_to_requester(self):
        """The rejection notification's recipient is the reservation's requester."""
        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('reservations:reject_reservation', kwargs={'pk': self.reservation.pk}),
            {'reason': 'Facility reserved for accreditation.'},
        )
        n = Notification.objects.filter(recipient=self.requester).first()
        self.assertIsNotNone(n)
        self.assertEqual(n.recipient, self.requester)

    def test_rejection_notification_message_contains_reason_and_outcome(self):
        """Rejection message contains the rejection reason and 'rejected'."""
        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('reservations:reject_reservation', kwargs={'pk': self.reservation.pk}),
            {'reason': 'Facility reserved for accreditation.'},
        )
        n = Notification.objects.filter(recipient=self.requester).first()
        self.assertIn('rejected', n.message.lower())
        self.assertIn('Facility reserved for accreditation.', n.message)

    def test_reviewer_does_not_receive_rejection_notification(self):
        """The reviewing staff user must NOT receive the rejection notification."""
        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('reservations:reject_reservation', kwargs={'pk': self.reservation.pk}),
            {'reason': 'Facility reserved for accreditation.'},
        )
        self.assertEqual(
            Notification.objects.filter(recipient=self.staff_user).count(), 0
        )

    # -------------------------------------------------------------------
    # FAILED TRANSITIONS — no notifications created
    # -------------------------------------------------------------------

    def test_failed_approval_creates_no_notification(self):
        """
        Approving an already-APPROVED reservation fails with ValidationError.
        No notification must be created for the failed transition.
        """
        # First, approve successfully
        self.reservation.approve(reviewer=self.staff_user)
        count_after_first = Notification.objects.count()

        # Attempt to approve again — this must fail
        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('reservations:approve_reservation', kwargs={'pk': self.reservation.pk})
        )
        # Notification count must remain unchanged
        self.assertEqual(Notification.objects.count(), count_after_first)

    def test_failed_rejection_creates_no_notification(self):
        """
        Rejecting an already-REJECTED reservation fails with ValidationError.
        No notification must be created for the failed transition.
        """
        # First, reject successfully
        self.reservation.reject(reviewer=self.staff_user, reason='Initial rejection.')
        count_after_first = Notification.objects.count()

        # Attempt to reject again — this must fail
        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('reservations:reject_reservation', kwargs={'pk': self.reservation.pk}),
            {'reason': 'Second attempt.'},
        )
        self.assertEqual(Notification.objects.count(), count_after_first)

    def test_repeated_invalid_transition_does_not_accumulate_notifications(self):
        """
        Repeated failed approval attempts must not create accumulating notifications.
        Zero additional notifications after two failed attempts.
        """
        # Approve once to make further approvals invalid
        self.reservation.approve(reviewer=self.staff_user)
        count_after_valid = Notification.objects.count()

        self.client.force_login(self.staff_user)
        # Attempt twice more
        self.client.post(
            reverse('reservations:approve_reservation', kwargs={'pk': self.reservation.pk})
        )
        self.client.post(
            reverse('reservations:approve_reservation', kwargs={'pk': self.reservation.pk})
        )
        self.assertEqual(Notification.objects.count(), count_after_valid)


class NotificationAtomicityTests(TestCase):
    """
    Verify that reservation status changes and notification creation
    are atomic: if notification creation fails, the reservation must
    remain in its original PENDING state (no partial write).

    We use unittest.mock.patch to simulate a database failure inside
    Notification.objects.create() without corrupting the real database.

    New concept — unittest.mock.patch:
    patch() temporarily replaces a real function or method with a fake
    (Mock) object for the duration of the test. Here we replace
    Notification.objects.create with a function that raises an exception,
    simulating what would happen if the database rejected the INSERT.
    After the test, the original function is automatically restored.
    """

    def setUp(self):
        self.client = Client()

        self.requester = User.objects.create_user(
            username='atomic_requester',
            password='testpass123',
            email='ar@dssc.edu.ph',
            role=User.Role.REQUESTER,
        )
        self.staff_user = User.objects.create_user(
            username='atomic_staff',
            password='testpass123',
            email='as@dssc.edu.ph',
            role=User.Role.STAFF,
        )

        facility_type = FacilityType.objects.create(name='Atomic Lab')
        self.facility = Facility.objects.create(
            facility_type=facility_type,
            name='Atomic Test Room',
            location='Building A',
            capacity=20,
            status=Facility.Status.AVAILABLE,
        )
        self.tomorrow = timezone.localdate() + datetime.timedelta(days=1)

    def _make_reservation(self):
        """Create a fresh PENDING reservation for each test."""
        return Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Atomicity test reservation',
            reservation_date=self.tomorrow,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(16, 0),
        )

    def test_reservation_stays_pending_if_notification_create_fails_on_approve(self):
        """
        If Notification.objects.create() raises a database exception during
        approval, transaction.atomic() rolls back the entire transaction.
        The reservation must remain PENDING — no partial write.
        """
        from unittest.mock import patch
        from django.db import DatabaseError

        reservation = self._make_reservation()
        self.client.force_login(self.staff_user)

        with patch(
            'notifications.models.Notification.objects.create',
            side_effect=DatabaseError('Simulated DB failure during notification creation'),
        ):
            # The view will raise DatabaseError (not caught by the view's
            # except ValidationError clause), which propagates as a 500.
            # We use raises=False via assertRaises context to catch it.
            try:
                self.client.post(
                    reverse('reservations:approve_reservation',
                            kwargs={'pk': reservation.pk})
                )
            except DatabaseError:
                pass  # Expected — DB error propagates out of the view

        # The atomic block rolled back — reservation must still be PENDING
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.PENDING)
        # And no notification was created
        self.assertEqual(
            Notification.objects.filter(recipient=self.requester).count(), 0
        )

    def test_reservation_stays_pending_if_notification_create_fails_on_reject(self):
        """
        If Notification.objects.create() raises a database exception during
        rejection, transaction.atomic() rolls back the entire transaction.
        The reservation must remain PENDING — no partial write.
        """
        from unittest.mock import patch
        from django.db import DatabaseError

        reservation = self._make_reservation()
        self.client.force_login(self.staff_user)

        with patch(
            'notifications.models.Notification.objects.create',
            side_effect=DatabaseError('Simulated DB failure during notification creation'),
        ):
            try:
                self.client.post(
                    reverse('reservations:reject_reservation',
                            kwargs={'pk': reservation.pk}),
                    {'reason': 'Test rejection reason.'},
                )
            except DatabaseError:
                pass  # Expected

        # The atomic block rolled back — reservation must still be PENDING
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.PENDING)
        self.assertEqual(
            Notification.objects.filter(recipient=self.requester).count(), 0
        )


# ===========================================================================
# PHASE 4 — Notification UI, read/unread, context processor, IDOR tests
# ===========================================================================

class NotificationListViewTests(TestCase):
    """Authentication, ownership, and content tests for the notification list view."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='list_user',
            password='testpass123',
            role=User.Role.REQUESTER,
        )
        self.other_user = User.objects.create_user(
            username='list_other',
            password='testpass123',
            role=User.Role.REQUESTER,
        )
        self.notif = Notification.objects.create(
            recipient=self.user,
            message='List view test notification.',
        )
        self.other_notif = Notification.objects.create(
            recipient=self.other_user,
            message='Other user notification — must not appear.',
        )

    def test_anonymous_redirected_to_login(self):
        """Anonymous user is redirected to login."""
        response = self.client.get(reverse('notifications:notification_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_authenticated_user_can_access_list(self):
        """Authenticated user can access the notification list."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('notifications:notification_list'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('notifications', response.context)

    def test_list_shows_only_own_notifications(self):
        """QuerySet is scoped to request.user — other users' notifications are excluded."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('notifications:notification_list'))
        qs = response.context['notifications']
        self.assertIn(self.notif, qs)
        self.assertNotIn(self.other_notif, qs)

    def test_all_roles_can_access_list(self):
        """STAFF and ADMIN roles can also access the notification list."""
        for role in [User.Role.STAFF, User.Role.ADMIN]:
            staff_or_admin = User.objects.create_user(
                username=f'list_{role.lower()}',
                password='testpass123',
                role=role,
            )
            self.client.force_login(staff_or_admin)
            response = self.client.get(reverse('notifications:notification_list'))
            self.assertEqual(response.status_code, 200)


class MarkNotificationReadTests(TestCase):
    """Tests for the mark-single-notification-read endpoint."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='read_user',
            password='testpass123',
            role=User.Role.REQUESTER,
        )
        self.other_user = User.objects.create_user(
            username='read_other',
            password='testpass123',
            role=User.Role.REQUESTER,
        )
        self.notif = Notification.objects.create(
            recipient=self.user,
            message='Unread notification.',
        )
        self.other_notif = Notification.objects.create(
            recipient=self.other_user,
            message='Other user notification.',
        )

    def test_anonymous_redirected(self):
        """Anonymous user is redirected to login."""
        response = self.client.post(
            reverse('notifications:mark_read', kwargs={'pk': self.notif.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_get_returns_405(self):
        """GET request to mark-read returns 405 — must be POST."""
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('notifications:mark_read', kwargs={'pk': self.notif.pk})
        )
        self.assertEqual(response.status_code, 405)
        self.notif.refresh_from_db()
        self.assertFalse(self.notif.is_read)

    def test_post_marks_notification_as_read(self):
        """POST marks the notification is_read=True."""
        self.client.force_login(self.user)
        self.client.post(
            reverse('notifications:mark_read', kwargs={'pk': self.notif.pk})
        )
        self.notif.refresh_from_db()
        self.assertTrue(self.notif.is_read)

    def test_post_redirects_to_notification_list(self):
        """Successful POST redirects to the notification list."""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('notifications:mark_read', kwargs={'pk': self.notif.pk})
        )
        self.assertRedirects(
            response,
            reverse('notifications:notification_list'),
            fetch_redirect_response=False,
        )

    def test_user_cannot_mark_another_users_notification_read(self):
        """
        IDOR protection: user cannot mark another user's notification as read.
        Must receive 403 Forbidden.
        """
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('notifications:mark_read', kwargs={'pk': self.other_notif.pk})
        )
        self.assertEqual(response.status_code, 403)
        self.other_notif.refresh_from_db()
        self.assertFalse(self.other_notif.is_read)

    def test_nonexistent_notification_returns_404(self):
        """Attempting to mark a non-existent notification returns 404."""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('notifications:mark_read', kwargs={'pk': 99999})
        )
        self.assertEqual(response.status_code, 404)


class MarkAllNotificationsReadTests(TestCase):
    """Tests for the mark-all-read endpoint."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='markall_user',
            password='testpass123',
            role=User.Role.REQUESTER,
        )
        self.other_user = User.objects.create_user(
            username='markall_other',
            password='testpass123',
            role=User.Role.REQUESTER,
        )
        # Two unread notifications for self.user
        self.n1 = Notification.objects.create(recipient=self.user, message='First.')
        self.n2 = Notification.objects.create(recipient=self.user, message='Second.')
        # One unread notification for other_user
        self.n_other = Notification.objects.create(
            recipient=self.other_user, message='Other.'
        )

    def test_anonymous_redirected(self):
        """Anonymous user is redirected to login."""
        response = self.client.post(reverse('notifications:mark_all_read'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_get_returns_405(self):
        """GET to mark-all-read returns 405."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('notifications:mark_all_read'))
        self.assertEqual(response.status_code, 405)

    def test_mark_all_read_marks_only_own_notifications(self):
        """
        Mark-all-read updates only the current user's notifications.
        Other users' notifications must remain unread.
        """
        self.client.force_login(self.user)
        self.client.post(reverse('notifications:mark_all_read'))

        self.n1.refresh_from_db()
        self.n2.refresh_from_db()
        self.n_other.refresh_from_db()

        self.assertTrue(self.n1.is_read)
        self.assertTrue(self.n2.is_read)
        self.assertFalse(self.n_other.is_read)   # other user unaffected

    def test_mark_all_read_redirects_to_list(self):
        """POST to mark-all-read redirects to notification_list."""
        self.client.force_login(self.user)
        response = self.client.post(reverse('notifications:mark_all_read'))
        self.assertRedirects(
            response,
            reverse('notifications:notification_list'),
            fetch_redirect_response=False,
        )


class UnreadCountContextProcessorTests(TestCase):
    """Tests for the unread_notification_count context processor."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='ctx_user',
            password='testpass123',
            role=User.Role.REQUESTER,
        )

    def test_unread_count_is_zero_for_anonymous(self):
        """Anonymous users receive unread_notification_count=0 in template context."""
        response = self.client.get(reverse('accounts:login'))
        # login page renders without user — context processor returns 0
        self.assertEqual(response.context.get('unread_notification_count', 0), 0)

    def test_unread_count_reflects_unread_notifications(self):
        """
        Context processor injects the correct unread count for the logged-in user.
        Verified through a real page response so the processor runs for real.
        """
        Notification.objects.create(recipient=self.user, message='Unread 1.')
        Notification.objects.create(recipient=self.user, message='Unread 2.')
        Notification.objects.create(recipient=self.user, message='Read.', is_read=True)

        self.client.force_login(self.user)
        response = self.client.get(reverse('notifications:notification_list'))
        self.assertEqual(response.context['unread_notification_count'], 2)

    def test_unread_count_updates_after_mark_all_read(self):
        """After mark-all-read, unread count drops to 0 on the next request."""
        Notification.objects.create(recipient=self.user, message='Unread.')
        self.client.force_login(self.user)

        # Mark all read
        self.client.post(reverse('notifications:mark_all_read'))

        response = self.client.get(reverse('notifications:notification_list'))
        self.assertEqual(response.context['unread_notification_count'], 0)

    def test_unread_count_only_counts_own_notifications(self):
        """
        The context processor must not count another user's unread notifications.
        """
        other = User.objects.create_user(
            username='ctx_other', password='x', role=User.Role.REQUESTER
        )
        Notification.objects.create(recipient=other, message='Other unread.')

        self.client.force_login(self.user)
        response = self.client.get(reverse('notifications:notification_list'))
        self.assertEqual(response.context['unread_notification_count'], 0)


class NotificationReservationLinkTests(TestCase):
    """
    Tests for the reservation link shown in the notification list.
    The link must only appear when the reservation still exists and
    the current user is authorised to view it.
    """

    def setUp(self):
        self.client = Client()
        self.requester = User.objects.create_user(
            username='link_requester',
            password='testpass123',
            role=User.Role.REQUESTER,
        )
        self.other_requester = User.objects.create_user(
            username='link_other',
            password='testpass123',
            role=User.Role.REQUESTER,
        )
        self.staff_user = User.objects.create_user(
            username='link_staff',
            password='testpass123',
            role=User.Role.STAFF,
        )
        facility_type = FacilityType.objects.create(name='Link Lab')
        self.facility = Facility.objects.create(
            facility_type=facility_type,
            name='Link Test Room',
            location='Building L',
            capacity=20,
            status=Facility.Status.AVAILABLE,
        )
        self.tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        self.reservation = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Link test reservation',
            reservation_date=self.tomorrow,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )
        # Notification linked to the reservation
        self.notif = Notification.objects.create(
            recipient=self.requester,
            reservation=self.reservation,
            message='Your reservation was approved.',
        )

    def test_reservation_link_shown_to_owner(self):
        """The 'View Reservation' link appears for the reservation owner."""
        self.client.force_login(self.requester)
        response = self.client.get(reverse('notifications:notification_list'))
        self.assertContains(
            response,
            reverse('reservations:reservation_detail',
                    kwargs={'pk': self.reservation.pk})
        )

    def test_reservation_link_shown_to_staff(self):
        """Staff users see the 'View Reservation' link for any notification's reservation."""
        staff_notif = Notification.objects.create(
            recipient=self.staff_user,
            reservation=self.reservation,
            message='Staff-visible notification.',
        )
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('notifications:notification_list'))
        self.assertContains(
            response,
            reverse('reservations:reservation_detail',
                    kwargs={'pk': self.reservation.pk})
        )

    def test_reservation_link_hidden_for_other_requester(self):
        """
        A REQUESTER who is NOT the reservation owner sees a notification without
        the 'View Reservation' link (they would get 403 if they followed it).
        The template only renders the link when the user can access the reservation.
        """
        # Give other_requester a notification referencing requester's reservation
        other_notif = Notification.objects.create(
            recipient=self.other_requester,
            reservation=self.reservation,
            message='Notification for different user.',
        )
        self.client.force_login(self.other_requester)
        response = self.client.get(reverse('notifications:notification_list'))
        # The reservation detail URL should NOT appear in the response for this user
        self.assertNotContains(
            response,
            reverse('reservations:reservation_detail',
                    kwargs={'pk': self.reservation.pk})
        )

    def test_deleted_reservation_handled_safely(self):
        """
        When reservation is SET_NULL (reservation deleted), the notification
        still renders without a 'View Reservation' link and no server error.
        """
        # Directly set reservation to None to simulate SET_NULL
        self.notif.reservation = None
        self.notif.save()

        self.client.force_login(self.requester)
        response = self.client.get(reverse('notifications:notification_list'))
        self.assertEqual(response.status_code, 200)
        # 'View Reservation' link must not appear
        self.assertNotContains(response, 'View Reservation')
