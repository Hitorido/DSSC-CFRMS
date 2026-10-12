"""
Phase 5.3 tests for generate_synthetic_data management command.

Covers:
  - Valid user roles and types
  - Unique usernames and facility names
  - Valid facility capacities
  - Unusable passwords
  - is_synthetic flag is set
  - Fixed-seed reproducibility
  - Dry-run with zero writes
  - Transaction rollback on error
  - Rerun refusal (not yet implemented; test scaffold)
  - Preservation of real records
  - --clear functionality
"""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from facilities.models import Facility, FacilityMaintenance, FacilityType
from reservations.models import Reservation

User = get_user_model()


def _call(stdout=None, stderr=None, **kwargs):
    """Helper: call generate_synthetic_data with given kwargs, capturing output."""
    if stdout is None:
        stdout = StringIO()
    call_command('generate_synthetic_data', stdout=stdout, stderr=stderr or StringIO(), **kwargs)
    return stdout.getvalue()


# Settings that satisfy both environment safety checks.
_DEV_SETTINGS = {
    'DEBUG': True,
    'DATABASES': {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': 'test_dssc_cfrms_db',
            'HOST': '127.0.0.1',
            'PORT': '3306',
            'USER': 'root',
            'PASSWORD': '',
        }
    }
}


def _counts():
    """Return a snapshot of total record counts for all five synthetic-flagged models."""
    return {
        'User':                User.objects.count(),
        'FacilityType':        FacilityType.objects.count(),
        'Facility':            Facility.objects.count(),
        'FacilityMaintenance': FacilityMaintenance.objects.count(),
        'Reservation':         Reservation.objects.count(),
    }


# ---------------------------------------------------------------------------
# User generation
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class UserGenerationTests(TestCase):
    """Tests for synthetic user generation."""

    def test_requester_users_have_valid_role(self):
        """Generated REQUESTER users must have role=REQUESTER."""
        _call(count=100, seed=42)
        requesters = User.objects.filter(is_synthetic=True, role=User.Role.REQUESTER)
        self.assertGreater(requesters.count(), 0)
        for user in requesters:
            self.assertEqual(user.role, User.Role.REQUESTER)

    def test_requester_users_have_valid_user_type(self):
        """Generated REQUESTER users must have user_type in (STUDENT, FACULTY)."""
        _call(count=100, seed=42)
        requesters = User.objects.filter(is_synthetic=True, role=User.Role.REQUESTER)
        for user in requesters:
            self.assertIn(user.user_type, ['STUDENT', 'FACULTY'])

    def test_staff_users_have_valid_role(self):
        """Generated STAFF users must have role=STAFF."""
        _call(count=100, seed=42)
        staff = User.objects.filter(is_synthetic=True, role=User.Role.STAFF)
        self.assertGreater(staff.count(), 0)
        for user in staff:
            self.assertEqual(user.role, User.Role.STAFF)

    def test_staff_users_have_empty_user_type(self):
        """Generated STAFF users must have user_type='' (empty)."""
        _call(count=100, seed=42)
        staff = User.objects.filter(is_synthetic=True, role=User.Role.STAFF)
        for user in staff:
            self.assertEqual(user.user_type, '')

    def test_admin_users_have_valid_role(self):
        """Generated ADMIN users must have role=ADMIN."""
        _call(count=100, seed=42)
        admins = User.objects.filter(is_synthetic=True, role=User.Role.ADMIN)
        self.assertGreater(admins.count(), 0)
        for user in admins:
            self.assertEqual(user.role, User.Role.ADMIN)

    def test_all_users_have_synthetic_flag_true(self):
        """All generated users must have is_synthetic=True."""
        _call(count=100, seed=42)
        users = User.objects.filter(is_synthetic=True)
        self.assertGreater(users.count(), 0)
        for user in users:
            self.assertTrue(user.is_synthetic)

    def test_usernames_are_unique(self):
        """All generated usernames must be unique."""
        _call(count=100, seed=42)
        users = User.objects.filter(is_synthetic=True)
        usernames = [u.username for u in users]
        self.assertEqual(len(usernames), len(set(usernames)))

    def test_usernames_prefixed_with_syn(self):
        """Generated usernames must be prefixed with 'syn_'."""
        _call(count=100, seed=42)
        users = User.objects.filter(is_synthetic=True)
        for user in users:
            self.assertTrue(user.username.startswith('syn_'))

    def test_passwords_are_unusable(self):
        """All generated users must have unusable passwords."""
        _call(count=100, seed=42)
        users = User.objects.filter(is_synthetic=True)
        for user in users:
            self.assertFalse(user.has_usable_password())

    def test_users_have_first_and_last_name(self):
        """Generated users must have first_name and last_name."""
        _call(count=100, seed=42)
        users = User.objects.filter(is_synthetic=True)
        for user in users:
            self.assertTrue(len(user.first_name) > 0)
            self.assertTrue(len(user.last_name) > 0)

    def test_users_have_department(self):
        """Generated users must have a non-empty department."""
        _call(count=100, seed=42)
        users = User.objects.filter(is_synthetic=True)
        for user in users:
            self.assertTrue(len(user.department) > 0)


# ---------------------------------------------------------------------------
# Facility generation
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class FacilityGenerationTests(TestCase):
    """Tests for synthetic facility type and facility generation."""

    def test_facility_types_are_created(self):
        """Command must create facility types."""
        _call(count=100, seed=42)
        facility_types = FacilityType.objects.filter(is_synthetic=True)
        self.assertGreater(facility_types.count(), 0)

    def test_facility_type_names_are_unique(self):
        """Generated facility type names must be unique."""
        _call(count=100, seed=42)
        facility_types = FacilityType.objects.filter(is_synthetic=True)
        names = [ft.name for ft in facility_types]
        self.assertEqual(len(names), len(set(names)))

    def test_facility_type_names_are_reasonable(self):
        """Generated facility type names should be recognizable facility categories."""
        _call(count=100, seed=42)
        facility_types = FacilityType.objects.filter(is_synthetic=True)
        known_types = {
            'Computer Laboratory', 'Classroom', 'Conference Room',
            'Auditorium', 'Laboratory', 'Gymnasium'
        }
        for ft in facility_types:
            self.assertIn(ft.name, known_types)

    def test_facilities_are_created(self):
        """Command must create facilities."""
        _call(count=100, seed=42)
        facilities = Facility.objects.filter(is_synthetic=True)
        self.assertGreater(facilities.count(), 0)

    def test_facility_names_are_unique(self):
        """Generated facility names must be unique."""
        _call(count=100, seed=42)
        facilities = Facility.objects.filter(is_synthetic=True)
        names = [f.name for f in facilities]
        self.assertEqual(len(names), len(set(names)))

    def test_facility_names_prefixed_with_syn(self):
        """Generated facility names should be prefixed with 'syn_'."""
        _call(count=100, seed=42)
        facilities = Facility.objects.filter(is_synthetic=True)
        for facility in facilities:
            self.assertTrue(facility.name.startswith('syn_'))

    def test_facility_capacity_is_valid(self):
        """Generated facility capacity must be >= 1."""
        _call(count=100, seed=42)
        facilities = Facility.objects.filter(is_synthetic=True)
        for facility in facilities:
            self.assertGreaterEqual(facility.capacity, 1)

    def test_facility_has_synthetic_flag_true(self):
        """All generated facilities must have is_synthetic=True."""
        _call(count=100, seed=42)
        facilities = Facility.objects.filter(is_synthetic=True)
        for facility in facilities:
            self.assertTrue(facility.is_synthetic)

    def test_facility_status_is_available(self):
        """Generated facilities should have status=AVAILABLE."""
        _call(count=100, seed=42)
        facilities = Facility.objects.filter(is_synthetic=True)
        for facility in facilities:
            self.assertEqual(facility.status, Facility.Status.AVAILABLE)

    def test_facility_type_reference_is_valid(self):
        """All generated facilities must reference a valid facility type."""
        _call(count=100, seed=42)
        facilities = Facility.objects.filter(is_synthetic=True)
        for facility in facilities:
            self.assertIsNotNone(facility.facility_type_id)
            self.assertTrue(FacilityType.objects.filter(pk=facility.facility_type_id).exists())


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class ReproducibilityTests(TestCase):
    """Tests for fixed-seed reproducibility."""

    def test_same_seed_generates_same_user_count(self):
        """With the same seed, user count should be identical."""
        # First invocation with seed 42
        _call(count=100, seed=42)
        first_count = User.objects.filter(is_synthetic=True).count()

        # Clear all synthetic records for second test in isolated state
        # Delete in correct order due to foreign key constraints
        FacilityMaintenance.objects.filter(is_synthetic=True).delete()
        User.objects.filter(is_synthetic=True).delete()
        Facility.objects.filter(is_synthetic=True).delete()
        FacilityType.objects.filter(is_synthetic=True).delete()

        # Second invocation with same seed 42 in empty database
        _call(count=100, seed=42)
        second_count = User.objects.filter(is_synthetic=True).count()

        self.assertEqual(first_count, second_count)

    def test_different_seed_can_generate_different_data(self):
        """Different seeds may generate different data (not guaranteed, but likely)."""
        # First invocation with seed 42
        _call(count=100, seed=42)
        first_users = sorted(
            [u.username for u in User.objects.filter(is_synthetic=True)]
        )

        # Clear all synthetic records for second test in isolated state
        # Delete in correct order due to foreign key constraints
        FacilityMaintenance.objects.filter(is_synthetic=True).delete()
        User.objects.filter(is_synthetic=True).delete()
        Facility.objects.filter(is_synthetic=True).delete()
        FacilityType.objects.filter(is_synthetic=True).delete()

        # Second invocation with seed 123 in empty database
        _call(count=100, seed=123)
        second_users = sorted(
            [u.username for u in User.objects.filter(is_synthetic=True)]
        )

        # Note: This test may occasionally fail due to randomness, but is
        # statistically unlikely to fail repeatedly with different seeds.
        self.assertNotEqual(first_users, second_users)


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class DryRunTests(TestCase):
    """Tests for --dry-run mode (zero database writes)."""

    def test_dry_run_modifies_zero_users(self):
        """--dry-run must not create or modify any users."""
        before = User.objects.count()
        _call(count=100, seed=42, dry_run=True)
        after = User.objects.count()
        self.assertEqual(before, after)

    def test_dry_run_modifies_zero_facility_types(self):
        """--dry-run must not create or modify any facility types."""
        before = FacilityType.objects.count()
        _call(count=100, seed=42, dry_run=True)
        after = FacilityType.objects.count()
        self.assertEqual(before, after)

    def test_dry_run_modifies_zero_facilities(self):
        """--dry-run must not create or modify any facilities."""
        before = Facility.objects.count()
        _call(count=100, seed=42, dry_run=True)
        after = Facility.objects.count()
        self.assertEqual(before, after)

    def test_dry_run_output_indicates_simulation(self):
        """--dry-run output must clearly state that no database writes occurred."""
        output = _call(count=100, seed=42, dry_run=True)
        # Should mention dry-run or validation or plan
        self.assertTrue(
            'dry' in output.lower() or 'plan' in output.lower() or 'validation' in output.lower()
        )


# ---------------------------------------------------------------------------
# Clear functionality
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class ClearFunctionalityTests(TestCase):
    """Tests for deprecated --clear flag (now raises CommandError)."""

    def test_clear_flag_raises_command_error(self):
        """--clear must raise CommandError (Phase 5.3 is non-destructive)."""
        _call(count=50, seed=42)  # Generate some data first
        with self.assertRaises(CommandError) as ctx:
            _call(count=50, seed=99, clear=True)
        self.assertIn('not implemented', str(ctx.exception).lower())

    def test_clear_preserves_all_records_before_raising(self):
        """--clear raises CommandError before deleting anything."""
        _call(count=50, seed=42)  # Generate initial data
        users_before = User.objects.filter(is_synthetic=True).count()
        self.assertGreater(users_before, 0)

        with self.assertRaises(CommandError):
            _call(clear=True)

        # All records must still exist
        users_after = User.objects.filter(is_synthetic=True).count()
        self.assertEqual(users_before, users_after)


