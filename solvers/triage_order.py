"""Independent second implementation for the task `triage_order` (label audit of gen_v3).

Written from the rendered text alone.  The state is parsed with one regular expression per phrasing that occurs; every
line that no expression recognises raises `Unrecognised` (nothing is skipped silently).  The numbered rules are turned
into a pairwise comparison function `precedes(a, b)` (not a sort key); the order is then built by repeated duels: the
case that beats every remaining case is taken next.  The answer is the case at the asked position; the option key is
returned.  If the written rules leave two cases level where it matters, `NotTotalOrder` is raised.

    solve(state, question, options) -> option key
"""
import re
from collections import OrderedDict

NOUN = r"(?:patient|visitor|vessel|job|task|request)"
NOUNS = NOUN + "s"


class Unrecognised(Exception):
    pass


class NotTotalOrder(Exception):
    pass


def _c(p):
    return re.compile(p.replace("<NS>", NOUNS).replace("<N>", NOUN))


def _fail(msg):
    raise Unrecognised(msg)


def _mins(s):
    m = re.match(r"^(\d\d):(\d\d)$", s)
    if not m:
        _fail("bad time %r" % s)
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        _fail("time out of range %r" % s)
    return h * 60 + mi


# ---------------------------------------------------------------------------------------------------- state layout
SINGLE = [
    ("loc", _c(r"^(?:Location|Service point|Queue of): (.+)$")),
    ("now", _c(r"^(?:Current time|Time now|Clock at the moment of the decision): (\d\d:\d\d)$")),
    ("asked", _c(r"^Position asked for: (first|second|third)$")),
    ("asked", _c(r"^Asked: the <N> that is (first|second|third) in the order$")),
    ("asked", _c(r"^Wanted: the <N> standing (first|second|third) in the order worked out at the current time$")),
]
BLOCK = [
    ("rules", _c(r"^(?:Rules, applied in the order given|Ordering rules \(apply them in this order\)|"
                 r"The order is fixed by these rules, taken in the order given):$")),
    ("notes", _c(r"^(?:Notes on the rules|Conventions|How to read the rules):$")),
    ("fields", _c(r"^(?:Fields of the list|Meaning of the fields|What the list shows):$")),
    ("list", _c(r"^(\d+) <NS> are waiting; the list is not sorted in any meaningful way:$")),
    ("list", _c(r"^Waiting <NS> \((\d+)\), in no particular order:$")),
    ("list", _c(r"^List of the (\d+) waiting <NS> \(the listing order means nothing\):$")),
]
POS = {"first": 1, "second": 2, "third": 3}


def split_state(state):
    out = {"loc": [], "now": [], "asked": [], "rules": [], "notes": [], "fields": [], "list": []}
    cur = None                       # (kind, lines, header_group)
    for raw in state.split("\n"):
        ln = raw.rstrip()
        if not ln.strip():
            cur = None
            continue
        hit = None
        for kind, rx in SINGLE:
            m = rx.match(ln)
            if m:
                hit = ("single", kind, m)
                break
        if hit is None:
            for kind, rx in BLOCK:
                m = rx.match(ln)
                if m:
                    hit = ("block", kind, m)
                    break
        if hit is not None:
            cur = None
            if hit[0] == "single":
                out[hit[1]].append(hit[2].group(1))
            else:
                cur = (hit[1], [], hit[2].group(1) if hit[2].groups() else None)
                out[hit[1]].append(cur)
            continue
        if cur is None:
            _fail("line outside any section: %r" % ln[:80])
        cur[1].append(ln)
    for k, v in out.items():
        if k == "loc":
            if len(v) > 1:
                _fail("several location lines")
        elif len(v) != 1:
            _fail("section %s found %d times" % (k, len(v)))
    return out


# ---------------------------------------------------------------------------------------------------- fields / list
ARRIVAL_DESC = _c(r"^time the <N> (?:arrived|was logged|was checked in|was submitted|entered|dropped anchor)\b")
APPT_DESC = _c(r"^(?:time of the|start of the) .*\"-\"")
DUR_DESC = _c(r"^(?:the )?(?:expected|estimated) .* in minutes")


