"""Independent second implementation for the task `record_rule` (generated record batches, version 2; gen_v4 states
carry an extra paragraph after the reference lists that says how a status column counts).

Question: "Which rule does the batch violate?"  Options: R1 ... Rk (option text = the sentence of the rule) and `none`.

The solver reads ONLY the rendered text (state, question, options):
  * parses the lead-in, the field list, the numbered rule sentences, the reference lists and the batch (JSON lines or
    a table with " | ");
  * recognises every rule sentence by its wording (sixty-odd phrasings), turns it into a small rule object and
    evaluates that rule record by record (pairwise / neighbour comparison where the rule is about several records);
  * returns the key of the one rule that is broken, or `none`.
Anything it does not recognise raises an exception (nothing is skipped silently); so does a batch in which two rules
come out broken (the text says that at most one rule is broken).
"""
import datetime
import json
import re

NONE_KEY = "none"

# ---------------------------------------------------------------------------------------------------------------
# fixed texts of the framing
# ---------------------------------------------------------------------------------------------------------------
CONVENTIONS = [
    "At most one rule is broken, and only in one place. A rule asks for exactly what its sentence says; whatever no "
    "listed rule covers is not a violation, however odd it looks.",
    "The batch breaks one of the rules at most, and then at a single spot. Only the listed rules are checked and each "
    "is read literally: data that looks odd but is covered by no rule does not count.",
    "Either every rule holds or exactly one is broken, at one spot. Nothing is a violation unless a listed rule, "
    "taken literally, forbids it.",
    "No batch breaks more than one rule, and a broken rule is broken once. Judge the batch by the listed rules alone, "
    "reading each one literally; anything they do not mention is acceptable.",
]
COUNT_PATTERNS = [
    r"\((\d+) records\) are shown below\.",                      # "... and the next batch (N records) are shown below."
    r"one batch of (\d+) records to be checked",                 # "Below are the integrity rules for X records and one batch of N records ..."
    r"this batch has (\d+) records\.",                           # "An import job checks every batch of X records ...; this batch has N records."
    r"^(\d+) [a-z ]+ records were delivered as one batch",        # "N X records were delivered as one batch ..."
]
FIELD_PREFIXES = ("Each record has these fields: ", "Record fields: ", "Fields per record: ")
RULE_HEADS = ("Rules:", "Integrity rules:", "Rules to check:")
JSON_HEADS = [
    "Records in batch order, one JSON object per line (a field that is missing or null is empty):",
    "The batch from first to last record, as JSON lines (an empty field is left out or set to null):",
    "Batch records in the order received, one JSON object each (null or a missing field means that the field is empty):",
]
TABLE_HEADS = [
    'Batch records in the order received, one row per record with " | " between cells ("-" alone means that the field is empty):',
    'Records in batch order, one row each, cells separated by " | " (a cell that holds only "-" is empty):',
    'The batch from first to last record, as a table with " | " between the cells (an empty field is shown as "-"):',
]
# The paragraph that follows the reference lists whenever a list carries a status column (four wordings, one meaning:
# the status beside a key counts only for a rule that NAMES a status; a rule that only asks for a key of the list
# accepts every key the list holds, whatever its status).  Recognised only as a whole paragraph, in this place.
STATUS_NOTES = (
    "The status written beside a key counts only for a rule that names a status. Every other rule that refers to the "
    "list accepts all of its keys, whatever their status.",
    "Note on statuses: a plain look-up rule (one that names no status) accepts any key of the list, with any status; "
    "a status is required only by a rule that names it.",
    "A listed key is a listed key, whatever its status: only a rule that names a status asks for it, and any other "
    "rule that refers to the list accepts all of its keys.",
    "Statuses in a reference list: a rule that only asks for a key of the list accepts every key the list holds, "
    "whatever its status; only a rule that names a status requires it.",
)

# ---------------------------------------------------------------------------------------------------------------
# rule sentences: (kind, regex, role of the groups).  F = field in backticks, W = quoted word, N = whole number.
# ---------------------------------------------------------------------------------------------------------------
F = r"`([a-z_0-9]+)`"
W = r'"([^"]*)"'
N = r"(-?\d+)"
WL3 = r'"([^"]*)", "([^"]*)", "([^"]*)"'
WL4 = r'"([^"]*)", "([^"]*)", "([^"]*)", "([^"]*)"'