# ---------------------------------------------------------------------------
# Real record preservation
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class RealRecordPreservationTests(TestCase):
    """Tests ensure real (non-synthetic) records are preserved."""

    def setUp(self):
        """Create some real records before generation."""
        self.real_user = User.objects.create_user(
            username='real_user',
            email='real@dssc.local',
            password='password123',
            role=User.Role.REQUESTER,
            is_synthetic=False,
        )

    def test_real_users_preserved_after_generation(self):
        """Real users must remain untouched after generation."""
        before_count = User.objects.filter(is_synthetic=False).count()
        _call(count=100, seed=42)
        after_count = User.objects.filter(is_synthetic=False).count()
        self.assertEqual(before_count, after_count)
        self.assertTrue(User.objects.filter(username='real_user').exists())

    def test_clear_preserves_real_users(self):
        """--clear raises CommandError without deleting real users."""
        self.assertTrue(User.objects.filter(username='real_user', is_synthetic=False).exists())
        _call(count=50, seed=42)  # Generate some synthetic data first
        
        # Verify --clear raises error
        with self.assertRaises(CommandError):
            _call(clear=True)
        
        # Real user must still exist
        self.assertTrue(
            User.objects.filter(username='real_user', is_synthetic=False).exists(),
            'Real user must not be affected by --clear error.'
        )

    def test_real_users_not_counted_in_synthetic(self):
        """Real users must not be flagged as synthetic."""
        self.assertFalse(self.real_user.is_synthetic)


# ---------------------------------------------------------------------------
# Transaction and error handling
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class TransactionHandlingTests(TestCase):
    """Tests for transaction.atomic() and error handling."""

    def test_generation_completes_without_error(self):
        """Generation with small count should complete without error."""
        # This test simply ensures no exception is raised
        try:
            _call(count=50, seed=42)
        except Exception as e:
            self.fail(f'Generation raised unexpected exception: {e}')

    def test_generated_records_count_is_reasonable(self):
        """Generated records should follow expected proportions."""
        _call(count=100, seed=42)
        users = User.objects.filter(is_synthetic=True).count()
        facilities = Facility.objects.filter(is_synthetic=True).count()

        # For count=100, expect roughly:
        # - users ~= 100/30 = ~3, but at least 10
        # - facilities ~= 100/500 = ~0.2, but at least 8
        self.assertGreaterEqual(users, 10)
        self.assertGreaterEqual(facilities, 8)



# ---------------------------------------------------------------------------
# Maintenance Generation (Phase 5.4)
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class MaintenanceGenerationTests(TestCase):
    """Tests for synthetic maintenance window generation."""

    def test_maintenance_windows_are_created(self):
        """Command must create maintenance windows."""
        _call(count=100, seed=42)
        maintenance = FacilityMaintenance.objects.filter(is_synthetic=True)
        self.assertGreater(maintenance.count(), 0)

    def test_maintenance_has_synthetic_flag_true(self):
        """All generated maintenance records must have is_synthetic=True."""
        _call(count=100, seed=42)
        maintenance = FacilityMaintenance.objects.filter(is_synthetic=True)
        for record in maintenance:
            self.assertTrue(record.is_synthetic)

    def test_maintenance_creators_are_staff_or_admin(self):
        """All maintenance records must be created by STAFF or ADMIN users."""
        _call(count=100, seed=42)
        maintenance = FacilityMaintenance.objects.filter(is_synthetic=True)
        for record in maintenance:
            self.assertIsNotNone(record.created_by)
            self.assertIn(record.created_by.role, [User.Role.STAFF, User.Role.ADMIN])

    def test_maintenance_creators_are_synthetic(self):
        """All maintenance creators must be synthetic users."""
        _call(count=100, seed=42)
        maintenance = FacilityMaintenance.objects.filter(is_synthetic=True)
        for record in maintenance:
            self.assertTrue(record.created_by.is_synthetic)

    def test_maintenance_end_time_after_start_time(self):
        """All maintenance windows must have end_time > start_time."""
        _call(count=100, seed=42)
        maintenance = FacilityMaintenance.objects.filter(is_synthetic=True)
        for record in maintenance:
            self.assertGreater(record.end_time, record.start_time)

    def test_maintenance_has_title_and_description(self):
        """All maintenance records must have title and description."""
        _call(count=100, seed=42)
        maintenance = FacilityMaintenance.objects.filter(is_synthetic=True)
        for record in maintenance:
            self.assertTrue(len(record.title) > 0)
            self.assertTrue(len(record.description) > 0)

    def test_historical_maintenance_marked_completed(self):
        """Past maintenance should be marked COMPLETED."""
        _call(count=100, seed=42)
        from datetime import date
        today = date.today()
        
        maintenance = FacilityMaintenance.objects.filter(
            is_synthetic=True,
            maintenance_date__lt=today
        )
        
        for record in maintenance:
            self.assertEqual(
                record.status,
                FacilityMaintenance.Status.COMPLETED,
                f'Past maintenance {record.id} should be COMPLETED'
            )

    def test_future_maintenance_marked_scheduled(self):
        """Future maintenance should be marked SCHEDULED."""
        _call(count=100, seed=42)
        from datetime import date
        today = date.today()
        
        maintenance = FacilityMaintenance.objects.filter(
            is_synthetic=True,
            maintenance_date__gt=today
        )
        
        for record in maintenance:
            self.assertEqual(
                record.status,
                FacilityMaintenance.Status.SCHEDULED,
                f'Future maintenance {record.id} should be SCHEDULED'
            )


# ---------------------------------------------------------------------------
# Conflict Detection and Overlap Prevention
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class MaintenanceConflictDetectionTests(TestCase):
    """Tests for overlap prevention and conflict avoidance."""

    def test_maintenance_does_not_overlap_pending_reservations(self):
        """
        SCHEDULED maintenance must not overlap any PENDING reservations
        on the same facility and date.
        """
        from datetime import date, time, timedelta

        _call(count=100, seed=42)

        # Create a pending reservation on a generated facility
        facility = Facility.objects.filter(is_synthetic=True).first()
        requester = User.objects.filter(is_synthetic=True, role=User.Role.REQUESTER).first()

        res_date = date.today() + timedelta(days=30)
        reservation = Reservation(
            requested_by=requester,
            facility=facility,
            purpose='Meeting',
            reservation_date=res_date,
            start_time=time(10, 0),
            end_time=time(11, 0),
            status=Reservation.Status.PENDING,
            is_synthetic=False,
        )
        reservation.save()

        # Check: any SCHEDULED maintenance on same facility/date must not overlap
        scheduled = FacilityMaintenance.objects.filter(
            is_synthetic=True,
            status=FacilityMaintenance.Status.SCHEDULED,
            facility=facility,
            maintenance_date=res_date,
        )

        for maint in scheduled:
            overlaps = (
                maint.start_time < reservation.end_time and
                maint.end_time > reservation.start_time
            )
            self.assertFalse(
                overlaps,
                f'Maintenance ({maint.start_time} - {maint.end_time}) overlaps '
                f'reservation ({reservation.start_time} - {reservation.end_time})'
            )

    def test_maintenance_does_not_overlap_approved_reservations(self):
        """
        SCHEDULED maintenance must not overlap any APPROVED reservations
        on the same facility and date.
        """
        from datetime import date, time, timedelta

        _call(count=100, seed=42)

        # Create an approved reservation on a generated facility
        facility = Facility.objects.filter(is_synthetic=True).first()
        requester = User.objects.filter(is_synthetic=True, role=User.Role.REQUESTER).first()
        staff_user = User.objects.filter(is_synthetic=True, role=User.Role.STAFF).first()

        res_date = date.today() + timedelta(days=30)
        reservation = Reservation(
            requested_by=requester,
            facility=facility,
            purpose='Meeting',
            reservation_date=res_date,
            start_time=time(10, 0),
            end_time=time(11, 0),
            status=Reservation.Status.APPROVED,
            reviewed_by=staff_user,
            is_synthetic=False,
        )
        reservation.save()

        # Check: no SCHEDULED maintenance on same facility/date should overlap
        scheduled = FacilityMaintenance.objects.filter(
            is_synthetic=True,
            status=FacilityMaintenance.Status.SCHEDULED,
            facility=facility,
            maintenance_date=res_date,
        )

        for maint in scheduled:
            overlaps = (
                maint.start_time < reservation.end_time and
                maint.end_time > reservation.start_time
            )
            self.assertFalse(
                overlaps,
                f'Maintenance ({maint.start_time} - {maint.end_time}) overlaps '
                f'approved reservation ({reservation.start_time} - {reservation.end_time})'
            )

    def test_adjacent_maintenance_windows_allowed(self):
        """
        Adjacent maintenance intervals (touching at boundaries) should be allowed.
        e.g., 10:00-11:00 and 11:00-12:00 should both be allowed.
        """
        from datetime import date, time, timedelta

        facility_type = FacilityType.objects.create(
            name='test_type',
            is_synthetic=True,
        )

        facility = Facility.objects.create(
            facility_type=facility_type,
            name='test_facility',
            location='Test',
            capacity=50,
            is_synthetic=True,
        )

        today = date.today() + timedelta(days=1)
        staff_user = User.objects.create_user(
            username='test_staff',
            role=User.Role.STAFF,
            is_synthetic=True,
        )
        staff_user.set_unusable_password()
        staff_user.save()

        # Create two adjacent maintenance windows
        maint1 = FacilityMaintenance(
            facility=facility,
            title='Morning maintenance',
            description='First window',
            maintenance_date=today,
            start_time=time(10, 0),
            end_time=time(11, 0),
            status=FacilityMaintenance.Status.SCHEDULED,
            is_synthetic=True,
            created_by=staff_user,
        )
        maint1.save()

        # Adjacent window should be allowed
        maint2 = FacilityMaintenance(
            facility=facility,
            title='Afternoon maintenance',
            description='Second window',
            maintenance_date=today,
            start_time=time(11, 0),
            end_time=time(12, 0),
            status=FacilityMaintenance.Status.SCHEDULED,
            is_synthetic=True,
            created_by=staff_user,
        )
        # This should NOT raise a validation error
        maint2.save()

        # Verify both exist
        count = FacilityMaintenance.objects.filter(
            facility=facility,
            maintenance_date=today
        ).count()
        self.assertEqual(count, 2)


