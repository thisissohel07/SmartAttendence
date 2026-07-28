# Smart Attendance Management System

A production-quality Smart Attendance Management System using Django, HTML5 Geolocation API, Bootstrap 5, OpenCV LBPH Face Recognition, and SQLite/PostgreSQL.

---

## Key Features

1. **Passwordless OTP Authentication**:
   - Registration and Login via Gmail SMTP Email OTP.
   - OTP expires in 5 minutes and is single-use (`is_used=True`).

2. **OpenCV LBPH Biometric Face Recognition**:
   - Single face detection (`haarcascade_frontalface_default.xml`).
   - Anti-spoofing protection (sharpness/blur texture variance check).
   - Duplicate face registration prevention.

3. **GPS Campus Geofencing**:
   - HTML5 Geolocation API sends latitude and longitude.
   - Haversine distance formula verifies student location within campus radius.

4. **Entry & Exit Attendance Rules**:
   - Entry attendance records timestamp, coordinates, and status (`PRESENT` or `LATE`).
   - Exit attendance records exit timestamp.
   - Exiting before 4:00 PM marks status as `LEFT_EARLY` and sends an automated alert email to the student's Department head.

5. **Analytics & Reports**:
   - Responsive Bootstrap 5 Glassmorphism UI with Dark & Light mode toggle.
   - Interactive Chart.js charts (Status Distribution Doughnut, Department Bar Chart, 7-Day Trend Line Chart).
   - Attendance report search/filtering with Excel (`openpyxl`) and PDF (`reportlab`) export capabilities.

---

## Setup & Running Locally

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Database Migrations**:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

3. **Seed Initial Data (Departments, Campus Config, Admin Account)**:
   ```bash
   python manage.py seed_data
   ```

4. **Run Development Server**:
   ```bash
   python manage.py runserver
   ```
   Access application at `http://127.0.0.1:8000/`.

