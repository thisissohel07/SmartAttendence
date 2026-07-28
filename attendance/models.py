import datetime
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="Department Name (e.g. Computer Science)")
    email = models.EmailField(help_text="Department HOD or Admin Email for Early Exit Alerts")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        ordering = ['name']

    def __str__(self):
        return self.name


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    roll_number = models.CharField(max_length=50, unique=True, help_text="Unique Roll Number")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='students')
    face_bytes = models.BinaryField(help_text="Binary LBPH Face Encoding / Image Feature Vector", null=True, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Student"
        verbose_name_plural = "Students"
        ordering = ['roll_number']

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.roll_number})"


class Attendance(models.Model):
    STATUS_CHOICES = (
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent'),
        ('LATE', 'Late'),
        ('LEFT_EARLY', 'Left Early'),
    )

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(default=timezone.now)
    entry_time = models.TimeField(null=True, blank=True)
    exit_time = models.TimeField(null=True, blank=True)
    entry_lat = models.FloatField(null=True, blank=True)
    entry_lon = models.FloatField(null=True, blank=True)
    exit_lat = models.FloatField(null=True, blank=True)
    exit_lon = models.FloatField(null=True, blank=True)
    confidence = models.FloatField(null=True, blank=True, help_text="Face recognition confidence score")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PRESENT')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Attendance Record"
        verbose_name_plural = "Attendance Records"
        unique_together = ('student', 'date')
        ordering = ['-date', '-entry_time']

    def __str__(self):
        return f"{self.student.roll_number} - {self.date} [{self.get_status_display()}]"


class EmailOTP(models.Model):
    email = models.EmailField(db_index=True)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Email OTP Log"
        verbose_name_plural = "Email OTP Logs"
        ordering = ['-created_at']

    def is_valid(self):
        """Check if OTP is not used and not expired."""
        return not self.is_used and timezone.now() <= self.expires_at

    def __str__(self):
        return f"OTP for {self.email} ({'Used' if self.is_used else 'Active'})"


class CampusConfig(models.Model):
    center_latitude = models.FloatField(default=12.9715987, help_text="Campus Center Latitude")
    center_longitude = models.FloatField(default=77.5945627, help_text="Campus Center Longitude")
    radius_meters = models.FloatField(default=500.0, help_text="Allowed Radius in Meters")
    college_start_time = models.TimeField(default=datetime.time(9, 0), help_text="College Opening Time (09:00 AM)")
    college_end_time = models.TimeField(default=datetime.time(16, 0), help_text="College Closing Time (04:00 PM)")

    class Meta:
        verbose_name = "Campus Configuration"
        verbose_name_plural = "Campus Configurations"

    def __str__(self):
        return f"Campus Geo Center ({self.center_latitude}, {self.center_longitude}) - Radius {self.radius_meters}m"
