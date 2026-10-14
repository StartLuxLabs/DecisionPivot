"""Independent solver for `log_count_check` (second author; written from the rendered text only).

state    = {"log": "<header line>\\n<one event per line>", "claim": "<one claim sentence>. <one sentence on the window ends>."}
question = "Is the claim correct for this log?"
options  = {key: "The claim is correct for this log." | "The claim is not correct for this log."}

Method: read the header, the event lines (four line layouts) and the claim (five phrasings, each with the word "exactly" before
the number, singular / plural nouns, a second sentence that says in words whether the start and the end of the window count).
A claim without "exactly" is not recognised (the stated number is only an exact count when the text says so).  The events of the claimed service and
severity are turned into a sorted list of seconds; the number of events in the window is the number STRICTLY inside the
window (two bisections) plus the events exactly at the start / at the end if the stated rule lets them count.  A second,
naive count (filter with <= / <) must agree.  Every line / sentence that is not recognised raises ValueError.
"""
import bisect
import json
import re

LEVELS = ("INFO", "WARN", "ERROR")
LVL = r"(INFO|WARN|ERROR)"
T = r"(\d\d:\d\d:\d\d)"
SVC = r"(svc-[a-z]+)"
CODE = r"([IWE]\d{4})"

HEADERS = [
    re.compile(r"^Event log for (\d{4}-\d\d-\d\d) \(UTC\)\. One event per line: time, service, level, code\.$"),
    re.compile(r"^Log extract of (\d{4}-\d\d-\d\d); every line is one event \(time, service, level, code\); times are UTC and ascending\.$"),
    re.compile(r"^Events recorded on (\d{4}-\d\d-\d\d) \(UTC\), oldest first\. Line format: time service level code\.$"),
    re.compile(r"^Service log, (\d{4}-\d\d-\d\d), times in UTC\. Columns: time service level code\.$"),
]

# (regex, group order of time / service / level / code)
LAYOUTS = {
    "plain": re.compile(rf"^{T} {SVC} {LVL} {CODE}$"),
    "square_time": re.compile(rf"^\[{T}\] {SVC} {LVL} {CODE}$"),
    "square_level": re.compile(rf"^{T} {SVC} \[{LVL}\] {CODE}$"),
    "pipes": re.compile(rf"^{T} \| {SVC} \| {LVL} \| {CODE}$"),
}

# claim phrasings: name -> (regex, noun kind); group names carry the fields
CLAIMS = [
    ("logged", re.compile(rf"^(?P<svc>{SVC}) logged exactly (?P<n>\d+) (?P<lvl>{LVL}) (?P<noun>events?) between (?P<a>{T}) and (?P<b>{T})\. (?P<rule>.+)$"), "event"),
    ("reported", re.compile(rf"^(?P<svc>{SVC}) reported exactly (?P<n>\d+) (?P<lvl>{LVL}) (?P<noun>events?) from (?P<a>{T}) until (?P<b>{T})\. (?P<rule>.+)$"), "event"),
    ("shows", re.compile(rf"^The log shows exactly (?P<n>\d+) (?P<lvl>{LVL}) (?P<noun>events?) from (?P<svc>{SVC}) in the window (?P<a>{T}) to (?P<b>{T})\. (?P<rule>.+)$"), "event"),
    ("period", re.compile(rf"^In the period from (?P<a>{T}) to (?P<b>{T}) there (?P<verb>was|were) exactly (?P<n>\d+) (?P<lvl>{LVL}) (?P<noun>lines?) for (?P<svc>{SVC})\. (?P<rule>.+)$"), "line"),
    ("wrote", re.compile(rf"^Between (?P<a>{T}) and (?P<b>{T}), (?P<svc>{SVC}) wrote exactly (?P<n>\d+) (?P<lvl>{LVL}) (?P<noun>entry|entries)\. (?P<rule>.+)$"), "entr"),
]


def secs(hms):
    h, m, s = (int(x) for x in hms.split(":"))
    assert 0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60, f"bad time {hms}"
    return h * 3600 + m * 60 + s


def parse_log(log):
    lines = log.split("\n")
    if not any(h.match(lines[0]) for h in HEADERS):
        raise ValueError(f"unknown header: {lines[0]!r}")
    body = lines[1:]
    if not body:
        raise ValueError("log without events")
    layout = None
    events = []
    for ln in body:
        hit = None
        for name, rx in LAYOUTS.items():
            m = rx.match(ln)
            if m:
                hit = (name, m)
                break
        if hit is None:
            raise ValueError(f"unknown event line: {ln!r}")
        if layout is None:
            layout = hit[0]
        elif layout != hit[0]:
            raise ValueError(f"mixed layouts: {layout} and {hit[0]} ({ln!r})")
        t, svc, lvl, code = hit[1].groups()
        if code[0] != lvl[0]:
            raise ValueError(f"code {code} does not fit level {lvl}: {ln!r}")
        events.append((secs(t), svc, lvl))
    for (a, _, _), (b, _, _) in zip(events, events[1:]):
        if b < a:
            raise ValueError("log not in ascending time order")
    return events


