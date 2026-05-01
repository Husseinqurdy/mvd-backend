"""
MUST Timetable PDF Parser — Text-based approach.
Reads the raw text from each page and parses the grid directly,
avoiding pdfplumber's table extraction which misses Thursday/Friday columns.
"""
import re
from dataclasses import dataclass, field
from datetime import time
from typing import Optional, List

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

# Matches time ranges like "07:30 - 08:15"
TIME_RANGE_RE = re.compile(r'^(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})$')
# Matches course|venue cells like "IT 6125 | Comp. LAB 02 *" or "BM 6117 | D 005"
CELL_RE = re.compile(r'([A-Z]{2,4}\s?\d{3,4}(?:\s[A-Z]+)?)\s*\|\s*([^\|]+?)(\s*\*)?\s*$', re.I)
# Group suffix like "GRP1", "GRP2", "GRP1"
GROUP_RE = re.compile(r'\b(GRP\w+)\b', re.I)


def _parse_time(s: str) -> Optional[time]:
    m = re.match(r'^(\d{1,2}):(\d{2})$', s.strip())
    return time(int(m.group(1)), int(m.group(2))) if m else None


def _parse_cell(cell: str):
    """Parse a timetable cell like 'IT 6125 | Comp. LAB 02 *' """
    cell = cell.strip()
    if not cell or 'BREAK' in cell.upper():
        return None
    is_cross = cell.endswith('*')
    cell = cell.rstrip('* ').strip()
    if '|' not in cell:
        return None
    parts = cell.split('|', 1)
    course = parts[0].strip().upper()
    venue_part = parts[1].strip()
    group = ''
    gm = GROUP_RE.search(venue_part)
    if gm:
        group = gm.group(0).upper()
        venue_part = venue_part[:gm.start()].strip()
    # Normalize venue code
    venue_code = re.sub(r'\s+', ' ', venue_part.upper()).strip().rstrip('.')
    return course, venue_code, group, is_cross


def _parse_header(text: str) -> dict:
    r = {'college': '', 'department': '', 'program': '',
         'uqf_level': 8, 'year_of_study': 1, 'semester': 1, 'academic_year': ''}
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for line in lines:
        lu = line.upper()
        if 'COLLEGE OF' in lu and not r['college']:
            r['college'] = line
        elif 'DEPARTMENT OF' in lu and not r['department']:
            r['department'] = line
        elif any(x in lu for x in ['BACHELOR', 'DIPLOMA', 'MASTER', 'CERTIFICATE']) and not r['program']:
            r['program'] = line
    m = re.search(r'UQF\s*(\d+)', text, re.I)
    if m:
        r['uqf_level'] = int(m.group(1))
    m = re.search(r'(FIRST|SECOND|THIRD|FOURTH|FIFTH)\s+YEAR', text, re.I)
    if m:
        r['year_of_study'] = WORD_NUM.get(m.group(1).upper(), 1)
    m = re.search(r'SEMESTER\s+(I{1,3}|[123])', text, re.I)
    if m:
        s = m.group(1).upper()
        r['semester'] = {'I': 1, 'II': 2, 'III': 3, '1': 1, '2': 2, '3': 3}.get(s, 1)
    m = re.search(r'(\d{4})[/\-](\d{4})', text)
    if m:
        r['academic_year'] = f"{m.group(1)}-{m.group(2)}"
    return r


def _parse_modules(text: str) -> List[ParsedModule]:
    mods = []
    in_modules = False
    for line in text.split('\n'):
        ls = line.strip()
        if ls.upper() == 'MODULES':
            in_modules = True
            continue
        if 'VENUE DEFINITION' in ls.upper() or 'WORKSHOP/STUDIO' in ls.upper():
            in_modules = False
        if not in_modules or not ls:
            continue
        # Pattern: "IT 6125 - Computerized Accounting | Nyambo N"
        m = re.match(r'([A-Z]{2,4}\s?\d{3,4}(?:\s[A-Z]+)?)\s*[-–]\s*(.+?)\s*\|\s*(.+)', ls, re.I)
        if m:
            mods.append(ParsedModule(
                course_code=m.group(1).strip().upper(),
                course_name=m.group(2).strip(),
                lecturer_name=m.group(3).strip(),
            ))
    return mods


def _parse_venues(text: str) -> List[ParsedVenue]:
    venues = []
    in_venue = False
    for line in text.split('\n'):
        ls = line.strip()
        if 'VENUE DEFINITION' in ls.upper():
            in_venue = True
            continue
        if not in_venue or not ls:
            continue
        if re.match(r'^(CODE|VENUE\s+TOR|PROGRAM\s+STU|CROSS)', ls, re.I):
            continue
        # Split by 2+ spaces or tabs
        parts = [p.strip() for p in re.split(r'\s{2,}|\t', ls) if p.strip()]
        if len(parts) >= 4:
            try:
                cap = int(parts[-1])
                venues.append(ParsedVenue(
                    code=parts[0].upper(),
                    name=parts[1],
                    wing=parts[2],
                    capacity=cap,
                ))
            except ValueError:
                pass
        elif len(parts) == 3:
            venues.append(ParsedVenue(code=parts[0].upper(), name=parts[1], wing=parts[2], capacity=0))
    return venues


