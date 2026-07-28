import json
import random
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Q
from django.views.decorators.http import require_POST, require_GET
from django.urls import reverse

from .models import Department, Student, Attendance, EmailOTP, CampusConfig
from .forms import StudentRegistrationForm, VerifyOTPForm, LoginForm, StudentProfileEditForm, AdminLoginForm
from .services.face import (
    base64_to_cv2_image, detect_and_extract_face,
    face_to_bytes, check_duplicate_face, verify_face
)
from .services.geo import verify_location
from .services.emailer import send_otp_email, send_early_exit_alert
from .services.reports import generate_excel_report, generate_pdf_report


def get_default_campus_config():
    """Retrieve or create default campus configuration."""
    config, _ = CampusConfig.objects.get_or_create(
        id=1,
        defaults={
            'center_latitude': 12.9715987,
            'center_longitude': 77.5945627,
            'radius_meters': 500.0,
            'college_start_time': datetime.time(9, 0),
            'college_end_time': datetime.time(16, 0),
        }
    )
    return config


def home_view(request):
    """Homepage landing view. Clears any cached session so visiting homepage always forces fresh re-login."""
    if request.user.is_authenticated:
        auth_logout(request)
    return render(request, 'attendance/home.html')


@login_required
def dashboard_view(request):
    """
    Dashboard View:
    - Admin (is_staff): College-wide analytics, stat cards, department charts, and all student logs.
    - Regular Student (not is_staff): Personal student dashboard showing only THEIR OWN profile & personal attendance.
    """
    student = getattr(request.user, 'student_profile', None)

    if not request.user.is_staff:
        # Regular Student View
        student_attendances = Attendance.objects.filter(student=student).order_by('-date', '-entry_time') if student else []
        today_att = student_attendances.filter(date=timezone.now().date()).first() if student else None

        context = {
            'student': student,
            'student_attendances': student_attendances,
            'today_att': today_att,
            'is_student_view': True,
        }
        return render(request, 'attendance/dashboard.html', context)

    # Admin / Staff View
    today = timezone.now().date()
    total_students = Student.objects.count()
    total_departments = Department.objects.count()
    registered_faces = Student.objects.exclude(face_bytes=None).count()

    today_attendances = Attendance.objects.filter(date=today)
    present_today = today_attendances.filter(status__in=['PRESENT', 'LATE']).count()
    late_today = today_attendances.filter(status='LATE').count()
    left_early_today = today_attendances.filter(status='LEFT_EARLY').count()
    absent_today = max(0, total_students - present_today - left_early_today)

    attendance_percentage = round((present_today / total_students * 100), 1) if total_students > 0 else 0.0

    recent_attendances = Attendance.objects.select_related('student__user', 'student__department').order_by('-created_at')[:10]

    status_chart_data = {
        'Present': today_attendances.filter(status='PRESENT').count(),
        'Late': late_today,
        'Left Early': left_early_today,
        'Absent': absent_today,
    }

    dept_labels = []
    dept_present_counts = []
    dept_avg_percentages = []

    for dept in Department.objects.all():
        dept_labels.append(dept.name)
        count = today_attendances.filter(student__department=dept, status__in=['PRESENT', 'LATE', 'LEFT_EARLY']).count()
        dept_present_counts.append(count)

        dept_students = Student.objects.filter(department=dept)
        if dept_students.exists():
            dept_pcts = []
            for st in dept_students:
                att_c = st.attendances.filter(status__in=['PRESENT', 'LATE', 'LEFT_EARLY']).count()
                tot_d = st.attendances.values('date').distinct().count() or 1
                dept_pcts.append((att_c / tot_d) * 100)
            avg_pct = round(sum(dept_pcts) / len(dept_pcts), 1)
        else:
            avg_pct = 0.0
        dept_avg_percentages.append(avg_pct)

    past_7_days = [(today - datetime.timedelta(days=i)) for i in range(6, -1, -1)]
    trend_labels = [d.strftime('%b %d') for d in past_7_days]
    trend_counts = [Attendance.objects.filter(date=d, status__in=['PRESENT', 'LATE', 'LEFT_EARLY']).count() for d in past_7_days]

    # Overall Attendance Percentage calculation for all students by Department
    student_summary = []
    total_college_days = Attendance.objects.values('date').distinct().count() or 1

    all_students = Student.objects.select_related('user', 'department').all().order_by('department__name', 'roll_number')
    for st in all_students:
        att_count = st.attendances.filter(status__in=['PRESENT', 'LATE', 'LEFT_EARLY']).count()
        total_st_days = st.attendances.values('date').distinct().count() or total_college_days
        pct = round((att_count / total_st_days * 100), 1) if total_st_days > 0 else 0.0
        
        student_summary.append({
            'roll_number': st.roll_number,
            'name': st.user.get_full_name() or st.user.username,
            'department': st.department.name if st.department else "N/A",
            'present_days': att_count,
            'total_days': total_st_days,
            'percentage': pct,
        })

    context = {
        'total_students': total_students,
        'total_departments': total_departments,
        'registered_faces': registered_faces,
        'present_today': present_today,
        'absent_today': absent_today,
        'late_today': late_today,
        'left_early_today': left_early_today,
        'attendance_percentage': attendance_percentage,
        'recent_attendances': recent_attendances,
        'student_summary': student_summary,
        'status_chart_data_json': json.dumps(status_chart_data),
        'dept_labels_json': json.dumps(dept_labels),
        'dept_counts_json': json.dumps(dept_present_counts),
        'dept_avg_percentages_json': json.dumps(dept_avg_percentages),
        'trend_labels_json': json.dumps(trend_labels),
        'trend_counts_json': json.dumps(trend_counts),
        'is_student_view': False,
    }
    return render(request, 'attendance/dashboard.html', context)


