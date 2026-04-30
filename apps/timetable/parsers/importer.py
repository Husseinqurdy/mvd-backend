from django.utils import timezone
from django.db import transaction
from apps.venues.models import Building, Venue
from apps.timetable.models import (
    AcademicPeriod, College, Department, Program,
    TimetableSession, TimetableImportLog,
)

WING_BUILDING = {
    'MECHANICAL WING':           'Mechanical Wing',
    'ELECTRICAL WING':           'Electrical Wing',
    'CIVIL/ARCH WING':           'Civil & Architecture Wing',
    'COMPUTER LABORATORY WING':  'Computer Laboratory Wing',
    'THEATRES ZONE':             'Theatres Zone',
    'DR. MAGUFULI LIBRARY':      'Dr. Magufuli Library',
    'ACADEMIC BLOCK':            'Academic Block',
    'COSTE AND LABORATORY ZONE': 'COSTE & Laboratory Zone',
    'CENTRAL HALL WING':         'Central Hall Wing',
    'WORKSHOP':                  'Workshop Zone',
}


def _building(wing: str) -> Building:
    name = WING_BUILDING.get(wing.upper().strip(), wing or 'MUST Main Campus')
    code = ''.join(w[0] for w in name.split()[:4]).upper() or 'BLDG'
    b, _ = Building.objects.get_or_create(name=name, defaults={'code': code})
    return b


def _venue(code: str, name: str = '', wing: str = '', capacity: int = 0):
    try:
        return Venue.objects.get(code=code), False
    except Venue.DoesNotExist:
        pass
    cu = code.upper()
    nu = (name or code).upper()
    if 'LAB' in cu or 'LAB' in nu:
        vtype = 'LAB'
    elif 'TH ' in cu[:4] or 'THEATRE' in nu or 'NLH' in cu:
        vtype = 'THEATRE'
    elif 'LIBRARY' in nu or cu.startswith('LP') or cu.startswith('LG'):
        vtype = 'LIBRARY'
    else:
        vtype = 'LECTURE_HALL'
    v = Venue.objects.create(
        building=_building(wing), name=name or code,
        code=code, venue_type=vtype, capacity=capacity,
        wing=wing, is_active=True,
    )
    return v, True


def _program(prog_name, dept_name, college_name, uqf):
    col_code = ''.join(w[0] for w in college_name.split()[:4]).upper() or 'COL'
    col, _   = College.objects.get_or_create(name=college_name, defaults={'code': col_code})
    dep_code = ''.join(w[0] for w in dept_name.split()[:4]).upper() or 'DEPT'
    dep, _   = Department.objects.get_or_create(name=dept_name, defaults={'college': col, 'code': dep_code})
    lvl = {6: 'DIPLOMA', 7: 'DIPLOMA', 8: 'BSC', 9: 'MSC'}.get(uqf, 'BSC')
    p_code = ''.join(w[0] for w in prog_name.split()[:5]).upper() + f'-UQF{uqf}'
    prog, _ = Program.objects.get_or_create(
        code=p_code,
        defaults={'department': dep, 'name': prog_name, 'level': lvl, 'uqf_level': uqf},
    )
    return prog


@transaction.atomic
def import_pdf(pages: list, period: AcademicPeriod, user, replace=False) -> dict:
    s = {'sessions_created': 0, 'sessions_skipped': 0, 'venues_created': 0, 'errors': []}
    if replace:
        TimetableSession.objects.filter(period=period, import_source='pdf').delete()

    for page in pages:
        vdefs   = {v.code: v for v in page.venues}
        mod_map = {m.course_code: m for m in page.modules}
        try:
            prog = _program(
                page.program or 'Unknown Program',
                page.department or 'Unknown Department',
                page.college or 'Unknown College',
                page.uqf_level,
            )
        except Exception as e:
            s['errors'].append(f'Program: {e}')
            continue

        for slot in page.slots:
            vd = vdefs.get(slot.venue_code)
            try:
                venue, created = _venue(
                    slot.venue_code,
                    name=vd.name if vd else '',
                    wing=vd.wing if vd else '',
                    capacity=vd.capacity if vd else 0,
                )
                if created:
                    s['venues_created'] += 1
            except Exception as e:
                s['errors'].append(f'Venue {slot.venue_code}: {e}')
                s['sessions_skipped'] += 1
                continue

            mod = mod_map.get(slot.course_code)
            exists = TimetableSession.objects.filter(
                period=period, venue=venue, day_of_week=slot.day,
                start_time=slot.start_time, course_code=slot.course_code,
                group=slot.group,
            ).exists()
            if exists:
                s['sessions_skipped'] += 1
                continue

            TimetableSession.objects.create(
                period=period, program=prog, year_of_study=page.year_of_study,
                course_code=slot.course_code,
                course_name=mod.course_name if mod else '',
                lecturer_name=mod.lecturer_name if mod else '',
                venue=venue, day_of_week=slot.day,
                start_time=slot.start_time, end_time=slot.end_time,
                group=slot.group, is_cross_cutting=slot.is_cross,
                is_active=True, import_source='pdf',
            )
            s['sessions_created'] += 1

    TimetableImportLog.objects.create(
        imported_by=user, source='pdf', period=period,
        status='SUCCESS' if not s['errors'] else 'PARTIAL',
        sessions_created=s['sessions_created'],
        sessions_skipped=s['sessions_skipped'],
        venues_created=s['venues_created'],
        errors='\n'.join(s['errors'][:30]),
    )
    return s


@transaction.atomic
def import_excel(rows: list, period: AcademicPeriod, user, source='excel', replace=False) -> dict:
    s = {'sessions_created': 0, 'sessions_skipped': 0, 'venues_created': 0, 'errors': []}
    if replace:
        TimetableSession.objects.filter(period=period, import_source=source).delete()

    for row in rows:
        try:
            venue, created = _venue(row.venue_code)
            if created:
                s['venues_created'] += 1
        except Exception as e:
            s['errors'].append(f'Venue {row.venue_code}: {e}')
            s['sessions_skipped'] += 1
            continue

        prog = None
        if row.program_code:
            try:
                prog = Program.objects.get(code=row.program_code)
            except Program.DoesNotExist:
                pass

        exists = TimetableSession.objects.filter(
            period=period, venue=venue, day_of_week=row.day,
            start_time=row.start_time, course_code=row.course_code, group=row.group,
        ).exists()
        if exists:
            s['sessions_skipped'] += 1
            continue

        TimetableSession.objects.create(
            period=period, program=prog, year_of_study=row.year_of_study,
            course_code=row.course_code, course_name=row.course_name,
            lecturer_name=row.lecturer_name, venue=venue, day_of_week=row.day,
            start_time=row.start_time, end_time=row.end_time,
            group=row.group, is_cross_cutting=row.is_cross,
            is_active=True, import_source=source,
        )
        s['sessions_created'] += 1

    TimetableImportLog.objects.create(
        imported_by=user, source=source, period=period,
        status='SUCCESS' if not s['errors'] else 'PARTIAL',
        sessions_created=s['sessions_created'],
        sessions_skipped=s['sessions_skipped'],
        venues_created=s['venues_created'],
        errors='\n'.join(s['errors'][:30]),
    )
    return s