def parse_rule(rule, a, b):
    """-> (start counts, end counts); a, b = the two time strings of the claim in the order written (start, end)."""
    simple = {
        "The window includes its start and its end.": (True, True),
        "Bounds are inclusive.": (True, True),
        "Both end times count.": (True, True),
        "The start time counts; the end time does not.": (True, False),
        "The window includes its start but not its end.": (True, False),
        "Bounds are half-open: start included, end excluded.": (True, False),
        "Neither end time counts.": (False, False),
        "Bounds are exclusive.": (False, False),
        "The window excludes its start and its end.": (False, False),
    }
    if rule in simple:
        return simple[rule]
    m = re.fullmatch(rf"Events at exactly {T} or {T} are (not )?included\.", rule)
    if m:
        if {m.group(1), m.group(2)} != {a, b}:
            raise ValueError(f"rule names other times than the window: {rule!r}")
        inc = m.group(3) is None
        return (inc, inc)
    m = re.fullmatch(rf"An event at exactly {T} is included, an event at exactly {T} is not\.", rule)
    if m:
        if (m.group(1), m.group(2)) == (a, b):
            return (True, False)
        if (m.group(1), m.group(2)) == (b, a):
            return (False, True)
        raise ValueError(f"rule names other times than the window: {rule!r}")
    raise ValueError(f"unknown rule sentence: {rule!r}")


def parse_claim(claim):
    claim = claim.strip()
    for name, rx, stem in CLAIMS:
        m = rx.match(claim)
        if not m:
            continue
        g = m.groupdict()
        n = int(g["n"])
        noun = g["noun"]
        plural = noun.endswith("s") or noun == "entries"
        if plural == (n == 1):
            raise ValueError(f"number disagreement in claim: {claim!r}")
        if "verb" in g and g["verb"] is not None and (g["verb"] == "were") != (n != 1):
            raise ValueError(f"verb disagreement in claim: {claim!r}")
        sc, ec = parse_rule(g["rule"], g["a"], g["b"])
        return {"phrasing": name, "service": g["svc"], "level": g["lvl"], "n": n,
                "start": secs(g["a"]), "end": secs(g["b"]), "start_counts": sc, "end_counts": ec}
    raise ValueError(f"unknown claim phrasing: {claim!r}")


def count_events(events, c):
    cell = sorted(t for (t, svc, lvl) in events if svc == c["service"] and lvl == c["level"])
    lo, hi = c["start"], c["end"]
    if not lo < hi:
        raise ValueError("window is empty or reversed")
    strictly_inside = bisect.bisect_left(cell, hi) - bisect.bisect_right(cell, lo)
    at_start = bisect.bisect_right(cell, lo) - bisect.bisect_left(cell, lo)
    at_end = bisect.bisect_right(cell, hi) - bisect.bisect_left(cell, hi)
    n = strictly_inside + (at_start if c["start_counts"] else 0) + (at_end if c["end_counts"] else 0)
    # second count, written the naive way
    naive = 0
    for (t, svc, lvl) in events:
        if svc != c["service"] or lvl != c["level"]:
            continue
        above = t > lo or (t == lo and c["start_counts"])
        below = t < hi or (t == hi and c["end_counts"])
        if above and below:
            naive += 1
    assert naive == n, f"two counts disagree: {n} vs {naive}"
    return n


def _state_fields(state):
    if isinstance(state, str):
        try:
            state = json.loads(state)
        except ValueError:
            raise ValueError("state is a string that is not JSON")
    if not isinstance(state, dict) or set(state) != {"log", "claim"}:
        raise ValueError(f"unexpected state layout: {type(state).__name__}")
    return state["log"], state["claim"]


def solve(state, question, options):
    if question.strip() != "Is the claim correct for this log?":
        raise ValueError(f"unknown question: {question!r}")
    yes_keys = [k for k, v in options.items() if v.strip() == "The claim is correct for this log."]
    no_keys = [k for k, v in options.items() if v.strip() == "The claim is not correct for this log."]
    if len(options) != 2 or len(yes_keys) != 1 or len(no_keys) != 1:
        raise ValueError(f"unknown options: {dict(options)!r}")
    log, claim = _state_fields(state)
    events = parse_log(log)
    c = parse_claim(claim)
    if c["service"] not in {svc for (_, svc, _) in events}:
        raise ValueError(f"claimed service {c['service']} does not occur in the log")
    return yes_keys[0] if count_events(events, c) == c["n"] else no_keys[0]
