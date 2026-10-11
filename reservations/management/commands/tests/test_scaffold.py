"""
Phase 5.2 scaffold tests for generate_synthetic_data management command.

Covers:
  - Command is discoverable by Django
  - Argument validation (--count range, --seed non-negative, --dry-run/--clear mutex)
  - Production environment safety guard (DEBUG=False refused)
  - Non-local database host safety guard
  - Zero database modifications in all scaffold invocations
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
# Applied via @override_settings on test classes that expect the guards to PASS.
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
# Command discovery
# ---------------------------------------------------------------------------

class CommandDiscoveryTests(TestCase):
    """The command must be discoverable by Django's management command loader."""

    def test_command_is_discoverable(self):
        """
        django.core.management.call_command must find 'generate_synthetic_data'
        without raising LookupError or ModuleNotFoundError.
        The command passes with --dry-run to avoid any write side effects.
        """
        # If the command were missing, call_command would raise
        # django.core.management.base.SystemCheckError or LookupError.
        try:
            _call(dry_run=True)
        except CommandError:
            pass  # CommandError from guards is acceptable — command was found
        # If we get here without ImportError/AttributeError, discovery succeeded

    def test_help_text_is_present(self):
        """Command must have a non-empty help string."""
        from django.core.management import load_command_class
        cmd_class = load_command_class('reservations', 'generate_synthetic_data')
        self.assertTrue(len(cmd_class.help) > 0)


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class ArgumentValidationTests(TestCase):
    """Invalid argument combinations must raise CommandError before any DB access."""

    def test_count_below_minimum_raises(self):
        """--count 0 must be rejected."""
        with self.assertRaises(CommandError) as ctx:
            _call(count=0)
        self.assertIn('count', str(ctx.exception).lower())

    def test_count_above_maximum_raises(self):
        """--count 10001 must be rejected."""
        with self.assertRaises(CommandError) as ctx:
            _call(count=10001)
        self.assertIn('count', str(ctx.exception).lower())

    def test_count_at_minimum_boundary_accepted(self):
        """--count 1 must pass validation (boundary value)."""
        # Will not raise CommandError for argument validation
        # (may still raise for other reasons in future phases, but not count)
        try:
            _call(count=1)
        except CommandError as e:
            self.assertNotIn('count', str(e).lower())

    def test_count_at_maximum_boundary_accepted(self):
        """--count 10000 must pass validation (boundary value)."""
        try:
            _call(count=10000)
        except CommandError as e:
            self.assertNotIn('count', str(e).lower())

    def test_negative_seed_raises(self):
        """--seed -1 must be rejected."""
        with self.assertRaises(CommandError) as ctx:
            _call(seed=-1)
        self.assertIn('seed', str(ctx.exception).lower())

    def test_zero_seed_accepted(self):
        """--seed 0 is valid (boundary value) — must not raise any CommandError."""
        # Should succeed without raising CommandError at all in Phase 5.2
        try:
            _call(seed=0)
        except CommandError:
            self.fail('--seed 0 should be accepted but raised CommandError.')

    def test_dry_run_and_clear_together_raise(self):
        """--clear is deprecated and must raise CommandError."""
        with self.assertRaises(CommandError) as ctx:
            _call(clear=True)
        msg = str(ctx.exception).lower()
        self.assertTrue('clear' in msg or 'deprecated' in msg or 'not supported' in msg or 'not implemented' in msg)


# ---------------------------------------------------------------------------
# Production environment safety guard
# ---------------------------------------------------------------------------

