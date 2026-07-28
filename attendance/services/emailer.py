import logging
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

def send_otp_email(recipient_email, otp_code):
    """
    Send OTP verification email using Gmail SMTP.
    OTP expires in 5 minutes.
    """
    subject = "Smart Attendance System - Verification OTP"
    from_email = settings.DEFAULT_FROM_EMAIL

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f7fe; padding: 20px; }}
            .container {{ max-width: 500px; margin: 0 auto; background: #ffffff; border-radius: 12px; padding: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }}
            .header {{ text-align: center; border-bottom: 2px solid #4f46e5; padding-bottom: 15px; margin-bottom: 20px; }}
            .header h2 {{ color: #4f46e5; margin: 0; }}
            .otp-box {{ font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #4f46e5; background: #eef2ff; padding: 15px 25px; text-align: center; border-radius: 8px; margin: 20px 0; border: 1px dashed #4f46e5; }}
            .footer {{ font-size: 12px; color: #6b7280; text-align: center; margin-top: 25px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Smart Attendance System</h2>
            </div>
            <p>Hello,</p>
            <p>Your One-Time Password (OTP) for verification is:</p>
            <div class="otp-box">{otp_code}</div>
            <p><strong>Note:</strong> This OTP is valid for <strong>5 minutes</strong> and can only be used once. Do not share this code with anyone.</p>
            <div class="footer">
                &copy; Smart Attendance Management System. Secure Biometric & GPS Authentication.
            </div>
        </div>
    </body>
    </html>
    """
    text_content = f"Smart Attendance System Verification OTP: {otp_code}. Valid for 5 minutes."

    try:
        msg = EmailMultiAlternatives(subject, text_content, from_email, [recipient_email])
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        return True, "OTP sent successfully to email."
    except Exception as e:
        logger.error(f"Failed to send OTP email to {recipient_email}: {str(e)}")
        # Print to console for dev mode visibility
        print(f"\n[DEV MODE OTP FALLBACK] Recipient: {recipient_email} | OTP: {otp_code} | Error: {e}\n")
        return True, f"OTP generated: {otp_code} (Console fallback active)"


def send_early_exit_alert(attendance_record):
    """
    Send automatic alert email to the Department email address when a student exits before college closing hours.
    Email includes: Student Name, Roll Number, Department, Exit Time, Date.
    """
    student = attendance_record.student
    department = student.department

    if not department or not department.email:
        logger.warning(f"Department email not configured for department {department}")
        return False, "Department email not configured."

    subject = f"⚠️ EARLY EXIT ALERT: {student.user.get_full_name()} ({student.roll_number})"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_email = department.email

    exit_time_str = attendance_record.exit_time.strftime('%I:%M %p') if attendance_record.exit_time else "N/A"
    date_str = attendance_record.date.strftime('%B %d, %Y')

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #fff5f5; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; padding: 30px; border-top: 5px solid #ef4444; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }}
            .header {{ font-size: 20px; font-weight: bold; color: #dc2626; margin-bottom: 20px; }}
            .table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            .table td {{ padding: 10px; border-bottom: 1px solid #fee2e2; }}
            .table td.label {{ font-weight: bold; color: #4b5563; width: 35%; }}
            .table td.value {{ color: #111827; }}
            .badge {{ display: inline-block; padding: 4px 12px; border-radius: 9999px; background: #fef2f2; color: #991b1b; font-weight: bold; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                ⚠️ Student Early Exit Notification
            </div>
            <p>This is an automated notification to inform you that a student has logged an exit attendance prior to college closing hours.</p>
            
            <table class="table">
                <tr>
                    <td class="label">Student Name</td>
                    <td class="value">{student.user.get_full_name()}</td>
                </tr>
                <tr>
                    <td class="label">Roll Number</td>
                    <td class="value">{student.roll_number}</td>
                </tr>
                <tr>
                    <td class="label">Department</td>
                    <td class="value">{department.name}</td>
                </tr>
                <tr>
                    <td class="label">Exit Time</td>
                    <td class="value">{exit_time_str}</td>
                </tr>
                <tr>
                    <td class="label">Date</td>
                    <td class="value">{date_str}</td>
                </tr>
                <tr>
                    <td class="label">Status</td>
                    <td class="value"><span class="badge">LEFT_EARLY</span></td>
                </tr>
            </table>

            <p style="font-size: 13px; color: #6b7280;">Please verify with the student regarding authorized permission for leaving early.</p>
        </div>
    </body>
    </html>
    """

    text_content = f"Early Exit Alert: {student.user.get_full_name()} ({student.roll_number}) left early at {exit_time_str} on {date_str}."

    try:
        msg = EmailMultiAlternatives(subject, text_content, from_email, [recipient_email])
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        return True, "Early exit email alert sent successfully."
    except Exception as e:
        logger.error(f"Failed to send early exit email to {recipient_email}: {str(e)}")
        print(f"\n[DEV MODE EARLY EXIT EMAIL] Recipient: {recipient_email} | Student: {student.roll_number} | Error: {e}\n")
        return False, str(e)
