from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django import forms
from django.core.exceptions import ValidationError
from .models import User


DEPARTMENT_COURSE_CHOICES = [
    ('', 'Select a course or program'),
    ('COLLEGE OF AGRICULTURE AND RELATED SCIENCES (CARS)', [
        ('CARS - BSA - Animal Science', 'Bachelor of Science in Agriculture (BSA) - Animal Science'),
        ('CARS - BSA - Crop Protection', 'Bachelor of Science in Agriculture (BSA) - Crop Protection'),
        ('CARS - BSA - Horticulture', 'Bachelor of Science in Agriculture (BSA) - Horticulture'),
        ('CARS - BSAB', 'Bachelor of Science in Agribusiness (BSAB)'),
        ('CARS - BSABE', 'Bachelor of Science in Agricultural and Biosystems Engineering (BSABE)'),
        ('CARS - BSAF', 'Bachelor of Science in Agroforestry (BSAF)'),
        ('CARS - BS VetTech', 'Bachelor of Science in Veterinary Technology (BS VetTech)'),
    ]),
    ('COLLEGE OF INFORMATION AND DIGITAL SCIENCES (CIDS)', [
        ('CIDS - BSIT', 'Bachelor of Science in Information Technology (BSIT)'),
        ('CIDS - BSIS', 'Bachelor of Science in Information Systems (BSIS)'),
        ('CIDS - DIT', '3-Year Diploma in Information Technology (DIT)'),
        ('CIDS - ACT', '2-Year Associate in Computer Technology (ACT)'),
    ]),
    ('COLLEGE OF TEACHER EDUCATION (CTED)', [
        ('CTED - BEED', 'Bachelor of Elementary Education (BEED)'),
        ('CTED - BSED - English', 'Bachelor of Secondary Education (BSED) - English'),
        ('CTED - BSED - Social Studies', 'Bachelor of Secondary Education (BSED) - Social Studies'),
        ('CTED - BSED - Mathematics', 'Bachelor of Secondary Education (BSED) - Mathematics'),
        ('CTED - BSED - Science', 'Bachelor of Secondary Education (BSED) - Science'),
        ('CTED - BSED - Filipino', 'Bachelor of Secondary Education (BSED) - Filipino'),
        ('CTED - BTLED - Home Economics', 'Bachelor of Technology and Livelihood Education (BTLED) - Home Economics'),
    ]),
    ('COLLEGE OF BUSINESS EDUCATION AND GOVERNANCE (CBEG)', [
        ('CBEG - BSAIS', 'Bachelor of Science in Accounting Information Systems (BSAIS)'),
        ('CBEG - BPA', 'Bachelor of Public Administration (BPA)'),
    ]),
    ('COLLEGE OF ENGINEERING AND TECHNOLOGY (CET)', [
        ('CET - BIT', 'Bachelor of Industrial Technology (BIT)'),
    ]),
    ('COLLEGE OF MATHEMATICS, ARTS, AND SCIENCES (CMAS)', [
        ('CMAS - BS Mathematics', 'Bachelor of Science in Mathematics'),
        ('CMAS - BS Biology - Biodiversity', 'Bachelor of Science in Biology - Biodiversity track'),
        ('CMAS - BS Biology - Medical Biology', 'Bachelor of Science in Biology - Medical Biology track'),
        ('CMAS - BSES', 'Bachelor of Science in Environmental Science (BSES)'),
        ('CMAS - BSFT', 'Bachelor of Science in Food Technology (BSFT)'),
        ('CMAS - BS DevCom', 'Bachelor of Science in Development Communication (BS DevCom)'),
    ]),
    ('COLLEGE OF GRADUATE AND PROFESSIONAL EDUCATION (CGPE)', [
        ('CGPE - PhD - Educational Management', 'Doctor of Philosophy (PhD) in Educational Management'),
        ('CGPE - PhD - Business Administration', 'Doctor of Philosophy (PhD) in Business Administration'),
        ('CGPE - MAEd - Educational Management', 'Master of Arts in Education (MAEd) - Educational Management'),
        ('CGPE - MAEd - Mathematics Teaching', 'Master of Arts in Education (MAEd) - Mathematics Teaching'),
        ('CGPE - MAEd - Language Teaching', 'Master of Arts in Education (MAEd) - Language Teaching'),
        ('CGPE - MAEd - Science Teaching', 'Master of Arts in Education (MAEd) - Science Teaching'),
        ('CGPE - MBA - Agri-Business Management', 'Master in Business Administration (MBA) - Agri-Business Management'),
    ]),
]


class RegisterForm(UserCreationForm):
    """
    Public self-registration form.

    Exposes only fields appropriate for self-service signup.
    role is intentionally excluded — new accounts are always REQUESTER.
    Role elevation is an Admin action done through the CFRMS Admin Console.
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
    department = forms.ChoiceField(
        choices=DEPARTMENT_COURSE_CHOICES,
        required=False,
        help_text='Select your college and course.',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = User
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'department',
            'password1',
            'password2',
        ]

    def save(self, commit=True):
        user = super().save(commit=False)
        # Ensure all new self-registered accounts are REQUESTER
        user.role = User.Role.REQUESTER
        user.user_type = User.UserType.STUDENT
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
