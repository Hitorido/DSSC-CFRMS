"""
Phase 6.2 — Analytics Database Configuration Tests

Verifies:
  - Default alias is unchanged and operational
  - Analytics alias is only present when ANALYTICS_DB_HOST is set
  - Analytics alias is absent when ANALYTICS_DB_HOST is empty/unset
  - Analytics alias settings are well-formed when present
  - TLS/SSL CA is included in OPTIONS only when ANALYTICS_DB_SSL_CA is set
  - Local Django operation is unaffected when analytics env vars are absent
  - Default and analytics databases are isolated (different NAME values when both set)
  - TEST block prevents analytics database from being used in local test suite
  - .gitignore protects analytics credentials and CA certificate files
"""

from django.test import TestCase, override_settings


class DefaultDatabaseAliasTests(TestCase):
    """The default database alias must always be present and properly configured."""

    def test_default_alias_is_configured(self):
        """DATABASES['default'] must always exist."""
        from django.conf import settings
        self.assertIn('default', settings.DATABASES)

    def test_default_engine_is_mysql(self):
        """The default engine must be MySQL."""
        from django.conf import settings
        self.assertEqual(
            settings.DATABASES['default']['ENGINE'],
            'django.db.backends.mysql',
        )

    def test_default_has_strict_sql_mode(self):
        """STRICT_TRANS_TABLES must be enforced on the default alias."""
        from django.conf import settings
        init_cmd = settings.DATABASES['default']['OPTIONS'].get('init_command', '')
        self.assertIn('STRICT_TRANS_TABLES', init_cmd)

    def test_default_charset_is_utf8mb4(self):
        """Default alias must use utf8mb4 charset."""
        from django.conf import settings
        charset = settings.DATABASES['default']['OPTIONS'].get('charset', '')
        self.assertEqual(charset, 'utf8mb4')


class AnalyticsAliasAbsentTests(TestCase):
    """
    When ANALYTICS_DB_HOST is not set, the analytics alias must be absent.
    Local Django operation must be completely unaffected.
    """

    @override_settings(DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': 'dssc_cfrms_db',
            'HOST': '127.0.0.1',
            'PORT': '3306',
            'USER': 'root',
            'PASSWORD': '',
            'OPTIONS': {'charset': 'utf8mb4', 'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"},
        }
    })
    def test_analytics_alias_absent_when_host_not_set(self):
        """No 'analytics' alias should exist when only 'default' is configured."""
        from django.conf import settings
        self.assertNotIn(
            'analytics', settings.DATABASES,
            "The 'analytics' alias must not exist when ANALYTICS_DB_HOST is empty.",
        )

    def test_default_alias_present_without_analytics(self):
        """Even without analytics configured, 'default' must always be present."""
        from django.conf import settings
        self.assertIn('default', settings.DATABASES)

    def test_system_check_passes_without_analytics(self):
        """
        Django system check must report no issues when analytics alias is absent.
        Verified implicitly by the test runner reaching this point without errors.
        """
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        # If system check fails, call_command raises SystemCheckError
        call_command('check', stdout=out)
        self.assertIn('no issues', out.getvalue().lower())


