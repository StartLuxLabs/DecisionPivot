"""Independent second solver for the task `answerable_facts` (label audit of gen_v4).

Written from the rendered text alone.  The state is {"facts": <rules of reading + table>, "question": <one question>},
the instruction is "Can the question be answered from the facts listed?", the options are yes / no.

Method (not the generator's): the question is parsed into a small expression tree (a reference to an organisation:
the organisation itself, "the <parent label> of <ref>", "its <parent label>", "the only subsidiary of <org>"; and an
operation: look up an attribute, compare two attributes, total an attribute over the listed subsidiaries).  The
tree is then evaluated against the table the way the rules of reading prescribe, and every fact it touches is
logged as "needed"; the answer is yes exactly when no needed fact is missing.  Rules of reading are PARSED from the
state (closed world, links only through the parent row, a figure per organisation, and the one inherited fact with
its label); an unknown sentence or row raises.
"""
import re

QUESTION = "Can the question be answered from the facts listed?"
YES_TEXT = "Every fact the question needs is listed."
NO_TEXT = "At least one fact the question needs is not listed."

# attribute labels as they appear in the rendered tables (all label sets); used only to recognise the phrase in the
# question; the meaning of a label (parent link, inherited fact) comes from the rules of reading in the state.
LABELS = [
    "foundation year", "year of founding", "year founded", "founding year",
    "main office", "head office", "headquarters", "registered office",
    "parent company", "parent group", "parent body", "parent organisation",
    "staff count", "head count", "workforce size", "number of employees",
    "core product", "main product", "product line", "flagship product",
    "site count", "location count", "number of sites", "number of locations",
    "CEO", "managing director", "top executive", "chief executive",
    "home region", "base region", "operating region", "region of operation",
]
NUMBERS = {"two": 2, "three": 3, "four": 4}

CLOSED_RULES = [
    r"These rows are everything that is known, and nothing outside them may be assumed\.",
    r"Use only the rows below; a fact that has no row is unknown\.",
    r"The table is the only source, and a fact without a row cannot be used\.",
    r"Answer from the rows alone: whatever has no row is not available\.",
]
FIGURE_RULES = [
    r"For a comparison or a sum, each organisation involved must have its own figure; the totals, differences or "
    r"averages of other figures do not replace it\.",
    r"Every organisation in a comparison or a total needs a figure of its own in a row; a figure is never calculated "
    r"from other rows\.",
    r"Each figure must have its own row: a figure is never taken from the figures of other organisations, and a "
    r"comparison or a total needs all the figures it covers\.",
    r"A comparison or a total needs the figure of every organisation it covers, and no figure can be worked out from "
    r"other figures\.",
]
LINK_RULES = [   # group p = label of the link row
    r"Do not infer links from names; an organisation counts as a subsidiary of another only when its (?P<p>.+?) row "
    r"names it\.",
    r"Links exist only where a row states them: an organisation is a subsidiary of X only if it has a (?P<p>.+?) row "
    r"that names X, and similar names do not count\.",
    r"An? (?P<p>.+?) row is the only evidence of a link between two organisations; an organisation is a subsidiary of "
    r"another only if its own (?P=p) row names it\.",
    r"Organisations are related only where a row says so: an? (?P<p>.+?) row makes an organisation a subsidiary of "
    r"the one it names, and a shared family name proves nothing\.",
]
INHERIT_RULES = [   # group r = label of the inherited fact
    r"An organisation without an? (?P<r>.+?) row shares the (?P=r) of its parent, as long as the parent has an? "
    r"(?P=r) row of its own\. Nothing else is inherited\.",
    r"The (?P<r>.+?) is the one fact that is inherited: when an organisation has no (?P=r) row, it takes the (?P=r) "
    r"of its parent, if the parent has an? (?P=r) row of its own\.",
    r"If an organisation has no (?P<r>.+?) row, its (?P=r) is that of its parent, but only when the parent has an? "
    r"(?P=r) row; no other fact is taken over from a parent\.",
    r"One exception: an organisation that has no row for its (?P<r>.+?) takes over the (?P=r) of its parent, "
    r"provided the parent has a row for its own (?P=r)\.",
]

