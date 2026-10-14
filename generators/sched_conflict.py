"""Task sched_conflict (layer D, generated, programmatic truth): "Can the requested booking be confirmed as it stands?"

State.  One text: a list of rooms (seats, opening hours; from level 2 equipment; at level 3 a kind of room), the booking
rules in plain words, the confirmed bookings (id, room, day, start-end, organiser, attendees by full name) and ONE request
(room, day, start, end or duration, organiser, attendees, equipment needed).  The answer is yes when the request, added to
the confirmed bookings exactly as written, breaks none of the stated rules, and no when it breaks one.

Rules written into every state (level 1: the first, the third and the fourth; touching allowed for rooms):
  overlap    two bookings of one room may not overlap; level 1: they may touch; level 2: the room needs a reset gap of G
             minutes between bookings (one G for all rooms, given in the rule); level 3: the gap depends on the kind of room
             (a list "kind -> minutes"); no gap is needed at opening or closing time
  person     nobody (organiser or attendee) is in two bookings that overlap on the same day, whatever the rooms; touching
             is fine for people, the reset gap concerns rooms only; people are identified by their full name
  hours      the booking lies inside the opening hours of its room (start at opening time / end at closing time allowed)
  seats      attendees + 1 (the organiser, who is not repeated in the attendee list) <= seats of the room
  equipment  the room itself has every item the request needs (exact names)
  level 2+   the request gives start and duration (end = start + duration)
  level 3    a day field such as Mon/Thu is a repeating booking (same room, time, people on each listed day); days are independent

Contrast pairs.  600 items = 300 pairs (`group`): the same state with ONE field changed (`meta.field`):
  overlap    a time of the request (start, end or duration) moved by 5, 10 or 15 minutes into a neighbour of the room or
             into its reset gap; the positive touches that neighbour exactly (level 1) or keeps exactly the gap
  person     one attendee name of the request replaced by a person who sits in an overlapping booking of ANOTHER room
             (the replaced person has a booking that only touches), or a time of the request moved by 5-15 minutes into a
             booking that one attendee has in another room (in the positive the two only touch)
  seats      the seat number of the requested room: positive = exactly organiser + attendees, negative = one less
  hours      a time of the request moved 5-15 minutes outside the opening hours, or the opening / closing time of the room
             moved by 15 minutes; the positive starts exactly at opening time or ends exactly at closing time
  equipment  one equipment word: an item the request needs replaced by one the room lacks, or the needed item of the room
             replaced by another one
Both members of a pair have the same number of lines; everything except the one field is shared, so the decoys (bookings
in other rooms at the same time, bookings of the same room or of the same people on other days, people who share a first
or a family name, meetings of attendees that touch the request, rooms that are too small / closed / not equipped) appear
in both classes.

Levels (200 items each): 1 = 2 rooms, 6-8 bookings, one day, rules overlap / hours / seats, start-end request;
2 = 3-4 rooms, 12-16 bookings, one day, one reset gap, people, equipment, start + duration; 3 = 5-6 rooms, 20-28 booking
lines over 2-3 days, repeating bookings, reset gap by kind of room, 5-8 attendees with other meetings in other rooms.

gen_v4 (2026-10-08) - the decisive check is no longer mostly a cheap one.  Reviewers found level-2/3 items decided by one
sum on the request line (start + duration beyond closing time) or by the seat count, with the booking list irrelevant.  Now
the planted rule is drawn mostly among the checks that need the booking list (number of negatives per level):
  level 1  overlap 34, hours 33, seats 33                              (unchanged: the easy level, 66 % cheap)
  level 2  overlap 35, person 35, hours 10, seats 10, equipment 10    (30 % cheap; was 60 %)
  level 3  overlap 43, person 42, hours 5, seats 5, equipment 5       (15 % cheap; was 60 %)
Level 3 in addition: about 90 % of the planted overlaps lie inside the reset gap of the room kind (the request does not
touch the neighbour's own time, so the gap of THAT kind of room decides), the decisive neighbour / conflicting booking is a
repeating booking in about 80 % of the items and the day of the request is not the first listed day in about two thirds; the
remaining cheap negatives need a computed end (hours: start + duration against closing time), a count of names (seats) or
2-3 needed items (equipment).  Hours, seats and equipment are decoys exactly at their limit in the other items: the room
is exactly full in 80 % of them, has exactly the needed equipment in 70 %, and the request starts at opening time / ends at
closing time in both members wherever the changed field leaves that edge alone (else a neighbour of the room sits exactly at
the gap).  No sentence of the state changed, so the independent solver reads every state as before.

Truth: ``analyse(spec)`` works on the structured specification only (no text is parsed).  The script asserts for every pair:
the confirmed bookings respect every rule among themselves, the positive breaks nothing, the negative breaks exactly the
planted rule (one neighbour, one person, one seat, one item, the planted number of minutes), one leaf of the specification
and one line of the text differ, plus balance, duplicate, vocabulary and length checks.

    python3 generators/sched_conflict.py
Environment: BENCH_OUT=<dir> writes <dir>/sched_conflict/ instead of generated/tasks/sched_conflict/; BENCH_SEED=<int> (only together
with BENCH_OUT) builds a second set of the same design from another root seed (ids "sched_conflict:s<k>:<number>").
"""
import collections
import copy
import json
import os
import random
import re
import sys

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated")   # items go to HERE/tasks/<family>/ (BENCH_OUT: elsewhere)
TASK = "sched_conflict"
DEFAULT_SEED = 20261007
_ENV_SEED, _ENV_OUT = os.environ.get("BENCH_SEED"), os.environ.get("BENCH_OUT")
if _ENV_SEED is not None and not _ENV_OUT:
    sys.stderr.write("BENCH_SEED is accepted only together with BENCH_OUT (the published set is never overwritten by another seed).\n")
    sys.exit(2)
SEED = int(_ENV_SEED) if _ENV_SEED is not None else DEFAULT_SEED
SEALED = _ENV_SEED is not None
OUT_DIR = os.path.join(os.path.abspath(_ENV_OUT), TASK) if _ENV_OUT else os.path.join(HERE, "tasks", TASK)
ID_PREFIX = f"{TASK}:s{SEED}:" if SEALED else f"{TASK}:"
MASTER = random.Random(SEED)                       # the root; every other generator is derived from it through SALT
SALT = "%016x" % MASTER.getrandbits(64)

INSTRUCTIONS = "Can the requested booking be confirmed as it stands?"
OPTIONS = {"yes": "Yes - the request breaks none of the stated rules and can be confirmed as written.",
           "no": "No - the request breaks at least one of the stated rules and cannot be confirmed as written."}
KINDS = ["overlap", "person", "seats", "hours", "equipment"]
CHEAP = ("hours", "seats", "equipment")                   # the checks that need no booking list
LEVEL_KINDS = {1: ["overlap", "hours", "seats"], 2: KINDS, 3: KINDS}
# negatives per kind, in the order of LEVEL_KINDS (gen_v3: 20 each at levels 2 and 3, i.e. 60 % decided by a cheap check)
LEVEL_COUNTS = {1: [34, 33, 33], 2: [35, 35, 10, 10, 10], 3: [43, 42, 5, 5, 5]}
P_FULL, P_EXACT_EQ, P_LIMIT, P_GAP_ONLY, P_REPEAT, P_LATER = 0.8, 0.7, 0.75, 0.85, 0.85, 0.7    # decoy / route dials of levels 2 and 3
ROOMS = {1: (2, 2), 2: (3, 4), 3: (5, 6)}
BOOKINGS = {1: (6, 8), 2: (12, 16), 3: (20, 28)}
ATTENDEES = {1: (1, 4), 2: (3, 6), 3: (5, 8)}
POOL = {1: (9, 12), 2: (13, 17), 3: (20, 26)}
PARTY = {1: [2, 2, 3, 3, 3, 4], 2: [2, 2, 3, 3, 4, 4, 5], 3: [2, 3, 3, 4, 4, 5, 6, 7]}
REQ_LEN = {1: (20, 110), 2: (25, 110), 3: (25, 120)}
LENS = [20, 25, 30, 30, 40, 45, 45, 50, 60, 60, 75, 90, 105, 120]
GRID_OPEN = list(range(7 * 60, 9 * 60 + 1, 15))            # a room that is open all day: 07:00 ... 09:00, every quarter of an hour,
GRID_CLOSE = list(range(16 * 60, 19 * 60 + 1, 15))         # to 16:00 ... 19:00
MORNING = (list(range(7 * 60, 8 * 60 + 1, 15)), list(range(12 * 60, 14 * 60 + 1, 15)))        # a room that is open in the morning only
AFTERNOON = (list(range(11 * 60, 13 * 60 + 1, 15)), list(range(17 * 60, 20 * 60 + 1, 15)))    # ... in the afternoon only
DAYN = ["Mon", "Tue", "Wed", "Thu", "Fri"]
LAYOUTS = ["table", "records", "lines"]


class Reject(Exception):
    """a random draw that cannot be completed; the pair is drawn again with the next derived generator"""


def rng_for(*parts):
    return random.Random(SALT + ":" + TASK + ":" + ":".join(str(p) for p in parts))