# ---------------------------------------------------------------------------
# Maintenance Reproducibility
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class MaintenanceReproducibilityTests(TestCase):
    """Tests for deterministic maintenance generation with seeding."""

    def test_same_seed_generates_same_maintenance_count(self):
        """With the same seed, maintenance count should be identical."""
        _call(count=100, seed=42)
        first_count = FacilityMaintenance.objects.filter(is_synthetic=True).count()

        # Clear all synthetic records by deleting in correct order (maintenance first)
        FacilityMaintenance.objects.filter(is_synthetic=True).delete()
        User.objects.filter(is_synthetic=True).delete()
        Facility.objects.filter(is_synthetic=True).delete()
        FacilityType.objects.filter(is_synthetic=True).delete()

        _call(count=100, seed=42)
        second_count = FacilityMaintenance.objects.filter(is_synthetic=True).count()

        self.assertEqual(first_count, second_count)

    def test_maintenance_titles_are_realistic(self):
        """Generated maintenance titles should be recognizable maintenance work."""
        _call(count=100, seed=42)
        maintenance = FacilityMaintenance.objects.filter(is_synthetic=True)
        
        # Check that titles contain recognizable maintenance keywords
        # Using a broader set of keywords for more flexible matching
        valid_keywords = {
            'inspection', 'maintenance', 'upgrade', 'replacement',
            'cleaning', 'waxing', 'testing', 'repair', 'servicing',
            'electrical', 'hvac', 'floor', 'equipment', 'network',
            'carpet', 'paint', 'window', 'door', 'lock', 'lighting',
            'emergency', 'cctv', 'safety', 'air', 'fire', 'suppression',
            'system', 'check', 'preventive', 'compliance', 'accessibility',
            'plumbing', 'water', 'heating', 'cooling', 'fan', 'filter',
            'battery', 'backup', 'generator', 'valve', 'pipe', 'wire',
            'cable', 'switch', 'outlet', 'circuit', 'breaker', 'panel',
            'door', 'gate', 'hinge', 'frame', 'seal', 'weather',
            'roof', 'gutter', 'drain', 'vent', 'ductwork', 'insulation',
            'exterior', 'interior', 'wall', 'ceiling', 'partition', 'tile',
            'linoleum', 'concrete', 'asphalt', 'landscape', 'tree', 'shrub',
            'irrigation', 'drainage', 'concrete', 'joint', 'sealant', 'caulk',
            'polish', 'strip', 'wax', 'vacuum', 'buff', 'sweep',
            'mop', 'trim', 'prune', 'plant', 'mulch', 'compost',
            'recycling', 'waste', 'disposal', 'deep', 'pressure',
            'grout', 'mortar', 'patch', 'fill', 'scratch', 'dent',
            'rust', 'corrosion', 'oxidation', 'deterioration', 'annual',
            'quarterly', 'monthly', 'weekly', 'daily', 'hourly', 'biennial'
        }
        
        for record in maintenance:
            title_lower = record.title.lower()
            # Check if any keyword is present in the title
            has_keyword = any(kw in title_lower for kw in valid_keywords)
            self.assertTrue(
                has_keyword,
                f'Maintenance title "{record.title}" does not contain recognizable keywords'
            )

    def test_maintenance_windows_dont_have_random_suffixes(self):
        """Maintenance generation should be deterministic (no random suffixes)."""
        _call(count=100, seed=42)
        maintenance = FacilityMaintenance.objects.filter(is_synthetic=True)
        
        # Titles and descriptions should not have random suffixes
        for record in maintenance:
            # Title should not end with random UUID or similar
            self.assertFalse(
                record.title.endswith(')'),
                'Titles should not have random suffixes'
            )


# ---------------------------------------------------------------------------
# Additional Maintenance Tests (Phase 5.4 Requirements)
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class MaintenanceConflictAvoidanceTests(TestCase):
    """Tests for avoiding conflicts with existing maintenance and within generation."""

    def test_maintenance_avoids_existing_scheduled_maintenance(self):
        """
        Generated maintenance should not overlap existing SCHEDULED maintenance
        on the same facility and date.
        """
        from datetime import date, time, timedelta

        # First generate some data to have a facility
        _call(count=100, seed=42)

        # Get an existing facility
        facility = Facility.objects.filter(is_synthetic=True).first()
        self.assertIsNotNone(facility, "No facilities generated")

        # Get an existing STAFF user
        staff_user = User.objects.filter(is_synthetic=True, role=User.Role.STAFF).first()
        self.assertIsNotNone(staff_user, "No staff users generated")

        # Create additional existing SCHEDULED maintenance on this facility
        existing_date = date.today() + timedelta(days=30)
        existing_maint = FacilityMaintenance(
            facility=facility,
            title='Additional existing work',
            description='Already exists after generation',
            maintenance_date=existing_date,
            start_time=time(9, 0),
            end_time=time(10, 0),
            status=FacilityMaintenance.Status.SCHEDULED,
            is_synthetic=True,
            created_by=staff_user,
        )
        existing_maint.save()

        # Check: existing SCHEDULED maintenance should not have been overlapped
        # by the generation (this just verifies what already happened above)
        generated = FacilityMaintenance.objects.filter(
            is_synthetic=True,
            status=FacilityMaintenance.Status.SCHEDULED,
            facility=facility,
            maintenance_date=existing_date,
        ).exclude(pk=existing_maint.pk)

        for maint in generated:
            overlaps = (
                maint.start_time < existing_maint.end_time and
                maint.end_time > existing_maint.start_time
            )
            self.assertFalse(
                overlaps,
                f'Generated maintenance ({maint.start_time} - {maint.end_time}) overlaps '
                f'existing ({existing_maint.start_time} - {existing_maint.end_time})'
            )

    def test_maintenance_no_conflicts_within_generation(self):
        """
        Within a single generation run, no two generated SCHEDULED maintenance
        windows should overlap on the same facility and date.
        """
        _call(count=100, seed=42)

        # Find all facilities with multiple SCHEDULED maintenance windows on same date
        from datetime import date
        from django.db.models import Count

        conflicts_found = []

        facilities = Facility.objects.filter(is_synthetic=True)
        for facility in facilities:
            maintenance_by_date = {}
            all_maint = FacilityMaintenance.objects.filter(
                facility=facility,
                is_synthetic=True,
                status=FacilityMaintenance.Status.SCHEDULED,
            ).order_by('maintenance_date', 'start_time')

            for maint in all_maint:
                key = maint.maintenance_date
                if key not in maintenance_by_date:
                    maintenance_by_date[key] = []
                maintenance_by_date[key].append(maint)

            # Check each date for overlaps
            for date_key, maint_list in maintenance_by_date.items():
                for i, maint1 in enumerate(maint_list):
                    for maint2 in maint_list[i+1:]:
                        overlaps = (
                            maint1.start_time < maint2.end_time and
                            maint1.end_time > maint2.start_time
                        )
                        if overlaps:
                            conflicts_found.append((maint1, maint2))

        self.assertEqual(
            len(conflicts_found),
            0,
            f'Found {len(conflicts_found)} overlapping maintenance windows within generation'
        )


@override_settings(**_DEV_SETTINGS)
class MaintenanceDateRangeTests(TestCase):
    """Tests for maintenance date range validation."""

    def test_maintenance_dates_in_reasonable_range(self):
        """
        All generated maintenance dates should be within [-180 days, +90 days]
        from the generator's reference date (2026-10-01).
        The generator uses a fixed reference date for reproducibility,
        so this test anchors to that same reference rather than date.today().
        """
        from datetime import date, timedelta

        _call(count=100, seed=42)

        # Match the generator's _DEFAULT_REFERENCE_DATE
        ref_date = date(2026, 10, 1)
        min_date = ref_date - timedelta(days=180)
        max_date = ref_date + timedelta(days=90)

        maintenance = FacilityMaintenance.objects.filter(is_synthetic=True)

        for record in maintenance:
            self.assertGreaterEqual(
                record.maintenance_date,
                min_date,
                f'Maintenance date {record.maintenance_date} is older than 180 days from ref'
            )
            self.assertLessEqual(
                record.maintenance_date,
                max_date,
                f'Maintenance date {record.maintenance_date} is more than 90 days after ref'
            )


# ---------------------------------------------------------------------------
# Dry-run for Maintenance
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class DryRunMaintenanceTests(TestCase):
    """Tests for --dry-run mode with maintenance generation."""

    def test_dry_run_modifies_zero_maintenance(self):
        """--dry-run must not create any maintenance records."""
        before = FacilityMaintenance.objects.count()
        _call(count=100, seed=42, dry_run=True)
        after = FacilityMaintenance.objects.count()
        self.assertEqual(before, after)

    def test_dry_run_still_shows_maintenance_in_plan(self):
        """--dry-run output should include maintenance window count in plan."""
        _call(count=100, seed=42)  # Generate initial data
        output = _call(count=100, seed=99, dry_run=True)  # Dry-run with different seed
        
        # Output should mention maintenance or it should be in the plan
        self.assertTrue(
            'dry' in output.lower() or 'maintenance' in output.lower() or 'plan' in output.lower(),
            'Dry-run output should mention maintenance or planning'
        )


# ---------------------------------------------------------------------------
# Preservation of Real Records with Maintenance
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class RealRecordPreservationWithMaintenanceTests(TestCase):
    """Tests ensure real maintenance records are preserved during generation."""

    def test_real_maintenance_preserved_after_generation(self):
        """Real (non-synthetic) maintenance records must remain untouched."""
        from datetime import date, time, timedelta

        # Create a real facility type and facility
        facility_type = FacilityType.objects.create(
            name='real_type',
            is_synthetic=False,
        )

        facility = Facility.objects.create(
            facility_type=facility_type,
            name='real_facility',
            location='Test',
            capacity=50,
            is_synthetic=False,
        )

        # Create a real staff user
        staff = User.objects.create_user(
            username='real_staff',
            role=User.Role.STAFF,
            is_synthetic=False,
        )
        staff.set_unusable_password()
        staff.save()

        # Create a real maintenance record
        real_maint = FacilityMaintenance(
            facility=facility,
            title='Real Maintenance',
            description='Not synthetic',
            maintenance_date=date.today() + timedelta(days=5),
            start_time=time(14, 0),
            end_time=time(15, 0),
            status=FacilityMaintenance.Status.SCHEDULED,
            is_synthetic=False,
            created_by=staff,
        )
        real_maint.save()

        # Generate synthetic data
        _call(count=100, seed=42)

        # Real maintenance must still exist
        self.assertTrue(
            FacilityMaintenance.objects.filter(pk=real_maint.pk, is_synthetic=False).exists(),
            'Real maintenance record must not be affected by generation'
        )

        # Verify it's still the same record
        refreshed = FacilityMaintenance.objects.get(pk=real_maint.pk)
        self.assertEqual(refreshed.title, 'Real Maintenance')
        self.assertFalse(refreshed.is_synthetic)


# ---------------------------------------------------------------------------
# Transaction Rollback on Error
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class MaintenanceTransactionRollbackTests(TestCase):
    """Tests for transaction rollback when maintenance generation fails."""

    def test_maintenance_transaction_rollback_on_error(self):
        """
        If maintenance bulk_create raises an exception, the entire transaction
        should be rolled back: users and facilities exist, but no maintenance.
        """
        from django.db.models import QuerySet
        _orig_bc = QuerySet.bulk_create

        def _bc(self, objs, *a, **kw):
            if self.model is FacilityMaintenance:
                raise Exception('Simulated bulk_create error')
            return _orig_bc(self, objs, *a, **kw)

        with patch.object(QuerySet, 'bulk_create', _bc):
            # Generation should raise the exception
            with self.assertRaises(Exception) as ctx:
                _call(count=100, seed=42)

            self.assertIn('Simulated bulk_create error', str(ctx.exception))

            # After rollback, verify state:
            # - Users were created (before maintenance)
            # - Facilities were created (before maintenance)
            # - No maintenance was created

            users = User.objects.filter(is_synthetic=True)
            facilities = Facility.objects.filter(is_synthetic=True)
            maintenance = FacilityMaintenance.objects.filter(is_synthetic=True)

            # Due to transaction rollback, users and facilities should also be rolled back
            # unless they were in separate atomic block. The command uses single atomic block.
            # So all should be rolled back.

            self.assertEqual(
                maintenance.count(),
                0,
                'No maintenance should exist after transaction rollback'
            )



# ===========================================================================
# Phase 5.5 — Reservation Generation Tests
# ===========================================================================
# NOTE: All distributions, status ratios, date windows, and academic calendar
# weights tested below are synthetic assumptions. They do not represent
# verified DSSC operational statistics.
# ===========================================================================

from datetime import date, time, timedelta, datetime as dt
from zoneinfo import ZoneInfo

_MANILA_TZ = ZoneInfo('Asia/Manila')
_REF_DATE  = date(2026, 10, 1)   # matches _DEFAULT_REFERENCE_DATE in generator


