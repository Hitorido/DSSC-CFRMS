from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Facility, FacilityType


User = get_user_model()


class FacilitySearchFilterTests(TestCase):
    def setUp(self):
        self.requester = User.objects.create_user(
            username='facility_filter_requester',
            password='testpass123',
            role=User.Role.REQUESTER,
        )
        self.client.force_login(self.requester)
        computer_lab = FacilityType.objects.create(name='Computer Laboratory')
        auditorium = FacilityType.objects.create(name='Auditorium')
        self.computer_facility = Facility.objects.create(
            facility_type=computer_lab,
            name='IT Laboratory East',
            location='North Campus',
            capacity=30,
        )
        self.auditorium = Facility.objects.create(
            facility_type=auditorium,
            name='Main Hall',
            location='South Campus',
            capacity=200,
            status=Facility.Status.MAINTENANCE,
        )

    def test_search_returns_matches_and_excludes_unrelated_facilities(self):
        response = self.client.get(reverse('facilities:facility_list'), {'search': 'computer'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['facilities']), [self.computer_facility])

    def test_status_filter_returns_only_selected_status(self):
        response = self.client.get(
            reverse('facilities:facility_list'),
            {'status': Facility.Status.MAINTENANCE},
        )

        self.assertEqual(list(response.context['facilities']), [self.auditorium])

    def test_empty_search_returns_facilities_without_error(self):
        response = self.client.get(reverse('facilities:facility_list'), {'search': ''})

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(
            response.context['facilities'],
            [self.computer_facility, self.auditorium],
        )