def parse_fields(lines):
    fields = OrderedDict()
    for ln in lines:
        m = re.match(r"^- ([a-z]+): (.+)$", ln)
        if not m:
            _fail("field line not recognised: %r" % ln[:80])
        if m.group(1) in fields:
            _fail("field described twice: " + m.group(1))
        fields[m.group(1)] = m.group(2)
    roles = {}
    for name, desc in fields.items():
        if name in ("ticket", "class", "flag"):
            role = name
        elif ARRIVAL_DESC.match(desc):
            role = "arrival"
        elif APPT_DESC.match(desc):
            role = "appt"
        elif DUR_DESC.match(desc):
            role = "dur"
        else:
            _fail("field %r with description %r has no known role" % (name, desc[:60]))
        if role in roles:
            _fail("two columns with role " + role)
        roles[role] = name
    for need in ("ticket", "class", "flag", "arrival"):
        if need not in roles:
            _fail("no column with role " + need)
    return fields, roles


def parse_list(lines, count):
    if not lines:
        _fail("empty list")
    head = lines[0]
    raw = []                                   # list of OrderedDict name -> text
    if head.startswith("ticket,"):
        names = head.split(",")
        for ln in lines[1:]:
            cells = ln.split(",")
            if len(cells) != len(names):
                _fail("row has %d cells, header %d: %r" % (len(cells), len(names), ln[:60]))
            raw.append(OrderedDict(zip(names, cells)))
    elif head.startswith("ticket |"):
        names = head.split(" | ")
        for ln in lines[1:]:
            cells = ln.split(" | ")
            if len(cells) != len(names):
                _fail("row has %d cells, header %d: %r" % (len(cells), len(names), ln[:60]))
            raw.append(OrderedDict(zip(names, cells)))
    else:
        names = None
        for ln in lines:
            m = re.match(r"^([A-Z]+-\d+): (.+)$", ln)
            if not m:
                _fail("row not recognised: %r" % ln[:60])
            row = OrderedDict([("ticket", m.group(1))])
            for part in m.group(2).split("; "):
                mm = re.match(r"^([a-z]+) (\S+)$", part)
                if not mm:
                    _fail("cell not recognised: %r" % part)
                if mm.group(1) in row:
                    _fail("cell twice: " + part)
                row[mm.group(1)] = mm.group(2)
            raw.append(row)
        names = list(raw[0].keys())
        for r in raw:
            if list(r.keys()) != names:
                _fail("rows do not share one set of cells")
    if len(raw) != count:
        _fail("announced %d cases, found %d" % (count, len(raw)))
    return names, raw


def build_cases(names, raw, fields, roles):
    if set(names) != set(fields):
        _fail("table columns %s differ from the described fields %s" % (sorted(names), sorted(fields)))
    cases = []
    seen_id, seen_num = set(), set()
    for r in raw:
        t = r[roles["ticket"]]
        m = re.match(r"^([A-Z]+)-(\d+)$", t)
        if not m:
            _fail("ticket not recognised: %r" % t)
        if t in seen_id:
            _fail("ticket twice: " + t)
        seen_id.add(t)
        num = int(m.group(2))
        if num in seen_num:
            _fail("ticket number twice: %d" % num)       # the state says numbers are unique
        seen_num.add(num)
        c = {"id": t, "num": num}
        if not re.match(r"^\d+$", r[roles["class"]]):
            _fail("class not a number: %r" % r[roles["class"]])
        c["cls"] = int(r[roles["class"]])
        c["arr"] = _mins(r[roles["arrival"]])
        fl = r[roles["flag"]]
        if fl != "-" and not re.match(r"^[a-z]+$", fl):
            _fail("flag not recognised: %r" % fl)
        c["flag"] = None if fl == "-" else fl
        if "appt" in roles:
            v = r[roles["appt"]]
            c["appt"] = None if v == "-" else _mins(v)
        if "dur" in roles:
            v = r[roles["dur"]]
            if not re.match(r"^\d+$", v):
                _fail("duration not a number: %r" % v)
            c["dur"] = int(v)
        cases.append(c)
    return cases


