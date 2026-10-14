"""Independent second solver for the task dep_resolve (does the proposed set of pinned versions install cleanly?).

Written from the rendered text alone.  The state has five paragraphs: introduction, conventions, environment, index,
pins.  Every sentence of the conventions is matched against a catalogue of the phrasings that occur; the meaning of the
operators, the version order, the list of conditions of "installs cleanly" and the meaning of a conflict entry are TAKEN
FROM THOSE SENTENCES (an unknown sentence raises).  The index is read in its three layouts (one fact per line, version
lines separated by '|', markdown table), the pins in all their layouts.  Nothing is skipped silently: every unknown line
raises ValueError.

    solve(state, question, options) -> option key
"""
import html
import re

NOUN = r"(?:packages?|plugins?|modules?|components?|extensions?)"
REGS = r"(?:package index|plugin registry|module feed|component depot|extension catalogue)"
VERB = r"(?:depends on|needs|requires)"
CTERM = r"(?:conflicts with|clashes with|cannot be combined with)"
RTKEY = r"(?:runtime range|supported runtime|runtime)"
OPS = r"(?:>=|<=|==|!=|>|<)"
VER = r"\d+(?:\.\d+)*"
BOUND = OPS + VER
BOUNDS = BOUND + r"(?:," + BOUND + r")*"
NAME = r"[a-z]+(?:-[a-z]+)*"


def bad(msg):
    raise ValueError(msg)


# ----------------------------------------------------------------------------------------------------- versions
def vt(s):
    if not re.fullmatch(VER, s):
        bad("not a version: %r" % s)
    return tuple(int(p) for p in s.split("."))


def compare(a, b):
    """number-by-number comparison from the left, every number as a whole number; -1 / 0 / +1"""
    if len(a) != len(b):
        bad("versions with a different number of parts: %r %r" % (a, b))
    for x, y in zip(a, b):
        if x < y:
            return -1
        if x > y:
            return 1
    return 0


def _padded(v):                       # second, independent way: fixed-width text per number, compared as text
    return ".".join("%09d" % n for n in v)


def cmp_checked(a, b):
    c = compare(a, b)
    pa, pb = _padded(a), _padded(b)
    c2 = -1 if pa < pb else (1 if pa > pb else 0)
    assert c == c2, "internal: two comparisons disagree"
    return c


# meaning of the phrases that define an operator in the three phrasings
PHRASE = {
    "at least": "ge", "that version or newer": "ge", "at least V": "ge",
    "strictly newer": "gt", "newer only": "gt", "newer than V": "gt",
    "at most": "le", "that version or older": "le", "at most V": "le",
    "strictly older": "lt", "older only": "lt", "older than V": "lt",
    "exactly this version": "eq", "only that version": "eq", "exactly V": "eq",
    "anything but this version": "ne", "every version but that one": "ne", "any version except V": "ne",
}
MEANING = {
    "ge": lambda c: c >= 0, "gt": lambda c: c > 0, "le": lambda c: c <= 0,
    "lt": lambda c: c < 0, "eq": lambda c: c == 0, "ne": lambda c: c != 0,
}


def parse_bounds(text):
    out = []
    for part in text.split(","):
        m = re.fullmatch("(" + OPS + ")(" + VER + ")", part)
        if not m:
            bad("bad bound %r" % part)
        out.append((m.group(1), vt(m.group(2))))
    return out


# ----------------------------------------------------------------------------------------------------- conventions
def norm_sentence(s):
    s = re.sub(REGS, "REG", s, flags=re.I)
    s = re.sub(r"\b(?:a|an) (" + NOUN + r")\b", r"\1", s)
    s = re.sub(r"\b" + NOUN + r"\b", "NOUN", s)
    return s