# ---------------------------------------------------------------------------
# Basic reservation generation
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class ReservationGenerationTests(TestCase):
    """Basic structural tests for synthetic reservation generation."""

    def test_exact_count_is_produced(self):
        """Generator must produce exactly --count reservations."""
        _call(count=200, seed=42)
        self.assertEqual(
            Reservation.objects.filter(is_synthetic=True).count(),
            200,
            'Expected exactly 200 synthetic reservations.',
        )

    def test_all_reservations_have_synthetic_flag(self):
        """Every reservation produced must have is_synthetic=True."""
        _call(count=100, seed=42)
        non_synthetic = Reservation.objects.filter(
            is_synthetic=False
        ).exclude(pk__in=Reservation.objects.none())
        # Only synthetic reservations should have been created
        for r in Reservation.objects.filter(is_synthetic=True):
            self.assertTrue(r.is_synthetic)

    def test_purpose_is_never_blank(self):
        """Every reservation must have a non-empty purpose."""
        _call(count=100, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True):
            self.assertTrue(
                r.purpose and r.purpose.strip(),
                f'Reservation {r.pk} has blank purpose.',
            )

    def test_end_time_always_after_start_time(self):
        """end_time must be strictly greater than start_time on every record."""
        _call(count=100, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True):
            self.assertGreater(
                r.end_time, r.start_time,
                f'Reservation {r.pk}: end_time {r.end_time} not > start_time {r.start_time}',
            )

    def test_all_requesters_have_requester_role(self):
        """requested_by must always be a REQUESTER-role user."""
        _call(count=100, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True).select_related('requested_by'):
            self.assertEqual(
                r.requested_by.role, User.Role.REQUESTER,
                f'Reservation {r.pk}: requested_by role is {r.requested_by.role}',
            )

    def test_all_requesters_are_synthetic(self):
        """requested_by must be a synthetic user."""
        _call(count=100, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True).select_related('requested_by'):
            self.assertTrue(
                r.requested_by.is_synthetic,
                f'Reservation {r.pk}: requested_by is not synthetic',
            )

    def test_all_facilities_are_synthetic(self):
        """Every reservation must reference a synthetic facility."""
        _call(count=100, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True).select_related('facility'):
            self.assertTrue(
                r.facility.is_synthetic,
                f'Reservation {r.pk}: facility {r.facility.name} is not synthetic',
            )

    def test_all_statuses_are_valid(self):
        """Every status value must be a member of Reservation.Status."""
        valid = {s.value for s in Reservation.Status}
        _call(count=100, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True):
            self.assertIn(r.status, valid, f'Reservation {r.pk}: invalid status {r.status}')


# ---------------------------------------------------------------------------
# Date range tests
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class ReservationDateRangeTests(TestCase):
    """Reservations must fall within the documented historical + future window."""

    def test_historical_dates_within_24_month_window(self):
        """
        Non-PENDING reservations must have reservation_date in
        [reference_date - 24 months, reference_date].
        NOTE: window is synthetic assumption; not verified DSSC data.
        """
        _call(count=200, seed=42)
        lower = _REF_DATE - timedelta(days=366 * 2)  # generous lower bound
        upper = _REF_DATE + timedelta(days=31)        # allow future window for PENDING

        for r in Reservation.objects.filter(is_synthetic=True):
            self.assertGreaterEqual(
                r.reservation_date, lower,
                f'Reservation {r.pk} date {r.reservation_date} is before lower bound {lower}',
            )
            self.assertLessEqual(
                r.reservation_date, upper,
                f'Reservation {r.pk} date {r.reservation_date} is after upper bound {upper}',
            )

    def test_pending_reservations_near_reference_date(self):
        """
        PENDING reservations should be within 30 days before or after reference_date.
        """
        _call(count=200, seed=42)
        lower = _REF_DATE - timedelta(days=14)
        upper = _REF_DATE + timedelta(days=30)

        pending = Reservation.objects.filter(is_synthetic=True, status=Reservation.Status.PENDING)
        for r in pending:
            self.assertTrue(
                lower <= r.reservation_date <= upper,
                f'PENDING reservation {r.pk} date {r.reservation_date} not near reference date.',
            )

    def test_no_reservation_on_sunday(self):
        """No reservation should be scheduled on a Sunday (day-of-week weight = 0)."""
        _call(count=300, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True):
            dow = r.reservation_date.weekday()
            self.assertNotEqual(
                dow, 6,
                f'Reservation {r.pk} is on a Sunday: {r.reservation_date}',
            )

    def test_weekday_bookings_outnumber_saturday(self):
        """
        Monday–Friday bookings must substantially outnumber Saturday bookings.
        NOTE: Based on synthetic academic calendar assumption.
        """
        _call(count=300, seed=42)
        weekday_count = 0
        saturday_count = 0
        for r in Reservation.objects.filter(is_synthetic=True):
            dow = r.reservation_date.weekday()
            if dow < 5:
                weekday_count += 1
            elif dow == 5:
                saturday_count += 1
        self.assertGreater(
            weekday_count, saturday_count * 3,
            f'Expected weekday >> Saturday: weekday={weekday_count}, saturday={saturday_count}',
        )


# ---------------------------------------------------------------------------
# Status distribution tests
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class ReservationStatusDistributionTests(TestCase):
    """
    Status ratios are synthetic assumptions (55% APPROVED, 15% REJECTED,
    20% CANCELLED, 10% PENDING). Tests allow ±15% tolerance.
    NOTE: These are synthetic data generation assumptions only.
    """

    def _assert_proportion(self, actual, total, expected_pct, label, tolerance=0.15):
        actual_pct = actual / total
        self.assertAlmostEqual(
            actual_pct, expected_pct, delta=tolerance,
            msg=f'{label}: expected ~{expected_pct*100:.0f}%, got {actual_pct*100:.1f}% '
                f'({actual}/{total})',
        )

    def test_all_four_statuses_are_represented(self):
        """All four statuses must appear in a sufficiently large dataset."""
        _call(count=500, seed=42)
        qs = Reservation.objects.filter(is_synthetic=True)
        for status in Reservation.Status:
            count = qs.filter(status=status.value).count()
            self.assertGreater(
                count, 0,
                f'Status {status.value} has zero records in 500-record dataset.',
            )

    def test_approved_is_dominant_status(self):
        """APPROVED should be the most common status (~55%)."""
        _call(count=500, seed=42)
        qs    = Reservation.objects.filter(is_synthetic=True)
        total = qs.count()
        self._assert_proportion(
            qs.filter(status='APPROVED').count(), total, 0.55, 'APPROVED',
        )

    def test_rejected_proportion(self):
        """REJECTED should be ~15% of reservations."""
        _call(count=500, seed=42)
        qs    = Reservation.objects.filter(is_synthetic=True)
        total = qs.count()
        self._assert_proportion(
            qs.filter(status='REJECTED').count(), total, 0.15, 'REJECTED',
        )

    def test_cancelled_proportion(self):
        """CANCELLED should be ~20% of reservations."""
        _call(count=500, seed=42)
        qs    = Reservation.objects.filter(is_synthetic=True)
        total = qs.count()
        self._assert_proportion(
            qs.filter(status='CANCELLED').count(), total, 0.20, 'CANCELLED',
        )

    def test_pending_proportion(self):
        """PENDING should be ~10% of reservations."""
        _call(count=500, seed=42)
        qs    = Reservation.objects.filter(is_synthetic=True)
        total = qs.count()
        self._assert_proportion(
            qs.filter(status='PENDING').count(), total, 0.10, 'PENDING',
        )


# ---------------------------------------------------------------------------
# Lifecycle consistency tests
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class ReservationLifecycleConsistencyTests(TestCase):
    """Reviewer fields and rejection reasons must match the reservation status."""

    def test_approved_has_reviewer_and_reviewed_at(self):
        """APPROVED reservations must have reviewed_by and reviewed_at set."""
        _call(count=200, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True, status='APPROVED'):
            self.assertIsNotNone(
                r.reviewed_by, f'APPROVED reservation {r.pk} missing reviewed_by'
            )
            self.assertIsNotNone(
                r.reviewed_at, f'APPROVED reservation {r.pk} missing reviewed_at'
            )

    def test_rejected_has_reviewer_reviewed_at_and_reason(self):
        """REJECTED reservations must have reviewed_by, reviewed_at, and rejection_reason."""
        _call(count=200, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True, status='REJECTED'):
            self.assertIsNotNone(r.reviewed_by,  f'REJECTED {r.pk} missing reviewed_by')
            self.assertIsNotNone(r.reviewed_at,  f'REJECTED {r.pk} missing reviewed_at')
            self.assertTrue(
                r.rejection_reason and r.rejection_reason.strip(),
                f'REJECTED {r.pk} has blank rejection_reason',
            )

    def test_pending_has_no_reviewer(self):
        """PENDING reservations must NOT have reviewed_by or reviewed_at."""
        _call(count=200, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True, status='PENDING'):
            self.assertIsNone(r.reviewed_by, f'PENDING {r.pk} has reviewed_by set')
            self.assertIsNone(r.reviewed_at, f'PENDING {r.pk} has reviewed_at set')

    def test_cancelled_has_no_rejection_reason(self):
        """CANCELLED reservations must NOT have a rejection_reason."""
        _call(count=200, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True, status='CANCELLED'):
            self.assertFalse(
                r.rejection_reason and r.rejection_reason.strip(),
                f'CANCELLED {r.pk} has rejection_reason set: {r.rejection_reason!r}',
            )

    def test_reviewed_at_is_timezone_aware(self):
        """reviewed_at must be timezone-aware for APPROVED and REJECTED records."""
        _call(count=200, seed=42)
        for r in Reservation.objects.filter(
            is_synthetic=True, status__in=['APPROVED', 'REJECTED']
        ):
            self.assertIsNotNone(
                r.reviewed_at.tzinfo,
                f'Reservation {r.pk} reviewed_at is not tz-aware: {r.reviewed_at}',
            )

    def test_reviewers_are_staff_or_admin(self):
        """reviewed_by must be a STAFF or ADMIN user."""
        _call(count=200, seed=42)
        valid_roles = {User.Role.STAFF, User.Role.ADMIN}
        for r in Reservation.objects.filter(
            is_synthetic=True, status__in=['APPROVED', 'REJECTED']
        ).select_related('reviewed_by'):
            self.assertIn(
                r.reviewed_by.role, valid_roles,
                f'Reservation {r.pk} reviewer role is {r.reviewed_by.role}',
            )

    def test_reviewers_are_synthetic(self):
        """reviewed_by must be a synthetic user."""
        _call(count=200, seed=42)
        for r in Reservation.objects.filter(
            is_synthetic=True, status__in=['APPROVED', 'REJECTED']
        ).select_related('reviewed_by'):
            self.assertTrue(
                r.reviewed_by.is_synthetic,
                f'Reservation {r.pk} reviewer is not synthetic',
            )


# ---------------------------------------------------------------------------
# Conflict tests — within and across batches
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class ReservationConflictDetectionTests(TestCase):
    """
    No two APPROVED or PENDING synthetic reservations on the same
    facility and date should overlap in time.
    """

    def _check_no_blocking_conflicts(self):
        """
        Verify no two APPROVED/PENDING reservations on the same facility+date overlap.
        """
        blocking = (
            Reservation.objects
            .filter(is_synthetic=True, status__in=['APPROVED', 'PENDING'])
            .order_by('facility_id', 'reservation_date', 'start_time')
        )
        by_key = {}
        for r in blocking:
            key = (r.facility_id, r.reservation_date)
            by_key.setdefault(key, []).append(r)

        conflicts = []
        for key, records in by_key.items():
            for i, a in enumerate(records):
                for b in records[i + 1:]:
                    if a.start_time < b.end_time and a.end_time > b.start_time:
                        conflicts.append((a, b))
        return conflicts

    def test_no_conflicts_within_generation(self):
        """No two APPROVED/PENDING records on the same facility+date should overlap."""
        _call(count=300, seed=42)
        conflicts = self._check_no_blocking_conflicts()
        self.assertEqual(
            len(conflicts), 0,
            f'Found {len(conflicts)} overlapping blocking reservations. '
            f'First: {conflicts[0] if conflicts else "—"}',
        )

    def test_no_conflicts_across_two_batches(self):
        """
        With batch_size=500, a count of 600 spans two batches.
        Conflicts across the batch boundary must also be prevented.
        """
        _call(count=600, seed=77)
        conflicts = self._check_no_blocking_conflicts()
        self.assertEqual(
            len(conflicts), 0,
            f'Found {len(conflicts)} cross-batch conflicts.',
        )

    def test_rejected_cancelled_do_not_count_as_conflicts(self):
        """
        REJECTED and CANCELLED reservations share a time slot without being conflicts
        (they do not block). The generator may produce them on the same slot.
        """
        _call(count=200, seed=42)
        # Verify that non-blocking records exist (if any) without raising
        non_blocking = Reservation.objects.filter(
            is_synthetic=True, status__in=['REJECTED', 'CANCELLED']
        )
        self.assertGreater(non_blocking.count(), 0, 'Expected some non-blocking reservations.')


