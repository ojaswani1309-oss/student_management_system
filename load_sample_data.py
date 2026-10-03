"""Load (or remove) demo data.

    python manage.py load_sample_data            # create demo data
    python manage.py load_sample_data --clear    # delete ONLY the demo students (is_demo=True)

Demo students are flagged with is_demo=True, so your real student records are never touched.
All demo students log in with the password:  Student@123
"""
import datetime
import random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from students.models import Attendance, Course, Department, Marks, Student, Subject

DEPARTMENTS = [
    ('Computer Science', 'CS'),
    ('Computer Science & Artificial Intelligence', 'CSAI'),
    ('Information Technology', 'IT'),
    ('Electronics', 'ECE'),
    ('Mechanical', 'ME'),
    ('Civil', 'CE'),
]

# course_id, name, department code
COURSES = [
    ('BTCS', 'B.Tech Computer Science', 'CS'),
    ('BTAI', 'B.Tech Computer Science & AI', 'CSAI'),
    ('BTIT', 'B.Tech Information Technology', 'IT'),
    ('BTEC', 'B.Tech Electronics', 'ECE'),
    ('BTME', 'B.Tech Mechanical Engineering', 'ME'),
    ('BTCE', 'B.Tech Civil Engineering', 'CE'),
]

# course_id -> semester -> [(name, code, credits)]
SUBJECTS = {
    'BTCS': {
        3: [('Data Structures', 'CS301', 4), ('Database Management Systems', 'CS302', 4),
            ('Object Oriented Programming', 'CS303', 3), ('Discrete Mathematics', 'CS304', 3),
            ('Computer Organization', 'CS305', 3)],
        4: [('Operating Systems', 'CS401', 4), ('Design & Analysis of Algorithms', 'CS402', 4),
            ('Computer Networks', 'CS403', 3), ('Software Engineering', 'CS404', 3),
            ('Python Programming', 'CS405', 2)],
    },
    'BTAI': {3: [('Data Structures', 'AI301', 4), ('Machine Learning Fundamentals', 'AI302', 4),
                 ('Probability & Statistics', 'AI303', 3), ('Python for AI', 'AI304', 3),
                 ('Database Systems', 'AI305', 3)]},
    'BTIT': {3: [('Data Structures', 'IT301', 4), ('Web Technologies', 'IT302', 3),
                 ('Database Systems', 'IT303', 4), ('Computer Networks', 'IT304', 3),
                 ('Operating Systems', 'IT305', 4)]},
    'BTEC': {3: [('Analog Electronics', 'EC301', 4), ('Digital Logic Design', 'EC302', 4),
                 ('Signals & Systems', 'EC303', 3), ('Network Analysis', 'EC304', 3)]},
    'BTME': {3: [('Thermodynamics', 'ME301', 4), ('Fluid Mechanics', 'ME302', 4),
                 ('Strength of Materials', 'ME303', 3), ('Manufacturing Processes', 'ME304', 3)]},
    'BTCE': {3: [('Structural Analysis', 'CE301', 4), ('Surveying', 'CE302', 3),
                 ('Concrete Technology', 'CE303', 3), ('Hydraulics', 'CE304', 4)]},
}

# name, gender, course_id, semester
STUDENTS = [
    ('Rahul Sharma', 'M', 'BTCS', 4), ('Priya Verma', 'F', 'BTCS', 4), ('Amit Singh', 'M', 'BTCS', 3),
    ('Neha Gupta', 'F', 'BTAI', 3), ('Arjun Mehta', 'M', 'BTAI', 3), ('Sneha Patel', 'F', 'BTIT', 3),
    ('Vikram Rao', 'M', 'BTIT', 3), ('Ananya Iyer', 'F', 'BTEC', 3), ('Karan Malhotra', 'M', 'BTME', 3),
    ('Pooja Yadav', 'F', 'BTCE', 3), ('Mohit Kumar', 'M', 'BTCS', 3), ('Divya Nair', 'F', 'BTAI', 3),
]
SHORT = {'BTCS': 'CS', 'BTAI': 'AI', 'BTIT': 'IT', 'BTEC': 'EC', 'BTME': 'ME', 'BTCE': 'CE'}
DEMO_PASSWORD = 'Student@123'


def last_weekdays(count):
    """Return the most recent `count` weekdays (Mon-Fri), oldest first."""
    days, day = [], datetime.date.today()
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day -= datetime.timedelta(days=1)
    return sorted(days)


class Command(BaseCommand):
    help = 'Load demo departments, courses, subjects, students, attendance and marks.'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Delete demo students (is_demo=True) and exit.')

    def handle(self, *args, **options):
        if options['clear']:
            user_ids = list(Student.objects.filter(is_demo=True).values_list('user_id', flat=True))
            User.objects.filter(pk__in=user_ids).delete()
            self.stdout.write(self.style.SUCCESS(f'Removed {len(user_ids)} demo students (and their data).'))
            return

        random.seed(42)
        with transaction.atomic():
            departments = {code: Department.objects.get_or_create(
                code=code, defaults={'name': name, 'description': f'Department of {name}'})[0]
                for name, code in DEPARTMENTS}
            courses = {cid: Course.objects.get_or_create(
                course_id=cid, defaults={'name': name, 'department': departments[dept],
                                         'duration_years': 4, 'total_semesters': 8})[0]
                for cid, name, dept in COURSES}
            for cid, by_sem in SUBJECTS.items():
                for sem, items in by_sem.items():
                    for name, code, credits in items:
                        Subject.objects.get_or_create(
                            subject_code=code,
                            defaults={'name': name, 'course': courses[cid], 'semester': sem, 'credits': credits})

            dates = last_weekdays(20)
            created = 0
            for number, (name, gender, cid, sem) in enumerate(STUDENTS, start=1):
                username = name.lower().replace(' ', '.')
                year = 2025 if sem == 3 else 2024
                student_id = f'BT{year}{SHORT[cid]}{number:03d}'
                if Student.objects.filter(student_id=student_id).exists() or User.objects.filter(username=username).exists():
                    continue
                course = courses[cid]
                first, _, last = name.partition(' ')
                user = User.objects.create_user(username=username, email=f'{username}@example.edu',
                                                password=DEMO_PASSWORD, first_name=first, last_name=last)
                student = Student.objects.create(
                    user=user, student_id=student_id, full_name=name, email=f'{username}@example.edu',
                    phone=f'9876543{number:03d}', date_of_birth=datetime.date(2004 + number % 2, number % 12 + 1, number + 5),
                    gender=gender, address=f'{number + 10}, Model Town, Meerut, Uttar Pradesh',
                    department=course.department, course=course, semester=sem, enrollment_year=year, is_demo=True)

                presence = random.uniform(0.62, 0.97)
                ability = random.uniform(0.6, 1.0)
                current = Subject.objects.filter(course=course, semester=sem)
                Attendance.objects.bulk_create([
                    Attendance(student=student, subject=subj, date=d, status='P' if random.random() < presence else 'A')
                    for subj in current for d in dates], ignore_conflicts=True)
                Marks.objects.bulk_create([
                    Marks(student=student, subject=subj,
                          internal_marks=min(40, int(40 * ability * random.uniform(0.85, 1.0)) + 1),
                          external_marks=min(60, int(60 * ability * random.uniform(0.8, 1.0)) + 1))
                    for subj in Subject.objects.filter(course=course, semester__lte=sem)])
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Sample data ready. {created} demo students created. Demo login password: {DEMO_PASSWORD}'))
        self.stdout.write('Example demo login ->  username: rahul.sharma   password: Student@123')
