from django.contrib import admin
from .models import AcademicPeriod, College, Department, Program, TimetableSession, TimetableImportLog

@admin.register(AcademicPeriod)
class PeriodAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'is_active']

@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    list_display = ['code', 'name']

@admin.register(Department)
class DeptAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'college']

@admin.register(Program)
class ProgAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'level', 'uqf_level', 'department']

@admin.register(TimetableSession)
class SessionAdmin(admin.ModelAdmin):
    list_display  = ['course_code', 'course_name', 'venue', 'day_of_week', 'start_time', 'end_time', 'program']
    list_filter   = ['day_of_week', 'period', 'is_active', 'import_source']
    search_fields = ['course_code', 'course_name', 'lecturer_name']

@admin.register(TimetableImportLog)
class LogAdmin(admin.ModelAdmin):
    list_display = ['source', 'period', 'status', 'sessions_created', 'created_at']
    readonly_fields = ['created_at']
