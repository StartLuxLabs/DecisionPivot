"""Independent second solver for gen_v3 / sched_conflict.

Written from the rendered text only.  The state is read the way a careful person reads a booking sheet:

  1. split it into paragraphs (opening line, rooms, optional list of reset gaps, rules, confirmed bookings, request);
  2. every rule sentence must be recognised (full-sentence match); each recognised sentence switches on one convention
     (and fixes its parameters, e.g. the reset gap), an unknown sentence raises;
  3. rooms, bookings and the request are parsed with one strict reader per layout (table / records / lines);
  4. the request is checked against every rule the text states (hours, seats, room clash with reset gap, people,
     equipment); answer `no` as soon as one is broken, otherwise `yes`.

Differences to the obvious implementation: the room rule is checked pairwise after ordering the two bookings by start
(the later one must begin at or after earlier end + gap); the people rule compares sets of busy minutes.
Anything that is not recognised, not resolvable or not stated raises an exception - nothing is skipped silently.
"""
import re


class Unrecognised(Exception):
    pass


class NotStated(Exception):
    pass


# ----------------------------------------------------------------------------------------------------------- vocabulary
ORG = r"(?:organiser|host|leader|trainer|tutor)"
ATT = r"(?:attendees|guests|players|trainees|students)"
ATT1 = r"(?:attendee|guest|player|trainee|student)"
SEATS = r"(?:seats|places)"
SEAT = r"(?:seat|place)"
EV = r"(?:meeting|activity|rehearsal|course|tutorial)"
EVS = r"(?:meetings|activities|rehearsals|courses|tutorials)"
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")

NAME_RX = r"[A-Z][a-z]+ [A-Z][a-z]+"
ITEM_RX = r"[a-z]+(?: [a-z]+)*"

# ------------------------------------------------------------------------------------------------------------- rules
_RULE_TEMPLATES = [
    # opening hours
    ("hours", "A booking must lie inside the opening hours of its room; it may start exactly at opening time and end exactly at closing time."),
    ("hours", "Opening hours are binding: start not earlier than the opening time of the room, end not later than its closing time, equality allowed."),
    ("hours", "No booking may start before its room opens or end after it closes."),
    ("hours_eq", "Starting at opening time or ending at closing time is fine."),
    # rooms: touching allowed
    ("room_touch", "Two bookings of the same room must not overlap, but they may touch: one may start at the very minute the other ends."),
    ("room_touch", "Bookings of one room may not overlap in time; a booking that starts exactly at the end time of another one does not overlap it."),
    ("room_single", "A room holds one {EV} at a time."),
    ("room_touch_eq", "Back-to-back is fine: a booking may begin exactly when the previous one in that room ends."),
    # rooms: reset gap, one number
    ("gap_fixed", "A room needs {n} minutes of reset between bookings: if one ends at time T, the next booking of that room may start at T + {m} minutes or later, not before."),
    ("gap_fixed", "After a booking, its room is blocked for a reset gap of {n} minutes: the next booking there may start exactly {m} minutes after that end, not earlier."),
    ("gap_fixed", "Two bookings of the same room need at least {n} minutes between them (reset gap), from the end of one to the start of the next; exactly {m} minutes is enough."),
    # rooms: reset gap by kind
    ("gap_kind", "A room needs a reset between bookings whose length depends on its kind: if one booking ends at time T, the next booking of that room may start at T + gap or later, not before."),
    ("gap_kind", "After a booking, its room is blocked for the reset gap listed for its kind of room: the next booking there may start exactly when the gap is over, not earlier."),
    ("gap_kind", "Two bookings of the same room need at least the reset gap of that room's kind between them, from the end of one to the start of the next; exactly the gap is enough."),
    ("gap_edges", "No reset is needed after opening or before closing time."),
    ("gap_edges", "Opening and closing times need no gap."),
    ("gap_edges", "No gap is needed at opening or closing time."),
    # people
    ("people", "A person, whether {ORG} or {ATT1}, cannot be in two bookings that overlap in time on the same day, even in different rooms."),
    ("people", "The {ORG} and all {ATT} are busy for the whole booking, and nobody may be in two bookings that overlap on the same day, whatever the rooms."),
    ("people", "Everyone named in a booking ({ORG} or {ATT1}) is occupied for its whole length; the request fails if one of its people is occupied by another booking of that day during any part of it."),
    ("people_touch", "People need no gap: one {EV} may end at the very minute the person's next one starts."),
    ("people_touch", "Back-to-back {EVS} are fine for people; only rooms need the reset gap."),
    ("people_touch", "Bookings that only touch are fine for a person: the reset gap is for rooms, not for people."),
    # seats
    ("seats", "Capacity: the number of {ATT} plus one for the {ORG} (who is not listed among the {ATT}) must not exceed the {SEATS} of the room; equal is allowed."),
    ("seats", "Everyone needs a {SEAT}: the {ORG} plus all {ATT} must not exceed the {SEATS} of the room."),
    ("seats_once", "The {ORG} is never repeated among the {ATT}."),
    ("seats", "The {SEATS} of a room limit the group: {ORG} and {ATT} together must fit."),
    ("seats_once", "The {ORG} counts as one person and is not in the {ATT} list; a full room is fine."),
    # equipment
    ("equip", "Each item the request needs must be in the equipment list of the requested room itself; an item with a different name is a different item."),
    ("equip", "The request is confirmed only if its room has all the items it needs."),
    ("equip_extra", "Extra equipment does no harm; a similar item under another name does not help."),
    ("equip", "The room must have every item the request needs; equipment of other rooms does not count, and names must match exactly."),
    # duration
    ("duration", "The end time of the request is its start time plus its duration."),
    ("duration", "The request gives a start time and a duration; it ends at start + duration."),
    ("duration", "The request lasts from its start time for the stated number of minutes."),
    # days and repeating bookings
    ("days", "Bookings on different days never clash."),
    ("days", "Days are independent: only bookings on the day of the request can stand in its way."),
    ("days", "What is booked on another day has no effect on the request."),
    ("repeat", "A booking whose day field lists several days (like Mon/Thu) takes place on each of them, at the same time, in the same room, with the same people."),
    ("repeat", "A day field with slashes, such as Tue/Wed/Fri, marks a repeating booking: it occupies its room and its people on each listed day at the stated time."),
    ("repeat", "Some bookings repeat: a day field with several days separated by slashes means the booking exists on each of those days with the same room, time and people."),
    # names
    ("names", "Full names identify people: the same first name with another family name is another person."),
    ("names", "People are identified by their full name; a shared first or family name alone means nothing."),
    ("names", "Two entries are the same person only if the full names are identical."),
]