RULE_FORMS = [
    # --- every value of one field differs -------------------------------------------------------------------------
    ("unique", rf"Within the batch, all values of {F} differ from one another\.", "f"),
    ("unique", rf"No two records of the batch may carry the same {F}\.", "f"),
    ("unique", rf"Each {F} appears at most once in the batch; a repeated {F} breaks this rule\.", "f f"),
    ("unique", rf"{F} is the record key: a value may occur only once in the batch\.", "f"),
    # --- exactly one of two fields filled in ---------------------------------------------------------------------
    ("xor", rf"Of the two fields {F} and {F}, one is filled in and the other is empty, in every record\.", "a b"),
    ("xor", rf"{F} and {F} exclude each other, and one of them is always filled in\.", "a b"),
    ("xor", rf"Exactly one of {F} and {F} must be filled in: never both, never neither\.", "a b"),
    ("xor", rf"Each record fills in either {F} or {F}, but not both and not neither\.", "a b"),
    # --- whole number within two limits ----------------------------------------------------------------------------
    ("range", rf"{F} must be a whole number from {N} to {N}; {N} and {N} themselves are allowed\.", "f lo hi lo hi"),
    ("range", rf"{F} is never smaller than {N} and never larger than {N}\.", "f lo hi"),
    ("range", rf"{F} stays within {N} to {N}, limits included\.", "f lo hi"),
    ("range", rf"The lowest allowed {F} is {N}, the highest is {N}\.", "f lo hi"),
    # --- limits that depend on a second field ---------------------------------------------------------------------
    ("dep_range", rf"For a record with {F} = {W}, {F} lies between {N} and {N}; for a record with {F} = {W}, between "
                  rf"{N} and {N} \(limits included in both cases\)\.", "b w1 v lo1 hi1 b w2 lo2 hi2"),
    ("dep_range", rf"The allowed span of {F} depends on {F}: {N} to {N} for {W}, {N} to {N} for {W}, limits included\.",
     "v b lo1 hi1 w1 lo2 hi2 w2"),
    ("dep_range", rf"If {F} is {W}, {F} is at least {N} and at most {N}; if {F} is {W}, at least {N} and at most {N}\.",
     "b w1 v lo1 hi1 b w2 lo2 hi2"),
    ("dep_range", rf"{F} must be from {N} to {N} when {F} is {W} and from {N} to {N} when {F} is {W}; the limits are "
                  rf"included\.", "v lo1 hi1 b w1 lo2 hi2 b w2"),
    # --- key of a reference list (status not asked about) ---------------------------------------------------------
    ("reference", rf"Each {F} has to be found among the keys of the reference list {F}\.", "f l"),
    ("reference", rf"A {F} that is not a key of the reference list {F} is not allowed\.", "f l"),
    ("reference", rf"{F} must be one of the keys of the reference list {F}\.", "f l"),
    ("reference", rf"The reference list {F} must contain every value of {F}\.", "l f"),
    # --- key of a reference list with a named status ---------------------------------------------------------------
    ("ref_active", rf"Each {F} has to appear in the reference list {F} with the status {W}; an entry with any other "
                   rf"status does not count\.", "f l s"),
    ("ref_active", rf"A {F} is valid only if the reference list {F} holds it and marks it {W}\.", "f l s"),
    ("ref_active", rf"{F} must be a key of the reference list {F} whose status there is {W}\.", "f l s"),
    ("ref_active", rf"Every value of {F} must be an entry of the reference list {F} that is marked {W}\.", "f l s"),
    # --- a trigger value makes a second field mandatory -----------------------------------------------------------
    ("conditional", rf"Whenever {F} is {W}, {F} must be filled in\.", "t w d"),
    ("conditional", rf"{F} may be empty only if {F} is not {W}\.", "d t w"),
    ("conditional", rf"A record whose {F} is {W} needs a filled-in {F}; for other records {F} is optional\.", "t w d d"),
    ("conditional", rf"If {F} equals {W}, an empty {F} is not allowed\.", "t w d"),
    # --- the pair of two fields occurs once ------------------------------------------------------------------------
    ("composite", rf"A combination of {F} and {F} that turns up in two records is not allowed, although each of the two "
                  rf"fields may repeat by itself\.", "a b"),
    ("composite", rf"The pair \({F}, {F}\) may occur only once in the batch; either field on its own may repeat\.", "a b"),
    ("composite", rf"No two records agree in both {F} and {F}; agreeing in just one of the two is fine\.", "a b"),
    ("composite", rf"{F} and {F} together identify a record: two records with the same {F} must differ in {F}\.", "a b x y"),
    # --- value from a short list ------------------------------------------------------------------------------------
    ("allowed", rf"{F} must be one of the following: {WL3}\.", "f w w w"),
    ("allowed", rf"{F} must be one of the following: {WL4}\.", "f w w w w"),
    ("allowed", rf"No value of {F} other than {WL3} is accepted\.", "f w w w"),
    ("allowed", rf"No value of {F} other than {WL4} is accepted\.", "f w w w w"),
    ("allowed", rf"Accepted values of {F}: {WL3}; nothing else\.", "f w w w"),
    ("allowed", rf"Accepted values of {F}: {WL4}; nothing else\.", "f w w w w"),
    ("allowed", rf"{F} is restricted to this list: {WL3}\.", "f w w w"),
    ("allowed", rf"{F} is restricted to this list: {WL4}\.", "f w w w w"),
    # --- order of two dates (first = the field named first in the sentence) ----------------------------------------
    ("date_order", rf"No record has a {F} that lies before its {F}; the two may coincide\.", "a b #ge"),   # a >= b
    ("date_order", rf"{F} falls on the day of {F} or on a later day\.", "a b #ge"),                          # a >= b
    ("date_order", rf"{F} is never after {F}; both on the same day is acceptable\.", "a b #le"),            # a <= b
    ("date_order", rf"{F} precedes {F} or equals it\.", "a b #le"),                                          # a <= b
    ("date_order", rf"No record has a {F} on or before its {F}\.", "a b #gt"),                               # a > b
    ("date_order", rf"{F} falls at least one day after {F}\.", "a b #gt"),                                   # a >= b + 1 day
    ("date_order", rf"{F} precedes {F}, and the two never coincide\.", "a b #lt"),                           # a < b
    ("date_order", rf"{F} lies strictly before {F}: the same day breaks the rule\.", "a b #lt"),             # a < b
    # --- stored total = sum / product of two fields -----------------------------------------------------------------
    ("derived", rf"{F} is the sum of {F} and {F}; any other stored value breaks the rule\.", "t x y #+"),
    ("derived", rf"{F} must equal {F} plus {F}\.", "t x y #+"),
    ("derived", rf"The stored {F} has to match {F} \+ {F}\.", "t x y #+"),
    ("derived", rf"In every record, {F} and {F} add up to exactly {F}\.", "x y t #+"),
    ("derived", rf"In every record, {F} times {F} gives exactly {F}\.", "x y t #*"),
    ("derived", rf"{F} is the product of {F} and {F}; any other stored value breaks the rule\.", "t x y #*"),
    ("derived", rf"{F} must equal {F} multiplied by {F}\.", "t x y #*"),
    ("derived", rf"The stored {F} has to match {F} x {F}\.", "t x y #*"),
    # --- running number -------------------------------------------------------------------------------------------
    ("sequence", rf"Every record after the first has a {F} that is one higher than that of the record just before "
                 rf"it\.", "f #one"),
    ("sequence", rf"The values of {F} are consecutive in batch order: no number is skipped or repeated, wherever the "
                 rf"count starts\.", "f #one"),
    ("sequence", rf"{F} rises by exactly {N} from each record to the next one in the batch; the first record may carry "
                 rf"any number\.", "f step"),
    ("sequence", rf"Going down the batch, each {F} is the {F} of the record before it plus {N} \(the starting number is "
                 rf"free\)\.", "f f step"),
    # --- a field naming the key of an earlier record --------------------------------------------------------------
    ("self_ref", rf"Each {F} that is given must match the {F} of a preceding record of the batch\.", "r k"),
    ("self_ref", rf"{F} may be empty; otherwise it holds a {F} found in one of the records above it\.", "r k"),
    ("self_ref", rf"A filled-in {F} names the {F} of another record of this batch, and that record comes before the "
                 rf"one that names it\.", "r k"),
    ("self_ref", rf"When {F} is filled in, it must be the {F} of a record that stands earlier in the batch\.", "r k"),
]
RULE_FORMS = [(k, re.compile("^" + rx + "$"), roles) for k, rx, roles in RULE_FORMS]
assert len(RULE_FORMS) == 64