def fmt(t):
    return "%02d:%02d" % (t // 60, t % 60)


def draw_hours(rng, half, keep_open=False, keep_close=False):
    """opening and closing time of a room; `half` = probability of a half-day room.  keep_open / keep_close leave out the
    last opening / first closing value, so that an opening time moved 15 minutes later (closing time earlier) stays a value
    that unchanged rooms have too."""
    u = rng.random()
    og, cg = MORNING if u < half / 2.0 else AFTERNOON if u < half else (GRID_OPEN, GRID_CLOSE)
    return rng.choice(og[:-1] if keep_open else og), rng.choice(cg[1:] if keep_close else cg)


def mm(s):
    return int(s[:2]) * 60 + int(s[3:5])


# ----------------------------------------------------------------------------------------------- invented names
GIVEN_ON = ["Al", "Be", "Ca", "Da", "El", "Fa", "Ga", "Ha", "Il", "Jo", "Ka", "Le", "Ma", "Ne", "Ol", "Pa", "Qui", "Ro", "Sa", "Te",
            "Ul", "Ve", "Wi", "Xa", "Ya", "Ze", "Bri", "Cle", "Dri", "Fre", "Gre", "Ky", "Lu", "Mo", "Ni", "Or", "Pho", "Ru", "Si", "To"]
GIVEN_CO = ["ren", "lia", "vin", "dra", "mir", "sso", "nna", "rik", "bel", "tor", "nis", "ya", "lo", "vek", "sha", "dan"]
FAMILY_ON = ["Arv", "Bolt", "Cres", "Dunn", "Evr", "Falk", "Grim", "Hest", "Isk", "Jorv", "Kald", "Lind", "Mart", "Nyl", "Orm", "Pell",
             "Quar", "Rost", "Selv", "Thorn", "Ulm", "Vard", "Wren", "Yeld", "Zann", "Brax", "Clem", "Dask", "Fror", "Garn", "Halv",
             "Kirs", "Lask", "Mund", "Nerv", "Osk", "Perr", "Rund", "Skar", "Tolv"]
FAMILY_CO = ["en", "ov", "ari", "holm", "ack", "ell", "ume", "ard", "eth", "une", "ossa", "ik", "ald", "ora", "ista", "ow"]
ROOM_ON = ["Ka", "Lo", "Me", "Ni", "Osa", "Pe", "Ru", "Sy", "Tu", "Ve", "Za", "Bo", "Cy", "De", "Fi", "Go", "Hu", "Ixa", "Ju", "Ely",
           "Abe", "Ume", "Wo", "Qua"]
ROOM_CO = ["rna", "lden", "stro", "vik", "mbra", "nda", "ssel", "tora", "lume", "ria", "nto", "phis", "dral", "quay", "xen"]
SITE_ON = ["Var", "Hel", "Tre", "Osk", "Bren", "Cal", "Dor", "Lin", "Mar", "Nor", "Pen", "Rav", "Sol", "Tam", "Wes"]
SITE_CO = ["holt", "mont", "vale", "wick", "stead", "bury", "garth", "mere", "ford", "by"]

DOMAINS = collections.OrderedDict()
DOMAINS["office"] = {
    "site": ["{n} Partners", "{n} Analytics", "{n} Group"], "rooms_noun": "meeting rooms", "event": "meeting", "events": "meetings",
    "org": "organiser", "att": "attendee", "atts": "attendees", "seat": "seat", "seats": "seats",
    "kinds": ["meeting room", "workshop room", "video suite"],
    "equipment": ["projector", "whiteboard", "video link", "conference phone", "flip chart", "wall screen", "document camera", "speaker set"]}
DOMAINS["campus"] = {
    "site": ["{n} Institute", "{n} College", "{n} School of Science"], "rooms_noun": "teaching rooms", "event": "tutorial", "events": "tutorials",
    "org": "tutor", "att": "student", "atts": "students", "seat": "seat", "seats": "seats",
    "kinds": ["seminar room", "computer lab", "wet lab"],
    "equipment": ["projector", "blackboard", "lectern", "visualiser", "fume hood", "microscope set", "recording kit", "smart board"]}
DOMAINS["studio"] = {
    "site": ["{n} Music School", "{n} Conservatory", "{n} Rehearsal House"], "rooms_noun": "rehearsal rooms", "event": "rehearsal", "events": "rehearsals",
    "org": "leader", "att": "player", "atts": "players", "seat": "place", "seats": "places",
    "kinds": ["practice room", "ensemble room", "recording room"],
    "equipment": ["grand piano", "upright piano", "drum kit", "mixing desk", "bass amp", "guitar amp", "music stands", "vocal booth"]}
DOMAINS["centre"] = {
    "site": ["{n} Community Centre", "{n} Neighbourhood House", "{n} Village Forum"], "rooms_noun": "activity rooms", "event": "activity", "events": "activities",
    "org": "host", "att": "guest", "atts": "guests", "seat": "place", "seats": "places",
    "kinds": ["club room", "craft room", "hall"],
    "equipment": ["sound system", "stage lights", "pottery kiln", "sewing machines", "gym mats", "kitchen unit", "mirror wall", "floor loom"]}
DOMAINS["workshop"] = {
    "site": ["{n} Training Works", "{n} Makers Yard", "{n} Skills Centre"], "rooms_noun": "training rooms", "event": "course", "events": "courses",
    "org": "trainer", "att": "trainee", "atts": "trainees", "seat": "seat", "seats": "seats",
    "kinds": ["classroom", "machine shop", "electronics lab"],
    "equipment": ["laser cutter", "plasma cutter", "drill press", "band saw", "table saw", "welding bay", "soldering irons", "test rig"]}

# ------------------------------------------------------------------------------------------------------ wording
INTRO = ["{site}: {rooms_noun} and their bookings (24-hour clock).",
         "Booking sheet for the {rooms_noun} of {site}; 24-hour clock.",
         "{site} - {rooms_noun}. Times are on the 24-hour clock."]
FIXED = ["The listed bookings are confirmed and fixed. The new request is confirmed only if, exactly as written, it breaks none of the rules.",
         "All listed bookings are confirmed and cannot be moved. The request is judged as written: every rule must hold for it.",
         "Confirmed bookings stay as they are. The request is confirmed unchanged or not at all, which needs every rule to hold for it."]
TITLES = {"rooms": ["Rooms", "Room list", "Available rooms"],
          "gaps": ["Reset gap by kind of room", "Reset gaps", "Kinds of room and their reset gap"],
          "rules": ["Rules", "Booking rules", "Conventions"],
          "bookings": ["Confirmed bookings", "Existing bookings", "Bookings already confirmed"],
          "request": ["Request", "New request", "Requested booking"]}
TITLE_STYLES = ["{t}", "{T}", "== {t} ==", "{t}:"]
RULE_TEXT = {
    "touch": [
        "Two bookings of the same room must not overlap, but they may touch: one may start at the very minute the other ends.",
        "A room holds one {event} at a time. Back-to-back is fine: a booking may begin exactly when the previous one in that room ends.",
        "Bookings of one room may not overlap in time; a booking that starts exactly at the end time of another one does not overlap it."],
    "gap": [
        "After a booking, its room is blocked for a reset gap of {G} minutes: the next booking there may start exactly {G} minutes after that end, not earlier. Opening and closing times need no gap.",
        "Two bookings of the same room need at least {G} minutes between them (reset gap), from the end of one to the start of the next; exactly {G} minutes is enough. No gap is needed at opening or closing time.",
        "A room needs {G} minutes of reset between bookings: if one ends at time T, the next booking of that room may start at T + {G} minutes or later, not before. No reset is needed after opening or before closing time."],
    "gap_kind": [
        "After a booking, its room is blocked for the reset gap listed for its kind of room: the next booking there may start exactly when the gap is over, not earlier. Opening and closing times need no gap.",
        "Two bookings of the same room need at least the reset gap of that room's kind between them, from the end of one to the start of the next; exactly the gap is enough. No gap is needed at opening or closing time.",
        "A room needs a reset between bookings whose length depends on its kind: if one booking ends at time T, the next booking of that room may start at T + gap or later, not before. No reset is needed after opening or before closing time."],
    "person": [
        "The {org} and all {atts} are busy for the whole booking, and nobody may be in two bookings that overlap on the same day, whatever the rooms. Bookings that only touch are fine for a person: the reset gap is for rooms, not for people.",
        "A person, whether {org} or {att}, cannot be in two bookings that overlap in time on the same day, even in different rooms. People need no gap: one {event} may end at the very minute the person's next one starts.",
        "Everyone named in a booking ({org} or {att}) is occupied for its whole length; the request fails if one of its people is occupied by another booking of that day during any part of it. Back-to-back {events} are fine for people; only rooms need the reset gap."],
    "hours": [
        "A booking must lie inside the opening hours of its room; it may start exactly at opening time and end exactly at closing time.",
        "No booking may start before its room opens or end after it closes. Starting at opening time or ending at closing time is fine.",
        "Opening hours are binding: start not earlier than the opening time of the room, end not later than its closing time, equality allowed."],
    "seats": [
        "Everyone needs a {seat}: the {org} plus all {atts} must not exceed the {seats} of the room. The {org} is never repeated among the {atts}.",
        "Capacity: the number of {atts} plus one for the {org} (who is not listed among the {atts}) must not exceed the {seats} of the room; equal is allowed.",
        "The {seats} of a room limit the group: {org} and {atts} together must fit. The {org} counts as one person and is not in the {atts} list; a full room is fine."],
    "equipment": [
        "The room must have every item the request needs; equipment of other rooms does not count, and names must match exactly.",
        "Each item the request needs must be in the equipment list of the requested room itself; an item with a different name is a different item.",
        "The request is confirmed only if its room has all the items it needs. Extra equipment does no harm; a similar item under another name does not help."],
    "names": [
        "People are identified by their full name; a shared first or family name alone means nothing.",
        "Two entries are the same person only if the full names are identical.",
        "Full names identify people: the same first name with another family name is another person."],
    "duration": [
        "The request gives a start time and a duration; it ends at start + duration.",
        "The end time of the request is its start time plus its duration.",
        "The request lasts from its start time for the stated number of minutes."],
    "repeat": [
        "A booking whose day field lists several days (like Mon/Thu) takes place on each of them, at the same time, in the same room, with the same people.",
        "Some bookings repeat: a day field with several days separated by slashes means the booking exists on each of those days with the same room, time and people.",
        "A day field with slashes, such as Tue/Wed/Fri, marks a repeating booking: it occupies its room and its people on each listed day at the stated time."],
    "days": [
        "Bookings on different days never clash.",
        "Days are independent: only bookings on the day of the request can stand in its way.",
        "What is booked on another day has no effect on the request."],
}
RULES_BY_LEVEL = {1: ["touch", "hours", "seats"],
                  2: ["gap", "person", "hours", "seats", "equipment", "names", "duration"],
                  3: ["gap_kind", "person", "hours", "seats", "equipment", "names", "duration", "repeat", "days"]}
SECTION_ORDERS = [["intro", "rooms", "rules", "bookings", "request"],
                  ["intro", "rules", "rooms", "bookings", "request"],
                  ["intro", "request", "rooms", "bookings", "rules"]]


# ------------------------------------------------------------------------------------- truth on the specification
def interval(rq):
    s = mm(rq["start"])
    return s, (mm(rq["end"]) if "end" in rq else s + rq["duration"])


def gap_of(spec, room):
    g = spec["gap"]
    if g["mode"] == "none":
        return 0
    return g["minutes"] if g["mode"] == "single" else g["by_kind"][room["kind"]]


def people_of(b):
    return [b["organiser"]] + list(b["attendees"])


def analyse(spec, gap_mode=None, people_gap=False, any_room=False, any_day=False, first_day=False, skip_org=False,
            strict_hours=False, touch_clash=False, given_only=False):
    """-> {rule: evidence}; an empty list means that the request respects the rule.  The keyword arguments switch on ONE
    wrong reading each (used only to measure how far a careless reader gets; the truth uses none of them)."""
    rq = spec["request"]
    room = [r for r in spec["rooms"] if r["name"] == rq["room"]][0]
    s, e = interval(rq)
    G = gap_of(spec, room)
    if gap_mode == "zero":
        G = 0
    elif gap_mode in ("max", "min") and spec["gap"]["mode"] == "by_kind":
        G = (max if gap_mode == "max" else min)(spec["gap"]["by_kind"].values())
    key = (lambda n: n.split(" ")[0]) if given_only else (lambda n: n)
    mine = [key(n) for n in people_of(rq)]
    res = collections.OrderedDict((k, []) for k in KINDS)
    for b in spec["bookings"]:
        bdays = b["days"][:1] if first_day else b["days"]
        if not any_day and rq["day"] not in bdays:
            continue
        bs, be = mm(b["start"]), mm(b["end"])
        if b["room"] == rq["room"] or any_room:
            clear = (be + G < s or e + G < bs) if touch_clash else (be + G <= s or e + G <= bs)
            if not clear:
                res["overlap"].append(b["id"])
        pg = G if people_gap else 0
        if bs < e + pg and s < be + pg:
            res["person"] += [[n, b["id"]] for n in people_of(b) if key(n) in mine]
    o, c = mm(room["open"]), mm(room["close"])
    if s < o or (strict_hours and s == o):
        res["hours"].append(["start", o - s])
    if e > c or (strict_hours and e == c):
        res["hours"].append(["end", e - c])
    n = len(mine) - (1 if skip_org else 0)
    if n > room["seats"]:
        res["seats"].append(n - room["seats"])
    res["equipment"] = [x for x in rq.get("needs", []) if x not in room.get("equipment", [])]
    return res


def broken(spec, **kw):
    a = analyse(spec, **kw)
    return [k for k in KINDS if a[k] and k in spec["rules"]]


def truth(spec):
    return not broken(spec)


def calendar_problems(spec):
    """the confirmed bookings among themselves: [] when they respect every rule (at level 1 also the unstated person rule)"""
    rooms = {r["name"]: r for r in spec["rooms"]}
    B, out = spec["bookings"], []
    for b in B:
        r, ppl = rooms[b["room"]], people_of(b)
        if not (mm(r["open"]) <= mm(b["start"]) < mm(b["end"]) <= mm(r["close"])):
            out.append(("hours", b["id"]))
        if len(ppl) > r["seats"] or len(ppl) < 2 or len(set(ppl)) != len(ppl):
            out.append(("group", b["id"]))
        if not b["days"] or any(d not in spec["days"] for d in b["days"]) or len(set(b["days"])) != len(b["days"]):
            out.append(("days", b["id"]))
    for i, a in enumerate(B):
        for b in B[i + 1:]:
            if not [d for d in a["days"] if d in b["days"]]:
                continue
            a1, a2, b1, b2 = mm(a["start"]), mm(a["end"]), mm(b["start"]), mm(b["end"])
            if a["room"] == b["room"]:
                G = gap_of(spec, rooms[a["room"]])
                if not (a2 + G <= b1 or b2 + G <= a1):
                    out.append(("room", a["id"], b["id"]))
            if a1 < b2 and b1 < a2 and [n for n in people_of(a) if n in people_of(b)]:
                out.append(("person", a["id"], b["id"]))
    return out


def leaves(x, path=()):
    if isinstance(x, dict):
        for k in x:
            for item in leaves(x[k], path + (k,)):
                yield item
    elif isinstance(x, list):
        for i, v in enumerate(x):
            for item in leaves(v, path + (i,)):
                yield item
    else:
        yield path, x


def features(spec):
    """near-limit situations and decoys of one item (counts); used for the README tables and for sanity checks"""
    rq = spec["request"]
    room = [r for r in spec["rooms"] if r["name"] == rq["room"]][0]
    s, e = interval(rq)
    G, mine = gap_of(spec, room), people_of(rq)
    given, family = [n.split(" ")[0] for n in mine], [n.split(" ")[1] for n in mine]
    f = collections.OrderedDict((k, 0) for k in (
        "room_neighbour_exact", "starts_at_opening", "ends_at_closing", "room_exactly_full", "equipment_exactly_needed", "attendee_meeting_touches",
        "other_room_same_time", "other_room_booking_touches", "namesake_same_time", "same_room_other_day", "attendee_busy_other_day",
        "repeating_on_the_day", "other_room_too_small", "other_room_closed", "other_room_lacks_item", "other_room_has_all_items"))
    f["starts_at_opening"], f["ends_at_closing"] = int(s == mm(room["open"])), int(e == mm(room["close"]))
    f["room_exactly_full"] = int(len(mine) == room["seats"])
    f["equipment_exactly_needed"] = int(bool(rq.get("needs")) and sorted(rq["needs"]) == sorted(room.get("equipment", [])))
    for b in spec["bookings"]:
        bs, be, today, ppl = mm(b["start"]), mm(b["end"]), rq["day"] in b["days"], people_of(b)
        shared = [n for n in ppl if n in mine]
        if today:
            f["repeating_on_the_day"] += len(b["days"]) > 1
            if b["room"] == rq["room"]:
                f["room_neighbour_exact"] += (be + G == s or e + G == bs)
            else:
                f["attendee_meeting_touches"] += bool(shared) and (be == s or bs == e)
                f["other_room_booking_touches"] += (be == s or bs == e)
                if bs < e and s < be:
                    f["other_room_same_time"] += 1
                    f["namesake_same_time"] += any(n not in mine and (n.split(" ")[0] in given or n.split(" ")[1] in family) for n in ppl)
        else:
            f["same_room_other_day"] += b["room"] == rq["room"] and not (be + G <= s or e + G <= bs)
            f["attendee_busy_other_day"] += bool(shared) and bs < e and s < be
    for r in spec["rooms"]:
        if r is not room:
            f["other_room_too_small"] += r["seats"] < len(mine)
            f["other_room_closed"] += s < mm(r["open"]) or e > mm(r["close"])
            f["other_room_lacks_item"] += any(x not in r.get("equipment", []) for x in rq.get("needs", []))
            f["other_room_has_all_items"] += bool(rq.get("needs")) and all(x in r.get("equipment", []) for x in rq["needs"])
    return collections.OrderedDict((k, int(v)) for k, v in f.items())


CHEAP_READER = "cheap checks only: hours, seats, equipment (no booking read), otherwise yes"
SLOPPY = [("touching bookings of a room read as a clash", {"touch_clash": True}),
          ("reset gap ignored", {"gap_mode": "zero"}),
          ("largest listed reset gap used for every room", {"gap_mode": "max"}),
          ("smallest listed reset gap used for every room", {"gap_mode": "min"}),
          ("reset gap also demanded between the meetings of a person", {"people_gap": True}),
          ("room ignored: any booking at that time blocks", {"any_room": True}),
          ("day ignored", {"any_day": True}),
          ("repeating bookings read on their first day only", {"first_day": True}),
          ("organiser not counted for the seats", {"skip_org": True}),
          ("opening / closing time itself read as outside", {"strict_hours": True}),
          ("people matched by first name", {"given_only": True}),
          ("only the bookings of the requested room are read (people, seats, hours, equipment skipped)", {"only": ["overlap"]}),
          ("people never checked", {"skip": ["person"]}),
          (CHEAP_READER, {"only": list(CHEAP)}),
          ("always yes", {"only": []})]


def sloppy_answer(spec, kw):
    kw = dict(kw)
    only, skip = kw.pop("only", None), kw.pop("skip", [])
    bad = [k for k in broken(spec, **kw) if (only is None or k in only) and k not in skip]
    return not bad


# ---------------------------------------------------------------------------------------------------- the plan
def spread(rng, combos, n):
    out = []
    while len(out) < n:
        c = [dict(x) for x in combos]
        rng.shuffle(c)
        out += c
    return out[:n]


def variants(rng, level, kind, n):
    """n variants of one kind at one level, every combination used as equally often as n allows"""
    D = (5, 10, 15)
    # (minutes moved, minutes that the positive keeps inside the limit).  Level 1 writes start and end, so a time that sits
    # exactly on a limit can be spotted without knowing the room: there half of the positives keep 5 minutes (see `inside`)
    steps = [(5, 0), (10, 0), (15, 0), (10, 5), (15, 5), (10, 5)] if level == 1 else [(d, 0) for d in D]
    if kind == "overlap":
        sides = [("prev", "start"), ("next", "end")] if level == 1 else [("prev", "start"), ("next", "duration"), ("next", "start")]
        return spread(rng, [{"side": a, "field": f, "delta": d, "inside": i} for a, f in sides for d, i in steps], n)
    if kind == "hours":
        req = [("open", "start"), ("close", "end")] if level == 1 else [("open", "start"), ("close", "duration"), ("close", "start")]
        half = n // 2
        if level == 3:                                       # only violations that need the computed end (start + duration) and the closing time
            req = [("close", "duration"), ("close", "start")]
            a = spread(rng, [{"side": sd, "field": f, "delta": d, "inside": i} for sd, f in req for d, i in steps], n - half)
            b = spread(rng, [{"side": "close", "field": "close", "delta": 15}], half)
            return a + b
        a = spread(rng, [{"side": sd, "field": f, "delta": d, "inside": i} for sd, f in req for d, i in steps], n - half)
        b = spread(rng, [{"side": "open", "field": "open", "delta": 15}, {"side": "close", "field": "close", "delta": 15}], half)
        return a + b
    if kind == "person":
        half = n // 2
        a = spread(rng, [{"mode": "name", "side": sd, "delta": d} for sd in ("prev", "next") for d in D], n - half)
        b = spread(rng, [{"mode": "time", "shift": sh, "delta": d} for sh in ("start-", "start+", "duration+") for d in D], half)
        return a + b
    if kind == "equipment":
        return spread(rng, [{"field": "needs"}, {"field": "room"}], n)
    return [{} for _ in range(n)]


def make_plan():
    rng = rng_for("plan")
    plan = []
    for level in (1, 2, 3):
        layouts = (LAYOUTS * 34)[:100]
        rng.shuffle(layouts)
        k = 0
        all_doms = (list(DOMAINS) * (100 // len(DOMAINS)))[:100]           # the domains cycle over the kinds: 20 per domain and level
        for kind, n in zip(LEVEL_KINDS[level], LEVEL_COUNTS[level]):
            doms = all_doms[:n]
            all_doms = all_doms[n:]
            rng.shuffle(doms)
            for v, d in zip(variants(rng, level, kind, n), doms):
                plan.append({"level": level, "kind": kind, "variant": v, "domain": d, "layout": layouts[k]})
                k += 1
    rng.shuffle(plan)
    return plan


# ---------------------------------------------------------------------------------------------------- one pair
def build_pair(rng, P):
    """-> (specification of the positive, of the negative, info).  Raises Reject when a draw cannot be completed."""
    L, kind, var = P["level"], P["kind"], P["variant"]
    dom = DOMAINS[P["domain"]]
    delta, inside = var.get("delta", 0), var.get("inside", 0)
    side, field, mode, shift = var.get("side"), var.get("field"), var.get("mode"), var.get("shift")

    # ---- rooms, days, reset gaps
    n_rooms, n_book = rng.randint(*ROOMS[L]), rng.randint(*BOOKINGS[L])
    r0 = rng.randrange(n_rooms)
    days = sorted(rng.sample(range(5), rng.choice([2, 3, 3]))) if L == 3 else [rng.randrange(5)]
    d0 = rng.choice(days[1:]) if L == 3 and rng.random() < 0.8 else rng.choice(days)      # level 3: mostly not the first day of the week sample, so that a
    # repeating booking can list another day before the day of the request (Mon/Thu read on Thu)
    odays = [d for d in days if d != d0]
    if rng.random() < 0.6:
        rnames = [o + rng.choice(ROOM_CO) for o in rng.sample(ROOM_ON, n_rooms)]
    else:
        rnames = ["%s-%d" % (c, rng.randrange(101, 500)) for c in rng.sample("ABCDEFGHKLMNPRSTW", n_rooms)]
    site = rng.choice(dom["site"]).format(n=rng.choice(SITE_ON) + rng.choice(SITE_CO))
    kinds, by_kind = [None] * n_rooms, None
    if L == 1:
        gaps = [0] * n_rooms
    elif L == 2:
        g_all = [5, 10, 15, 20]
        if kind == "overlap" and rng.random() < P_GAP_ONLY:   # the planted overlap lies inside the reset gap (the gap is at least `delta`)
            g_all = [g for g in g_all if g >= delta]
        gaps = [rng.choice(g_all)] * n_rooms
    else:
        kk, vals = rng.sample(dom["kinds"], 3), rng.sample([5, 10, 15, 20, 30], 3)
        if rng.random() < 0.15:
            vals[rng.randrange(3)] = 0
        by_kind = collections.OrderedDict(zip(kk, vals))
        kinds = [kk[i % 3] for i in range(n_rooms)]
        rng.shuffle(kinds)
        if kind == "overlap" and rng.random() < P_GAP_ONLY:
            # the planted overlap lies inside the reset gap of the requested room's kind: the request does not touch the neighbour's
            # own time, so only the gap of THAT kind of room (list of gaps) decides.  The gap of the kind is at least `delta`.
            k0 = kinds[r0]
            if by_kind[k0] < delta:
                big = max(by_kind, key=lambda k: by_kind[k])
                by_kind[k0], by_kind[big] = by_kind[big], by_kind[k0]
        gaps = [by_kind[k] for k in kinds]
    G0 = gaps[r0]

    # ---- people (given names and family names are unique inside an item, except the namesakes planted below)
    g_on, f_on = rng.sample(GIVEN_ON, len(GIVEN_ON)), rng.sample(FAMILY_ON, len(FAMILY_ON))

    def new_person(given=None, family=None, length=None):
        for _ in range(8):
            if (not given and not g_on) or (not family and not f_on):
                raise Reject("names used up")
            gi, fi = (None if given else g_on.pop()), (None if family else f_on.pop())
            for _ in range(30):
                name = (given or gi + rng.choice(GIVEN_CO)) + " " + (family or fi + rng.choice(FAMILY_CO))
                if length is None or len(name) == length:
                    return name
        raise Reject("no name of that length")

    n_att = rng.randint(*ATTENDEES[L])
    if kind == "seats":
        n_att = max(n_att, 2)                               # the negative of a seats pair has party - 1 >= 2 seats
    party = n_att + 1
    org, atts = new_person(), [new_person() for _ in range(n_att)]
    pool = [org] + atts + [new_person() for _ in range(rng.randint(*POOL[L]) - party)]
    ix = rng.randrange(n_att)                               # the attendee slot that is swapped (person / name) or pivots (person / time)
    Y = new_person(length=len(atts[ix])) if (kind == "person" and mode == "name") else None
    if Y:
        pool.append(Y)
    crew = [org] + atts + ([Y] if Y else [])                # everybody who is in the request of one of the two members

    # ---- seats, equipment, opening hours
    if kind == "seats":
        seat_pos = party
    elif L >= 2:                                            # the room is exactly full in most items whose planted rule is another one (a decoy in both members)
        seat_pos = party + (0 if rng.random() < P_FULL else rng.choice([1, 1, 2, 3]))
    else:
        seat_pos = party + rng.choice([0, 0, 0, 0, 1, 1, 1, 2, 3, 4])
    seat_neg = party - 1 if kind == "seats" else seat_pos
    seats = [rng.randint(2, 12) for _ in range(n_rooms)]
    if L == 1 and party >= 3:                               # with two rooms: the other one is too small for the request half of the time
        seats = [rng.randint(2, party - 1) if rng.random() < 0.5 else rng.randint(party, 12) for _ in range(n_rooms)]
    seats[r0] = seat_pos
    equipment, needs, E, F = [[] for _ in range(n_rooms)], [], None, None
    if L >= 2:
        items = list(dom["equipment"])
        if kind == "equipment":                              # several needed items to compare with the list of one room
            n_needs = rng.choice([2, 2, 3] if L == 2 else [2, 3, 3])
        else:
            n_needs = rng.choice([1, 2, 2] if L == 2 else [1, 2, 2, 3])
        needs = rng.sample(items, n_needs)
        n_spare = 0 if rng.random() < P_EXACT_EQ else rng.choice([1, 1, 2])    # mostly exactly the needed items (a decoy in both members)
        eq0 = needs + rng.sample([x for x in items if x not in needs], n_spare)
        rng.shuffle(eq0)
        equipment = [rng.sample(items, rng.randint(1, 4)) for _ in range(n_rooms)]
        equipment[r0] = eq0
        if kind == "equipment":
            E = rng.choice(needs)
            cand = [x for x in items if x not in eq0]
            near = [x for x in cand if x.split(" ")[-1] == E.split(" ")[-1]]       # e.g. upright piano for grand piano
            same = [x for x in cand if len(x) == len(E)]
            F = rng.choice(near) if near and rng.random() < 0.5 else rng.choice(same) if same else rng.choice(cand)
        if rng.random() < 0.5:                               # another room has everything the request (of either member) needs
            j = rng.choice([i for i in range(n_rooms) if i != r0])
            full = needs + ([F] if field == "needs" else [])
            full += rng.sample([x for x in items if x not in full], rng.choice([0, 1]))
            rng.shuffle(full)
            equipment[j] = full
        if F and not any(F in equipment[i] for i in range(n_rooms) if i != r0):   # the other item is seen in another room in both members
            j = rng.choice([i for i in range(n_rooms) if i != r0])
            equipment[j].insert(rng.randrange(len(equipment[j]) + 1), F)
    hrs = [draw_hours(rng, 0.3) for _ in range(n_rooms)]
    hrs[r0] = draw_hours(rng, 0.2, keep_open=(field == "open"), keep_close=(field == "close"))
    opens, closes = [h[0] for h in hrs], [h[1] for h in hrs]
    o0, c0 = opens[r0], closes[r0]

    # ---- the request: positive [s, e), negative [ns, ne)
    longer = delta if (field in ("end", "duration") or shift == "duration+" or (L == 1 and field == "start")) else 0
    for _ in range(60):                                      # the negative is `longer` minutes longer: both lengths stay inside the range,
        dur = rng.randrange(REQ_LEN[L][0], REQ_LEN[L][1] - longer + 5, 5)
        if L == 1 or len(str(dur)) == len(str(dur + longer)):                  # and a written duration keeps its number of digits
            break
    else:
        raise Reject("duration")
    if kind == "hours":
        place = side
    elif L >= 2:
        # the opening hours are a decoy: the request starts exactly at opening time / ends exactly at closing time in MOST items whose
        # planted rule is another one, and in BOTH members: only where the changed field leaves that edge of the request alone
        # (a start that shifts or an end that moves would leave the limit in one member only, and that would mark a class)
        start_fixed = kind in ("seats", "equipment") or (kind == "person" and (mode == "name" or shift == "duration+")) or \
            (kind == "overlap" and field == "duration")
        end_fixed = kind in ("seats", "equipment") or (kind == "person" and mode == "name")
        edges = (["open"] if start_fixed else []) + (["close"] if end_fixed else [])
        # with one fixed edge only, half of the items take the limit of the hours there and the other half (below) a neighbour of the
        # room exactly at the gap: the start sits ON a limit of the room in both members either way
        place = rng.choice(edges) if edges and rng.random() < (P_LIMIT if len(edges) == 2 else 0.45) else "mid"
    else:
        u = rng.random()
        place = "open" if u < 0.12 else "close" if u < 0.24 else "mid"
        if (place == "open" and ((kind == "overlap" and side == "prev") or shift == "start-")) or \
           (place == "close" and ((kind == "overlap" and side == "next") or shift in ("start+", "duration+"))):
            place = "mid"
    s = o0 if place == "open" else c0 - dur if place == "close" else rng.randrange(o0 + 60, c0 - dur - 60 + 5, 5)
    if kind == "hours":
        s += inside if side == "open" else -inside            # a positive that keeps `inside` minutes to the opening / closing time
    e = s + dur
    ns, ne, o0n, c0n = s, e, o0, c0
    if kind == "overlap":
        if side == "prev":
            ns, ne = s - delta, (e if L == 1 else e - delta)
        elif field in ("end", "duration"):
            ne = e + delta
        else:
            ns, ne = s + delta, e + delta
    elif kind == "hours":
        if field == "open":
            o0n = o0 + 15
        elif field == "close":
            c0n = c0 - 15
        elif side == "open":
            ns, ne = s - delta, (e if L == 1 else e - delta)
        elif field in ("end", "duration"):
            ne = e + delta
        else:
            ns, ne = s + delta, e + delta
    elif kind == "person" and mode == "time":
        if shift == "start-":
            ns, ne = s - delta, e - delta
        elif shift == "start+":
            ns, ne = s + delta, e + delta
        else:
            ne = e + delta
    lo, hi = min(s, ns), max(e, ne)                         # every minute that belongs to the request in one of the members
    both_lo, both_hi = max(s, ns), min(e, ne)               # the minutes that belong to it in both
    if kind != "hours" and (lo < o0 or hi > c0):
        raise Reject("request outside the hours")
    if kind == "hours":
        # one other room: open long before the request (it can hold a booking that ends when the request starts), or with its
        # own opening / closing time exactly at the earliest start / latest end of the request (a reader of the wrong row sees
        # a request that starts at opening time), or as drawn
        j, u = rng.choice([i for i in range(n_rooms) if i != r0]), rng.random()
        p_far, p_same = (0.0, 0.8) if field in ("open", "close") else (0.6, 0.2) if L == 1 else (0.4, 0.3)
        if side == "open":
            early = [t for t in GRID_OPEN if t <= lo - 30]
            t = rng.choice(early) if u < p_far and early else lo if p_far <= u < p_far + p_same and lo % 15 == 0 and lo >= 7 * 60 else None
            if t is not None and closes[j] - t >= 240:
                opens[j] = t
        else:
            late = [t for t in GRID_CLOSE + AFTERNOON[1] if t >= hi + 30]
            t = rng.choice(late) if u < p_far and late else hi if p_far <= u < p_far + p_same and hi % 15 == 0 and hi <= 20 * 60 else None
            if t is not None and t - opens[j] >= 240:
                closes[j] = t
    eff_open, eff_close, eff_seats = list(opens), list(closes), list(seats)
    eff_open[r0], eff_close[r0], eff_seats[r0] = max(o0, o0n), min(c0, c0n), seat_neg   # what the confirmed bookings must respect in both members

    # ---- occupancy of the rooms
    bookings, occ = [], collections.defaultdict(list)

    def fits(room, ds, a, b):
        if b - a < 20 or a < eff_open[room] or b > eff_close[room]:
            return False
        g = gaps[room]
        return all(y + g <= a or b + g <= x for d in ds for x, y in occ[(room, d)])

    def add(room, ds, a, b, tag, need=(), forced=None):
        bk = {"room": room, "days": sorted(ds), "start": a, "end": b, "tag": tag, "need": list(need), "forced": forced, "people": []}
        for d in bk["days"]:
            occ[(room, d)].append((a, b))
        bookings.append(bk)
        return bk

    def rep_days(prob, later=False):
        """days of a planted booking of the request's day: at level 3 it is sometimes a repeating booking; with `later` the
        other day is an earlier one when there is one, so that the day of the request is not the first day of the field"""
        if L == 3 and rng.random() < prob:
            earlier, after = [d for d in odays if d < d0], [d for d in odays if d > d0]
            if later and earlier and rng.random() < P_LATER:
                return sorted([d0, rng.choice(earlier)])
            pick = after if later and after else odays       # `later` not drawn: the request day stays the first listed one where it can
            return sorted([d0] + rng.sample(pick, 1 if len(pick) == 1 or rng.random() < 0.7 else 2))
        return [d0]

    def place_other(a, b, ds, tag, need=(), forced=None):
        cand = [r for r in range(n_rooms) if r != r0]
        rng.shuffle(cand)
        for dd in ([ds, [d0]] if len(ds) > 1 else [ds]):
            for r in cand:
                if fits(r, dd, a, b):
                    return add(r, dd, a, b, tag, need, forced)
        return None

    # the neighbour that the negative of an `overlap` pair runs into (the positive keeps exactly the gap to it)
    neighbour = None
    if kind == "overlap":
        ln = rng.randrange(25, 95, 5)
        if side == "prev":
            a_, b_ = max(s - G0 - inside - ln, eff_open[r0]), s - G0 - inside
        else:
            a_, b_ = e + G0 + inside, min(e + G0 + inside + ln, eff_close[r0])
        ds = rep_days(P_REPEAT, later=True)
        if not fits(r0, ds, a_, b_):
            raise Reject("no room for the neighbour")
        neighbour = add(r0, ds, a_, b_, "neighbour")
    occ[(r0, d0)].append((lo, hi))                          # the request itself: everything planted later keeps clear of both members
    # other neighbours in the requested room: exactly at the gap, a little further away, or none
    no_shift = (s, e) == (ns, ne)
    plan_nb = {}
    for sd in ("prev", "next"):
        if (kind == "overlap" and sd == side) or (sd == "prev" and place == "open") or (sd == "next" and place == "close"):
            continue
        u = rng.random()
        p0 = 0.5
        if L >= 2 and not no_shift:
            # a neighbour exactly at the gap: likely when the negative is exact to it (it is then a decoy of the negative, which the
            # positive of an `overlap` pair cannot have), rare when only the positive is (the planted neighbour is its limit already)
            p0 = 0.75 if (lo == ns if sd == "prev" else hi == ne) else 0.2
        plan_nb[sd] = 0 if u < p0 else rng.choice([5, 10, 15, 20, 30, 45]) if u < p0 + (1 - p0) / 2 else None
    if no_shift and place == "mid" and 0 not in plan_nb.values():
        plan_nb[rng.choice(sorted(plan_nb))] = 0            # an unshifted request sits ON a limit of its room at least once
    exact = 0
    for sd in ("prev", "next"):
        off = plan_nb.get(sd)
        if off is None:
            continue
        ln = rng.randrange(25, 95, 5)
        a_, b_ = (max(lo - G0 - off - ln, eff_open[r0]), lo - G0 - off) if sd == "prev" else (hi + G0 + off, min(hi + G0 + off + ln, eff_close[r0]))
        for ds in (rep_days(0.4), [d0]):
            if fits(r0, ds, a_, b_):
                add(r0, ds, a_, b_, "near")
                exact += off == 0
                break
    if no_shift and place == "mid" and not exact:
        raise Reject("no room for a neighbour at the limit")

    # ---- people who are busy elsewhere (level 2 and 3)
    viol, touched = None, []
    if kind == "person":
        ln = rng.randrange(30, 85, 5)
        if mode == "name":                                   # Y sits in a booking of another room that overlaps the request by delta minutes
            a_, b_ = (s + delta - ln, s + delta) if side == "prev" else (e - delta, e - delta + ln)
            viol = place_other(a_, b_, rep_days(P_REPEAT, later=True), "conflict", [Y], Y)
            ln2 = rng.randrange(20, 80, 5)                   # X, whom Y replaces, has a booking that only touches the request
            a2, b2 = (s - ln2, s) if rng.random() < 0.5 else (e, e + ln2)
            tb = place_other(a2, b2, rep_days(0.3), "touch", [atts[ix]])
            if tb is None:
                a2, b2 = (e, e + ln2) if b2 == s else (s - ln2, s)
                tb = place_other(a2, b2, [d0], "touch", [atts[ix]])
            if tb is None:
                raise Reject("no room for the touching booking")
        else:                                                # the pivot attendee has a booking that touches the positive and is cut by the negative
            a_, b_ = (s - ln, s) if shift == "start-" else (e, e + ln)
            viol = place_other(a_, b_, rep_days(P_REPEAT, later=True), "conflict", [atts[ix]], atts[ix])
        if viol is None:
            raise Reject("no room for the conflicting booking")
        touched.append(atts[ix])
    if L >= 2:
        free_crew = [n for n in [org] + atts if n not in touched]
        rng.shuffle(free_crew)
        if kind == "person":
            n_touch = rng.choice([1, 1, 2] if L == 2 else [1, 2, 2])
        else:
            n_touch = rng.choice([0, 1, 1, 2] if L == 2 else [1, 1, 2, 2])
        for t in range(n_touch):
            n = free_crew.pop()
            ln = rng.randrange(20, 80, 5)
            if kind == "person" and t == 0:
                # somebody else of the request has a booking that touches the request of the NEGATIVE exactly (and that of the
                # positive when the times are the same): a touching meeting is seen in both classes of the person pairs
                sides = [sd for sd in ("before", "after") if (lo == ns if sd == "before" else hi == ne)]
                rng.shuffle(sides)
                for sd in sides:
                    a_, b_ = (lo - ln, lo) if sd == "before" else (hi, hi + ln)
                    if place_other(a_, b_, rep_days(0.3), "touch", [n]):
                        break
                else:
                    raise Reject("no room for the touching decoy")
                continue
            off = 0 if rng.random() < 0.7 else rng.choice([5, 10])
            a_, b_ = (lo - off - ln, lo - off) if rng.random() < 0.5 else (hi + off, hi + off + ln)
            place_other(a_, b_, rep_days(0.3), "touch", [n])
    if L == 1 and not no_shift:
        # level 1 writes start and end.  A booking of the OTHER room ends exactly when the request starts (or starts exactly
        # when it ends): for the request of the positive when that one sits exactly on its limit, for the request of the
        # negative when the positive keeps 5 minutes.  So neither "this time occurs elsewhere in the state" nor "a booking of
        # the other room touches the request" marks a class.  Nobody of the request is in that booking.
        ln = rng.randrange(20, 70, 5)
        if ns != s:
            t = ns if inside else s
            a_, b_ = t - ln, t
        else:
            t = ne if inside else e
            a_, b_ = t, t + ln
        place_other(a_, b_, [d0], "echo")
    # a booking in another room at the time of the request (nobody of the request is in it); sometimes with a namesake
    same_time = None
    for _ in range(6):
        ln = rng.randrange(25, 95, 5)
        a_ = rng.randrange(both_lo - ln + 10, both_hi - 5, 5)
        same_time = place_other(a_, a_ + ln, rep_days(0.3), "same_time")
        if same_time is not None:
            break
    if same_time is None and not (viol and no_shift):
        closed = [r for r in range(n_rooms) if r != r0 and (lo < opens[r] or hi > closes[r])]
        if not (L == 1 and closed):                          # with two rooms the other one may instead be closed at that time
            raise Reject("no room for the booking at the same time")
    if L >= 2 and same_time is not None:
        stable = [n for n in [org] + atts if not (Y and n == atts[ix])]
        if rng.random() < 0.45:
            z = new_person(given=rng.choice(stable).split(" ")[0])
            pool.append(z)
            same_time["need"].append(z)
        if rng.random() < 0.25 and eff_seats[same_time["room"]] >= 2 and len(same_time["need"]) < 2:
            z = new_person(family=rng.choice(stable).split(" ")[1])
            pool.append(z)
            same_time["need"].append(z)
    if L == 3:
        stable = [n for n in [org] + atts if not (Y and n == atts[ix])]
        rng.shuffle(stable)
        # the requested room, another day, at the clock time of the request; one person of the request is in it
        for _ in range(40):
            ln = rng.randrange(25, 85, 5)
            a_ = rng.randrange(both_lo - ln + 10, both_hi - 5, 5)
            ds = sorted(odays) if len(odays) == 2 and rng.random() < 0.5 else [rng.choice(odays)]
            if fits(r0, ds, a_, a_ + ln):
                add(r0, ds, a_, a_ + ln, "other_day", [stable[0]])
                break
        else:
            raise Reject("no room for the other-day booking")
        if rng.random() < 0.6:                               # another room, another day, same clock time, another person of the request
            ln = rng.randrange(25, 85, 5)
            a_ = rng.randrange(both_lo - ln + 10, both_hi - 5, 5)
            cand = [r for r in range(n_rooms) if r != r0]
            rng.shuffle(cand)
            ds = [rng.choice(odays)]
            for r in cand:
                if fits(r, ds, a_, a_ + ln):
                    add(r, ds, a_, a_ + ln, "other_day", [stable[1]])
                    break
    if len(bookings) > n_book:
        raise Reject("too many planted bookings")

    # ---- the remaining bookings
    tries = 0
    while len(bookings) < n_book:
        tries += 1
        if tries > 4000:
            raise Reject("calendar cannot be filled")
        cnt = [sum(1 for bk in bookings if bk["room"] == r) for r in range(n_rooms)]
        room = rng.choices(range(n_rooms), [1.0 / (1 + c) ** 2 for c in cnt])[0]
        if L == 3 and rng.random() < 0.22:
            ds = sorted(rng.sample(days, 2 if len(days) == 2 or rng.random() < 0.7 else 3))
        elif L == 3:
            ds = [rng.choices(days, [1.4 if d == d0 else 1.0 for d in days])[0]]
        else:
            ds = [d0]
        ln = rng.choice(LENS)
        slots = [iv for d in ds for iv in occ[(room, d)]]
        if slots and rng.random() < 0.45:                    # directly before or after something that is already there
            x, y = rng.choice(slots)
            a_ = y + gaps[room] if rng.random() < 0.5 else x - gaps[room] - ln
        else:
            a_ = rng.randrange(eff_open[room], eff_close[room] - ln + 5, 5)
        if fits(room, ds, a_, a_ + ln):
            add(room, ds, a_, a_ + ln, "fill")
    n_rep = sum(1 for bk in bookings if len(bk["days"]) > 1)
    if L == 3 and not 3 <= n_rep <= 8:
        raise Reject("number of repeating bookings")

    # ---- who is in which booking
    busy = {n: [] for n in pool}
    load = {n: 0 for n in pool}
    for n in crew:
        busy[n].append((d0, lo, hi, True))                   # the request (both members); only the planted conflict may cut into it

    def is_free(n, bk, ignore_request=False):
        return not any(d in bk["days"] and a < bk["end"] and bk["start"] < b and not (req and ignore_request) for d, a, b, req in busy[n])

    def put(n, bk):
        bk["people"].append(n)
        load[n] += 1
        for d in bk["days"]:
            busy[n].append((d, bk["start"], bk["end"], False))

    for bk in bookings:
        for n in bk["need"]:
            if not is_free(n, bk, ignore_request=(bk["forced"] == n)) or len(bk["people"]) >= eff_seats[bk["room"]]:
                raise Reject("planted person is not free")
            put(n, bk)
    order = list(range(len(bookings)))
    rng.shuffle(order)
    for i in order:
        bk = bookings[i]
        want = min(eff_seats[bk["room"]], max(len(bk["people"]), rng.choice(PARTY[L])))
        cand = [n for n in pool if n not in bk["people"] and is_free(n, bk) and not (bk["tag"] == "echo" and n in crew)]
        keyed = sorted(((rng.random() ** ((1.0 + load[n]) / (2.5 if n in crew else 1.0)), n) for n in cand), reverse=True)
        for _, n in keyed[:max(0, want - len(bk["people"]))]:
            put(n, bk)
        if len(bk["people"]) < 2:
            raise Reject("booking with one person")
    for n in crew:                                           # everybody of the request is seen somewhere in the confirmed bookings
        if load[n] == 0:
            cand = [bk for bk in bookings if len(bk["people"]) < eff_seats[bk["room"]] and is_free(n, bk) and bk["tag"] != "echo"]
            if not cand:
                raise Reject("person without any booking")
            put(n, rng.choice(cand))
    if L >= 2:
        elsewhere = [bk for bk in bookings if d0 in bk["days"] and bk["room"] != r0]
        busy_crew = [n for n in [org] + atts if any(n in bk["people"] for bk in elsewhere)]
        spread_rooms = sorted(set(bk["room"] for bk in elsewhere if any(n in bk["people"] for n in [org] + atts)))
        if len(busy_crew) < (2 if L == 2 else 4) or len(spread_rooms) < (1 if L == 2 else 3):
            raise Reject("attendees have too few other meetings")
    for bk in bookings:
        rng.shuffle(bk["people"])
        if bk["forced"] is not None and bk["people"][0] == bk["forced"]:      # the conflicting person is found in an attendee list
            bk["people"][0], bk["people"][1] = bk["people"][1], bk["people"][0]

    # ---- order of the list and ids
    sort = rng.choice({1: ["room_time", "time"], 2: ["time", "mixed"], 3: ["day_time", "mixed", "mixed"]}[L])
    if sort == "mixed":
        rng.shuffle(bookings)
    elif sort == "room_time":
        bookings.sort(key=lambda bk: (bk["room"], bk["start"]))
    else:
        bookings.sort(key=lambda bk: (bk["days"][0], bk["start"], bk["room"]))
    if rng.random() < 0.6:
        pre = rng.choice("BKMNQRT")
        ids = ["%s%02d" % (pre, i + 1) for i in range(len(bookings))]
    else:
        num, ids = rng.randrange(101, 640), []
        for _ in bookings:
            ids.append("#%d" % num)
            num += rng.randint(1, 7)
    for bk, i in zip(bookings, ids):
        bk["id"] = i

    # ---- the two specifications
    rules = [k for k in KINDS if k in LEVEL_KINDS[L]]
    gap = {"mode": "none"} if L == 1 else {"mode": "single", "minutes": G0} if L == 2 else {"mode": "by_kind", "by_kind": by_kind}
    rooms = []
    for r in range(n_rooms):
        d = collections.OrderedDict([("name", rnames[r])])
        if L == 3:
            d["kind"] = kinds[r]
        d["seats"] = seats[r]
        if L >= 2:
            d["equipment"] = list(equipment[r])
        d["open"], d["close"] = fmt(opens[r]), fmt(closes[r])
        rooms.append(d)
    rq = collections.OrderedDict([("room", rnames[r0]), ("day", DAYN[d0]), ("start", fmt(s))])
    if L == 1:
        rq["end"] = fmt(e)
    else:
        rq["duration"] = dur
    rq["organiser"], rq["attendees"] = org, list(atts)
    if L >= 2:
        rq["needs"] = list(needs)
    pos = collections.OrderedDict([
        ("level", L), ("domain", P["domain"]), ("site", site), ("days", [DAYN[d] for d in days]), ("rules", rules), ("gap", gap),
        ("rooms", rooms),
        ("bookings", [collections.OrderedDict([("id", bk["id"]), ("room", rnames[bk["room"]]), ("days", [DAYN[d] for d in bk["days"]]),
                                               ("start", fmt(bk["start"])), ("end", fmt(bk["end"])), ("organiser", bk["people"][0]),
                                               ("attendees", list(bk["people"][1:]))]) for bk in bookings]),
        ("request", rq)])
    neg = copy.deepcopy(pos)
    nrq, nroom = neg["request"], neg["rooms"][r0]
    if (s, e) != (ns, ne):
        if ns != s:
            nrq["start"], changed = fmt(ns), "request.start"
        elif L == 1:
            nrq["end"], changed = fmt(ne), "request.end"
        else:
            nrq["duration"], changed = ne - ns, "request.duration"
    elif kind == "hours":
        nroom["open"], nroom["close"], changed = fmt(o0n), fmt(c0n), "room." + field
    elif kind == "seats":
        nroom["seats"], changed = seat_neg, "room.seats"
    elif kind == "equipment" and field == "needs":
        nrq["needs"][nrq["needs"].index(E)], changed = F, "request.needs"
    elif kind == "equipment":
        nroom["equipment"][nroom["equipment"].index(E)], changed = F, "room.equipment"
    else:
        nrq["attendees"][ix], changed = Y, "request.attendee"
    dec = neighbour if kind == "overlap" else viol if kind == "person" else None        # the booking that the negative runs into
    route = collections.OrderedDict([
        ("rule", kind), ("needs_booking_list", kind not in CHEAP), ("booking", dec["id"] if dec else None),
        ("repeating", bool(dec) and len(dec["days"]) > 1),
        ("request_day_not_first_listed", bool(dec) and len(dec["days"]) > 1 and dec["days"][0] != d0),
        ("gap_only", kind == "overlap" and not (dec["start"] < ne and ns < dec["end"])),
        ("reset_gap_minutes", G0 if kind == "overlap" else None)])
    info = {"field": changed, "delta": delta, "sort": sort, "placing": place,
            "neighbour": neighbour["id"] if neighbour else None, "conflict_booking": viol["id"] if viol else None,
            "conflict_person": (Y or atts[ix]) if viol else None, "pivot": atts[ix] if kind == "person" else None, "route": route}
    return pos, neg, info


# ------------------------------------------------------------------------------------------- checks on one pair
def check_pair(P, pos, neg, info):
    L, kind, var = P["level"], P["kind"], P["variant"]
    delta, inside = var.get("delta", 0), var.get("inside", 0)
    assert inside in (0, 5) and (inside == 0 or L == 1)
    for sp in (pos, neg):
        probs = calendar_problems(sp)
        assert not probs, ("the confirmed bookings break a rule among themselves", probs)
        names = [n for b in sp["bookings"] for n in people_of(b)] + people_of(sp["request"])
        assert all(re.fullmatch(r"[A-Z][a-z]+ [A-Z][a-z]+", n) for n in names), names
        assert len(set(people_of(sp["request"]))) == len(people_of(sp["request"]))
        assert len(set(b["id"] for b in sp["bookings"])) == len(sp["bookings"]) and len(set(r["name"] for r in sp["rooms"])) == len(sp["rooms"])
        assert all(n in [m for b in sp["bookings"] for m in people_of(b)] for n in people_of(sp["request"])), "a person of the request is in no booking"
        assert sp["request"]["day"] in sp["days"] and all(t % 5 == 0 for t in interval(sp["request"]))
    a, b = analyse(pos), analyse(neg)
    assert not any(a[k] for k in KINDS), ("the positive breaks a rule", a)
    assert [k for k in KINDS if b[k]] == [kind], ("the negative must break exactly the planted rule", kind, b)
    assert kind in pos["rules"] and truth(pos) is True and truth(neg) is False
    da, db = collections.OrderedDict(leaves(pos)), collections.OrderedDict(leaves(neg))
    assert list(da) == list(db)
    diff = [p for p in da if da[p] != db[p]]
    assert len(diff) == 1, ("exactly one leaf of the specification may differ", diff)
    path = diff[0]
    r0 = [i for i, r in enumerate(pos["rooms"]) if r["name"] == pos["request"]["room"]][0]
    if path[0] == "request":
        label = "request." + {"attendees": "attendee"}.get(path[1], path[1])
    else:
        assert path[:2] == ("rooms", r0), path
        label = "room." + path[2]
    assert label == info["field"], (label, info["field"])
    room, nroom = pos["rooms"][r0], neg["rooms"][r0]
    G = gap_of(pos, room)
    (s, e), (ns, ne) = interval(pos["request"]), interval(neg["request"])
    by_id = {x["id"]: x for x in pos["bookings"]}
    mine = people_of(pos["request"])
    if kind == "overlap":
        assert b["overlap"] == [info["neighbour"]], b
        nb = by_id[info["neighbour"]]
        if var["side"] == "prev":                            # the positive keeps exactly the gap (plus `inside`), the negative is short of it
            assert mm(nb["end"]) + G + inside == s and mm(nb["end"]) + G - ns == delta - inside > 0
        else:
            assert e + G + inside == mm(nb["start"]) and ne + G - mm(nb["start"]) == delta - inside > 0
    elif kind == "hours":
        assert len(b["hours"]) == 1 and b["hours"][0][1] == delta - inside > 0, b
        assert (s == mm(room["open"]) + inside) if var["side"] == "open" else (e == mm(room["close"]) - inside)
        assert b["hours"][0][0] == ("start" if var["side"] == "open" else "end")
    elif kind == "seats":
        assert b["seats"] == [1] and len(mine) == room["seats"] == nroom["seats"] + 1
    elif kind == "equipment":
        assert len(b["equipment"]) == 1
    else:
        assert b["person"] == [[info["conflict_person"], info["conflict_booking"]]], b
        cb = by_id[info["conflict_booking"]]
        assert cb["room"] != pos["request"]["room"] and info["conflict_person"] in cb["attendees"]
        assert min(ne, mm(cb["end"])) - max(ns, mm(cb["start"])) == delta
        touching = [x for x in pos["bookings"] if pos["request"]["day"] in x["days"] and x["room"] != pos["request"]["room"]
                    and info["pivot"] in people_of(x) and (mm(x["end"]) == s or mm(x["start"]) == e)]
        assert touching, "the positive of a person pair has an attendee whose other booking touches the request"
        assert features(neg)["attendee_meeting_touches"] >= 1, "the negative of a person pair shows a touching booking too"
    fa, fb = features(pos), features(neg)
    if kind == "overlap" and not inside:
        assert fa["room_neighbour_exact"] >= 1
    if (s, e) == (ns, ne) and kind != "hours":
        assert fa["room_neighbour_exact"] + fa["starts_at_opening"] + fa["ends_at_closing"] >= 1
    for f in (fa, fb):                                       # a booking in another room during the request (level 1: or the other room is closed then)
        assert f["other_room_same_time"] >= 1 or (L == 1 and f["other_room_closed"] >= 1), f
    rt = info["route"]
    assert rt["rule"] == kind and rt["needs_booking_list"] == (kind not in CHEAP)
    if kind == "overlap":                                    # decided by the reset gap alone exactly when the planted minutes do not exceed the gap
        assert rt["gap_only"] == (delta - inside <= G) and rt["reset_gap_minutes"] == G
    if kind in ("overlap", "person"):
        dbk = by_id[rt["booking"]]
        assert rt["repeating"] == (len(dbk["days"]) > 1) and pos["request"]["day"] in dbk["days"]
        assert rt["request_day_not_first_listed"] == (len(dbk["days"]) > 1 and dbk["days"][0] != pos["request"]["day"])
    else:
        assert rt["booking"] is None and not rt["repeating"] and not rt["gap_only"]
    if L >= 2 and kind != "hours" and info["placing"] in ("open", "close"):          # the decoy at the limit stands in BOTH members
        key = "starts_at_opening" if info["placing"] == "open" else "ends_at_closing"
        assert fa[key] == 1 and fb[key] == 1, (info["placing"], fa, fb)
    if L >= 2 and kind == "equipment":
        assert len(pos["request"]["needs"]) >= 2
    if L == 3 and kind == "hours":                           # needs the computed end and the closing time of the room
        assert b["hours"][0][0] == "end"
    if L == 3:
        assert fa["same_room_other_day"] >= 1 and fb["same_room_other_day"] >= 1
        assert fa["attendee_busy_other_day"] >= 1 and fb["attendee_busy_other_day"] >= 1
        assert 3 <= sum(1 for x in pos["bookings"] if len(x["days"]) > 1) <= 8
    assert ROOMS[L][0] <= len(pos["rooms"]) <= ROOMS[L][1] and BOOKINGS[L][0] <= len(pos["bookings"]) <= BOOKINGS[L][1]
    assert ATTENDEES[L][0] <= len(pos["request"]["attendees"]) <= ATTENDEES[L][1]
    assert len(pos["days"]) == (1 if L < 3 else len(pos["days"])) and (L < 3 or 2 <= len(pos["days"]) <= 3)
    return fa, fb


# --------------------------------------------------------------------------------------------------- rendering
def make_look(rng, P):
    L = P["level"]
    order = list(RULES_BY_LEVEL[L])
    rng.shuffle(order)
    return collections.OrderedDict([
        ("layout", P["layout"]), ("title_style", rng.randrange(len(TITLE_STYLES))),
        ("titles", collections.OrderedDict((k, rng.randrange(3)) for k in ("rooms", "gaps", "rules", "bookings", "request"))),
        ("intro", rng.randrange(3)), ("fixed", rng.randrange(3)), ("rule_order", order),
        ("rule_variant", collections.OrderedDict((r, rng.randrange(3)) for r in RULES_BY_LEVEL[L])),
        ("rule_format", rng.choice(["bullets", "numbers", "paragraph"])), ("sections", rng.randrange(len(SECTION_ORDERS)))])


def cap(w):
    return w[0].upper() + w[1:]


def render(spec, look):
    dom, L, lay = DOMAINS[spec["domain"]], spec["level"], look["layout"]
    V = {k: dom[k] for k in ("org", "att", "atts", "seat", "seats", "event", "events", "rooms_noun")}
    rq, B = spec["request"], spec["bookings"]

    def title(key):
        t = TITLES[key][look["titles"][key]]
        return TITLE_STYLES[look["title_style"]].format(t=t, T=t.upper())

    hours = lambda r: "%s-%s" % (r["open"], r["close"])
    rooms = [title("rooms")]
    if lay == "table":
        rooms.append(" | ".join(["room"] + (["kind"] if L == 3 else []) + [V["seats"]] + (["equipment"] if L >= 2 else []) + ["open"]))
        for r in spec["rooms"]:
            rooms.append(" | ".join([r["name"]] + ([r["kind"]] if L == 3 else []) + [str(r["seats"])]
                                    + ([", ".join(r["equipment"])] if L >= 2 else []) + [hours(r)]))
    elif lay == "records":
        for r in spec["rooms"]:
            parts = ([f"kind {r['kind']}"] if L == 3 else []) + [f"{V['seats']} {r['seats']}"] \
                + ([f"equipment {', '.join(r['equipment'])}"] if L >= 2 else []) + [f"open {hours(r)}"]
            rooms.append(f"- {r['name']}: " + "; ".join(parts))
    else:
        for r in spec["rooms"]:
            parts = [f"{r['seats']} {V['seats']}", f"open {hours(r)}"] + ([f"equipment: {', '.join(r['equipment'])}"] if L >= 2 else [])
            rooms.append((f"{r['name']} ({r['kind']})" if L == 3 else r["name"]) + ": " + "; ".join(parts) + ".")
    if L == 3:
        bk = spec["gap"]["by_kind"]
        rooms += ["", title("gaps")]
        if lay == "table":
            rooms += ["kind | reset gap"] + [f"{k} | {g} min" for k, g in bk.items()]
        elif lay == "records":
            rooms += [f"- {k}: reset gap {g} min" for k, g in bk.items()]
        else:
            rooms.append("; ".join(f"{k} {g} min" for k, g in bk.items()) + ".")

    day = lambda b: "/".join(b["days"])
    span = lambda b: "%s-%s" % (b["start"], b["end"])
    books = [title("bookings")]
    if lay == "table":
        books.append(f"id | room | day | time | {V['org']} | {V['atts']}")
        books += [" | ".join([b["id"], b["room"], day(b), span(b), b["organiser"], ", ".join(b["attendees"])]) for b in B]
    elif lay == "records":
        books += [f"- {b['id']}: room {b['room']}; day {day(b)}; time {span(b)}; {V['org']} {b['organiser']}; {V['atts']} {', '.join(b['attendees'])}" for b in B]
    else:
        books += [f"{b['id']}. {b['room']}, {day(b)}, {span(b)}. {cap(V['org'])}: {b['organiser']}. {cap(V['atts'])}: {', '.join(b['attendees'])}." for b in B]

    when = [("start", rq["start"]), ("end", rq["end"])] if L == 1 else [("start", rq["start"]), ("duration", "%d min" % rq["duration"])]
    cells = [("room", rq["room"]), ("day", rq["day"])] + when + [(V["org"], rq["organiser"]), (V["atts"], ", ".join(rq["attendees"]))]
    if L >= 2:
        cells.append(("needs", ", ".join(rq["needs"])))
    req = [title("request")]
    if lay == "table":
        req += [" | ".join(k for k, _ in cells), " | ".join(v for _, v in cells)]
    elif lay == "records":
        req += [f"- {k}: {v}" for k, v in cells]
    else:
        line = f"{rq['room']}, {rq['day']}, {when[0][0]} {when[0][1]}, {when[1][0]} {when[1][1]}. {cap(V['org'])}: {rq['organiser']}. {cap(V['atts'])}: {', '.join(rq['attendees'])}."
        req.append(line + (f" Needs: {', '.join(rq['needs'])}." if L >= 2 else ""))

    sentences = [RULE_TEXT[r][look["rule_variant"][r]].format(G=spec["gap"].get("minutes"), **V) for r in look["rule_order"]]
    rules = [title("rules")]
    if look["rule_format"] == "bullets":
        rules += ["- " + x for x in sentences]
    elif look["rule_format"] == "numbers":
        rules += ["%d. %s" % (i + 1, x) for i, x in enumerate(sentences)]
    else:
        rules.append(" ".join(sentences))
    intro = [INTRO[look["intro"]].format(site=spec["site"], **V) + " " + FIXED[look["fixed"]]]
    sec = {"intro": intro, "rooms": rooms, "rules": rules, "bookings": books, "request": req}
    return "\n\n".join("\n".join(sec[k]) for k in SECTION_ORDERS[look["sections"]])


# ------------------------------------------------------------------------------------------ checks on the whole set
TOKEN = re.compile(r"[a-z]+")


def best_threshold(xs, ys):
    order = sorted(zip(xs, ys))
    n, pos = len(order), sum(ys)
    best, left, i = max(pos, n - pos) / n, 0, 0
    while i < n:
        j = i
        while j < n and order[j][0] == order[i][0]:
            left += order[j][1]
            j += 1
        a = (j - left) + (pos - left)
        best = max(best, a / n, (n - a) / n)
        i = j
    return best


def vocabulary_test(rows, min_freq=20, max_ratio=2.0):
    """no word that occurs in at least min_freq states may be more than max_ratio times as frequent in one class as in the other"""
    cnt = {"yes": collections.Counter(), "no": collections.Counter()}
    for r in rows:
        cnt[r["gold"]].update(set(TOKEN.findall(r["state"].lower())))
    n = {g: sum(1 for r in rows if r["gold"] == g) for g in cnt}
    worst, tested = (1.0, ""), 0
    for w in sorted(set(cnt["yes"]) | set(cnt["no"])):
        a, b = cnt["yes"][w], cnt["no"][w]
        if a + b < min_freq:
            continue
        tested += 1
        ra, rb = a / n["yes"], b / n["no"]
        ratio = max(ra, rb) / min(ra, rb) if min(ra, rb) > 0 else float("inf")
        if ratio > worst[0]:
            worst = (ratio, w)
    assert worst[0] <= max_ratio, ("a word marks a class", worst)
    return tested, worst


def assign_orders(rows):
    """exactly half of the yes rows and half of the no rows of every level list `yes` first (drawn, recorded in meta.order)"""
    for level in (1, 2, 3):
        for gold in ("yes", "no"):
            idx = [i for i, r in enumerate(rows) if r["gold"] == gold and r["meta"]["level"] == level]
            flags = [True] * (len(idx) // 2) + [False] * (len(idx) - len(idx) // 2)
            rng_for("options", level, gold).shuffle(flags)
            for i, yes_first in zip(idx, flags):
                order = ["yes", "no"] if yes_first else ["no", "yes"]
                rows[i]["questions"]["q"]["criteria"] = collections.OrderedDict((k, OPTIONS[k]) for k in order)
                rows[i]["meta"]["order"] = order


def main():
    plan = make_plan()
    built, attempts = [], []
    for g, P in enumerate(plan, 1):
        for attempt in range(600):
            rng = rng_for("pair", g, attempt)
            try:
                pos, neg, info = build_pair(rng, P)
            except Reject:
                continue
            break
        else:
            raise RuntimeError("pair %d (%s, level %d) cannot be built" % (g, P["kind"], P["level"]))
        attempts.append(attempt + 1)
        fa, fb = check_pair(P, pos, neg, info)
        look = make_look(rng, P)
        ta, tb = render(pos, look), render(neg, look)
        la, lb = ta.split("\n"), tb.split("\n")
        assert len(la) == len(lb) and sum(1 for x, y in zip(la, lb) if x != y) == 1, "the two states differ in exactly one line"
        assert abs(len(ta) - len(tb)) <= 12, (len(ta), len(tb))
        swap = rng.random() < 0.5                             # which member is called a / b: drawn, says nothing about the class
        for spec, text, feat, positive in ((pos, ta, fa, True), (neg, tb, fb, False)):
            ev = analyse(spec)
            meta = collections.OrderedDict([
                ("source_id", "g%04d%s" % (g, "ab"[positive == swap])), ("level", P["level"]), ("domain", P["domain"]),
                ("deviation", None if positive else P["kind"]), ("order", None), ("pair_deviation", P["kind"]),
                ("field", info["field"]), ("variant", P["variant"]), ("layout", P["layout"]), ("listing", info["sort"]),
                ("rooms", len(spec["rooms"])), ("bookings", len(spec["bookings"])), ("days", len(spec["days"])),
                ("attendees", len(spec["request"]["attendees"])), ("evidence", collections.OrderedDict((k, v) for k, v in ev.items() if v)),
                ("route", info["route"]), ("features", feat), ("look", look), ("spec", spec)])
            if SEALED:
                meta["seed"] = SEED
            built.append({"state": text, "gold": "yes" if positive else "no", "group": "%sg%04d" % (ID_PREFIX, g), "meta": meta})
    rng_for("items").shuffle(built)
    rows = []
    for n, x in enumerate(built, 1):
        rows.append(collections.OrderedDict([
            ("id", "%s%05d" % (ID_PREFIX, n)), ("state", x["state"]),
            ("questions", {"q": collections.OrderedDict([("type", "choice"), ("instructions", INSTRUCTIONS), ("criteria", None)])}),
            ("gold", x["gold"]), ("soft", None), ("group", x["group"]), ("meta", x["meta"])]))
    assign_orders(rows)

    # ---- the whole set
    assert len(rows) == 600 and len(set(r["id"] for r in rows)) == 600 and len(set(r["state"] for r in rows)) == 600, "600 distinct states"
    C = collections.Counter
    assert C(r["gold"] for r in rows) == {"yes": 300, "no": 300}
    assert C((r["meta"]["level"], r["gold"]) for r in rows) == {(l, g): 100 for l in (1, 2, 3) for g in ("yes", "no")}
    dev = C((r["meta"]["level"], r["meta"]["deviation"]) for r in rows if r["gold"] == "no")
    assert dev == {(l, k): n for l in (1, 2, 3) for k, n in zip(LEVEL_KINDS[l], LEVEL_COUNTS[l])}, dev
    assert all(r["meta"]["deviation"] is None for r in rows if r["gold"] == "yes")
    first = C((r["meta"]["level"], r["gold"], r["meta"]["order"][0]) for r in rows)
    assert all(first[(l, g, k)] == 50 for l in (1, 2, 3) for g in ("yes", "no") for k in ("yes", "no")), first
    groups = collections.defaultdict(list)
    for r in rows:
        groups[r["group"]].append(r)
        assert truth(r["meta"]["spec"]) == (r["gold"] == "yes")
        assert list(r["questions"]["q"]["criteria"]) == r["meta"]["order"] and r["questions"]["q"]["instructions"] == INSTRUCTIONS
        assert 600 <= len(r["state"]) <= 14000, len(r["state"])
    assert len(groups) == 300
    for members in groups.values():
        assert sorted(m["gold"] for m in members) == ["no", "yes"]
        assert members[0]["state"].count("\n") == members[1]["state"].count("\n")
    assert len(set(r["meta"]["domain"] for r in rows)) == len(DOMAINS)
    ys = [r["gold"] == "yes" for r in rows]
    t_len = best_threshold([len(r["state"]) for r in rows], ys)
    t_lines = best_threshold([r["state"].count("\n") + 1 for r in rows], ys)
    assert abs(t_len - 0.5) <= 0.02 and abs(t_lines - 0.5) <= 0.02, (t_len, t_lines)
    tested, worst = vocabulary_test(rows)
    longer = C((len(a["state"]) > len(b["state"])) - (len(a["state"]) < len(b["state"]))
               for a, b in ((sorted(m, key=lambda r: r["gold"])) for m in groups.values()))       # a = no, b = yes

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "items.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    lens = {l: sorted(len(r["state"]) for r in rows if r["meta"]["level"] == l) for l in (1, 2, 3)}
    sloppy = collections.OrderedDict()
    for name, kw in SLOPPY:
        sloppy[name] = [sum(sloppy_answer(r["meta"]["spec"], kw) == (r["gold"] == "yes") for r in rows if r["meta"]["level"] == l) / 200.0
                        for l in (1, 2, 3)]
    task = collections.OrderedDict([
        ("task", TASK), ("layer", "D"),
        ("title", "Generated room calendars: can the requested booking be confirmed as it stands?"),
        ("decision", "whether one requested room booking can be confirmed unchanged, given the rooms, the written booking rules and the "
                     "confirmed bookings (yes), or breaks one of the rules (no)"),
        ("source", collections.OrderedDict([("name", f"generator build/gen_{TASK}.py"), ("url", ""), ("files", []),
                                            ("split", "generated, seed %d%s" % (SEED, " (sealed split, BENCH_SEED)" if SEALED else "")),
                                            ("version", "gen_v4, 2026-10-08: the planted rule is mostly a booking-list check (levels 2 / 3: 70 / 85 % overlap + person, was 40 %); hours, seats and equipment are decoys exactly at their limit in both members; level-3 overlaps mostly inside the reset gap of the room kind, decisive bookings mostly repeating with the request day not listed first")])),
        ("licence", "generated by the benchmark's script (no third-party text)"), ("redistribution", "items included"),
        ("labels", "programmatic"), ("item_source", "generated"), ("metric", "accuracy"), ("chance", 0.5), ("rows", len(rows)),
        ("groups", len(groups)), ("question_type", "choice"), ("options", 2),
        ("skill", "check one booking request against a room calendar: interval arithmetic with reset gaps, opening hours, seat counts, "
                  "equipment lists and the other meetings of every attendee"),
        ("knobs", "level 1-3: rooms 2 / 3-4 / 5-6, booking lines 6-8 / 12-16 / 20-28, days 1 / 1 / 2-3, rules 3 / 5 / 5, reset gap none / one "
                  "value / by kind of room, request as start-end / start + duration, repeating bookings only at level 3, attendees 2-4 / 3-6 / 5-8; "
                  "near miss of 5, 10 or 15 minutes, one seat, one item, one person; planted rule per level (negatives) overlap / person / hours / "
                  "seats / equipment: 34 / 0 / 33 / 33 / 0, 35 / 35 / 10 / 10 / 10, 43 / 42 / 5 / 5 / 5"),
        ("notes", "600 items = 300 contrast pairs (group): the same state with ONE field changed (meta.field: a time of the request, one attendee "
                  "name, the seat number, an opening or closing time, one equipment word); the positive sits exactly on the limit that the negative "
                  "crosses. Every convention is written in the state; meta.spec holds the structured specification, meta.evidence what the request "
                  "breaks, meta.features the near-limit situations and decoys. Item accuracy is the metric; the group allows a pair analysis. "
                  "State length %d to %d characters. gen_v4 fix: reviewers found level 2 / 3 items decided by one cheap sum (start + duration beyond closing "
                  "time, seat count); the planted rule is now mostly overlap (reset gap of the room kind) or person (other room), hours / seats / "
                  "equipment are 15 %% of the negatives at level 3 and 30 %% at level 2 and sit exactly at their limit in the other items." %
                  (min(len(r["state"]) for r in rows), max(len(r["state"]) for r in rows)))])
    with open(os.path.join(OUT_DIR, "task.json"), "w", encoding="utf-8") as f:
        json.dump(task, f, indent=1)
        f.write("\n")
    write_readme(rows, groups, lens, sloppy, t_len, t_lines, tested, worst, longer, attempts)

    print("written:", OUT_DIR, "| seed", SEED)
    print("class x level:", {l: dict(C(r["gold"] for r in rows if r["meta"]["level"] == l)) for l in (1, 2, 3)})
    print("deviation x level:", {l: {k: dev[(l, k)] for k in LEVEL_KINDS[l]} for l in (1, 2, 3)})
    print("changed field x level:", {l: dict(sorted(C(r["meta"]["field"] for r in rows if r["meta"]["level"] == l and r["gold"] == "no").items())) for l in (1, 2, 3)})
    print("state characters min / median / max per level:", {l: (v[0], v[len(v) // 2], v[-1]) for l, v in lens.items()})
    print("best threshold on characters %.3f, on lines %.3f; vocabulary: %d words tested, worst ratio %.2f (%s)" % (t_len, t_lines, tested, worst[0], worst[1]))
    print("negative longer / equal / shorter than its positive:", longer[1], longer[0], longer[-1])
    print("attempts per pair: mean %.1f, max %d" % (sum(attempts) / len(attempts), max(attempts)))
    for name, acc in sloppy.items():
        print("  careless reader %-95s %s" % (name, "  ".join("%.3f" % a for a in acc)))


def fmt_example(r):
    m = r["meta"]
    head = (f"`{r['id']}` (group `{r['group']}`, level {m['level']}, domain {m['domain']}, gold **{r['gold']}**, "
            f"planted kind of the pair `{m['pair_deviation']}`, changed field of the pair `{m['field']}`)")
    why = ("what the request breaks (`meta.evidence`): `" + json.dumps(m["evidence"]) + "`") if r["gold"] == "no" else \
        "the request breaks nothing; in its partner item the field named above is changed"
    opts = "\n".join(f"- `{k}`: {v}" for k, v in r["questions"]["q"]["criteria"].items())
    return "\n".join([head, "", "```", r["state"], "```", "", f"Question: {r['questions']['q']['instructions']}", "", opts, "", why])


def write_readme(rows, groups, lens, sloppy, t_len, t_lines, tested, worst, longer, attempts):
    C = collections.Counter
    neg = [r for r in rows if r["gold"] == "no"]
    dev = C((r["meta"]["level"], r["meta"]["deviation"]) for r in neg)
    fld = C((r["meta"]["level"], r["meta"]["deviation"], r["meta"]["field"]) for r in neg)
    dom = C((r["meta"]["domain"], r["meta"]["level"]) for r in rows)
    lay = C(r["meta"]["layout"] for r in rows)
    feat_names = list(rows[0]["meta"]["features"])
    share = lambda l, g, k: sum(1 for r in rows if r["meta"]["level"] == l and r["gold"] == g and r["meta"]["features"][k] > 0) / 100.0
    ex = [next(r for r in rows if r["meta"]["level"] == l and r["gold"] == g and r["meta"]["pair_deviation"] == k)
          for l, g, k in ((1, "no", "overlap"), (2, "yes", "person"), (3, "no", "person"))]
    kinds_rows = "\n".join(f"| `{k}` | " + " | ".join(str(dev[(l, k)]) if (l, k) in dev else "-" for l in (1, 2, 3)) + f" | {sum(dev[(l, k)] for l in (1, 2, 3))} |"
                           for k in KINDS)
    field_rows = "\n".join(f"| `{k}` | `{f}` | " + " | ".join(str(fld[(l, k, f)]) for l in (1, 2, 3)) + " |"
                           for k in KINDS for f in sorted(set(x[2] for x in fld if x[1] == k)))
    feat_rows = "\n".join(f"| `{k}` | " + " | ".join("%.2f / %.2f" % (share(l, "yes", k), share(l, "no", k)) for l in (1, 2, 3)) + " |" for k in feat_names)
    sloppy_rows = "\n".join(f"| {n} | " + " | ".join("%.3f" % a for a in acc) + " |" for n, acc in sloppy.items())
    dom_rows = "\n".join(f"| `{d}` | " + " | ".join(str(dom[(d, l)]) for l in (1, 2, 3)) + " |" for d in DOMAINS)
    cheap = {l: sum(dev[(l, k)] for k in CHEAP if (l, k) in dev) for l in (1, 2, 3)}
    cheap_row = " | ".join("%d %%" % cheap[l] for l in (1, 2, 3))
    cheap_acc = " | ".join("%.3f" % sloppy[CHEAP_READER][l - 1] for l in (1, 2, 3))
    routes = {l: [r["meta"]["route"] for r in neg if r["meta"]["level"] == l and r["meta"]["route"]["needs_booking_list"]] for l in (1, 2, 3)}
    ovr = {l: [x for x in routes[l] if x["rule"] == "overlap"] for l in (1, 2, 3)}
    gap_row = " | ".join("-" if l == 1 else "%d %% (%d of %d)" % (round(100.0 * sum(x["gap_only"] for x in ovr[l]) / len(ovr[l])), sum(x["gap_only"] for x in ovr[l]), len(ovr[l]))
                         for l in (1, 2, 3))
    rep_row = " | ".join("-" if l < 3 else "%d %%" % round(100.0 * sum(x["repeating"] for x in routes[l]) / len(routes[l])) for l in (1, 2, 3))
    later_row = " | ".join("-" if l < 3 else "%d %%" % round(100.0 * sum(x["request_day_not_first_listed"] for x in routes[l]) / len(routes[l]))
                           for l in (1, 2, 3))
    seed_note = f" This copy was built with BENCH_SEED={SEED} (sealed split; ids carry `s{SEED}`)." if SEALED else ""
    txt = f"""# {TASK}

Generated room calendars: can the requested booking be confirmed as it stands? (layer D, generated, programmatic truth)

- Decision: one booking request is checked against the rooms, the written rules and the confirmed bookings; `yes` = it breaks
  nothing and can be confirmed unchanged, `no` = it breaks exactly one planted rule.
- Source: generator `build/gen_{TASK}.py` (Python 3.9, standard library only, no argument; root `random.Random({SEED})`, every
  other generator derived from it; two runs give identical files).{seed_note} No third-party text; all names are built from syllables.
- Rows: {len(rows)} in {len(groups)} contrast pairs (`group`), 300 yes / 300 no, 200 per level; metric accuracy (chance 0.5).
- Rebuild: `python3 build/gen_{TASK}.py` (optional `BENCH_OUT=<dir>`; `BENCH_SEED=<int>` only together with `BENCH_OUT`).

## What is generated

The state is one text with five parts (their order is drawn per pair from three orders): an opening line, the rooms, the rules,
the confirmed bookings and the request. Three layouts (`meta.layout`: table {lay['table']}, records {lay['records']}, lines {lay['lines']} items),
three phrasings of every rule sentence, title and opening sentence, rules as bullets / numbered / one paragraph, rule order
shuffled, five domains with their own words for organiser, attendees, seats and equipment (`meta.domain`), room names as
invented words or codes, booking ids as `B01` or `#214`, list sorted by time, by room or unsorted (`meta.listing`).

Formats that never change: times `HH:MM` (24-hour clock, multiples of 5 minutes), ranges `HH:MM-HH:MM`, durations `N min`,
days `Mon` .. `Fri`, a repeating booking `Mon/Thu`, people `Given Family` separated by `, `, equipment items separated by `, `.
The request gives `start` and `end` at level 1 and `start` and `duration` at levels 2 and 3.

## Conventions (all of them are written in every state that needs them)

| rule | wording in the state (one of three phrasings) | level |
|---|---|---|
| room, touching | two bookings of one room may touch but not overlap | 1 |
| room, reset gap | after a booking the room is blocked for G minutes; the next one may start exactly G minutes later; no gap at opening / closing time. G is one number in the rule (level 2) or listed per kind of room (level 3; a kind may have 0 min) | 2, 3 |
| people | organiser and attendees are busy for the whole booking; nobody is in two bookings that overlap on the same day, whatever the rooms; touching is fine for people, the gap is for rooms only | 2, 3 |
| full names | only identical full names are the same person | 2, 3 |
| hours | inside the opening hours of the room; start at opening time and end at closing time allowed | 1, 2, 3 |
| seats | attendees + 1 for the organiser (never repeated in the attendee list) <= seats; a full room is allowed | 1, 2, 3 |
| equipment | the requested room itself has every needed item, exact names | 2, 3 |
| duration | end = start + duration | 2, 3 |
| repeating | a day field with slashes means the booking exists on each listed day (same room, time, people) | 3 |
| days | bookings on different days never clash | 3 |

At level 1 the people rule is not stated; the script still guarantees that nobody of the request is in an overlapping booking,
so a reader who assumes that rule gets the same answer. The confirmed bookings respect every rule among themselves in both members.

## Levels

| level | rooms | booking lines | days | rules that can be broken | request | reset gap | attendees |
|---|---|---|---|---|---|---|---|
| 1 | 2 | 6-8 | 1 | overlap, hours, seats | start, end | none (touching allowed) | 2-4 |
| 2 | 3-4 | 12-16 | 1 | overlap, person, seats, hours, equipment | start, duration | one value for all rooms | 3-6 |
| 3 | 5-6 | 20-28 (3-8 of them repeating) | 2-3 | the same five | start, duration | by kind of room | 5-8 |

State length in characters (min / median / max): level 1 {lens[1][0]} / {lens[1][100]} / {lens[1][-1]}, level 2 {lens[2][0]} / {lens[2][100]} / {lens[2][-1]},
level 3 {lens[3][0]} / {lens[3][100]} / {lens[3][-1]}.

**What makes level 3 hard.** A yes needs all of these, a no needs the one that fails, and nothing marks which one:
1. end of the request = start + duration;
2. the kind of the requested room (room list) and the reset gap of that kind (list of gaps);
3. the bookings of that room on that day, including repeating ones whose day field only contains the day among others
   (`Mon/Thu` is a booking on Thursday too), and excluding bookings of the same room at the same clock time on other days
   (present in every level-3 item);
4. for each neighbour: its end + gap <= start of the request, or end of the request + gap <= its start (the positive of an
   `overlap` pair keeps exactly the gap; the negative is 5-15 minutes inside the gap or inside the booking);
5. for each of the 6-9 people of the request: every booking of that day that names them, in the 4-5 other rooms (touching ones
   are fine, a same-time booking on another day is fine, a namesake is another person);
6. opening hours of the room against start and computed end, seats against the count of names plus one, each needed item
   against the equipment list of that one room.
Steps 1, 2 and 4 alone are four operations on facts from four places (request, room list, gap list, booking lines).

**Which check decides (gen_v4).** The reviewers' complaint was that the decisive check was too often one cheap sum on the request
line (start + duration beyond closing time) or the seat count, so that the booking list did not matter. Target shares of the
planted rule among the negatives (and so the accuracy of a reader who checks only hours, seats and equipment and otherwise says
yes: 0.5 + 0.5 x cheap share), and what the items measure:

| negatives per level | level 1 | level 2 | level 3 |
|---|---|---|---|
| target: planted rule needs the booking list (`overlap`, `person`) | 34 % (unchanged, easy level) | 70 % | 85 % |
| target: planted rule is a cheap check (`hours`, `seats`, `equipment`) | 66 % | 30 % | 15 % |
| measured: negatives decided by a cheap check | {cheap_row} |
| measured: accuracy of the cheap-checks-only reader (table below) | {cheap_acc} |
| measured: `overlap` negatives that lie inside the reset gap only (the request does not touch the neighbour's own time) | {gap_row} |
| measured: `overlap` / `person` negatives whose decisive booking is a repeating one | {rep_row} |
| measured: ... and the day of the request is NOT the first day of its day field | {later_row} |

Level 3 in detail: `overlap` 43, `person` 42, `hours` 5, `seats` 5, `equipment` 5 negatives; level 2: 35 / 35 / 10 / 10 / 10. About 90 %
of the planted overlaps lie in the reset gap of the room kind (the gap list decides, a reader who ignores the gap says yes) and
the neighbour or the conflicting booking is a repeating booking in about 80 % of the items (a reader who reads only the first
day of the day field misses about two thirds of the decisive bookings). The cheap negatives that remain at level 3 are the
ones that need a computation over several facts: `hours` always crosses the closing time through start + duration (or a
closing time moved 15 minutes), `seats` needs a count of 5-8 attendee names plus the organiser against the room, `equipment` needs 2-3
items against the list of one room. In all other items hours, seats and equipment are decoys exactly at their limit: the
requested room is exactly full in about 80 % of them, has exactly the needed equipment in about 70 %, and the request starts
at opening time / ends at closing time in both members wherever the changed field leaves that edge alone (about a quarter of
the items; where the whole request shifts the limit would stay in one member only and would mark a class, so a neighbour of the
room exactly at the gap is the decoy there).

## Deviation kinds (negatives; the positive of the pair is the same state without the change)

| `meta.deviation` | level 1 | level 2 | level 3 | all |
|---|---|---|---|---|
{kinds_rows}

- `overlap`: a time of the request is moved by 5, 10 or 15 minutes into the neighbouring booking of the room or into its reset gap
  (levels 2 and 3: in about 90 % of the items into the reset gap only, so that the minutes of the gap decide; level 3: the gap is the
  one listed for the kind of the requested room, and the neighbour is a repeating booking in about 80 % of the items).
- `person`: one attendee name is replaced by a person who is in a booking of another room that overlaps the request by 5-15 minutes
  (the replaced person has a booking that only touches the request), or a time of the request is moved by 5-15 minutes into
  a booking that one attendee has in another room. The conflicting person is always in the attendee list of that booking.
- `seats`: the seat number of the requested room is one less than organiser + attendees (positive: exactly equal).
- `hours`: a time of the request is moved 5-15 minutes before opening / after closing time, or the opening / closing time
  of the room is moved by 15 minutes (positive: starts exactly at opening time or ends exactly at closing time). Level 3: only
  the closing side (the end is start + duration, or the closing time is moved 15 minutes earlier), 5 negatives.
- `equipment`: one needed item is replaced by an item the room does not have, or the needed item in the room's list is
  replaced by another item (the other item exists in another room in both members). Levels 2 and 3: the request needs 2-3 items.

The one changed field (`meta.field`), negatives per level 1 / 2 / 3:

| kind | field | level 1 | level 2 | level 3 |
|---|---|---|---|---|
{field_rows}

Domains (items per level 1 / 2 / 3):

| domain | level 1 | level 2 | level 3 |
|---|---|---|---|
{dom_rows}

## Near-limit situations and decoys (share of items that have at least one; yes / no)

| `meta.features` | level 1 | level 2 | level 3 |
|---|---|---|---|
{feat_rows}

`room_neighbour_exact` = a booking of the requested room keeps exactly the gap to the request (touches it at level 1);
`attendee_meeting_touches` = somebody of the request has a booking in another room that ends when the request starts or starts
when it ends; `other_room_same_time` = a booking in another room during the request; `namesake_same_time` = that booking holds a
person who shares only the first or only the family name with somebody of the request; `same_room_other_day` /
`attendee_busy_other_day` = a booking of the requested room / of somebody of the request at the clock time of the request on
another day; `other_room_*` = another room is too small, closed at that time, or lacks a needed item. All of them are part of
the shared state, so they occur in both classes (small differences come from pairs whose changed field is a time).
The one larger difference is `room_neighbour_exact`: the positive of an `overlap` pair sits ON the gap of its planted neighbour and
its negative, whose time moved, cannot (levels 2 / 3: 43 and 35 of the pairs). Decoys that are exact for the negative only (the
neighbour at exactly the gap of the moved time, in the `person` pairs with a shifted time) and decoys exact in both members (the
start of an `overlap` pair that changes the duration, the unchanged times of the other pairs) compensate part of it; the
hours limit (`starts_at_opening`, `ends_at_closing`), the full room and the exact equipment are equal in the two classes up to
the pairs whose planted rule is that very check.

How far a careless reader gets (accuracy per level 1 / 2 / 3; each row switches ONE convention off, computed on the specification):

| reading | level 1 | level 2 | level 3 |
|---|---|---|---|
{sloppy_rows}

## Checks made by the script (it stops on the first failure)

- per pair: the confirmed bookings respect every rule among themselves (rooms with the gap, people, hours, seats); the positive
  breaks no rule; the negative breaks exactly the planted rule and nothing else - exactly one neighbour (the planted one, by the
  planted number of minutes), exactly one (person, booking) with an overlap of the planted minutes in another room and in an
  attendee list, exactly one seat, exactly one item, exactly the planted minutes outside the hours; the positive sits on that
  limit (gap kept exactly, room exactly full, start at opening / end at closing, the other booking touches);
- per pair (gen_v4): the route of the planted rule (`meta.route`: rule, decisive booking, repeating or not, day of the request not the
  first listed day, inside the reset gap only) is recomputed from the two specifications and must agree with the draw; a decoy
  placed at opening / closing time stands in both members; an `equipment` pair needs at least two items;
- per pair: exactly one leaf of the two specifications differs and it is the planted field; the two texts have the same number
  of lines and differ in exactly one line; their lengths differ by at most 12 characters (negative longer / equal / shorter:
  {longer[1]} / {longer[0]} / {longer[-1]} pairs);
- every level-3 item has a booking of the requested room and a booking of somebody of the request at the same clock time on
  another day; every item has a booking in another room during the request; everybody of the request occurs in a confirmed booking;
- whole set: 600 distinct states, 300 / 300, 100 / 100 inside every level, the kinds as in the table, `yes` listed first in
  exactly half of the yes rows and half of the no rows of every level, truth recomputed from `meta.spec` for every row;
- no word occurring in at least 20 states is more than twice as frequent in one class ({tested} words tested, worst ratio
  {worst[0]:.2f}); best single threshold on the number of characters {t_len:.3f} and on the number of lines {t_lines:.3f}.

Random draws that cannot be completed (no free room for a planted booking, and so on) are drawn again with the next derived
generator: {sum(attempts) / len(attempts):.1f} draws per pair on average, at most {max(attempts)}.

## Examples (one per level)

""" + "\n\n".join(f"### Level {r['meta']['level']}\n\n" + fmt_example(r) for r in ex) + """

## Independence

This generator was written from scratch for the benchmark. It shares no template, no sentence, no name list and no item
layout with the generators the authors use for training data, and none of its sentences is taken from benchmark v0 or from
a published data set. Evaluation only.
"""
    with open(os.path.join(OUT_DIR, "README.md"), "w", encoding="utf-8") as f:
        f.write(txt)


if __name__ == "__main__":
    main()
