"""Task log_count_check (layer C, generated, programmatic truth): "is the claim correct for this log?"

Item design.  The state is an event log of one day (30, 60 or 90 lines; each line "time service level code", times
strictly ascending, 4 to 6 invented services, levels INFO / WARN / ERROR) and a claim of the form
    "svc-kelta logged 7 ERROR events between 09:00:00 and 11:30:00.  Both end times count."
The claim names a service, a level, a time window (with the rule for the two end times stated in words: both counted,
start counted and end not, or neither counted) and a count.  The gold answer is yes when the log holds exactly that many
such events and no otherwise.  Truth is computed by counting.

Contrast pairs.  600 items = 300 pairs: one log with a true claim (yes) and the same log with the claim changed in ONE
field (no):
  off_by_one  the stated count is the true count + 1 or - 1
  off_by_two  the stated count is the true count + 2 or - 2
  window      the claim names the neighbouring window (shifted by one window length plus a gap) and keeps the stated count,
              which is the count of the window it no longer names
  service     another service is named and the stated count is kept: it is the count of the service no longer named
The log is the same in both members of a pair, so length, vocabulary and structure cannot tell them apart.

The stated count is no cue (gen_v4).  A `window` or `service` negative states the same count as its positive (only the window or
the service changed); an off-by negative states a count that is 1 or 2 away.  Within EVERY level (30, 60, 90 lines) the stated counts of
the negatives have the same histogram as the true counts of the positives, over the same range (0 to 4, 0 to 8, 0 to 12; an off-by shift
never leaves the range of its level).  So a claim of 0 events is as often true as false, a claim of k > 0 events is as often true as
false, and no table "stated count -> answer" (per level or overall) is better than chance.  The 25 one-step shifts of a level (an odd
number) cannot cancel exactly, so the two histograms of a level differ in ONE pair (L1 distance 2, never in the bin of 0; asserted).
The shifts are found by a maximum bipartite matching of the off-by pairs to the true counts of the off-by pairs of the same level (a pair
is matched to the true count it will state; see match_shifts).  Measured and asserted by count_cue_probe.
Number agreement.  The noun after the count is singular for 1 and plural otherwise, in every phrasing ("1 ERROR event", "exactly 1 ERROR
entry", "there was 1 ERROR line"; "0 ERROR events"); the text check parses both forms and asserts the agreement.

Four planted cells.  Besides the claimed cell (claimed service, level and window) every log holds the cell the `window`
negative points to (same service and level, neighbouring window), the cell the `service` negative points to (other service,
claimed window) and a fourth cell (other service, neighbouring window), with counts that differ from the true count by 1 to 4.
All four cells get the same structure, whatever the deviation: events of the cell just outside its window (1 to 240 seconds),
the same distractors in both windows (the service at another level, other services at the same level) and, per window bound with
probability 0.2, an event exactly at the start or the end of the window, where the stated rule for the end times decides whether
it counts.  So the claimed service is not the busiest one, the claimed window is not the busiest one, and a decoy cell cannot be
told from the true one (measured and asserted: structure_probe).

Dials: lines 30, 60, 90 = meta.level 1, 2, 3 (100 pairs each; each deviation kind 25 pairs per level; true counts up to 4, 8, 12).
Metadata: meta.level is the difficulty level (1, 2, 3); the severity of the claim (INFO / WARN / ERROR) is meta.log_level; the old dial
field meta.lines (30 / 60 / 90) stays.
Truth twice: ``truth(spec)`` counts on the structured events; ``check(item)`` parses the rendered log lines (four line
layouts) and the rendered claim (five phrasings, singular and plural nouns, twelve wordings of the rule for the end times) and counts again.
    python3 generators/log_count_check.py
"""
import collections
import json
import os
import random
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repository root (this file is generators/<family>.py)
HERE = os.path.join(REPO, "generated")                               # the items are written to HERE/tasks/<family>/
AUDITS = os.path.join(REPO, "audits")                                # validate.py and audit.py, run on HERE/tasks/<family>/
SEED = 20261007
TASK = "log_count_check"
PAIRS = 300
LEVELS = ["INFO", "WARN", "ERROR"]
CAP = {30: 4, 60: 8, 90: 12}                       # largest true count per log length (the log must keep room for four planted cells)
STATED_MAX = max(CAP.values())
LEVEL_OF = {30: 1, 60: 2, 90: 3}                   # difficulty level (meta.level) of a log length (meta.lines)
KINDS = ["off_by_one", "off_by_two", "window", "service"]
SHIFT = {"off_by_one": 1, "off_by_two": 2}         # change of the stated count of the off-by negatives
INSTRUCTIONS = "Is the claim correct for this log?"
OPTIONS = {"yes": "The claim is correct for this log.", "no": "The claim is not correct for this log."}


def rng_for(*parts):
    return random.Random(":".join(str(p) for p in (SEED, TASK) + parts))


# ---------------------------------------------------------------------------------------------------- invented names
START = ["Kel", "Vor", "Tal", "Mar", "Dra", "Sen", "Ori", "Quil", "Bar", "Hal", "Jor", "Lum", "Nor", "Pel", "Ryn", "Sol",
         "Tev", "Zan", "Fen", "Gar", "Kor", "Mel", "Nim", "Pav", "Rav", "Sav", "Tor", "Vel", "Wen", "Yar", "Zol", "Bel",
         "Cor", "Dov", "Eld", "Fal", "Gal", "Hes", "Jav", "Kas", "Lor", "Mir", "Nev", "Per", "Ros", "Sul", "Tam", "Ves",
         "Zer", "Ald", "Bran", "Cris", "Dern", "Fran", "Grel", "Hald", "Krin", "Prav", "Stel", "Trel", "Vrin"]
END = ["vane", "mora", "trin", "dex", "wick", "lor", "tis", "ven", "sal", "dar", "kos", "nex", "phel", "quin", "rov", "tan",
       "vik", "zen", "bel", "dor", "fen", "gan", "kar", "lis", "mun", "nor", "pen", "rik", "sel", "tor", "van", "xan",
       "yor", "zim", "dra", "lia", "ria"]
BLOCK = {"barbel", "bellis", "beltis", "corbel", "crissal", "garbel", "marmar", "norsel", "norsk", "origan", "pernor",
         "sensal", "sultan", "tallis", "torsel", "torsk", "trellis", "vessel", "belbel", "korkar", "talvan", "salsal", "trellor"}


def service_name(rng):
    while True:
        w = rng.choice(START).lower() + rng.choice(END)
        if w not in BLOCK:
            return "svc-" + w