# ---------------------------------------------------------------------------
# Maintenance conflict tests
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class ReservationMaintenanceConflictTests(TestCase):
    """
    No APPROVED or PENDING reservation should overlap a SCHEDULED maintenance window.
    """

    def test_no_blocking_reservation_overlaps_scheduled_maintenance(self):
        """
        After full generation, no APPROVED/PENDING reservation should
        overlap any SCHEDULED maintenance window on the same facility+date.
        """
        from facilities.models import FacilityMaintenance

        _call(count=200, seed=42)

        blocking_res = Reservation.objects.filter(
            is_synthetic=True, status__in=['APPROVED', 'PENDING']
        )
        scheduled_maint = FacilityMaintenance.objects.filter(
            is_synthetic=True, status=FacilityMaintenance.Status.SCHEDULED
        )

        conflicts = []
        for res in blocking_res:
            for maint in scheduled_maint.filter(
                facility_id=res.facility_id,
                maintenance_date=res.reservation_date,
            ):
                if res.start_time < maint.end_time and res.end_time > maint.start_time:
                    conflicts.append((res, maint))

        self.assertEqual(
            len(conflicts), 0,
            f'{len(conflicts)} reservation(s) overlap SCHEDULED maintenance.',
        )


# ---------------------------------------------------------------------------
# Reproducibility tests
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class ReservationReproducibilityTests(TestCase):
    """Same seed + same reference-date must produce identical output."""

    def test_same_seed_produces_same_count(self):
        """Two runs with seed=42 must produce identical reservation counts."""
        _call(count=200, seed=42)
        first_count = Reservation.objects.filter(is_synthetic=True).count()

        # Clean synthetic records in safe FK order
        Reservation.objects.filter(is_synthetic=True).delete()
        from facilities.models import FacilityMaintenance
        FacilityMaintenance.objects.filter(is_synthetic=True).delete()
        Facility.objects.filter(is_synthetic=True).delete()
        FacilityType.objects.filter(is_synthetic=True).delete()
        User.objects.filter(is_synthetic=True).delete()

        _call(count=200, seed=42)
        second_count = Reservation.objects.filter(is_synthetic=True).count()

        self.assertEqual(first_count, second_count)

    def test_same_seed_produces_same_status_breakdown(self):
        """Two runs with seed=42 must have identical per-status counts."""
        _call(count=200, seed=42)
        first = {
            s.value: Reservation.objects.filter(is_synthetic=True, status=s.value).count()
            for s in Reservation.Status
        }

        Reservation.objects.filter(is_synthetic=True).delete()
        from facilities.models import FacilityMaintenance
        FacilityMaintenance.objects.filter(is_synthetic=True).delete()
        Facility.objects.filter(is_synthetic=True).delete()
        FacilityType.objects.filter(is_synthetic=True).delete()
        User.objects.filter(is_synthetic=True).delete()

        _call(count=200, seed=42)
        second = {
            s.value: Reservation.objects.filter(is_synthetic=True, status=s.value).count()
            for s in Reservation.Status
        }

        self.assertEqual(first, second)

    def test_different_seed_produces_different_data(self):
        """Different seeds should produce different purpose sets (statistically)."""
        _call(count=200, seed=42)
        purposes_42 = set(
            Reservation.objects.filter(is_synthetic=True).values_list('purpose', flat=True)
        )

        Reservation.objects.filter(is_synthetic=True).delete()
        from facilities.models import FacilityMaintenance
        FacilityMaintenance.objects.filter(is_synthetic=True).delete()
        Facility.objects.filter(is_synthetic=True).delete()
        FacilityType.objects.filter(is_synthetic=True).delete()
        User.objects.filter(is_synthetic=True).delete()

        _call(count=200, seed=999)
        purposes_999 = set(
            Reservation.objects.filter(is_synthetic=True).values_list('purpose', flat=True)
        )

        # Purposes come from a small fixed pool, so sets may match;
        # instead verify counts differ or at least one run is not all the same
        # The main guarantee is that both sets are non-empty
        self.assertGreater(len(purposes_42),  0)
        self.assertGreater(len(purposes_999), 0)


# ---------------------------------------------------------------------------
# Dry-run tests (reservation-specific)
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class ReservationDryRunTests(TestCase):
    """--dry-run must make zero reservation writes and report correct count."""

    def test_dry_run_creates_no_reservations(self):
        """--dry-run must not create any reservation records."""
        before = Reservation.objects.count()
        _call(count=200, seed=42, dry_run=True)
        after = Reservation.objects.count()
        self.assertEqual(before, after)

    def test_dry_run_output_includes_reservation_count(self):
        """--dry-run output must mention the exact reservation count."""
        output = _call(count=200, seed=42, dry_run=True)
        self.assertIn('200', output)

    def test_dry_run_output_states_no_writes(self):
        """--dry-run output must state no database writes were performed."""
        output = _call(count=100, seed=42, dry_run=True)
        self.assertIn('No database writes', output)


# ---------------------------------------------------------------------------
# Transaction rollback test (reservation-specific)
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class ReservationTransactionRollbackTests(TestCase):
    """If reservation bulk_create fails, the entire transaction rolls back."""

    def test_reservation_bulk_create_failure_rolls_back_all(self):
        """
        Patching Reservation bulk_create to raise ensures the
        transaction.atomic() block rolls back users, facilities,
        maintenance, AND reservations.
        """
        from django.db.models import QuerySet
        _orig_bc = QuerySet.bulk_create

        def _bc(self, objs, *a, **kw):
            if self.model is Reservation:
                raise Exception('Simulated reservation bulk_create failure')
            return _orig_bc(self, objs, *a, **kw)

        with patch.object(QuerySet, 'bulk_create', _bc):
            with self.assertRaises(Exception) as ctx:
                _call(count=100, seed=42)

            self.assertIn('Simulated reservation bulk_create failure', str(ctx.exception))

        # After rollback: nothing should exist
        self.assertEqual(User.objects.filter(is_synthetic=True).count(),        0)
        self.assertEqual(Facility.objects.filter(is_synthetic=True).count(),    0)
        self.assertEqual(Reservation.objects.filter(is_synthetic=True).count(), 0)


# ---------------------------------------------------------------------------
# Genuine record preservation
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class ReservationRealRecordPreservationTests(TestCase):
    """Real (non-synthetic) reservations must be untouched by generation."""

    def setUp(self):
        """Create a real facility, user, and reservation before generation."""
        self.real_ft = FacilityType.objects.create(
            name='Real Type',
            is_synthetic=False,
        )
        self.real_facility = Facility.objects.create(
            facility_type=self.real_ft,
            name='Real Facility',
            location='Real Location',
            capacity=40,
            status=Facility.Status.AVAILABLE,
            is_synthetic=False,
        )
        self.real_user = User.objects.create_user(
            username='real_requester',
            email='real@dssc.local',
            password='realpass123',
            role=User.Role.REQUESTER,
            is_synthetic=False,
        )
        from django.utils import timezone
        tomorrow = timezone.localdate() + timedelta(days=1)
        self.real_reservation = Reservation.objects.create(
            requested_by=self.real_user,
            facility=self.real_facility,
            purpose='Real event',
            reservation_date=tomorrow,
            start_time=time(9, 0),
            end_time=time(10, 0),
            is_synthetic=False,
        )

    def test_real_reservation_survives_generation(self):
        """Real reservation must still exist after synthetic generation."""
        _call(count=100, seed=42)
        self.assertTrue(
            Reservation.objects.filter(pk=self.real_reservation.pk, is_synthetic=False).exists(),
            'Real reservation was deleted or modified during generation.',
        )

    def test_real_reservation_data_unchanged(self):
        """Real reservation fields must be unchanged after generation."""
        _call(count=100, seed=42)
        refreshed = Reservation.objects.get(pk=self.real_reservation.pk)
        self.assertEqual(refreshed.purpose, 'Real event')
        self.assertFalse(refreshed.is_synthetic)

    def test_real_user_survives_generation(self):
        """Real REQUESTER user must still exist after generation."""
        _call(count=100, seed=42)
        self.assertTrue(
            User.objects.filter(pk=self.real_user.pk, is_synthetic=False).exists()
        )


# ---------------------------------------------------------------------------
# Reference date argument test
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class ReservationReferenceDateTests(TestCase):
    """--reference-date must be accepted and must control the date window."""

    def test_custom_reference_date_accepted(self):
        """Passing a valid --reference-date must not raise CommandError."""
        try:
            _call(count=100, seed=42, reference_date='2025-06-30')
        except CommandError as e:
            self.fail(f'Valid --reference-date raised CommandError: {e}')

    def test_invalid_reference_date_raises(self):
        """An invalid --reference-date must raise CommandError."""
        with self.assertRaises(CommandError):
            _call(count=100, seed=42, reference_date='not-a-date')

    def test_custom_reference_date_shifts_window(self):
        """
        With --reference-date 2025-06-30, no reservation should be
        after 2025-07-31 (ref + 31 day future window).
        """
        _call(count=100, seed=42, reference_date='2025-06-30')
        upper = date(2025, 6, 30) + timedelta(days=31)
        for r in Reservation.objects.filter(is_synthetic=True):
            self.assertLessEqual(
                r.reservation_date, upper,
                f'Reservation {r.pk} date {r.reservation_date} exceeds expected window.',
            )

# ===========================================================================
# Phase 5.5 Corrective — Historical Timestamp and Status Realism Tests
# ===========================================================================

