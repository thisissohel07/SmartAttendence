from django.urls import path
from . import views

urlpatterns = [
    # Homepage Landing (Options to Login or Register)
    path('', views.home_view, name='home'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Registration Flow (Passwordless OTP + Live Face Capture)
    path('register/', views.register_step1_view, name='register_step1'),
    path('register/verify-otp/', views.register_verify_otp_view, name='register_verify_otp'),
    path('register/capture-face/', views.register_capture_face_view, name='register_capture_face'),

    # Passwordless Login Flow & Admin Login
    path('login/', views.auth_login_view, name='auth_login'),
    path('login/verify-otp/', views.login_verify_otp_view, name='login_verify_otp'),
    path('admin-login/', views.admin_login_view, name='admin_login'),
    path('logout/', views.logout_view, name='logout'),

    # Attendance Biometric & Geofencing Scanners
    path('scan/entry/', views.scan_entry_view, name='scan_entry'),
    path('scan/exit/', views.scan_exit_view, name='scan_exit'),

    # Analytics & Reports
    path('reports/', views.reports_view, name='reports'),
    path('profile/', views.profile_view, name='profile'),
]