class Unreadable(Exception):
    pass


# ---------------------------------------------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------------------------------------------
def parse_fields(line):
    for p in FIELD_PREFIXES:
        if line.startswith(p):
            body = line[len(p):]
            break
    else:
        raise Unreadable("field list not recognised: " + line[:60])
    assert body.endswith("."), "field list does not end with a full stop"
    body = body[:-1]
    pos, fields = 0, []
    rx = re.compile(r"([a-z_0-9]+) \((text|whole number|date, YYYY-MM-DD)\)(?:, |$)")
    while pos < len(body):
        m = rx.match(body, pos)
        if not m:
            raise Unreadable("field list: cannot read at " + body[pos:pos + 40])
        t = {"text": "text", "whole number": "int", "date, YYYY-MM-DD": "date"}[m.group(2)]
        fields.append((m.group(1), t))
        pos = m.end()
    names = [n for n, _ in fields]
    assert len(set(names)) == len(names), "duplicate field name"
    return fields


def parse_rule(sentence):
    for kind, rx, roles in RULE_FORMS:
        m = rx.match(sentence)
        if m:
            toks = roles.split()
            extra = [t[1:] for t in toks if t.startswith("#")]
            toks = [t for t in toks if not t.startswith("#")]
            assert len(toks) == len(m.groups()), (roles, m.groups())
            return kind, toks, list(m.groups()), (extra[0] if extra else None)
    raise Unreadable("rule sentence not recognised: " + sentence)