def _compile_rule(template):
    esc = re.escape(template)
    for tok, val in (("ORG", ORG), ("ATT1", ATT1), ("ATT", ATT), ("SEATS", SEATS), ("SEAT", SEAT), ("EVS", EVS), ("EV", EV)):
        esc = esc.replace(r"\{%s\}" % tok, val)
    esc = esc.replace(r"\{n\}", r"(?P<n>\d+)").replace(r"\{m\}", r"(?P<m>\d+)")
    return re.compile(esc)


RULES = [(tag, _compile_rule(t)) for tag, t in _RULE_TEMPLATES]

OPENINGS = [
    re.compile(r"(?P<venue>.+?): (?P<kind>[a-z]+) rooms and their bookings \((?P<h>\d+)-hour clock\)\. (?P<rest>.+)"),
    re.compile(r"Booking sheet for the (?P<kind>[a-z]+) rooms of (?P<venue>.+?); (?P<h>\d+)-hour clock\. (?P<rest>.+)"),
    re.compile(r"(?P<venue>.+?) - (?P<kind>[a-z]+) rooms\. Times are on the (?P<h>\d+)-hour clock\. (?P<rest>.+)"),
]
OPENING_REST = (
    "Confirmed bookings stay as they are. The request is confirmed unchanged or not at all, which needs every rule to hold for it.",
    "The listed bookings are confirmed and fixed. The new request is confirmed only if, exactly as written, it breaks none of the rules.",
    "All listed bookings are confirmed and cannot be moved. The request is judged as written: every rule must hold for it.",
)

SECTIONS = {
    "rooms": ("rooms", "available rooms", "room list"),
    "rules": ("rules", "booking rules", "conventions"),
    "bookings": ("confirmed bookings", "bookings already confirmed", "existing bookings"),
    "request": ("request", "requested booking", "new request"),
    "gaps": ("reset gaps", "reset gap by kind of room", "kinds of room and their reset gap"),
}


