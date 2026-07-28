from django.contrib import admin
from .models import Department, Student, Attendance, EmailOTP, CampusConfig

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'email', 'created_at')
    search_fields = ('name', 'email')
    ordering = ('name',)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('roll_number', 'get_full_name', 'get_email', 'department', 'has_face_registered', 'registered_at')
    search_fields = ('roll_number', 'user__first_name', 'user__last_name', 'user__email')
    list_filter = ('department', 'registered_at')

    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Full Name'

    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'

    def has_face_registered(self, obj):
        return bool(obj.face_bytes)
    has_face_registered.boolean = True
    has_face_registered.short_description = 'Face Enrolled'


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'entry_time', 'exit_time', 'status', 'confidence', 'entry_lat', 'entry_lon')
    list_filter = ('status', 'date', 'student__department')
    search_fields = ('student__roll_number', 'student__user__first_name', 'student__user__last_name')
    date_hierarchy = 'date'


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'otp', 'created_at', 'expires_at', 'is_used')
    list_filter = ('is_used', 'created_at')
    search_fields = ('email', 'otp')


@admin.register(CampusConfig)
class CampusConfigAdmin(admin.ModelAdmin):
    list_display = ('center_latitude', 'center_longitude', 'radius_meters', 'college_start_time', 'college_end_time')