def build_rule(sentence):
    kind, roles, g, extra = parse_rule(sentence)
    r = {"kind": kind, "text": sentence}
    if kind == "unique":
        assert len(set(g)) == 1
        r["f"] = g[0]
    elif kind == "xor":
        assert roles[0] == "a" and g[0] != g[1]
        r["a"], r["b"] = g[0], g[1]
    elif kind == "range":
        r["f"], r["lo"], r["hi"] = g[0], int(g[1]), int(g[2])
        assert r["lo"] <= r["hi"]
        if len(g) == 5:
            assert (int(g[3]), int(g[4])) == (r["lo"], r["hi"]), "limits repeated differently in the sentence"
    elif kind == "dep_range":
        pos = {}                                  # roles may repeat (the branch field is named twice)
        for role, val in zip(roles, g):
            pos.setdefault(role, []).append(val)
        assert len(set(pos["b"])) == 1
        r["v"], r["b"] = pos["v"][0], pos["b"][0]
        r["branches"] = {}
        for i in (1, 2):
            r["branches"][pos["w%d" % i][0]] = (int(pos["lo%d" % i][0]), int(pos["hi%d" % i][0]))
        assert len(r["branches"]) == 2
        for lo, hi in r["branches"].values():
            assert lo <= hi
    elif kind in ("reference", "ref_active"):
        d = dict(zip(roles, g))
        r["f"], r["l"] = d["f"], d["l"]
        r["s"] = d.get("s")
    elif kind == "conditional":
        pos = {}
        for role, val in zip(roles, g):
            pos.setdefault(role, []).append(val)
        assert len(set(pos["d"])) == 1
        r["t"], r["w"], r["d"] = pos["t"][0], pos["w"][0], pos["d"][0]
    elif kind == "composite":
        if len(g) == 4:                           # "A and B together identify a record: two records with the same X must differ in Y"
            assert {g[2], g[3]} == {g[0], g[1]} and g[2] != g[3]
        r["a"], r["b"] = g[0], g[1]
        assert r["a"] != r["b"]
    elif kind == "allowed":
        r["f"], r["words"] = g[0], g[1:]
        assert len(set(r["words"])) == len(r["words"])
    elif kind == "date_order":
        r["a"], r["b"], r["rel"] = g[0], g[1], extra
        assert r["a"] != r["b"]
    elif kind == "derived":
        r["t"], r["x"], r["y"], r["op"] = g[roles.index("t")], g[roles.index("x")], g[roles.index("y")], extra
        assert len({r["t"], r["x"], r["y"]}) == 3
    elif kind == "sequence":
        if roles == ["f", "f", "step"]:
            assert g[0] == g[1]
        r["f"] = g[0]
        r["step"] = 1 if extra == "one" else int(g[-1])
    elif kind == "self_ref":
        r["r"], r["k"] = g[0], g[1]
        assert r["r"] != r["k"]
    else:
        raise Unreadable(kind)
    return r