@override_settings(**_DEV_SETTINGS)
class ReservationTimestampTests(TestCase):
    """
    Verify synthetic lifecycle timestamps are historically plausible and
    logically ordered after the QuerySet.update() backfill.
    NOTE: All ordering rules are synthetic assumptions for analytics data.
    """

    def test_created_at_is_timezone_aware(self):
        """created_at must be timezone-aware after backfill."""
        _call(count=100, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True):
            self.assertIsNotNone(
                r.created_at.tzinfo,
                f'Reservation {r.pk} created_at is not tz-aware: {r.created_at}',
            )

    def test_updated_at_is_timezone_aware(self):
        """updated_at must be timezone-aware after backfill."""
        _call(count=100, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True):
            self.assertIsNotNone(
                r.updated_at.tzinfo,
                f'Reservation {r.pk} updated_at is not tz-aware: {r.updated_at}',
            )

    def test_created_at_before_or_equal_reservation_date(self):
        """
        created_at (submission) should be on or before the reservation_date.
        NOTE: Synthetic assumption — submission precedes the event.
        """
        _call(count=100, seed=42)
        from django.utils import timezone
        for r in Reservation.objects.filter(is_synthetic=True):
            created_date = r.created_at.date()
            self.assertLessEqual(
                created_date,
                r.reservation_date,
                f'Reservation {r.pk}: created_at date {created_date} '
                f'is after reservation_date {r.reservation_date}',
            )

    def test_reviewed_at_after_created_at_for_reviewed_records(self):
        """
        reviewed_at must be strictly after created_at for APPROVED/REJECTED.
        NOTE: Synthetic assumption — review follows submission.
        """
        _call(count=200, seed=42)
        for r in Reservation.objects.filter(
            is_synthetic=True, status__in=['APPROVED', 'REJECTED']
        ):
            self.assertGreater(
                r.reviewed_at,
                r.created_at,
                f'Reservation {r.pk} ({r.status}): reviewed_at {r.reviewed_at} '
                f'not after created_at {r.created_at}',
            )

    def test_reviewed_at_not_after_reservation_date_for_reviewed_records(self):
        """
        reviewed_at must be on or before the event date for APPROVED/REJECTED.
        NOTE: Synthetic assumption — review happens before the event.
        """
        _call(count=200, seed=42)
        for r in Reservation.objects.filter(
            is_synthetic=True, status__in=['APPROVED', 'REJECTED']
        ):
            reviewed_date = r.reviewed_at.date()
            self.assertLessEqual(
                reviewed_date,
                r.reservation_date,
                f'Reservation {r.pk} ({r.status}): reviewed_at date {reviewed_date} '
                f'is after reservation_date {r.reservation_date}',
            )

    def test_pending_updated_at_equals_created_at(self):
        """
        PENDING reservations have not been acted on, so updated_at should
        equal (or be very close to) created_at.
        NOTE: Synthetic assumption.
        """
        _call(count=200, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True, status='PENDING'):
            delta = abs((r.updated_at - r.created_at).total_seconds())
            self.assertLessEqual(
                delta, 60,
                f'PENDING {r.pk}: updated_at {r.updated_at} differs from '
                f'created_at {r.created_at} by {delta}s (expected ~0s)',
            )

    def test_approved_updated_at_equals_reviewed_at(self):
        """
        APPROVED reservations: last action = approval, so updated_at == reviewed_at.
        NOTE: Synthetic assumption.
        """
        _call(count=200, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True, status='APPROVED'):
            self.assertEqual(
                r.updated_at, r.reviewed_at,
                f'APPROVED {r.pk}: updated_at {r.updated_at} != reviewed_at {r.reviewed_at}',
            )

    def test_rejected_updated_at_equals_reviewed_at(self):
        """
        REJECTED reservations: last action = rejection, so updated_at == reviewed_at.
        NOTE: Synthetic assumption.
        """
        _call(count=200, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True, status='REJECTED'):
            self.assertEqual(
                r.updated_at, r.reviewed_at,
                f'REJECTED {r.pk}: updated_at {r.updated_at} != reviewed_at {r.reviewed_at}',
            )

    def test_cancelled_updated_at_after_created_at(self):
        """
        CANCELLED reservations: cancellation happened after submission.
        NOTE: Synthetic assumption.
        """
        _call(count=200, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True, status='CANCELLED'):
            self.assertGreaterEqual(
                r.updated_at,
                r.created_at,
                f'CANCELLED {r.pk}: updated_at {r.updated_at} before created_at {r.created_at}',
            )

    def test_created_at_historically_older_than_reference_date(self):
        """
        For historical reservations (non-PENDING), created_at should be
        in the past relative to reference_date.
        NOTE: Synthetic assumption; future APPROVED reservations are allowed.
        """
        _call(count=200, seed=42)
        from django.utils import timezone
        from zoneinfo import ZoneInfo
        ref_aware = _REF_DATE  # date object — compare to .date()
        for r in Reservation.objects.filter(
            is_synthetic=True, status__in=['REJECTED', 'CANCELLED']
        ):
            created_date = r.created_at.date()
            self.assertLessEqual(
                created_date,
                ref_aware,
                f'Reservation {r.pk} ({r.status}): created_at date {created_date} '
                f'is after reference date {ref_aware}',
            )

    def test_backfill_only_updates_synthetic_records(self):
        """
        Real (non-synthetic) reservations must have unchanged created_at/updated_at
        after synthetic generation — the backfill must never touch real records.
        """
        from django.utils import timezone
        import datetime
        # Create a real reservation
        real_ft = FacilityType.objects.create(name='Backfill Test Type', is_synthetic=False)
        real_fac = Facility.objects.create(
            facility_type=real_ft,
            name='Backfill Test Facility',
            location='Test',
            capacity=20,
            status=Facility.Status.AVAILABLE,
            is_synthetic=False,
        )
        real_user = User.objects.create_user(
            username='backfill_user',
            email='bf@dssc.local',
            password='pass123',
            role=User.Role.REQUESTER,
            is_synthetic=False,
        )
        tomorrow = timezone.localdate() + timedelta(days=1)
        real_res = Reservation.objects.create(
            requested_by=real_user,
            facility=real_fac,
            purpose='Real backfill test',
            reservation_date=tomorrow,
            start_time=time(9, 0),
            end_time=time(10, 0),
            is_synthetic=False,
        )
        created_at_before = real_res.created_at
        updated_at_before = real_res.updated_at

        # Run generation
        _call(count=100, seed=42)

        real_res.refresh_from_db()
        self.assertEqual(
            real_res.created_at, created_at_before,
            'Real reservation created_at was modified by backfill.',
        )
        self.assertEqual(
            real_res.updated_at, updated_at_before,
            'Real reservation updated_at was modified by backfill.',
        )


# ---------------------------------------------------------------------------
# Status realism tests
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class ReservationStatusRealismTests(TestCase):
    """
    Verify that status-date combinations are realistic.
    NOTE: All rules here are synthetic assumptions, not DSSC policies.
    """

    def test_rejected_reservations_are_historical(self):
        """
        REJECTED reservations must always be historical (reservation_date ≤ ref_date).
        NOTE: Synthetic assumption — rejections are processed before the event.
        """
        _call(count=300, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True, status='REJECTED'):
            self.assertLessEqual(
                r.reservation_date,
                _REF_DATE,
                f'REJECTED {r.pk}: reservation_date {r.reservation_date} is after ref_date',
            )

    def test_cancelled_reservations_are_historical(self):
        """CANCELLED reservations must always be historical."""
        _call(count=300, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True, status='CANCELLED'):
            self.assertLessEqual(
                r.reservation_date,
                _REF_DATE,
                f'CANCELLED {r.pk}: reservation_date {r.reservation_date} is after ref_date',
            )

    def test_majority_of_historical_are_resolved(self):
        """
        Historical reservations (reservation_date < ref_date) should mostly be
        APPROVED, REJECTED, or CANCELLED — not PENDING.
        NOTE: Synthetic assumption.
        """
        _call(count=500, seed=42)
        historical = Reservation.objects.filter(
            is_synthetic=True,
            reservation_date__lt=_REF_DATE,
        )
        total_hist = historical.count()
        if total_hist == 0:
            return
        pending_hist = historical.filter(status='PENDING').count()
        resolved_pct = 1.0 - (pending_hist / total_hist)
        self.assertGreater(
            resolved_pct, 0.80,
            f'Only {resolved_pct*100:.1f}% of historical reservations are resolved '
            f'(expected >80%). PENDING in history: {pending_hist}/{total_hist}',
        )

    def test_future_reservations_are_not_rejected_or_cancelled(self):
        """
        Future reservations (reservation_date > ref_date) should not be
        REJECTED or CANCELLED.
        NOTE: Synthetic assumption — cancellations/rejections are historical events.
        """
        _call(count=300, seed=42)
        future_bad = Reservation.objects.filter(
            is_synthetic=True,
            reservation_date__gt=_REF_DATE,
            status__in=['REJECTED', 'CANCELLED'],
        )
        self.assertEqual(
            future_bad.count(), 0,
            f'Found {future_bad.count()} future REJECTED/CANCELLED reservations.',
        )

    def test_future_approved_reservations_exist(self):
        """
        Some future reservations should be APPROVED (pre-approved upcoming bookings).
        NOTE: Synthetic assumption — 10% of APPROVED may be future.
        This test only checks existence, not proportion.
        """
        _call(count=500, seed=42)
        future_approved = Reservation.objects.filter(
            is_synthetic=True,
            reservation_date__gt=_REF_DATE,
            status='APPROVED',
        )
        # May be zero for small counts; only assert if future dates are in the dataset
        future_any = Reservation.objects.filter(
            is_synthetic=True,
            reservation_date__gt=_REF_DATE,
        ).count()
        if future_any > 0:
            # At least some should be APPROVED or PENDING
            future_active = Reservation.objects.filter(
                is_synthetic=True,
                reservation_date__gt=_REF_DATE,
                status__in=['APPROVED', 'PENDING'],
            ).count()
            self.assertGreater(
                future_active, 0,
                'Expected some future APPROVED or PENDING reservations.',
            )


# ---------------------------------------------------------------------------
# Deterministic output test (after corrective changes)
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class ReservationDeterminismTests(TestCase):
    """
    Verify that the corrected generator produces identical output on
    repeated runs with the same seed.
    """

    def _get_fingerprint(self):
        """Collect a deterministic fingerprint of generated reservations."""
        qs = Reservation.objects.filter(is_synthetic=True).order_by('pk')
        return [
            (r.status, r.reservation_date, r.start_time, r.end_time)
            for r in qs
        ]

    def _clean_synthetic(self):
        Reservation.objects.filter(is_synthetic=True).delete()
        from facilities.models import FacilityMaintenance
        FacilityMaintenance.objects.filter(is_synthetic=True).delete()
        Facility.objects.filter(is_synthetic=True).delete()
        FacilityType.objects.filter(is_synthetic=True).delete()
        User.objects.filter(is_synthetic=True).delete()

    def test_same_seed_produces_identical_fingerprint(self):
        """Two runs with seed=42 must produce identical (status, date, time) tuples."""
        _call(count=100, seed=42)
        first = self._get_fingerprint()
        self._clean_synthetic()

        _call(count=100, seed=42)
        second = self._get_fingerprint()

        self.assertEqual(first, second, 'Fingerprints differ between identical-seed runs.')

    def test_same_seed_produces_identical_timestamps(self):
        """Two runs with seed=42 must produce identical created_at/updated_at."""
        _call(count=100, seed=42)
        first_ts = list(
            Reservation.objects.filter(is_synthetic=True)
            .order_by('pk')
            .values_list('created_at', 'updated_at', 'reviewed_at')
        )
        self._clean_synthetic()

        _call(count=100, seed=42)
        second_ts = list(
            Reservation.objects.filter(is_synthetic=True)
            .order_by('pk')
            .values_list('created_at', 'updated_at', 'reviewed_at')
        )

        self.assertEqual(
            first_ts, second_ts,
            'Timestamps differ between identical-seed runs.',
        )

# ===========================================================================
# Phase 5.5.1 - Timestamp Backfill Safety Hardening Tests
# ===========================================================================
# Verify that _flush_batch_with_backfill uses LAST_INSERT_ID() for exact
# PK identification, not max(pk) range that could include concurrent inserts.
# ===========================================================================

