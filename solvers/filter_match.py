"""Independent solver for `filter_match` (gen_v4 label audit).

A request in words (6 to 12 constraints, four layouts) and one catalogue record (JSON): does the record satisfy every
constraint?  The solver
  1. splits the request into constraint clauses and convention sentences (day-count and date-plus-days conventions),
  2. reads every clause with an anchored regular expression (one per phrasing); a clause that no expression matches, or
     that two different readings match, raises an error - nothing is skipped silently,
  3. evaluates each constraint on the record with exact rational arithmetic (fractions, never floats) and its own
     calendar (days-from-civil), taking conversion factors and the day-count convention from the request itself.
Python 3.9, standard library only.  Written from the rendered text alone.
"""
import json
import re
from decimal import Decimal
from fractions import Fraction

# ----------------------------------------------------------------------------------------------------------------
# exact numbers and calendar
# ----------------------------------------------------------------------------------------------------------------


def frac(v):
    """Exact value of a JSON number (int, float written by json, Decimal) or of a decimal string."""
    if isinstance(v, bool):
        raise ValueError("boolean where a number was expected")
    if isinstance(v, int):
        return Fraction(v)
    if isinstance(v, float):
        return Fraction(repr(v))          # shortest round-trip text = the digits that were written
    if isinstance(v, Decimal):
        return Fraction(v)
    if isinstance(v, str):
        return Fraction(v)
    raise ValueError("not a number: %r" % (v,))