def _parse_timetable_grid(page) -> List[ParsedSlot]:
    """
    Parse timetable using pdfplumber words — reads actual word positions
    to determine which column (day) each cell belongs to.
    This is more reliable than extract_table() which misses columns.
    """
    words = page.extract_words(
        x_tolerance=3,
        y_tolerance=3,
        keep_blank_chars=False,
        use_text_flow=False,
    )
    if not words:
        return []

    # Step 1: Find header row — words containing day names
    day_columns = {}  # day_num -> (x_left, x_right)
    header_y = None

    for w in words:
        wl = w['text'].strip().lower()
        if wl in DAY_MAP:
            day_columns[DAY_MAP[wl]] = w['x0']
            if header_y is None or w['top'] < header_y:
                header_y = w['top']

    if not day_columns:
        return []

    # Sort days by x-position
    sorted_days = sorted(day_columns.items(), key=lambda x: x[1])  # [(day, x0), ...]

    # Build column boundaries: each day spans from its x0 to next day's x0
    col_bounds = []
    for i, (day, x0) in enumerate(sorted_days):
        x1 = sorted_days[i + 1][1] if i + 1 < len(sorted_days) else page.width
        col_bounds.append((day, x0 - 5, x1))

    # Step 2: Find time-slot rows — words matching "HH:MM" in leftmost area
    # Group all words by approximate row (y-coordinate)
    ROW_TOLERANCE = 5
    rows = {}  # y_bucket -> [words]
    for w in words:
        if w['top'] <= (header_y or 0):
            continue
        bucket = round(w['top'] / ROW_TOLERANCE) * ROW_TOLERANCE
        rows.setdefault(bucket, []).append(w)

    # Step 3: Parse time rows
    time_slots = {}  # y_bucket -> (start_time, end_time)
    for y, row_words in rows.items():
        # Collect leftmost words (x0 < first day column - 10)
        first_day_x = sorted_days[0][1] if sorted_days else 999
        left_words = [w['text'] for w in row_words if w['x0'] < first_day_x - 5]
        row_text = ' '.join(left_words).strip()
        m = re.search(r'(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})', row_text)
        if m:
            t1 = _parse_time(m.group(1))
            t2 = _parse_time(m.group(2))
            if t1 and t2:
                time_slots[y] = (t1, t2)

    # Step 4: For each time slot row, read content in each day column
    slots = []
    for y, (t1, t2) in time_slots.items():
        for day, x_left, x_right in col_bounds:
            # Collect words in this row's y-range and this day's x-range
            cell_words = []
            for ry, row_words in rows.items():
                if abs(ry - y) <= ROW_TOLERANCE * 2:
                    for w in row_words:
                        if x_left <= w['x0'] < x_right:
                            cell_words.append(w['text'])
            if not cell_words:
                continue
            cell_text = ' '.join(cell_words).strip()
            parsed = _parse_cell(cell_text)
            if parsed:
                course, venue_code, group, is_cross = parsed
                slots.append(ParsedSlot(
                    day=day,
                    start_time=t1,
                    end_time=t2,
                    course_code=course,
                    venue_code=venue_code,
                    group=group,
                    is_cross=is_cross,
                ))

    return slots


def _merge_slots(slots: List[ParsedSlot]) -> List[ParsedSlot]:
    """Merge consecutive time slots of same course+venue+day+group into one session."""
    if not slots:
        return slots
    slots.sort(key=lambda s: (s.day, s.start_time))
    merged = [slots[0]]
    for slot in slots[1:]:
        prev = merged[-1]
        if (prev.day == slot.day
                and prev.course_code == slot.course_code
                and prev.venue_code == slot.venue_code
                and prev.group == slot.group
                and prev.end_time == slot.start_time):
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
    text = page.extract_text(x_tolerance=3, y_tolerance=3) or ''
    if 'MBEYA UNIVERSITY' not in text.upper():
        return None

    hdr     = _parse_header(text)
    modules = _parse_modules(text)
    venues  = _parse_venues(text)

    # Parse timetable grid using word positions (most reliable method)
    slots = _parse_timetable_grid(page)

    # Fallback: try extract_table if word-based got nothing
    if not slots:
        for settings in [
            {"vertical_strategy": "lines",  "horizontal_strategy": "lines"},
            {"vertical_strategy": "text",   "horizontal_strategy": "lines"},
            {"vertical_strategy": "lines",  "horizontal_strategy": "text"},
        ]:
            table = page.extract_table(settings)
            if not table:
                continue
            header_row = table[0]
            day_cols = {}
            for ci, cell in enumerate(header_row):
                if cell and cell.strip().lower() in DAY_MAP:
                    day_cols[ci] = DAY_MAP[cell.strip().lower()]
            if not day_cols:
                continue
            for row in table[1:]:
                if not row or not row[0]:
                    continue
                slot_txt = (row[0] or '').strip()
                if 'BREAK' in slot_txt.upper():
                    continue
                m = re.search(r'(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})', slot_txt)
                if not m:
                    continue
                t1 = _parse_time(m.group(1))
                t2 = _parse_time(m.group(2))
                if not t1 or not t2:
                    continue
                for ci, day in day_cols.items():
                    if ci >= len(row):
                        continue
                    parsed = _parse_cell(row[ci] or '')
                    if parsed:
                        course, venue_code, group, is_cross = parsed
                        slots.append(ParsedSlot(
                            day=day, start_time=t1, end_time=t2,
                            course_code=course, venue_code=venue_code,
                            group=group, is_cross=is_cross,
                        ))
            if slots:
                break

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