ORDER = [
    r"Versions are compared number by number from the left, each number as a whole number: 1\.10\.0 is newer than 1\.9\.3, and 2\.0\.0 is newer than 1\.12\.7\.",
    r"Versions are ordered part by part as integers, not as text: 3\.10\.0 is later than 3\.9\.9, and 2\.0\.0 is later than 1\.15\.2\.",
    r"To order two versions, compare the first numbers, then the second, then the third, always as whole numbers, so 0\.10\.1 comes after 0\.9\.8 and 1\.2\.10 after 1\.2\.9\.",
]
ORDER_RT = [
    r" Runtime versions \(two parts\) follow the same order, so 4\.11 is later than 4\.9\.",
    r" Runtime versions have two numbers and are compared the same way \(3\.10 is newer than 3\.9\)\.",
    r" The same holds for the two-part runtime versions: 2\.10 comes after 2\.9\.",
]
OP_SENT = [
    (r"Bounds read as follows: (?P<defs>.+?); where several bounds follow one name, all of them apply\."),
    (r"Each bound is an operator and a version: (?P<defs>.+?); a list of bounds is met only when each bound is met\."),
    (r"After NOUN name come one or more bounds separated by commas, and every bound must hold: (?P<defs>.+?)\."),
]
CLEAN_1 = (r"A clean install needs all of the following: each pin is a version that the REG lists; "
           r"for each pinned version, each NOUN it (?P<verb>" + VERB + r") is pinned too, at a version inside the stated bounds"
           r"(?P<rt>; the runtime of the environment satisfies the runtime bounds of all pinned versions)?"
           r"(?:; no pinned version has a '(?P<ct>" + CTERM + r")' entry that applies to another pin)?\.")
CLEAN_2 = (r"The proposed set installs cleanly when every pinned version is listed in the REG(?:,| and) "
           r"every requirement of every pinned version names NOUN that is pinned at a version meeting all of its bounds"
           r"(?P<rt>,? (?:and )?the runtime of the target environment meets every runtime bound of every pinned version)?"
           r"(?P<cf>,? and no conflict entry of a pinned version applies to another pin)?\.")
CLEAN_3 = (r"The set is clean only if the REG lists every pinned version(?:,| and) "
           r"every requirement of a pinned version is met by the pin of the required NOUN"
           r"(?P<rt>, (?:and )?each runtime bound of a pinned version holds for the environment's runtime)?"
           r"(?P<cf>, and none of the pinned versions has a conflict entry that applies to another pin)?\.")

SIMPLE = {
    "only_entries": [
        r"Only the entries of the pinned versions count; what the REG says about other versions plays no part\.",
        r"Entries of versions that are not pinned are irrelevant\.",
        r"Requirements and other entries of versions without a pin do not matter\.",
    ],
    "unpinned_unmet": [
        r"No NOUN is added automatically: if a pinned version requires NOUN that has no pin, that requirement fails\.",
        r"Nothing is installed besides the pins, so a requirement on NOUN without a pin is not met\.",
        r"Only pinned NOUN get installed; a required NOUN that has no pin counts as unmet\.",
    ],
    "extra_pins": [
        r"Extra pins are fine: a pinned NOUN that nothing requires is harmless as long as its own entry is satisfied\.",
        r"Pinning NOUN that nothing needs is allowed, but the entry of that pinned version must still be met\.",
        r"A pin that no pinned version requires does no harm by itself; its own entry is checked like that of every other pin\.",
    ],
    "runtime_sem": [
        r"A runtime bound of a pinned version is met when the runtime of the target environment satisfies it; 'any' sets no runtime bound\.",
        r"Runtime bounds are checked against the runtime of the target environment; a version marked 'any' runs on every runtime\.",
        r"The environment's runtime must satisfy each runtime bound of each pinned version \('any' means no bound\)\.",
    ],
}
CONF_SENT = [
    (r"An entry '(?P<ct>" + CTERM + r") P B' under a pinned version means that the set fails when P is pinned at a version "
     r"meeting the bound B; it does not matter which of the two lists it, and an entry about NOUN without a pin, or whose pin "
     r"misses B, does no harm\."),
    (r"Conflicts \('(?P<ct>" + CTERM + r")'\): a pinned version that names NOUN P with a bound blocks the set exactly when P is "
     r"pinned at a version meeting that bound; if P has no pin, or its pin misses the bound, nothing happens\."),
    (r"If a pinned version has a '(?P<ct>" + CTERM + r")' entry naming another NOUN and that NOUN is pinned at a version inside "
     r"the given bound, the set is not clean \(whichever side lists it\); entries about NOUN that are not pinned, or whose pin "
     r"lies outside the bound, are harmless\."),
]


