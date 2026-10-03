import datetime
import json

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.db.models import Avg, Count, F, ProtectedError, Q
from django.http import HttpResponseServerError
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .decorators import admin_required, student_required
from .forms import CourseForm, DepartmentForm, LoginForm, MarksForm, StudentForm, SubjectForm
from .models import Attendance, Course, Department, Marks, Student, Subject
from .utils import attendance_overall, overall_result, subject_attendance


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def to_int(value):
    """Return int(value) for digit strings, otherwise None."""
    return int(value) if value and str(value).isdigit() else None


def paginate(request, queryset, per_page=10):
    page = Paginator(queryset, per_page).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    return page, params.urlencode()


def form_page(request, form_class, title, redirect_name, success_message, instance=None):
    """Shared add/edit view: shows the form, validates it, saves it."""
    form = form_class(request.POST or None, request.FILES or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
        except DatabaseError:
            messages.error(request, 'A database error occurred while saving. Please try again.')
        else:
            messages.success(request, success_message)
            return redirect(redirect_name)
    elif request.method == 'POST':
        messages.error(request, 'Please correct the errors below.')
    return render(request, 'form.html', {'form': form, 'title': title, 'back_url': reverse(redirect_name)})


def delete_object(request, model, pk, redirect_name, label):
    obj = get_object_or_404(model, pk=pk)
    try:
        obj.delete()
        messages.success(request, f'{label} deleted successfully.')
    except ProtectedError:
        messages.error(request, f'Cannot delete this {label.lower()} because other records depend on it. '
                                f'Remove those records first.')
    except DatabaseError:
        messages.error(request, 'A database error occurred. Nothing was deleted.')
    return redirect(redirect_name)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
def redirect_by_role(user):
    return redirect('admin_dashboard' if user.is_staff else 'portal_dashboard')


def home(request):
    if request.user.is_authenticated:
        return redirect_by_role(request.user)
    return redirect('login')


def login_view(request):
    if request.user.is_authenticated:
        return redirect_by_role(request.user)
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = authenticate(request, username=form.cleaned_data['identifier'],
                            password=form.cleaned_data['password'])
        if user is None:
            form.add_error(None, 'Invalid username/email or password.')
        elif not user.is_staff and not hasattr(user, 'student'):
            form.add_error(None, 'No student profile is linked to this account. Please contact the administrator.')
        else:
            login(request, user)
            next_url = request.GET.get('next', '')
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            return redirect_by_role(user)
    return render(request, 'login.html', {'form': form})


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')


# ---------------------------------------------------------------------------
# Admin: dashboard & profile
# ---------------------------------------------------------------------------
@admin_required
def admin_dashboard(request):
    att = Attendance.objects.aggregate(total=Count('id'), present=Count('id', filter=Q(status='P')))
    avg_attendance = round(att['present'] * 100 / att['total'], 1) if att['total'] else 0
    avg_marks = Marks.objects.aggregate(avg=Avg(F('internal_marks') + F('external_marks')))['avg'] or 0

    departments = Department.objects.annotate(
        total=Count('students__attendance_records'),
        present=Count('students__attendance_records', filter=Q(students__attendance_records__status='P')),
    )
    dept_labels = [d.code for d in departments]
    dept_values = [round(d.present * 100 / d.total, 1) if d.total else 0 for d in departments]

    grade_counts = {g: 0 for g in ['A+', 'A', 'B', 'C', 'D', 'F']}
    for mark in Marks.objects.only('internal_marks', 'external_marks'):
        grade_counts[mark.grade] += 1

    context = {
        'total_students': Student.objects.count(),
        'total_courses': Course.objects.count(),
        'total_departments': Department.objects.count(),
        'total_subjects': Subject.objects.count(),
        'avg_attendance': avg_attendance,
        'avg_marks': round(avg_marks, 1),
        'recent_students': Student.objects.select_related('department', 'course').order_by('-created_at')[:5],
        'recent_results': Marks.objects.select_related('student', 'subject').order_by('-updated_at')[:5],
        'dept_labels': dept_labels,
        'dept_values': dept_values,
        'grade_labels': list(grade_counts.keys()),
        'grade_values': list(grade_counts.values()),
    }
    return render(request, 'admin_dashboard.html', context)


@admin_required
def admin_profile(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    for field in form.fields.values():
        field.widget.attrs['class'] = 'form-control'
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Your password was changed successfully.')
        return redirect('admin_profile')
    return render(request, 'admin_profile.html', {'form': form})


# ---------------------------------------------------------------------------
# Admin: students
# ---------------------------------------------------------------------------
@admin_required
def student_list(request):
    students = Student.objects.select_related('department', 'course')
    q = request.GET.get('q', '').strip()
    if q:
        students = students.filter(Q(full_name__icontains=q) | Q(student_id__icontains=q) | Q(email__icontains=q))
    department, course = to_int(request.GET.get('department')), to_int(request.GET.get('course'))
    semester, year = to_int(request.GET.get('semester')), to_int(request.GET.get('year'))
    if department:
        students = students.filter(department_id=department)
    if course:
        students = students.filter(course_id=course)
    if semester:
        students = students.filter(semester=semester)
    if year:
        students = students.filter(enrollment_year=year)

    page, querystring = paginate(request, students.order_by('student_id'))
    context = {
        'page': page, 'querystring': querystring,
        'departments': Department.objects.all(),
        'courses': Course.objects.select_related('department'),
        'semesters': range(1, 13),
        'years': Student.objects.order_by('-enrollment_year').values_list('enrollment_year', flat=True).distinct(),
        'q': q, 'sel_department': department, 'sel_course': course, 'sel_semester': semester, 'sel_year': year,
    }
    return render(request, 'students/list.html', context)


@admin_required
def student_add(request):
    return form_page(request, StudentForm, 'Add Student', 'student_list', 'Student added successfully.')


@admin_required
def student_edit(request, pk):
    student = get_object_or_404(Student, pk=pk)
    return form_page(request, StudentForm, f'Edit Student: {student.full_name}', 'student_list',
                     'Student updated successfully.', instance=student)


@admin_required
def student_detail(request, pk):
    student = get_object_or_404(Student.objects.select_related('department', 'course'), pk=pk)
    return render(request, 'students/detail.html', {
        'student': student, 'is_admin_view': True,
        'attendance_rows': subject_attendance(student),
        'attendance_total': attendance_overall(student),
        'result': overall_result(student),
    })


@admin_required
@require_POST
def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)
    try:
        student.user.delete()          # deleting the user also deletes the student (cascade)
        messages.success(request, 'Student deleted successfully.')
    except DatabaseError:
        messages.error(request, 'A database error occurred. Nothing was deleted.')
    return redirect('student_list')


# ---------------------------------------------------------------------------
# Admin: departments
# ---------------------------------------------------------------------------
@admin_required
def department_list(request):
    departments = Department.objects.annotate(course_count=Count('courses', distinct=True),
                                              student_count=Count('students', distinct=True))
    return render(request, 'departments/list.html', {'departments': departments})


@admin_required
def department_add(request):
    return form_page(request, DepartmentForm, 'Add Department', 'department_list', 'Department added successfully.')


@admin_required
def department_edit(request, pk):
    obj = get_object_or_404(Department, pk=pk)
    return form_page(request, DepartmentForm, 'Edit Department', 'department_list',
                     'Department updated successfully.', instance=obj)


@admin_required
@require_POST
def department_delete(request, pk):
    return delete_object(request, Department, pk, 'department_list', 'Department')


# ---------------------------------------------------------------------------
# Admin: courses
# ---------------------------------------------------------------------------
@admin_required
def course_list(request):
    courses = Course.objects.select_related('department').annotate(subject_count=Count('subjects', distinct=True))
    q = request.GET.get('q', '').strip()
    department = to_int(request.GET.get('department'))
    if q:
        courses = courses.filter(Q(name__icontains=q) | Q(course_id__icontains=q))
    if department:
        courses = courses.filter(department_id=department)
    page, querystring = paginate(request, courses.order_by('name'))
    return render(request, 'courses/list.html', {
        'page': page, 'querystring': querystring, 'departments': Department.objects.all(),
        'q': q, 'sel_department': department})


@admin_required
def course_add(request):
    return form_page(request, CourseForm, 'Add Course', 'course_list', 'Course added successfully.')


@admin_required
def course_edit(request, pk):
    obj = get_object_or_404(Course, pk=pk)
    return form_page(request, CourseForm, 'Edit Course', 'course_list', 'Course updated successfully.', instance=obj)


@admin_required
@require_POST
def course_delete(request, pk):
    return delete_object(request, Course, pk, 'course_list', 'Course')


# ---------------------------------------------------------------------------
# Admin: subjects
# ---------------------------------------------------------------------------
@admin_required
def subject_list(request):
    subjects = Subject.objects.select_related('course')
    q = request.GET.get('q', '').strip()
    course, semester = to_int(request.GET.get('course')), to_int(request.GET.get('semester'))
    if q:
        subjects = subjects.filter(Q(name__icontains=q) | Q(subject_code__icontains=q))
    if course:
        subjects = subjects.filter(course_id=course)
    if semester:
        subjects = subjects.filter(semester=semester)
    page, querystring = paginate(request, subjects)
    return render(request, 'subjects/list.html', {
        'page': page, 'querystring': querystring, 'courses': Course.objects.all(), 'semesters': range(1, 13),
        'q': q, 'sel_course': course, 'sel_semester': semester})


@admin_required
def subject_add(request):
    return form_page(request, SubjectForm, 'Add Subject', 'subject_list', 'Subject added successfully.')


@admin_required
def subject_edit(request, pk):
    obj = get_object_or_404(Subject, pk=pk)
    return form_page(request, SubjectForm, 'Edit Subject', 'subject_list', 'Subject updated successfully.', instance=obj)


@admin_required
@require_POST
def subject_delete(request, pk):
    return delete_object(request, Subject, pk, 'subject_list', 'Subject')


# ---------------------------------------------------------------------------
# Admin: attendance
# ---------------------------------------------------------------------------
@admin_required
def attendance_mark(request):
    """Pick department/course/semester/subject/date, then mark Present/Absent for each student."""
    sel_department = to_int(request.GET.get('department'))
    sel_course = to_int(request.GET.get('course'))
    sel_semester = to_int(request.GET.get('semester'))
    sel_subject = to_int(request.GET.get('subject'))
    date_text = request.GET.get('date', '')

    rows, subject, date = [], None, None
    selection_ready = all([sel_course, sel_semester, sel_subject, date_text])

    if selection_ready:
        try:
            date = datetime.date.fromisoformat(date_text)
        except ValueError:
            messages.error(request, 'Please enter a valid date.')
            selection_ready = False
        else:
            if date > datetime.date.today():
                messages.error(request, 'Attendance cannot be marked for a future date.')
                selection_ready = False
    if selection_ready:
        subject = Subject.objects.filter(pk=sel_subject, course_id=sel_course, semester=sel_semester).first()
        if subject is None:
            messages.error(request, 'The selected subject does not belong to that course and semester.')
            selection_ready = False

    if selection_ready:
        students = list(Student.objects.filter(course_id=sel_course, semester=sel_semester).order_by('student_id'))
        existing = dict(Attendance.objects.filter(subject=subject, date=date).values_list('student_id', 'status'))

        if request.method == 'POST':
            submitted = {s.pk: request.POST.get(f'status_{s.pk}') for s in students}
            if any(v not in ('P', 'A') for v in submitted.values()):
                messages.error(request, 'Invalid attendance value submitted. Please try again.')
            else:
                try:
                    with transaction.atomic():
                        for student in students:
                            Attendance.objects.update_or_create(
                                student=student, subject=subject, date=date,
                                defaults={'status': submitted[student.pk]})
                    messages.success(request, f'Attendance saved for {len(students)} students.')
                    return redirect(request.get_full_path())
                except DatabaseError:
                    messages.error(request, 'A database error occurred while saving attendance.')
        rows = [(s, existing.get(s.pk, 'P')) for s in students]
        if not students:
            messages.warning(request, 'No students are enrolled in that course and semester.')

    return render(request, 'attendance/mark.html', {
        'departments': Department.objects.all(),
        'courses': Course.objects.select_related('department'),
        'subjects': Subject.objects.select_related('course'),
        'semesters': range(1, 9),
        'sel_department': sel_department, 'sel_course': sel_course,
        'sel_semester': sel_semester, 'sel_subject': sel_subject, 'date_value': date_text,
        'today': datetime.date.today().isoformat(),
        'rows': rows, 'subject': subject, 'selection_ready': selection_ready,
    })


@admin_required
def attendance_report(request):
    """Attendance summary (total / present / absent / %) for every student."""
    course, semester = to_int(request.GET.get('course')), to_int(request.GET.get('semester'))
    subject, q = to_int(request.GET.get('subject')), request.GET.get('q', '').strip()

    students = Student.objects.select_related('course', 'department')
    if course:
        students = students.filter(course_id=course)
    if semester:
        students = students.filter(semester=semester)
    if q:
        students = students.filter(Q(full_name__icontains=q) | Q(student_id__icontains=q))

    subject_cond = Q(attendance_records__subject_id=subject) if subject else None
    total_filter = subject_cond
    present_filter = Q(attendance_records__status='P') & subject_cond if subject else Q(attendance_records__status='P')
    students = students.annotate(
        total=Count('attendance_records', filter=total_filter),
        present=Count('attendance_records', filter=present_filter),
    ).order_by('student_id')

    page, querystring = paginate(request, students)
    for s in page:
        s.absent = s.total - s.present
        s.percentage = round(s.present * 100 / s.total, 1) if s.total else 0
    return render(request, 'attendance/report.html', {
        'page': page, 'querystring': querystring, 'courses': Course.objects.all(),
        'subjects': Subject.objects.select_related('course'), 'semesters': range(1, 13),
        'q': q, 'sel_course': course, 'sel_semester': semester, 'sel_subject': subject})


# ---------------------------------------------------------------------------
# Admin: marks & results
# ---------------------------------------------------------------------------
@admin_required
def marks_list(request):
    marks = Marks.objects.select_related('student', 'subject', 'subject__course')
    q = request.GET.get('q', '').strip()
    course, semester = to_int(request.GET.get('course')), to_int(request.GET.get('semester'))
    if q:
        marks = marks.filter(Q(student__full_name__icontains=q) | Q(student__student_id__icontains=q)
                             | Q(subject__name__icontains=q))
    if course:
        marks = marks.filter(subject__course_id=course)
    if semester:
        marks = marks.filter(subject__semester=semester)
    page, querystring = paginate(request, marks.order_by('student__student_id', 'subject__semester', 'subject__name'))
    return render(request, 'results/marks_list.html', {
        'page': page, 'querystring': querystring, 'courses': Course.objects.all(), 'semesters': range(1, 13),
        'q': q, 'sel_course': course, 'sel_semester': semester})


@admin_required
def marks_add(request):
    return form_page(request, MarksForm, 'Add Marks', 'marks_list', 'Marks saved successfully.')


@admin_required
def marks_edit(request, pk):
    obj = get_object_or_404(Marks, pk=pk)
    return form_page(request, MarksForm, 'Edit Marks', 'marks_list', 'Marks updated successfully.', instance=obj)


@admin_required
@require_POST
def marks_delete(request, pk):
    return delete_object(request, Marks, pk, 'marks_list', 'Marks record')


def result_context(request, student):
    semester = to_int(request.GET.get('semester'))
    semesters = student.marks.order_by('subject__semester').values_list('subject__semester', flat=True).distinct()
    return {'student': student, 'result': overall_result(student, semester),
            'semesters': semesters, 'sel_semester': semester}


@admin_required
def result_view(request, pk):
    student = get_object_or_404(Student.objects.select_related('department', 'course'), pk=pk)
    context = result_context(request, student)
    context['is_admin_view'] = True
    return render(request, 'results/result.html', context)


# ---------------------------------------------------------------------------
# Student portal (a student only ever sees request.user.student - no IDs in URLs)
# ---------------------------------------------------------------------------
@student_required
def portal_dashboard(request):
    student = request.user.student
    attendance = attendance_overall(student)
    result = overall_result(student)
    low_attendance = [r for r in subject_attendance(student) if r['percentage'] < 75]
    return render(request, 'student_dashboard.html', {
        'student': student, 'attendance': attendance, 'result': result,
        'subject_count': Subject.objects.filter(course=student.course, semester=student.semester).count(),
        'low_attendance': low_attendance, 'recent_marks': result['rows'][-5:],
    })


@student_required
def portal_profile(request):
    student = request.user.student
    return render(request, 'students/detail.html', {
        'student': student, 'is_admin_view': False,
        'attendance_rows': subject_attendance(student),
        'attendance_total': attendance_overall(student),
        'result': overall_result(student),
    })


@student_required
def portal_attendance(request):
    student = request.user.student
    return render(request, 'attendance/my_attendance.html', {
        'student': student, 'rows': subject_attendance(student), 'total': attendance_overall(student)})


@student_required
def portal_results(request):
    context = result_context(request, request.user.student)
    context['is_admin_view'] = False
    return render(request, 'results/result.html', context)


@student_required
def portal_subjects(request):
    student = request.user.student
    subjects = Subject.objects.filter(course=student.course).order_by('semester', 'name')
    return render(request, 'subjects/my_subjects.html', {'student': student, 'subjects': subjects})


# ---------------------------------------------------------------------------
# Error pages
# ---------------------------------------------------------------------------
def _error(request, status, title, message):
    return render(request, 'errors/error.html', {'code': status, 'title': title, 'message': message}, status=status)


def error_400(request, exception=None):
    return _error(request, 400, 'Invalid Request', 'The request could not be understood. Please check the form and try again.')


def error_403(request, exception=None):
    return _error(request, 403, 'Unauthorized Access', 'You do not have permission to view this page.')


def error_404(request, exception=None):
    return _error(request, 404, 'Page Not Found', 'The page or record you are looking for does not exist (for example, the student was not found).')


def error_500(request):
    # Rendered without the request so it still works if the database is down.
    html = render_to_string('errors/error.html', {
        'code': 500, 'title': 'Server / Database Error',
        'message': 'Something went wrong on our side. Please try again later.'})
    return HttpResponseServerError(html)
