import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from facilities.models import Facility, FacilityType
from .models import Reservation


User = get_user_model()


class MyReservationFilterTests(TestCase):
    def setUp(self):
        self.requester = User.objects.create_user(
            username='reservation_filter_requester',
            password='testpass123',
            role=User.Role.REQUESTER,
        )
        self.other_requester = User.objects.create_user(
            username='reservation_filter_other',
            password='testpass123',
            role=User.Role.REQUESTER,
        )
        self.client.force_login(self.requester)
        facility_type = FacilityType.objects.create(name='Filter Test Room')
        self.facility = Facility.objects.create(
            facility_type=facility_type,
            name='Filter Test Facility',
            location='Main Campus',
            capacity=25,
        )
        reservation_date = timezone.localdate() + datetime.timedelta(days=1)
        self.own_rejected = self._create_reservation(
            self.requester,
            reservation_date,
            Reservation.Status.REJECTED,
        )
        self.other_rejected = self._create_reservation(
            self.other_requester,
            reservation_date + datetime.timedelta(days=1),
            Reservation.Status.REJECTED,
        )
        self.own_pending = self._create_reservation(
            self.requester,
            reservation_date + datetime.timedelta(days=2),
            Reservation.Status.PENDING,
        )

    def _create_reservation(self, requester, date, status):
        return Reservation.objects.create(
            requested_by=requester,
            facility=self.facility,
            purpose='Filter test reservation',
            reservation_date=date,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status=status,
        )

    def test_status_filter_stays_within_requesters_own_reservations(self):
        response = self.client.get(
            reverse('reservations:my_reservations'),
            {'status': Reservation.Status.REJECTED},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['reservations']), [self.own_rejected])
        self.assertNotIn(self.other_rejected, response.context['reservations'])
        self.assertNotIn(self.own_pending, response.context['reservations'])