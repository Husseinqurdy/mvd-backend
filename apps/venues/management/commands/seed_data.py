from django.core.management.base import BaseCommand
from datetime import date, time


class Command(BaseCommand):
    help = 'Seed database with sample MUST data'

    def handle(self, *args, **options):
        from apps.accounts.models import User
        from apps.venues.models import Building, Venue
        from apps.timetable.models import AcademicPeriod

        self.stdout.write('Seeding...')

        # Buildings from IST PDF
        b1, _ = Building.objects.get_or_create(code='COMP-LAB', defaults={'name': 'Computer Laboratory Wing'})
        b2, _ = Building.objects.get_or_create(code='CIVIL',    defaults={'name': 'Civil & Architecture Wing'})
        b3, _ = Building.objects.get_or_create(code='THEATRE',  defaults={'name': 'Theatres Zone'})
        b4, _ = Building.objects.get_or_create(code='LIBRARY',  defaults={'name': 'Dr. Magufuli Library'})
        b5, _ = Building.objects.get_or_create(code='ACADEMIC', defaults={'name': 'Academic Block'})

        venues = [
            dict(building=b1, name='Central Computer Lab 1', code='COMP. LAB 01', venue_type='LAB',          capacity=50),
            dict(building=b1, name='Central Computer Lab 2', code='COMP. LAB 02', venue_type='LAB',          capacity=50),
            dict(building=b1, name='Workshop Computer Lab 3',code='WCL 03',        venue_type='LAB',          capacity=50),
            dict(building=b2, name='Mechanical Wing 211',    code='211-C',         venue_type='LECTURE_HALL', capacity=70),
            dict(building=b2, name='Civil Wing D005',        code='D 005',         venue_type='LECTURE_HALL', capacity=130),
            dict(building=b2, name='Civil Wing D006',        code='D006',          venue_type='LECTURE_HALL', capacity=130),
            dict(building=b3, name='Theatre 1',              code='TH 01',         venue_type='THEATRE',      capacity=110),
            dict(building=b3, name='Theatre 2',              code='TH 02',         venue_type='THEATRE',      capacity=110),
            dict(building=b4, name='Library Phase II Ground Floor', code='LPII-GF-R', venue_type='LIBRARY',  capacity=110),
            dict(building=b4, name='Library Phase II Basement P1',  code='LPII-BF-P1', venue_type='LIBRARY', capacity=110),
            dict(building=b5, name='Academic Block A-118',   code='A-118',         venue_type='LECTURE_HALL', capacity=100),
            dict(building=b5, name='Academic Block A-109',   code='A-109',         venue_type='LECTURE_HALL', capacity=93),
        ]
        for v in venues:
            Venue.objects.get_or_create(code=v['code'], defaults=v)

        # Period
        period, _ = AcademicPeriod.objects.get_or_create(
            name='Semester II — 2025/2026',
            defaults={'start_date': date(2026, 1, 20), 'end_date': date(2026, 6, 30), 'is_active': True},
        )

        # Users
        admin_u, created = User.objects.get_or_create(email='admin@must.ac.tz', defaults={
            'full_name': 'System Admin', 'role': 'ADMIN', 'is_staff': True, 'is_superuser': True,
        })
        if created:
            admin_u.set_password('admin1234'); admin_u.save()

        lec, created = User.objects.get_or_create(email='mlay@must.ac.tz', defaults={
            'full_name': 'Eng. Joshua Mlay', 'role': 'LECTURER', 'department': 'Electrical Engineering',
        })
        if created:
            lec.set_password('lecturer1234'); lec.save()

        cr, created = User.objects.get_or_create(email='cr@must.ac.tz', defaults={
            'full_name': 'Class Representative', 'role': 'CLASS_REP', 'department': 'ICT',
        })
        if created:
            cr.set_password('cr1234'); cr.save()

        self.stdout.write(self.style.SUCCESS(
            '\n✅ Seed complete!\n'
            '   Admin:    admin@must.ac.tz  / admin1234\n'
            '   Lecturer: mlay@must.ac.tz   / lecturer1234\n'
            '   Class Rep:cr@must.ac.tz     / cr1234\n\n'
            '   Upload the IST timetable PDF at: /dashboard/timetable/import\n'
        ))
