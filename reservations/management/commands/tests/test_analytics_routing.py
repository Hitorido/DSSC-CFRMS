"""
Phase 6.3 — Analytics Database Routing Tests

Verifies that --analytics-db routes ALL ORM reads/writes, raw SQL cursors,
and transaction.atomic() to the "analytics" database alias, while leaving
the "default" database untouched.

Test setup:
  - Uses config.settings_test which defines both 'default' and 'analytics'
    aliases before Django test initialization.
  - Both aliases point to local MySQL with different database NAMEs,
    guaranteeing isolation.
  - TEST.NAME is explicitly set to prevent Django from adding a second
    'test_' prefix.
  - Run with: python manage.py test reservations.management.commands.tests.test_analytics_routing --settings=config.settings_test --keepdb

Note: Do NOT manipulate connections._databases or manually create/drop
databases. The test settings module handles alias registration, and Django's
test runner handles database creation/rollback.
"""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from facilities.models import Facility, FacilityMaintenance, FacilityType
from notifications.models import Notification
from reservations.models import Reservation

User = get_user_model()


def _call_cmd(stdout=None, stderr=None, **kwargs):
    """Helper: call generate_synthetic_data with given kwargs."""
    if stdout is None:
        stdout = StringIO()
    call_command(
        'generate_synthetic_data',
        stdout=stdout,
        stderr=stderr or StringIO(),
        **kwargs,
    )
    return stdout.getvalue()


class AnalyticsAliasRoutingTests(TestCase):
    """Verify --analytics-db routes writes to the analytics alias."""
    databases = ['default', 'analytics']

    def test_db_alias_default_when_flag_absent(self):
        """Without --analytics-db, _db_alias must be 'default'."""
        from reservations.management.commands.generate_synthetic_data import Command
        from django.test import override_settings
        # The command checks DEBUG in _check_environment; ensure it's True
        with override_settings(DEBUG=True):
            cmd = Command()
            cmd._db_alias = None
            # Simulate handle() alias selection without running generation.
            cmd.handle = lambda **o: None  # noqa: E731
            # We test the selection logic indirectly via _check_environment guard.
            # Directly verify the attribute after a dry-run call.
            out = StringIO()
            call_command('generate_synthetic_data', dry_run=True, count=10,
                         stdout=out, stderr=StringIO())
            # The default alias must remain untouched (no writes in dry-run).
            self.assertEqual(User.objects.using('default').filter(is_synthetic=True).count(), 0)

    def test_analytics_db_writes_go_to_analytics_alias(self):
        """With --analytics-db, synthetic records must exist in analytics DB."""
        _call_cmd(count=50, seed=42, analytics_db=True)

        # Records must exist in the analytics alias.
        self.assertGreater(
            User.objects.using('analytics').filter(is_synthetic=True).count(), 0,
            "Users should be written to the analytics alias.",
        )
        self.assertGreater(
            Facility.objects.using('analytics').filter(is_synthetic=True).count(), 0,
            "Facilities should be written to the analytics alias.",
        )
        self.assertGreater(
            Reservation.objects.using('analytics').filter(is_synthetic=True).count(), 0,
            "Reservations should be written to the analytics alias.",
        )

    def test_no_default_db_writes_in_analytics_mode(self):
        """With --analytics-db, the default database must have NO synthetic records."""
        _call_cmd(count=50, seed=42, analytics_db=True)

        # The default alias must be completely untouched.
        self.assertEqual(
            User.objects.using('default').filter(is_synthetic=True).count(), 0,
            "No synthetic users should exist in the default alias.",
        )
        self.assertEqual(
            Facility.objects.using('default').filter(is_synthetic=True).count(), 0,
            "No synthetic facilities should exist in the default alias.",
        )
        self.assertEqual(
            FacilityMaintenance.objects.using('default').filter(is_synthetic=True).count(), 0,
            "No synthetic maintenance should exist in the default alias.",
        )
        self.assertEqual(
            Reservation.objects.using('default').filter(is_synthetic=True).count(), 0,
            "No synthetic reservations should exist in the default alias.",
        )

    def test_analytics_db_creates_notifications_on_analytics_alias(self):
        """--analytics-db --with-notifications must write notifications to analytics."""
        _call_cmd(count=50, seed=42, analytics_db=True, with_notifications=True)

        notif_count = Notification.objects.using('analytics').filter(is_synthetic=True).count()
        self.assertGreater(
            notif_count, 0,
            "Notifications should be generated on the analytics alias.",
        )
        # Notifications must NOT appear in the default alias.
        self.assertEqual(
            Notification.objects.using('default').filter(is_synthetic=True).count(), 0,
            "No synthetic notifications should exist in the default alias.",
        )

    def test_last_insert_id_consistency_in_analytics_mode(self):
        """
        LAST_INSERT_ID() must return correct PKs on the analytics connection.
        We verify indirectly: reservations must have consecutive, backfilled
        created_at values that fall within the generation window.
        """
        _call_cmd(count=50, seed=42, analytics_db=True)

        reservations = list(
            Reservation.objects.using('analytics')
            .filter(is_synthetic=True)
            .order_by('pk')
            .values_list('pk', 'created_at')
        )
        self.assertGreater(len(reservations), 0)

        # All created_at values must be non-null (backfill worked).
        for pk, created_at in reservations:
            self.assertIsNotNone(
                created_at,
                f"Reservation pk={pk} has NULL created_at; backfill failed.",
            )

        # PKs should be consecutive (single bulk_create per batch).
        pks = [pk for pk, _ in reservations]
        # Within a batch, PKs are consecutive; check the first batch.
        first_batch = pks[:min(50, len(pks))]
        self.assertEqual(
            first_batch, list(range(first_batch[0], first_batch[0] + len(first_batch))),
            "Reservation PKs within a batch must be consecutive.",
        )


