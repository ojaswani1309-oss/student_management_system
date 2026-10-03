from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # ----- Admin -----
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('profile/', views.admin_profile, name='admin_profile'),

    path('students/', views.student_list, name='student_list'),
    path('students/add/', views.student_add, name='student_add'),
    path('students/<int:pk>/', views.student_detail, name='student_detail'),
    path('students/<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('students/<int:pk>/delete/', views.student_delete, name='student_delete'),

    path('departments/', views.department_list, name='department_list'),
    path('departments/add/', views.department_add, name='department_add'),
    path('departments/<int:pk>/edit/', views.department_edit, name='department_edit'),
    path('departments/<int:pk>/delete/', views.department_delete, name='department_delete'),

    path('courses/', views.course_list, name='course_list'),
    path('courses/add/', views.course_add, name='course_add'),
    path('courses/<int:pk>/edit/', views.course_edit, name='course_edit'),
    path('courses/<int:pk>/delete/', views.course_delete, name='course_delete'),

    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/add/', views.subject_add, name='subject_add'),
    path('subjects/<int:pk>/edit/', views.subject_edit, name='subject_edit'),
    path('subjects/<int:pk>/delete/', views.subject_delete, name='subject_delete'),

    path('attendance/', views.attendance_mark, name='attendance_mark'),
    path('attendance/report/', views.attendance_report, name='attendance_report'),

    path('marks/', views.marks_list, name='marks_list'),
    path('marks/add/', views.marks_add, name='marks_add'),
    path('marks/<int:pk>/edit/', views.marks_edit, name='marks_edit'),
    path('marks/<int:pk>/delete/', views.marks_delete, name='marks_delete'),
    path('results/<int:pk>/', views.result_view, name='result_view'),

    # ----- Student portal (no IDs in the URLs: students only see their own data) -----
    path('portal/', views.portal_dashboard, name='portal_dashboard'),
    path('portal/profile/', views.portal_profile, name='portal_profile'),
    path('portal/attendance/', views.portal_attendance, name='portal_attendance'),
    path('portal/results/', views.portal_results, name='portal_results'),
    path('portal/subjects/', views.portal_subjects, name='portal_subjects'),
]