def parse_reflist(head, lines):
    """returns (name, ordered list of (key, status or None)).  `lines` = the following lines of the paragraph."""
    m = re.match(r"^Reference list `([a-z_0-9]+)` with (\d+) (entries|keys)(.*)$", head)
    if not m:
        raise Unreadable("reference list heading not recognised: " + head[:70])
    name, n, what, rest = m.group(1), int(m.group(2)), m.group(3), m.group(4)
    entries = []
    if rest == " (key: status): " or rest.startswith(" (key: status): "):
        assert what == "entries" and not lines
        for part in rest[len(" (key: status): "):].split("; "):
            mm = re.match(r"^([A-Za-z]+-\d+): ([a-z]+)$", part)
            if not mm:
                raise Unreadable("list entry not recognised: " + part)
            entries.append((mm.group(1), mm.group(2)))
    elif rest.startswith(": "):
        assert what == "keys" and not lines
        for part in rest[2:].split(", "):
            if not re.match(r"^[A-Za-z]+-\d+$", part):
                raise Unreadable("list key not recognised: " + part)
            entries.append((part, None))
    elif rest == ", one per line (key: status):":
        assert what == "entries"
        for ln in lines:
            mm = re.match(r"^([A-Za-z]+-\d+): ([a-z]+)$", ln)
            if not mm:
                raise Unreadable("list line not recognised: " + ln)
            entries.append((mm.group(1), mm.group(2)))
    elif rest == ", one per line:":
        assert what == "keys"
        for ln in lines:
            if not re.match(r"^[A-Za-z]+-\d+$", ln):
                raise Unreadable("list line not recognised: " + ln)
            entries.append((ln, None))
    else:
        raise Unreadable("reference list layout not recognised: " + head[:90])
    assert len(entries) == n, "list %s announces %d, holds %d" % (name, n, len(entries))
    keys = [k for k, _ in entries]
    assert len(set(keys)) == len(keys), "duplicate key in list " + name
    return name, entries


def to_value(raw, ftype, where):
    """raw: JSON value or table cell text; returns None for empty."""
    if raw is None:
        return None
    if ftype == "int":
        if isinstance(raw, bool):
            raise Unreadable("bool where a number is expected: " + where)
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str) and re.match(r"^-?\d+$", raw):
            return int(raw)
        raise Unreadable("not a whole number: %r (%s)" % (raw, where))
    if not isinstance(raw, str):
        raise Unreadable("not a text: %r (%s)" % (raw, where))
    if raw == "" or raw.strip() != raw:
        raise Unreadable("empty or padded text value (%s)" % where)
    if ftype == "date":
        m = re.match(r"^(\d{4})-(\d\d)-(\d\d)$", raw)
        if not m:
            raise Unreadable("not a date: %r (%s)" % (raw, where))
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return raw


