"""
Reservation application workflow tests.

Covers:
- Reservation creation (form, view, security)
- Reservation detail (object-level authorization)
- Requester cancellation (ownership, lifecycle)
- Staff/Admin approval (RBAC, lifecycle, reviewer recording)
- Staff/Admin rejection (RBAC, reason required, lifecycle)

Baseline: 43 tests existed before this feature (model + RBAC tests).
"""
import datetime

from django.contrib import messages as django_messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from facilities.models import Facility, FacilityType
from reservations.models import Reservation

User = get_user_model()


class WorkflowTestBase(TestCase):
    """
    Shared setUp for all workflow test cases.
    Creates users, facility, and common reservation fixtures.
    """

    def setUp(self):
        self.client = Client()

        self.requester = User.objects.create_user(
            username='requester1',
            password='testpass123',
            email='r1@dssc.edu.ph',
            role=User.Role.REQUESTER,
        )
        self.requester2 = User.objects.create_user(
            username='requester2',
            password='testpass123',
            email='r2@dssc.edu.ph',
            role=User.Role.REQUESTER,
        )
        self.staff_user = User.objects.create_user(
            username='staff1',
            password='testpass123',
            email='s1@dssc.edu.ph',
            role=User.Role.STAFF,
        )
        self.admin_user = User.objects.create_user(
            username='admin1',
            password='testpass123',
            email='a1@dssc.edu.ph',
            role=User.Role.ADMIN,
        )

        facility_type = FacilityType.objects.create(name='Conference Room')
        self.facility = Facility.objects.create(
            facility_type=facility_type,
            name='Main Conference Room',
            location='Admin Building',
            capacity=30,
            status=Facility.Status.AVAILABLE,
        )
        self.unavailable_facility = Facility.objects.create(
            facility_type=facility_type,
            name='Closed Room',
            location='Building B',
            capacity=20,
            status=Facility.Status.UNAVAILABLE,
        )

        self.tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        self.day_after = timezone.localdate() + datetime.timedelta(days=2)

        # A pre-existing reservation owned by requester1
        self.reservation = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Test Meeting',
            reservation_date=self.tomorrow,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )


# ---------------------------------------------------------------------------
# CREATION TESTS
# ---------------------------------------------------------------------------

