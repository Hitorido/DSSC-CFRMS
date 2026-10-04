"""
View, form, and RBAC tests for the FacilityMaintenance management workflow.

Covers:
- RBAC: anonymous redirect, REQUESTER 403, STAFF/ADMIN access
- Create view: GET/POST, created_by from session, status not from browser,
  invalid time range, reservation conflict, maintenance overlap
- Detail view: access control
- Complete action: POST-only, lifecycle transition, invalid transition
- Cancel action: POST-only, lifecycle transition, invalid transition
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from facilities.models import Facility, FacilityMaintenance, FacilityType
from reservations.models import Reservation

User = get_user_model()


class MaintenanceViewTestBase(TestCase):
    """
    Shared fixtures for all maintenance view tests.
    """

    def setUp(self):
        self.client = Client()

        self.requester = User.objects.create_user(
            username='view_requester',
            password='testpass123',
            email='vr@dssc.edu.ph',
            role=User.Role.REQUESTER,
        )
        self.staff_user = User.objects.create_user(
            username='view_staff',
            password='testpass123',
            email='vs@dssc.edu.ph',
            role=User.Role.STAFF,
        )
        self.admin_user = User.objects.create_user(
            username='view_admin',
            password='testpass123',
            email='va@dssc.edu.ph',
            role=User.Role.ADMIN,
        )

        facility_type = FacilityType.objects.create(name='View Test Lab')
        self.facility = Facility.objects.create(
            facility_type=facility_type,
            name='View Test Room',
            location='Building T',
            capacity=25,
            status=Facility.Status.AVAILABLE,
        )

        self.tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        self.day_after = timezone.localdate() + datetime.timedelta(days=2)

        # A baseline SCHEDULED maintenance: tomorrow 10:00–12:00
        self.maintenance = FacilityMaintenance.objects.create(
            facility=self.facility,
            title='Baseline View Maintenance',
            maintenance_date=self.tomorrow,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
            created_by=self.staff_user,
        )

    def _valid_post_data(self, date=None):
        """Return valid POST data for creating a non-conflicting maintenance record."""
        return {
            'facility': self.facility.pk,
            'title': 'New Inspection',
            'description': 'Test description',
            'maintenance_date': (date or self.day_after).isoformat(),
            'start_time': '09:00',
            'end_time': '11:00',
        }


# ---------------------------------------------------------------------------
# RBAC — LIST VIEW
# ---------------------------------------------------------------------------

class MaintenanceListRBACTests(MaintenanceViewTestBase):

    def test_anonymous_redirected_to_login(self):
        """Anonymous user accessing maintenance list is redirected to login."""
        response = self.client.get(reverse('facilities:maintenance_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_requester_gets_403(self):
        """REQUESTER gets HTTP 403 on the maintenance list."""
        self.client.force_login(self.requester)
        response = self.client.get(reverse('facilities:maintenance_list'))
        self.assertEqual(response.status_code, 403)

    def test_staff_can_access_list(self):
        """STAFF can access the maintenance list."""
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('facilities:maintenance_list'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('maintenance_records', response.context)

    def test_admin_can_access_list(self):
        """ADMIN can access the maintenance list."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('facilities:maintenance_list'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('maintenance_records', response.context)

    def test_list_contains_maintenance_record(self):
        """The list context includes the baseline maintenance record."""
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('facilities:maintenance_list'))
        self.assertIn(self.maintenance, response.context['maintenance_records'])


# ---------------------------------------------------------------------------
# RBAC — CREATE VIEW
# ---------------------------------------------------------------------------