# ---------------------------------------------------------------------------------------------------- rules
RULE_PATTERNS = [
    ("wait", _c(r"^A <N> that has waited at least (\d+) minutes moves up one class\.$")),
    ("wait", _c(r"^Once the waiting time of a <N> is at least (\d+) minutes, it is moved up one class\.$")),
    ("wait", _c(r"^Waiting at least (\d+) minutes lifts a <N> by one class\.$")),
    ("flag", _c(r"^The flag \"([^\"]+)\" moves a <N> up one class\.$")),
    ("flag", _c(r"^Any <N> carrying the flag \"([^\"]+)\" is lifted by one class\.$")),
    ("flag", _c(r"^A <N> with the flag \"([^\"]+)\" counts one class more urgent\.$")),
    ("class", _c(r"^Lower class number first\.$")),
    ("class", _c(r"^The <NS> are taken class by class, smallest class number first\.$")),
    ("class", _c(r"^A <N> with a lower class number goes before a <N> with a higher class number\.$")),
    ("arrival_col", _c(r"^Of two <NS>, the one with the earlier time under \"([a-z]+)\" is ahead\.$")),
    ("arrival_word", _c(r"^The <N> that (arrived|was logged|was checked in|was submitted|entered|anchored) earlier goes first\.$")),
    ("arrival_word", _c(r"^Earlier (arrival|logging time|check-in|submission|entry|anchoring time) first\.$")),
    ("appt", _c(r"^Among <NS> of one class, a <N> with a due (.+?) is ahead of a <N> without a due one\.$")),
    ("appt", _c(r"^Within the same class, <NS> whose (.+?) is due go first\.$")),
    ("appt", _c(r"^Inside a class, every <N> whose (.+?) is due precedes every <N> whose \1 is not due\.$")),
    ("dur_col", _c(r"^Of two <NS>, the one with fewer minutes under \"([a-z]+)\" is ahead\.$")),
    ("dur_word", _c(r"^Shorter (.+?) first\.$")),
    ("dur_word", _c(r"^The <N> with the shorter (.+?) goes first\.$")),
    ("ticket", _c(r"^Lower ticket number first\.$")),
    ("ticket", _c(r"^Last tie-break: the <N> with the lower ticket number goes first\.$")),
    ("ticket", _c(r"^If <NS> are still level, the lower ticket number is ahead\.$")),
]


def _prefix(a, b):
    a, b = a.replace("-", "").lower(), b.replace("-", "").lower()
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return n


def parse_rules(lines, fields, roles):
    rules = []
    for i, ln in enumerate(lines, 1):
        m = re.match(r"^(\d+)\. (.+)$", ln)
        if not m or int(m.group(1)) != i:
            _fail("rule line not numbered %d: %r" % (i, ln[:60]))
        text = m.group(2)
        hits = [(k, rx.match(text)) for k, rx in RULE_PATTERNS if rx.match(text)]
        if len(hits) != 1:
            _fail("rule %d not recognised (%d patterns): %r" % (i, len(hits), text[:90]))
        kind, mm = hits[0]
        r = {"no": i, "text": text}
        if kind == "wait":
            r["kind"], r["W"] = "wait", int(mm.group(1))
        elif kind == "flag":
            r["kind"], r["flag"] = "flag", mm.group(1)
        elif kind == "class":
            r["kind"] = "class"
        elif kind == "ticket":
            r["kind"] = "ticket"
        elif kind == "arrival_col":
            if mm.group(1) != roles["arrival"]:
                _fail("rule %d orders by column %r, the arrival column is %r" % (i, mm.group(1), roles["arrival"]))
            r["kind"] = "arrival"
        elif kind == "arrival_word":
            if _prefix(re.sub(r"^was ", "", mm.group(1)).split()[0], roles["arrival"]) < 3:
                _fail("rule %d word %r does not fit the arrival column %r" % (i, mm.group(1), roles["arrival"]))
            r["kind"] = "arrival"
        elif kind == "appt":
            if "appt" not in roles:
                _fail("rule %d needs an appointment column; there is none" % i)
            ph = mm.group(1)
            if ph not in fields[roles["appt"]] and roles["appt"] not in ph.split():
                _fail("rule %d: %r is not the appointment column %r" % (i, ph, roles["appt"]))
            r["kind"] = "appt"
        elif kind == "dur_col":
            if "dur" not in roles or mm.group(1) != roles["dur"]:
                _fail("rule %d: column %r is not the duration column" % (i, mm.group(1)))
            r["kind"] = "dur"
        elif kind == "dur_word":
            if "dur" not in roles:
                _fail("rule %d needs a duration column; there is none" % i)
            if mm.group(1) not in fields[roles["dur"]]:
                _fail("rule %d: %r is not the duration column %r" % (i, mm.group(1), roles["dur"]))
            r["kind"] = "dur"
        rules.append(r)
    if not rules:
        _fail("no rules")
    return rules