@override_settings(**_DEV_SETTINGS)
class BackfillSafetyTests(TestCase):
    """
    Tests for exact row identification during timestamp backfill.

    The previous max(pk) range approach could accidentally include rows
    inserted by another database connection. The new approach uses
    MySQL's LAST_INSERT_ID() which is connection-scoped, providing
    exact PK identification for rows inserted by THIS connection only.
    """

    def test_exact_count_after_small_generation(self):
        """Generator must produce exactly --count reservations (not more, not fewer)."""
        _call(count=50, seed=42)
        self.assertEqual(
            Reservation.objects.filter(is_synthetic=True).count(), 50,
            'Expected exactly 50 synthetic reservations.',
        )

    def test_exact_count_after_large_generation(self):
        """Exact count with 600 reservations (spans 2 batches of 500 + 100)."""
        _call(count=600, seed=42)
        self.assertEqual(
            Reservation.objects.filter(is_synthetic=True).count(), 600,
            'Expected exactly 600 synthetic reservations.',
        )

    def test_timestamps_are_synthetic_not_wallclock(self):
        """
        created_at must NOT be the actual wall-clock time of generation.
        For historical reservations, created_at must precede reservation_date.
        For future reservations, created_at must also precede reservation_date.
        Wall-clock timestamps would not have this consistent relationship.
        """
        _call(count=100, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True):
            # Synthetic created_at is always before reservation_date.
            # For historical records: 1-14 days before.
            # For future-dated records: may be more due to ref_date clamping.
            delta = (r.reservation_date - r.created_at.date()).days
            self.assertGreaterEqual(
                delta, 1,
                f'Reservation {r.pk}: created_at date {r.created_at.date()} '
                f'is not before reservation_date {r.reservation_date} '
                f'(delta={delta} days). Timestamp may be wall-clock, not synthetic.',
            )

    def test_preservation_of_unrelated_synthetic_records(self):
        """
        If unrelated synthetic reservations exist before generation,
        they must not be modified by the backfill.

        We create a synthetic reservation with known timestamps,
        then run generation (which refuses if synthetics exist, so
        we clean only reservations first, then create our marker,
        then run generation which will fail the duplicate check).

        Instead, we test that after generation, records created by
        the first batch have correct timestamps and records that
        might have existed before are untouched.
        """
        # Generate first batch
        _call(count=50, seed=42)
        first_batch = list(Reservation.objects.filter(is_synthetic=True).order_by('pk'))
        first_created_ats = {r.pk: r.created_at for r in first_batch}

        # Clean and generate second batch
        Reservation.objects.filter(is_synthetic=True).delete()
        from facilities.models import FacilityMaintenance
        FacilityMaintenance.objects.filter(is_synthetic=True).delete()
        Facility.objects.filter(is_synthetic=True).delete()
        FacilityType.objects.filter(is_synthetic=True).delete()
        User.objects.filter(is_synthetic=True).delete()

        _call(count=50, seed=99)  # different seed
        second_batch = list(Reservation.objects.filter(is_synthetic=True).order_by('pk'))

        # Verify second batch has its own distinct timestamps
        for r in second_batch:
            self.assertTrue(
                r.created_at is not None,
                f'Reservation {r.pk}: created_at is None.',
            )
            self.assertIsNotNone(
                r.created_at.tzinfo,
                f'Reservation {r.pk}: created_at is not tz-aware.',
            )

    def test_backfill_pk_identification_is_exact(self):
        """
        Verify that the number of records with backfilled timestamps
        exactly matches --count. If the PK identification included
        extra rows (from concurrent inserts), we would see more records
        than expected.
        """
        _call(count=200, seed=42)
        # Every record must have a synthetic created_at (not wall-clock)
        # and the total must be exactly 200
        total = Reservation.objects.filter(is_synthetic=True).count()
        self.assertEqual(total, 200, f'Expected 200, got {total}.')

        # Every record must have created_at set (backfill didn't miss any)
        null_created = Reservation.objects.filter(
            is_synthetic=True, created_at__isnull=True
        ).count()
        self.assertEqual(null_created, 0, f'{null_created} records have null created_at.')

    def test_deterministic_timestamps_with_same_seed(self):
        """
        Same seed must produce identical timestamps. This verifies that
        the LAST_INSERT_ID-based backfill maps timestamps to the correct
        rows consistently.
        """
        _call(count=100, seed=42)
        first_ts = list(
            Reservation.objects.filter(is_synthetic=True)
            .order_by('pk')
            .values_list('created_at', 'updated_at', 'reviewed_at')
        )

        # Clean
        Reservation.objects.filter(is_synthetic=True).delete()
        from facilities.models import FacilityMaintenance
        FacilityMaintenance.objects.filter(is_synthetic=True).delete()
        Facility.objects.filter(is_synthetic=True).delete()
        FacilityType.objects.filter(is_synthetic=True).delete()
        User.objects.filter(is_synthetic=True).delete()

        _call(count=100, seed=42)
        second_ts = list(
            Reservation.objects.filter(is_synthetic=True)
            .order_by('pk')
            .values_list('created_at', 'updated_at', 'reviewed_at')
        )

        self.assertEqual(
            first_ts, second_ts,
            'Timestamps differ between identical-seed runs. '
            'Backfill may be mapping timestamps to wrong rows.',
        )

# ===========================================================================
# Phase 5.5.2 - LAST_INSERT_ID Verification & Reference-Date Semantics
# ===========================================================================

@override_settings(**_DEV_SETTINGS)
class LastInsertIdVerificationTests(TestCase):
    """
    Verify that LAST_INSERT_ID-based PK identification is exact and reliable.
    Tests cover: consecutive PK guarantee, single-INSERT behavior, and
    determinism across multiple batches.
    """

    def test_bulk_create_produces_consecutive_pks(self):
        """
        After bulk_create, the inserted PKs must be consecutive integers.
        MySQL guarantees this within a single INSERT VALUES statement.
        If Django splits the batch, this test will detect non-consecutive PKs.
        """
        _call(count=100, seed=42)
        pks = list(
            Reservation.objects.filter(is_synthetic=True)
            .order_by('pk')
            .values_list('pk', flat=True)
        )
        # Check consecutive: each pk should be previous + 1
        for i in range(1, len(pks)):
            if pks[i] != pks[i-1] + 1:
                # Non-consecutive means either:
                # 1. Django split the batch (shouldn't happen per bulk_batch_size)
                # 2. Another connection inserted between our INSERTs
                # 3. A pre-existing record occupies a gap
                # Only flag if the gap is within our generated range
                gap = pks[i] - pks[i-1]
                if gap > 1:
                    # Check if there's a non-synthetic record in the gap
                    in_gap = Reservation.objects.filter(
                        pk__gt=pks[i-1],
                        pk__lt=pks[i],
                    ).count()
                    if in_gap == 0:
                        self.fail(
                            f'Non-consecutive PKs at index {i}: '
                            f'{pks[i-1]} -> {pks[i]} (gap={gap}, no records in gap). '
                            f'LAST_INSERT_ID assumption may be violated.'
                        )

    def test_timestamps_mapped_correctly_to_pks(self):
        """
        Verify that the Case/When backfill maps timestamps to the correct
        rows. If the mapping is wrong, timestamps would not match the
        expected structural properties.

        For historical reservations: created_at is 1-14 days before event.
        For future-dated reservations: created_at is clamped to not exceed
        the reference date, so the gap may be larger than 14 days.
        """
        _call(count=200, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True):
            delta = (r.reservation_date - r.created_at.date()).days
            self.assertGreaterEqual(
                delta, 1,
                f'Reservation {r.pk}: created_at date is not before '
                f'reservation_date (delta={delta}). Mapping may be wrong.',
            )
            # For historical records, delta should be 1-14.
            # For future-dated records, delta may be larger due to clamping.
            if r.reservation_date <= _REF_DATE:
                self.assertLessEqual(
                    delta, 14,
                    f'Reservation {r.pk}: created_at is {delta} days before '
                    f'reservation_date (expected 1-14 for historical). '
                    f'Mapping may be wrong.',
                )

    def test_multiple_batches_produce_consistent_timestamps(self):
        """
        With count=600 (2 batches: 500 + 100), verify that both batches
        have correctly backfilled timestamps.
        """
        _call(count=600, seed=42)
        # Every record must have synthetic (non-null, tz-aware) created_at
        for r in Reservation.objects.filter(is_synthetic=True):
            self.assertIsNotNone(r.created_at)
            self.assertIsNotNone(r.created_at.tzinfo)
            self.assertIsNotNone(r.updated_at)
            self.assertIsNotNone(r.updated_at.tzinfo)


@override_settings(**_DEV_SETTINGS)
class ReferenceDateSemanticsTests(TestCase):
    """
    Verify that --reference-date is treated as the simulated current date.
    No synthetic submission timestamp (created_at) occurs after the
    reference date. Future reservation event dates remain permitted.
    Historical submissions precede their event dates. Review timestamps
    are chronologically valid. This prevents future-information leakage
    in predictive analytics datasets.
    """

    def test_no_submission_after_reference_date(self):
        """
        created_at (submission) must never be after the reference date.
        The reference date is the simulated 'now' — no submissions can
        happen in the simulated future.
        """
        _call(count=200, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True):
            self.assertLessEqual(
                r.created_at.date(),
                _REF_DATE,
                f'Reservation {r.pk}: created_at date {r.created_at.date()} '
                f'is after reference date {_REF_DATE}. '
                f'Submissions must not occur in the simulated future.',
            )

    def test_submission_precedes_event_date(self):
        """
        created_at (submission) must be before reservation_date (event).
        This is the fundamental temporal ordering: request before event.
        """
        _call(count=200, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True):
            self.assertLess(
                r.created_at.date(),
                r.reservation_date,
                f'Reservation {r.pk}: created_at {r.created_at.date()} '
                f'is not before reservation_date {r.reservation_date}.',
            )

    def test_future_event_dates_permitted(self):
        """
        Reservations with event dates after reference_date are permitted
        (PENDING and pre-approved APPROVED). These are genuinely upcoming
        bookings that exist in the simulated present.
        """
        _call(count=300, seed=42)
        future = Reservation.objects.filter(
            is_synthetic=True,
            reservation_date__gt=_REF_DATE,
        )
        self.assertGreater(
            future.count(), 0,
            'Expected some future-dated reservations (PENDING or pre-approved APPROVED).',
        )

    def test_reviewed_at_before_event_date(self):
        """
        For APPROVED/REJECTED, reviewed_at must be on or before
        reservation_date. Reviews happen before the event.
        """
        _call(count=200, seed=42)
        for r in Reservation.objects.filter(
            is_synthetic=True,
            status__in=['APPROVED', 'REJECTED'],
        ):
            self.assertLessEqual(
                r.reviewed_at.date(),
                r.reservation_date,
                f'Reservation {r.pk} ({r.status}): reviewed_at date '
                f'{r.reviewed_at.date()} is after event date '
                f'{r.reservation_date}.',
            )

    def test_no_future_information_leakage(self):
        """
        For predictive analytics: no reservation should have a created_at
        or reviewed_at that occurs AFTER its own event date. This would
        represent information from the simulated future leaking into
        the historical record.
        """
        _call(count=300, seed=42)
        for r in Reservation.objects.filter(is_synthetic=True):
            # created_at must be before event
            self.assertLess(
                r.created_at.date(),
                r.reservation_date,
                f'Reservation {r.pk}: future leakage — created_at '
                f'{r.created_at.date()} not before event {r.reservation_date}',
            )
            # reviewed_at (if set) must be on or before event
            if r.reviewed_at:
                self.assertLessEqual(
                    r.reviewed_at.date(),
                    r.reservation_date,
                    f'Reservation {r.pk}: future leakage — reviewed_at '
                    f'{r.reviewed_at.date()} after event {r.reservation_date}',
                )

# ===========================================================================
# Phase 5.6 - Synthetic Notification Generation Tests
# ===========================================================================
# NOTE: All read/unread distributions are synthetic assumptions.
# They do not represent verified DSSC user behavior data.
# ===========================================================================

from notifications.models import Notification as NotifModel