ROW_LAYOUTS = {
    "numbered": re.compile(r"^(?P<n>\d+)\. (?P<e>.+?) \| (?P<a>.+?) \| (?P<v>.+)$"),
    "dots": re.compile(r"^(?P<e>.+?) · (?P<a>.+?) · (?P<v>.+)$"),
    "dashes": re.compile(r"^- (?P<e>.+?) — (?P<a>.+?): (?P<v>.+)$"),
    "pipes": re.compile(r"^\| (?P<e>.+?) \| (?P<a>.+?) \| (?P<v>.+?) \|$"),
}
HEADERS = ("Entity · Attribute · Value", "| Entity | Attribute | Value |", "|---|---|---|")


class Unreadable(Exception):
    pass


# ----------------------------------------------------------------------------------------------------------------
class Table:
    def __init__(self, text):
        lines = text.split("\n")
        self.rules = {"closed": [], "figure": [], "link": [], "inherit": []}
        self.par = None          # label of the link row
        self.reg = None          # label of the inherited fact
        rows = []
        layout = None
        for i, ln in enumerate(lines):
            if not ln.strip():
                raise Unreadable("empty line %d" % i)
            kind = self._rule(ln)
            if kind:
                if rows:
                    raise Unreadable("rule after the table started: %r" % ln[:60])
                continue
            if ln in HEADERS:
                continue
            hit = None
            for name, rx in ROW_LAYOUTS.items():
                m = rx.match(ln)
                if m:
                    hit = (name, m)
                    break
            if hit is None:
                raise Unreadable("unrecognised line %d: %r" % (i, ln[:80]))
            name, m = hit
            if layout is None:
                layout = name
            elif layout != name:
                raise Unreadable("mixed layouts %s / %s" % (layout, name))
            if name == "numbered" and int(m["n"]) != len(rows) + 1:
                raise Unreadable("row numbering broken at %r" % ln[:40])
            rows.append((m["e"], m["a"], m["v"]))
        for k in ("closed", "figure", "link", "inherit"):
            if len(self.rules[k]) != 1 and k != "inherit":
                raise Unreadable("rule group %r found %d times" % (k, len(self.rules[k])))
        if len(self.rules["inherit"]) > 1:
            raise Unreadable("inheritance rule found twice")
        if not rows:
            raise Unreadable("no rows")
        self.rows = rows
        self.facts = {}
        for e, a, v in rows:
            if (e, a) in self.facts:
                raise Unreadable("two rows for %s / %s" % (e, a))
            self.facts[(e, a)] = v
        # every attribute label of the table must be a known label (so that no row is silently another kind of fact)
        for e, a, v in rows:
            if a not in LABELS:
                raise Unreadable("unknown attribute label %r" % a)
        if self.par not in LABELS[8:12]:
            raise Unreadable("link label %r of the rules is not a parent label" % self.par)
        for e, a, v in rows:       # a row of another parent-type label would be a link the rules do not recognise
            if a in LABELS[8:12] and a != self.par:
                raise Unreadable("row with the link label %r, but the rules speak of %r" % (a, self.par))
        if self.reg is not None and self.reg not in LABELS:
            raise Unreadable("inherited label %r unknown" % self.reg)
        # entities: subjects of rows and everything a link row names
        self.ents = {e for e, _, _ in rows} | {v for e, a, v in rows if a == self.par}
        for e in self.ents:
            if not re.fullmatch(r"[A-Z][a-z]+ [A-Z][a-z]+", e):
                raise Unreadable("odd organisation name %r" % e)
        # a parent row names another organisation; no organisation is its own ancestor
        self.parent = {e: v for e, a, v in rows if a == self.par}
        for e in self.parent:
            seen, cur = {e}, e
            while cur in self.parent:
                cur = self.parent[cur]
                if cur in seen:
                    raise Unreadable("link cycle at %s" % e)
                seen.add(cur)
        # numeric attributes hold plain integers only
        for e, a, v in rows:
            if re.fullmatch(r"\d+", v):
                continue
            if is_figure(a):
                raise Unreadable("figure row with a non-integer value: %s / %s / %s" % (e, a, v))

    def _rule(self, ln):
        for k, group in (("closed", CLOSED_RULES), ("figure", FIGURE_RULES), ("link", LINK_RULES),
                         ("inherit", INHERIT_RULES)):
            for rx in group:
                m = re.fullmatch(rx, ln)
                if m:
                    self.rules[k].append(ln)
                    if k == "link":
                        self.par = m["p"]
                    if k == "inherit":
                        self.reg = m["r"]
                    return k
        return None

    # --- evaluation ---------------------------------------------------------------------------------------------
    def children(self, org):
        return sorted(c for c, p in self.parent.items() if p == org)