# ---------------------------------------------------------------------------------------------------- conventions
NOTE_PATTERNS = [
    ("noop", _c(r"^Whatever the list shows that no rule uses \(a column, a flag\) is for information only\.$")),
    ("noop", _c(r"^An earlier rule always outranks a later one; a later rule only breaks ties that remain after the rules above it\.$")),
    ("noop", _c(r"^Columns and flags that no rule mentions have no effect on the order\.$")),
    ("noop", _c(r"^Only what the rules name counts; any other column or flag changes nothing\.$")),
    ("noop", _c(r"^Ticket numbers are the digits after the dash, compared as numbers, and they are unique\.$")),
    ("noop", _c(r"^All positions \(first, second, third\) refer to a single order computed at the current time; the clock is not moved in between\.$")),
    ("noop", _c(r"^Every <N> has its own ticket number: the number that follows the dash in the identifier\.$")),
    ("noop", _c(r"^Read the rules from top to bottom; a later rule is used only to separate <NS> that every earlier rule leaves level\.$")),
    ("noop", _c(r"^The ticket number is the number after the dash; no two <NS> have the same one\.$")),
    ("noop", _c(r"^After a class change a <N> is treated like every other <N> of its new class\.$")),
    ("noop", _c(r"^The rules are applied in the order given: a rule decides only between <NS> that all rules before it leave level\.$")),
    ("noop", _c(r"^A <N> that has moved up is an ordinary member of its new class; nothing else about it changes\.$")),
    ("noop", _c(r"^The order is worked out once, for all waiting <NS>, at the current time; first, second and third are positions in this one order\.$")),
    ("noop", _c(r"^Rank every waiting <N> once, as things stand at the current time; the position asked for is a place in that ranking\.$")),
    ("noop", _c(r"^Once moved, a <N> competes inside its new class on equal terms with the <NS> already there\.$")),
    ("step1", _c(r"^Moving up one class means that the class number becomes one smaller \(class (\d+) becomes class (\d+)\)\.$")),
    ("step1", _c(r"^\"Up one class\" is the class number minus 1; for example, class (\d+) turns into class (\d+)\.$")),
    ("step1r", _c(r"^A <N> that moves up one class gets the next smaller class number, for instance (\d+) instead of (\d+)\.$")),
    ("top", _c(r"^There is no class above class (\d+), so a change that would lead above class \1 stops at class \1\.$")),
    ("top", _c(r"^Class (\d+) is the top: a <N> never moves above class \1\.$")),
    ("top", _c(r"^No <N> can go higher than class (\d+); a <N> of class \1 stays in class \1 whatever applies to it\.$")),
    ("limit", _c(r"^The limit itself counts: (\d+) minutes of waiting are enough, one minute less is not\.$")),
    ("limit", _c(r"^\"At least (\d+) minutes\" includes exactly \1 minutes; (\d+) minutes are not enough\.$")),
    ("limit", _c(r"^A wait of exactly (\d+) minutes counts as at least \1 minutes\.$")),
    ("setclass1", _c(r"^Rule (\d+) does not order anything by itself: it sets the class that the later rules use\.$")),
    ("setclass2", _c(r"^Rules (\d+) and (\d+) do not order anything by themselves: they set the class that the later rules use\.$")),
    ("setclass1", _c(r"^Rule (\d+) changes the class of a <N> and is applied to every <N> before anything is compared; in the rules after it, \"class\" means the class after this change\.$")),
    ("setclass2", _c(r"^Rules (\d+) and (\d+) change the class of a <N> and are applied to every <N> before anything is compared; in the rules after them, \"class\" means the class after these changes\.$")),
    ("first1", _c(r"^First apply rule (\d+) to each <N>; from rule (\d+) on, the word \"class\" stands for the changed class\.$")),
    ("first2", _c(r"^First apply rules (\d+) and (\d+) to each <N>; from rule (\d+) on, the word \"class\" stands for the changed class\.$")),
    ("waitcol", _c(r"^To get the waiting time, subtract the \"([a-z]+)\" time from the current time \(in minutes; same day; 24-hour clock\)\.$")),
    ("waitcol", _c(r"^Waiting time = current time minus the time under \"([a-z]+)\", in minutes \(same day, 24-hour clock\)\.$")),
    ("waitcol", _c(r"^The waiting time of a <N> is counted in minutes from the time under \"([a-z]+)\" to the current time; all times are today, on a 24-hour clock\.$")),
    ("combo_add", _c(r"^The two class changes are cumulative: meeting rule (\d+) and rule (\d+) means two classes up, with class (\d+) as the limit\.$")),
    ("combo_add", _c(r"^Rules (\d+) and (\d+) add up: a <N> that meets both moves up two classes \(but never above class (\d+)\)\.$")),
    ("combo_add1", _c(r"^Both class changes can apply to the same <N>; it then moves up two classes in total, stopping at class (\d+)\.$")),
    ("combo_one", _c(r"^The two class changes are not cumulative: meeting rule (\d+) and rule (\d+) counts the same as meeting one of them\.$")),
    ("combo_one", _c(r"^Rules (\d+) and (\d+) do not add up: a <N> that meets both still moves up one class only\.$")),
    ("combo_one", _c(r"^A <N> moves up at most one class in total, even when both rule (\d+) and rule (\d+) apply to it\.$")),
    ("arr_unique", _c(r"^No two <NS> in the list have the same time under \"([a-z]+)\"\.$")),
    ("arr_unique", _c(r"^Every <N> in the list has its own \"([a-z]+)\" time; no two are equal\.$")),
    ("arr_unique_last", _c(r"^The times under \"([a-z]+)\" are all different, so the last rule never leaves two <NS> level\.$")),
    ("due_col", _c(r"^Due means that the time under \"([a-z]+)\" has been reached: it is equal to the current time or before it\.$")),
    ("due_phrase", _c(r"^A (.+?) counts as due from its own minute on, that is, when it is not later than the current time\.$")),
    ("due_phrase", _c(r"^A (.+?) is due when its time is the current time or earlier; a later one is not due yet\.$")),
    ("due_level", _c(r"^The <NS> with a due (.+?) are level with each other under this rule \(the times under \"([a-z]+)\" are not compared\), and so are the <NS> without a due one\.$")),
    ("due_level2", _c(r"^Two <NS> that are both due, or both not due \(no (.+?), or one that is still to come\), stay level under this rule\.$")),
    ("due_level3", _c(r"^The rule only separates due from not due: how early the (.+?) was does not matter, and \"-\" or a later time counts as not due\.$")),
]