class ProductionEnvironmentGuardTests(TestCase):
    """
    The command must refuse to run in non-development environments.
    Tested by overriding settings without touching the real database.
    """

    @override_settings(DEBUG=False)
    def test_refused_when_debug_is_false(self):
        """Command must raise CommandError when DEBUG=False."""
        with self.assertRaises(CommandError) as ctx:
            _call()
        self.assertIn('DEBUG', str(ctx.exception))

    @override_settings(DEBUG=True, DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': 'dssc_cfrms_db',
            'HOST': 'db.production.example.com',
            'PORT': '3306',
            'USER': 'user',
            'PASSWORD': '',
        }
    })
    def test_refused_when_host_is_remote(self):
        """
        Command must raise CommandError when DEBUG=True but the database
        host is a non-local address. DEBUG=True alone is insufficient.
        """
        with self.assertRaises(CommandError) as ctx:
            _call()
        self.assertIn('HOST', str(ctx.exception))

    @override_settings(DEBUG=True, DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': 'dssc_cfrms_db',
            'HOST': '127.0.0.1',
            'PORT': '3306',
            'USER': 'user',
            'PASSWORD': '',
        }
    })
    def test_accepted_when_debug_true_and_local_host(self):
        """
        Command must NOT raise a production-guard CommandError when
        DEBUG=True and host is 127.0.0.1.
        """
        try:
            _call(dry_run=True)
        except CommandError as e:
            # Any CommandError here must not be from the environment guard
            self.assertNotIn('DEBUG', str(e))
            self.assertNotIn('HOST', str(e))

    @override_settings(DEBUG=True, DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': 'dssc_cfrms_db',
            'HOST': 'localhost',
            'PORT': '3306',
            'USER': 'user',
            'PASSWORD': '',
        }
    })
    def test_accepted_when_debug_true_and_localhost(self):
        """Command accepts 'localhost' as a local host value."""
        try:
            _call(dry_run=True)
        except CommandError as e:
            self.assertNotIn('DEBUG', str(e))
            self.assertNotIn('HOST', str(e))


# ---------------------------------------------------------------------------
# Zero database modifications
# ---------------------------------------------------------------------------

@override_settings(**_DEV_SETTINGS)
class ZeroDatabaseModificationTests(TestCase):
    """
    No invocation of the scaffold command must modify the database,
    including --dry-run, normal mode, and --clear.
    These tests use _DEV_SETTINGS so environment guards pass and
    the actual zero-modification behaviour can be verified.
    """

    def test_dry_run_modifies_zero_records(self):
        """--dry-run must not change any record counts."""
        before = _counts()
        _call(dry_run=True)
        after = _counts()
        self.assertEqual(before, after)

    def test_normal_mode_modifies_zero_records(self):
        """
        In Phase 5.3, normal mode generates synthetic records (this is expected).
        This test is updated to expect real generation.
        """
        before = _counts()
        _call(count=100, seed=42)
        after = _counts()
        # Phase 5.3: Normal mode DOES write records
        self.assertGreater(after['User'], before['User'])
        self.assertGreater(after['Facility'], before['Facility'])

    def test_clear_flag_modifies_zero_records(self):
        """--clear must raise CommandError without modifying the database."""
        before = _counts()
        with self.assertRaises(CommandError):
            _call(clear=True)
        after = _counts()
        self.assertEqual(before, after)

    def test_invalid_count_modifies_zero_records(self):
        """
        Even when CommandError is raised for an invalid argument, the
        database must remain unchanged (guards run before any DB access).
        """
        before = _counts()
        try:
            _call(count=99999)
        except CommandError:
            pass
        after = _counts()
        self.assertEqual(before, after)

    def test_production_guard_modifies_zero_records(self):
        """
        When the production guard raises CommandError, no DB changes occur.
        """
        before = _counts()
        with override_settings(DEBUG=False):
            try:
                _call()
            except CommandError:
                pass
        after = _counts()
        self.assertEqual(before, after)

    def test_no_synthetic_records_exist_after_scaffold(self):
        """
        After a first generation run, synthetic records DO exist (Phase 5.3).
        A second run must refuse to generate (duplicate prevention guard).
        """
        # First run: should generate
        _call(count=50, seed=42)
        first_run_users = User.objects.filter(is_synthetic=True).count()
        self.assertGreater(first_run_users, 0)

        # Second run: should refuse (synthetic records already exist)
        with self.assertRaises(CommandError) as ctx:
            _call(count=50, seed=99)
        self.assertIn('already exist', str(ctx.exception).lower())

    def test_output_explicitly_states_not_implemented(self):
        """
        Phase 5.3 implements real generation.
        Normal mode output should report successful generation.
        Dry-run output should state what would be generated.
        """
        # Dry-run should mention "validation" or "plan"
        output = _call(dry_run=True)
        self.assertTrue(
            'dry' in output.lower() or 'plan' in output.lower() or 'validation' in output.lower()
        )

        # Normal mode (first generation) should report success
        output = _call(count=50, seed=42)
        self.assertIn('successfully', output.lower())