class ReservationCreationViewTests(WorkflowTestBase):

    def _post_valid(self, user=None):
        """Helper: POST a valid reservation creation as the given user (default: requester)."""
        if user is None:
            user = self.requester
        self.client.force_login(user)
        return self.client.post(reverse('reservations:create_reservation'), {
            'facility': self.facility.pk,
            'purpose': 'New Event',
            'reservation_date': self.day_after.isoformat(),
            'start_time': '14:00',
            'end_time': '16:00',
        })

    def test_requester_can_access_create_form(self):
        """REQUESTER can GET the create reservation form."""
        self.client.force_login(self.requester)
        response = self.client.get(reverse('reservations:create_reservation'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)

    def test_anonymous_create_redirects_to_login(self):
        """Anonymous user accessing create form is redirected to login."""
        response = self.client.get(reverse('reservations:create_reservation'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_staff_cannot_use_requester_create_endpoint(self):
        """STAFF user gets 403 on the requester-only create endpoint."""
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('reservations:create_reservation'))
        self.assertEqual(response.status_code, 403)

    def test_admin_cannot_use_requester_create_endpoint(self):
        """ADMIN user gets 403 on the requester-only create endpoint."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('reservations:create_reservation'))
        self.assertEqual(response.status_code, 403)

    def test_valid_post_creates_pending_reservation(self):
        """Valid POST creates a PENDING reservation in the database."""
        self._post_valid()
        new_res = Reservation.objects.filter(
            requested_by=self.requester,
            purpose='New Event',
        ).first()
        self.assertIsNotNone(new_res)
        self.assertEqual(new_res.status, Reservation.Status.PENDING)

    def test_requested_by_is_authenticated_user_not_post_data(self):
        """requested_by is set from session, not from any POST field."""
        # POST includes no 'requested_by' field — it should be assigned server-side
        self._post_valid(user=self.requester)
        new_res = Reservation.objects.filter(purpose='New Event').first()
        self.assertIsNotNone(new_res)
        self.assertEqual(new_res.requested_by, self.requester)

    def test_browser_cannot_forge_requested_by(self):
        """
        Even if the POST includes a forged requested_by value, the view
        ignores it and assigns request.user. The form excludes requested_by
        so it simply never reaches the model from form data.
        """
        self.client.force_login(self.requester)
        self.client.post(reverse('reservations:create_reservation'), {
            'facility': self.facility.pk,
            'purpose': 'Forged Ownership',
            'reservation_date': self.day_after.isoformat(),
            'start_time': '14:00',
            'end_time': '16:00',
            'requested_by': self.requester2.pk,  # forged — must be ignored
        })
        forged_res = Reservation.objects.filter(purpose='Forged Ownership').first()
        self.assertIsNotNone(forged_res)
        self.assertEqual(forged_res.requested_by, self.requester)  # session user, not forged pk

    def test_valid_post_redirects_to_my_reservations(self):
        """Successful POST redirects to my_reservations (POST/Redirect/GET)."""
        response = self._post_valid()
        self.assertRedirects(response, reverse('reservations:my_reservations'),
                             fetch_redirect_response=False)

    def test_invalid_time_range_rejected(self):
        """end_time <= start_time returns form with errors, no reservation created."""
        self.client.force_login(self.requester)
        count_before = Reservation.objects.count()
        response = self.client.post(reverse('reservations:create_reservation'), {
            'facility': self.facility.pk,
            'purpose': 'Bad Times',
            'reservation_date': self.day_after.isoformat(),
            'start_time': '14:00',
            'end_time': '13:00',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Reservation.objects.count(), count_before)

    def test_past_date_rejected(self):
        """Reservation date in the past returns form with errors, no reservation created."""
        self.client.force_login(self.requester)
        yesterday = (timezone.localdate() - datetime.timedelta(days=1)).isoformat()
        count_before = Reservation.objects.count()
        response = self.client.post(reverse('reservations:create_reservation'), {
            'facility': self.facility.pk,
            'purpose': 'Past Event',
            'reservation_date': yesterday,
            'start_time': '09:00',
            'end_time': '11:00',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Reservation.objects.count(), count_before)

    def test_unavailable_facility_rejected(self):
        """Posting a reservation for an UNAVAILABLE facility returns errors."""
        self.client.force_login(self.requester)
        count_before = Reservation.objects.count()
        response = self.client.post(reverse('reservations:create_reservation'), {
            'facility': self.unavailable_facility.pk,
            'purpose': 'Unavailable Room',
            'reservation_date': self.day_after.isoformat(),
            'start_time': '09:00',
            'end_time': '11:00',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Reservation.objects.count(), count_before)

    def test_conflicting_reservation_rejected(self):
        """
        self.reservation already holds 09:00-11:00 on tomorrow.
        An overlapping POST for the same slot must not create a new record.
        """
        self.client.force_login(self.requester)
        count_before = Reservation.objects.count()
        response = self.client.post(reverse('reservations:create_reservation'), {
            'facility': self.facility.pk,
            'purpose': 'Conflicting Slot',
            'reservation_date': self.tomorrow.isoformat(),
            'start_time': '10:00',
            'end_time': '12:00',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Reservation.objects.count(), count_before)


# ---------------------------------------------------------------------------
# DETAIL SECURITY TESTS
# ---------------------------------------------------------------------------

class ReservationDetailAuthorizationTests(WorkflowTestBase):

    def test_requester_can_view_own_reservation(self):
        """REQUESTER can view their own reservation detail."""
        self.client.force_login(self.requester)
        response = self.client.get(
            reverse('reservations:reservation_detail', kwargs={'pk': self.reservation.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['reservation'], self.reservation)

    def test_requester_cannot_view_another_users_reservation(self):
        """REQUESTER gets 403 when accessing a reservation they do not own."""
        other_res = Reservation.objects.create(
            requested_by=self.requester2,
            facility=self.facility,
            purpose='Requester2 Event',
            reservation_date=self.day_after,
            start_time=datetime.time(13, 0),
            end_time=datetime.time(15, 0),
        )
        self.client.force_login(self.requester)
        response = self.client.get(
            reverse('reservations:reservation_detail', kwargs={'pk': other_res.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_can_view_any_reservation_detail(self):
        """STAFF can view reservation detail for any requester's reservation."""
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse('reservations:reservation_detail', kwargs={'pk': self.reservation.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_admin_can_view_any_reservation_detail(self):
        """ADMIN can view reservation detail for any requester's reservation."""
        self.client.force_login(self.admin_user)
        response = self.client.get(
            reverse('reservations:reservation_detail', kwargs={'pk': self.reservation.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_anonymous_user_redirected_to_login(self):
        """Anonymous user accessing detail is redirected to login."""
        response = self.client.get(
            reverse('reservations:reservation_detail', kwargs={'pk': self.reservation.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_nonexistent_reservation_returns_404(self):
        """Accessing a non-existent pk returns 404."""
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse('reservations:reservation_detail', kwargs={'pk': 99999})
        )
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# CANCELLATION TESTS
# ---------------------------------------------------------------------------

class ReservationCancellationTests(WorkflowTestBase):

    def test_requester_can_cancel_own_pending_reservation(self):
        """REQUESTER can POST to cancel their own PENDING reservation."""
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse('reservations:cancel_reservation', kwargs={'pk': self.reservation.pk})
        )
        self.assertRedirects(response, reverse('reservations:my_reservations'),
                             fetch_redirect_response=False)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.CANCELLED)

    def test_get_request_does_not_cancel(self):
        """GET request to cancel endpoint returns 405, does not cancel."""
        self.client.force_login(self.requester)
        response = self.client.get(
            reverse('reservations:cancel_reservation', kwargs={'pk': self.reservation.pk})
        )
        self.assertEqual(response.status_code, 405)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.PENDING)

    def test_requester_cannot_cancel_another_users_reservation(self):
        """REQUESTER gets 403 when trying to cancel another user's reservation."""
        other_res = Reservation.objects.create(
            requested_by=self.requester2,
            facility=self.facility,
            purpose='Requester2 Reservation',
            reservation_date=self.day_after,
            start_time=datetime.time(13, 0),
            end_time=datetime.time(15, 0),
        )
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse('reservations:cancel_reservation', kwargs={'pk': other_res.pk})
        )
        self.assertEqual(response.status_code, 403)
        other_res.refresh_from_db()
        self.assertNotEqual(other_res.status, Reservation.Status.CANCELLED)

    def test_staff_cannot_use_requester_cancel_endpoint(self):
        """STAFF gets 403 on the requester-only cancel endpoint."""
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse('reservations:cancel_reservation', kwargs={'pk': self.reservation.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_cancel_rejected_reservation_raises_error_message(self):
        """Cancelling an already-REJECTED reservation is an invalid transition; shows error."""
        self.reservation.status = Reservation.Status.REJECTED
        self.reservation.save()
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse('reservations:cancel_reservation', kwargs={'pk': self.reservation.pk})
        )
        # Should redirect (not crash) and show error message
        self.assertRedirects(response, reverse('reservations:my_reservations'),
                             fetch_redirect_response=False)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.REJECTED)

    def test_cancel_already_cancelled_reservation_raises_error_message(self):
        """Cancelling an already-CANCELLED reservation is an invalid transition; shows error."""
        self.reservation.status = Reservation.Status.CANCELLED
        self.reservation.save()
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse('reservations:cancel_reservation', kwargs={'pk': self.reservation.pk})
        )
        self.assertRedirects(response, reverse('reservations:my_reservations'),
                             fetch_redirect_response=False)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.CANCELLED)


# ---------------------------------------------------------------------------
# APPROVAL TESTS
# ---------------------------------------------------------------------------

class ReservationApprovalTests(WorkflowTestBase):

    def test_staff_can_approve_pending_reservation(self):
        """STAFF can POST to approve a PENDING reservation."""
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse('reservations:approve_reservation', kwargs={'pk': self.reservation.pk})
        )
        self.assertRedirects(response, reverse('reservations:pending_reservations'),
                             fetch_redirect_response=False)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.APPROVED)

    def test_admin_can_approve_pending_reservation(self):
        """ADMIN can POST to approve a PENDING reservation."""
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('reservations:approve_reservation', kwargs={'pk': self.reservation.pk})
        )
        self.assertRedirects(response, reverse('reservations:pending_reservations'),
                             fetch_redirect_response=False)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.APPROVED)

    def test_requester_cannot_approve(self):
        """REQUESTER gets 403 on the approve endpoint."""
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse('reservations:approve_reservation', kwargs={'pk': self.reservation.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_approval_records_reviewed_by(self):
        """Approval records the reviewing staff user."""
        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('reservations:approve_reservation', kwargs={'pk': self.reservation.pk})
        )
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.reviewed_by, self.staff_user)

    def test_approval_records_reviewed_at(self):
        """Approval records the reviewed_at timestamp."""
        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('reservations:approve_reservation', kwargs={'pk': self.reservation.pk})
        )
        self.reservation.refresh_from_db()
        self.assertIsNotNone(self.reservation.reviewed_at)

    def test_get_cannot_approve(self):
        """GET request to approve endpoint returns 405, reservation remains PENDING."""
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse('reservations:approve_reservation', kwargs={'pk': self.reservation.pk})
        )
        self.assertEqual(response.status_code, 405)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.PENDING)

    def test_approve_non_pending_reservation_redirects_with_error(self):
        """Approving an APPROVED reservation (invalid transition) redirects with error message."""
        self.reservation.status = Reservation.Status.APPROVED
        self.reservation.save()
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse('reservations:approve_reservation', kwargs={'pk': self.reservation.pk})
        )
        # Should redirect to detail with error, not crash
        self.assertRedirects(
            response,
            reverse('reservations:reservation_detail', kwargs={'pk': self.reservation.pk}),
            fetch_redirect_response=False,
        )