# ------------------------------------------------------------------------------------------------------ small readers
def minutes(s):
    m = re.fullmatch(r"(\d\d):(\d\d)", s.strip())
    if not m:
        raise Unrecognised("time %r" % s)
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        raise Unrecognised("time out of range %r" % s)
    return h * 60 + mi


def span(s):
    m = re.fullmatch(r"(\d\d:\d\d)-(\d\d:\d\d)", s.strip())
    if not m:
        raise Unrecognised("time range %r" % s)
    a, b = minutes(m.group(1)), minutes(m.group(2))
    if not a < b:
        raise Unrecognised("empty or reversed range %r" % s)
    return a, b


def person(s):
    s = s.strip()
    if not re.fullmatch(NAME_RX, s):
        raise Unrecognised("person name %r" % s)
    return s


def persons(s):
    parts = [person(p) for p in s.split(", ")]
    if len(set(parts)) != len(parts):
        raise Unrecognised("a name is repeated inside one list: %r" % s)
    return parts


def items(s):
    parts = s.split(", ")
    for p in parts:
        if not re.fullmatch(ITEM_RX, p):
            raise Unrecognised("equipment item %r" % p)
    return parts


def day_list(s):
    parts = s.strip().split("/")
    for p in parts:
        if p not in DAYS:
            raise Unrecognised("day %r" % s)
    if len(set(parts)) != len(parts):
        raise Unrecognised("day repeated %r" % s)
    return parts


def duration(s):
    m = re.fullmatch(r"(\d+) min", s.strip())
    if not m:
        raise Unrecognised("duration %r" % s)
    return int(m.group(1))


def section_of(line):
    t = line.strip()
    m = re.fullmatch(r"==\s*(.+?)\s*==", t)
    if m:
        t = m.group(1)
    elif t.endswith(":"):
        t = t[:-1]
    t = t.strip().lower()
    for k, names in SECTIONS.items():
        if t in names:
            return k
    return None


def bullets(lines):
    out = []
    for l in lines:
        m = re.fullmatch(r"- (.+)", l)
        if not m:
            raise Unrecognised("bullet expected: %r" % l)
        out.append(m.group(1))
    return out


def table(lines):
    head = lines[0].split(" | ")
    rows = []
    for l in lines[1:]:
        cells = l.split(" | ")
        if len(cells) != len(head):
            raise Unrecognised("table row has %d cells, header %d: %r" % (len(cells), len(head), l))
        rows.append(dict(zip(head, cells)))
    return head, rows


def pick_word(d, options, what):
    hit = [k for k in options if k in d]
    if len(hit) != 1:
        raise Unrecognised("%s: expected exactly one of %s in %s" % (what, options, sorted(d)))
    return d[hit[0]]


ORG_WORDS = ("organiser", "host", "leader", "trainer", "tutor")
ATT_WORDS = ("attendees", "guests", "players", "trainees", "students")
SEAT_WORDS = ("seats", "places")


# ------------------------------------------------------------------------------------------------------------ parsing
def parse_opening(p):
    for rx in OPENINGS:
        m = rx.fullmatch(p)
        if m:
            if m.group("h") != "24":
                raise Unrecognised("clock %s" % m.group("h"))
            if m.group("rest") not in OPENING_REST:
                raise Unrecognised("opening sentences %r" % m.group("rest"))
            return
    raise Unrecognised("opening paragraph %r" % p[:80])


def parse_rules(lines):
    if len(lines) == 1 and not re.match(r"(- |\d+\. )", lines[0]):
        text = lines[0]
    elif all(l.startswith("- ") for l in lines):
        text = " ".join(l[2:] for l in lines)
    else:
        nums = []
        parts = []
        for l in lines:
            m = re.fullmatch(r"(\d+)\. (.+)", l)
            if not m:
                raise Unrecognised("rule line %r" % l)
            nums.append(int(m.group(1)))
            parts.append(m.group(2))
        if nums != list(range(1, len(nums) + 1)):
            raise Unrecognised("rule numbering %r" % nums)
        text = " ".join(parts)
    sentences = re.split(r"(?<=\.)\s+(?=[A-Z])", text)
    found = {}
    for s in sentences:
        hits = [(tag, rx.fullmatch(s)) for tag, rx in RULES if rx.fullmatch(s)]
        if len(hits) != 1:
            raise Unrecognised("rule sentence not recognised (%d hits): %r" % (len(hits), s))
        tag, m = hits[0]
        found.setdefault(tag, [])
        found[tag].append(m.groupdict())
    return found


