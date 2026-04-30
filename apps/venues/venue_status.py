from django.utils import timezone
from apps.venues.models import Venue
from apps.timetable.models import TimetableSession, AcademicPeriod


def _now():
    return timezone.localtime(timezone.now())


def _active_period():
    try:
        return AcademicPeriod.objects.get(is_active=True)
    except AcademicPeriod.DoesNotExist:
        return None


def _is_cancelled(session_id: int, date) -> bool:
    from apps.timetable.models import CancelledSession
    return CancelledSession.objects.filter(session_id=session_id, date=date).exists()


def get_venue_status(venue: Venue, at=None) -> dict:
    now     = at or _now()
    weekday = now.isoweekday()
    t       = now.time()
    today   = now.date()
    period  = _active_period()

    current = None
    if period:
        s = TimetableSession.objects.filter(
            period=period, venue=venue,
            day_of_week=weekday,
            start_time__lte=t, end_time__gt=t,
            is_active=True,
        ).select_related('program').first()
        if s and not _is_cancelled(s.id, today):
            current = _fmt_session(s)

    if not current:
        from apps.requests.models import VenueRequest
        r = VenueRequest.objects.filter(
            venue=venue, status='APPROVED',
            date=today,
            start_time__lte=t, end_time__gt=t,
        ).first()
        if r:
            current = _fmt_request(r)

    next_s = None
    if period:
        candidates = TimetableSession.objects.filter(
            period=period, venue=venue,
            day_of_week=weekday,
            start_time__gt=t, is_active=True,
        ).order_by('start_time')
        for n in candidates:
            if not _is_cancelled(n.id, today):
                next_s = _fmt_session(n)
                break

    return {
        'venue_id':        venue.id,
        'venue_code':      venue.code,
        'venue_name':      venue.name,
        'building':        venue.building.name,
        'capacity':        venue.capacity,
        'venue_type':      venue.get_venue_type_display(),
        'status':          'OCCUPIED' if current else 'AVAILABLE',
        'current_session': current,
        'next_session':    next_s,
        'evaluated_at':    now.isoformat(),
    }


def get_all_statuses() -> list:
    venues = Venue.objects.filter(is_active=True).select_related('building')
    return [get_venue_status(v) for v in venues]


def get_today_sessions() -> list:
    """
    Returns all timetable sessions + approved requests scheduled for TODAY.
    Used by TV Display.
    """
    now     = _now()
    weekday = now.isoweekday()
    today   = now.date()
    period  = _active_period()
    result  = []

    if period:
        sessions = TimetableSession.objects.filter(
            period=period,
            day_of_week=weekday,
            is_active=True,
        ).select_related('venue', 'venue__building', 'program').order_by('start_time')

        for s in sessions:
            cancelled = _is_cancelled(s.id, today)
            is_now      = s.start_time <= now.time() < s.end_time
            is_upcoming = s.start_time > now.time()
            result.append({
                'session_id':    s.id,
                'type':          'TIMETABLE',
                'course_code':   s.course_code,
                'course_name':   s.course_name,
                'lecturer':      s.lecturer_name or 'TBA',
                'program':       s.program.name if s.program else '',
                'year':          s.year_of_study,
                'group':         s.group,
                'start_time':    s.start_time.strftime('%H:%M'),
                'end_time':      s.end_time.strftime('%H:%M'),
                'venue_code':    s.venue.code,
                'venue_name':    s.venue.name,
                'building':      s.venue.building.name,
                'capacity':      s.venue.capacity,
                'cancelled':     cancelled,
                'is_now':        is_now and not cancelled,
                'is_upcoming':   is_upcoming and not cancelled,
            })

    # Also include approved venue requests for today
    from apps.requests.models import VenueRequest
    req_sessions = VenueRequest.objects.filter(
        date=today, status='APPROVED',
    ).select_related('venue', 'venue__building', 'requested_by').order_by('start_time')

    for r in req_sessions:
        import datetime
        st = r.start_time if isinstance(r.start_time, datetime.time) else r.start_time
        et = r.end_time   if isinstance(r.end_time,   datetime.time) else r.end_time
        is_now      = st <= now.time() < et
        is_upcoming = st > now.time()
        result.append({
            'session_id':    f'req_{r.id}',
            'type':          'REQUEST',
            'course_code':   '',
            'course_name':   r.purpose,
            'lecturer':      r.requested_by.full_name,
            'program':       '',
            'year':          '',
            'group':         '',
            'start_time':    st.strftime('%H:%M'),
            'end_time':      et.strftime('%H:%M'),
            'venue_code':    r.venue.code,
            'venue_name':    r.venue.name,
            'building':      r.venue.building.name,
            'capacity':      r.venue.capacity,
            'cancelled':     False,
            'is_now':        is_now,
            'is_upcoming':   is_upcoming,
        })

    # Sort combined list by start_time
    result.sort(key=lambda x: x['start_time'])
    return result


def _fmt_session(s: TimetableSession) -> dict:
    return {
        'type':        'TIMETABLE',
        'session_id':  s.id,
        'course_code': s.course_code,
        'course_name': s.course_name,
        'lecturer':    s.lecturer_name or 'TBA',
        'program':     s.program.name if s.program else '',
        'year':        s.year_of_study,
        'start_time':  s.start_time.strftime('%H:%M'),
        'end_time':    s.end_time.strftime('%H:%M'),
        'group':       s.group,
    }


def _fmt_request(r) -> dict:
    return {
        'type':        'REQUEST',
        'session_id':  None,
        'course_code': '',
        'course_name': r.purpose,
        'lecturer':    r.requested_by.full_name,
        'program':     '',
        'year':        '',
        'start_time':  r.start_time.strftime('%H:%M'),
        'end_time':    r.end_time.strftime('%H:%M'),
        'group':       '',
    }
