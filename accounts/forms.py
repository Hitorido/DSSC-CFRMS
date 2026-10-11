from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django import forms
from django.core.exceptions import ValidationError
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


class ProfileForm(forms.ModelForm):
    """Allow users to edit personal details without exposing role permissions."""

    class Meta:
        model = User
        fields = [
            'profile_image',
            'first_name',
            'last_name',
            'email',
            'phone_number',
            'user_type',
            'department',
            'bio',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'autocomplete': 'given-name'}),
            'last_name': forms.TextInput(attrs={'autocomplete': 'family-name'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
            'phone_number': forms.TextInput(attrs={'type': 'tel', 'autocomplete': 'tel'}),
            'department': forms.TextInput(),
            'bio': forms.Textarea(attrs={'rows': 4, 'maxlength': 280}),
            'profile_image': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }
        labels = {
            'user_type': 'Account type',
            'department': 'Department or course',
            'bio': 'About me',
            'profile_image': 'Profile photo',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.ClearableFileInput):
                field.widget.attrs.setdefault('class', 'form-control profile-file-input')
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault('class', 'form-control')
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault('class', 'form-select')
            else:
                field.widget.attrs.setdefault('class', 'form-control')

    def clean_profile_image(self):
        image = self.cleaned_data.get('profile_image')
        uploaded_image = self.files.get(self.add_prefix('profile_image'))
        if uploaded_image and uploaded_image.size > 5 * 1024 * 1024:
            raise ValidationError('Choose an image smaller than 5 MB.')
        return image


class CFRMSPasswordChangeForm(PasswordChangeForm):
    """Apply the shared form styling to Django's built-in password form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control', 'autocomplete': 'current-password'})
        self.fields['new_password1'].widget.attrs['autocomplete'] = 'new-password'
        self.fields['new_password2'].widget.attrs['autocomplete'] = 'new-password'