def parse_gaps(lines):
    out = {}
    if " | " in lines[0]:
        head, rows = table(lines)
        if head != ["kind", "reset gap"]:
            raise Unrecognised("gap table header %r" % head)
        for r in rows:
            out[r["kind"]] = duration(r["reset gap"])
    elif lines[0].startswith("- "):
        for b in bullets(lines):
            m = re.fullmatch(r"([a-z]+(?: [a-z]+)*): reset gap (\d+ min)", b)
            if not m:
                raise Unrecognised("gap bullet %r" % b)
            out[m.group(1)] = duration(m.group(2))
    else:
        if len(lines) != 1 or not lines[0].endswith("."):
            raise Unrecognised("gap line %r" % lines)
        for part in lines[0][:-1].split("; "):
            m = re.fullmatch(r"([a-z]+(?: [a-z]+)*) (\d+ min)", part)
            if not m:
                raise Unrecognised("gap entry %r" % part)
            out[m.group(1)] = duration(m.group(2))
    if not out:
        raise Unrecognised("empty gap list")
    return out


class Room(object):
    def __init__(self, name, seats, opn, cls, kind=None, equipment=None):
        self.name, self.seats, self.open, self.close, self.kind, self.equipment = name, seats, opn, cls, kind, equipment


def parse_rooms(lines):
    rooms = {}

    def add(name, seats, rng, kind, equip):
        if name in rooms:
            raise Unrecognised("room listed twice: %s" % name)
        rooms[name] = Room(name, seats, rng[0], rng[1], kind, equip)

    if " | " in lines[0]:
        head, rows = table(lines)
        for r in rows:
            seats = int(pick_word(r, SEAT_WORDS, "rooms table"))
            equip = items(r["equipment"]) if "equipment" in r else None
            add(r["room"], seats, span(r["open"]), r.get("kind"), equip)
        allowed = {"room", "kind", "equipment", "open"} | set(SEAT_WORDS)
        if not set(head) <= allowed:
            raise Unrecognised("room columns %r" % head)
    elif lines[0].startswith("- "):
        for b in bullets(lines):
            m = re.fullmatch(r"([^:]+): (.+)", b)
            if not m:
                raise Unrecognised("room bullet %r" % b)
            kind = seats = rng = equip = None
            for part in m.group(2).split("; "):
                mm = re.fullmatch(r"kind (%s)" % ITEM_RX, part)
                if mm:
                    kind = mm.group(1)
                    continue
                mm = re.fullmatch(r"%s (\d+)" % SEATS, part)
                if mm:
                    seats = int(mm.group(1))
                    continue
                mm = re.fullmatch(r"equipment (%s(?:, %s)*)" % (ITEM_RX, ITEM_RX), part)
                if mm:
                    equip = items(mm.group(1))
                    continue
                mm = re.fullmatch(r"open (\d\d:\d\d-\d\d:\d\d)", part)
                if mm:
                    rng = span(mm.group(1))
                    continue
                raise Unrecognised("room part %r" % part)
            if seats is None or rng is None:
                raise Unrecognised("room without seats or hours %r" % b)
            add(m.group(1), seats, rng, kind, equip)
    else:
        for l in lines:
            m = re.fullmatch(r"([^:(]+?)(?: \(([a-z]+(?: [a-z]+)*)\))?: (.+)\.", l)
            if not m:
                raise Unrecognised("room line %r" % l)
            kind, seats, rng, equip = m.group(2), None, None, None
            for part in m.group(3).split("; "):
                mm = re.fullmatch(r"(\d+) %s" % SEATS, part)
                if mm:
                    seats = int(mm.group(1))
                    continue
                mm = re.fullmatch(r"open (\d\d:\d\d-\d\d:\d\d)", part)
                if mm:
                    rng = span(mm.group(1))
                    continue
                mm = re.fullmatch(r"equipment: (.+)", part)
                if mm:
                    equip = items(mm.group(1))
                    continue
                raise Unrecognised("room part %r" % part)
            if seats is None or rng is None:
                raise Unrecognised("room without seats or hours %r" % l)
            add(m.group(1), seats, rng, kind, equip)
    if not rooms:
        raise Unrecognised("no rooms")
    return rooms