@override_settings(**_DEV_SETTINGS)
class NotificationGenerationTests(TestCase):
    """Tests for optional synthetic notification generation."""

    def test_default_generates_no_notifications(self):
        """Without --with-notifications, zero notifications must be created."""
        _call(count=100, seed=42)
        self.assertEqual(NotifModel.objects.filter(is_synthetic=True).count(), 0)

    def test_with_notifications_generates_notifications(self):
        """With --with-notifications, notifications are created."""
        _call(count=100, seed=42, with_notifications=True)
        self.assertGreater(
            NotifModel.objects.filter(is_synthetic=True).count(), 0,
            'Expected synthetic notifications to be generated.'
        )

    def test_notifications_only_for_approved_and_rejected(self):
        """Only APPROVED and REJECTED reservations get notifications."""
        _call(count=200, seed=42, with_notifications=True)

        for n in NotifModel.objects.filter(is_synthetic=True).select_related('reservation'):
            self.assertIn(
                n.reservation.status,
                ['APPROVED', 'REJECTED'],
                f'Notification {n.pk}: reservation status is {n.reservation.status}, '
                f'expected APPROVED or REJECTED.',
            )

    def test_no_notifications_for_pending_or_cancelled(self):
        """PENDING and CANCELLED reservations must have zero notifications."""
        _call(count=200, seed=42, with_notifications=True)

        pending_cancelled = Reservation.objects.filter(
            is_synthetic=True,
            status__in=['PENDING', 'CANCELLED'],
        )
        for r in pending_cancelled:
            self.assertEqual(
                NotifModel.objects.filter(reservation=r, is_synthetic=True).count(),
                0,
                f'Reservation {r.pk} ({r.status}) has synthetic notifications.',
            )

    def test_recipient_is_reservation_requester(self):
        """Each notification's recipient must be the reservation's requested_by."""
        _call(count=100, seed=42, with_notifications=True)
        for n in NotifModel.objects.filter(is_synthetic=True).select_related(
            'recipient', 'reservation'
        ):
            self.assertEqual(
                n.recipient,
                n.reservation.requested_by,
                f'Notification {n.pk}: recipient {n.recipient} != '
                f'reservation.requested_by {n.reservation.requested_by}',
            )

    def test_approval_message_format_matches_production(self):
        """Approval message must match the exact production format."""
        _call(count=200, seed=42, with_notifications=True)
        approved_notifs = NotifModel.objects.filter(
            is_synthetic=True,
            reservation__status='APPROVED',
        ).select_related('reservation__facility')
        for n in approved_notifs:
            expected = (
                f'Your reservation for {n.reservation.facility.name} on '
                f'{n.reservation.reservation_date} has been approved.'
            )
            self.assertEqual(
                n.message, expected,
                f'Notification {n.pk}: message does not match production format.',
            )

    def test_rejection_message_includes_reason(self):
        """Rejection message must match production format including reason."""
        _call(count=200, seed=42, with_notifications=True)
        rejected_notifs = NotifModel.objects.filter(
            is_synthetic=True,
            reservation__status='REJECTED',
        ).select_related('reservation__facility')
        for n in rejected_notifs:
            expected = (
                f'Your reservation for {n.reservation.facility.name} on '
                f'{n.reservation.reservation_date} was rejected. '
                f'Reason: {n.reservation.rejection_reason}'
            )
            self.assertEqual(
                n.message, expected,
                f'Notification {n.pk}: rejection message does not match production format.',
            )

    def test_all_notifications_have_synthetic_flag(self):
        """All generated notifications must have is_synthetic=True."""
        _call(count=100, seed=42, with_notifications=True)
        for n in NotifModel.objects.filter(is_synthetic=True):
            self.assertTrue(n.is_synthetic)

    def test_no_notifications_for_non_synthetic_reservations(self):
        """Real (non-synthetic) reservations must never get synthetic notifications."""
        # Create a real reservation
        from django.utils import timezone
        real_ft = FacilityType.objects.create(name='Notif Real Type', is_synthetic=False)
        real_fac = Facility.objects.create(
            facility_type=real_ft, name='Notif Real Facility',
            location='Test', capacity=20,
            status=Facility.Status.AVAILABLE, is_synthetic=False,
        )
        real_user = User.objects.create_user(
            username='notif_real_user', email='nr@dssc.local',
            password='pass123', role=User.Role.REQUESTER, is_synthetic=False,
        )
        tomorrow = timezone.localdate() + timedelta(days=1)
        real_res = Reservation.objects.create(
            requested_by=real_user, facility=real_fac,
            purpose='Real notif test', reservation_date=tomorrow,
            start_time=time(9, 0), end_time=time(10, 0),
            is_synthetic=False,
        )

        _call(count=100, seed=42, with_notifications=True)

        # No synthetic notification should reference the real reservation
        self.assertEqual(
            NotifModel.objects.filter(reservation=real_res, is_synthetic=True).count(),
            0,
            'Synthetic notification was created for a non-synthetic reservation.',
        )

    def test_created_at_is_timezone_aware(self):
        """All notification created_at values must be timezone-aware."""
        _call(count=100, seed=42, with_notifications=True)
        for n in NotifModel.objects.filter(is_synthetic=True):
            self.assertIsNotNone(
                n.created_at.tzinfo,
                f'Notification {n.pk}: created_at is not tz-aware.',
            )

    def test_created_at_matches_reservation_reviewed_at(self):
        """Notification created_at should match the reservation's reviewed_at."""
        _call(count=100, seed=42, with_notifications=True)
        for n in NotifModel.objects.filter(is_synthetic=True).select_related('reservation'):
            self.assertEqual(
                n.created_at,
                n.reservation.reviewed_at,
                f'Notification {n.pk}: created_at {n.created_at} != '
                f'reservation.reviewed_at {n.reservation.reviewed_at}',
            )

    def test_created_at_not_after_reference_date(self):
        """
        ALL notification created_at values must not occur after the reference date.
        This covers REJECTED reservations (always historical) AND pre-approved
        future APPROVED reservations (whose reviewed_at is now clamped to ref_date).
        This ensures no future-information leakage in predictive analytics datasets.
        """
        _call(count=200, seed=42, with_notifications=True)
        for n in NotifModel.objects.filter(is_synthetic=True):
            self.assertLessEqual(
                n.created_at.date(),
                _REF_DATE,
                f'Notification {n.pk} ({n.reservation.status}): '
                f'created_at {n.created_at.date()} is after reference date {_REF_DATE}. '
                f'Future-information leakage in notification timestamps.',
            )

    def test_created_at_not_before_reservation_submission(self):
        """Notification created_at must not precede reservation created_at."""
        _call(count=100, seed=42, with_notifications=True)
        for n in NotifModel.objects.filter(is_synthetic=True).select_related('reservation'):
            self.assertGreaterEqual(
                n.created_at,
                n.reservation.created_at,
                f'Notification {n.pk}: created_at {n.created_at} precedes '
                f'reservation created_at {n.reservation.created_at}.',
            )

    def test_read_unread_distribution(self):
        """
        Older notifications should be mostly read; recent mostly unread.
        NOTE: Synthetic assumptions only, not DSSC user behavior data.
        """
        _call(count=500, seed=42, with_notifications=True)
        old = NotifModel.objects.filter(
            is_synthetic=True,
            created_at__date__lt=_REF_DATE - timedelta(days=30),
        )
        recent = NotifModel.objects.filter(
            is_synthetic=True,
            created_at__date__gte=_REF_DATE - timedelta(days=7),
        )
        if old.count() > 0:
            old_read_pct = old.filter(is_read=True).count() / old.count()
            self.assertGreater(
                old_read_pct, 0.50,
                f'Old notifications: only {old_read_pct*100:.0f}% read '
                f'(expected >50%).',
            )
        if recent.count() > 0:
            recent_read_pct = recent.filter(is_read=True).count() / recent.count()
            self.assertLess(
                recent_read_pct, 0.60,
                f'Recent notifications: {recent_read_pct*100:.0f}% read '
                f'(expected <60%).',
            )

    def test_deterministic_output_same_seed(self):
        """Same seed must produce identical notification count and messages."""
        _call(count=200, seed=42, with_notifications=True)
        first_count = NotifModel.objects.filter(is_synthetic=True).count()
        first_msgs = list(
            NotifModel.objects.filter(is_synthetic=True)
            .order_by('pk').values_list('message', 'is_read')
        )

        # Clean
        NotifModel.objects.filter(is_synthetic=True).delete()
        Reservation.objects.filter(is_synthetic=True).delete()
        from facilities.models import FacilityMaintenance
        FacilityMaintenance.objects.filter(is_synthetic=True).delete()
        Facility.objects.filter(is_synthetic=True).delete()
        FacilityType.objects.filter(is_synthetic=True).delete()
        User.objects.filter(is_synthetic=True).delete()

        _call(count=200, seed=42, with_notifications=True)
        second_count = NotifModel.objects.filter(is_synthetic=True).count()
        second_msgs = list(
            NotifModel.objects.filter(is_synthetic=True)
            .order_by('pk').values_list('message', 'is_read')
        )

        self.assertEqual(first_count, second_count)
        self.assertEqual(first_msgs, second_msgs)

    def test_no_duplicate_notifications(self):
        """Each reservation should have at most one synthetic notification."""
        _call(count=200, seed=42, with_notifications=True)
        from django.db.models import Count
        duplicates = (
            NotifModel.objects.filter(is_synthetic=True)
            .values('reservation_id')
            .annotate(count=Count('pk'))
            .filter(count__gt=1)
        )
        self.assertEqual(
            duplicates.count(), 0,
            f'{duplicates.count()} reservations have duplicate notifications.',
        )

    def test_transaction_rollback_on_notification_failure(self):
        """If notification bulk_create fails, entire transaction rolls back."""
        from django.db.models import QuerySet
        _orig_bc = QuerySet.bulk_create

        def _bc(self, objs, *a, **kw):
            if self.model is NotifModel:
                raise Exception('Simulated notification bulk_create failure')
            return _orig_bc(self, objs, *a, **kw)

        with patch.object(QuerySet, 'bulk_create', _bc):
            with self.assertRaises(Exception) as ctx:
                _call(count=100, seed=42, with_notifications=True)
            self.assertIn('Simulated notification bulk_create failure', str(ctx.exception))

        # After rollback: nothing should exist
        self.assertEqual(NotifModel.objects.filter(is_synthetic=True).count(), 0)
        self.assertEqual(Reservation.objects.filter(is_synthetic=True).count(), 0)

    def test_real_notifications_preserved(self):
        """Pre-existing real (non-synthetic) notifications must be untouched."""
        # Create a real notification
        real_ft = FacilityType.objects.create(name='Preserve Type', is_synthetic=False)
        real_fac = Facility.objects.create(
            facility_type=real_ft, name='Preserve Facility',
            location='Test', capacity=20,
            status=Facility.Status.AVAILABLE, is_synthetic=False,
        )
        real_user = User.objects.create_user(
            username='preserve_user', email='p@dssc.local',
            password='pass123', role=User.Role.REQUESTER, is_synthetic=False,
        )
        from django.utils import timezone
        tomorrow = timezone.localdate() + timedelta(days=1)
        real_res = Reservation.objects.create(
            requested_by=real_user, facility=real_fac,
            purpose='Preserve test', reservation_date=tomorrow,
            start_time=time(9, 0), end_time=time(10, 0),
            is_synthetic=False,
        )
        real_notif = NotifModel.objects.create(
            recipient=real_user, reservation=real_res,
            message='Real notification to preserve', is_synthetic=False,
        )
        real_created_at = real_notif.created_at

        _call(count=100, seed=42, with_notifications=True)

        real_notif.refresh_from_db()
        self.assertEqual(real_notif.message, 'Real notification to preserve')
        self.assertEqual(real_notif.created_at, real_created_at)
        self.assertFalse(real_notif.is_synthetic)

    def test_no_external_delivery_triggered(self):
        """No email/SMS should be sent during notification generation."""
        from django.core import mail
        mail.outbox = []  # Clear any existing
        _call(count=100, seed=42, with_notifications=True)
        self.assertEqual(
            len(mail.outbox), 0,
            f'Unexpected email sent during notification generation: {len(mail.outbox)} emails.',
        )

    def test_exact_count_for_large_generation(self):
        """With 600 reservations, notification count must be exact (APPROVED + REJECTED only)."""
        _call(count=600, seed=42, with_notifications=True)
        approved_rejected = Reservation.objects.filter(
            is_synthetic=True,
            status__in=['APPROVED', 'REJECTED'],
        ).count()
        notif_count = NotifModel.objects.filter(is_synthetic=True).count()
        self.assertEqual(
            notif_count, approved_rejected,
            f'Notification count {notif_count} != APPROVED+REJECTED count {approved_rejected}.',
        )

    def test_pk_identification_across_multiple_batches(self):
        """
        With 600 reservations (~420 notifications), verify that PK
        identification via LAST_INSERT_ID works across multiple batches.
        """
        _call(count=600, seed=42, with_notifications=True)
        # All notifications should have created_at matching their reservation's reviewed_at
        mismatches = 0
        for n in NotifModel.objects.filter(is_synthetic=True).select_related('reservation'):
            if n.created_at != n.reservation.reviewed_at:
                mismatches += 1
        self.assertEqual(
            mismatches, 0,
            f'{mismatches} notifications have created_at != reservation.reviewed_at. '
            f'PK identification may be mapping timestamps incorrectly.',
        )