def check_notes(lines, rules, roles, fields, cases):
    changers = [r for r in rules if r["kind"] in ("wait", "flag")]
    ch_nos = [r["no"] for r in changers]
    waits = [r["W"] for r in rules if r["kind"] == "wait"]
    info = {"combo": None, "top": set(), "false": []}

    def ph_ok(ph):
        return "appt" in roles and (ph in fields[roles["appt"]] or roles["appt"] in ph.split())

    for ln in lines:
        m0 = re.match(r"^- (.+)$", ln)
        if not m0:
            _fail("convention line without dash: %r" % ln[:60])
        text = m0.group(1)
        hits = [(k, rx.match(text)) for k, rx in NOTE_PATTERNS if rx.match(text)]
        if len(hits) != 1:
            _fail("convention not recognised (%d patterns): %r" % (len(hits), text[:100]))
        kind, m = hits[0]
        g = m.groups()
        if kind == "noop":
            pass
        elif kind == "step1":
            if int(g[0]) - 1 != int(g[1]):
                _fail("odd class step: " + text)
        elif kind == "step1r":
            if int(g[0]) != int(g[1]) - 1:
                _fail("odd class step: " + text)
        elif kind == "top":
            info["top"].add(int(g[0]))
        elif kind == "limit":
            if not waits or any(int(g[0]) != w for w in waits):
                _fail("limit statement %s does not match the waiting rule %s: %s" % (g[0], waits, text))
            if len(g) > 1 and int(g[1]) != int(g[0]) - 1:
                _fail("odd limit statement: " + text)
        elif kind == "setclass1":
            if ch_nos != [int(g[0])]:
                _fail("class-changing rule numbers %s vs text %s" % (ch_nos, text))
        elif kind == "setclass2":
            if ch_nos != [int(g[0]), int(g[1])]:
                _fail("class-changing rule numbers %s vs text %s" % (ch_nos, text))
        elif kind == "first1":
            if ch_nos != [int(g[0])] or int(g[1]) != ch_nos[-1] + 1:
                _fail("apply-first statement does not fit: " + text)
        elif kind == "first2":
            if ch_nos != [int(g[0]), int(g[1])] or int(g[2]) != ch_nos[-1] + 1:
                _fail("apply-first statement does not fit: " + text)
        elif kind == "waitcol":
            if g[0] != roles["arrival"]:
                _fail("waiting time counted from %r, arrival column is %r" % (g[0], roles["arrival"]))
        elif kind in ("combo_add", "combo_one"):
            if len(ch_nos) != 2 or [int(g[0]), int(g[1])] != ch_nos:
                _fail("combination statement does not fit the class-changing rules: " + text)
            if kind == "combo_add":
                info["top"].add(int(g[2]))
            info["combo"] = "add" if kind == "combo_add" else "one"
        elif kind == "combo_add1":
            if len(ch_nos) != 2:
                _fail("combination statement with %d class-changing rules" % len(ch_nos))
            info["top"].add(int(g[0]))
            info["combo"] = "add"
        elif kind == "arr_unique":
            if g[0] != roles["arrival"]:
                _fail("uniqueness stated for column %r, arrival column is %r" % (g[0], roles["arrival"]))
            if len(set(c["arr"] for c in cases)) != len(cases):
                info["false"].append("state says arrival times are all different; they are not")
        elif kind == "arr_unique_last":
            if g[0] != roles["arrival"] or rules[-1]["kind"] != "arrival":
                _fail("uniqueness statement for the last rule does not fit: " + text)
            if len(set(c["arr"] for c in cases)) != len(cases):
                info["false"].append("state says arrival times are all different; they are not")
        elif kind == "due_col":
            if "appt" not in roles or g[0] != roles["appt"]:
                _fail("due defined on column %r, appointment column is %r" % (g[0], roles.get("appt")))
        elif kind in ("due_phrase", "due_level", "due_level2", "due_level3"):
            if not ph_ok(g[0]):
                _fail("due statement about %r, appointment column is %r" % (g[0], roles.get("appt")))
            if kind == "due_level" and g[1] != roles["appt"]:
                _fail("due statement names column %r, appointment column is %r" % (g[1], roles.get("appt")))
    return info