class Booking(object):
    def __init__(self, ident, room, days, start, end, org, att):
        self.id, self.room, self.days, self.start, self.end, self.org, self.att = ident, room, days, start, end, org, att

    @property
    def people(self):
        return [self.org] + self.att


def parse_bookings(lines):
    out = []
    if " | " in lines[0]:
        head, rows = table(lines)
        if head[:4] != ["id", "room", "day", "time"] or len(head) != 6:
            raise Unrecognised("booking columns %r" % head)
        if head[4] not in ORG_WORDS or head[5] not in ATT_WORDS:
            raise Unrecognised("booking columns %r" % head)
        for r in rows:
            s, e = span(r["time"])
            out.append(Booking(r["id"], r["room"], day_list(r["day"]), s, e, person(r[head[4]]), persons(r[head[5]])))
    elif lines[0].startswith("- "):
        for b in bullets(lines):
            m = re.fullmatch(r"(#?[A-Z]?\d+): room ([^;]+); day ([A-Za-z/]+); time (\d\d:\d\d-\d\d:\d\d); (%s) ([^;]+); (%s) ([^;]+)" % (ORG, ATT), b)
            if not m:
                raise Unrecognised("booking bullet %r" % b)
            s, e = span(m.group(4))
            out.append(Booking(m.group(1), m.group(2), day_list(m.group(3)), s, e, person(m.group(6)), persons(m.group(8))))
    else:
        for l in lines:
            m = re.fullmatch(r"(#?[A-Z]?\d+)\. ([^,]+), ([A-Za-z/]+), (\d\d:\d\d-\d\d:\d\d)\. ([A-Z][a-z]+): ([^.]+)\. ([A-Z][a-z]+): ([^.]+)\.", l)
            if not m:
                raise Unrecognised("booking line %r" % l)
            if m.group(5).lower() not in ORG_WORDS or m.group(7).lower() not in ATT_WORDS:
                raise Unrecognised("booking line words %r" % l)
            s, e = span(m.group(4))
            out.append(Booking(m.group(1), m.group(2), day_list(m.group(3)), s, e, person(m.group(6)), persons(m.group(8))))
    if not out:
        raise Unrecognised("no bookings")
    ids = [b.id for b in out]
    if len(set(ids)) != len(ids):
        raise Unrecognised("booking id repeated")
    return out


class Request(object):
    pass


def parse_request(lines):
    q = Request()
    q.room = q.day = q.start = q.end = q.dur = q.org = q.att = q.needs = None
    if " | " in lines[0]:
        head, rows = table(lines)
        if len(rows) != 1:
            raise Unrecognised("request rows %d" % len(rows))
        r = rows[0]
        known = {"room", "day", "start", "end", "duration", "needs"} | set(ORG_WORDS) | set(ATT_WORDS)
        if not set(head) <= known:
            raise Unrecognised("request columns %r" % head)
        q.room, q.day = r["room"], r["day"]
        q.start = minutes(r["start"])
        if "end" in r:
            q.end = minutes(r["end"])
        if "duration" in r:
            q.dur = duration(r["duration"])
        q.org = person(pick_word(r, ORG_WORDS, "request"))
        q.att = persons(pick_word(r, ATT_WORDS, "request"))
        if "needs" in r:
            q.needs = items(r["needs"])
    elif lines[0].startswith("- "):
        kv = {}
        for b in bullets(lines):
            m = re.fullmatch(r"([a-z]+): (.+)", b)
            if not m or m.group(1) in kv:
                raise Unrecognised("request bullet %r" % b)
            kv[m.group(1)] = m.group(2)
        known = {"room", "day", "start", "end", "duration", "needs"} | set(ORG_WORDS) | set(ATT_WORDS)
        if not set(kv) <= known:
            raise Unrecognised("request fields %r" % sorted(kv))
        q.room, q.day = kv["room"], kv["day"]
        q.start = minutes(kv["start"])
        if "end" in kv:
            q.end = minutes(kv["end"])
        if "duration" in kv:
            q.dur = duration(kv["duration"])
        q.org = person(pick_word(kv, ORG_WORDS, "request"))
        q.att = persons(pick_word(kv, ATT_WORDS, "request"))
        if "needs" in kv:
            q.needs = items(kv["needs"])
    else:
        if len(lines) != 1:
            raise Unrecognised("request lines %d" % len(lines))
        m = re.fullmatch(r"([^,]+), ([A-Za-z]+), start (\d\d:\d\d), (?:end (\d\d:\d\d)|duration (\d+ min))\. ([A-Z][a-z]+): ([^.]+)\. ([A-Z][a-z]+): ([^.]+)\.(?: Needs: ([^.]+)\.)?", lines[0])
        if not m:
            raise Unrecognised("request line %r" % lines[0])
        if m.group(6).lower() not in ORG_WORDS or m.group(8).lower() not in ATT_WORDS:
            raise Unrecognised("request words %r" % lines[0])
        q.room, q.day = m.group(1), m.group(2)
        q.start = minutes(m.group(3))
        if m.group(4):
            q.end = minutes(m.group(4))
        if m.group(5):
            q.dur = duration(m.group(5))
        q.org, q.att = person(m.group(7)), persons(m.group(9))
        if m.group(10):
            q.needs = items(m.group(10))
    if q.day not in DAYS:
        raise Unrecognised("request day %r" % q.day)
    if (q.end is None) == (q.dur is None):
        raise Unrecognised("request needs exactly one of end / duration")
    return q