class Eval:
    """Evaluates one question; `needed` collects (organisation, label, listed?) for each fact it asked for."""

    def __init__(self, table):
        self.t = table
        self.needed = []

    def ask(self, org, label):
        v = self.t.facts.get((org, label))
        self.needed.append((org, label, v is not None))
        return v

    def value(self, org, label):
        """Value of `label` for `org`, honouring the one inherited fact (one step through a listed parent row)."""
        v = self.ask(org, label)
        if v is not None:
            return v
        if self.t.reg is not None and label == self.t.reg:
            par = self.ask(org, self.t.par)
            if par is None:
                return None
            return self.ask(par, label)
        return None

    def resolve(self, ref):
        kind = ref[0]
        if kind == "org":
            if ref[1] not in self.t.ents:
                raise Unreadable("organisation %r is not in the table" % ref[1])
            return ref[1]
        if kind == "parent":
            child = self.resolve(ref[1])
            if child is None:
                return None
            return self.ask(child, self.t.par)
        if kind == "only_sub":
            org = self.resolve(("org", ref[1]))
            subs = self.t.children(org)
            if len(subs) > 1:
                raise Unreadable("'the only subsidiary of %s' but the table lists %d" % (org, len(subs)))
            if not subs:
                self.needed.append((org, "(a subsidiary row naming it)", False))
                return None
            self.needed.append((subs[0], self.t.par, True))
            return subs[0]
        raise Unreadable("bad reference %r" % (ref,))


# ----------------------------------------------------------------------------------------------------------------
def is_figure(label):
    """Founding year, head count and number of sites are the figures (the rest of the labels hold names)."""
    return label in LABELS[0:4] + LABELS[12:16] + LABELS[20:24]


def _alt(words):
    return "|".join(re.escape(w) for w in sorted(set(words), key=lambda w: (-len(w), w)))


