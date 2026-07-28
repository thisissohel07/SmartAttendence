from .models import CampusConfig, Student

def attendance_context(request):
    """Global context processor for header stats, campus config, and theme preferences."""
    campus_config = CampusConfig.objects.first()
    
    logged_in_student = None
    if request.user.is_authenticated and not request.user.is_staff:
        try:
            logged_in_student = request.user.student_profile
        except Student.DoesNotExist:
            pass

    return {
        'campus_config': campus_config,
        'logged_in_student': logged_in_student,
    }
