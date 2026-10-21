from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom User model for CFRMS extending Django's AbstractUser.

    Keeps all built-in fields:
    - username, password, first_name, last_name, email, is_active, is_staff, is_superuser, date_joined

    Separation of concerns:
    - `role`: Controls system-level authorization (permissions in CFRMS).
    - `user_type`: Legacy requester classification. Permissions come from `role`.
    - `department`: College / unit affiliation (e.g., BSIS, Education, Administration).
    """

    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        STAFF = 'STAFF', 'Staff'
        FACULTY = 'FACULTY', 'Faculty'
        REQUESTER = 'REQUESTER', 'Student Requester'

    class UserType(models.TextChoices):
        STUDENT = 'STUDENT', 'Student'
        FACULTY = 'FACULTY', 'Faculty'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.REQUESTER,
        help_text='System authorization level determining access and permissions.',
    )

    user_type = models.CharField(
        max_length=20,
        choices=UserType.choices,
        blank=True,
        default='',
        help_text='Legacy requester classification. Account permissions are controlled by role.',
    )

    department = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='College, department, or office affiliation at DSSC.',
    )
    phone_number = models.CharField(
        max_length=30,
        blank=True,
        default='',
        help_text='Optional contact number.',
    )
    bio = models.CharField(
        max_length=280,
        blank=True,
        default='',
        help_text='A short profile description (280 characters maximum).',
    )
    profile_image = models.ImageField(
        upload_to='profile_images/',
        blank=True,
        help_text='Optional profile photo. Maximum file size: 5 MB.',
    )

    is_synthetic = models.BooleanField(
        default=False,
        help_text='True if this record was created by the synthetic data generator.',
    )

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['username']

    def __str__(self):
        full_name = self.get_full_name()
        display = full_name if full_name else self.username
        return f"{display} ({self.get_role_display()})"

    # NOTE: Authorization Architecture Distinction:
    # Django's built-in `is_staff` flag strictly controls access to the Django Admin (/admin/).
    # It is NOT equivalent to CFRMS `role == Role.STAFF`.
    # CFRMS business logic and permissions must check `role` (or the properties below),
    # never `request.user.is_staff`.

    @property
    def is_admin_role(self):
        """Returns True if the user has the CFRMS ADMIN authorization role."""
        return self.role == self.Role.ADMIN

    @property
    def is_staff_role(self):
        """Returns True if the user has the CFRMS STAFF authorization role (Facility Staff)."""
        return self.role == self.Role.STAFF

    @property
    def is_requester_role(self):
        """Returns True if the user has the CFRMS REQUESTER authorization role."""
        return self.role == self.Role.REQUESTER

    @property
    def is_student_role(self):
        """Student requesters can submit and manage their own reservations."""
        return self.is_requester_role and self.user_type != self.UserType.FACULTY

    @property
    def is_faculty_role(self):
        """Faculty is a reviewer role, assigned by an administrator."""
        return self.role == self.Role.FACULTY

    @property
    def is_unassigned_faculty_account(self):
        """Legacy self-identified faculty accounts awaiting admin role assignment."""
        return self.is_requester_role and self.user_type == self.UserType.FACULTY

    @property
    def is_reservation_reviewer(self):
        """Staff, faculty, and admins can review student reservation requests."""
        return self.role in (self.Role.STAFF, self.Role.FACULTY, self.Role.ADMIN)