# ---------------------------------------------------------------------------
# REJECTION TESTS
# ---------------------------------------------------------------------------

class ReservationRejectionTests(WorkflowTestBase):

    def test_staff_can_reject_pending_reservation(self):
        """STAFF can POST to reject a PENDING reservation with a reason."""
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse('reservations:reject_reservation', kwargs={'pk': self.reservation.pk}),
            {'reason': 'Facility reserved for accreditation.'},
        )
        self.assertRedirects(response, reverse('reservations:pending_reservations'),
                             fetch_redirect_response=False)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.REJECTED)

    def test_admin_can_reject_pending_reservation(self):
        """ADMIN can POST to reject a PENDING reservation with a reason."""
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('reservations:reject_reservation', kwargs={'pk': self.reservation.pk}),
            {'reason': 'Admin override required.'},
        )
        self.assertRedirects(response, reverse('reservations:pending_reservations'),
                             fetch_redirect_response=False)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.REJECTED)

    def test_requester_cannot_reject(self):
        """REQUESTER gets 403 on the reject endpoint."""
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse('reservations:reject_reservation', kwargs={'pk': self.reservation.pk}),
            {'reason': 'Trying to reject.'},
        )
        self.assertEqual(response.status_code, 403)

    def test_rejection_reason_required(self):
        """POST without a reason redirects to detail with error, no state change."""
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse('reservations:reject_reservation', kwargs={'pk': self.reservation.pk}),
            {'reason': ''},
        )
        self.assertRedirects(
            response,
            reverse('reservations:reservation_detail', kwargs={'pk': self.reservation.pk}),
            fetch_redirect_response=False,
        )
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.PENDING)