def _templates(t):
    A = "(?P<a>%s)" % _alt(LABELS)
    P = re.escape(t.par)
    E = "(?P<e>%s)" % _alt(t.ents)
    E1 = "(?P<e1>%s)" % _alt(t.ents)
    E2 = "(?P<e2>%s)" % _alt(t.ents)
    D = "(?P<d>greater|smaller)"
    NP = "(?P<np>.+)"
    NP1L = "(?P<np1>.+?)"
    NP2 = "(?P<np2>.+)"
    return [
        # --- look-ups
        ("look", r"Looking at %s: what is its %s\?" % (E, A)),
        ("look", r"State the %s of %s\." % (A, NP)),
        ("look", r"Give the %s of %s\." % (A, NP)),
        ("look", r"What is the %s of %s\?" % (A, NP)),
        ("look", r"For %s, what is the %s\?" % (NP, A)),
        ("look1", r"Look up the %s of %s and report its %s\." % (P, E, A)),
        ("look1", r"Find the %s of %s, then state its %s\." % (P, E, A)),
        ("look_sub", r"Find the one listed subsidiary of %s and state its %s\." % (E, A)),
        ("look2", r"Starting at %s, go to its %s, then to that organisation's %s, and state the %s of the one you "
                  r"reach\." % (E, P, P, A)),
        ("lookn", r"Starting at %s, follow the %s link (?P<n>two|three|four) times and state the %s of the "
                  r"organisation you reach\." % (E, P, A)),
        # --- comparisons
        ("cmp_ee", r"Compare %s and %s: which one has the %s %s\?" % (E1, E2, D, A)),
        ("cmp_ee", r"Which has the %s %s: %s or %s\?" % (D, A, E1, E2)),
        ("cmp_np", r"Is the %s of %s %s than the (?P=a) of %s\?" % (A, NP1L, D, NP2)),
        ("cmp_np", r"Which is %s: the %s of %s or the (?P=a) of %s\?" % (D, A, NP1L, NP2)),
        ("cmp_np", r"Does %s have an? %s %s than %s\?" % (NP1L, D, A, NP2)),
        ("cmp_np", r"Compare the %s of %s with the (?P=a) of %s: which is %s\?" % (A, NP1L, "(?P<np2>.+?)", D)),
        ("cmp_its", r"Compare %s with its %s: which has the %s %s\?" % (NP1L, P, D, A)),
        # --- totals
        ("sum", r"Add up the %s of every subsidiary of %s that the table lists\." % (A, E)),
        ("sum", r"What is the combined %s of the listed subsidiaries of %s\?" % (A, E)),
        ("sum", r"Give the total %s of the subsidiaries of %s listed in the table\." % (A, E)),
        ("sum", r"What do the listed subsidiaries of %s have as a combined %s\?" % (E, A)),
    ]


def parse_ref(t, s, subject=None):
    s = s.strip()
    if s in t.ents:
        return ("org", s)
    m = re.fullmatch(r"the %s of (.+)" % re.escape(t.par), s)
    if m:
        return ("parent", parse_ref(t, m.group(1), subject))
    if re.fullmatch(r"its %s" % re.escape(t.par), s):
        if subject is None or subject[0] != "org":
            raise Unreadable("'its %s' without a plain organisation as its subject" % t.par)
        return ("parent", subject)
    for rx in (r"the only subsidiary listed for (.+)", r"the only subsidiary of (.+) that the table lists",
               r"the only listed subsidiary of (.+)", r"the one listed subsidiary of (.+)"):
        m = re.fullmatch(rx, s)
        if m and m.group(1) in t.ents:
            return ("only_sub", m.group(1))
    raise Unreadable("cannot read the reference %r" % s)


def parse_question(t, q):
    hits = []
    for kind, rx in _templates(t):
        m = re.fullmatch(rx, q)
        if m:
            hits.append((kind, m))
    if not hits:
        raise Unreadable("unrecognised question: %r" % q)
    # a question may be matched by several templates only if they read it the same way (e.g. greedy splits)
    parsed = []
    for kind, m in hits:
        try:
            parsed.append(_build(t, kind, m))
        except Unreadable as exc:
            parsed.append(exc)
    good = [p for p in parsed if not isinstance(p, Exception)]
    if not good:
        raise parsed[0]
    first = good[0]
    for g in good[1:]:
        if g != first:
            raise Unreadable("question read two ways: %r / %r" % (first, g))
    return first


def _build(t, kind, m):
    a = m["a"]
    if kind in ("look", "look_sub", "look1", "look2", "lookn"):
        if kind == "look":
            ref = parse_ref(t, m["np"]) if "np" in m.groupdict() else ("org", m["e"])
        elif kind == "look_sub":
            ref = ("only_sub", m["e"])
        elif kind == "look1":
            ref = ("parent", ("org", m["e"]))
        elif kind == "look2":
            ref = ("parent", ("parent", ("org", m["e"])))
        else:
            ref = ("org", m["e"])
            for _ in range(NUMBERS[m["n"]]):
                ref = ("parent", ref)
        return ("look", ref, a)
    if kind == "cmp_ee":
        return ("cmp", ("org", m["e1"]), ("org", m["e2"]), a, m["d"])
    if kind == "cmp_np":
        r1 = parse_ref(t, m["np1"])
        r2 = parse_ref(t, m["np2"], subject=r1)
        return ("cmp", r1, r2, a, m["d"])
    if kind == "cmp_its":
        r1 = parse_ref(t, m["np1"])
        return ("cmp", r1, ("parent", r1), a, m["d"])
    if kind == "sum":
        return ("sum", m["e"], a)
    raise Unreadable("template kind %r" % kind)


