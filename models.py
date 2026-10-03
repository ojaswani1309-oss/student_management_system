import datetime

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

phone_validator = RegexValidator(
    r'^\+?\d{10,15}$',
    'Enter a valid phone number (10-15 digits, optional leading +).',
)


def calculate_grade(percentage):
    """Convert a percentage into a letter grade."""
    if percentage >= 90:
        return 'A+'
    if percentage >= 80:
        return 'A'
    if percentage >= 70:
        return 'B'
    if percentage >= 60:
        return 'C'
    if percentage >= 50:
        return 'D'
    return 'F'


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Course(models.Model):
    course_id = models.CharField('Course ID', max_length=20, unique=True)
    name = models.CharField('Course name', max_length=150)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='courses')
    duration_years = models.PositiveSmallIntegerField(
        'Duration (years)', validators=[MinValueValidator(1), MaxValueValidator(6)])
    total_semesters = models.PositiveSmallIntegerField(
        'Total semesters', validators=[MinValueValidator(1), MaxValueValidator(12)])

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.course_id})'


class Subject(models.Model):
    subject_code = models.CharField('Subject ID / Code', max_length=20, unique=True)
    name = models.CharField('Subject name', max_length=150)
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='subjects')
    semester = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    credits = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])

    class Meta:
        ordering = ['course__name', 'semester', 'name']

    def clean(self):
        if self.course_id and self.semester and self.semester > self.course.total_semesters:
            raise ValidationError({'semester': f'This course only has {self.course.total_semesters} semesters.'})

    def __str__(self):
        return f'{self.subject_code} - {self.name}'


class Student(models.Model):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female'), ('O', 'Other')]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student')
    student_id = models.CharField('Student ID', max_length=20, unique=True)
    full_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    phone = models.CharField('Phone number', max_length=16, validators=[phone_validator])
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    address = models.TextField()
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='students')
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='students')
    semester = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    enrollment_year = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    photo = models.ImageField('Profile photo', upload_to='profile_photos/', blank=True, null=True)
    is_demo = models.BooleanField('Demo data', default=False,
                                  help_text='True for records created by load_sample_data.')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['student_id']

    def clean(self):
        if self.date_of_birth and self.date_of_birth >= datetime.date.today():
            raise ValidationError({'date_of_birth': 'Date of birth must be in the past.'})
        if self.course_id and self.department_id:
            if self.course.department_id != self.department_id:
                raise ValidationError({'course': 'The selected course does not belong to the selected department.'})
            if self.semester and self.semester > self.course.total_semesters:
                raise ValidationError({'semester': f'This course only has {self.course.total_semesters} semesters.'})

    @property
    def initials(self):
        parts = self.full_name.split()
        return ''.join(p[0] for p in parts[:2]).upper() or '?'

    def __str__(self):
        return f'{self.student_id} - {self.full_name}'


class Attendance(models.Model):
    STATUS_CHOICES = [('P', 'Present'), ('A', 'Absent')]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField()
    status = models.CharField(max_length=1, choices=STATUS_CHOICES)

    class Meta:
        unique_together = ('student', 'subject', 'date')
        ordering = ['-date']

    def __str__(self):
        return f'{self.student.student_id} | {self.subject.subject_code} | {self.date} | {self.status}'


class Marks(models.Model):
    MAX_INTERNAL = 40
    MAX_EXTERNAL = 60

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='marks')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='marks')
    internal_marks = models.PositiveSmallIntegerField(
        validators=[MaxValueValidator(MAX_INTERNAL, message='Internal marks cannot exceed 40.')])
    external_marks = models.PositiveSmallIntegerField(
        validators=[MaxValueValidator(MAX_EXTERNAL, message='External marks cannot exceed 60.')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'subject')
        verbose_name_plural = 'marks'
        ordering = ['-updated_at']

    @property
    def total(self):
        return self.internal_marks + self.external_marks

    @property
    def percentage(self):
        return round(self.total * 100 / (self.MAX_INTERNAL + self.MAX_EXTERNAL), 2)

    @property
    def grade(self):
        return calculate_grade(self.percentage)

    def clean(self):
        if self.student_id and self.subject_id:
            if self.subject.course_id != self.student.course_id:
                raise ValidationError('This subject does not belong to the selected student\'s course.')
            if self.subject.semester > self.student.semester:
                raise ValidationError('This subject belongs to a later semester than the student\'s current semester.')

    def __str__(self):
        return f'{self.student.student_id} | {self.subject.subject_code} | {self.total}'