CODE_POOL = {"INFO": [f"I{n}" for n in (1001, 1002, 1007, 1010, 1042, 1100, 1207, 1310, 1404, 1512)],
             "WARN": [f"W{n}" for n in (2003, 2010, 2031, 2105, 2210, 2307, 2411, 2520)],
             "ERROR": [f"E{n}" for n in (4001, 4012, 4040, 4103, 4290, 5000, 5003, 5021, 5110, 5204)]}

HEADERS = ["Event log for {d} (UTC). One event per line: time, service, level, code.",
           "Service log, {d}, times in UTC. Columns: time service level code.",
           "Log extract of {d}; every line is one event (time, service, level, code); times are UTC and ascending.",
           "Events recorded on {d} (UTC), oldest first. Line format: time service level code."]
LINE_FORMATS = ["{t} {s} {l} {c}", "{t} | {s} | {l} | {c}", "[{t}] {s} {l} {c}", "{t} {s} [{l}] {c}"]
# (template, (singular noun, plural noun)); {w} is the noun that agrees with the count n (singular for 1, plural for 0 and 2 or more),
# {v} the verb of the existential phrasing ("there was 1 ... line", "there were 3 ... lines")
FRAMES = [("{s} logged exactly {n} {l} {w} between {a} and {b}.", ("event", "events")),
          ("Between {a} and {b}, {s} wrote exactly {n} {l} {w}.", ("entry", "entries")),
          ("The log shows exactly {n} {l} {w} from {s} in the window {a} to {b}.", ("event", "events")),
          ("In the period from {a} to {b} there {v} exactly {n} {l} {w} for {s}.", ("line", "lines")),
          ("{s} reported exactly {n} {l} {w} from {a} until {b}.", ("event", "events"))]
BOUNDS = {"both": ["Both end times count.", "Events at exactly {a} or {b} are included.", "The window includes its start and its end.",
                   "Bounds are inclusive."],
          "half": ["The start time counts; the end time does not.", "An event at exactly {a} is included, an event at exactly {b} is not.",
                   "The window includes its start but not its end.", "Bounds are half-open: start included, end excluded."],
          "none": ["Neither end time counts.", "Events at exactly {a} or {b} are not included.",
                   "The window excludes its start and its end.", "Bounds are exclusive."]}


def hms(sec):
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def in_window(sec, t1, t2, incl):
    if incl == "both":
        return t1 <= sec <= t2
    if incl == "half":
        return t1 <= sec < t2
    return t1 < sec < t2


# -------------------------------------------------------------------------------------- truth on the specification
def count_events(events, claim):
    return sum(1 for sec, svc, lvl, _ in events
               if svc == claim["service"] and lvl == claim["level"] and in_window(sec, claim["start"], claim["end"], claim["incl"]))


def truth(spec):
    return count_events(spec["events"], spec["claim"]) == spec["claim"]["count"]


# ---------------------------------------------------------- check: the answer from the rendered text alone
T = r"(\d\d:\d\d:\d\d)"
S = r"(svc-[a-z]+)"
L = "(INFO|WARN|ERROR)"
LINE_PATTERNS = [re.compile(p) for p in (rf"{T} {S} {L} ([A-Z]\d{{4}})", rf"{T} \| {S} \| {L} \| ([A-Z]\d{{4}})",
                                         rf"\[{T}\] {S} {L} ([A-Z]\d{{4}})", rf"{T} {S} \[{L}\] ([A-Z]\d{{4}})")]
CLAIM_PATTERNS = [                                  # both number forms are parsed; check() asserts that the form agrees with the count
    rf"(?P<s>{S}) logged exactly (?P<n>\d+) (?P<l>{L}) (?P<w>events?) between (?P<a>{T}) and (?P<b>{T})\.",
    rf"Between (?P<a>{T}) and (?P<b>{T}), (?P<s>{S}) wrote exactly (?P<n>\d+) (?P<l>{L}) (?P<w>entry|entries)\.",
    rf"The log shows exactly (?P<n>\d+) (?P<l>{L}) (?P<w>events?) from (?P<s>{S}) in the window (?P<a>{T}) to (?P<b>{T})\.",
    rf"In the period from (?P<a>{T}) to (?P<b>{T}) there (?P<v>was|were) exactly (?P<n>\d+) (?P<l>{L}) (?P<w>lines?) for (?P<s>{S})\.",
    rf"(?P<s>{S}) reported exactly (?P<n>\d+) (?P<l>{L}) (?P<w>events?) from (?P<a>{T}) until (?P<b>{T})\.",
]
SINGULAR = {"event", "entry", "line"}
BOUND_PATTERNS = [
    ("both", r"Both end times count\."), ("both", rf"Events at exactly (?P<a>{T}) or (?P<b>{T}) are included\."),
    ("both", r"The window includes its start and its end\."), ("both", r"Bounds are inclusive\."),
    ("half", r"The start time counts; the end time does not\."),
    ("half", rf"An event at exactly (?P<a>{T}) is included, an event at exactly (?P<b>{T}) is not\."),
    ("half", r"The window includes its start but not its end\."), ("half", r"Bounds are half-open: start included, end excluded\."),
    ("none", r"Neither end time counts\."), ("none", rf"Events at exactly (?P<a>{T}) or (?P<b>{T}) are not included\."),
    ("none", r"The window excludes its start and its end\."), ("none", r"Bounds are exclusive\."),
]


def secs(t):
    h, m, s = map(int, t.split(":"))
    return h * 3600 + m * 60 + s


def check(item):
    """the answer (True / False) recomputed from the rendered state alone"""
    st = item["state"]
    events, last = [], -1
    for line in st["log"].split("\n")[1:]:
        hits = [m for p in LINE_PATTERNS for m in [p.fullmatch(line)] if m]
        assert len(hits) == 1, f"log line not parsed: {line!r}"
        t, svc, lvl, _ = hits[0].groups()
        assert secs(t) > last, f"times are not ascending at {line!r}"
        last = secs(t)
        events.append((secs(t), svc, lvl))
    first, second = st["claim"].split(". ", 1)[0] + ".", st["claim"].split(". ", 1)[1]
    c = [m.groupdict() for p in CLAIM_PATTERNS for m in [re.fullmatch(p, first)] if m]
    assert len(c) == 1, f"claim not parsed: {first!r}"
    c = c[0]
    assert (c["w"] in SINGULAR) == (int(c["n"]) == 1), f"number agreement: {c['n']} {c['w']} in {first!r}"
    assert c.get("v") is None or (c["v"] == "was") == (int(c["n"]) == 1), f"number agreement: {c['v']} {c['n']} in {first!r}"
    b = [(k, m.groupdict()) for k, p in BOUND_PATTERNS for m in [re.fullmatch(p, second)] if m]
    assert len(b) == 1, f"bounds sentence not parsed: {second!r}"
    incl, g = b[0]
    assert all(g[x] == c[x] for x in g if g[x]), "times of the two sentences differ"
    a, z = secs(c["a"]), secs(c["b"])
    n = sum(1 for sec, svc, lvl in events if svc == c["s"] and lvl == c["l"] and in_window(sec, a, z, incl))
    return n == int(c["n"])


