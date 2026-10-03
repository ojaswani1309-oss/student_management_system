from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Course, Department, Marks, Student, Subject


class StyledFormMixin:
    """Adds the 'form-control' CSS class to every widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing} form-control'.strip()




class CourseSelect(forms.Select):
    """Select widget that stores each course's department id (used by JavaScript filtering)."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        instance = getattr(value, 'instance', None)
        if instance is not None:
            option['attrs']['data-department'] = instance.department_id
        return option


class LoginForm(forms.Form):
    identifier = forms.CharField(
        label='Username or Email', max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Enter username or email', 'autofocus': True}))
    password = forms.CharField(
        label='Password', widget=forms.PasswordInput(attrs={'placeholder': 'Enter password'}))


class DepartmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'code', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def clean_code(self):
        return self.cleaned_data['code'].strip().upper()


class CourseForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Course
        fields = ['course_id', 'name', 'department', 'duration_years', 'total_semesters']

    def clean_course_id(self):
        return self.cleaned_data['course_id'].strip().upper()


class SubjectForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['subject_code', 'name', 'course', 'semester', 'credits']

    def clean_subject_code(self):
        return self.cleaned_data['subject_code'].strip().upper()


class StudentForm(StyledFormMixin, forms.ModelForm):
    username = forms.CharField(max_length=150)
    password = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False))

    field_order = [
        'student_id', 'full_name', 'email', 'phone', 'date_of_birth', 'gender', 'department',
        'course', 'semester', 'enrollment_year', 'username', 'password', 'address', 'photo',
    ]

    class Meta:
        model = Student
        fields = [
            'student_id', 'full_name', 'email', 'phone', 'date_of_birth', 'gender', 'address',
            'department', 'course', 'semester', 'enrollment_year', 'photo',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'course': CourseSelect(),
            'phone': forms.TextInput(attrs={'placeholder': '9876543210', 'pattern': r'\+?\d{10,15}'}),
            'photo': forms.FileInput(attrs={'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['course'].queryset = Course.objects.select_related('department')
        if self.instance.pk:
            self.fields['username'].initial = self.instance.user.username
            self.fields['password'].help_text = 'Leave blank to keep the current password.'
        else:
            self.fields['password'].help_text = 'Minimum 8 characters.'

    def _other_users(self):
        users = User.objects.all()
        if self.instance.pk:
            users = users.exclude(pk=self.instance.user_id)
        return users

    def clean_student_id(self):
        return self.cleaned_data['student_id'].strip().upper()

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if self._other_users().filter(username__iexact=username).exists():
            raise ValidationError('This username is already taken.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if self._other_users().filter(email__iexact=email).exists():
            raise ValidationError('A user with this email already exists.')
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not self.instance.pk and not password:
            raise ValidationError('Password is required for a new student.')
        if password:
            validate_password(password)
        return password

    def save(self, commit=True):
        student = super().save(commit=False)
        with transaction.atomic():
            user = student.user if student.pk else User()
            user.username = self.cleaned_data['username']
            user.email = student.email
            first, _, last = student.full_name.partition(' ')
            user.first_name, user.last_name = first[:150], last[:150]
            user.is_staff = False
            user.is_superuser = False
            if self.cleaned_data.get('password'):
                user.set_password(self.cleaned_data['password'])
            user.save()
            student.user = user
            student.save()
        return student


class MarksForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Marks
        fields = ['student', 'subject', 'internal_marks', 'external_marks']
        widgets = {
            'internal_marks': forms.NumberInput(attrs={'min': 0, 'max': Marks.MAX_INTERNAL}),
            'external_marks': forms.NumberInput(attrs={'min': 0, 'max': Marks.MAX_EXTERNAL}),
        }
        help_texts = {
            'internal_marks': 'Out of 40',
            'external_marks': 'Out of 60',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = Student.objects.order_by('student_id')
        self.fields['subject'].queryset = Subject.objects.select_related('course')