def parse_conventions(par):
    lines = par.split("\n")
    if not re.fullmatch(r"(Conventions|Rules of this check|How to read the entries and when a set is clean):", lines[0]):
        bad("unknown convention header %r" % lines[0])
    conv = {"order": False, "order_rt": False, "ops": None, "listed": False, "reqs": False, "runtime": False,
            "conflicts": False, "conf_term": None, "verb": None, "tags": set(), "terms": set()}
    for raw in lines[1:]:
        s = re.sub(r"^(?:\* |- |\d+\. )", "", raw)
        s = norm_sentence(s)
        done = False
        for o in ORDER:
            m = re.fullmatch(o + "(" + "|".join(ORDER_RT) + ")?", s)
            if m:
                conv["order"] = True
                if m.group(1):
                    conv["order_rt"] = True
                done = True
        if done:
            continue
        for o in OP_SENT:
            m = re.fullmatch(o, s)
            if m:
                ops = {}
                for item in re.split(r", ", m.group("defs")):
                    mm = re.fullmatch("(" + OPS + r")V?\s*\(?(.+?)\)?", item)
                    if not mm or mm.group(2) not in PHRASE:
                        bad("unknown operator definition %r" % item)
                    ops[mm.group(1)] = MEANING[PHRASE[mm.group(2)]]
                if set(ops) != {">=", ">", "<=", "<", "==", "!="}:
                    bad("operator definitions incomplete: %r" % sorted(ops))
                conv["ops"] = ops
                done = True
        if done:
            continue
        for c in (CLEAN_1, CLEAN_2, CLEAN_3):
            m = re.fullmatch(c, s)
            if m:
                d = m.groupdict()
                conv["listed"] = conv["reqs"] = True
                conv["runtime"] = bool(d.get("rt"))
                if "cf" in d:
                    conv["conflicts"] = bool(d.get("cf"))
                else:
                    conv["conflicts"] = bool(d.get("ct"))
                if d.get("ct"):
                    conv["terms"].add(d["ct"])
                if d.get("verb"):
                    conv["verb"] = d["verb"]
                done = True
        if done:
            continue
        for tag, pats in SIMPLE.items():
            for p in pats:
                if re.fullmatch(p, s):
                    conv["tags"].add(tag)
                    done = True
        if done:
            continue
        for p in CONF_SENT:
            m = re.fullmatch(p, s)
            if m:
                conv["tags"].add("conflict_sem")
                conv["terms"].add(m.group("ct"))
                done = True
        if done:
            continue
        bad("unknown convention sentence: %r" % raw)
    # what must have been said
    for k in ("order", "ops", "listed"):
        if not conv[k]:
            bad("convention missing: %s" % k)
    for t in ("only_entries", "unpinned_unmet", "extra_pins"):
        if t not in conv["tags"]:
            bad("convention missing: %s" % t)
    if conv["runtime"] and not ("runtime_sem" in conv["tags"] and conv["order_rt"]):
        bad("runtime is a condition but its convention sentences are missing")
    if len(conv["terms"]) > 1:
        bad("two different conflict terms in the conventions")
    if conv["terms"]:
        conv["conf_term"] = next(iter(conv["terms"]))
    if conv["conflicts"] and "conflict_sem" not in conv["tags"]:
        bad("conflict condition without the sentence that defines it")
    if "conflict_sem" in conv["tags"] and not conv["conflicts"]:
        bad("conflict sentence present but conflict is not a condition")
    return conv


# ----------------------------------------------------------------------------------------------------- introduction, environment
def parse_intro(par):
    pats = [
        r"An? [a-z ]+ called (?P<env>[a-z]+-\d+) is to receive " + NOUN + r" from the (?P<reg>" + REGS + r")\.",
        r"(?P<env>[a-z]+-\d+) \(an? [a-z ]+\) should get the " + NOUN + r" listed under the pins, drawn from the (?P<reg>" + REGS + r")\.",
        r"Proposed install on (?P<env>[a-z]+-\d+), an? [a-z ]+: the " + NOUN + r" pinned at the end, taken from the (?P<reg>" + REGS + r") below\.",
    ]
    for p in pats:
        m = re.fullmatch(p, par)
        if m:
            return m.group("env"), m.group("reg")
    bad("unknown introduction %r" % par[:80])


def parse_env(par):
    pats = [
        r"Target environment: (?P<env>[a-z]+-\d+)(?:, runtime (?P<rt>" + VER + r"))?\.",
        r"Install target: (?P<env>[a-z]+-\d+)(?:, running runtime (?P<rt>" + VER + r"))?\.",
        r"Environment: (?P<env>[a-z]+-\d+) \([a-z ]+\)(?:; runtime version (?P<rt>" + VER + r"))?\.",
    ]
    for p in pats:
        m = re.fullmatch(p, par)
        if m:
            return m.group("env"), (vt(m.group("rt")) if m.group("rt") else None)
    bad("unknown environment paragraph %r" % par)


