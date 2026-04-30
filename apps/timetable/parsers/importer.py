"""
Timetable importer — PDF and Excel/CSV.
Commits in batches of 50 to avoid long-running transactions that kill gunicorn workers.
"""
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
    lvl      = {6: 'DIPLOMA', 7: 'DIPLOMA', 8: 'BSC', 9: 'MSC'}.get(uqf, 'BSC')
    p_code   = ''.join(w[0] for w in prog_name.split()[:5]).upper() + f'-UQF{uqf}'
    prog, _  = Program.objects.get_or_create(
        code=p_code,
        defaults={'department': dep, 'name': prog_name, 'level': lvl, 'uqf_level': uqf},
    )
    return prog


def _commit_batch(batch: list, s: dict):
    """Insert a batch of TimetableSession dicts in one transaction."""
    if not batch:
        return
    with transaction.atomic():
        for kw in batch:
            try:
                TimetableSession.objects.create(**kw)
                s['sessions_created'] += 1
            except Exception as e:
                s['errors'].append(str(e)[:120])
                s['sessions_skipped'] += 1


# ── PDF Import ────────────────────────────────────────────────────────────────

def import_pdf(pages: list, period: AcademicPeriod, user, replace=False) -> dict:
    s = {'sessions_created': 0, 'sessions_skipped': 0, 'venues_created': 0, 'errors': []}

    # Delete old sessions outside of long transaction
    if replace:
        TimetableSession.objects.filter(period=period, import_source='pdf').delete()

    batch = []
    BATCH_SIZE = 50

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

            # Check duplicate
            exists = TimetableSession.objects.filter(
                period=period, venue=venue, day_of_week=slot.day,
                start_time=slot.start_time, course_code=slot.course_code,
                group=slot.group,
            ).exists()
            if exists:
                s['sessions_skipped'] += 1
                continue

            mod = mod_map.get(slot.course_code)
            batch.append(dict(
                period=period, program=prog, year_of_study=page.year_of_study,
                course_code=slot.course_code,
                course_name=mod.course_name if mod else '',
                lecturer_name=mod.lecturer_name if mod else '',
                venue=venue, day_of_week=slot.day,
                start_time=slot.start_time, end_time=slot.end_time,
                group=slot.group, is_cross_cutting=slot.is_cross,
                is_active=True, import_source='pdf',
            ))

            if len(batch) >= BATCH_SIZE:
                _commit_batch(batch, s)
                batch = []

    # Remaining
    _commit_batch(batch, s)

    TimetableImportLog.objects.create(
        imported_by=user, source='pdf', period=period,
        status='SUCCESS' if not s['errors'] else 'PARTIAL',
        sessions_created=s['sessions_created'],
        sessions_skipped=s['sessions_skipped'],
        venues_created=s['venues_created'],
        errors='\n'.join(s['errors'][:20]),
    )
    return s


# ── Excel / CSV Import ────────────────────────────────────────────────────────

def import_excel(rows: list, period: AcademicPeriod, user, source='excel', replace=False) -> dict:
    s = {'sessions_created': 0, 'sessions_skipped': 0, 'venues_created': 0, 'errors': []}

    if replace:
        TimetableSession.objects.filter(period=period, import_source=source).delete()

    batch = []
    BATCH_SIZE = 50

    for i, row in enumerate(rows):
        try:
            venue, created = _venue(
                row.get('venue_code', '').strip(),
                name=row.get('venue_name', ''),
                wing=row.get('building', ''),
                capacity=int(row.get('capacity', 0) or 0),
            )
            if created:
                s['venues_created'] += 1
        except Exception as e:
            s['errors'].append(f'Row {i+2} venue: {e}')
            s['sessions_skipped'] += 1
            continue

        try:
            prog = _program(
                row.get('program', 'Unknown Program'),
                row.get('department', 'Unknown Department'),
                row.get('college', 'Unknown College'),
                int(row.get('uqf_level', 8) or 8),
            )
        except Exception as e:
            s['errors'].append(f'Row {i+2} program: {e}')
            s['sessions_skipped'] += 1
            continue

        from datetime import time as dt_time
        def _t(v):
            if isinstance(v, dt_time):
                return v
            try:
                parts = str(v).strip().split(':')
                return dt_time(int(parts[0]), int(parts[1]))
            except Exception:
                return dt_time(7, 30)

        exists = TimetableSession.objects.filter(
            period=period, venue=venue,
            day_of_week=int(row.get('day_of_week', 1) or 1),
            start_time=_t(row.get('start_time')),
            course_code=str(row.get('course_code', '')).strip(),
            group=str(row.get('group', '')).strip(),
        ).exists()
        if exists:
            s['sessions_skipped'] += 1
            continue

        batch.append(dict(
            period=period, program=prog,
            year_of_study=int(row.get('year_of_study', 1) or 1),
            course_code=str(row.get('course_code', '')).strip(),
            course_name=str(row.get('course_name', '')).strip(),
            lecturer_name=str(row.get('lecturer_name', '')).strip(),
            venue=venue,
            day_of_week=int(row.get('day_of_week', 1) or 1),
            start_time=_t(row.get('start_time')),
            end_time=_t(row.get('end_time')),
            group=str(row.get('group', '')).strip(),
            is_cross_cutting=bool(row.get('is_cross_cutting', False)),
            is_active=True, import_source=source,
        ))

        if len(batch) >= BATCH_SIZE:
            _commit_batch(batch, s)
            batch = []

    _commit_batch(batch, s)

    TimetableImportLog.objects.create(
        imported_by=user, source=source, period=period,
        status='SUCCESS' if not s['errors'] else 'PARTIAL',
        sessions_created=s['sessions_created'],
        sessions_skipped=s['sessions_skipped'],
        venues_created=s['venues_created'],
        errors='\n'.join(s['errors'][:20]),
    )
    return s