def parse_state(state):
    paras = state.split("\n\n")
    lead = paras[0]
    assert "\n" not in lead, "lead-in has several lines"
    if not any(c in lead for c in CONVENTIONS):
        raise Unreadable("general conventions not recognised")
    declared = None
    for pat in COUNT_PATTERNS:
        m = re.search(pat, lead)
        if m:
            declared = int(m.group(1))
            break
    if declared is None:
        raise Unreadable("record count of the lead-in not found")
    fields = rules = batch_head = None
    reflists = {}
    batch_lines = None
    status_note = False
    for p in paras[1:]:
        lines = p.split("\n")
        first = lines[0]
        if first.startswith(FIELD_PREFIXES):
            assert fields is None and len(lines) == 1
            fields = parse_fields(first)
        elif first in RULE_HEADS:
            assert rules is None
            rules = []
            for i, ln in enumerate(lines[1:], 1):
                m = re.match(r"^(R\d+)\. (.*)$", ln)
                if not m:
                    raise Unreadable("rule line not recognised: " + ln[:60])
                assert m.group(1) == "R%d" % i, "rule numbering"
                rules.append((m.group(1), m.group(2)))
        elif first.startswith("Reference list "):
            assert not status_note and batch_head is None, "a reference list after the status note / the batch"
            name, entries = parse_reflist(first, lines[1:])
            assert name not in reflists
            reflists[name] = entries
        elif p in STATUS_NOTES:
            assert not status_note, "the status note stands twice"
            assert rules is not None and batch_head is None, "the status note must stand after the rules, before the batch"
            if not any(s is not None for e in reflists.values() for _, s in e):
                raise Unreadable("status note although no reference list carries a status")
            status_note = True
        elif first in JSON_HEADS or first in TABLE_HEADS:
            assert batch_head is None
            batch_head, batch_lines = first, lines[1:]
        else:
            raise Unreadable("paragraph not recognised: " + first[:70])
    if fields is None or rules is None or batch_head is None:
        raise Unreadable("a part of the state is missing")
    if any(s is not None for e in reflists.values() for _, s in e) and not status_note:
        raise Unreadable("a reference list carries a status column but the state does not say how statuses count")
    ftype = dict(fields)
    records = []
    if batch_head in JSON_HEADS:
        for i, ln in enumerate(batch_lines, 1):
            try:
                obj = json.loads(ln)
            except ValueError:
                raise Unreadable("JSON line %d not readable" % i)
            if not isinstance(obj, dict):
                raise Unreadable("JSON line %d is not an object" % i)
            for k in obj:
                if k not in ftype:
                    raise Unreadable("unknown field %r in record %d" % (k, i))
            records.append({n: to_value(obj.get(n), t, "%s of record %d" % (n, i)) for n, t in fields})
    else:
        cols = batch_lines[0].split(" | ")
        assert sorted(cols) == sorted(ftype), "table header differs from the field list"
        for i, ln in enumerate(batch_lines[1:], 1):
            cells = ln.split(" | ")
            if len(cells) != len(cols):
                raise Unreadable("row %d has %d cells, header %d" % (i, len(cells), len(cols)))
            rec = {}
            for c, cell in zip(cols, cells):
                rec[c] = to_value(None if cell == "-" else cell, ftype[c], "%s of record %d" % (c, i))
            records.append(rec)
    assert len(records) == declared, "the lead-in announces %d records, the batch holds %d" % (declared, len(records))
    return fields, rules, reflists, records, status_note


# ---------------------------------------------------------------------------------------------------------------
# evaluation: every function returns the (1-based) record numbers at which the rule is broken
# ---------------------------------------------------------------------------------------------------------------
def need(rec, name, i):
    v = rec[name]
    if v is None:
        raise Unreadable("field %s is empty in record %d where the rule needs a value" % (name, i))
    return v