# ----------------------------------------------------------------------------------------------------- the index
class Entry(object):
    def __init__(self):
        self.reqs = []          # (name, [(op, vtuple)])
        self.req_lines = 0
        self.nothing = False
        self.runtime = None     # None = not stated; [] = any; list of bounds
        self.rt_lines = 0
        self.conf = []
        self.conf_lines = 0


def new_entry(index, key):
    if key not in index:
        index[key] = Entry()
    return index[key]


def add_reqs(e, text):
    if text == "nothing":
        if e.req_lines:
            bad("'nothing' beside other requirements")
        e.nothing = True
        e.req_lines += 1
        return
    if e.nothing:
        bad("requirement beside 'nothing'")
    for item in text.split("; "):
        m = re.fullmatch("(" + NAME + ") (" + BOUNDS + ")", item)
        if not m:
            bad("bad requirement %r" % item)
        e.reqs.append((m.group(1), parse_bounds(m.group(2))))
    e.req_lines += 1


def add_runtime(e, text):
    if e.rt_lines:
        bad("two runtime statements for one version")
    e.rt_lines += 1
    e.runtime = [] if text == "any" else parse_bounds(text)


def add_conf(e, text):
    if text == "none":
        if e.conf_lines:
            bad("'none' beside other conflicts")
        e.conf_lines += 1
        return
    for item in text.split("; "):
        m = re.fullmatch("(" + NAME + ") (" + BOUNDS + ")", item)
        if not m:
            bad("bad conflict entry %r" % item)
        e.conf.append((m.group(1), parse_bounds(m.group(2))))
    e.conf_lines += 1


