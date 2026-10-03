"""Small helper functions used by several views."""
from django.db.models import Count, Q

from .models import Attendance, calculate_grade


def _pct(part, whole):
    return round(part * 100 / whole, 1) if whole else 0


def attendance_overall(student):
    """Total classes / present / absent / percentage across all subjects."""
    data = Attendance.objects.filter(student=student).aggregate(
        total=Count('id'), present=Count('id', filter=Q(status='P')))
    total, present = data['total'], data['present']
    return {'total': total, 'present': present, 'absent': total - present, 'percentage': _pct(present, total)}


def subject_attendance(student):
    """List of per-subject attendance dictionaries for one student."""
    rows = (
        Attendance.objects.filter(student=student)
        .values('subject__name', 'subject__subject_code')
        .annotate(total=Count('id'), present=Count('id', filter=Q(status='P')))
        .order_by('subject__name')
    )
    result = []
    for row in rows:
        row['absent'] = row['total'] - row['present']
        row['percentage'] = _pct(row['present'], row['total'])
        result.append(row)
    return result


def overall_result(student, semester=None):
    """Marks rows plus total / percentage / grade for one student (optionally one semester)."""
    marks = student.marks.select_related('subject').order_by('subject__semester', 'subject__name')
    if semester:
        marks = marks.filter(subject__semester=semester)
    rows = list(marks)
    total = sum(m.total for m in rows)
    max_total = 100 * len(rows)
    percentage = round(total * 100 / max_total, 2) if rows else 0
    return {
        'rows': rows,
        'count': len(rows),
        'total': total,
        'max_total': max_total,
        'percentage': percentage,
        'grade': calculate_grade(percentage) if rows else '-',
    }