class MaintenanceCreateRBACTests(MaintenanceViewTestBase):

    def test_anonymous_redirected_on_create_get(self):
        """Anonymous user accessing create form is redirected to login."""
        response = self.client.get(reverse('facilities:maintenance_create'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_requester_gets_403_on_create(self):
        """REQUESTER gets 403 on GET to the create view."""
        self.client.force_login(self.requester)
        response = self.client.get(reverse('facilities:maintenance_create'))
        self.assertEqual(response.status_code, 403)

    def test_requester_gets_403_on_create_post(self):
        """REQUESTER gets 403 on POST to the create view."""
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse('facilities:maintenance_create'),
            self._valid_post_data(),
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_can_get_create_form(self):
        """STAFF can access the create form (GET)."""
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('facilities:maintenance_create'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)

    def test_admin_can_get_create_form(self):
        """ADMIN can access the create form (GET)."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('facilities:maintenance_create'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)


# ---------------------------------------------------------------------------
# CREATE — Valid submissions
# ---------------------------------------------------------------------------

class MaintenanceCreateValidTests(MaintenanceViewTestBase):

    def test_staff_can_create_maintenance(self):
        """STAFF can POST valid data and create a SCHEDULED maintenance record."""
        self.client.force_login(self.staff_user)
        count_before = FacilityMaintenance.objects.count()
        response = self.client.post(
            reverse('facilities:maintenance_create'),
            self._valid_post_data(),
        )
        self.assertEqual(FacilityMaintenance.objects.count(), count_before + 1)
        new_m = FacilityMaintenance.objects.filter(title='New Inspection').first()
        self.assertIsNotNone(new_m)
        self.assertEqual(new_m.status, FacilityMaintenance.Status.SCHEDULED)

    def test_admin_can_create_maintenance(self):
        """ADMIN can POST valid data and create a maintenance record."""
        self.client.force_login(self.admin_user)
        count_before = FacilityMaintenance.objects.count()
        self.client.post(
            reverse('facilities:maintenance_create'),
            self._valid_post_data(),
        )
        self.assertEqual(FacilityMaintenance.objects.count(), count_before + 1)

    def test_created_by_comes_from_request_user_not_post_data(self):
        """
        created_by must be set from request.user (session), never from POST data.
        The form excludes created_by, so any forged value in POST is ignored.
        """
        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('facilities:maintenance_create'),
            {
                **self._valid_post_data(),
                'created_by': self.admin_user.pk,   # forged — must be ignored
            },
        )
        new_m = FacilityMaintenance.objects.filter(title='New Inspection').first()
        self.assertIsNotNone(new_m)
        self.assertEqual(new_m.created_by, self.staff_user)   # session user, not forged pk

    def test_browser_cannot_spoof_status(self):
        """
        status is not a form field; a browser-submitted status value must be ignored.
        New records must always start as SCHEDULED regardless of what POST contains.
        """
        self.client.force_login(self.staff_user)
        self.client.post(
            reverse('facilities:maintenance_create'),
            {
                **self._valid_post_data(),
                'status': 'COMPLETED',   # spoofed — must be ignored
            },
        )
        new_m = FacilityMaintenance.objects.filter(title='New Inspection').first()
        self.assertIsNotNone(new_m)
        self.assertEqual(new_m.status, FacilityMaintenance.Status.SCHEDULED)

    def test_successful_create_redirects_to_detail(self):
        """Successful POST redirects to the new maintenance record's detail page."""
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse('facilities:maintenance_create'),
            self._valid_post_data(),
        )
        new_m = FacilityMaintenance.objects.filter(title='New Inspection').first()
        self.assertRedirects(
            response,
            reverse('facilities:maintenance_detail', kwargs={'pk': new_m.pk}),
            fetch_redirect_response=False,
        )


# ---------------------------------------------------------------------------
# CREATE — Validation failures
# ---------------------------------------------------------------------------

class MaintenanceCreateValidationTests(MaintenanceViewTestBase):

    def test_invalid_time_range_shown_as_form_error(self):
        """end_time <= start_time returns form with error, no record created."""
        self.client.force_login(self.staff_user)
        count_before = FacilityMaintenance.objects.count()
        response = self.client.post(
            reverse('facilities:maintenance_create'),
            {
                'facility': self.facility.pk,
                'title': 'Bad Times',
                'maintenance_date': self.day_after.isoformat(),
                'start_time': '14:00',
                'end_time': '13:00',   # before start
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(FacilityMaintenance.objects.count(), count_before)
        # end_time error should appear in form
        self.assertTrue(response.context['form'].errors)

    def test_overlapping_maintenance_shown_as_form_error(self):
        """
        Scheduling maintenance that overlaps self.maintenance (tomorrow 10:00–12:00)
        must return the form with a non-field error, no record created.
        """
        self.client.force_login(self.staff_user)
        count_before = FacilityMaintenance.objects.count()
        response = self.client.post(
            reverse('facilities:maintenance_create'),
            {
                'facility': self.facility.pk,
                'title': 'Overlapping Maintenance',
                'maintenance_date': self.tomorrow.isoformat(),
                'start_time': '11:00',   # overlaps 10:00–12:00
                'end_time': '13:00',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(FacilityMaintenance.objects.count(), count_before)
        self.assertTrue(response.context['form'].non_field_errors())

    def test_reservation_conflict_shown_as_form_error(self):
        """
        Scheduling maintenance that conflicts with an existing PENDING reservation
        must return the form with a non-field error, no record created.
        """
        Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Existing booking',
            reservation_date=self.day_after,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )

        self.client.force_login(self.staff_user)
        count_before = FacilityMaintenance.objects.count()
        response = self.client.post(
            reverse('facilities:maintenance_create'),
            {
                'facility': self.facility.pk,
                'title': 'Conflicts with reservation',
                'maintenance_date': self.day_after.isoformat(),
                'start_time': '10:00',   # overlaps 09:00–11:00
                'end_time': '12:00',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(FacilityMaintenance.objects.count(), count_before)
        self.assertTrue(response.context['form'].non_field_errors())


# ---------------------------------------------------------------------------
# DETAIL VIEW
# ---------------------------------------------------------------------------

class MaintenanceDetailRBACTests(MaintenanceViewTestBase):

    def test_anonymous_redirected_on_detail(self):
        """Anonymous user is redirected to login on detail view."""
        response = self.client.get(
            reverse('facilities:maintenance_detail', kwargs={'pk': self.maintenance.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_requester_gets_403_on_detail(self):
        """REQUESTER gets 403 on the maintenance detail view."""
        self.client.force_login(self.requester)
        response = self.client.get(
            reverse('facilities:maintenance_detail', kwargs={'pk': self.maintenance.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_can_view_detail(self):
        """STAFF can access the maintenance detail view."""
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse('facilities:maintenance_detail', kwargs={'pk': self.maintenance.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['maintenance'], self.maintenance)

    def test_admin_can_view_detail(self):
        """ADMIN can access the maintenance detail view."""
        self.client.force_login(self.admin_user)
        response = self.client.get(
            reverse('facilities:maintenance_detail', kwargs={'pk': self.maintenance.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_nonexistent_maintenance_returns_404(self):
        """Accessing a non-existent pk returns 404."""
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse('facilities:maintenance_detail', kwargs={'pk': 99999})
        )
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# COMPLETE ACTION
# ---------------------------------------------------------------------------

class MaintenanceCompleteTests(MaintenanceViewTestBase):

    def test_complete_requires_post(self):
        """GET to the complete endpoint returns 405 and does not change status."""
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse('facilities:maintenance_complete', kwargs={'pk': self.maintenance.pk})
        )
        self.assertEqual(response.status_code, 405)
        self.maintenance.refresh_from_db()
        self.assertEqual(self.maintenance.status, FacilityMaintenance.Status.SCHEDULED)

    def test_requester_gets_403_on_complete(self):
        """REQUESTER gets 403 on the complete endpoint."""
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse('facilities:maintenance_complete', kwargs={'pk': self.maintenance.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_can_complete_scheduled_maintenance(self):
        """STAFF can POST to mark SCHEDULED maintenance as COMPLETED."""
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse('facilities:maintenance_complete', kwargs={'pk': self.maintenance.pk})
        )
        self.assertRedirects(
            response,
            reverse('facilities:maintenance_detail', kwargs={'pk': self.maintenance.pk}),
            fetch_redirect_response=False,
        )
        self.maintenance.refresh_from_db()
        self.assertEqual(self.maintenance.status, FacilityMaintenance.Status.COMPLETED)

    def test_admin_can_complete_scheduled_maintenance(self):
        """ADMIN can POST to mark SCHEDULED maintenance as COMPLETED."""
        self.client.force_login(self.admin_user)
        self.client.post(
            reverse('facilities:maintenance_complete', kwargs={'pk': self.maintenance.pk})
        )
        self.maintenance.refresh_from_db()
        self.assertEqual(self.maintenance.status, FacilityMaintenance.Status.COMPLETED)

    def test_complete_already_completed_handled_safely(self):
        """
        Attempting to complete an already COMPLETED record is an invalid
        lifecycle transition. The view must catch the ValidationError,
        show an error message, and redirect without crashing.
        """
        self.maintenance.complete()
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse('facilities:maintenance_complete', kwargs={'pk': self.maintenance.pk})
        )
        # Must redirect to detail, not 500
        self.assertRedirects(
            response,
            reverse('facilities:maintenance_detail', kwargs={'pk': self.maintenance.pk}),
            fetch_redirect_response=False,
        )
        # Status unchanged
        self.maintenance.refresh_from_db()
        self.assertEqual(self.maintenance.status, FacilityMaintenance.Status.COMPLETED)

    def test_complete_cancelled_maintenance_handled_safely(self):
        """
        Attempting to complete a CANCELLED record is an invalid transition.
        Must handle gracefully.
        """
        self.maintenance.cancel()
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse('facilities:maintenance_complete', kwargs={'pk': self.maintenance.pk})
        )
        self.assertRedirects(
            response,
            reverse('facilities:maintenance_detail', kwargs={'pk': self.maintenance.pk}),
            fetch_redirect_response=False,
        )
        self.maintenance.refresh_from_db()
        self.assertEqual(self.maintenance.status, FacilityMaintenance.Status.CANCELLED)


# ---------------------------------------------------------------------------
# CANCEL ACTION
# ---------------------------------------------------------------------------

class MaintenanceCancelTests(MaintenanceViewTestBase):

    def test_cancel_requires_post(self):
        """GET to the cancel endpoint returns 405 and does not change status."""
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse('facilities:maintenance_cancel', kwargs={'pk': self.maintenance.pk})
        )
        self.assertEqual(response.status_code, 405)
        self.maintenance.refresh_from_db()
        self.assertEqual(self.maintenance.status, FacilityMaintenance.Status.SCHEDULED)

    def test_requester_gets_403_on_cancel(self):
        """REQUESTER gets 403 on the cancel endpoint."""
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse('facilities:maintenance_cancel', kwargs={'pk': self.maintenance.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_can_cancel_scheduled_maintenance(self):
        """STAFF can POST to cancel a SCHEDULED maintenance window."""
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse('facilities:maintenance_cancel', kwargs={'pk': self.maintenance.pk})
        )
        self.assertRedirects(
            response,
            reverse('facilities:maintenance_list'),
            fetch_redirect_response=False,
        )
        self.maintenance.refresh_from_db()
        self.assertEqual(self.maintenance.status, FacilityMaintenance.Status.CANCELLED)

    def test_admin_can_cancel_scheduled_maintenance(self):
        """ADMIN can POST to cancel a SCHEDULED maintenance window."""
        self.client.force_login(self.admin_user)
        self.client.post(
            reverse('facilities:maintenance_cancel', kwargs={'pk': self.maintenance.pk})
        )
        self.maintenance.refresh_from_db()
        self.assertEqual(self.maintenance.status, FacilityMaintenance.Status.CANCELLED)

    def test_cancel_already_cancelled_handled_safely(self):
        """
        Attempting to cancel an already CANCELLED record is an invalid transition.
        Must redirect to detail with error message, not crash.
        """
        self.maintenance.cancel()
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse('facilities:maintenance_cancel', kwargs={'pk': self.maintenance.pk})
        )
        self.assertRedirects(
            response,
            reverse('facilities:maintenance_detail', kwargs={'pk': self.maintenance.pk}),
            fetch_redirect_response=False,
        )
        self.maintenance.refresh_from_db()
        self.assertEqual(self.maintenance.status, FacilityMaintenance.Status.CANCELLED)

    def test_cancel_completed_maintenance_handled_safely(self):
        """
        Attempting to cancel a COMPLETED record is an invalid transition.
        Must handle gracefully.
        """
        self.maintenance.complete()
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse('facilities:maintenance_cancel', kwargs={'pk': self.maintenance.pk})
        )
        self.assertRedirects(
            response,
            reverse('facilities:maintenance_detail', kwargs={'pk': self.maintenance.pk}),
            fetch_redirect_response=False,
        )
        self.maintenance.refresh_from_db()
        self.assertEqual(self.maintenance.status, FacilityMaintenance.Status.COMPLETED)
