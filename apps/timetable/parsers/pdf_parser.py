"""
Parses MUST timetable PDFs.
Returns list of ParsedPage objects.

Key fix: consecutive slots of the same course+venue+day+group are MERGED
into one session. e.g. 7:30-8:15 + 8:15-9:45 = 7:30-9:45 (one session).
"""
import re
from dataclasses import dataclass, field
from datetime import time
from typing import Optional

try:
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False


@dataclass
class ParsedVenue:
    code: str
    name: str
    wing: str
    capacity: int


@dataclass
class ParsedModule:
    course_code: str
    course_name: str
    lecturer_name: str


@dataclass
class ParsedSlot:
    day: int
    start_time: time
    end_time: time
    course_code: str
    venue_code: str
    group: str
    is_cross: bool


@dataclass
class ParsedPage:
    college: str = ''
    department: str = ''
    program: str = ''
    uqf_level: int = 8
    year_of_study: int = 1
    semester: int = 1
    academic_year: str = ''
    slots: list = field(default_factory=list)
    modules: list = field(default_factory=list)
    venues: list = field(default_factory=list)


DAY_MAP = {
    'monday': 1, 'tuesday': 2, 'wednesday': 3,
    'thursday': 4, 'friday': 5, 'saturday': 6,
}
WORD_NUM = {'FIRST': 1, 'SECOND': 2, 'THIRD': 3, 'FOURTH': 4, 'FIFTH': 5}


def _parse_time(s: str) -> Optional[time]:
    m = re.match(r'^(\d{1,2}):(\d{2})$', s.strip())
    return time(int(m.group(1)), int(m.group(2))) if m else None


def _parse_range(s: str):
    parts = s.split('-')
    if len(parts) == 2:
        t1 = _parse_time(parts[0].strip())
        t2 = _parse_time(parts[1].strip())
        if t1 and t2:
            return t1, t2
    return None, None


def _parse_cell(cell: str) -> Optional[tuple]:
    if not cell or not cell.strip() or 'BREAK' in cell.upper():
        return None
    cross = cell.strip().endswith('*')
    cell  = cell.rstrip('* ').strip()
    parts = [p.strip() for p in cell.split('|')]
    if len(parts) < 2:
        return None
    course = parts[0].strip().upper()
    venue_part = parts[1].strip()
    group = ''
    gm = re.search(r'\bGRP\w+', venue_part, re.I)
    if gm:
        group = gm.group(0).upper()
        venue_part = venue_part[:gm.start()].strip()
    return course, venue_part.upper(), group, cross


def _parse_header(text: str) -> dict:
    r = {'college': '', 'department': '', 'program': '',
         'uqf_level': 8, 'year_of_study': 1, 'semester': 1, 'academic_year': ''}
    for line in text.split('\n'):
        lu = line.upper().strip()
        if 'COLLEGE OF' in lu:
            r['college'] = line.strip()
        elif 'DEPARTMENT OF' in lu:
            r['department'] = line.strip()
        elif any(x in lu for x in ['BACHELOR', 'DIPLOMA', 'MASTER', 'CERTIFICATE']):
            r['program'] = line.strip()
    m = re.search(r'UQF\s*(\d+)', text, re.I)
    if m:
        r['uqf_level'] = int(m.group(1))
    m = re.search(r'(FIRST|SECOND|THIRD|FOURTH|FIFTH)\s+YEAR', text, re.I)
    if m:
        r['year_of_study'] = WORD_NUM.get(m.group(1).upper(), 1)
    m = re.search(r'SEMESTER\s+(I{1,3}|[12])', text, re.I)
    if m:
        s = m.group(1).upper()
        r['semester'] = {'I': 1, 'II': 2, 'III': 3}.get(s, 1)
    m = re.search(r'(\d{4})[/-](\d{4})', text)
    if m:
        r['academic_year'] = f"{m.group(1)}-{m.group(2)}"
    return r


def _parse_modules(text: str) -> list:
    mods = []
    pat  = re.compile(r'([A-Z]{2,4}\s*\d{4})\s*[-–]\s*([^|]+)\|\s*(.+)', re.I)
    for line in text.split('\n'):
        m = pat.search(line)
        if m:
            mods.append(ParsedModule(
                course_code=m.group(1).strip().upper(),
                course_name=m.group(2).strip(),
                lecturer_name=m.group(3).strip(),
            ))
    return mods