# ---------------------------------------------------------------------------------------------------- the order
def analyse(state, drop=()):
    """`drop`: rule numbers to leave out (used only by the ablation study in the audit notes; solve() never drops)."""
    parts = split_state(state)
    now = _mins(parts["now"][0])
    pos = POS[parts["asked"][0]]
    fields, roles = parse_fields(parts["fields"][0][1])
    count = int(parts["list"][0][2])
    names, raw = parse_list(parts["list"][0][1], count)
    cases = build_cases(names, raw, fields, roles)
    rules = parse_rules(parts["rules"][0][1], fields, roles)
    info = check_notes(parts["notes"][0][1], rules, roles, fields, cases)

    changers = [r for r in rules if r["kind"] in ("wait", "flag")]
    for r in rules:                                    # class changers come first, as every convention says
        if r["kind"] in ("wait", "flag") and any(x["kind"] not in ("wait", "flag") for x in rules[:r["no"] - 1]):
            _fail("a class-changing rule stands after an ordering rule")
    top = None
    if changers:
        if len(info["top"]) != 1:
            _fail("floor class stated %s times/values %s" % (len(info["top"]), sorted(info["top"])))
        top = next(iter(info["top"]))
        if len(changers) == 2 and info["combo"] is None:
            _fail("two class changes but no statement on how they combine")
    if len(changers) < 2 and info["combo"] is not None:
        _fail("combination statement without two class-changing rules")

    eff = [r for r in rules if r["no"] not in drop]
    act = [r for r in eff if r["kind"] in ("wait", "flag")]
    for c in cases:                                    # class after the class-changing rules
        met = 0
        for r in act:
            if r["kind"] == "wait" and now - c["arr"] >= r["W"]:
                met += 1
            if r["kind"] == "flag" and c["flag"] == r["flag"]:
                met += 1
        up = met if info["combo"] == "add" else min(met, 1)
        c["cls2"] = max(top, c["cls"] - up) if top is not None else c["cls"]

    def due(c):
        return c["appt"] is not None and c["appt"] <= now

    def precedes(a, b):
        """-1 if a stands before b, +1 if b stands before a, 0 if every rule leaves them level."""
        for r in eff:
            k = r["kind"]
            if k in ("wait", "flag"):
                continue
            if k == "class":
                x, y = a["cls2"], b["cls2"]
            elif k == "arrival":
                x, y = a["arr"], b["arr"]
            elif k == "appt":
                if a["cls2"] != b["cls2"] and not drop:
                    _fail("appointment rule reached for cases of different classes")
                x, y = (0 if due(a) else 1), (0 if due(b) else 1)
            elif k == "dur":
                x, y = a["dur"], b["dur"]
            elif k == "ticket":
                x, y = a["num"], b["num"]
            else:
                _fail("rule kind " + k)
            if x != y:
                return -1 if x < y else 1
        return 0

    ties = [(a["id"], b["id"]) for i, a in enumerate(cases) for b in cases[i + 1:] if precedes(a, b) == 0]
    # order by duels: the case that beats every remaining case is next
    rest, order = list(cases), []
    while rest:
        winners = [x for x in rest if all(precedes(x, y) < 0 for y in rest if y is not x)]
        if len(winners) != 1:
            break
        order.append(winners[0])
        rest.remove(winners[0])
    return {"order": [c["id"] for c in order], "complete": not rest, "ties": ties, "pos": pos, "cases": cases,
            "false_statements": info["false"]}


def solve(state, question, options):
    if not re.match(r"^Which waiting case do the rules (?:put at the position asked for in the state|select)\?$", question.strip()):
        _fail("question not recognised: %r" % question[:100])
    res = analyse(state)
    ids = set(c["id"] for c in res["cases"])
    pos = res["pos"]
    if len(res["order"]) < pos:
        raise NotTotalOrder("the rules leave cases level at or before position %d: %s" % (pos, res["ties"][:3]))
    ans = res["order"][pos - 1]
    keys = {}
    for k, txt in options.items():
        named = [i for i in ids if re.search(r"(?<![A-Za-z0-9-])" + re.escape(i) + r"(?![0-9])", str(txt))]
        if len(named) != 1:
            _fail("option %r: its text names %d cases of the queue: %s" % (k, len(named), named))
        if k in ids and k != named[0]:
            _fail("option key %r but its text names %r" % (k, named[0]))
        if named[0] in keys:
            _fail("two options name the same case " + named[0])
        keys[named[0]] = k
    if ans not in keys:
        _fail("the case at position %d (%s) is not among the options" % (pos, ans))
    return keys[ans]
