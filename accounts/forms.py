from django.contrib.auth.forms import UserCreationForm
from django import forms
from .models import User


class RegisterForm(UserCreationForm):
    """
    Public self-registration form.

    Exposes only fields appropriate for self-service signup.
    role is intentionally excluded — new accounts are always REQUESTER.
    Role elevation is an Admin action done through /admin/.
    """

    first_name = forms.CharField(
        max_length=150,
        required=True,
        help_text='Enter your first name.',
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        help_text='Enter your last name.',
    )
    email = forms.EmailField(
        required=False,
        help_text='Optional but recommended.',
    )
    user_type = forms.ChoiceField(
        choices=[('', '— Select type —')] + list(User.UserType.choices),
        required=False,
        help_text='Select Student or Faculty if applicable.',
    )
    department = forms.CharField(
        max_length=100,
        required=False,
        help_text='Your college, department, or office (e.g. BSIS, Education).',
    )

    class Meta:
        model = User
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'user_type',
            'department',
            'password1',
            'password2',
        ]

    def save(self, commit=True):
        user = super().save(commit=False)
        # Ensure all new self-registered accounts are REQUESTER
        user.role = User.Role.REQUESTER
        if commit:
            user.save()
        return user