def _parse_venues(text: str) -> list:
    venues = []
    in_sec = False
    for line in text.split('\n'):
        if 'VENUE DEFINITION' in line.upper():
            in_sec = True
            continue
        if not in_sec:
            continue
        if re.match(r'^\s*(CODE|VENUE TORE|PROGRAM|CROSS)', line, re.I):
            continue
        parts = [p.strip() for p in re.split(r'\s{2,}|\t', line.strip()) if p.strip()]
        if len(parts) >= 4:
            try:
                cap = int(parts[-1])
                venues.append(ParsedVenue(code=parts[0].upper(), name=parts[1], wing=parts[2], capacity=cap))
            except ValueError:
                pass
        elif len(parts) == 3:
            venues.append(ParsedVenue(code=parts[0].upper(), name=parts[1], wing=parts[2], capacity=0))
    return venues


def _merge_slots(slots: list) -> list:
    """
    Merge consecutive time slots that belong to the same session.

    The MUST PDF splits a session like 7:30-9:45 into multiple rows:
      7:30-8:15  CS101|LH1
      8:15-9:00  CS101|LH1
      9:00-9:45  CS101|LH1

    This function detects rows where:
      - Same day, course_code, venue_code, group
      - Previous slot's end_time == current slot's start_time  (consecutive)

    And merges them into a single slot: 7:30-9:45
    """
    if not slots:
        return slots

    merged = [slots[0]]
    for slot in slots[1:]:
        prev = merged[-1]
        is_same = (
            prev.day         == slot.day
            and prev.course_code == slot.course_code
            and prev.venue_code  == slot.venue_code
            and prev.group       == slot.group
            and prev.end_time    == slot.start_time   # strictly consecutive
        )
        if is_same:
            # Extend previous slot to cover current slot's end_time
            merged[-1] = ParsedSlot(
                day=prev.day,
                start_time=prev.start_time,
                end_time=slot.end_time,
                course_code=prev.course_code,
                venue_code=prev.venue_code,
                group=prev.group,
                is_cross=prev.is_cross,
            )
        else:
            merged.append(slot)

    return merged


def _parse_page(page) -> Optional[ParsedPage]:
    text = page.extract_text() or ''
    if 'MBEYA UNIVERSITY' not in text.upper():
        return None

    hdr     = _parse_header(text)
    modules = _parse_modules(text)
    venues  = _parse_venues(text)
    slots   = []

    # Use explicit table settings to ensure all columns are captured
    table_settings = {
        "vertical_strategy":   "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance":      5,
        "join_tolerance":      3,
        "edge_min_length":     3,
        "min_words_vertical":  1,
        "min_words_horizontal": 1,
    }
    table = page.extract_table(table_settings)
    # Fallback: try with text strategy if lines strategy misses columns
    if not table or not any(
        cell and cell.strip().lower() in DAY_MAP
        for cell in (table[0] if table else [])
    ):
        table = page.extract_table({
            "vertical_strategy":   "text",
            "horizontal_strategy": "lines",
        })
    if not table or not any(
        cell and cell.strip().lower() in DAY_MAP
        for cell in (table[0] if table else [])
    ):
        table = page.extract_table({
            "vertical_strategy":   "lines",
            "horizontal_strategy": "text",
        })

    if table and table[0]:
        day_cols = {}
        for ci, cell in enumerate(table[0]):
            if cell and cell.strip().lower() in DAY_MAP:
                day_cols[ci] = DAY_MAP[cell.strip().lower()]

        for row in table[1:]:
            if not row or not row[0]:
                continue
            slot_txt = (row[0] or '').strip()
            if 'BREAK' in slot_txt.upper():
                continue
            t1, t2 = _parse_range(slot_txt)
            if not t1:
                continue
            for ci, day in day_cols.items():
                if ci >= len(row):
                    continue
                parsed = _parse_cell(row[ci] or '')
                if not parsed:
                    continue
                course, venue_code, group, cross = parsed
                slots.append(ParsedSlot(
                    day=day, start_time=t1, end_time=t2,
                    course_code=course, venue_code=venue_code,
                    group=group, is_cross=cross,
                ))

    # Sort by day then start_time before merging — critical for merge to work
    slots.sort(key=lambda s: (s.day, s.start_time))

    # Merge consecutive slots of same course+venue+day+group into one session
    slots = _merge_slots(slots)

    return ParsedPage(
        college=hdr['college'], department=hdr['department'],
        program=hdr['program'], uqf_level=hdr['uqf_level'],
        year_of_study=hdr['year_of_study'], semester=hdr['semester'],
        academic_year=hdr['academic_year'],
        slots=slots, modules=modules, venues=venues,
    )


def parse_pdf(source) -> list:
    if not HAS_PDF:
        raise ImportError('pdfplumber not installed. Run: pip install pdfplumber')
    import io
    if isinstance(source, bytes):
        source = io.BytesIO(source)
    pages = []
    with pdfplumber.open(source) as pdf:
        for page in pdf.pages:
            p = _parse_page(page)
            if p and (p.slots or p.program):
                pages.append(p)
    return pages