def parse(state):
    paras = state.strip("\n").split("\n\n")
    parse_opening(paras[0])
    sec = {}
    for p in paras[1:]:
        lines = p.split("\n")
        k = section_of(lines[0])
        if k is None:
            raise Unrecognised("section header %r" % lines[0])
        if k in sec:
            raise Unrecognised("section twice: %s" % k)
        body = [l for l in lines[1:]]
        if not body or any(not l.strip() for l in body):
            raise Unrecognised("empty line or empty section in %s" % k)
        sec[k] = body
    for need in ("rooms", "rules", "bookings", "request"):
        if need not in sec:
            raise Unrecognised("section missing: %s" % need)
    rules = parse_rules(sec["rules"])
    rooms = parse_rooms(sec["rooms"])
    gaps = parse_gaps(sec["gaps"]) if "gaps" in sec else None
    bookings = parse_bookings(sec["bookings"])
    req = parse_request(sec["request"])
    return rules, rooms, gaps, bookings, req


# ---------------------------------------------------------------------------------------------------------- the logic
def reset_gap(rules, rooms, gaps, room):
    """The reset gap the text states for `room`, in minutes (0 when touching is stated as allowed)."""
    fixed = rules.get("gap_fixed")
    kind = rules.get("gap_kind")
    touch = rules.get("room_touch") or (rules.get("room_single") and rules.get("room_touch_eq"))
    states = [bool(fixed), bool(kind), bool(touch)]
    if sum(states) != 1:
        raise NotStated("room rule: need exactly one of fixed gap / gap by kind / touching allowed, got %r" % states)
    if fixed:
        if len(fixed) != 1:
            raise Unrecognised("two fixed-gap sentences")
        n, m = fixed[0]["n"], fixed[0]["m"]
        if n != m:
            raise Unrecognised("gap numbers differ inside one sentence: %s / %s" % (n, m))
        if gaps is not None:
            raise Unrecognised("fixed gap in the rule and a gap list as well")
        return int(n)
    if kind:
        if gaps is None:
            raise NotStated("gap by kind without a gap list")
        k = rooms[room].kind
        if k is None:
            raise NotStated("room %s has no kind" % room)
        if k not in gaps:
            raise NotStated("no reset gap listed for kind %r" % k)
        return gaps[k]
    if gaps is not None:
        raise Unrecognised("gap list although touching rule")
    return 0


def check_world(rules, rooms, gaps, bookings):
    """The confirmed bookings must respect every stated rule among themselves; otherwise the sheet contradicts itself."""
    for b in bookings:
        rm = rooms[b.room]
        if b.org in b.att:
            raise Unrecognised("booking %s: the organiser is repeated among the attendees" % b.id)
        if b.start < rm.open or b.end > rm.close:
            raise Unrecognised("booking %s lies outside the opening hours of %s" % (b.id, b.room))
        if 1 + len(b.att) > rm.seats:
            raise Unrecognised("booking %s has more people than seats in %s" % (b.id, b.room))
    for i in range(len(bookings)):
        for j in range(i + 1, len(bookings)):
            a, b = bookings[i], bookings[j]
            if not set(a.days) & set(b.days):
                continue
            if a.room == b.room:
                (s1, e1), (s2, e2) = sorted([(a.start, a.end), (b.start, b.end)])
                if s2 < e1 + reset_gap(rules, rooms, gaps, a.room):
                    raise Unrecognised("confirmed bookings %s and %s break the room rule" % (a.id, b.id))
            if "people" in rules and set(a.people) & set(b.people) and a.start < b.end and b.start < a.end:
                raise Unrecognised("confirmed bookings %s and %s double-book a person" % (a.id, b.id))