def closure_answer(t, qn):
    """Second route to the same answer: first close the table under the rules (the one inherited fact, one step),
    then answer the question by plain look-ups in the closed table.  True = every needed fact is available."""
    known = dict(t.facts)
    if t.reg is not None:
        for org in sorted(t.ents):
            p = t.parent.get(org)
            if (org, t.reg) not in t.facts and p is not None and (p, t.reg) in t.facts:
                known[(org, t.reg)] = t.facts[(p, t.reg)]
    kids = {}
    for c_, p_ in t.parent.items():
        kids.setdefault(p_, []).append(c_)

    def walk(ref):                       # organisation reached, or None when a link row is missing
        if ref[0] == "org":
            return ref[1]
        if ref[0] == "parent":
            o = walk(ref[1])
            return None if o is None else known.get((o, t.par))
        if ref[0] == "only_sub":
            ks = kids.get(ref[1], [])
            return ks[0] if len(ks) == 1 else None
        raise Unreadable("bad reference")

    if qn[0] == "look":
        o = walk(qn[1])
        return o is not None and (o, qn[2]) in known
    if qn[0] == "cmp":
        os_ = [walk(qn[1]), walk(qn[2])]
        return all(o is not None and (o, qn[3]) in known for o in os_)
    if qn[0] == "sum":
        return all((c_, qn[2]) in known for c_ in kids.get(qn[1], []))
    raise Unreadable("bad question")


def explain(state, question="Can the question be answered from the facts listed?"):
    """(answer 'yes'/'no', list of needed facts) - used for diagnosis, and by solve()."""
    t = Table(state["facts"])
    qn = parse_question(t, state["question"])
    ev = Eval(t)
    ok = True
    if qn[0] == "look":
        org = ev.resolve(qn[1])
        ok = org is not None and ev.value(org, qn[2]) is not None
    elif qn[0] == "cmp":
        if not is_figure(qn[3]):
            raise Unreadable("a comparison of a non-figure (%s)" % qn[3])
        vals = []
        for ref in (qn[1], qn[2]):
            org = ev.resolve(ref)
            vals.append(None if org is None else ev.value(org, qn[3]))
        ok = all(v is not None for v in vals)
        if ok:
            for v in vals:
                if not re.fullmatch(r"\d+", v):
                    raise Unreadable("comparison of a non-figure value %r" % v)
    elif qn[0] == "sum":
        if not is_figure(qn[2]):
            raise Unreadable("a total of a non-figure (%s)" % qn[2])
        org = ev.resolve(("org", qn[1]))
        subs = t.children(org)
        if not subs:
            raise Unreadable("a total over the subsidiaries of %s, but none is listed" % org)
        for s in subs:
            ev.needed.append((s, t.par, True))
        vals = [ev.value(s, qn[2]) for s in subs]
        ok = all(v is not None for v in vals)
        if ok:
            for v in vals:
                if not re.fullmatch(r"\d+", v):
                    raise Unreadable("total over a non-figure value %r" % v)
    if ok != closure_answer(t, qn):
        raise Unreadable("the two evaluation routes disagree")
    # every organisation the question names must be mentioned by the table
    return ("yes" if ok else "no"), ev.needed


def solve(state, question, options):
    if question.strip() != QUESTION:
        raise Unreadable("unexpected instruction %r" % question)
    pos = [k for k, v in options.items() if v == YES_TEXT]
    neg = [k for k, v in options.items() if v == NO_TEXT]
    if len(pos) != 1 or len(neg) != 1 or len(options) != 2:
        raise Unreadable("unexpected options %r" % (dict(options),))
    ans, needed = explain(state)
    return pos[0] if ans == "yes" else neg[0]