# ==============================================================================
# STUDENT REGISTRATION FLOW (Passwordless, OTP + Live Face Capture)
# ==============================================================================

def register_step1_view(request):
    """Step 1: Collect Name, Roll Number, Email, Department and send OTP."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            full_name = form.cleaned_data['full_name']
            roll_number = form.cleaned_data['roll_number']
            department = form.cleaned_data['department']

            # Generate 6-digit OTP
            otp = f"{random.randint(100000, 999999)}"
            expires_at = timezone.now() + datetime.timedelta(minutes=5)

            # Invalidate old OTPs for this email
            EmailOTP.objects.filter(email=email).update(is_used=True)

            EmailOTP.objects.create(
                email=email,
                otp=otp,
                expires_at=expires_at
            )

            # Store in session
            request.session['pending_registration'] = {
                'full_name': full_name,
                'roll_number': roll_number,
                'email': email,
                'department_id': department.id,
                'otp_verified': False
            }

            # Send Email OTP
            success, msg = send_otp_email(email, otp)
            messages.success(request, f"OTP sent to {email}. Valid for 5 minutes.")
            return redirect('register_verify_otp')
    else:
        form = StudentRegistrationForm()

    return render(request, 'attendance/register_step1.html', {'form': form})


def register_verify_otp_view(request):
    """Step 2: Verify OTP sent to Gmail."""
    pending = request.session.get('pending_registration')
    if not pending:
        messages.error(request, "Registration session expired. Please start again.")
        return redirect('register_step1')

    if request.method == 'POST':
        form = VerifyOTPForm(request.POST)
        if form.is_valid():
            user_otp = form.cleaned_data['otp'].strip()
            email = pending['email'].strip().lower()

            otp_record = EmailOTP.objects.filter(
                email__iexact=email,
                otp=user_otp
            ).order_by('-created_at').first()

            if not otp_record:
                messages.error(request, "Invalid OTP code. Please check your email and try again.")
            elif otp_record.is_used:
                messages.error(request, "This OTP has already been used. Please request a new OTP.")
            elif timezone.now() > otp_record.expires_at:
                messages.error(request, "OTP expired. Please request a new registration.")
                del request.session['pending_registration']
                return redirect('register_step1')
            else:
                # Mark OTP as used
                otp_record.is_used = True
                otp_record.save()

                pending['otp_verified'] = True
                request.session['pending_registration'] = pending
                messages.success(request, "OTP verified successfully! Please capture your face.")
                return redirect('register_capture_face')
    else:
        form = VerifyOTPForm()

    return render(request, 'attendance/register_verify_otp.html', {
        'form': form,
        'email': pending['email']
    })


def register_capture_face_view(request):
    """Step 3: Automatically open webcam, scan single face, prevent duplicates & save."""
    pending = request.session.get('pending_registration')
    if not pending or not pending.get('otp_verified'):
        messages.error(request, "Unauthorized access. Complete OTP verification first.")
        return redirect('register_step1')

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_base64 = data.get('image')

            if not image_base64:
                return JsonResponse({'success': False, 'message': 'No image data received.'})

            # Convert base64 to cv2 image
            bgr_img = base64_to_cv2_image(image_base64)

            # Detect single face
            success, msg, face_gray, bbox = detect_and_extract_face(bgr_img)
            if not success:
                return JsonResponse({'success': False, 'message': msg})

            # Check duplicate face against existing registered students
            existing_students = Student.objects.exclude(face_bytes=None)
            is_dup, dup_student = check_duplicate_face(face_gray, existing_students)
            if is_dup:
                return JsonResponse({
                    'success': False,
                    'message': f"Face already registered under Roll Number: {dup_student.roll_number}."
                })

            # Convert face to PNG bytes for DB storage
            face_bytes = face_to_bytes(face_gray)

            # Create User and Student Record
            department = get_object_or_404(Department, id=pending['department_id'])
            
            # Use email as username
            username = pending['email']
            first_name = pending['full_name'].split()[0]
            last_name = " ".join(pending['full_name'].split()[1:]) if len(pending['full_name'].split()) > 1 else ""

            user = User.objects.create_user(
                username=username,
                email=pending['email'],
                first_name=first_name,
                last_name=last_name
            )
            user.set_unusable_password()
            user.save()

            student = Student.objects.create(
                user=user,
                roll_number=pending['roll_number'],
                department=department,
                face_bytes=face_bytes
            )

            # Log user in
            auth_login(request, user)

            # Clear session data
            del request.session['pending_registration']

            return JsonResponse({
                'success': True,
                'message': 'Registration successful! Face enrolled securely.',
                'redirect_url': reverse('dashboard')
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': f"Error processing face: {str(e)}"})

    return render(request, 'attendance/register_capture_face.html', {'pending': pending})


# ==============================================================================
# PASSWORDLESS LOGIN FLOW
# ==============================================================================

def auth_login_view(request):
    """Passwordless Login: Email input. Requires fresh OTP verification every time."""
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']

            # Generate OTP
            otp = f"{random.randint(100000, 999999)}"
            expires_at = timezone.now() + datetime.timedelta(minutes=5)

            EmailOTP.objects.filter(email=email).update(is_used=True)
            EmailOTP.objects.create(
                email=email,
                otp=otp,
                expires_at=expires_at
            )

            request.session['pending_login_email'] = email
            send_otp_email(email, otp)
            messages.success(request, f"OTP sent to {email}. Valid for 5 minutes.")
            return redirect('login_verify_otp')
    else:
        form = LoginForm()

    return render(request, 'attendance/auth_login.html', {'form': form})


def admin_login_view(request):
    """Admin / Faculty Login View inside Attendance Management System UI."""
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AdminLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username'].strip()
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)

            if user is not None and user.is_staff:
                auth_login(request, user)
                messages.success(request, f"Welcome to Admin Portal, {user.get_full_name() or user.username}!")
                return redirect('dashboard')
            else:
                messages.error(request, "Invalid Admin credentials or staff access required.")
    else:
        form = AdminLoginForm()

    return render(request, 'attendance/admin_login.html', {'form': form})


def login_verify_otp_view(request):
    """Passwordless Login: OTP verification."""
    email = request.session.get('pending_login_email')
    if not email:
        messages.error(request, "Login session expired. Please enter your email.")
        return redirect('auth_login')

    if request.method == 'POST':
        form = VerifyOTPForm(request.POST)
        if form.is_valid():
            user_otp = form.cleaned_data['otp'].strip()
            clean_email = email.strip().lower()

            otp_record = EmailOTP.objects.filter(
                email__iexact=clean_email,
                otp=user_otp
            ).order_by('-created_at').first()

            if not otp_record:
                messages.error(request, "Invalid OTP code. Please check your email and try again.")
            elif otp_record.is_used:
                messages.error(request, "This OTP has already been used. Please request a new OTP.")
            elif timezone.now() > otp_record.expires_at:
                messages.error(request, "OTP expired. Please request a new OTP.")
                del request.session['pending_login_email']
                return redirect('auth_login')
            else:
                otp_record.is_used = True
                otp_record.save()

                user = User.objects.get(email=email)
                auth_login(request, user)

                del request.session['pending_login_email']
                messages.success(request, f"Welcome back, {user.get_full_name()}!")
                return redirect('dashboard')
    else:
        form = VerifyOTPForm()

    return render(request, 'attendance/login_verify_otp.html', {'form': form, 'email': email})


def logout_view(request):
    """Log out current user."""
    auth_logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('auth_login')


# ==============================================================================
# ENTRY & EXIT ATTENDANCE SCANNING (Biometric Face + Geofencing)
# ==============================================================================

@login_required
def scan_entry_view(request):
    """
    Entry Attendance Scanning View.
    Validates GPS Geofencing + OpenCV LBPH Face Recognition + College Timings.
    """
    if request.user.is_staff:
        messages.warning(request, "Admins/Faculty do not perform student attendance scans.")
        return redirect('dashboard')

    campus_config = get_default_campus_config()

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_base64 = data.get('image')
            user_lat = data.get('latitude')
            user_lon = data.get('longitude')

            # 1. GPS Verification
            is_inside, distance, geo_msg = verify_location(user_lat, user_lon, campus_config)
            if not is_inside:
                return JsonResponse({'success': False, 'message': geo_msg, 'reason': 'GPS_FAILED'})

            # 2. Face Detection
            bgr_img = base64_to_cv2_image(image_base64)
            success, face_msg, face_gray, bbox = detect_and_extract_face(bgr_img)
            if not success:
                return JsonResponse({'success': False, 'message': face_msg, 'reason': 'FACE_FAILED'})

            # 3. Match Face against current logged in student (or any registered student)
            student = getattr(request.user, 'student_profile', None)
            if not student:
                # Fallback: Search among all students to match face
                existing_students = Student.objects.exclude(face_bytes=None)
                is_dup, matched_student = check_duplicate_face(face_gray, existing_students, threshold=70.0)
                if is_dup:
                    student = matched_student
                else:
                    return JsonResponse({'success': False, 'message': 'Face not recognized.', 'reason': 'FACE_MISMATCH'})
            else:
                is_match, conf = verify_face(face_gray, student, threshold=70.0)
                if not is_match:
                    return JsonResponse({'success': False, 'message': 'Face not recognized.', 'reason': 'FACE_MISMATCH'})

            # 4. Check if student has ALREADY completed entry scan today
            now_dt = timezone.now()
            today = now_dt.date()
            current_time = now_dt.time()

            existing_att = Attendance.objects.filter(student=student, date=today).first()
            if existing_att and existing_att.entry_time:
                time_str = existing_att.entry_time.strftime("%I:%M %p")
                return JsonResponse({
                    'success': False,
                    'message': f"Today's entry is completed! (Marked at {time_str})",
                    'reason': 'ALREADY_COMPLETED'
                })

            # Determine status: LATE if arriving after start time
            status = 'PRESENT'
            if current_time > campus_config.college_start_time:
                status = 'LATE'

            attendance, created = Attendance.objects.get_or_create(
                student=student,
                date=today,
                defaults={
                    'entry_time': current_time,
                    'entry_lat': user_lat,
                    'entry_lon': user_lon,
                    'status': status,
                    'confidence': 92.5
                }
            )

            if not created and not attendance.entry_time:
                attendance.entry_time = current_time
                attendance.entry_lat = user_lat
                attendance.entry_lon = user_lon
                attendance.status = status
                attendance.save()

            time_str = current_time.strftime("%I:%M %p")
            status_text = "LATE" if status == 'LATE' else "PRESENT"
            return JsonResponse({
                'success': True,
                'message': f"Entry attendance marked as {status_text} at {time_str}!",
                'student_name': student.user.get_full_name(),
                'roll_number': student.roll_number,
                'status': status_text,
                'time': time_str
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': f"Server error: {str(e)}"})

    today = timezone.now().date()
    student = getattr(request.user, 'student_profile', None)
    already_completed = False
    completed_time_str = ""

    if student:
        att = Attendance.objects.filter(student=student, date=today).first()
        if att and att.entry_time:
            already_completed = True
            completed_time_str = att.entry_time.strftime("%I:%M %p")

    context = {
        'campus_config': campus_config,
        'already_completed': already_completed,
        'completed_time_str': completed_time_str,
    }
    return render(request, 'attendance/scan_entry.html', context)


@login_required
def scan_exit_view(request):
    """
    Exit Attendance Scanning View.
    Checks face + GPS. If exiting before 4:00 PM (college_end_time), marks status LEFT_EARLY & emails HOD.
    """
    if request.user.is_staff:
        messages.warning(request, "Admins/Faculty do not perform student attendance scans.")
        return redirect('dashboard')

    campus_config = get_default_campus_config()

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_base64 = data.get('image')
            user_lat = data.get('latitude')
            user_lon = data.get('longitude')

            # 1. GPS Verification
            is_inside, distance, geo_msg = verify_location(user_lat, user_lon, campus_config)
            if not is_inside:
                return JsonResponse({'success': False, 'message': geo_msg, 'reason': 'GPS_FAILED'})

            # 2. Face Detection
            bgr_img = base64_to_cv2_image(image_base64)
            success, face_msg, face_gray, bbox = detect_and_extract_face(bgr_img)
            if not success:
                return JsonResponse({'success': False, 'message': face_msg, 'reason': 'FACE_FAILED'})

            # 3. Match Face
            student = getattr(request.user, 'student_profile', None)
            if not student:
                existing_students = Student.objects.exclude(face_bytes=None)
                is_dup, matched_student = check_duplicate_face(face_gray, existing_students, threshold=70.0)
                if is_dup:
                    student = matched_student
                else:
                    return JsonResponse({'success': False, 'message': 'Face not recognized.', 'reason': 'FACE_MISMATCH'})
            else:
                is_match, conf = verify_face(face_gray, student, threshold=70.0)
                if not is_match:
                    return JsonResponse({'success': False, 'message': 'Face not recognized.', 'reason': 'FACE_MISMATCH'})

            # 4. Check if student has ALREADY completed exit scan today
            now_dt = timezone.now()
            today = now_dt.date()
            current_time = now_dt.time()

            existing_att = Attendance.objects.filter(student=student, date=today).first()
            if existing_att and existing_att.exit_time:
                time_str = existing_att.exit_time.strftime("%I:%M %p")
                return JsonResponse({
                    'success': False,
                    'message': f"Today's exit is completed! (Marked at {time_str})",
                    'reason': 'ALREADY_COMPLETED'
                })

            if not existing_att or not existing_att.entry_time:
                return JsonResponse({
                    'success': False,
                    'message': "Entry scan missing! You must complete Scan Entry before scanning exit.",
                    'reason': 'NO_ENTRY'
                })

            existing_att.exit_time = current_time
            existing_att.exit_lat = user_lat
            existing_att.exit_lon = user_lon

            # Check if student is leaving before college closing hours
            is_early_exit = current_time < campus_config.college_end_time
            if is_early_exit:
                existing_att.status = 'LEFT_EARLY'
                existing_att.save()
                send_early_exit_alert(existing_att)
                exit_msg = f"Exit recorded at {current_time.strftime('%I:%M %p')}. Marked as LEFT_EARLY. Department alert sent."
            else:
                existing_att.save()
                exit_msg = f"Exit attendance marked successfully at {current_time.strftime('%I:%M %p')}!"

            return JsonResponse({
                'success': True,
                'message': exit_msg,
                'student_name': student.user.get_full_name(),
                'roll_number': student.roll_number,
                'exit_time': current_time.strftime('%I:%M %p'),
                'is_early_exit': is_early_exit
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': f"Server error: {str(e)}"})

    today = timezone.now().date()
    student = getattr(request.user, 'student_profile', None)
    already_completed = False
    completed_time_str = ""

    if student:
        att = Attendance.objects.filter(student=student, date=today).first()
        if att and att.exit_time:
            already_completed = True
            completed_time_str = att.exit_time.strftime("%I:%M %p")

    context = {
        'campus_config': campus_config,
        'already_completed': already_completed,
        'completed_time_str': completed_time_str,
    }
    return render(request, 'attendance/scan_exit.html', context)


# ==============================================================================
# REPORTS & EXPORT (Excel / PDF)
# ==============================================================================

@login_required
def reports_view(request):
    """Attendance reports, searching, filtering, and Excel/PDF downloading (Admin/Staff only)."""
    if not request.user.is_staff:
        messages.error(request, "Access Denied: Reports & department analytics are restricted to Admin/Faculty.")
        return redirect('dashboard')

    queryset = Attendance.objects.select_related('student__user', 'student__department').order_by('-date', '-entry_time')

    # Filter parameters
    search_query = request.GET.get('q', '').strip()
    dept_id = request.GET.get('department')
    status = request.GET.get('status')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if search_query:
        queryset = queryset.filter(
            Q(student__roll_number__icontains=search_query) |
            Q(student__user__first_name__icontains=search_query) |
            Q(student__user__last_name__icontains=search_query) |
            Q(student__user__email__icontains=search_query)
        )

    if dept_id:
        queryset = queryset.filter(student__department_id=dept_id)

    if status:
        queryset = queryset.filter(status=status)

    if start_date:
        queryset = queryset.filter(date__gte=start_date)

    if end_date:
        queryset = queryset.filter(date__lte=end_date)

    # Export options
    export_format = request.GET.get('export')
    if export_format == 'excel':
        excel_bytes = generate_excel_report(queryset)
        response = HttpResponse(excel_bytes, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="attendance_report_{timezone.now().strftime("%Y%m%d")}.xlsx"'
        return response
    elif export_format == 'pdf':
        pdf_bytes = generate_pdf_report(queryset)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="attendance_report_{timezone.now().strftime("%Y%m%d")}.pdf"'
        return response

    context = {
        'attendances': queryset[:100],  # Limit display list to 100 for fast page rendering
        'departments': Department.objects.all(),
        'search_query': search_query,
        'selected_dept': dept_id,
        'selected_status': status,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'attendance/reports.html', context)


@login_required
def profile_view(request):
    """Student Profile, editing name & department, and personal attendance history."""
    student = getattr(request.user, 'student_profile', None)
    attendances = Attendance.objects.filter(student=student).order_by('-date') if student else []

    if request.method == 'POST':
        form = StudentProfileEditForm(request.POST)
        if form.is_valid():
            full_name = form.cleaned_data['full_name'].strip()
            department = form.cleaned_data['department']

            # Update User first_name and last_name
            name_parts = full_name.split()
            first_name = name_parts[0] if name_parts else ""
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

            user = request.user
            user.first_name = first_name
            user.last_name = last_name
            user.save()

            # Update Student department
            if student:
                student.department = department
                student.save()

            messages.success(request, "Profile updated successfully!")
            return redirect('profile')
    else:
        initial_data = {
            'full_name': request.user.get_full_name() or request.user.username,
            'department': student.department if student else None
        }
        form = StudentProfileEditForm(initial=initial_data)

    return render(request, 'attendance/profile.html', {
        'student': student,
        'attendances': attendances,
        'form': form
    })