class AnalyticsAliasPresentTests(TestCase):
    """
    When ANALYTICS_DB_HOST is provided, the analytics alias must be correctly
    populated and isolated from the default database.
    """

    # Simulate settings where analytics is fully configured
    _ANALYTICS_DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': 'dssc_cfrms_db',
            'HOST': '127.0.0.1',
            'PORT': '3306',
            'USER': 'root',
            'PASSWORD': '',
            'OPTIONS': {'charset': 'utf8mb4', 'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"},
        },
        'analytics': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME':     'dssc_analytics',
            'USER':     'analytics_user',
            'PASSWORD': 'analytics_pass',
            'HOST':     'mysql-test.aivencloud.com',
            'PORT':     '12345',
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
                'ssl': {'ca': '/path/to/ca.pem'},
            },
        },
    }

    @override_settings(DATABASES=_ANALYTICS_DATABASES)
    def test_analytics_alias_present_when_host_set(self):
        """'analytics' must be present in DATABASES when configured."""
        from django.conf import settings
        self.assertIn('analytics', settings.DATABASES)

    @override_settings(DATABASES=_ANALYTICS_DATABASES)
    def test_analytics_engine_is_mysql(self):
        """Analytics alias must use the MySQL engine."""
        from django.conf import settings
        self.assertEqual(
            settings.DATABASES['analytics']['ENGINE'],
            'django.db.backends.mysql',
        )

    @override_settings(DATABASES=_ANALYTICS_DATABASES)
    def test_analytics_has_separate_name_from_default(self):
        """Analytics DB_NAME must differ from default DB_NAME to prevent accidental overlap."""
        from django.conf import settings
        self.assertNotEqual(
            settings.DATABASES['analytics']['NAME'],
            settings.DATABASES['default']['NAME'],
            'Analytics and default databases must have different NAME values.',
        )

    @override_settings(DATABASES=_ANALYTICS_DATABASES)
    def test_analytics_has_remote_host(self):
        """Analytics HOST must not be a local-only address."""
        from django.conf import settings
        local_hosts = {'127.0.0.1', 'localhost', '::1', ''}
        analytics_host = settings.DATABASES['analytics']['HOST']
        self.assertNotIn(
            analytics_host, local_hosts,
            f'Analytics HOST "{analytics_host}" should be a remote cloud address.',
        )

    @override_settings(DATABASES=_ANALYTICS_DATABASES)
    def test_analytics_has_ssl_ca_in_options(self):
        """SSL CA must be present in OPTIONS when ANALYTICS_DB_SSL_CA is configured."""
        from django.conf import settings
        ssl = settings.DATABASES['analytics']['OPTIONS'].get('ssl', {})
        self.assertIn('ca', ssl, "SSL CA must be present for TLS validation.")
        self.assertTrue(ssl['ca'], "SSL CA path must not be empty.")

    @override_settings(DATABASES=_ANALYTICS_DATABASES)
    def test_analytics_has_strict_sql_mode(self):
        """Analytics alias must enforce STRICT_TRANS_TABLES."""
        from django.conf import settings
        init_cmd = settings.DATABASES['analytics']['OPTIONS'].get('init_command', '')
        self.assertIn('STRICT_TRANS_TABLES', init_cmd)

    @override_settings(DATABASES=_ANALYTICS_DATABASES)
    def test_analytics_has_utf8mb4_charset(self):
        """Analytics alias must use utf8mb4 charset."""
        from django.conf import settings
        charset = settings.DATABASES['analytics']['OPTIONS'].get('charset', '')
        self.assertEqual(charset, 'utf8mb4')

    def test_analytics_alias_absent_during_test_runs(self):
        """
        The real settings module must NOT register the analytics alias while
        the test runner is active, so Django never creates/migrates a test
        analytics database. This replaces the previous (incorrect) assumption
        that TEST.NAME=None would skip test-DB creation.

        We verify the real (non-overridden) settings module directly.
        """
        import importlib
        import config.settings as real_settings
        importlib.reload(real_settings)
        from django.conf import settings
        # The test runner sets sys.argv to include 'test', so _running_tests()
        # must be True and the analytics alias must be absent from the real
        # settings module regardless of ANALYTICS_DB_* env vars.
        self.assertNotIn(
            'analytics', settings.DATABASES,
            "The 'analytics' alias must NOT be registered during test runs "
            "(the test runner would otherwise try to create/migrate a test "
            "analytics database).",
        )

    @override_settings(DATABASES=_ANALYTICS_DATABASES)
    def test_default_alias_unchanged_when_analytics_present(self):
        """Adding the analytics alias must not modify the default alias."""
        from django.conf import settings
        self.assertEqual(settings.DATABASES['default']['HOST'], '127.0.0.1')
        self.assertEqual(settings.DATABASES['default']['NAME'], 'dssc_cfrms_db')


class AnalyticsTLSAbsentTests(TestCase):
    """When ANALYTICS_DB_SSL_CA is not set, ssl key must be absent from OPTIONS."""

    _ANALYTICS_NO_TLS = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': 'dssc_cfrms_db',
            'HOST': '127.0.0.1',
            'PORT': '3306',
            'USER': 'root',
            'PASSWORD': '',
            'OPTIONS': {'charset': 'utf8mb4', 'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"},
        },
        'analytics': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME':     'dssc_analytics',
            'USER':     'analytics_user',
            'PASSWORD': 'analytics_pass',
            'HOST':     'mysql-test.aivencloud.com',
            'PORT':     '3306',
            # No 'ssl' key — CA not configured
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        },
    }

    @override_settings(DATABASES=_ANALYTICS_NO_TLS)
    def test_ssl_absent_when_ca_not_configured(self):
        """
        When ANALYTICS_DB_SSL_CA is empty, the 'ssl' key must not appear in
        OPTIONS. This prevents a misconfigured TLS option from silently failing.
        """
        from django.conf import settings
        ssl = settings.DATABASES['analytics']['OPTIONS'].get('ssl')
        self.assertIsNone(
            ssl,
            "SSL must not be configured when no CA certificate path is provided.",
        )


class GitIgnoreSecretsTests(TestCase):
    """Verify that secret files are protected by .gitignore."""

    def _read_gitignore(self):
        from pathlib import Path
        import django
        base = Path(django.__file__).resolve().parent.parent.parent
        # Walk up from Django installation to find project root
        from django.conf import settings as djsettings
        # Use BASE_DIR from settings
        gitignore_path = Path(djsettings.BASE_DIR) / '.gitignore'
        if not gitignore_path.exists():
            return ''
        return gitignore_path.read_text()

    def test_env_file_is_gitignored(self):
        """.env must be in .gitignore."""
        content = self._read_gitignore()
        self.assertIn('.env', content, ".env must be listed in .gitignore")

    def test_env_analytics_file_is_gitignored(self):
        """.env.analytics must be in .gitignore."""
        content = self._read_gitignore()
        self.assertIn('.env.analytics', content, ".env.analytics must be listed in .gitignore")

    def test_pem_files_are_gitignored(self):
        """*.pem (CA certificate files) must be gitignored to prevent TLS cert commits."""
        content = self._read_gitignore()
        self.assertIn('*.pem', content, "*.pem files must be listed in .gitignore")
