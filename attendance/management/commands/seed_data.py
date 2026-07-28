import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from attendance.models import Department, CampusConfig

class Command(BaseCommand):
    help = 'Seeds initial departments, admin user, and campus configuration.'

    def handle(self, *args, **options):
        self.stdout.write("Seeding database initial data...")

        # 1. Seed Departments
        depts = [
            ("Computer Science & Engineering", "cse.hod@college.edu"),
            ("Information Technology", "it.hod@college.edu"),
            ("Artificial Intelligence & Machine Learning (AIML)", "aiml.hod@college.edu"),
            ("Artificial Intelligence & Data Science (AIDS)", "aids.hod@college.edu"),
            ("Internet of Things (IOT)", "iot.hod@college.edu"),
            ("Electronics & Communication", "ece.hod@college.edu"),
            ("Mechanical Engineering", "mech.hod@college.edu"),
            ("Electrical & Electronics", "eee.hod@college.edu"),
        ]

        for name, email in depts:
            dept, created = Department.objects.get_or_create(
                name=name,
                defaults={'email': email}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Department: {name}"))

        # 2. Seed Campus Config
        config, created = CampusConfig.objects.get_or_create(
            id=1,
            defaults={
                'center_latitude': 12.9715987,
                'center_longitude': 77.5945627,
                'radius_meters': 500.0,
                'college_start_time': datetime.time(9, 0),
                'college_end_time': datetime.time(16, 0),
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Created default Campus Configuration."))

        # 3. Seed Superuser if not exists
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@smartattendance.com', 'admin123')
            self.stdout.write(self.style.SUCCESS("Created superuser: admin / admin123"))

        self.stdout.write(self.style.SUCCESS("Data seeding complete."))