_DIM = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def day_number(s):
    """Days since 1970-01-01 of an ISO date (proleptic Gregorian), checked for validity."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if not m:
        raise ValueError("not an ISO date: %r" % (s,))
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12):
        raise ValueError("bad month in %r" % (s,))
    dim = _DIM[mo - 1] + (1 if mo == 2 and _leap(y) else 0)
    if not (1 <= d <= dim):
        raise ValueError("bad day in %r" % (s,))
    y2 = y - (1 if mo <= 2 else 0)
    era = y2 // 400
    yoe = y2 - era * 400
    doy = (153 * (mo + (-3 if mo > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


# ----------------------------------------------------------------------------------------------------------------
# comparator phrases
# ----------------------------------------------------------------------------------------------------------------

# a comparator in front of the number ("at most 5 kg") ...
PRE_NUM = {
    "at most": "<=", "no more than": "<=", "not above": "<=",
    "less than": "<", "lower than": "<", "below": "<", "under": "<",
    "at least": ">=", "no less than": ">=", "not below": ">=",
    "more than": ">", "higher than": ">", "above": ">", "over": ">",
}
# ... or behind it ("5 kg or less")
POST_NUM = {"or less": "<=", "or more": ">="}
# dates: comparator in front of the date, "D at the latest", "from D onwards"
PRE_DATE = {
    "no later than": "<=", "not after": "<=", "on or before": "<=",
    "before": "<", "earlier than": "<", "prior to": "<", "strictly before": "<",
    "no earlier than": ">=", "not before": ">=", "on or after": ">=",
    "after": ">", "later than": ">", "strictly after": ">", "subsequent to": ">",
}

NUM = r"\d+(?:\.\d+)?"
DATE = r"\d{4}-\d{2}-\d{2}"
REG = r"(?-i:[A-Z][A-Za-z]*-(?:North|South|East|West))"
CERT = r"(?-i:[A-Z]{3}-[A-Z0-9])"
CERTS = CERT + r"(?:, " + CERT + r")*(?: and " + CERT + r")"
NAME = r"(?-i:[A-Z][a-z]+)"
NAMES = NAME + r"(?:(?:, | or )" + NAME + r")*"
CATEGORY = r"(?-i:[A-Z][a-z]+(?: [a-z]+)*)"
TAG = r"(?-i:[a-z]+)"

UNITS = {
    "none": "",
    "days": r"days?",
    "cur": r"(?-i:[A-Z]{3})",
    "percent": r"percent",
    "months": r"months?",
    "units": r"units?",
    "W": r"W",
    "mAh": r"mAh",
    "cm": r"cm",
    "dB": r"dB",
    "kg": r"kg",
    "inch": r"inch(?:es)?",
    "litre": r"litres?",
    "hour": r"hours?",
}


def _alt(words):
    return "(?:" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + ")"


def cmp_pat(unit):
    u = (r"\s+" + UNITS[unit]) if UNITS[unit] else ""
    return ("(?:" + _alt(PRE_NUM) + r"\s+" + NUM + u + "|" + NUM + u + r"\s+" + _alt(POST_NUM) + ")")


def parse_cmp(text, unit):
    """-> (operator, exact limit, unit token or None) of 'at most 5 kg' / '5 kg or less'."""
    u = (r"\s+(?P<unit>" + UNITS[unit] + ")") if UNITS[unit] else ""
    m = re.fullmatch(r"(?P<w>" + _alt(PRE_NUM) + r")\s+(?P<n>" + NUM + ")" + u, text, re.I)
    if m:
        return PRE_NUM[m.group("w").lower()], Fraction(m.group("n")), m.groupdict().get("unit")
    m = re.fullmatch(r"(?P<n>" + NUM + ")" + u + r"\s+(?P<w>" + _alt(POST_NUM) + ")", text, re.I)
    if m:
        return POST_NUM[m.group("w").lower()], Fraction(m.group("n")), m.groupdict().get("unit")
    raise ValueError("comparator not understood: %r" % (text,))


def dcmp_pat():
    return ("(?:" + _alt(PRE_DATE) + r"\s+" + DATE + "|" + DATE + r"\s+at the latest|from\s+" + DATE + r"\s+onwards)")


def parse_dcmp(text):
    m = re.fullmatch(r"(?P<w>" + _alt(PRE_DATE) + r")\s+(?P<d>" + DATE + ")", text, re.I)
    if m:
        return PRE_DATE[m.group("w").lower()], day_number(m.group("d"))
    m = re.fullmatch(r"(?P<d>" + DATE + r")\s+at the latest", text, re.I)
    if m:
        return "<=", day_number(m.group("d"))
    m = re.fullmatch(r"from\s+(?P<d>" + DATE + r")\s+onwards", text, re.I)
    if m:
        return ">=", day_number(m.group("d"))
    raise ValueError("date comparator not understood: %r" % (text,))


def holds(a, op, b):
    """a op b, decided by the sign of the exact difference."""
    d = a - b
    if op == "<=":
        return d <= 0
    if op == "<":
        return d < 0
    if op == ">=":
        return d >= 0
    if op == ">":
        return d > 0
    raise ValueError("operator " + op)


# ----------------------------------------------------------------------------------------------------------------
# templates (one anchored expression per phrasing; matched case-insensitively, names are case-sensitive)
# ----------------------------------------------------------------------------------------------------------------

TEMPLATES = []          # (kind, compiled regex, extra)


def expand(p):
    p = re.sub(r"@CMP:(\w+)@", lambda m: "(?P<cmp>" + cmp_pat(m.group(1)) + ")", p)
    p = p.replace("@DCMP@", "(?P<dcmp>" + dcmp_pat() + ")")
    p = p.replace("@NUM@", NUM).replace("@DATE@", DATE).replace("@REG@", REG)
    p = p.replace("@CERTS@", CERTS).replace("@NAMES@", NAMES).replace("@CATEGORY@", CATEGORY).replace("@TAG@", TAG)
    return p


def add(kind, pattern, **extra):
    TEMPLATES.append((kind, re.compile(expand(pattern), re.I), extra))


# --- one field, one limit ---------------------------------------------------------------------------------------
SIMPLE = [  # (word in the request, record field, unit)
    ("rating", "rating", "none"),
    ("warranty", "warranty_months", "months"),
    ("stock", "stock_units", "units"),
    ("power", "power_w", "W"),
    ("battery capacity", "battery_mah", "mAh"),
    ("width", "width_cm", "cm"),
    ("noise level", "noise_db", "dB"),
    ("price", "price", "cur"),
]
for _w, _f, _u in SIMPLE:
    add("num", r"(?:the|its) " + _w + r" (?:is|must be|has to be) @CMP:" + _u + "@", field=_f, unit=_u)
    add("num", r"it has an? " + _w + r" that is @CMP:" + _u + "@", field=_f, unit=_u)

# --- sums, quotients, discounts ---------------------------------------------------------------------------------
add("total", r"price and shipping fee together come to @CMP:cur@")
add("total", r"paying the price and the shipping fee costs @CMP:cur@ in all")
add("total", r"the total of the price and the shipping fee is @CMP:cur@")
add("total", r"the price plus the shipping fee is @CMP:cur@")

add("unit", r"the unit price, worked out as bundle price divided by bundle size, is @CMP:cur@")
add("unit", r"each unit costs @CMP:cur@, counting the bundle price divided by the bundle size")
add("unit", r"dividing the bundle price by the bundle size gives a unit price that is @CMP:cur@")
add("unit", r"the price per unit \(bundle price divided by bundle size\) is @CMP:cur@")

add("disc", r"the discount from the list price to the price, worked out exactly as a share of the list price, is @CMP:percent@")
add("disc", r"the price has been cut by @CMP:percent@ from the list price, worked out exactly")
add("disc", r"the price is lower than the list price by @CMP:percent@, worked out exactly")
add("disc", r"the price is @CMP:percent@ below the list price, worked out exactly")

# --- conversions (the factor is stated in the clause) ----------------------------------------------------------------
# quantity: (record field, record unit word, plural noun, small unit regex, big unit key, subject word, verb phrase)
QUANT = {
    "weight": ("weight_g", "grams", "weights", r"g", "kg", "weight", "weighs {C}"),
    "length": ("length_cm", "centimetres", "lengths", r"cm", "inch", "length", "measures {C} in length"),
    "volume": ("volume_ml", "millilitres", "volumes", r"ml", "litre", "volume", "holds {C}"),
    "runtime": ("runtime_min", "minutes", "run times", r"minutes?", "hour", "run time", "runs for {C}"),
}
for _q, (_f, _ru, _pl, _small, _big, _subj, _verb) in QUANT.items():
    C = "@CMP:" + _big + "@"
    BIG = UNITS[_big]
    A = r"\(the record gives " + _pl + r" in " + _ru + r", and (?P<nb>@NUM@) (?P<ub>" + BIG + r") = (?P<ns>@NUM@) (?P<us>" + _small + r")\)"
    B = r"\(" + _pl + r" in the record are in " + _ru + r", (?P<ns>@NUM@) (?P<us>" + _small + r") making (?P<nb>@NUM@) (?P<ub>" + BIG + r")\)"
    Cc = r", the record showing " + _pl + r" in " + _ru + r" at (?P<ns>@NUM@) (?P<us>" + _small + r") to the (?P<ub>" + BIG + r")"
    D = r", converted from the " + _ru + r" of the record at (?P<ns>@NUM@) (?P<us>" + _small + r") per (?P<ub>" + BIG + r"),"
    kw = dict(quant=_q, field=_f, unit=_big)
    add("conv", r"the " + _subj + r" is " + C + " " + A, **kw)
    add("conv", "it " + _verb.format(C=C) + " " + B, **kw)
    add("conv", r"the " + _subj + r" must be " + C + Cc, **kw)
    add("conv", r"its " + _subj + D + " is " + C, **kw)

# --- dates ----------------------------------------------------------------------------------------------------------
add("date", r"(?:the|its) availability date (?:is|must be|has to be) @DCMP@", field="available_from")
add("date", r"(?:the|its) release date (?:is|must be|has to be) @DCMP@", field="release_date")
add("ready", r"the ready date, which is the stocked date plus the handling days, is @DCMP@")
add("ready", r"the stocked date plus the handling time in days is @DCMP@")
add("ready", r"adding the handling days to the stocked date gives a date that is @DCMP@")
add("ready", r"the item is ready @DCMP@, counting the stocked date plus the handling days")

add("gap", r"the shipping date falls @CMP:days@ after the manufacturing date")
add("gap", r"the gap from the manufacturing date to the shipping date is @CMP:days@")
add("gap", r"the number of days between the manufacturing date and the shipping date is @CMP:days@")
add("gap", r"the item waits @CMP:days@ between the manufacturing date and the shipping date")

add("age", r"as of (?P<asof>@DATE@), the listing has been (?:online|live) for @CMP:days@, counted from the listing date")
add("age", r"on (?P<asof>@DATE@), the age of the listing in days, counted from the listing date, is @CMP:days@")
add("age", r"the number of days from the listing date to (?P<asof>@DATE@) is @CMP:days@")

# --- certifications -------------------------------------------------------------------------------------------------
add("certs", r"(?P<cmp>" + cmp_pat("none") + r") of these certifications are held: (?P<certs>@CERTS@)")
add("certs", r"among the certifications (?P<certs>@CERTS@), (?P<cmp>" + cmp_pat("none") + r") are held")
add("certs", r"the number of certifications held among (?P<certs>@CERTS@) is (?P<cmp>" + cmp_pat("none") + r")")
add("certs", r"the record lists (?P<cmp>" + cmp_pat("none") + r") of the certifications (?P<certs>@CERTS@)")

# --- delivery that applies outside one origin --------------------------------------------------------------------------
add("cond", r"if the item ships from outside (?P<r1>@REG@), the delivery time is @CMP:days@ \(items that ship from (?P<r2>@REG@) have no delivery limit\)")
add("cond", r"delivery takes @CMP:days@ for items shipped from outside (?P<r1>@REG@), and there is no limit for items shipped from (?P<r2>@REG@)")
add("cond", r"an item that ships from anywhere other than (?P<r1>@REG@) must have a delivery time of @CMP:days@, and items shipped from (?P<r2>@REG@) have no limit")
add("cond", r"when the item does not ship from (?P<r1>@REG@), the delivery time is @CMP:days@, and when it ships from (?P<r2>@REG@), no delivery limit applies")

# --- categorical ------------------------------------------------------------------------------------------------------
add("category", r"it is filed under the category (?P<cat>@CATEGORY@)")
add("category", r"its category is (?P<cat>@CATEGORY@)")
add("category", r"the category must be (?P<cat>@CATEGORY@)")
add("category", r"it belongs to the category (?P<cat>@CATEGORY@)")

add("tag_present", r"it carries the tag (?P<tag>@TAG@)")
add("tag_present", r"it has the (?P<tag>@TAG@) tag")
add("tag_present", r"it is tagged (?P<tag>@TAG@)")
add("tag_present", r"the tag (?P<tag>@TAG@) must be present")
add("tag_absent", r"it does not carry the tag (?P<tag>@TAG@)")
add("tag_absent", r"it has no (?P<tag>@TAG@) tag")
add("tag_absent", r"it is not tagged (?P<tag>@TAG@)")
add("tag_absent", r"the tag (?P<tag>@TAG@) must be absent")

add("region", r"it ships to (?P<reg>@REG@)")
add("region", r"it can be shipped to (?P<reg>@REG@)")
add("region", r"shipping to (?P<reg>@REG@) is possible")
add("region", r"(?P<reg>@REG@) is one of the regions it ships to")

add("maker", r"it was made by (?P<names>@NAMES@)")
add("maker", r"it is made by (?P<names>@NAMES@)")
add("maker", r"its maker is one of (?P<names>@NAMES@)")
add("maker", r"the maker is (?P<names>@NAMES@)")

# ----------------------------------------------------------------------------------------------------------------
# conventions stated by the request
# ----------------------------------------------------------------------------------------------------------------
DAY_CONVENTIONS = [
    r"day counts are the difference between the two dates \(the same day counts as (\d+) days?\)",
    r"counting days means subtracting one date from the other \(the same day counts as (\d+) days?\)",
    r"a count of days is the difference between the two dates; two identical dates are (\d+) days? apart",
    r"days between two dates are counted as the plain difference of the dates, so the same day is (\d+) days?",
]
PLUS_CONVENTIONS = [
    r"a date plus n days means n days later on the calendar \(the date itself counts as day (\d+)\)",
    r"adding n days to a date gives the date n days after it; the date itself is day (\d+)",
    r"a date plus n days is the date n days later \(adding (\d+) days gives the same date\)",
    r"adding days to a date moves it forward by exactly that many days \(adding (\d+) days gives the same date\)",
]

SENT_END = re.compile(r"(?<=[A-Za-z0-9)%])\.\s+(?=[A-Z0-9])")


def read_convention(sentence):
    s = sentence.strip().rstrip(".").strip()
    for p in DAY_CONVENTIONS:
        m = re.fullmatch(p, s, re.I)
        if m:
            return "day", int(m.group(1))
    for p in PLUS_CONVENTIONS:
        m = re.fullmatch(p, s, re.I)
        if m:
            return "plus", int(m.group(1))
    return None


HEAD_LINES = ("Find a listing that meets every requirement below:", "Requirements (all must hold):")
HEAD_SENT = "The listing must satisfy every point below."
HEAD_SEMI = "I need a listing for which all of these hold:"


def split_request(req):
    """-> (constraint clauses, convention sentences)."""
    req = req.strip()
    lines = req.split("\n")
    if len(lines) > 1:
        assert lines[0] in HEAD_LINES, "unknown lead-in line: %r" % (lines[0],)
        clauses, rest, number = [], [], 0
        for ln in lines[1:]:
            m = re.fullmatch(r"- (.+)", ln)
            m2 = re.fullmatch(r"(\d+)\) (.+)", ln)
            if m and lines[0] == HEAD_LINES[0]:
                clauses.append(m.group(1))
            elif m2 and lines[0] == HEAD_LINES[1]:
                number += 1
                assert int(m2.group(1)) == number, "numbering of the constraints is not 1, 2, 3, ..."
                clauses.append(m2.group(2))
            else:
                rest.append(ln)
        return [c.strip().rstrip(".").strip() for c in clauses], rest
    if req.startswith(HEAD_SENT + " "):
        sentences = SENT_END.split(req[len(HEAD_SENT) + 1:])
        clauses, conv = [], []
        for s in sentences:
            (conv if read_convention(s) else clauses).append(s)
        return [c.strip().rstrip(".").strip() for c in clauses], conv
    if req.startswith(HEAD_SEMI + " "):
        sentences = SENT_END.split(req[len(HEAD_SEMI) + 1:])
        first, conv = sentences[0], sentences[1:]
        parts = [p.strip() for p in first.strip().rstrip(".").split(";")]
        assert len(parts) >= 2
        for i, p in enumerate(parts):
            if i == len(parts) - 1:
                assert p.startswith("and "), "the last clause should start with 'and'"
                parts[i] = p[4:].strip()
            else:
                assert not p.startswith("and "), "'and' before a clause that is not the last"
        return parts, conv
    raise ValueError("unknown request layout: %r" % (req[:60],))


# ----------------------------------------------------------------------------------------------------------------
# evaluating one constraint
# ----------------------------------------------------------------------------------------------------------------

def need(rec, field):
    if field not in rec:
        raise KeyError("the request constrains '%s' but the record has no such field" % field)
    return rec[field]


def read_clause(text):
    text = re.sub(r"\s+", " ", text.strip())
    hits = []
    for kind, rx, extra in TEMPLATES:
        m = rx.fullmatch(text)
        if m:
            hits.append((kind, m, extra))
    if not hits:
        raise ValueError("clause not recognised: %r" % (text,))
    if len(hits) > 1:
        kinds = set((k, tuple(sorted(e.items()))) for k, _, e in hits)
        if len(kinds) > 1:
            raise ValueError("clause read in two ways: %r" % (text,))
    return hits[0]


def evaluate(text, rec, conv):
    """-> (kind, truth)"""
    kind, m, extra = read_clause(text)
    g = m.groupdict()
    cur = rec.get("currency")

    def money_ok(unit_tok):
        assert unit_tok == cur, "limit in %s but the record is in %s: %r" % (unit_tok, cur, text)

    def day_offset():
        if "day" not in conv:
            raise ValueError("a clause counts days but the request states no day-count convention: %r" % (text,))
        return conv["day"]

    if kind == "num":
        op, lim, tok = parse_cmp(g["cmp"], extra["unit"])
        if extra["unit"] == "cur":
            money_ok(tok)
        return kind, holds(frac(need(rec, extra["field"])), op, lim)

    if kind == "total":
        op, lim, tok = parse_cmp(g["cmp"], "cur")
        money_ok(tok)
        return kind, holds(frac(need(rec, "price")) + frac(need(rec, "shipping_fee")), op, lim)

    if kind == "unit":
        op, lim, tok = parse_cmp(g["cmp"], "cur")
        money_ok(tok)
        size = frac(need(rec, "bundle_size"))
        assert size > 0
        return kind, holds(frac(need(rec, "bundle_price")) / size, op, lim)

    if kind == "disc":
        op, lim, _ = parse_cmp(g["cmp"], "percent")
        lp, p = frac(need(rec, "list_price")), frac(need(rec, "price"))
        assert lp > 0
        return kind, holds((lp - p) * 100 / lp, op, lim)

    if kind == "conv":
        op, lim, _ = parse_cmp(g["cmp"], extra["unit"])
        nb = frac(g["nb"]) if g.get("nb") else Fraction(1)
        ns = frac(g["ns"])
        assert nb > 0 and ns > 0
        per_big = ns / nb                      # record units that make one big unit
        return kind, holds(frac(need(rec, extra["field"])) / per_big, op, lim)

    if kind == "date":
        op, d = parse_dcmp(g["dcmp"])
        return kind, holds(Fraction(day_number(need(rec, extra["field"]))), op, Fraction(d))

    if kind == "ready":
        if "plus" not in conv:
            raise ValueError("ready-date clause but no 'date plus N days' convention: %r" % (text,))
        assert conv["plus"] == 0, "unsupported date-plus convention"
        op, d = parse_dcmp(g["dcmp"])
        ready = day_number(need(rec, "stocked_on")) + int(need(rec, "handling_days"))
        return kind, holds(Fraction(ready), op, Fraction(d))

    if kind == "gap":
        op, lim, _ = parse_cmp(g["cmp"], "days")
        gap = day_number(need(rec, "shipped_on")) - day_number(need(rec, "manufactured_on")) + day_offset()
        return kind, holds(Fraction(gap), op, lim)

    if kind == "age":
        op, lim, _ = parse_cmp(g["cmp"], "days")
        age = day_number(g["asof"]) - day_number(need(rec, "listed_on")) + day_offset()
        return kind, holds(Fraction(age), op, lim)

    if kind == "certs":
        op, lim, _ = parse_cmp(g["cmp"], "none")
        listed = re.findall(CERT, g["certs"])
        assert len(listed) == len(set(listed)) and len(listed) >= 2
        held = need(rec, "certifications")
        assert len(held) == len(set(held)), "duplicate certification in the record"
        n = 0
        for c in listed:
            if c in held:
                n += 1
        return kind, holds(Fraction(n), op, lim)

    if kind == "cond":
        assert g["r1"] == g["r2"], "the two regions of a delivery clause differ: %r" % (text,)
        op, lim, _ = parse_cmp(g["cmp"], "days")
        if need(rec, "ships_from") == g["r1"]:
            return kind, True
        return kind, holds(frac(need(rec, "delivery_days")), op, lim)

    if kind == "category":
        return kind, need(rec, "category") == g["cat"]

    if kind in ("tag_present", "tag_absent"):
        has = g["tag"] in need(rec, "tags")
        return kind, has if kind == "tag_present" else (not has)

    if kind == "region":
        return kind, g["reg"] in need(rec, "ships_to")

    if kind == "maker":
        names = re.split(r", | or ", g["names"])
        assert len(names) >= 2
        return kind, need(rec, "maker") in names

    raise AssertionError("unhandled kind " + kind)


# ----------------------------------------------------------------------------------------------------------------
# entry point
# ----------------------------------------------------------------------------------------------------------------

def load_state(state):
    if isinstance(state, str):
        state = json.loads(state, parse_float=Decimal)
    assert isinstance(state, dict) and set(state) == {"request", "record"}, "state fields: %r" % (sorted(state),)
    return state["request"], state["record"]


def check_record(rec):
    for f in ("currency", "category", "maker", "ships_from", "ships_to", "tags", "certifications"):
        assert f in rec, "record lacks " + f
    assert isinstance(rec["ships_to"], list) and isinstance(rec["tags"], list) and isinstance(rec["certifications"], list)


def explain(state):
    req, rec = load_state(state)
    check_record(rec)
    clauses, conv_sentences = split_request(req)
    conv = {}
    for s in conv_sentences:
        for ln in SENT_END.split(s.strip()):
            r = read_convention(ln)
            if r is None:
                raise ValueError("sentence not recognised: %r" % (ln,))
            if r[0] in conv and conv[r[0]] != r[1]:
                raise ValueError("two different conventions stated")
            conv[r[0]] = r[1]
    assert 6 <= len(clauses) <= 12, "%d constraints" % len(clauses)
    out = []
    for c in clauses:
        kind, ok = evaluate(c, rec, conv)
        out.append((c, kind, ok))
    # conventions that no clause needs would be suspicious; they are reported by the caller, not an error here
    return out


def solve(state, question, options):
    assert "satisfy every constraint" in question, "unexpected question: %r" % (question,)
    assert set(options) == {"yes", "no"}, "unexpected options: %r" % (list(options),)
    res = explain(state)
    return "yes" if all(ok for _, _, ok in res) else "no"