def parse_index(par, reg_name):
    lines = par.split("\n")
    h1 = norm_sentence(lines[0])
    if not (re.fullmatch(r"The REG lists these versions:", h1) or re.fullmatch(r"Entries of the REG:", h1)
            or re.fullmatch(r"REG \(one entry per listed version\):", h1)):
        bad("unknown index header %r" % lines[0])
    if reg_name.lower() not in lines[0].lower():
        bad("index header names another registry")
    h2 = lines[1]
    layout = None
    hdr_term = None
    if re.fullmatch(r"(On a version line, '\|' separates the entries|Entries of one version are separated by '\|'|"
                    r"Each version line gives its entries separated by '\|')\.", h2):
        layout = "pipe"
    elif re.fullmatch(r"('-' marks an empty cell|A '-' in a cell means none|Cells with '-' are empty)\.", h2):
        layout = "table"
    else:
        m = re.fullmatch(r"(?:One fact per line|Every line states one fact about one listed version|"
                         r"Each line holds a single fact about a version)"
                         r"(?:(?:[;,] (?:and )?(?:a version (?:without a|with no) '(?P<t1>" + CTERM + r")' line (?:has no such entry|declares none)"
                         r"|no '(?P<t2>" + CTERM + r")' line means none)))?\.", h2)
        if m:
            layout = "fact"
            hdr_term = m.group("t1") or m.group("t2")
        else:
            bad("unknown index header line %r" % h2)
    body = lines[2:]
    index = {}
    if layout == "fact":
        for l in body:
            m = re.fullmatch("(" + NAME + ") (" + VER + ") (" + VERB + ") (.+)", l)
            if m:
                e = new_entry(index, (m.group(1), vt(m.group(2))))
                e.verb = m.group(3)
                add_reqs(e, m.group(4))
                continue
            m = re.fullmatch("(" + NAME + ") (" + VER + ") (" + RTKEY + ") (any|" + BOUNDS + ")", l)
            if m:
                add_runtime(new_entry(index, (m.group(1), vt(m.group(2)))), m.group(4))
                continue
            m = re.fullmatch("(" + NAME + ") (" + VER + ") (" + CTERM + ") (" + NAME + " " + BOUNDS + ")", l)
            if m:
                e = new_entry(index, (m.group(1), vt(m.group(2))))
                e.conf_term = m.group(3)
                add_conf(e, m.group(4))
                continue
            bad("unknown index fact line %r" % l)
    elif layout == "pipe":
        cur = None
        seen_names = set()
        for l in body:
            m = re.fullmatch("(" + NAME + "):", l)
            if m:
                cur = m.group(1)
                if cur in seen_names:
                    bad("package listed twice: %s" % cur)
                seen_names.add(cur)
                continue
            if cur is None or not l.startswith("  "):
                bad("unknown index line %r" % l)
            parts = l[2:].split(" | ")
            ver = vt(parts[0])
            key = (cur, ver)
            if key in index:
                bad("version listed twice: %r" % (key,))
            e = new_entry(index, key)
            if len(parts) < 2:
                bad("version line without requirement part: %r" % l)
            m = re.fullmatch("(" + VERB + "): (.+)", parts[1])
            if not m:
                bad("bad requirement part %r" % parts[1])
            e.verb = m.group(1)
            add_reqs(e, m.group(2))
            for p in parts[2:]:
                m = re.fullmatch("(" + RTKEY + "): (any|" + BOUNDS + ")", p)
                if m:
                    add_runtime(e, m.group(2))
                    continue
                m = re.fullmatch("(" + CTERM + "): (none|" + NAME + " " + BOUNDS + "(?:; " + NAME + " " + BOUNDS + ")*)", p)
                if m:
                    e.conf_term = m.group(1)
                    add_conf(e, m.group(2))
                    continue
                bad("unknown part %r" % p)
    else:  # table
        hdr = None
        for l in body:
            if not l.startswith("|"):
                bad("unknown table line %r" % l)
            cells = [c.strip() for c in l.strip()[1:-1].split("|")] if l.endswith("|") else bad("table row without closing bar")
            if hdr is None:
                hdr = cells
                if len(hdr) < 3 or hdr[1] != "version" or not re.fullmatch(NOUN + "|name", hdr[0]) or not re.fullmatch(VERB, hdr[2]):
                    bad("unknown table header %r" % hdr)
                kinds = ["name", "version", "req"]
                for h in hdr[3:]:
                    if re.fullmatch(RTKEY, h):
                        kinds.append("runtime")
                    elif re.fullmatch(CTERM, h):
                        kinds.append("conf")
                    else:
                        bad("unknown table column %r" % h)
                if len(set(kinds)) != len(kinds):
                    bad("repeated table column")
                continue
            if all(re.fullmatch(r"-{3,}", c) for c in cells):
                if len(cells) != len(hdr):
                    bad("separator row width")
                continue
            if len(cells) != len(hdr):
                bad("table row width %r" % l)
            key = (cells[0], vt(cells[1]))
            if not re.fullmatch(NAME, cells[0]) or key in index:
                bad("bad or repeated table row %r" % l)
            e = new_entry(index, key)
            e.verb = hdr[2]
            if cells[2] == "-":
                add_reqs(e, "nothing")
            else:
                add_reqs(e, cells[2])
            for kind, h, c in zip(kinds[3:], hdr[3:], cells[3:]):
                if kind == "runtime":
                    if not re.fullmatch("any|" + BOUNDS, c):
                        bad("bad runtime cell %r" % c)
                    add_runtime(e, c)
                else:
                    e.conf_term = h
                    if c == "-":
                        add_conf(e, "none")
                    else:
                        add_conf(e, c)
    return index, layout, hdr_term


def index_terms(index):
    verbs = set(getattr(e, "verb", None) for e in index.values())
    terms = set(getattr(e, "conf_term", None) for e in index.values()) - {None}
    return verbs, terms


# ----------------------------------------------------------------------------------------------------- pins
def parse_pins(par):
    lines = par.split("\n")
    if not re.fullmatch(r"(Pins to install|Proposed pins|The proposal pins exactly these " + NOUN + r"):", lines[0]):
        bad("unknown pins header %r" % lines[0])
    pins = {}
    table = None
    for l in lines[1:]:
        m = None
        if l.startswith("|"):
            cells = [c.strip() for c in l.strip()[1:-1].split("|")]
            if len(cells) != 2:
                bad("pin table row width %r" % l)
            if table is None:
                if not (re.fullmatch(NOUN + "|name", cells[0]) and re.fullmatch(r"pin|pinned version|pinned at", cells[1])):
                    bad("unknown pin table header %r" % l)
                table = True
                continue
            if all(re.fullmatch(r"-{3,}", c) for c in cells):
                continue
            n, v = cells
        else:
            m = re.fullmatch(r"(?:- )?(" + NAME + r")(?: at | = | )(" + VER + ")", l)
            if not m:
                bad("unknown pin line %r" % l)
            n, v = m.group(1), m.group(2)
        if not re.fullmatch(NAME, n):
            bad("bad pin name %r" % n)
        if n in pins:
            bad("package pinned twice: %s" % n)
        pins[n] = vt(v)
    if not pins:
        bad("no pins")
    return pins