class ReservationReportViewTests(WorkflowTestBase):

    def _create_report_reservation(self, *, reservation_date=None, facility=None, status):
        return Reservation.objects.create(
            requested_by=self.requester,
            facility=facility or self.facility,
            purpose='Report Test Event',
            reservation_date=reservation_date or self.tomorrow,
            start_time=datetime.time(13, 0),
            end_time=datetime.time(15, 0),
            status=status,
        )

    def test_staff_can_access_report(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('reservations:reservation_report'))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_access_report(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('reservations:reservation_report'))
        self.assertEqual(response.status_code, 200)

    def test_requester_gets_forbidden(self):
        self.client.force_login(self.requester)
        response = self.client.get(reverse('reservations:reservation_report'))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_redirects_to_login(self):
        response = self.client.get(reverse('reservations:reservation_report'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_status_filter_and_summary_counts(self):
        approved = self._create_report_reservation(status=Reservation.Status.APPROVED)
        self._create_report_reservation(status=Reservation.Status.REJECTED)
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse('reservations:reservation_report'),
            {'status': Reservation.Status.APPROVED},
        )

        self.assertEqual(list(response.context['reservations']), [approved])
        self.assertEqual(response.context['summary']['total'], 1)
        self.assertEqual(response.context['summary']['approved'], 1)
        self.assertEqual(response.context['summary']['pending'], 0)

    def test_date_filter_limits_report_range(self):
        later = self._create_report_reservation(
            reservation_date=self.day_after,
            status=Reservation.Status.APPROVED,
        )
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse('reservations:reservation_report'),
            {'start_date': self.day_after.isoformat(), 'end_date': self.day_after.isoformat()},
        )

        self.assertEqual(list(response.context['reservations']), [later])

    def test_facility_filter_limits_report(self):
        other_facility = Facility.objects.create(
            facility_type=self.facility.facility_type,
            name='Report Test Room',
            location='Building C',
            capacity=25,
            status=Facility.Status.AVAILABLE,
        )
        matching = self._create_report_reservation(
            facility=other_facility,
            status=Reservation.Status.APPROVED,
        )
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse('reservations:reservation_report'),
            {'facility': other_facility.pk},
        )

        self.assertEqual(list(response.context['reservations']), [matching])

    def test_report_context_and_table_contain_reservation(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse('reservations:reservation_report'))

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.reservation, response.context['reservations'])
        self.assertContains(response, self.facility.name)
        self.assertContains(response, self.requester.username)
        self.assertContains(response, self.reservation.purpose)

    def test_rejection_stores_reviewed_by(self):
        """Rejection stores the reviewing staff user."""
        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('reservations:reject_reservation', kwargs={'pk': self.reservation.pk}),
            {'reason': 'Conflict with institutional activity.'},
        )
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.reviewed_by, self.staff_user)

    def test_rejection_stores_reviewed_at(self):
        """Rejection stores the reviewed_at timestamp."""
        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('reservations:reject_reservation', kwargs={'pk': self.reservation.pk}),
            {'reason': 'Conflict with institutional activity.'},
        )
        self.reservation.refresh_from_db()
        self.assertIsNotNone(self.reservation.reviewed_at)

    def test_rejection_stores_reason(self):
        """Rejection stores the provided reason on the model."""
        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('reservations:reject_reservation', kwargs={'pk': self.reservation.pk}),
            {'reason': 'Specific reason text.'},
        )
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.rejection_reason, 'Specific reason text.')

    def test_get_cannot_reject(self):
        """GET request to reject endpoint returns 405, reservation remains PENDING."""
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse('reservations:reject_reservation', kwargs={'pk': self.reservation.pk})
        )
        self.assertEqual(response.status_code, 405)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.PENDING)

    def test_reject_non_pending_reservation_redirects_with_error(self):
        """Rejecting an already-REJECTED reservation (invalid transition) redirects with error."""
        self.reservation.status = Reservation.Status.REJECTED
        self.reservation.save()
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse('reservations:reject_reservation', kwargs={'pk': self.reservation.pk}),
            {'reason': 'Trying again.'},
        )
        self.assertRedirects(
            response,
            reverse('reservations:reservation_detail', kwargs={'pk': self.reservation.pk}),
            fetch_redirect_response=False,
        )
