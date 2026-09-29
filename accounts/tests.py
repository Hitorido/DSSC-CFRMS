import datetime
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from facilities.models import Facility, FacilityType
from reservations.models import Reservation

User = get_user_model()


class AuthAndRBACTestCase(TestCase):
    """
    Tests for CFRMS authentication (login/logout) and
    role-based access control (REQUESTER, STAFF, ADMIN).
    """

    def setUp(self):
        self.client = Client()

        self.requester = User.objects.create_user(
            username='requester1',
            email='requester1@dssc.edu.ph',
            password='testpassword123',
            role=User.Role.REQUESTER,
        )
        self.requester2 = User.objects.create_user(
            username='requester2',
            email='requester2@dssc.edu.ph',
            password='testpassword123',
            role=User.Role.REQUESTER,
        )
        self.staff_user = User.objects.create_user(
            username='staff1',
            email='staff1@dssc.edu.ph',
            password='testpassword123',
            role=User.Role.STAFF,
            # Django's is_staff flag is FALSE — they can log in to CFRMS
            # as a STAFF role but cannot access Django Admin
        )
        self.admin_user = User.objects.create_user(
            username='admin1',
            email='admin1@dssc.edu.ph',
            password='testpassword123',
            role=User.Role.ADMIN,
        )
        # A user with Django is_staff=True but CFRMS role=REQUESTER
        # Should NOT gain CFRMS STAFF authorization
        self.django_staff_only = User.objects.create_user(
            username='django_staff_only',
            email='djangostaff@dssc.edu.ph',
            password='testpassword123',
            role=User.Role.REQUESTER,
            is_staff=True,  # Django Admin access only, NOT CFRMS STAFF
        )

        # Create facility and reservations for queryset tests
        facility_type = FacilityType.objects.create(name='Lecture Hall')
        self.facility = Facility.objects.create(
            facility_type=facility_type,
            name='Lecture Hall 101',
            location='Building A',
            capacity=80,
            status=Facility.Status.AVAILABLE,
        )
        self.tomorrow = timezone.localdate() + datetime.timedelta(days=1)

        # Create a reservation owned by requester1
        self.requester1_reservation = Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Requester 1 Test Event',
            reservation_date=self.tomorrow,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )

    # -------------------------------------------------------------------
    # AUTHENTICATION TESTS
    # -------------------------------------------------------------------

    def test_anonymous_user_accessing_home_redirects_to_login(self):
        """Anonymous users must be redirected to login when accessing protected pages."""
        response = self.client.get(reverse('home'))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next=/", fetch_redirect_response=False)

    def test_anonymous_user_accessing_facilities_redirects_to_login(self):
        """Anonymous access to facilities list must redirect to login."""
        response = self.client.get(reverse('facilities:facility_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_valid_user_can_login(self):
        """A valid username/password should produce a successful login and redirect."""
        response = self.client.post(
            reverse('accounts:login'),
            {'username': 'requester1', 'password': 'testpassword123'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)

    def test_invalid_credentials_fail_login(self):
        """Invalid credentials must not authenticate the user."""
        response = self.client.post(
            reverse('accounts:login'),
            {'username': 'requester1', 'password': 'WRONGPASSWORD'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['user'].is_authenticated)

    def test_logout_ends_authenticated_session(self):
        """After logging out, the session must be invalidated."""
        self.client.login(username='requester1', password='testpassword123')
        self.client.post(reverse('accounts:logout'))
        # After logout, protected page should redirect to login
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    # -------------------------------------------------------------------
    # REQUESTER ACCESS TESTS
    # -------------------------------------------------------------------

    def test_requester_can_access_home(self):
        """An authenticated REQUESTER can access the home view."""
        self.client.login(username='requester1', password='testpassword123')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_requester_can_access_facilities(self):
        """An authenticated REQUESTER can view the facility list."""
        self.client.login(username='requester1', password='testpassword123')
        response = self.client.get(reverse('facilities:facility_list'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('facilities', response.context)

    def test_requester_can_access_own_reservations(self):
        """A REQUESTER can access their own reservations view."""
        self.client.login(username='requester1', password='testpassword123')
        response = self.client.get(reverse('reservations:my_reservations'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('reservations', response.context)

    def test_my_reservations_queryset_only_returns_own_records(self):
        """
        The my_reservations QuerySet must ONLY return the logged-in user's reservations.
        Creates a reservation for requester2 and verifies requester1 cannot see it.
        """
        # Create reservation owned by requester2
        Reservation.objects.create(
            requested_by=self.requester2,
            facility=self.facility,
            purpose='Requester 2 Test Event',
            reservation_date=self.tomorrow + datetime.timedelta(days=1),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )

        self.client.login(username='requester1', password='testpassword123')
        response = self.client.get(reverse('reservations:my_reservations'))

        qs = response.context['reservations']
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().requested_by, self.requester)

    def test_requester_cannot_access_pending_approval_page(self):
        """A REQUESTER must receive HTTP 403 when accessing the staff pending view."""
        self.client.login(username='requester1', password='testpassword123')
        response = self.client.get(reverse('reservations:pending_reservations'))
        self.assertEqual(response.status_code, 403)

    # -------------------------------------------------------------------
    # STAFF ACCESS TESTS
    # -------------------------------------------------------------------

    def test_staff_can_access_home(self):
        """An authenticated STAFF can access the home view."""
        self.client.login(username='staff1', password='testpassword123')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_staff_can_access_facilities(self):
        """An authenticated STAFF can view the facility list."""
        self.client.login(username='staff1', password='testpassword123')
        response = self.client.get(reverse('facilities:facility_list'))
        self.assertEqual(response.status_code, 200)

    def test_staff_can_access_pending_reservations(self):
        """An authenticated STAFF can access the pending reservations view."""
        self.client.login(username='staff1', password='testpassword123')
        response = self.client.get(reverse('reservations:pending_reservations'))
        self.assertEqual(response.status_code, 200)

    def test_pending_view_only_returns_pending_status(self):
        """The pending_reservations view QuerySet must only contain PENDING reservations."""
        # Approve the existing reservation so it is no longer PENDING
        self.requester1_reservation.status = Reservation.Status.APPROVED
        self.requester1_reservation.save()

        # Create a new PENDING reservation
        Reservation.objects.create(
            requested_by=self.requester2,
            facility=self.facility,
            purpose='Still Pending Event',
            reservation_date=self.tomorrow + datetime.timedelta(days=2),
            start_time=datetime.time(14, 0),
            end_time=datetime.time(16, 0),
        )

        self.client.login(username='staff1', password='testpassword123')
        response = self.client.get(reverse('reservations:pending_reservations'))
        qs = response.context['reservations']

        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().status, Reservation.Status.PENDING)

    # -------------------------------------------------------------------
    # ADMIN ACCESS TESTS
    # -------------------------------------------------------------------

    def test_admin_can_access_home(self):
        """An authenticated ADMIN can access the home view."""
        self.client.login(username='admin1', password='testpassword123')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_access_facilities(self):
        """An authenticated ADMIN can view the facility list."""
        self.client.login(username='admin1', password='testpassword123')
        response = self.client.get(reverse('facilities:facility_list'))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_access_pending_reservations(self):
        """An authenticated ADMIN can access the pending reservations view."""
        self.client.login(username='admin1', password='testpassword123')
        response = self.client.get(reverse('reservations:pending_reservations'))
        self.assertEqual(response.status_code, 200)

    # -------------------------------------------------------------------
    # AUTHORIZATION SECURITY TESTS
    # -------------------------------------------------------------------

    def test_authenticated_unauthorized_access_returns_403(self):
        """
        An authenticated REQUESTER accessing a STAFF/ADMIN page must receive
        HTTP 403 Forbidden, not 404 or a silent redirect.
        """
        self.client.login(username='requester1', password='testpassword123')
        response = self.client.get(reverse('reservations:pending_reservations'))
        self.assertEqual(response.status_code, 403)

    def test_django_is_staff_flag_alone_does_not_grant_cfrms_staff_authorization(self):
        """
        CRITICAL: A user with Django is_staff=True but CFRMS role=REQUESTER
        must NOT gain access to CFRMS STAFF-only views.
        Django's is_staff controls Django Admin access only.
        CFRMS authorization is governed exclusively by the 'role' field.
        """
        self.assertTrue(self.django_staff_only.is_staff)           # Django Admin: YES
        self.assertEqual(self.django_staff_only.role, User.Role.REQUESTER)  # CFRMS role: REQUESTER
        self.assertFalse(self.django_staff_only.is_staff_role)     # CFRMS STAFF check: NO

        self.client.login(username='django_staff_only', password='testpassword123')
        response = self.client.get(reverse('reservations:pending_reservations'))
        self.assertEqual(response.status_code, 403)


class DashboardKPITestCase(TestCase):
    """
    Unit tests for basic dashboard KPI counts (Member 5).
    Verifies total facilities, total reservations, pending, approved, today's count,
    role-based scoping for requesters vs staff/admin, and anonymous redirection.
    """

    def setUp(self):
        self.client = Client()

        self.requester1 = User.objects.create_user(
            username='kpi_requester1',
            password='password123',
            role=User.Role.REQUESTER,
        )
        self.requester2 = User.objects.create_user(
            username='kpi_requester2',
            password='password123',
            role=User.Role.REQUESTER,
        )
        self.staff_user = User.objects.create_user(
            username='kpi_staff',
            password='password123',
            role=User.Role.STAFF,
        )
        self.admin_user = User.objects.create_user(
            username='kpi_admin',
            password='password123',
            role=User.Role.ADMIN,
        )

        facility_type = FacilityType.objects.create(name='KPI Lab')
        self.facility1 = Facility.objects.create(
            facility_type=facility_type,
            name='KPI Room 1',
            location='Floor 1',
            capacity=30,
            status=Facility.Status.AVAILABLE,
        )
        self.facility2 = Facility.objects.create(
            facility_type=facility_type,
            name='KPI Room 2',
            location='Floor 2',
            capacity=50,
            status=Facility.Status.AVAILABLE,
        )

        self.today = timezone.localdate()
        self.tomorrow = self.today + datetime.timedelta(days=1)

        # Requester 1 reservations:
        # 1. PENDING today (10:00 - 11:00)
        self.r1_pending_today = Reservation.objects.create(
            requested_by=self.requester1,
            facility=self.facility1,
            purpose='Req1 Today Pending',
            reservation_date=self.today,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(11, 0),
            status=Reservation.Status.PENDING,
        )
        # 2. APPROVED tomorrow (09:00 - 10:00)
        self.r1_approved_tomorrow = Reservation.objects.create(
            requested_by=self.requester1,
            facility=self.facility1,
            purpose='Req1 Tomorrow Approved',
            reservation_date=self.tomorrow,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=Reservation.Status.APPROVED,
        )

        # Requester 2 reservations:
        # 1. APPROVED today (14:00 - 15:00)
        self.r2_approved_today = Reservation.objects.create(
            requested_by=self.requester2,
            facility=self.facility2,
            purpose='Req2 Today Approved',
            reservation_date=self.today,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(15, 0),
            status=Reservation.Status.APPROVED,
        )

    def test_anonymous_user_redirected(self):
        """Anonymous user must be redirected to login page when accessing home."""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_requester_kpi_counts_own_records_only(self):
        """Requester sees total facilities, but reservation KPIs count only their own records."""
        self.client.login(username='kpi_requester1', password='password123')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

        # Context assertions
        self.assertEqual(response.context['total_facilities'], 2)
        self.assertEqual(response.context['total_reservations'], 2)
        self.assertEqual(response.context['pending_reservations'], 1)
        self.assertEqual(response.context['approved_reservations'], 1)
        self.assertEqual(response.context['todays_reservations'], 1)

        # Template HTML rendering assertion
        self.assertContains(response, 'Total Facilities')
        self.assertContains(response, 'Total Reservations')

    def test_staff_kpi_counts_system_wide(self):
        """Staff sees system-wide reservation KPIs across all requesters."""
        self.client.login(username='kpi_staff', password='password123')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['total_facilities'], 2)
        self.assertEqual(response.context['total_reservations'], 3)
        self.assertEqual(response.context['pending_reservations'], 1)
        self.assertEqual(response.context['approved_reservations'], 2)
        self.assertEqual(response.context['todays_reservations'], 2)

    def test_admin_kpi_counts_system_wide(self):
        """Admin sees system-wide reservation KPIs across all requesters."""
        self.client.login(username='kpi_admin', password='password123')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['total_facilities'], 2)
        self.assertEqual(response.context['total_reservations'], 3)
        self.assertEqual(response.context['pending_reservations'], 1)
        self.assertEqual(response.context['approved_reservations'], 2)
        self.assertEqual(response.context['todays_reservations'], 2)

