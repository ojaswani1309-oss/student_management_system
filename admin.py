from django.contrib import admin

from .models import Attendance, Course, Department, Marks, Student, Subject

admin.site.register(Department)
admin.site.register(Course)
admin.site.register(Subject)
admin.site.register(Student)
admin.site.register(Attendance)
admin.site.register(Marks)