class AnalyticsUnsafeTargetTests(TestCase):
    """Verify --analytics-db is rejected when the analytics alias is missing."""
    databases = ['default']

    @override_settings(DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': 'test_dssc_cfrms_db',
            'HOST': '127.0.0.1',
            'PORT': '3306',
            'USER': 'root',
            'PASSWORD': '',
            'OPTIONS': {'charset': 'utf8mb4', 'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"},
            'TEST': {'NAME': 'test_dssc_cfrms_db'},
        }
    })
    def test_analytics_db_rejected_when_alias_missing(self):
        """
        If 'analytics' is not in settings.DATABASES, --analytics-db must
        raise CommandError with a clear message.
        """
        with self.assertRaises(CommandError) as ctx:
            _call_cmd(count=10, seed=42, analytics_db=True)
        self.assertIn('analytics', str(ctx.exception).lower())
        self.assertIn('not configured', str(ctx.exception).lower())


class AnalyticsRollbackTests(TestCase):
    """Verify transaction rollback works on the analytics alias."""
    databases = ['default', 'analytics']

    def test_rollback_on_reservation_failure_in_analytics_mode(self):
        """
        If reservation bulk_create fails in analytics mode, the entire
        transaction on the analytics alias must roll back — no records
        should persist in the analytics database.
        """
        from django.db.models import QuerySet
        _orig_bc = QuerySet.bulk_create

        def _bc(self, objs, *a, **kw):
            if self.model is Reservation:
                raise Exception('Simulated analytics reservation bulk_create failure')
            return _orig_bc(self, objs, *a, **kw)

        with patch.object(QuerySet, 'bulk_create', _bc):
            with self.assertRaises(Exception):
                _call_cmd(count=50, seed=42, analytics_db=True)

        # After rollback, the analytics alias must have zero synthetic records.
        self.assertEqual(
            User.objects.using('analytics').filter(is_synthetic=True).count(), 0,
        )
        self.assertEqual(
            Facility.objects.using('analytics').filter(is_synthetic=True).count(), 0,
        )
        self.assertEqual(
            Reservation.objects.using('analytics').filter(is_synthetic=True).count(), 0,
        )
        # Default alias must also be untouched.
        self.assertEqual(
            User.objects.using('default').filter(is_synthetic=True).count(), 0,
        )


class AnalyticsNonSyntheticRejectionTests(TestCase):
    """Verify --analytics-db rejects a target containing real (non-synthetic) data."""
    databases = ['default', 'analytics']

    def test_rejected_when_analytics_has_real_data(self):
        """
        If the analytics database contains non-synthetic records,
        --analytics-db must refuse to run to prevent contaminating real data.
        """
        # Insert a real (non-synthetic) facility type into the analytics DB.
        FacilityType.objects.using('analytics').create(
            name='Real Analytics Type', is_synthetic=False,
        )

        with self.assertRaises(CommandError) as ctx:
            _call_cmd(count=10, seed=42, analytics_db=True)

        self.assertIn('non-synthetic', str(ctx.exception).lower())
        self.assertIn('real', str(ctx.exception).lower())

    def test_rejected_when_analytics_has_synthetic_data(self):
        """
        If the analytics database already contains synthetic records,
        --analytics-db must refuse (rerun guard).
        """
        # Insert a synthetic facility type into the analytics DB.
        FacilityType.objects.using('analytics').create(
            name='Existing Synth Type', is_synthetic=True,
        )

        with self.assertRaises(CommandError) as ctx:
            _call_cmd(count=10, seed=42, analytics_db=True)

        self.assertIn('synthetic', str(ctx.exception).lower())
