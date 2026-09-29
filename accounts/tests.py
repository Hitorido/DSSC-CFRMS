from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class UserModelTestCase(TestCase):
    """
    Focused test suite validating custom User model roles,
    authorization properties, and password security.
    """

    def test_normal_user_defaults_to_requester_role(self):
        """A newly created user should default to the REQUESTER role."""
        user = User.objects.create_user(
            username='jdelacruz',
            email='jdelacruz@dssc.edu.ph',
            password='testpassword123',
        )
        self.assertEqual(user.role, User.Role.REQUESTER)
        self.assertTrue(user.is_requester_role)
        self.assertFalse(user.is_admin_role)
        self.assertFalse(user.is_staff_role)

    def test_admin_role_properties(self):
        """An ADMIN role user should satisfy is_admin_role and not others."""
        admin_user = User.objects.create_user(
            username='super_admin',
            email='admin@dssc.edu.ph',
            password='testpassword123',
            role=User.Role.ADMIN,
        )
        self.assertEqual(admin_user.role, User.Role.ADMIN)
        self.assertTrue(admin_user.is_admin_role)
        self.assertFalse(admin_user.is_staff_role)
        self.assertFalse(admin_user.is_requester_role)

    def test_staff_role_properties(self):
        """A STAFF role user should satisfy is_staff_role and not others."""
        staff_user = User.objects.create_user(
            username='facility_officer',
            email='officer@dssc.edu.ph',
            password='testpassword123',
            role=User.Role.STAFF,
        )
        self.assertEqual(staff_user.role, User.Role.STAFF)
        self.assertTrue(staff_user.is_staff_role)
        self.assertFalse(staff_user.is_admin_role)
        self.assertFalse(staff_user.is_requester_role)

    def test_requester_role_properties(self):
        """A explicitly created REQUESTER should satisfy is_requester_role."""
        requester_user = User.objects.create_user(
            username='student_maria',
            email='maria@dssc.edu.ph',
            password='testpassword123',
            role=User.Role.REQUESTER,
            user_type=User.UserType.STUDENT,
            department='BSIS',
        )
        self.assertEqual(requester_user.role, User.Role.REQUESTER)
        self.assertEqual(requester_user.user_type, User.UserType.STUDENT)
        self.assertEqual(requester_user.department, 'BSIS')
        self.assertTrue(requester_user.is_requester_role)
        self.assertFalse(requester_user.is_admin_role)
        self.assertFalse(requester_user.is_staff_role)

    def test_password_security(self):
        """
        Verify create_user hashes the password using PBKDF2,
        does not store raw text, and check_password validates correctly.
        """
        raw_password = 'SuperSecretCFRMSPassword2026!'
        user = User.objects.create_user(
            username='secure_user',
            email='secure@dssc.edu.ph',
            password=raw_password,
        )

        # Raw password must NEVER equal stored database string
        self.assertNotEqual(user.password, raw_password)

        # Password string must be a hashed format (e.g. pbkdf2_sha256$...)
        self.assertTrue(user.password.startswith('pbkdf2_sha256$'))

        # check_password() correctly verifies matching password
        self.assertTrue(user.check_password(raw_password))

        # check_password() rejects invalid password
        self.assertFalse(user.check_password('WrongPassword!'))
