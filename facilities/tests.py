from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase

from .models import Facility, FacilityType


class FacilityModelTestCase(TestCase):
    """
    Focused test suite validating FacilityType and Facility models,
    their relationships, constraints, status defaults, and deletion protection.
    """

    def setUp(self):
        self.facility_type = FacilityType.objects.create(
            name='Computer Laboratory',
            description='Rooms equipped with desktop workstations and internet access.',
        )

    def test_facility_type_creation_and_str(self):
        """Verify FacilityType creation and __str__ representation."""
        self.assertEqual(str(self.facility_type), 'Computer Laboratory')
        self.assertEqual(self.facility_type.facilities.count(), 0)

    def test_facility_creation_with_relationship(self):
        """Verify Facility creation and relationship to FacilityType."""
        facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='IT ComLab 1',
            location='IT Building 2nd Floor',
            capacity=40,
        )
        self.assertEqual(facility.facility_type, self.facility_type)
        self.assertEqual(facility.status, Facility.Status.AVAILABLE)
        self.assertTrue(facility.is_operational)
        self.assertIn('IT ComLab 1', str(facility))
        self.assertIn('40', str(facility))

    def test_reverse_relationship_using_related_name(self):
        """Verify reverse querying facilities from FacilityType via related_name='facilities'."""
        f1 = Facility.objects.create(
            facility_type=self.facility_type,
            name='IT ComLab 1',
            location='IT Building 2nd Floor',
            capacity=40,
        )
        f2 = Facility.objects.create(
            facility_type=self.facility_type,
            name='IT ComLab 2',
            location='IT Building 2nd Floor',
            capacity=35,
        )
        related_facilities = self.facility_type.facilities.all()
        self.assertEqual(related_facilities.count(), 2)
        self.assertIn(f1, related_facilities)
        self.assertIn(f2, related_facilities)

    def test_on_delete_protect_prevents_category_deletion_when_facilities_exist(self):
        """Verify models.PROTECT raises ProtectedError when deleting a referenced FacilityType."""
        Facility.objects.create(
            facility_type=self.facility_type,
            name='IT ComLab 1',
            location='IT Building 2nd Floor',
            capacity=40,
        )
        with self.assertRaises(ProtectedError):
            self.facility_type.delete()

    def test_facility_name_must_be_unique(self):
        """Verify duplicate facility name raises IntegrityError at database layer."""
        Facility.objects.create(
            facility_type=self.facility_type,
            name='DSSC Gymnasium',
            location='Main Campus',
            capacity=1000,
        )
        with self.assertRaises(IntegrityError):
            Facility.objects.create(
                facility_type=self.facility_type,
                name='DSSC Gymnasium',
                location='Somewhere Else',
                capacity=500,
            )

    def test_positive_capacity_rule_via_model_validation(self):
        """
        Verify Django model validation (full_clean) rejects capacity <= 0.
        Note: Model.objects.create() does not automatically invoke full_clean(),
        so full_clean() is explicitly called to test validation logic.
        """
        facility_zero = Facility(
            facility_type=self.facility_type,
            name='Invalid Zero Cap Room',
            location='Building A',
            capacity=0,
        )
        with self.assertRaises(ValidationError):
            facility_zero.full_clean()

    def test_positive_capacity_rule_via_database_constraint(self):
        """
        Verify the database CheckConstraint (facility_capacity_gt_zero)
        rejects capacity <= 0 even if full_clean() is bypassed during direct create.
        """
        with self.assertRaises(IntegrityError):
            Facility.objects.create(
                facility_type=self.facility_type,
                name='Direct DB Bypass Zero Room',
                location='Building B',
                capacity=0,
            )
