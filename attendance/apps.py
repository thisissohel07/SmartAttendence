from django.apps import AppConfig

class AttendanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'attendance'
    verbose_name = 'Smart Attendance Management'

    def ready(self):
        import attendance.signals  # noqa