def broken_places(rule, fields, reflists, records, status_note=False):
    kind = rule["kind"]
    ftype = dict(fields)
    names = set(ftype)
    for k in ("f", "a", "b", "v", "t", "d", "x", "y", "r"):
        if k in rule and rule[k] not in names:
            raise Unreadable("rule names unknown field %s" % rule[k])
    if kind == "derived":
        for k in ("t", "x", "y"):
            assert ftype[rule[k]] == "int", "derived rule on a non-number field"
    if kind in ("range", "sequence"):
        assert ftype[rule["f"]] == "int"
    if kind == "dep_range":
        assert ftype[rule["v"]] == "int"
    if kind == "date_order":
        assert ftype[rule["a"]] == "date" and ftype[rule["b"]] == "date"
    if kind in ("reference", "ref_active"):
        if rule["l"] not in reflists:
            raise Unreadable("rule names unknown list %s" % rule["l"])
    out = []
    n = len(records)

    if kind == "unique":
        f = rule["f"]
        for i in range(n):
            for j in range(i + 1, n):
                vi, vj = records[i][f], records[j][f]
                if vi is None or vj is None:
                    raise Unreadable("empty key value under a uniqueness rule")
                if vi == vj:
                    out.append(j + 1)             # the later copy is the place of the violation
        return sorted(set(out))

    if kind == "composite":
        a, b = rule["a"], rule["b"]
        for i in range(n):
            for j in range(i + 1, n):
                pa, pb = (records[i][a], records[i][b]), (records[j][a], records[j][b])
                if None in pa or None in pb:
                    raise Unreadable("empty value under a pair rule")
                if pa == pb:
                    out.append(j + 1)
        return sorted(set(out))

    if kind == "sequence":
        f, step = rule["f"], rule["step"]
        for i in range(1, n):
            prev, cur = need(records[i - 1], f, i), need(records[i], f, i + 1)
            if cur - prev != step:
                out.append(i + 1)
        return out

    if kind == "self_ref":
        r, k = rule["r"], rule["k"]
        for i in range(n):
            ref = records[i][r]
            if ref is None:
                continue
            ok = False
            for j in range(0, i):                 # only records that stand EARLIER
                if records[j][k] is not None and records[j][k] == ref:
                    ok = True
                    break
            if not ok:
                out.append(i + 1)
        return out

    lst = None
    if kind in ("reference", "ref_active"):
        lst = dict(reflists[rule["l"]])
        if kind == "ref_active":
            if any(s is None for s in lst.values()):
                raise Unreadable("status asked for but list %s has no status column" % rule["l"])
        elif any(s is not None for s in lst.values()) and not status_note:
            # a plain look-up over a list with statuses: the status is ignored only because the state says so
            raise Unreadable("plain look-up over list %s with statuses, but no note says that statuses are ignored" % rule["l"])

    for i, rec in enumerate(records, 1):
        if kind == "xor":
            filled = (rec[rule["a"]] is not None) + (rec[rule["b"]] is not None)
            bad = filled != 1
        elif kind == "range":
            v = need(rec, rule["f"], i)
            bad = not (rule["lo"] <= v <= rule["hi"])
        elif kind == "dep_range":
            br = rec[rule["b"]]
            if br is None:
                raise Unreadable("branch field empty in record %d" % i)
            v = need(rec, rule["v"], i)
            if br in rule["branches"]:
                lo, hi = rule["branches"][br]
                bad = not (lo <= v <= hi)
            else:
                bad = False                       # a branch the rule does not mention: nothing is asked
        elif kind == "reference":
            v = need(rec, rule["f"], i)
            bad = v not in lst
        elif kind == "ref_active":
            v = need(rec, rule["f"], i)
            bad = not (v in lst and lst[v] == rule["s"])
        elif kind == "conditional":
            trig = rec[rule["t"]]
            bad = (trig == rule["w"]) and rec[rule["d"]] is None
        elif kind == "allowed":
            v = need(rec, rule["f"], i)
            bad = v not in rule["words"]
        elif kind == "date_order":
            da, db = need(rec, rule["a"], i), need(rec, rule["b"], i)
            rel = rule["rel"]
            if rel == "ge":
                bad = not (da >= db)
            elif rel == "le":
                bad = not (da <= db)
            elif rel == "gt":
                bad = not (da > db)
            elif rel == "lt":
                bad = not (da < db)
            else:
                raise Unreadable(rel)
        elif kind == "derived":
            x, y, t = need(rec, rule["x"], i), need(rec, rule["y"], i), need(rec, rule["t"], i)
            val = x + y if rule["op"] == "+" else x * y
            bad = val != t
        else:
            raise Unreadable(kind)
        if bad:
            out.append(i)
    return out


def analyse(state):
    fields, rules, reflists, records, status_note = parse_state(state)
    res = {}
    for key, sentence in rules:
        rule = build_rule(sentence)
        res[key] = (rule["kind"], broken_places(rule, fields, reflists, records, status_note), sentence)
    return res, rules


def solve(state, question, options):
    assert question.strip() == "Which rule does the batch violate?", "unknown question"
    res, rules = analyse(state)
    keys = [k for k, _ in rules]
    assert sorted(options.keys()) == sorted(keys + [NONE_KEY]), "option keys differ from the rule keys of the state"
    for k, s in rules:
        assert options[k] == s, "option text of %s differs from the rule sentence of the state" % k
    assert options[NONE_KEY].startswith("No rule is violated"), "text of the none option"
    broken = [k for k in keys if res[k][1]]
    if len(broken) > 1:
        raise Unreadable("two rules come out broken: " + "; ".join("%s %s at %s" % (k, res[k][0], res[k][1]) for k in broken))
    return broken[0] if broken else NONE_KEY