# ------------------------------------------------------------------------------------------------- one pair
def alt_count(rng, c0, cap):
    """count of an alternative reading (neighbouring window, other service): c0 shifted by 1 to 4"""
    for _ in range(100):
        d = rng.choices([1, 2, 3, 4], [0.3, 0.3, 0.2, 0.2])[0] * rng.choice([1, -1])
        if 0 <= c0 + d <= cap:
            return c0 + d
    return c0 + 1 if c0 + 1 <= cap else c0 - 1


def build_log(rng, N, plan):
    """-> (events [(sec, service, level, code)], claim of the positive, claim of the negative, info).

    Four cells are planted in EVERY log, whatever the deviation: (claimed service | other service) x (claimed window | neighbouring
    window) at the claimed level.  The claimed cell holds the true count c0; the cell the `window` negative names and the cell the
    `service` negative names hold c1 (the true count of that negative, 1 to 4 away from c0, while the negative keeps stating c0); the
    other cells hold similar counts (c0 +- 1 to 4).  All four cells get the same
    structure (events of the cell just outside its window, boundary events, the same distractors), so the claimed service is not
    the busiest one, the claimed window is not the busiest one, and a decoy cell cannot be told from the true one."""
    kind, c0, c1, level, incl, cap = plan["kind"], plan["c0"], plan["c1"], plan["level"], plan["incl"], CAP[N]
    n_svc = rng.randint(4, 5 if N == 30 else 6)
    services = []
    while len(services) < n_svc:
        s = service_name(rng)
        if s not in services:
            services.append(s)
    svc, other = services[0], services[1]
    rest_svcs = services[2:]
    lw = rng.choice([45, 60, 75, 90, 120, 150, 180]) * 60
    gap, m0 = 600, 900
    t0 = rng.randrange(6 * 12, 9 * 12) * 300                          # first possible event: 06:00 to 08:55
    end = t0 + m0 + 2 * lw + gap + m0 + rng.choice([0, 1800, 3600, 7200])
    base = t0 + m0
    w_a, w_b = (base, base + lw), (base + lw + gap, base + 2 * lw + gap)
    w0, w1 = (w_a, w_b) if rng.random() < 0.5 else (w_b, w_a)        # w0 = claimed window of the positive, w1 = its neighbour
    counts = {(svc, 0): c0, (svc, 1): c1 if kind == "window" else alt_count(rng, c0, cap),
              (other, 0): c1 if kind == "service" else alt_count(rng, c0, cap), (other, 1): alt_count(rng, c0, cap)}
    windows = (w0, w1)
    used, events = set(), []

    def put(sec, s, lvl):
        assert sec not in used
        used.add(sec)
        events.append((sec, s, lvl))

    def interior(t1, t2, k, s, lvl):
        for sec in rng.sample(range(t1 + 1, t2), k):
            while sec in used:
                sec = rng.randrange(t1 + 1, t2)
            put(sec, s, lvl)

    # room for near misses, distractors and one event per other service (boundary events: at most four more)
    d_near, d_lvl, d_svc = rng.randint(1, 2), rng.randint(1, 1 + N // 45), rng.randint(1, 1 + N // 45)
    fixed = {(svc, 0)} | ({(svc, 1)} if kind == "window" else set()) | ({(other, 0)} if kind == "service" else set())
    free_counts = [k for k in counts if k not in fixed]
    n_dist = lambda: 4 * d_near + 2 * (2 * d_lvl + d_svc) + (n_svc - 2)
    while sum(counts.values()) + 2 + n_dist() > N:
        if d_near > 1:
            d_near -= 1
        elif d_lvl > 1 or d_svc > 1:
            d_lvl, d_svc = (d_lvl - 1, d_svc) if d_lvl > 1 else (d_lvl, d_svc - 1)
        else:
            k = max((k for k in free_counts if counts[k] > 0), key=lambda k: counts[k], default=None)
            if k is None:
                raise RuntimeError("no room")
            counts[k] -= 1
    # boundary events: every bound of a window belongs to one of the two services of the cell pair or to nobody; a bound that
    # would count (as the stated rule says) is only planted when the cell has a count left for it
    owners = {(w, side): rng.choices([svc, other, None], [0.2, 0.2, 0.6])[0] for w in (0, 1) for side in (0, 1)}
    bnd = {}
    for (sv, w), c in counts.items():
        got, left = [], c
        for side in (0, 1):
            if owners[(w, side)] != sv:
                continue
            if (side == 0 and incl in ("both", "half")) or (side == 1 and incl == "both"):
                if left == 0:
                    continue
                left -= 1
            got.append(side)
        bnd[(sv, w)] = got
    # plant the four cells
    for (sv, w), c in counts.items():
        t1, t2 = windows[w]
        counted = 0
        for side in bnd[(sv, w)]:
            put(t1 if side == 0 else t2, sv, level)
            counted += (side == 0 and incl in ("both", "half")) or (side == 1 and incl == "both")
        assert counted <= c
        interior(t1, t2, c - counted, sv, level)
        for _ in range(d_near):                                      # events of the cell just outside its window
            for _ in range(50):
                d = rng.choice([1, 1, 2, 3, 10, 30, 90, 240])
                sec = t1 - d if rng.random() < 0.5 else t2 + d
                if sec not in used:
                    put(sec, sv, level)
                    break
    for t1, t2 in windows:                                           # the same distractors in both windows
        interior(t1, t2, d_lvl, svc, rng.choice([x for x in LEVELS if x != level]))
        interior(t1, t2, d_lvl, other, rng.choice([x for x in LEVELS if x != level]))
        for _ in range(d_svc):
            interior(t1, t2, 1, rng.choice(rest_svcs), level)
    # background events: anywhere, but never inside a cell that must keep its planted count
    weights = [rng.choice([0.5, 0.6, 0.7]), rng.choice([0.2, 0.25, 0.3]), 0.1]
    forbid = [(sv, level, windows[w]) for sv in (svc, other) for w in (0, 1)]

    def allowed(sec, s, lvl):
        return sec not in used and not any(s == fs and lvl == fl and fw[0] <= sec <= fw[1] for fs, fl, fw in forbid)

    seen = collections.Counter(s for _, s, _ in events)
    for s in services:                                               # every service occurs in the log
        while seen[s] < 1:
            sec, lvl = rng.randrange(t0, end + 1), rng.choice(LEVELS)
            if allowed(sec, s, lvl):
                put(sec, s, lvl)
                seen[s] += 1
    if len(events) > N:
        raise RuntimeError("no room")
    while len(events) < N:
        sec, s, lvl = rng.randrange(t0, end + 1), rng.choice(services), rng.choices(LEVELS, weights)[0]
        if allowed(sec, s, lvl):
            put(sec, s, lvl)
    events.sort()
    events = [(sec, s, lvl, rng.choice(CODE_POOL[lvl])) for sec, s, lvl in events]
    pos = {"service": svc, "level": level, "start": w0[0], "end": w0[1], "incl": incl, "count": c0}
    neg = dict(pos, count=plan["s"])                                 # stated count of the negative: c0 (window, service) or c0 +- 1 / 2 (off-by)
    if kind == "window":
        neg["start"], neg["end"] = w1
    elif kind == "service":
        neg["service"] = other
    return events, pos, neg, {"boundary_events": len(bnd[(svc, 0)]), "services": n_svc, "claim_window_seconds": lw}


def render_log(events, date, style, header):
    return "\n".join([HEADERS[header].format(d=date)] + [LINE_FORMATS[style].format(t=hms(sec), s=s, l=l, c=c) for sec, s, l, c in events])


def render_claim(c, frame, bound):
    a, b = hms(c["start"]), hms(c["end"])
    template, (singular, plural) = FRAMES[frame]
    one = c["count"] == 1                                            # number agreement: "1 event" / "0 events" / "3 events"
    return (template.format(s=c["service"], n=c["count"], l=c["level"], a=a, b=b, w=singular if one else plural, v="was" if one else "were")
            + " " + BOUNDS[c["incl"]][bound].format(a=a, b=b))


# --------------------------------------------------------------------------------------------------- the plan
def allowed_stated(c0, kind, cap):
    """the stated counts an off-by negative of this kind can carry: c0 - 1 or c0 + 1 (off_by_one), c0 - 2 or c0 + 2 (off_by_two), always inside
    0..cap, the range of the true counts of the level (no stated count of a negative lies outside the range of the true counts)"""
    d = SHIFT[kind]
    return [v for v in (c0 - d, c0 + d) if 0 <= v <= cap]


def match_shifts(rng, c0s, kinds, cap):
    """One level: the true counts c0s and the kinds of its 100 pairs  ->  the stated counts s of the 100 negatives, or None.

    A `window` / `service` negative states the count of its positive (s = c0): only the window or the service changed.  The 50 off-by
    negatives state c0 +- 1 / c0 +- 2.  The histogram of the stated counts of the level equals the histogram of the true counts when the
    off-by pairs exchange their true counts: pair i states the true count of some off-by pair j, with |c0[j] - c0[i]| the shift of its kind
    (a bipartite matching of the off-by pairs to the true counts of the off-by pairs, augmenting paths).  A PERFECT matching cannot exist:
    25 shifts of one step and 25 of two steps add up to an odd number, never to 0.  The maximum matching leaves one pair unmatched; its
    negative takes another count of its range (not 0 if it can help it), so that the two histograms of the level differ by that one pair
    (L1 distance 2, the minimum).  Randomised (order of the pairs, order of the candidates); None if more than one pair stays unmatched or
    if the unmatched true count is 0 (the bin of the zero claims must be exactly equal): the caller draws again."""
    idx = [i for i, k in enumerate(kinds) if k in SHIFT]
    rng.shuffle(idx)
    slots = collections.defaultdict(list)                           # true count -> the off-by pairs that hold it
    for j in idx:
        slots[c0s[j]].append(j)
    adj = {}
    for i in idx:
        cand = allowed_stated(c0s[i], kinds[i], cap)
        rng.shuffle(cand)
        adj[i] = [j for v in cand for j in slots.get(v, [])]
    owner = {}                                                      # slot j -> the pair i whose negative states the true count of j

    def augment(i, seen):
        for j in adj[i]:
            if j not in seen:
                seen.add(j)
                if j not in owner or augment(owner[j], seen):
                    owner[j] = i
                    return True
        return False

    unmatched = []
    for i in idx:
        if not augment(i, set()):
            unmatched.append(i)
    if len(unmatched) != 1:
        return None
    free_slot = [j for j in idx if j not in owner]
    assert len(free_slot) == 1
    if c0s[free_slot[0]] == 0:
        return None
    s = list(c0s)                                                   # window / service: the count of the positive
    for j, i in owner.items():
        s[i] = c0s[j]
    i = unmatched[0]
    cand = allowed_stated(c0s[i], kinds[i], cap)
    assert c0s[free_slot[0]] not in cand                            # otherwise the matching was not maximal
    s[i] = rng.choice([v for v in cand if v > 0] or cand)
    return s


def make_plan():
    rng = rng_for("plan")
    pairs = []
    levels = ["ERROR"] * 120 + ["WARN"] * 105 + ["INFO"] * 75
    incls = ["both"] * 120 + ["half"] * 105 + ["none"] * 75
    rng.shuffle(levels)
    rng.shuffle(incls)
    for N in (30, 60, 90):
        cap = CAP[N]
        for attempt in range(5000):
            r = rng_for("plan", N, attempt)
            counts = [k % (cap + 1) for k in range(100)]
            kinds = [k for k in KINDS for _ in range(25)]
            r.shuffle(counts)
            r.shuffle(kinds)
            stated = match_shifts(r, counts, kinds, cap)
            if stated is not None:
                break
        else:
            raise RuntimeError(f"no matching of the stated counts for {N} lines")
        pairs += [{"N": N, "c0": counts[k], "kind": kinds[k], "s": stated[k]} for k in range(100)]
    rng.shuffle(pairs)
    for p, lv, inc in zip(pairs, levels, incls):
        p["level"], p["incl"] = lv, inc
        p["c1"] = alt_count(rng, p["c0"], CAP[p["N"]]) if p["kind"] in ("window", "service") else None
    return pairs


def to_item(n, pair, plan, spec, dev, info):
    claim = spec["claim"]
    meta = {"source_id": f"{n:05d}", "level": LEVEL_OF[plan["N"]], "lines": plan["N"], "pair": pair, "deviation": dev or "none",
            "true_count": spec["true_count"], "stated_count": claim["count"], "service": claim["service"],
            "log_level": claim["level"], "rule_for_end_times": claim["incl"],
            "boundary_events": info["boundary_events"], "services": info["services"],
            "window_minutes": (claim["end"] - claim["start"]) // 60, "spec": {"events": [list(e) for e in spec["events"]], "claim": claim}}
    return {"id": f"{TASK}:{n:05d}",
            "state": {"log": spec["log"], "claim": spec["claim_text"]},
            "questions": {"q": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": dict(OPTIONS)}},
            "gold": "no" if dev else "yes", "soft": None, "group": f"{TASK}:pair:{pair:03d}", "meta": meta}


def assign_orders(rows):
    """the order of the two options is drawn per item (exactly half of the positives and half of the negatives list `yes` first),
    recorded in meta.order and frozen in the file"""
    rng = rng_for("options")
    for gold in ("yes", "no"):
        idx = [i for i, r in enumerate(rows) if r["gold"] == gold]
        flags = [True] * (len(idx) // 2) + [False] * (len(idx) - len(idx) // 2)
        rng.shuffle(flags)
        for i, yes_first in zip(idx, flags):
            order = ["yes", "no"] if yes_first else ["no", "yes"]
            rows[i]["questions"]["q"]["criteria"] = {k: OPTIONS[k] for k in order}
            rows[i]["meta"]["order"] = order


# ------------------------------------------------------------------------------------------ vocabulary test
TOKEN = re.compile(r"[a-z0-9]+(?:[-_'][a-z0-9]+)*")


def state_text(item):
    st = item["state"]
    return st if isinstance(st, str) else "\n".join(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for v in st.values())


def vocabulary_test(items, classes, min_freq=20, max_ratio=2.0):
    """no token of frequency >= min_freq may occur in one class at more than max_ratio times the rate of another class"""
    cnt = {c: collections.Counter() for c in classes}
    for it in items:
        cnt[it["_class"]].update(TOKEN.findall(state_text(it).lower()))
    tot = {c: sum(cnt[c].values()) for c in classes}
    worst, tested, bad = (1.0, ""), 0, []
    for tok in sorted(set().union(*cnt.values())):
        if sum(cnt[c][tok] for c in classes) < min_freq:
            continue
        tested += 1
        rate = [cnt[c][tok] / tot[c] for c in classes]
        ratio = max(rate) / min(rate) if min(rate) > 0 else float("inf")
        if ratio > worst[0]:
            worst = (ratio, tok)
        if ratio > max_ratio:
            bad.append((tok, [cnt[c][tok] for c in classes]))
    assert not bad, f"vocabulary cue: {bad[:10]}"
    return tested, worst


def structure_probe(rows):
    """share of items whose claimed service is the busiest service of the log, and mean number of events in the claimed window,
    per class: a shortcut reader could use either; both must be (nearly) equal in the two classes"""
    res = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        ev, cl = r["meta"]["spec"]["events"], r["meta"]["spec"]["claim"]
        tot = collections.Counter(e[1] for e in ev)
        res["busiest"][r["gold"]].append(int(tot[cl["service"]] == max(tot.values())))
        res["window_events"][r["gold"]].append(sum(1 for e in ev if cl["start"] <= e[0] <= cl["end"]))
        res["service_level_events"][r["gold"]].append(sum(1 for e in ev if e[1] == cl["service"] and e[2] == cl["level"]))
    out = {k: {c: sum(x) / len(x) for c, x in v.items()} for k, v in res.items()}
    assert abs(out["busiest"]["yes"] - out["busiest"]["no"]) < 0.08, out
    assert abs(out["window_events"]["yes"] - out["window_events"]["no"]) < 1.5, out
    assert abs(out["service_level_events"]["yes"] - out["service_level_events"]["no"]) < 1.0, out
    return out


def count_cue_probe(rows):
    """what a reader can take from the stated count alone, without the log: for the whole family and per level, the share of true claims among
    the claims of 0 events and among the claims of k > 0 events, the better of the rules 'zero -> yes' / 'zero -> no', and the best table
    'stated count -> majority answer' (fitted on the items themselves, so an upper bound for every rule that reads only the stated count).
    'by_level' is the table that may also read the number of lines of the log (one table per level, over the 600 items).
    Asserted: every rule <= 0.52 and both shares between 0.45 and 0.55 (the design gives 0.50 to 0.505)."""
    def table_hits(items):
        tab = collections.defaultdict(collections.Counter)
        for r in items:
            tab[r["meta"]["stated_count"]][r["gold"]] += 1
        return sum(max(c.values()) for c in tab.values())

    out = {}
    for name, items in [("all", rows)] + [(v, [r for r in rows if r["meta"]["level"] == v]) for v in (1, 2, 3)]:
        z = [r for r in items if r["meta"]["stated_count"] == 0]
        nz = [r for r in items if r["meta"]["stated_count"] > 0]
        zero_yes = sum(1 for r in items if (r["gold"] == "yes") == (r["meta"]["stated_count"] == 0)) / len(items)
        out[name] = {"zero_claims": len(z), "zero_true": sum(r["gold"] == "yes" for r in z),
                     "nonzero_claims": len(nz), "nonzero_true": sum(r["gold"] == "yes" for r in nz),
                     "zero_rule": max(zero_yes, 1 - zero_yes), "table": table_hits(items) / len(items)}
    out["by_level"] = sum(table_hits([r for r in rows if r["meta"]["level"] == v]) for v in (1, 2, 3)) / len(rows)
    for name, o in out.items():
        if name == "by_level":
            assert o <= 0.52, out
            continue
        assert o["zero_rule"] <= 0.52 and o["table"] <= 0.52, (name, o)
        assert 0.45 <= o["zero_true"] / o["zero_claims"] <= 0.55 and 0.45 <= o["nonzero_true"] / o["nonzero_claims"] <= 0.55, (name, o)
    return out


# --------------------------------------------------------------------------------------------------- output
def run_tool(script, *args):
    r = subprocess.run([sys.executable, os.path.join(AUDITS, script), "--root", HERE] + list(args), capture_output=True, text=True, cwd=REPO)
    return r.stdout.strip().split("\n")


def fmt_item(it):
    out = [f"id `{it['id']}` (pair `{it['group']}`, gold **{it['gold']}**, deviation `{it['meta']['deviation']}`, "
           f"true count {it['meta']['true_count']}, stated count {it['meta']['stated_count']})", "",
           "state.log:", "```", it["state"]["log"], "```", "state.claim:", "```", it["state"]["claim"], "```",
           f"question: {it['questions']['q']['instructions']}", ""]
    out += [f"- `{k}`: {v}" for k, v in it["questions"]["q"]["criteria"].items()]
    return "\n".join(out)


def main():
    plan = make_plan()
    rows, built = [], []
    for i, p in enumerate(plan):
        for attempt in range(100):
            rng = rng_for("pair", i, attempt)
            try:
                events, pos, neg, info = build_log(rng, p["N"], p)
            except RuntimeError:
                continue
            break
        else:
            raise RuntimeError(f"pair {i}")
        date = f"2026-{rng.randint(1, 9):02d}-{rng.randint(1, 28):02d}"
        look = {"style": rng.randrange(4), "header": rng.randrange(4), "frame": rng.randrange(5), "bound": rng.randrange(4)}
        log = render_log(events, date, look["style"], look["header"])
        for dev, claim in ((None, pos), (p["kind"], neg)):
            text = render_claim(claim, look["frame"], look["bound"])
            spec = {"events": events, "claim": claim, "log": log, "claim_text": text,
                    "true_count": count_events(events, claim)}
            built.append((i, p, spec, dev, info))
    rng = rng_for("order")
    rng.shuffle(built)
    for n, (pair, p, spec, dev, info) in enumerate(built, 1):
        it = to_item(n, pair, p, spec, dev, info)
        # ---- truth twice
        assert truth(spec) == (dev is None), f"{it['id']}: truth {truth(spec)} but planted deviation {dev}"
        assert check(it) == truth(spec), f"{it['id']}: check {check(it)} != truth {truth(spec)}"
        assert len(spec["events"]) == p["N"] == len(spec["log"].split("\n")) - 1
        assert all(a[0] < b[0] for a, b in zip(spec["events"], spec["events"][1:])), "times must ascend strictly"
        assert len({e[1] for e in spec["events"]}) == info["services"] and 4 <= info["services"] <= 6
        it["_class"] = it["gold"]
        rows.append(it)
    rows.sort(key=lambda r: r["id"])
    assign_orders(rows)
    # ---- exactly one field of the claim differs, and the stated count of the negative is what the deviation says
    by_pair = collections.defaultdict(dict)
    for it in rows:
        by_pair[it["meta"]["pair"]][it["gold"]] = it
    for k, d in by_pair.items():
        a, b = d["yes"]["meta"]["spec"]["claim"], d["no"]["meta"]["spec"]["claim"]
        diff = [f for f in ("service", "level", "start", "end", "incl", "count") if a[f] != b[f]]
        dev = d["no"]["meta"]["deviation"]
        want = {"off_by_one": ["count"], "off_by_two": ["count"], "window": ["start", "end"], "service": ["service"]}[dev]
        assert diff == want, (k, dev, diff)
        assert d["yes"]["state"]["log"] == d["no"]["state"]["log"]
        ev = d["no"]["meta"]["spec"]["events"]
        tc, sc = d["no"]["meta"]["true_count"], d["no"]["meta"]["stated_count"]
        assert tc != sc
        if dev in ("off_by_one", "off_by_two"):
            assert abs(sc - d["yes"]["meta"]["true_count"]) == (1 if dev == "off_by_one" else 2)
        else:                                                        # the stated count is the count of the neighbouring window / other service
            assert sc == d["yes"]["meta"]["true_count"] == d["yes"]["meta"]["stated_count"]
            assert tc == plan[k]["c1"]
        assert sc == plan[k]["s"] and 0 <= sc <= CAP[d["no"]["meta"]["lines"]]      # a stated count never leaves the range of the true counts of its level
    # ---- balance and dials
    cls = collections.Counter(r["gold"] for r in rows)
    assert cls == {"yes": 300, "no": 300}, cls
    lines = collections.Counter(r["meta"]["lines"] for r in rows)
    assert set(lines.values()) == {200}, lines
    dev = collections.Counter(r["meta"]["deviation"] for r in rows)
    assert dev["none"] == 300 and all(dev[k] == 75 for k in KINDS), dev
    per_level = collections.Counter((r["meta"]["lines"], r["meta"]["deviation"]) for r in rows)
    assert all(per_level[(N, k)] == 25 for N in (30, 60, 90) for k in KINDS), per_level
    levels = collections.Counter((r["meta"]["level"], r["meta"]["lines"]) for r in rows)
    assert levels == {(1, 30): 200, (2, 60): 200, (3, 90): 200}, levels
    assert all(r["meta"]["level"] in (1, 2, 3) and r["meta"]["log_level"] in LEVELS for r in rows)
    pos_hist = collections.Counter(r["meta"]["true_count"] for r in rows if r["gold"] == "yes")
    neg_hist = collections.Counter(r["meta"]["stated_count"] for r in rows if r["gold"] == "no")
    # ---- the stated counts of the negatives and the true counts of the positives have the same histogram inside EVERY level
    level_hist = {}
    for N, v in LEVEL_OF.items():
        ph = collections.Counter(r["meta"]["true_count"] for r in rows if r["gold"] == "yes" and r["meta"]["level"] == v)
        nh = collections.Counter(r["meta"]["stated_count"] for r in rows if r["gold"] == "no" and r["meta"]["level"] == v)
        l1 = sum(abs(ph[x] - nh[x]) for x in range(STATED_MAX + 1))
        assert l1 <= 2, (v, ph, nh)                    # 2 is the minimum (25 one-step shifts cannot add up to zero)
        assert ph[0] == nh[0], (v, ph, nh)             # claims of 0 events: as many true as false in every level
        assert max(nh) <= CAP[N] and set(ph) == set(range(CAP[N] + 1)), (v, ph, nh)
        level_hist[v] = (ph, nh, l1)
    cue = count_cue_probe(rows)
    tested, worst = vocabulary_test(rows, ["yes", "no"])
    probe = structure_probe(rows)
    lengths = [len(state_text(r)) for r in rows]
    for r in rows:
        del r["_class"]
    d = f"{HERE}/tasks/{TASK}"
    os.makedirs(d, exist_ok=True)
    with open(f"{d}/items.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(rows, key=lambda r: r["id"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    task = {"task": TASK, "layer": "C", "title": "Generated event logs: is the stated count of events correct for this log?",
            "decision": "whether a claim about the number of events of one service and level in a time window is correct for the given log (yes) or not (no)",
            "source": {"name": f"generator build/gen_{TASK}.py", "url": "", "files": [], "split": "generated, seed 20261007",
                       "version": "gen_v4, 2026-10-08: stated counts equally distributed in both classes within every level (no zero-claim cue), "
                                  "number agreement in the claim wording, meta.level = 1/2/3 and meta.log_level"},
            "licence": "generated by the benchmark's script (no third-party text)", "redistribution": "items included",
            "labels": "programmatic", "item_source": "generated", "metric": "accuracy", "chance": 0.5, "rows": len(rows),
            "groups": PAIRS, "question_type": "choice", "options": 2,
            "notes": ("600 items = 300 contrast pairs (meta.pair, group): one log with a true claim (yes) and the same log with the claim changed in "
                      "one field (no): stated count off by one or two, the window replaced by the neighbouring window, or the service replaced by "
                      "another service of the log (the stated count is then that of the window / service of the pair's true claim). The metric is "
                      "item accuracy; the group allows a pair analysis. Dial: lines (30, 60, 90) = meta.level 1, 2, 3; meta.log_level is the severity "
                      "named in the claim. Within every level the stated counts of the negatives and the true counts of the positives have the same "
                      "histogram (0 to 4, 0 to 8, 0 to 12; L1 distance 2 per level, the minimum), so a claim of 0 events is as often true as false and "
                      "no table 'stated count -> answer' beats chance. The noun after the count agrees with it ('1 ERROR event'). Everything is invented "
                      "and every answer is computed twice (specification and a parser of the rendered text). "
                      "gen_v4 (2026-10-08) fixes: stated counts equal per level, singular / plural agreement, meta.level = difficulty level and "
                      "meta.log_level = claim severity. State length %d to %d characters (median %d)." % (min(lengths), max(lengths), sorted(lengths)[300]))}
    json.dump(task, open(f"{d}/task.json", "w"), indent=1)
    val = run_tool("validate.py", TASK)
    aud = run_tool("audit.py", TASK)
    print(val[1] if len(val) > 1 else val)
    print(aud[0])
    print(aud[1] if len(aud) > 1 else aud)
    sys.dont_write_bytecode = True
    sys.path.insert(0, AUDITS)
    import audit
    audit.HERE = HERE                       # the audit reads HERE/tasks/<family>/
    a = audit.audit(TASK)
    assert not a["flag"] and a["length"] < 0.55, a
    write_readme(d, rows, dev, lengths, val, aud, tested, worst, pos_hist, neg_hist, probe, cue, level_hist)
    print("vocabulary test:", tested, "tokens with frequency >= 20, worst ratio %.2f (%s)" % worst)
    print("counts per class", dict(cls), "| lines", dict(lines), "| deviation", dict(dev))
    for v, (ph, nh, l1) in level_hist.items():
        print(f"level {v}: true counts of positives", [ph[x] for x in range(STATED_MAX + 1)], "\n         stated counts of negatives", [nh[x] for x in range(STATED_MAX + 1)], f"(L1 {l1})")
    print("count cue: best table per level %.3f, zero rule %s, true among zero claims %s, among non-zero %s" % (
        cue["by_level"], [round(cue[v]["zero_rule"], 3) for v in (1, 2, 3)],
        [f"{cue[v]['zero_true']}/{cue[v]['zero_claims']}" for v in (1, 2, 3)], [f"{cue[v]['nonzero_true']}/{cue[v]['nonzero_claims']}" for v in (1, 2, 3)]))
    print("state length", min(lengths), max(lengths), "median", sorted(lengths)[300])


def singular_examples(rows):
    """claim sentences with a stated count of 1, one per phrasing (to show the number agreement)"""
    out = {}
    for r in sorted(rows, key=lambda x: x["id"]):
        if r["meta"]["stated_count"] != 1:
            continue
        first = r["state"]["claim"].split(". ", 1)[0] + "."
        frame = [k for k, p in enumerate(CLAIM_PATTERNS) if re.fullmatch(p, first)][0]
        out.setdefault(frame, first)
    return [out[k] for k in sorted(out)]


def write_readme(d, rows, dev, lengths, val, aud, tested, worst, pos_hist, neg_hist, probe, cue, level_hist):
    by_lvl = collections.Counter(r["meta"]["rule_for_end_times"] for r in rows if r["gold"] == "yes")
    bnd = collections.Counter(r["meta"]["boundary_events"] for r in rows if r["gold"] == "yes")
    lvls = collections.Counter(r["meta"]["log_level"] for r in rows if r["gold"] == "yes")
    ex = []
    for N, kind in ((30, "off_by_one"), (60, "window"), (90, "service")):
        ex.append(next(x for x in sorted(rows, key=lambda x: x["id"]) if x["meta"]["lines"] == N and x["meta"]["deviation"] == kind))
    one = singular_examples(rows)
    n_one = collections.Counter(r["gold"] for r in rows if r["meta"]["stated_count"] == 1)
    cue_rows = "\n".join(
        f"| {v} | {N} | {' '.join(str(level_hist[v][0][x]) for x in range(CAP[N] + 1))} | {' '.join(str(level_hist[v][1][x]) for x in range(CAP[N] + 1))} | "
        f"{level_hist[v][2]} | {cue[v]['zero_true']} / {cue[v]['zero_claims']} | {cue[v]['nonzero_true']} / {cue[v]['nonzero_claims']} | "
        f"{cue[v]['zero_rule']:.3f} | {cue[v]['table']:.3f} |" for N, v in LEVEL_OF.items())
    txt = f"""# {TASK}

Generated event logs: is the stated count of events correct for this log? (layer C, generated, programmatic truth)

- Decision: whether a claim about the number of events of one service and level in a time window is correct for the given log (yes) or not (no).
- Source: generator `build/gen_{TASK}.py` (standard library only, `random.Random(20261007)` and sub-generators; the output is identical on every run); no third-party text.
- Licence: generated by the benchmark's script (no third-party text); items included.
- Rows: {len(rows)} in {PAIRS} contrast pairs (300 yes, 300 no); metric: accuracy (chance 0.5).
- Rebuild: `python3 build/gen_{TASK}.py`
- Version: gen_v4 (2026-10-08). Fixes after the human review: the stated count is no cue (equal histograms per level), the noun after the count agrees with it, `meta.level` is the difficulty level and the severity of the claim is `meta.log_level`.

## What is generated

An event log of one day (lines `time service level code`, 4 to 6 invented services `svc-...`, levels INFO / WARN / ERROR, times strictly ascending,
shown in one of four line layouts under one of four headers) and a claim such as "svc-kelta logged 7 ERROR events between 09:00:00 and 11:30:00. Both end times count."
The claim is one of five phrasings; the second sentence states in words whether the end times of the window count (both: {by_lvl['both']} pairs, only the start: {by_lvl['half']}, neither: {by_lvl['none']}).
Severity named in the claim (`meta.log_level`): ERROR {lvls['ERROR']}, WARN {lvls['WARN']}, INFO {lvls['INFO']} pairs. The answer is yes when the log holds exactly the stated number of events of that service and severity in that window.
The order of the two options is drawn per item (`meta.order`; exactly half of the positives and half of the negatives list `yes` first).

**Pairs.** The positive and the negative of a pair share the log; the negative changes ONE field of the claim (`meta.deviation`): the stated count
is off by one or two (`off_by_one`, `off_by_two`), the window is replaced by the neighbouring window of the same length (`window`), or another service of the log is
named (`service`). A `window` or `service` negative keeps the stated count of its positive, which is then the count of the window / service next to the one named.

**The stated count is no cue.** Within every level the stated counts of the negatives have the same histogram as the true counts of the positives, over the same range
(0 to 4, 0 to 8, 0 to 12; an off-by shift never leaves the range of its level). So a claim of 0 events is as often true as false, a claim of k > 0 events is as often true
as false, and no table "stated count -> answer", fitted on the items themselves, is better than chance. The 25 one-step shifts of a level cannot cancel exactly (odd number), so the two histograms of
a level differ in one pair (L1 distance 2, never in the bin of 0). The shifts are found by a maximum bipartite matching of the off-by pairs to the true counts of their level.
Measured by the script (true / all claims; accuracy of the better of the rules "zero -> yes" and "zero -> no"; accuracy of the best table "stated count -> majority answer", an upper bound for every rule on the stated count alone):

| level | lines | true counts of positives (0, 1, ...) | stated counts of negatives | L1 | claims of 0 events: true / all | claims of k > 0: true / all | best zero rule | best table |
|---|---|---|---|---|---|---|---|---|
{cue_rows}

All 600 items: claims of 0 events {cue['all']['zero_true']} / {cue['all']['zero_claims']} true, claims of k > 0 events {cue['all']['nonzero_true']} / {cue['all']['nonzero_claims']} true; best table over the whole family {cue['all']['table']:.3f}, one table per level {cue['by_level']:.3f}.

**Number agreement.** The noun after the count is singular for a count of 1 and plural for 0 and for 2 or more, in every phrasing ("1 ERROR event", "exactly 1 ERROR entry",
"there was 1 ERROR line", "0 ERROR events"; verb "was" / "were" in the existential phrasing). {n_one['yes']} positives and {n_one['no']} negatives state a count of 1, for example:

""" + "\n".join(f'- "{s}"' for s in one) + f"""

`check(item)` parses both forms and asserts that the form agrees with the count.

**Four planted cells in every log.** Besides the claimed cell (claimed service, claimed level, claimed window) the log holds the cell the `window` negative points to
(same service and level, neighbouring window), the cell the `service` negative points to (other service, claimed window) and a fourth cell (other service,
neighbouring window), with similar counts (the count of a decoy cell differs from the true count by 1 to 4). All four cells get the same structure: events of the cell just
outside its window (1 to 240 seconds), the same distractors in both windows (the service at another level, the other services at the claimed level) and, with
probability 0.2 per bound, an event exactly at the start or the end of the window (`meta.boundary_events` counts them for the claimed cell: {sum(v for k, v in bnd.items() if k)} of 300 logs),
where the stated rule for the end times decides whether it counts. So neither the busiest service nor the busiest window nor the cell with the near misses is the claimed one more often
in one class than in the other (measured by the script, yes / no: claimed service is the busiest of the log in {probe['busiest']['yes']:.2f} / {probe['busiest']['no']:.2f} of the items; events in the claimed window {probe['window_events']['yes']:.1f} / {probe['window_events']['no']:.1f};
events of the claimed service and level in the whole log {probe['service_level_events']['yes']:.1f} / {probe['service_level_events']['no']:.1f}).

## Dials and metadata

| dial | levels | items per level |
|---|---|---|
| `meta.level` = difficulty level = `meta.lines` (events in the log) | 1 = 30 lines, 2 = 60 lines, 3 = 90 lines | 200 each |

`meta.log_level` is the severity named in the claim (INFO / WARN / ERROR); the old dial field `meta.lines` (30, 60, 90) stays.
State length: {min(lengths)} to {max(lengths)} characters (median {sorted(lengths)[len(lengths)//2]}). True counts range over 0 to 4 (level 1), 0 to 8 (level 2) and 0 to 12 (level 3).

## Deviation kinds (negatives)

| `meta.deviation` | items | per level (1 / 2 / 3) |
|---|---|---|
| `off_by_one` | {dev['off_by_one']} | 25 / 25 / 25 |
| `off_by_two` | {dev['off_by_two']} | 25 / 25 / 25 |
| `window` | {dev['window']} | 25 / 25 / 25 |
| `service` | {dev['service']} | 25 / 25 / 25 |

## Checks made by the script

- `truth(spec)` (counting on the structured events) and `check(item)` (parses the rendered log lines and the rendered claim, asserts the number agreement and counts again) agree on all 600 items.
- In every pair the log is identical, exactly one field of the claim differs (the count; the window; the service), the answer turns from yes to no, and the stated count of a
  `window` / `service` negative equals the count of its positive (planted exactly; the named window / service holds another count).
- Classes are exactly balanced; every level has exactly 200 items and 25 negatives of each kind.
- Stated counts of the negatives and true counts of the positives: same histogram inside every level (L1 distance 2 per level, the bin of 0 exactly equal); rules on the stated count alone: all at most 0.52 (table above).
- Vocabulary test: {tested} tokens of frequency >= 20 are tested; none occurs in one class at more than twice the rate of the other (largest ratio {worst[0]:.2f}, `{worst[1]}`).
- Shortcut audit (`python3 audit.py {TASK}`), best length rule below 0.55:

```
{aud[0]}
{aud[1]}
```

Validator: `{val[1].strip() if len(val) > 1 else val}`

## Examples (one per level; negatives)

""" + "\n\n".join(f"### level {x['meta']['level']} ({x['meta']['lines']} lines), deviation `{x['meta']['deviation']}`\n\n" + fmt_item(x) for x in ex) + """

## Independence from training generators

The items are disjoint from any training generator of the authors by construction: this is a new generator, written for the benchmark;
service names, codes, templates and logs share nothing with the generators used for training.
"""
    open(f"{d}/README.md", "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