# ----------------------------------------------------------------------------------------------------- the decision
def analyse(state):
    if "&" in state:                       # HTML-escaped operators (&gt; &lt;) mean the operators themselves
        state = html.unescape(state)
    paras = state.split("\n\n")
    if len(paras) != 5:
        bad("expected five paragraphs, found %d" % len(paras))
    env_i, reg = parse_intro(paras[0])
    conv = parse_conventions(paras[1])
    env, rt = parse_env(paras[2])
    if env != env_i:
        bad("environment name differs between introduction and environment paragraph")
    index, layout, hdr_term = parse_index(paras[3], reg)
    pins = parse_pins(paras[4])

    # consistency between the conventions and the data
    verbs, terms = index_terms(index)
    if conv["verb"] is not None and verbs != {conv["verb"]}:
        bad("requirement verb differs between conventions and index")
    if len(verbs) != 1:
        bad("several requirement verbs in the index")
    if conv["conf_term"] is not None and terms and terms != {conv["conf_term"]}:
        bad("conflict term differs between conventions and index")
    any_rt = any(e.rt_lines for e in index.values())
    any_conf = any(e.conf for e in index.values())
    if any(e.req_lines == 0 for e in index.values()):
        bad("a listed version without any requirement statement")
    if conv["runtime"]:
        if rt is None:
            bad("runtime condition but the environment has no runtime")
        if any(e.rt_lines != 1 for e in index.values()):
            bad("a listed version without exactly one runtime statement")
    else:
        if any_rt or rt is not None:
            bad("runtime data present although runtime is not a condition")
    if hdr_term is not None and hdr_term != conv["conf_term"]:
        bad("conflict term of the index header differs from the conventions")
    if conv["conflicts"]:
        if any(e.conf_lines == 0 and layout != "fact" for e in index.values()):
            bad("conflict condition but a version has no conflict cell")
        if layout == "fact" and hdr_term is None:
            bad("fact layout: nothing says that a version without a conflict line has none")
    else:
        if any_conf or terms:
            bad("conflict data present although conflicts are not a condition")
    pkgs = set(k[0] for k in index)
    for (n, v), e in index.items():        # every name that an entry mentions must be a package of the index
        for rn, _ in e.reqs + e.conf:
            if rn not in pkgs:
                bad("name %r in an entry is not a package of the index" % rn)
    ops = conv["ops"]

    def holds(v, bounds):
        for op, bv in bounds:
            if not ops[op](cmp_checked(v, bv)):
                return False
        return True

    reasons = []
    for name in sorted(pins):
        ver = pins[name]
        e = index.get((name, ver))
        if e is None:                                              # (1) every pinned version is listed
            reasons.append(("unlisted", name))
            continue
        for rname, bounds in e.reqs:                               # (2) every requirement met by a pin
            if rname not in pins:
                reasons.append(("missing", name, rname))
            elif not holds(pins[rname], bounds):
                reasons.append(("bound", name, rname))
        if conv["runtime"] and not holds(rt, e.runtime):           # (3) the runtime meets every runtime bound
            reasons.append(("runtime", name))
        if conv["conflicts"]:                                      # (4) no conflict entry applies to another pin
            for cname, bounds in e.conf:
                if cname == name:
                    bad("conflict entry about the package itself")
                if cname in pins and holds(pins[cname], bounds):
                    reasons.append(("conflict", name, cname))
    return reasons


def solve(state, question, options):
    if "install cleanly" not in question:
        bad("unexpected question %r" % question)
    yes = [k for k, t in options.items() if re.match(r"yes\b", t.strip(), re.I)]
    no = [k for k, t in options.items() if re.match(r"no\b", t.strip(), re.I)]
    if len(options) != 2 or len(yes) != 1 or len(no) != 1:
        bad("cannot identify the yes / no options: %r" % (options,))
    return yes[0] if not analyse(state) else no[0]