def solve_state(state):
    rules, rooms, gaps, bookings, req = parse(state)

    # ------- resolve names (everything must be found) -------
    if req.room not in rooms:
        raise Unrecognised("requested room %r not in the room list" % req.room)
    for b in bookings:
        if b.room not in rooms:
            raise Unrecognised("booking %s: unknown room %r" % (b.id, b.room))
    room = rooms[req.room]
    check_world(rules, rooms, gaps, bookings)

    # ------- the request's own time span -------
    if req.dur is not None:
        if "duration" not in rules:
            raise NotStated("the request gives a duration but no rule says how the end follows")
        end = req.start + req.dur
    else:
        end = req.end
    if not req.start < end:
        raise Unrecognised("request span is empty")
    s0, e0 = req.start, end

    # ------- conventions the data makes necessary -------
    if any(set(b.days) != {req.day} for b in bookings) and "days" not in rules:
        raise NotStated("bookings on other days exist but no rule says they do not matter")
    if any(len(b.days) > 1 for b in bookings) and "repeat" not in rules:
        raise NotStated("a booking lists several days but no rule explains it")
    everyone = {}
    for b in bookings:
        for p in b.people:
            everyone[p] = 1
    for p in [req.org] + req.att:
        everyone[p] = 1
    firsts, families = {}, {}
    for p in everyone:
        f, l = p.split(" ")
        firsts.setdefault(f, set()).add(p)
        families.setdefault(l, set()).add(p)
    namesakes = any(len(v) > 1 for v in firsts.values()) or any(len(v) > 1 for v in families.values())
    if namesakes and "names" not in rules:
        raise NotStated("people share a first or family name but no rule says how names are matched")
    if "people" in rules and "people_touch" not in rules:
        raise NotStated("people rule without a statement about touching bookings")
    broken = []

    # ------- opening hours -------
    if "hours" not in rules:
        raise NotStated("no rule about opening hours")
    if s0 < room.open or e0 > room.close:
        broken.append("hours")

    # ------- seats: the organiser plus the attendees -------
    if "seats" not in rules:
        raise NotStated("no rule about seats")
    group = [req.org] + req.att
    if req.org in req.att:
        raise Unrecognised("the organiser is repeated among the attendees")
    if len(group) > room.seats:
        broken.append("seats")

    # ------- equipment -------
    if req.needs is not None:
        if "equip" not in rules:
            raise NotStated("the request needs items but no rule says where they must be")
        if room.equipment is None:
            raise Unrecognised("no equipment list for the requested room")
        for it in req.needs:
            if it not in room.equipment:
                broken.append("equipment")
                break
    elif "equip" in rules:
        raise Unrecognised("equipment rule but the request needs nothing")

    # ------- the room: pairwise, the later booking must start at or after the earlier end + gap -------
    gap = reset_gap(rules, rooms, gaps, req.room)
    for b in bookings:
        if b.room != req.room or req.day not in b.days:
            continue
        (a_s, a_e), (c_s, c_e) = sorted([(s0, e0), (b.start, b.end)])
        if c_s < a_e + gap:
            broken.append("room")
            break

    # ------- people: busy minutes of every person on that day -------
    mine = set(range(s0, e0))
    if "people" in rules:
        busy = {}
        for b in bookings:
            if req.day in b.days:
                for p in b.people:
                    busy.setdefault(p, set()).update(range(b.start, b.end))
        for p in group:
            if busy.get(p, set()) & mine:
                broken.append("person")
                break

    return not broken, broken


def _answer_key(options, yes):
    want = "yes" if yes else "no"
    keys = [k for k, v in options.items() if str(v).strip().lower().startswith(want + " ")]
    if len(keys) != 1:
        raise Unrecognised("cannot find the %s option in %r" % (want, options))
    return keys[0]


def solve(state, question, options):
    if question.strip() != "Can the requested booking be confirmed as it stands?":
        raise Unrecognised("unexpected question %r" % question)
    if len(options) != 2:
        raise Unrecognised("expected two options")
    ok, _ = solve_state(state)
    return _answer_key(options, ok)
