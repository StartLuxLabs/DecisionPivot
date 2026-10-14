"""Task filter_match (layer G, generated, programmatic truth): "does the record satisfy every constraint of the request?"

Two versions.  The constant DIFFICULTY at the top of the file chooses the version: "v2" (the default, and what tasks/filter_match holds) or "v1"
(the first version); the environment variable BENCH_DIFFICULTY overrides it (``BENCH_DIFFICULTY=v1 python3 generators/filter_match.py``).  Either run
rewrites the task directory (items.jsonl, task.json, README.md) and is deterministic.  v1 was answered at 0.997 by a strong hosted model, so v2 asks for
6 / 9 / 12 constraints, adds ten kinds that need a small computation on the record, and keeps every planted constraint within ONE step of its limit.
The v1 code path is the first version, unchanged (main_v1, write_readme_v1); v2 is the block of functions ending in _v2.

VERSION v2 (default)

Item design.  The state is a request in words with 6, 9 or 12 constraints (four layouts, each with a lead-in sentence; four phrasings per kind and per
conversion; sixteen comparator phrases that say in words whether the limit itself counts) over the catalogue record of an invented product as a JSON
object (34 fields).  Twenty constraint kinds, all different within a request (also the values of ``meta.deviation``); at most one of the three that read
the price.  The ten of v1: price_max, feature_min, feature_max, category, excluded_tag, required_tag, region, date_max, date_min, maker_in.  Ten that need
a small computation on the record:
  unit_price_max  bundle price divided by bundle size              discount_min   the price is P percent below the list price, worked out exactly
  total_max       price plus shipping fee                          conv_max       weight (g to kg) or length (cm to inches), factor stated in the request
  conv_min        volume (ml to litres) or run time (min to hours) date_gap       days between the manufacturing date and the shipping date
  ready_by        the stocked date plus the handling days          listing_age    days from the listing date to a day named in the request
  certs_k_of_n    at least k of 3 or 4 listed certifications held  conditional    a delivery limit that applies only to items not shipped from a stated region
The compared quantity x of a constraint (the price, the unit price, the grams, the days, ...) has a smallest step (one cent, one gram, one day, one
certification, ...).  The truth is evaluated on x with exact fractions; the discount limit is never a whole number of cents.

Contrast pairs.  600 items = 300 pairs: the same request with a record that satisfies every constraint (yes), and the same record with ONE field changed
so that exactly one constraint fails (no).  In both members the planted quantity is ON the limit named in the request or ONE step from it: the negative on
the limit (a wording that does not count it) or one step beyond it, the positive on the limit (a wording that counts it) or one step inside it.  Patterns
(``meta.pattern``): edge_pos (positive on an inclusive limit, negative one step beyond), edge_neg (positive one step inside an exclusive limit, negative on
it), mirror (one step inside / one step outside), adjacent (discount: the highest price that is discounted enough / the next cent), switch (conditional:
the same delivery time, the item ships from inside the region = no limit, or from its sibling region = the limit applies), none (categorical kinds).
Exactly as many positives as negatives sit on a limit (``meta.margin`` at_limit) and one step from it (one_step).  The other numeric constraints are
satisfied in both members, on their limit or within two steps in half of the cases.  The cents of money limits are drawn at random (no digit pattern tells the classes apart).
Dial: constraints 6 / 9 / 12 (200 items each); every computed kind has 21 negatives (7 per level), every simple kind 9 (3 per level).
Truth twice.  ``truth_v2(spec)`` evaluates the structured constraints on the record; ``check_v2(item)`` parses the rendered request (stated limits,
conversion factors, reference days, lists of certifications) and evaluates it on the record again with its own date and fraction arithmetic; the script
asserts that both agree on all 600 items, that exactly the planted constraint fails in a negative, that the records of a pair differ in one field,
and that classes, levels, kinds and margins are balanced.

gen_v4 (2026-10-08) fixes four defects that the human audit found in v2 (the pair design, patterns, margins, balances and the twenty kinds are unchanged):
 (1) Day counts.  A request that counts days between two dates (date_gap, listing_age) ends with a sentence that states the convention (a count of days is the
     difference between the two dates, the same day is 0 days; four phrasings); a request with ready_by adds the sentence for "a date plus N days" (N days later).
     check_v2 reads these sentences and refuses a request that counts days without one.
 (2) Field wording.  The maker is only "made by" / "its maker is" / "the maker is", a region only "ships to" / "shipped to", the origin of the conditional kind only
     "ships from", the listing age is always "counted from the listing date", categories are "filed under"; FOREIGN asserts for every clause that no wording of another field occurs.
 (3) Plausible records.  PROFILE gives the plausible range of the price (euros; kronor count ten times as much) and of every physical spec (weight, length, width, volume, run time,
     power, battery, noise) of each of the 20 categories (a spec a category does not have is not in its records); every limit of a price or spec kind is drawn inside the range of the
     category and the near misses stay one step from it; the width is below the length; list price >= price; a bundle costs bundle size x (0.70 to 0.95) x the price, so the unit
     price limit lies near the price; the shipping fee is a few percent of the price.  check_plausible asserts all of it on every record.
 (4) meta.level = 1 / 2 / 3 for 6 / 9 / 12 constraints (meta.constraints stays).

VERSION v1 (DIFFICULTY = "v1")

Item design.  The state is a request in words with 3, 5 or 7 constraints over a catalogue record of an invented product, and
the record itself as a JSON object (id, title, category, maker, price and currency, rating and four more numeric features,
shipping regions, tags, release date, availability date).  Ten constraint kinds (also the values of ``meta.deviation``):
  price_max      the price is at most / less than ...            feature_min   a feature (rating, warranty, stock, battery, ...) is at least / more than ...
  feature_max    a feature (weight, width, power) is at most ... category      the category is ...
  excluded_tag   the record does not carry the tag ...            required_tag  the record carries the tag ...
  region         it ships to ...                                   maker_in      the maker is one of ...
  date_max       the availability date is on or before / before   date_min      the release date is on or after / after
Bounds are stated in words ("at most" counts the limit, "less than" does not; "on or before" counts the date, "before" does not).
The gold answer is yes when the record satisfies every constraint and no when it violates one.

Contrast pairs.  600 items = 300 pairs: the same request with a record that satisfies all constraints (yes), and the same
record with ONE field changed so that exactly one constraint fails by a small margin (no): price 1 to 5 % over the ceiling,
a feature one or a few steps under its minimum, a date one to five days late, the excluded tag present, the required tag
missing, a sibling category or region (same family name, other direction), a maker that is not listed.  The failing constraint
kind is ``meta.deviation`` (30 pairs per kind, 10 per kind and dial level).
Near the limits on both sides.  The planted constraint of a numeric or date kind is always close to its limit, in BOTH members of
the pair: pattern "edge" (the positive sits exactly on an inclusive limit and the negative one step beyond it, or the negative
sits exactly on an exclusive limit and the positive one step inside - equally often) or "mirror" (the positive k steps inside, the
negative k steps outside, k = 1 to 5 % of the limit); other numeric / date constraints of the request are satisfied by a wide
margin in 70 % of the pairs and by a small one in 30 %.  ``meta.margin`` labels the planted constraint of each item.
Dial: constraints 3, 5, 7 (100 pairs each).
Truth twice: ``truth(spec)`` evaluates the structured constraints on the record; ``check(item)`` parses the rendered request
(four layouts, four phrasings per constraint kind, sixteen comparator phrases) and evaluates it on the record again.

Run:
    python3 generators/filter_match.py
"""
import collections
import datetime
import json
import math
import os
import random
import re
import subprocess
import sys
from decimal import Decimal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repository root (this file is generators/<family>.py)
HERE = os.path.join(REPO, "generated")                               # the items are written to HERE/tasks/<family>/
AUDITS = os.path.join(REPO, "audits")                                # validate.py and audit.py, run on HERE/tasks/<family>/
SEED = 20261007
TASK = "filter_match"
PAIRS = 300
DIFFICULTY = "v2"        # "v2": the harder dials (default, what the task directory holds) | "v1": the first version (easier dials)
DIFFICULTY = os.environ.get("BENCH_DIFFICULTY", DIFFICULTY)             # e.g. BENCH_DIFFICULTY=v1 python3 generators/filter_match.py
assert DIFFICULTY in ("v1", "v2"), DIFFICULTY
KINDS = ["price_max", "feature_min", "feature_max", "category", "excluded_tag", "required_tag", "region", "date_max", "date_min",
         "maker_in"]
NUMERIC_KINDS = ["price_max", "feature_min", "feature_max", "date_max", "date_min"]
INSTRUCTIONS = "Does the record satisfy every constraint of the request?"
OPTIONS = {"yes": "The record satisfies every constraint of the request.",
           "no": "The record violates at least one constraint of the request."}


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


def coin(rng):
    while True:
        w = (rng.choice(START).lower() + rng.choice(END)).capitalize()
        if w.lower() not in BLOCK:
            return w


# ------------------------------------------------------------------------------------------------ catalogue data
def D(x):
    return Decimal(str(x))


NUM = {   # numeric features: label in the request, record field, unit text, step, decimals, plausible range, limits, directions
    "price": dict(label="price", field="price", unit=None, step=D(1), dec=0, lo=20, hi=900, dirs=("max",),
                  ths=[50, 60, 75, 80, 100, 120, 150, 200, 250, 300, 400, 450, 500, 750]),
    "rating": dict(label="rating", field="rating", unit="", step=D("0.1"), dec=1, lo=2.0, hi=5.0, dirs=("min",),
                   ths=[3.0, 3.2, 3.5, 3.8, 4.0, 4.2]),
    "weight": dict(label="weight", field="weight_kg", unit="kg", step=D("0.1"), dec=1, lo=0.3, hi=25.0, dirs=("max",),
                   ths=[2.0, 2.5, 3.0, 4.0, 5.0, 8.0, 10.0, 15.0]),
    "warranty": dict(label="warranty", field="warranty_months", unit="months", step=D(1), dec=0, lo=6, hi=60, dirs=("min",),
                     ths=[24, 30, 36, 48]),
    "stock": dict(label="stock", field="stock_units", unit="units", step=D(1), dec=0, lo=0, hi=500, dirs=("min",),
                  ths=[25, 30, 50, 75, 100, 150, 200]),
    "width": dict(label="width", field="width_cm", unit="cm", step=D(1), dec=0, lo=20, hi=220, dirs=("max",),
                  ths=[40, 50, 60, 80, 100, 120, 160]),
    "power": dict(label="power", field="power_w", unit="W", step=D(1), dec=0, lo=5, hi=2000, dirs=("min", "max"),
                  ths=[40, 60, 100, 150, 250, 500, 800, 1200]),
    "battery": dict(label="battery capacity", field="battery_mah", unit="mAh", step=D(10), dec=0, lo=1000, hi=20000, dirs=("min",),
                    ths=[2000, 3000, 4000, 5000, 6000, 8000, 10000, 12000]),
    "capacity": dict(label="capacity", field="capacity_l", unit="litres", step=D(1), dec=0, lo=5, hi=150, dirs=("min",),
                     ths=[20, 25, 30, 40, 50, 75, 100]),
}
DATES = {"date_max": dict(label="availability date", field="available_from", dirs="max", lo="2026-01-05", hi="2026-07-30",
                          lim_lo="2026-02-01", lim_hi="2026-05-31"),
         "date_min": dict(label="release date", field="release_date", dirs="min", lo="2023-01-10", hi="2025-12-20",
                          lim_lo="2024-01-01", lim_hi="2025-06-30")}
DOMAINS = [
    {"name": "outdoor", "nouns": ["lamp", "stove", "tent", "backpack", "cooler", "kettle"],
     "cats": ["Outdoor lighting", "Outdoor cooking", "Outdoor furniture", "Outdoor storage", "Outdoor tools"],
     "features": ["weight", "capacity", "warranty", "stock"]},
    {"name": "audio", "nouns": ["speaker", "headset", "amplifier", "microphone", "turntable", "radio"],
     "cats": ["Audio players", "Audio accessories", "Audio recording", "Audio amplifiers", "Audio cables"],
     "features": ["power", "battery", "warranty", "weight"]},
    {"name": "kitchen", "nouns": ["blender", "toaster", "grill", "mixer", "cooker", "scale"],
     "cats": ["Kitchen cooking", "Kitchen cleaning", "Kitchen storage", "Kitchen tools", "Kitchen small appliances"],
     "features": ["power", "capacity", "weight", "warranty"]},
    {"name": "office", "nouns": ["chair", "desk", "shelf", "lamp", "cabinet", "stand"],
     "cats": ["Office seating", "Office desks", "Office storage", "Office lighting", "Office accessories"],
     "features": ["width", "weight", "warranty", "stock"]},
]
EXCLUDABLE = ["refurbished", "clearance", "demo", "seconds", "imported", "bulk"]
REQUIRABLE = ["new", "eco", "gift", "limited", "handmade", "bundle"]
DIRECTIONS = ["North", "South", "East", "West"]
CURRENCIES = ["EUR", "USD", "GBP", "CHF", "SEK"]
UNITS_RE = "EUR|USD|GBP|CHF|SEK|kg|cm|W|mAh|litres|months|units"

# comparator phrases ({v} = the limit with its unit); wording fixes whether the limit itself counts
CMP = {"<=": ["at most {v}", "no more than {v}", "{v} or less", "not above {v}"],
       "<": ["less than {v}", "under {v}", "below {v}", "lower than {v}"],
       ">=": ["at least {v}", "no less than {v}", "{v} or more", "not below {v}"],
       ">": ["more than {v}", "over {v}", "above {v}", "higher than {v}"]}
DCMP = {"<=": ["on or before {v}", "no later than {v}", "not after {v}", "{v} at the latest"],
        "<": ["before {v}", "earlier than {v}", "strictly before {v}", "prior to {v}"],
        ">=": ["on or after {v}", "no earlier than {v}", "not before {v}", "from {v} onwards"],
        ">": ["after {v}", "later than {v}", "strictly after {v}", "subsequent to {v}"]}
NUM_FRAMES = ["the {lab} is {cp}", "the {lab} must be {cp}", "its {lab} is {cp}", "it has a {lab} that is {cp}"]
DATE_FRAMES = ["the {lab} is {cp}", "the {lab} must be {cp}", "its {lab} is {cp}", "the {lab} has to be {cp}"]
CAT_FRAMES = ["its category is {c}", "it is listed under the category {c}", "it belongs to the category {c}", "the category must be {c}"]
EXC_FRAMES = ["it does not carry the tag {t}", "it is not tagged {t}", "the tag {t} must be absent", "it has no {t} tag"]
REQ_FRAMES = ["it carries the tag {t}", "it is tagged {t}", "the tag {t} must be present", "it has the {t} tag"]
REG_FRAMES = ["it ships to {r}", "shipping to {r} is possible", "{r} is one of its shipping regions", "it can be delivered to {r}"]
MAK_FRAMES = ["it is made by {m}", "its maker is one of {m2}", "the maker is {m}", "it comes from {m}"]
LAYOUT_LEAD = ["I need a listing where ", "Find a listing that meets every requirement below:", "Requirements (all must hold):",
               "The listing must satisfy every point below. "]


def num_text(d):
    return format(D(d).normalize(), "f")


def to_json_number(d, dec):
    return int(d) if dec == 0 else float(d)


# -------------------------------------------------------------------------------------- truth on the specification
def holds(c, rec):
    """does the record satisfy constraint c (structured form)"""
    k = c["kind"]
    if k in ("price_max", "feature_min", "feature_max"):
        v, lim = D(rec[c["field"]]), D(c["limit"])
        return {"<=": v <= lim, "<": v < lim, ">=": v >= lim, ">": v > lim}[c["op"]]
    if k in ("date_max", "date_min"):
        v, lim = rec[c["field"]], c["limit"]
        return {"<=": v <= lim, "<": v < lim, ">=": v >= lim, ">": v > lim}[c["op"]]
    if k == "category":
        return rec["category"] == c["value"]
    if k == "excluded_tag":
        return c["value"] not in rec["tags"]
    if k == "required_tag":
        return c["value"] in rec["tags"]
    if k == "region":
        return c["value"] in rec["ships_to"]
    return rec["maker"] in c["values"]


def truth(spec):
    return all(holds(c, spec["record"]) for c in spec["constraints"])


# ---------------------------------------------------------- check: the answer from the rendered text alone
NUMLAB = "|".join(re.escape(v["label"]) for v in sorted(NUM.values(), key=lambda v: -len(v["label"])))
DATELAB = "|".join(re.escape(v["label"]) for v in DATES.values())
FIELD_OF = {v["label"]: v["field"] for v in list(NUM.values()) + list(DATES.values())}
NUMV = rf"(?P<v>\d+(?:\.\d+)?)(?: (?:{UNITS_RE}))?"
DATEV = r"(?P<v>\d{4}-\d\d-\d\d)"
# what each wording means, written out again here (the renderer's tables are not used): (operator, pattern of the comparator phrase)
NUM_CP = [("<=", rf"at most {NUMV}"), ("<=", rf"no more than {NUMV}"), ("<=", rf"{NUMV} or less"), ("<=", rf"not above {NUMV}"),
          ("<", rf"less than {NUMV}"), ("<", rf"under {NUMV}"), ("<", rf"below {NUMV}"), ("<", rf"lower than {NUMV}"),
          (">=", rf"at least {NUMV}"), (">=", rf"no less than {NUMV}"), (">=", rf"{NUMV} or more"), (">=", rf"not below {NUMV}"),
          (">", rf"more than {NUMV}"), (">", rf"over {NUMV}"), (">", rf"above {NUMV}"), (">", rf"higher than {NUMV}")]
DATE_CP = [("<=", rf"on or before {DATEV}"), ("<=", rf"no later than {DATEV}"), ("<=", rf"not after {DATEV}"), ("<=", rf"{DATEV} at the latest"),
           ("<", rf"before {DATEV}"), ("<", rf"earlier than {DATEV}"), ("<", rf"strictly before {DATEV}"), ("<", rf"prior to {DATEV}"),
           (">=", rf"on or after {DATEV}"), (">=", rf"no earlier than {DATEV}"), (">=", rf"not before {DATEV}"), (">=", rf"from {DATEV} onwards"),
           (">", rf"after {DATEV}"), (">", rf"later than {DATEV}"), (">", rf"strictly after {DATEV}"), (">", rf"subsequent to {DATEV}")]
NUM_PATTERNS = [(op, pre + rf"(?P<lab>{NUMLAB})" + mid + cp) for pre, mid in
                [("the ", " is "), ("the ", " must be "), ("its ", " is "), ("it has a ", " that is ")] for op, cp in NUM_CP]
DATE_PATTERNS = [(op, pre + rf"(?P<lab>{DATELAB})" + mid + cp) for pre, mid in
                 [("the ", " is "), ("the ", " must be "), ("its ", " is "), ("the ", " has to be ")] for op, cp in DATE_CP]
CATV = r"(?P<c>[A-Z][a-z]+(?: [a-z]+)+)"
TAGV = r"(?P<t>[a-z]+)"
REGV = r"(?P<r>[A-Z][a-z]+-(?:North|South|East|West))"
MAKV = r"(?P<m>[A-Z][a-z]+(?:, [A-Z][a-z]+)*(?: or [A-Z][a-z]+)?)"
MAKV2 = r"(?P<m>[A-Z][a-z]+(?:, [A-Z][a-z]+)+)"
OTHER_PATTERNS = [("category", rf"its category is {CATV}"), ("category", rf"it is listed under the category {CATV}"),
                  ("category", rf"it belongs to the category {CATV}"), ("category", rf"the category must be {CATV}"),
                  ("excluded_tag", rf"it does not carry the tag {TAGV}"), ("excluded_tag", rf"it is not tagged {TAGV}"),
                  ("excluded_tag", rf"the tag {TAGV} must be absent"), ("excluded_tag", rf"it has no {TAGV} tag"),
                  ("required_tag", rf"it carries the tag {TAGV}"), ("required_tag", rf"it is tagged {TAGV}"),
                  ("required_tag", rf"the tag {TAGV} must be present"), ("required_tag", rf"it has the {TAGV} tag"),
                  ("region", rf"it ships to {REGV}"), ("region", rf"shipping to {REGV} is possible"),
                  ("region", rf"{REGV} is one of its shipping regions"), ("region", rf"it can be delivered to {REGV}"),
                  ("maker_in", rf"it is made by {MAKV}"), ("maker_in", rf"its maker is one of {MAKV2}"),
                  ("maker_in", rf"the maker is {MAKV}"), ("maker_in", rf"it comes from {MAKV}")]


def split_clauses(req):
    lines = req.split("\n")
    if req.startswith(LAYOUT_LEAD[0]):
        parts = req[len(LAYOUT_LEAD[0]):]
        assert parts.endswith(".")
        parts = parts[:-1].split("; ")
        parts[-1] = re.sub(r"^and ", "", parts[-1])
    elif lines[0] == LAYOUT_LEAD[1]:
        parts = [re.sub(r"^- ", "", ln) for ln in lines[1:]]
    elif lines[0] == LAYOUT_LEAD[2]:
        parts = [re.sub(r"^\d+\) ", "", ln) for ln in lines[1:]]
    else:
        assert req.startswith(LAYOUT_LEAD[3]) and req.endswith(".")
        parts = req[len(LAYOUT_LEAD[3]):-1].split(". ")
    return [p[0].lower() + p[1:] if p.split()[0] in ("The", "Its", "It", "Shipping") else p for p in parts]


def parse_clause(cl):
    hits = []
    for op, pat in NUM_PATTERNS:
        m = re.fullmatch(pat, cl)
        if m:
            hits.append({"kind": "num", "op": op, "field": FIELD_OF[m["lab"]], "limit": m["v"]})
    for op, pat in DATE_PATTERNS:
        m = re.fullmatch(pat, cl)
        if m:
            hits.append({"kind": "date", "op": op, "field": FIELD_OF[m["lab"]], "limit": m["v"]})
    for kind, pat in OTHER_PATTERNS:
        m = re.fullmatch(pat, cl)
        if m:
            g = m.groupdict()
            if kind == "maker_in":
                hits.append({"kind": kind, "values": re.split(r", | or ", g["m"])})
            else:
                hits.append({"kind": kind, "value": g.get("c") or g.get("t") or g.get("r")})
    assert len(hits) == 1, f"clause parsed {len(hits)} times: {cl!r}"
    return hits[0]


def check(item):
    """the answer (True / False) recomputed from the rendered state alone"""
    st = item["state"]
    rec = json.loads(json.dumps(st["record"]))
    for c in (parse_clause(x) for x in split_clauses(st["request"])):
        k = c["kind"]
        if k == "num":
            v, lim = D(rec[c["field"]]), D(c["limit"])
            ok = {"<=": v <= lim, "<": v < lim, ">=": v >= lim, ">": v > lim}[c["op"]]
        elif k == "date":
            v, lim = rec[c["field"]], c["limit"]
            ok = {"<=": v <= lim, "<": v < lim, ">=": v >= lim, ">": v > lim}[c["op"]]
        elif k == "category":
            ok = rec["category"] == c["value"]
        elif k == "excluded_tag":
            ok = c["value"] not in rec["tags"]
        elif k == "required_tag":
            ok = c["value"] in rec["tags"]
        elif k == "region":
            ok = c["value"] in rec["ships_to"]
        else:
            ok = rec["maker"] in c["values"]
        if not ok:
            return False
    return True


# ------------------------------------------------------------------------------------------ building a pair
def snap(x, step):
    return (D(x) / step).to_integral_value() * step


def numeric_constraint(rng, kind, feat, direction, pattern):
    """a numeric constraint with the values of the positive and the negative record for the planted one"""
    spec = NUM[feat]
    limit = D(rng.choice(spec["ths"]))
    if pattern == "edge_pos":
        inclusive = True
    elif pattern == "edge_neg":
        inclusive = False
    else:
        inclusive = rng.random() < 0.5
    op = {("max", True): "<=", ("max", False): "<", ("min", True): ">=", ("min", False): ">"}[(direction, inclusive)]
    return {"kind": kind, "feature": feat, "field": spec["field"], "op": op, "limit": to_json_number(limit, spec["dec"]) if spec["dec"] == 0 else float(limit),
            "unit": spec["unit"], "dec": spec["dec"], "direction": direction, "inclusive": inclusive}


def num_values(rng, c, pattern):
    """(value of the positive, value of the negative) for the planted numeric constraint"""
    spec = NUM[c["feature"]]
    step, lim = spec["step"], D(c["limit"])
    inward = -1 if c["direction"] == "max" else 1                     # direction of 'inside'
    if pattern == "edge_pos":
        pos, neg = lim, lim - inward * step
    elif pattern == "edge_neg":
        pos, neg = lim + inward * step, lim
    else:
        k = max(1, int((lim * D(rng.choice(["0.01", "0.02", "0.03", "0.05"])) / step).to_integral_value()))
        k = min(k, max(1, int(lim * D("0.05") / step)))              # never more than 5 % of the limit
        pos, neg = lim + inward * k * step, lim - inward * k * step
    return pos, neg


def num_inside(rng, c, wide):
    """a value that satisfies the (non-planted) numeric constraint: by a wide margin (at least three steps), or by a small one"""
    spec = NUM[c["feature"]]
    step, lim = spec["step"], D(c["limit"])
    inward = -1 if c["direction"] == "max" else 1
    if wide:
        far = lim + inward * 3 * step
        lo, hi = (D(spec["lo"]), far) if inward < 0 else (far, D(spec["hi"]))
        if lo < hi:
            return snap(lo + (hi - lo) * D(rng.random()), step)
        return far
    k = rng.choice([0, 1, 1, 2, 3])
    if k == 0 and not c["inclusive"]:
        k = 1
    return lim + inward * k * step


def date_constraint(rng, kind, pattern):
    spec = DATES[kind]
    a, b = datetime.date.fromisoformat(spec["lim_lo"]), datetime.date.fromisoformat(spec["lim_hi"])
    limit = a + datetime.timedelta(days=rng.randrange((b - a).days + 1))
    inclusive = True if pattern == "edge_pos" else False if pattern == "edge_neg" else rng.random() < 0.5
    op = {("max", True): "<=", ("max", False): "<", ("min", True): ">=", ("min", False): ">"}[(spec["dirs"], inclusive)]
    return {"kind": kind, "field": spec["field"], "op": op, "limit": limit.isoformat(), "direction": spec["dirs"], "inclusive": inclusive}


def date_values(rng, c, pattern):
    lim = datetime.date.fromisoformat(c["limit"])
    inward = -1 if c["direction"] == "max" else 1
    one = datetime.timedelta(days=1)
    if pattern == "edge_pos":
        pos, neg = lim, lim - inward * one
    elif pattern == "edge_neg":
        pos, neg = lim + inward * one, lim
    else:
        k = datetime.timedelta(days=rng.choice([1, 2, 3, 5]))
        pos, neg = lim + inward * k, lim - inward * k
    return pos.isoformat(), neg.isoformat()


def date_inside(rng, c, wide):
    lim = datetime.date.fromisoformat(c["limit"])
    inward = -1 if c["direction"] == "max" else 1
    k = rng.randint(25, 120) if wide else rng.choice([0, 1, 1, 2, 3])
    if k == 0 and not c["inclusive"]:
        k = 1
    return (lim + inward * datetime.timedelta(days=k)).isoformat()


def margin_of(c, value):
    """label and size of the distance of a record value to the limit of a numeric / date constraint"""
    if c["kind"] in ("date_max", "date_min"):
        days = abs((datetime.date.fromisoformat(value) - datetime.date.fromisoformat(c["limit"])).days)
        return ("at_limit" if days == 0 else "tiny" if days == 1 else "small" if days <= 7 else "wide"), days
    pct = float(abs(D(value) - D(c["limit"])) / D(c["limit"]) * 100)
    return ("at_limit" if pct == 0 else "tiny" if pct <= 1 else "small" if pct <= 5 else "wide"), round(pct, 2)


def pick_frame(rng, phrase, frames):
    """a frame for the comparator phrase; 'must be' / 'has to be' do not take a phrase that starts with 'not'"""
    ok = [i for i, f in enumerate(frames) if not (phrase.startswith("not ") and ("must be" in f or "has to be" in f))]
    return rng.choice(ok)


def clause(c, rng, frame_cmp, currency):
    k = c["kind"]
    if k in ("price_max", "feature_min", "feature_max"):
        unit = currency if k == "price_max" else c["unit"]
        v = num_text(c["limit"]) + (f" {unit}" if unit else "")
        cp = CMP[c["op"]][frame_cmp].format(v=v)
        return NUM_FRAMES[pick_frame(rng, cp, NUM_FRAMES)].format(lab=NUM[c["feature"]]["label"], cp=cp)
    if k in ("date_max", "date_min"):
        cp = DCMP[c["op"]][frame_cmp].format(v=c["limit"])
        return DATE_FRAMES[pick_frame(rng, cp, DATE_FRAMES)].format(lab=DATES[k]["label"], cp=cp)
    frame = rng.randrange(4)
    if k == "category":
        return CAT_FRAMES[frame].format(c=c["value"])
    if k == "excluded_tag":
        return EXC_FRAMES[frame].format(t=c["value"])
    if k == "required_tag":
        return REQ_FRAMES[frame].format(t=c["value"])
    if k == "region":
        return REG_FRAMES[frame].format(r=c["value"])
    vs = c["values"]
    m = ", ".join(vs[:-1]) + " or " + vs[-1] if len(vs) > 1 else vs[0]
    return MAK_FRAMES[frame].format(m=m, m2=", ".join(vs))


def render_request(clauses, layout):
    cap = lambda s: s[0].upper() + s[1:]
    if layout == 0:
        return LAYOUT_LEAD[0] + "; ".join(clauses[:-1]) + "; and " + clauses[-1] + "."
    if layout == 1:
        return LAYOUT_LEAD[1] + "\n" + "\n".join(f"- {cap(x)}" for x in clauses)
    if layout == 2:
        return LAYOUT_LEAD[2] + "\n" + "\n".join(f"{n}) {cap(x)}" for n, x in enumerate(clauses, 1))
    return LAYOUT_LEAD[3] + " ".join(f"{cap(x)}." for x in clauses)


def make_pair(i, plan):
    """-> (positive spec, negative spec, info); retries with fresh random draws until the pair is valid"""
    for attempt in range(300):
        rng = rng_for("pair", i, attempt)
        try:
            return _make_pair(rng, plan)
        except (RuntimeError, ValueError):
            continue
    raise RuntimeError(f"pair {i}: no valid draw")


def _make_pair(rng, plan):
    dom = DOMAINS[plan["domain"]]
    n_con, planted = plan["constraints"], plan["kind"]
    currency = rng.choice(CURRENCIES)
    # ---- the kinds of the request: the planted one and distinct others; numeric features get distinct fields
    others = rng.sample([k for k in KINDS if k != planted], n_con - 1)
    kinds = [planted] + others
    rng.shuffle(kinds)
    min_f = rng.choice([f for f in ["rating"] + dom["features"] if "min" in NUM[f]["dirs"]])
    max_f = rng.choice([f for f in dom["features"] if "max" in NUM[f]["dirs"] and f != min_f])
    makers = []
    while len(makers) < 6:
        m = coin(rng)
        if m not in makers:
            makers.append(m)
    bases = []
    while len(bases) < 3:
        b = coin(rng)
        if b not in bases:
            bases.append(b)
    regions = [f"{b}-{d}" for b in bases for d in DIRECTIONS]
    pattern = plan["pattern"]                                      # edge_pos / edge_neg / mirror (numeric and date kinds)
    rec = {}                                                        # the record of the positive
    neg_change = None                                               # (field, new value, old value) of the planted violation
    excluded, required = [], []
    cons = []
    for kind in kinds:
        is_p = kind == planted
        pat = pattern if is_p else "free"
        if kind == "price_max":
            c = numeric_constraint(rng, kind, "price", "max", pat)
        elif kind == "feature_min":
            c = numeric_constraint(rng, kind, min_f, "min", pat)
        elif kind == "feature_max":
            c = numeric_constraint(rng, kind, max_f, "max", pat)
        elif kind in ("date_max", "date_min"):
            c = date_constraint(rng, kind, pat)
        elif kind == "category":
            c = {"kind": kind, "field": "category", "value": rng.choice(dom["cats"])}
        elif kind == "excluded_tag":
            c = {"kind": kind, "field": "tags", "value": rng.choice([t for t in EXCLUDABLE if t not in excluded])}
            excluded.append(c["value"])
        elif kind == "required_tag":
            c = {"kind": kind, "field": "tags", "value": rng.choice([t for t in REQUIRABLE if t not in required])}
            required.append(c["value"])
        elif kind == "region":
            c = {"kind": kind, "field": "ships_to", "value": rng.choice(regions)}
        else:
            c = {"kind": kind, "field": "maker", "values": rng.sample(makers, rng.choice([2, 3]))}
        cons.append(c)
    # ---- record values that satisfy every constraint (positive) and the planted change (negative)
    for c in cons:
        k, is_p = c["kind"], c["kind"] == planted
        if k in ("price_max", "feature_min", "feature_max"):
            if is_p:
                pv, nv = num_values(rng, c, pattern)
                rec[c["field"]] = pv
                neg_change = (c["field"], nv, pv)
            else:
                rec[c["field"]] = num_inside(rng, c, wide=rng.random() < 0.7)
        elif k in ("date_max", "date_min"):
            if is_p:
                pv, nv = date_values(rng, c, pattern)
                rec[c["field"]] = pv
                neg_change = (c["field"], nv, pv)
            else:
                rec[c["field"]] = date_inside(rng, c, wide=rng.random() < 0.7)
        elif k == "category":
            rec["category"] = c["value"]
            if is_p:
                neg_change = ("category", rng.choice([x for x in dom["cats"] if x != c["value"]]), c["value"])
        elif k == "region":
            ships = rng.sample([r for r in regions if r != c["value"]], rng.randint(2, 3))
            ships.insert(rng.randrange(len(ships) + 1), c["value"])
            rec["ships_to"] = ships
            if is_p:
                base = c["value"].split("-")[0]
                sib = [r for r in regions if r.startswith(base + "-") and r != c["value"] and r not in ships]
                if not sib:
                    raise RuntimeError("no sibling region")
                neg_change = ("ships_to", [rng.choice(sib) if r == c["value"] else r for r in ships], ships)
        elif k == "maker_in":
            rec["maker"] = rng.choice(c["values"])
            if is_p:
                neg_change = ("maker", rng.choice([m for m in makers if m not in c["values"]]), rec["maker"])
    # tags: every required tag present, no excluded tag, filler tags in between
    filler_pool = [t for t in EXCLUDABLE + REQUIRABLE if t not in excluded and t not in required]
    fillers = rng.sample(filler_pool, rng.randint(1, 2))
    tags = list(required) + fillers
    rng.shuffle(tags)
    rec["tags"] = tags
    for c in cons:
        if c["kind"] == planted == "excluded_tag":
            i_f = tags.index(rng.choice(fillers))
            neg_change = ("tags", [c["value"] if j == i_f else t for j, t in enumerate(tags)], tags)
        if c["kind"] == planted == "required_tag":
            decoy = rng.choice([t for t in filler_pool if t not in tags])
            neg_change = ("tags", [decoy if t == c["value"] else t for t in tags], tags)
    # fields no constraint fixes
    rec.setdefault("category", rng.choice(dom["cats"]))
    rec.setdefault("maker", rng.choice(makers))
    rec.setdefault("ships_to", rng.sample(regions, rng.randint(2, 4)))
    feats = ["rating"] + dom["features"]
    for f in ["price"] + feats:
        spec = NUM[f]
        if spec["field"] not in rec:
            v = D(rng.uniform(spec["lo"], spec["hi"]))
            rec[spec["field"]] = snap(v, spec["step"])
    for kind, spec in DATES.items():
        if spec["field"] not in rec:
            a, b = datetime.date.fromisoformat(spec["lo"]), datetime.date.fromisoformat(spec["hi"])
            rec[spec["field"]] = (a + datetime.timedelta(days=rng.randrange((b - a).days + 1))).isoformat()
    for f in ["price"] + feats:                                     # Decimal -> JSON number
        spec = NUM[f]
        rec[spec["field"]] = to_json_number(D(rec[spec["field"]]), spec["dec"])
    for c in cons:                                                   # limits as JSON numbers
        if "feature" in c:
            c["limit"] = to_json_number(D(c["limit"]), c["dec"])
    n_id = rng.randint(10000, 99999)
    rec.update({"id": f"L-{n_id}", "sku": f"SKU-{n_id}-{rng.choice('ABCDEFGH')}", "title": f"{coin(rng)} {rng.choice(['S', 'X', 'M', 'Pro', 'Mini', 'Plus'])}-{rng.randint(100, 999)}",
                "seller": f"{coin(rng)} {rng.choice(['Outlet', 'Shop', 'Direct', 'Store', 'Depot'])}", "currency": currency,
                "colour": rng.choice(["black", "white", "grey", "green", "blue", "red", "sand", "orange"]),
                "reviews": rng.randint(3, 4000), "return_window_days": rng.choice([14, 21, 30, 45, 60]), "listing_status": "active"})
    order = ["id", "sku", "title", "category", "maker", "seller", "price", "currency", "rating"] + [NUM[f]["field"] for f in dom["features"]] + \
            ["colour", "reviews", "return_window_days", "ships_to", "tags", "release_date", "available_from", "listing_status"]
    pos_rec = {k: rec[k] for k in order}
    field, new_value = neg_change[0], neg_change[1]
    if field in {v["field"] for v in NUM.values()}:
        new_value = to_json_number(D(new_value), next(v["dec"] for v in NUM.values() if v["field"] == field))
    neg_rec = dict(pos_rec)
    neg_rec[field] = new_value
    rng.shuffle(cons)                                                # the order of the constraints in the request
    layout = rng.randrange(4)
    clauses = [clause(c, rng, rng.randrange(4), currency) for c in cons]
    request = render_request(clauses, layout)
    planted_c = next(c for c in cons if c["kind"] == planted)
    return ({"constraints": cons, "record": pos_rec, "request": request},
            {"constraints": cons, "record": neg_rec, "request": request},
            {"planted": planted_c, "change": [field, new_value, pos_rec[field]], "currency": currency, "domain": dom["name"]})


# --------------------------------------------------------------------------------------------------- the plan
def make_plan():
    """300 pairs: constraints 3 / 5 / 7 x ten kinds (10 pairs each); the numeric and date kinds get the patterns edge_pos 9,
    edge_neg 9, mirror 12 (per kind), so that exactly as many positives as negatives sit on a limit"""
    rng = rng_for("plan")
    plan = []
    for n_con in (3, 5, 7):
        for kind in KINDS:
            plan += [{"constraints": n_con, "kind": kind} for _ in range(10)]
    for kind in NUMERIC_KINDS:
        idx = [k for k, p in enumerate(plan) if p["kind"] == kind]
        pats = ["edge_pos"] * 9 + ["edge_neg"] * 9 + ["mirror"] * 12
        rng.shuffle(pats)
        for k, pat in zip(idx, pats):
            plan[k]["pattern"] = pat
    for p in plan:
        p.setdefault("pattern", "none")
    doms = [k % 4 for k in range(PAIRS)]
    rng.shuffle(doms)
    for p, d in zip(plan, doms):
        p["domain"] = d
    rng.shuffle(plan)
    return plan


def to_item(n, pair, spec, info, dev):
    c = info["planted"]
    meta = {"source_id": f"{n:05d}", "pair": pair, "constraints": len(spec["constraints"]), "deviation": dev or "none",
            "planted_kind": c["kind"], "planted_field": c["field"], "domain": info["domain"],
            "kinds": sorted(x["kind"] for x in spec["constraints"])}
    if c["kind"] in NUMERIC_KINDS:
        val = spec["record"][c["field"]]
        meta["margin"], meta["margin_value"] = margin_of(c, val if isinstance(val, str) else str(val))
        meta["limit_wording"] = "inclusive" if c["inclusive"] else "exclusive"
    else:
        meta["margin"], meta["margin_value"] = "categorical", None
    meta["spec"] = {"constraints": spec["constraints"], "change": info["change"] if dev else None}
    return {"id": f"{TASK}:{n:05d}", "state": {"request": spec["request"], "record": spec["record"]},
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


# --------------------------------------------------------------------------------------------------- output
def run_tool(script, *args):
    r = subprocess.run([sys.executable, os.path.join(AUDITS, script), "--root", HERE] + list(args), capture_output=True, text=True, cwd=REPO)
    return r.stdout.strip().split("\n")


def fmt_item(it):
    out = [f"id `{it['id']}` (pair `{it['group']}`, gold **{it['gold']}**, deviation `{it['meta']['deviation']}`, margin `{it['meta']['margin']}`)", "",
           "state.request:", "```", it["state"]["request"], "```", "state.record:", "```", json.dumps(it["state"]["record"], indent=1, ensure_ascii=False), "```",
           f"question: {it['questions']['q']['instructions']}", ""]
    out += [f"- `{k}`: {v}" for k, v in it["questions"]["q"]["criteria"].items()]
    return "\n".join(out)


def main_v1():
    plan = make_plan()
    built = []
    for i, p in enumerate(plan):
        pos, neg, info = make_pair(i, p)
        built.append((i, p, pos, info, None))
        built.append((i, p, neg, info, p["kind"]))
    rng = rng_for("order")
    rng.shuffle(built)
    rows = []
    for n, (pair, p, spec, info, dev) in enumerate(built, 1):
        it = to_item(n, pair, spec, info, dev)
        # ---- truth twice
        assert truth(spec) == (dev is None), f"{it['id']}: truth {truth(spec)} but planted deviation {dev}"
        assert check(it) == truth(spec), f"{it['id']}: check {check(it)} != truth {truth(spec)}"
        # ---- exactly one constraint fails, and it is the planted one
        failing = [c for c in spec["constraints"] if not holds(c, spec["record"])]
        assert [c["kind"] for c in failing] == ([] if dev is None else [dev]), (it["id"], [c["kind"] for c in failing])
        assert len(spec["constraints"]) == p["constraints"]
        it["_class"] = it["gold"]
        rows.append(it)
    rows.sort(key=lambda r: r["id"])
    assign_orders(rows)
    by_pair = collections.defaultdict(dict)
    for it in rows:
        by_pair[it["meta"]["pair"]][it["gold"]] = it
    for k, d in by_pair.items():                                     # the pair differs in exactly one field of the record
        a, b = d["yes"]["state"]["record"], d["no"]["state"]["record"]
        assert [f for f in a if a[f] != b[f]] == [d["no"]["meta"]["planted_field"]], k
        assert d["yes"]["state"]["request"] == d["no"]["state"]["request"]
        assert list(a) == list(b)
    # ---- balance and dials
    cls = collections.Counter(r["gold"] for r in rows)
    assert cls == {"yes": 300, "no": 300}, cls
    nc = collections.Counter(r["meta"]["constraints"] for r in rows)
    assert set(nc.values()) == {200} and set(nc) == {3, 5, 7}, nc
    dev = collections.Counter(r["meta"]["deviation"] for r in rows)
    assert dev["none"] == 300 and all(dev[k] == 30 for k in KINDS), dev
    per = collections.Counter((r["meta"]["constraints"], r["meta"]["deviation"]) for r in rows)
    assert all(per[(n, k)] == 10 for n in (3, 5, 7) for k in KINDS), per
    margin = collections.Counter((r["gold"], r["meta"]["margin"]) for r in rows)
    assert margin[("yes", "at_limit")] == margin[("no", "at_limit")] == 45, margin
    near = {g: sum(margin[(g, m)] for m in ("at_limit", "tiny", "small")) for g in ("yes", "no")}
    assert near["yes"] == near["no"] == 150, near
    tested, worst = vocabulary_test(rows, ["yes", "no"])
    lengths = [len(state_text(r)) for r in rows]
    for r in rows:
        del r["_class"]
    d = f"{HERE}/tasks/{TASK}"
    os.makedirs(d, exist_ok=True)
    with open(f"{d}/items.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(rows, key=lambda r: r["id"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    task = {"task": TASK, "layer": "G", "title": "Generated catalogue requests: does the record satisfy every constraint?",
            "decision": "whether a catalogue record satisfies every constraint of a request (yes) or violates one of them by a small margin (no)",
            "source": {"name": f"generator build/gen_{TASK}.py", "url": "", "files": [], "split": "generated, seed 20261007",
                       "version": "script of 2026-10-07"},
            "licence": "generated by the benchmark's script (no third-party text)", "redistribution": "items included",
            "labels": "programmatic", "item_source": "generated", "metric": "accuracy", "chance": 0.5, "rows": len(rows),
            "groups": PAIRS, "question_type": "choice", "options": 2,
            "notes": ("600 items = 300 contrast pairs (meta.pair, group): one request with a record that satisfies all constraints (yes) and the same "
                      "record with one field changed so that exactly one constraint fails by a small margin (no). The metric is item accuracy; the group "
                      "allows a pair analysis. Dial: constraints (3, 5, 7). Numeric and date constraints that are planted sit close to their limit in both "
                      "members of a pair (meta.margin). Everything is invented and every answer is computed twice (specification and a parser of the "
                      "rendered request). State length %d to %d characters (median %d)." % (min(lengths), max(lengths), sorted(lengths)[300]))}
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
    write_readme_v1(d, rows, dev, margin, lengths, val, aud, tested, worst, near)
    print("vocabulary test:", tested, "tokens with frequency >= 20, worst ratio %.2f (%s)" % worst)
    print("counts per class", dict(cls), "| constraints", dict(nc), "| deviation", dict(dev))
    print("margin (class, label)", sorted(margin.items()))
    print("state length", min(lengths), max(lengths), "median", sorted(lengths)[300])


def write_readme_v1(d, rows, dev, margin, lengths, val, aud, tested, worst, near):
    ex = []
    for n, kind in ((3, "price_max"), (5, "date_max"), (7, "excluded_tag")):
        ex.append(next(x for x in sorted(rows, key=lambda x: x["id"]) if x["meta"]["constraints"] == n and x["meta"]["deviation"] == kind))
    mt = lambda g, m: margin[(g, m)]
    txt = f"""# {TASK}

Generated catalogue requests: does the record satisfy every constraint? (layer G, generated, programmatic truth)

- Decision: whether a catalogue record satisfies every constraint of a request (yes) or violates one of them by a small margin (no).
- Source: generator `build/gen_{TASK}.py` (standard library only, `random.Random(20261007)` and sub-generators; the output is identical on every run); no third-party text.
- Licence: generated by the benchmark's script (no third-party text); items included.
- Rows: {len(rows)} in {PAIRS} contrast pairs (300 yes, 300 no); metric: accuracy (chance 0.5).
- Rebuild: `python3 build/gen_{TASK}.py`

## What is generated

A request in words with 3, 5 or 7 constraints (one of four layouts; four phrasings per constraint kind; sixteen comparator phrases that say in words whether the limit itself counts) and a
catalogue record of an invented product as a JSON object (id, title, category, maker, price and currency, rating and four more numeric features of the domain, shipping regions,
tags, release date, availability date). Ten constraint kinds: price ceiling, feature minimum, feature maximum, required category, excluded tag, required tag, shipping region,
maker among a list, availability date not later than, release date not earlier than. Four domains (outdoor, audio, kitchen, office) with sibling categories and region families
(`Orsk-North` / `Orsk-South`). The answer is yes when the record satisfies every constraint.
The order of the two options is drawn per item (`meta.order`; exactly half of the positives and half of the negatives list `yes` first).

**Pairs.** The positive and the negative of a pair share the request and every field of the record but one. In the negative that one field changes so that exactly one constraint fails by a small
margin (`meta.deviation` = the constraint kind): a price one step to 5 % over the ceiling (or exactly on a ceiling that is stated as "less than"), a feature one to a few steps beyond its limit,
a date one to five days late (or early), the excluded tag present, the required tag missing, a sibling category, a sibling region, a maker that is not listed.

**Near the limits on both sides.** For the numeric and date kinds the planted constraint is close to its limit in both members of a pair: pattern *edge* (the positive sits exactly on an
inclusive limit and the negative one step beyond, or the negative sits exactly on an exclusive limit and the positive one step inside; equally often) or *mirror* (k steps inside / k steps outside, 1 to 5 % of the limit, or 1 to
5 days). Other numeric and date constraints are satisfied by a wide margin in 70 % of the pairs and by a small one in 30 %. `meta.margin` labels the planted constraint of every item
(`at_limit`: distance 0; `tiny`: up to 1 % or one day; `small`: up to 5 % or 7 days; `categorical`: no distance).

| `meta.margin` (planted constraint) | yes | no |
|---|---|---|
| at_limit | {mt('yes', 'at_limit')} | {mt('no', 'at_limit')} |
| tiny | {mt('yes', 'tiny')} | {mt('no', 'tiny')} |
| small | {mt('yes', 'small')} | {mt('no', 'small')} |
| categorical | {mt('yes', 'categorical')} | {mt('no', 'categorical')} |

Positives and negatives sit within a small margin of the limit equally often (planted numeric and date constraints: {near['yes']} of 300 positives, {near['no']} of 300 negatives).

## Dials

| dial | levels | items per level |
|---|---|---|
| `constraints` (in the request) | 3, 5, 7 | 200 each |

State length: {min(lengths)} to {max(lengths)} characters (median {sorted(lengths)[len(lengths)//2]}).

## Deviation kinds (negatives)

| `meta.deviation` | items | per dial level (3 / 5 / 7) |
|---|---|---|
""" + "\n".join(f"| `{k}` | {dev[k]} | 10 / 10 / 10 |" for k in KINDS) + f"""

## Checks made by the script

- `truth(spec)` (structured constraints on the record) and `check(item)` (parses the rendered request and evaluates it on the record again) agree on all 600 items.
- In every pair the request is identical, the records differ in exactly one field, the positive satisfies every constraint and the negative fails exactly one, the planted kind.
- Classes are exactly balanced; every dial level has 200 items; every constraint kind has 30 negatives (10 per level).
- Exactly as many positives as negatives sit exactly on a limit (45 each).
- Vocabulary test: {tested} tokens of frequency >= 20 are tested; none occurs in one class at more than twice the rate of the other (largest ratio {worst[0]:.2f}, `{worst[1]}`).
- Shortcut audit (`python3 audit.py {TASK}`), best length rule below 0.55:

```
{aud[0]}
{aud[1]}
```

Validator: `{val[1].strip() if len(val) > 1 else val}`

## Examples (one per `constraints` level; negatives)

""" + "\n\n".join(f"### constraints = {x['meta']['constraints']}, deviation `{x['meta']['deviation']}`\n\n" + fmt_item(x) for x in ex) + """

## Independence from training generators

The items are disjoint from any training generator of the authors by construction: this is a new generator, written for the benchmark;
names, templates and records share nothing with the generators used for training.
"""
    open(f"{d}/README.md", "w", encoding="utf-8").write(txt)


# ================================================================================================================ version v2
# The harder version (the default).  The pair design and the checks are those of v1; what changes: 6 / 9 / 12 constraints per request,
# ten more constraint kinds that need a small computation on the record (price per unit; discount from the list price; price plus
# shipping; a unit conversion whose factor the request states; days between two dates; a date plus a number of days; the age of the
# listing on a stated day; at least k of n certifications; a limit that only applies when another field has a given value), and near
# misses by ONE step of the compared quantity (one cent, one gram, one day, one certification) in both members of a pair.
from fractions import Fraction

KINDS_COMPUTED = ["unit_price_max", "discount_min", "total_max", "conv_max", "conv_min", "date_gap", "ready_by", "listing_age",
                  "certs_k_of_n", "conditional"]
KINDS2 = KINDS + KINDS_COMPUTED
CATEGORICAL2 = ["category", "excluded_tag", "required_tag", "region", "maker_in"]
PRICE_GROUP = {"price_max", "discount_min", "total_max"}            # these three read the same field (price): at most one per request
CONSTRAINTS2 = (6, 9, 12)
LEVEL_OF = {6: 1, 9: 2, 12: 3}                                      # meta.level (gen_v4): the dial "constraints" 6 / 9 / 12 as level 1 / 2 / 3
DAY_KINDS = ("date_gap", "listing_age", "ready_by")                  # the kinds that count days: their request states how (COUNT_NOTES / ADD_NOTES)
NUM2 = dict(NUM, noise=dict(label="noise level", field="noise_db", unit="dB", step=D(1), dec=0, lo=20, hi=90, dirs=("max",),
                            ths=[30, 35, 40, 45, 50, 55, 60, 65]))
DOMAINS2 = [
    {"name": "outdoor", "nouns": DOMAINS[0]["nouns"], "cats": DOMAINS[0]["cats"], "features": ["warranty", "stock", "width"],
     "min": ["rating", "warranty", "stock"], "max": ["width"]},
    {"name": "audio", "nouns": DOMAINS[1]["nouns"], "cats": DOMAINS[1]["cats"], "features": ["power", "battery", "noise"],
     "min": ["rating", "power", "battery"], "max": ["noise"]},
    {"name": "kitchen", "nouns": DOMAINS[2]["nouns"], "cats": DOMAINS[2]["cats"], "features": ["power", "warranty", "noise"],
     "min": ["rating", "power", "warranty"], "max": ["noise"]},
    {"name": "office", "nouns": DOMAINS[3]["nouns"], "cats": DOMAINS[3]["cats"], "features": ["width", "warranty", "stock"],
     "min": ["rating", "warranty", "stock"], "max": ["width"]},
]
CERT_POOL = ["ZEN-A", "KOR-2", "TAL-9", "DRA-1", "MEL-5", "BAR-3", "SEN-7", "VOR-4"]
PRICE_BASES = [49, 59, 74, 79, 99, 119, 149, 199, 249, 299, 399, 449, 499, 749]     # whole part of a price limit; the cents are drawn at random,
UNIT_BASES = [0, 1, 2, 3, 4, 5, 6, 8, 12]                           # so that the cents of a value one cent from a limit say nothing about the class
PACKS = [2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 24, 25, 30, 40, 50]
DISCOUNTS = [10, 12, 15, 20, 25, 30, 35, 40]
TOTAL_BASES = [60, 75, 99, 120, 150, 199, 250, 320, 450, 500, 750]
CONV = {"weight": dict(field="weight_g", big="kg", factor="1000", step="1", dirs="max", min_q="0.05"),      # min_q: the limit in the big unit is a multiple of it
        "length": dict(field="length_cm", big="inches", factor="2.54", step="0.1", dirs="max", min_q="5"),   # (5 inches = 12.7 cm: a whole number of 0.1 cm for every multiple of 5)
        "volume": dict(field="volume_ml", big="litres", factor="1000", step="1", dirs="min", min_q="0.05"),
        "runtime": dict(field="runtime_min", big="hours", factor="60", step="1", dirs="min", min_q="0.05")}      # (0.05 hours = 3 minutes)
CONV_OF = {"conv_max": ["weight", "length"], "conv_min": ["volume", "runtime"]}
INT_FIELDS = {"bundle_size", "weight_g", "volume_ml", "runtime_min", "handling_days", "delivery_days", "reviews", "stock_units",
              "warranty_months", "power_w", "battery_mah", "width_cm", "noise_db"}
LAYOUT_LEAD2 = ["I need a listing for which all of these hold: "] + LAYOUT_LEAD[1:]
# frames of the computed kinds: (text, comparator phrases it does not take).  No frame holds a semicolon or a full stop followed by a space.
AVOID_NOT, AVOID_NOT_HL = ("not ",), ("not ", "higher than", "lower than")
# gen_v4: "the price is above 25 percent below the list price" can be read as "above the price that is 25 percent below the list price" (the opposite), so the first discount
# frame takes neither "above" nor "over" (it keeps "at least", "no less than", "... or more", "more than"); the frames "cut by ..." / "lower than ... by ..." do not take "above"
AVOID_DISC1, AVOID_DISC2 = AVOID_NOT_HL + ("above", "over"), AVOID_NOT_HL + ("above",)
FRAMES2 = {
    "unit_price_max": [("the price per unit (bundle price divided by bundle size) is {cp}", ()),
                       ("dividing the bundle price by the bundle size gives a unit price that is {cp}", ()),
                       ("each unit costs {cp}, counting the bundle price divided by the bundle size", AVOID_NOT),
                       ("the unit price, worked out as bundle price divided by bundle size, is {cp}", ())],
    "discount_min": [("the price is {cp} below the list price, worked out exactly", AVOID_DISC1),
                     ("the discount from the list price to the price, worked out exactly as a share of the list price, is {cp}", ()),
                     ("the price has been cut by {cp} from the list price, worked out exactly", AVOID_DISC2),
                     ("the price is lower than the list price by {cp}, worked out exactly", AVOID_DISC2)],
    "total_max": [("the price plus the shipping fee is {cp}", ()), ("price and shipping fee together come to {cp}", AVOID_NOT),
                  ("the total of the price and the shipping fee is {cp}", ()), ("paying the price and the shipping fee costs {cp} in all", AVOID_NOT)],
    "date_gap": [("the number of days between the manufacturing date and the shipping date is {cp}", ()),
                 ("the shipping date falls {cp} after the manufacturing date", AVOID_NOT),
                 ("the gap from the manufacturing date to the shipping date is {cp}", ()),
                 ("the item waits {cp} between the manufacturing date and the shipping date", AVOID_NOT)],
    "listing_age": [("as of {ref}, the listing has been online for {cp}, counted from the listing date", AVOID_NOT),
                    ("on {ref}, the age of the listing in days, counted from the listing date, is {cp}", ()),
                    ("the number of days from the listing date to {ref} is {cp}", ()),
                    ("as of {ref}, the listing has been live for {cp}, counted from the listing date", AVOID_NOT)],
    "certs_k_of_n": [("{cp} of these certifications are held: {lst}", AVOID_NOT), ("the record lists {cp} of the certifications {lst}", AVOID_NOT),
                     ("the number of certifications held among {lst} is {cp}", ()), ("among the certifications {lst}, {cp} are held", AVOID_NOT)],
    "conditional": [("if the item ships from outside {R}, the delivery time is {cp} (items that ship from {R} have no delivery limit)", ()),
                    ("an item that ships from anywhere other than {R} must have a delivery time of {cp}, and items shipped from {R} have no limit", AVOID_NOT),
                    ("when the item does not ship from {R}, the delivery time is {cp}, and when it ships from {R}, no delivery limit applies", ()),
                    ("delivery takes {cp} for items shipped from outside {R}, and there is no limit for items shipped from {R}", AVOID_NOT)],
    "ready_by": [("the stocked date plus the handling time in days is {cp}", ()), ("adding the handling days to the stocked date gives a date that is {cp}", ()),
                 ("the ready date, which is the stocked date plus the handling days, is {cp}", ()),
                 ("the item is ready {cp}, counting the stocked date plus the handling days", ())],
}
# frames of the simple kinds that name a field in words (v2 / gen_v4): the maker is only "made by" / "its maker is", a region only "ships to" / "shipped to"
# (never "from", "origin", "comes from", "shipping regions", "delivered"), a category is "filed under" (not "listed"), so that no frame reads as another field
MAK_FRAMES2 = ["it is made by {m}", "its maker is one of {m2}", "the maker is {m}", "it was made by {m}"]
REG_FRAMES2 = ["it ships to {r}", "shipping to {r} is possible", "{r} is one of the regions it ships to", "it can be shipped to {r}"]
CAT_FRAMES2 = ["its category is {c}", "it is filed under the category {c}", "it belongs to the category {c}", "the category must be {c}"]
# the one sentence that says how days are counted (a request with date_gap or listing_age) and the one for a date plus N days (ready_by); four phrasings each
COUNT_NOTES = ["Day counts are the difference between the two dates (the same day counts as 0 days).",
               "Days between two dates are counted as the plain difference of the dates, so the same day is 0 days.",
               "A count of days is the difference between the two dates; two identical dates are 0 days apart.",
               "Counting days means subtracting one date from the other (the same day counts as 0 days)."]
ADD_NOTES = ["A date plus N days is the date N days later (adding 0 days gives the same date).",
             "Adding days to a date moves it forward by exactly that many days (adding 0 days gives the same date).",
             "Adding N days to a date gives the date N days after it; the date itself is day 0.",
             "A date plus N days means N days later on the calendar (the date itself counts as day 0)."]
CONV_FRAMES = {
    "weight": [("the weight is {cp} (the record gives weights in grams, and 1 kg = {f} g)", ()),
               ("the weight must be {cp}, the record showing weights in grams at {f} g to the kg", AVOID_NOT),
               ("it weighs {cp} (weights in the record are in grams, {f} g making 1 kg)", AVOID_NOT),
               ("its weight, converted from the grams of the record at {f} g per kg, is {cp}", ())],
    "length": [("the length is {cp} (the record gives lengths in centimetres, and 1 inch = {f} cm)", ()),
               ("the length must be {cp}, the record showing lengths in centimetres at {f} cm to the inch", AVOID_NOT),
               ("it measures {cp} in length (lengths in the record are in centimetres, {f} cm making 1 inch)", AVOID_NOT),
               ("its length, converted from the centimetres of the record at {f} cm per inch, is {cp}", ())],
    "volume": [("the volume is {cp} (the record gives volumes in millilitres, and 1 litre = {f} ml)", ()),
               ("the volume must be {cp}, the record showing volumes in millilitres at {f} ml to the litre", AVOID_NOT),
               ("it holds {cp} (volumes in the record are in millilitres, {f} ml making 1 litre)", AVOID_NOT),
               ("its volume, converted from the millilitres of the record at {f} ml per litre, is {cp}", ())],
    "runtime": [("the run time is {cp} (the record gives run times in minutes, and 1 hour = {f} minutes)", ()),
                ("the run time must be {cp}, the record showing run times in minutes at {f} minutes to the hour", AVOID_NOT),
                ("it runs for {cp} (run times in the record are in minutes, {f} minutes making 1 hour)", AVOID_NOT),
                ("its run time, converted from the minutes of the record at {f} minutes per hour, is {cp}", ())]}

# ------------------------------------------------------------------------------------------ plausible records (gen_v4)
# Lowest and highest plausible value of the price (in euros; a krona counts a tenth, see CURRENCY_SCALE) and of every physical spec of each product category.  A spec that a category does not have is absent here and from its
# records (an audio cable has no battery, an office desk no run time, a cooker has both a volume and a run time).  In every category the range of the
# width lies below the range of the length, so that no record is wider than it is long.  Every limit of a spec kind is drawn inside the range of the
# category (far enough from its inward end for 'well inside' values), the near misses sit one step from a limit, so all values stay inside the ranges;
# check_plausible asserts it for every record.
PROFILE = {
    "Outdoor lighting": dict(weight_g=(90, 2400), length_cm=(14, 45), width_cm=(6, 13), runtime_min=(150, 2400), price=(12, 140)),
    "Outdoor cooking": dict(weight_g=(450, 9000), length_cm=(36, 80), width_cm=(15, 35), volume_ml=(600, 6000), runtime_min=(40, 480), price=(25, 320)),
    "Outdoor furniture": dict(weight_g=(1500, 14000), length_cm=(70, 190), width_cm=(30, 60), price=(30, 420)),
    "Outdoor storage": dict(weight_g=(600, 12000), length_cm=(40, 100), width_cm=(20, 38), volume_ml=(5000, 80000), price=(18, 380)),
    "Outdoor tools": dict(weight_g=(180, 4500), length_cm=(45, 130), width_cm=(6, 40), price=(10, 260)),
    "Audio players": dict(weight_g=(90, 520), length_cm=(8, 22), power_w=(2, 40), battery_mah=(1000, 6000), noise_db=(15, 42), runtime_min=(300, 2400), price=(35, 520)),
    "Audio accessories": dict(weight_g=(25, 420), length_cm=(5, 24), power_w=(1, 12), battery_mah=(200, 3000), noise_db=(12, 40), runtime_min=(180, 2400), price=(8, 260)),
    "Audio recording": dict(weight_g=(40, 650), length_cm=(6, 35), power_w=(1, 15), battery_mah=(500, 4500), noise_db=(10, 36), runtime_min=(240, 1800), price=(30, 650)),
    "Audio amplifiers": dict(weight_g=(1500, 12000), length_cm=(18, 50), power_w=(25, 500), noise_db=(15, 45), price=(60, 900)),
    "Audio cables": dict(weight_g=(30, 700), length_cm=(30, 600), price=(4, 90)),
    "Kitchen cooking": dict(weight_g=(1500, 9000), length_cm=(22, 55), power_w=(300, 2200), noise_db=(25, 55), volume_ml=(1000, 8000), runtime_min=(30, 720), price=(30, 420)),
    "Kitchen cleaning": dict(weight_g=(900, 8000), length_cm=(24, 60), power_w=(400, 2200), noise_db=(35, 75), volume_ml=(300, 3000), runtime_min=(10, 120), price=(40, 560)),
    "Kitchen storage": dict(weight_g=(80, 2500), length_cm=(8, 40), volume_ml=(300, 6000), price=(5, 90)),
    "Kitchen tools": dict(weight_g=(40, 1200), length_cm=(12, 45), price=(5, 120)),
    "Kitchen small appliances": dict(weight_g=(500, 6000), length_cm=(15, 45), power_w=(250, 2200), noise_db=(40, 88), volume_ml=(400, 3000), price=(20, 320)),
    "Office seating": dict(weight_g=(3500, 25000), length_cm=(56, 130), width_cm=(32, 56), price=(45, 650)),
    "Office desks": dict(weight_g=(8000, 60000), length_cm=(100, 200), width_cm=(50, 95), price=(90, 900)),
    "Office storage": dict(weight_g=(2000, 60000), length_cm=(40, 200), width_cm=(25, 39), volume_ml=(20000, 400000), price=(30, 520)),
    "Office lighting": dict(weight_g=(300, 5000), length_cm=(20, 80), width_cm=(8, 19), runtime_min=(120, 1800), price=(15, 220)),
    "Office accessories": dict(weight_g=(300, 6000), length_cm=(50, 100), width_cm=(22, 49), price=(6, 140)),
}
SPEC_FIELDS = ["weight_g", "length_cm", "volume_ml", "runtime_min", "power_w", "battery_mah", "noise_db", "width_cm"]
SPEC_STEP = {"weight_g": D(1), "length_cm": D("0.1"), "volume_ml": D(1), "runtime_min": D(1), "power_w": D(1), "battery_mah": D(10), "noise_db": D(1),
             "width_cm": D(1), "price": D("0.01")}
LOG_SPECS = {"weight_g", "volume_ml", "runtime_min", "power_w", "battery_mah", "price"}          # drawn on a log scale over their range
DOM_SPECS = {"outdoor": {"price", "weight_g", "length_cm", "width_cm", "volume_ml", "runtime_min"},
             "audio": {"price", "weight_g", "length_cm", "power_w", "battery_mah", "noise_db", "runtime_min"},
             "kitchen": {"price", "weight_g", "length_cm", "power_w", "noise_db", "volume_ml", "runtime_min"},
             "office": {"price", "weight_g", "length_cm", "width_cm", "volume_ml", "runtime_min"}}
CURRENCY_SCALE = {"EUR": 1, "USD": 1, "GBP": 1, "CHF": 1, "SEK": 10}       # price ranges, shipping fees and bundle caps are in euros; a krona is worth about a tenth


def check_profile():
    for dom in DOMAINS2:
        for cat in dom["cats"]:
            p = PROFILE[cat]
            assert {"price", "weight_g", "length_cm"} <= set(p) <= DOM_SPECS[dom["name"]], (cat, sorted(p))
            assert all(p[f][0] < p[f][1] for f in p)
            if "width_cm" in p:
                assert p["width_cm"][1] <= p["length_cm"][0], cat    # never wider than long
    assert set(PROFILE) == {c for dom in DOMAINS2 for c in dom["cats"]}


check_profile()
QUANTA = [D(x) for x in ("1000", "500", "250", "100", "50", "25", "10", "5", "2.5", "1", "0.5", "0.25", "0.1", "0.05")]


def round_between(rng, lo, hi, min_q):
    """a round number between lo and hi: a multiple of the coarsest quantum (1000 ... 0.05; never finer than min_q, always a multiple of it) that leaves at
    least three candidates, else of the quantum that leaves most"""
    lo, hi = D(lo), D(hi)
    best = []
    for q in QUANTA:
        if q < min_q or q % min_q != 0:
            continue
        first, last = int((lo / q).to_integral_value(rounding="ROUND_CEILING")), int((hi / q).to_integral_value(rounding="ROUND_FLOOR"))
        cand = [m * q for m in range(first, last + 1)]
        if len(cand) >= 3:
            return rng.choice(cand)
        if len(cand) > len(best):
            best = cand
    if not best:
        raise RuntimeError("no round limit between %s and %s" % (lo, hi))
    return rng.choice(best)


def limit_window(lo, hi, direction, step):
    """where the limit of a max / min constraint on a spec may lie: at least 30 % of the range away from the inward end (room for values well inside the
    limit) and two steps from the other end (room for the near miss one step beyond it)"""
    lo, hi = D(lo), D(hi)
    if direction == "max":
        return lo + D("0.3") * (hi - lo), hi - 2 * step
    return lo + 2 * step, hi - D("0.3") * (hi - lo)


def draw_spec(rng, field, lo, hi):
    """a value of a spec inside its range, on the grid of the field"""
    v = math.exp(rng.uniform(math.log(lo), math.log(hi))) if field in LOG_SPECS else rng.uniform(lo, hi)
    return min(max(snap_to(D(str(round(v, 3))), SPEC_STEP[field]), D(lo)), D(hi))


def twin_ranges(a, b):
    """the ranges where two sibling categories are both plausible (None: they have different specs, or the ranges overlap too little)"""
    pa, pb = PROFILE[a], PROFILE[b]
    if set(pa) != set(pb):
        return None
    out = {}
    for f in pa:
        lo, hi = max(pa[f][0], pb[f][0]), min(pa[f][1], pb[f][1])
        if hi - lo < 5 * float(SPEC_STEP[f]):
            return None
        out[f] = (lo, hi)
    return out


def usable_on(dom, cat, kind):
    """can a constraint of this kind be built on a record of the category (a run time or a volume needs one in the profile; a noise or a width limit needs the spec)"""
    p = PROFILE[cat]
    if kind == "conv_min":
        return "volume_ml" in p or "runtime_min" in p
    if kind == "feature_max":
        return any(NUM2[f]["field"] in p for f in dom["max"])
    return True


def feature_ok(f, R):
    """does a record with the spec ranges R carry the feature f (rating, warranty and stock every record, the others when the category has the spec)"""
    return NUM2[f]["field"] in R or f in ("rating", "warranty", "stock")


def money(x):
    x = D(x)
    return str(int(x)) if x == x.to_integral_value() else f"{x:.2f}"


def iso(n):
    return datetime.date.fromordinal(int(n)).isoformat()


def ordinal(text):
    return datetime.date.fromisoformat(text).toordinal()


def op_of(direction, inclusive):
    return {("max", True): "<=", ("max", False): "<", ("min", True): ">=", ("min", False): ">"}[(direction, inclusive)]


def numc(kind, direction, inclusive, limit, step, bounds, **extra):
    """a constraint on a compared quantity x (price, unit price, grams, days, ...): satisfied when x <op> limit; one step = the
    smallest step of x; bounds = the values of x a record may take"""
    return {"kind": kind, "direction": direction, "inclusive": inclusive, "op": op_of(direction, inclusive), "limit": limit, "step": step,
            "bounds": bounds, **extra}


# ------------------------------------------------------------------------------------------------------ constraints (v2)
def setup_v2(rng, kind, ctx, pattern):
    """a constraint of the given kind; the pattern 'edge_pos' needs an inclusive limit, 'edge_neg' an exclusive one"""
    inc = {"edge_pos": True, "edge_neg": False}.get(pattern, rng.random() < 0.5)
    if kind == "price_max":                                         # the limit lies inside the price range of the category (round whole part, random cents)
        lo, hi = ctx["R"]["price"]
        a, b = limit_window(lo, hi, "max", D("0.01"))
        return numc(kind, "max", inc, round_between(rng, a, b - 1, D(1)) + D(rng.randint(0, 99)) / 100, D("0.01"), (D(lo), D(hi)), field="price", unit=ctx["currency"], roomy=True)
    if kind in ("feature_min", "feature_max"):
        f = ctx["min_f"] if kind == "feature_min" else ctx["max_f"]
        s = NUM2[f]
        direction = "min" if kind == "feature_min" else "max"
        if s["field"] in ctx["R"]:                                  # a spec of the category (power, battery, noise, width): the limit lies inside its plausible range
            lo, hi = ctx["R"][s["field"]]
            a, b = limit_window(lo, hi, direction, s["step"])
            return numc(kind, direction, inc, round_between(rng, a, b, s["step"]), s["step"], (D(lo), D(hi)), field=s["field"], feature=f, unit=s["unit"], roomy=True)
        return numc(kind, direction, inc, D(rng.choice(s["ths"])), s["step"], (D(s["lo"]), D(s["hi"])), field=s["field"], feature=f, unit=s["unit"])
    if kind in ("date_max", "date_min"):
        s = DATES[kind]
        return numc(kind, s["dirs"], inc, rng.randint(ordinal(s["lim_lo"]), ordinal(s["lim_hi"])), 1, (ordinal(s["lo"]), ordinal(s["hi"])), field=s["field"])
    if kind == "unit_price_max":                                    # built by setup_unit_price once the price of the record is known
        raise ValueError("unit_price_max is set up after the price")
    if kind == "discount_min":                                      # x = the price; the limit is the price that is exactly `percent` below the list price
        d = rng.choice(DISCOUNTS)                                   # (never a whole number of cents: no price is ON the limit, one cent separates yes and no)
        lo, hi = ctx["R"]["price"]                                  # the price (x) lies inside the price range of the category, the list price follows from it
        a, b = limit_window(lo, hi, "max", D("0.01"))
        keep = D(100 - d) / 100
        while True:
            lst = D(rng.randint(int(a / keep * 100), int(b / keep * 100))) / 100
            exact = lst * (100 - d) / 100
            if exact != exact.quantize(D("0.01")):
                break
        anchor = (exact * 100).to_integral_value(rounding="ROUND_FLOOR") / 100       # the highest price that is still discounted enough
        return numc(kind, "max", True, anchor, D("0.01"), (D(lo), lst * D("0.95")), field="price", list=lst, percent=d, exact=exact,
                    text_op=rng.choice([">=", ">"]), roomy=True)
    if kind == "total_max":                                         # x = price + shipping fee; the price is fixed, the shipping fee carries the step
        lo, hi = ctx["R"]["price"]
        a, b = limit_window(lo, hi, "max", D("0.01"))
        lim = round_between(rng, a, b - 1, D(1)) + D(rng.randint(0, 99)) / 100
        fee = min(lim * D(str(round(rng.uniform(0.03, 0.10), 3))), D(30 * CURRENCY_SCALE[ctx["currency"]])).quantize(D("0.01"))   # the shipping fee at the limit: 3 to 10 % of the total, at most 30 euros
        p0 = lim - fee
        if p0 < D(lo):
            raise RuntimeError("price below the range of the category")
        return numc(kind, "max", inc, lim, D("0.01"), (p0, lim), price=p0, unit=ctx["currency"], roomy=True)
    if kind in ("conv_max", "conv_min"):                            # x = the field in the small unit; the limit is stated in the big unit, inside the range of the category
        variants = [v for v in CONV_OF[kind] if CONV[v]["field"] in ctx["R"]]
        rng.shuffle(variants)
        for v in variants:
            s = CONV[v]
            lo, hi = ctx["R"][s["field"]]
            a, b = limit_window(lo, hi, s["dirs"], D(s["step"]))
            f = D(s["factor"])
            try:
                big = round_between(rng, a / f, b / f, D(s["min_q"]))
            except RuntimeError:
                continue
            return numc(kind, s["dirs"], inc, big * f, D(s["step"]), (D(lo), D(hi)), variant=v, field=s["field"], big=big, roomy=True)
        raise RuntimeError("no plausible limit for " + kind)
    if kind == "date_gap":                                          # x = days from the manufacturing date to the shipping date
        return numc(kind, rng.choice(["max", "min"]), inc, rng.randint(5, 60), 1, (0, 120), m_on=iso(ordinal("2025-09-01") + rng.randrange(180)))
    if kind == "ready_by":                                          # x = the stocked date + the handling days (as a day number); handling days carry the step
        h0 = rng.randint(6, 25)
        lim = ordinal(DATES["date_max"]["lim_lo"]) + rng.randrange(120)
        return numc(kind, "max", inc, lim, 1, (lim - h0, lim + 30), stocked_on=iso(lim - h0), h0=h0)
    if kind == "listing_age":                                       # x = days from the listing date to the reference day of the request
        return numc(kind, rng.choice(["max", "min"]), inc, rng.randint(14, 180), 1, (0, 400), ref=iso(ordinal("2026-06-01") + rng.randrange(120)))
    if kind == "certs_k_of_n":                                      # x = how many of the listed certifications the record holds
        n = rng.choice([3, 4])
        return numc(kind, "min", inc, 2 if n == 3 else rng.choice([2, 3]), 1, (0, n), listed=rng.sample(CERT_POOL, n))
    if kind == "conditional":                                       # x = the delivery days, only for items that do not ship from `origin`
        return numc(kind, "max", inc, rng.randint(2, 14), 1, (1, 30), origin=rng.choice(ctx["regions"]))
    if kind == "category":
        return {"kind": kind, "value": ctx["cat"]}
    if kind == "excluded_tag":
        v = rng.choice([t for t in EXCLUDABLE if t not in ctx["excluded"]])
        ctx["excluded"].append(v)
        return {"kind": kind, "value": v}
    if kind == "required_tag":
        v = rng.choice([t for t in REQUIRABLE if t not in ctx["required"]])
        ctx["required"].append(v)
        return {"kind": kind, "value": v}
    if kind == "region":
        return {"kind": kind, "value": rng.choice(ctx["regions"])}
    return {"kind": kind, "values": rng.sample(ctx["makers"], rng.choice([2, 3]))}          # maker_in


def setup_unit_price(rng, ctx, pattern, price):
    """unit_price_max, set up once the price of the record is known: a bundle costs bundle size x a unit price of 0.70 to 0.95 times the price, and the limit
    (the unit price on or one cent from it) lies at 0.78 to 0.92 times the price"""
    inc = {"edge_pos": True, "edge_neg": False}.get(pattern, rng.random() < 0.5)
    lim = (price * D(str(round(rng.uniform(0.78, 0.92), 3)))).quantize(D("0.01"))
    lo = (price * D("0.70")).quantize(D("0.01"), rounding="ROUND_UP")
    hi = (price * D("0.95")).quantize(D("0.01"), rounding="ROUND_DOWN")
    packs = [p for p in PACKS if p * price <= 6000 * CURRENCY_SCALE[ctx["currency"]]]      # no 40 cookers in a bundle
    return numc("unit_price_max", "max", inc, lim, D("0.01"), (lo, hi), pack=rng.choice(packs), unit=ctx["currency"], roomy=True)


def fields_of(c, x):
    """the record fields that realise the compared quantity x of constraint c"""
    k = c["kind"]
    if k in ("price_max", "feature_min", "feature_max", "discount_min", "conv_max", "conv_min"):
        return {c["field"]: x} if k != "discount_min" else {"list_price": c["list"], "price": x}
    if k in ("date_max", "date_min"):
        return {c["field"]: iso(x)}
    if k == "unit_price_max":
        return {"bundle_size": c["pack"], "bundle_price": x * c["pack"]}
    if k == "total_max":
        return {"price": c["price"], "shipping_fee": x - c["price"]}
    if k == "date_gap":
        return {"manufactured_on": c["m_on"], "shipped_on": iso(ordinal(c["m_on"]) + int(x))}
    if k == "ready_by":
        return {"stocked_on": c["stocked_on"], "handling_days": int(x) - ordinal(c["stocked_on"])}
    if k == "listing_age":
        return {"listed_on": iso(ordinal(c["ref"]) - int(x))}
    raise ValueError(k)


def snap_to(x, step):
    return (D(x) / step).to_integral_value() * step if isinstance(step, Decimal) else int(x)


def planted_x(c, pattern):
    """(quantity of the positive, of the negative): on the limit and one step beyond it, one step inside and on it, or one step either side"""
    lim, step = c["limit"], c["step"]
    inward = -1 if c["direction"] == "max" else 1
    if pattern == "adjacent":                                       # discount: the highest price that is discounted enough, and the next cent
        return lim, lim + step
    if pattern == "edge_pos":
        return lim, lim - inward * step
    if pattern == "edge_neg":
        return lim + inward * step, lim
    return lim + inward * step, lim - inward * step                 # mirror


def free_x(rng, c, near):
    """a quantity that satisfies the (non-planted) constraint: on the limit or one step inside it (near), or well inside (wide)"""
    lim, step, (lo, hi) = c["limit"], c["step"], c["bounds"]
    inward = -1 if c["direction"] == "max" else 1
    if near:
        k = rng.choice([0, 1, 1, 2])
        if k == 0 and not c["inclusive"]:
            k = 1
        return min(max(lim + inward * k * step, lo), hi)
    if c.get("roomy"):                                              # a spec, the unit price, the total: well inside, in the room that the plausible range leaves
        room = lim - lo if inward < 0 else hi - lim
        x = snap_to(lim + inward * max(3 * step, room * D(str(round(rng.uniform(0.15, 0.85), 2)))), step)
        return min(max(x, lo), hi)
    k = c["kind"]
    if k in ("date_max", "date_min"):
        margin = rng.randint(20, 120)
    elif k == "ready_by":
        margin = rng.randint(1, c["h0"])
    elif k in ("date_gap", "listing_age"):
        margin = rng.randint(3, 40) if inward > 0 or lim > 40 else rng.randint(1, max(1, lim - 1))
    elif k == "conditional":
        margin = rng.randint(1, max(1, lim - 1))
    elif k == "certs_k_of_n":
        margin = hi - lim if inward > 0 else lim
    else:
        margin = max(3 * step, lim * D(str(round(rng.uniform(0.1, 0.45), 2))))
    x = lim + inward * margin
    x = snap_to(x, step)
    return min(max(x, lo), hi)


def xval(c, rec):
    """the compared quantity of constraint c in a record, as an exact fraction"""
    k = c["kind"]
    if k in ("price_max", "feature_min", "feature_max", "discount_min", "conv_max", "conv_min"):
        return Fraction(D(rec[c["field"]]))
    if k == "total_max":
        return Fraction(D(rec["price"])) + Fraction(D(rec["shipping_fee"]))
    if k in ("date_max", "date_min"):
        return Fraction(ordinal(rec[c["field"]]))
    if k == "unit_price_max":
        return Fraction(D(rec["bundle_price"])) / rec["bundle_size"]
    if k == "date_gap":
        return Fraction(ordinal(rec["shipped_on"]) - ordinal(rec["manufactured_on"]))
    if k == "ready_by":
        return Fraction(ordinal(rec["stocked_on"]) + rec["handling_days"])
    if k == "listing_age":
        return Fraction(ordinal(c["ref"]) - ordinal(rec["listed_on"]))
    if k == "certs_k_of_n":
        return Fraction(len(set(rec["certifications"]) & set(c["listed"])))
    return Fraction(rec["delivery_days"])                           # conditional


def holds2(c, rec):
    """does the record satisfy constraint c (structured form)"""
    k = c["kind"]
    if k in CATEGORICAL2:
        return holds(c, rec)
    if k == "conditional" and rec["ships_from"] == c["origin"]:
        return True
    x, lim = xval(c, rec), Fraction(c.get("exact", c["limit"]))
    return {"<=": x <= lim, "<": x < lim, ">=": x >= lim, ">": x > lim}[c["op"]]


def truth_v2(spec):
    return all(holds2(c, spec["record"]) for c in spec["constraints"])


def jnum(field, v):
    return int(v) if field in INT_FIELDS else float(v)


def jsonable(o):
    if isinstance(o, (Decimal, Fraction)):
        return str(D(o)) if isinstance(o, Decimal) else str(float(o))
    if isinstance(o, dict):
        return {k: jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    return o


# ------------------------------------------------------------------------------------------------- rendering (v2)
def value_text(c, rng_unused=None):
    k = c["kind"]
    if k in ("price_max", "unit_price_max", "total_max"):
        return f"{money(c['limit'])} {c['unit']}"
    if k in ("feature_min", "feature_max"):
        return num_text(c["limit"]) + (f" {c['unit']}" if c["unit"] else "")
    if k == "discount_min":
        return f"{c['percent']} percent"
    if k in ("conv_max", "conv_min"):
        unit = CONV[c["variant"]]["big"]
        if c["big"] == 1:                                           # "1 litre", "1 hour"
            unit = {"litres": "litre", "hours": "hour", "inches": "inch"}.get(unit, unit)
        return f"{num_text(c['big'])} {unit}"
    if k in ("date_gap", "listing_age", "conditional"):
        return f"{c['limit']} days"
    if k == "certs_k_of_n":
        return str(c["limit"])
    return iso(c["limit"])                                          # date_max / date_min / ready_by


def text_op(c):
    """the operator as the sentence states it (a discount is stated as a percentage that must be reached, not as a price)"""
    return c["text_op"] if c["kind"] == "discount_min" else c["op"]


def clause_v2(c, rng, ctx):
    k = c["kind"]
    if k in ("price_max", "feature_min", "feature_max"):
        cp = CMP[c["op"]][rng.randrange(4)].format(v=value_text(c))
        lab = "price" if k == "price_max" else NUM2[c["feature"]]["label"]
        return NUM_FRAMES[pick_frame(rng, cp, NUM_FRAMES)].format(lab=lab, cp=cp)
    if k in ("date_max", "date_min"):
        cp = DCMP[c["op"]][rng.randrange(4)].format(v=value_text(c))
        return DATE_FRAMES[pick_frame(rng, cp, DATE_FRAMES)].format(lab=DATES[k]["label"], cp=cp)
    if k == "category":
        return CAT_FRAMES2[rng.randrange(4)].format(c=c["value"])
    if k == "excluded_tag":
        return EXC_FRAMES[rng.randrange(4)].format(t=c["value"])
    if k == "required_tag":
        return REQ_FRAMES[rng.randrange(4)].format(t=c["value"])
    if k == "region":
        return REG_FRAMES2[rng.randrange(4)].format(r=c["value"])
    if k == "maker_in":
        vs = c["values"]
        return MAK_FRAMES2[rng.randrange(4)].format(m=", ".join(vs[:-1]) + " or " + vs[-1], m2=", ".join(vs))
    frames = CONV_FRAMES[c["variant"]] if k in ("conv_max", "conv_min") else FRAMES2[k]
    frame, avoid = rng.choice(frames)
    op = text_op(c)
    if k == "ready_by":
        cp = rng.choice(DCMP[op]).format(v=value_text(c))
    else:
        cp = rng.choice([p for p in CMP[op] if not any(p.startswith(a) for a in avoid)]).format(v=value_text(c))
    lst = ", ".join(c["listed"][:-1]) + " and " + c["listed"][-1] if k == "certs_k_of_n" else ""
    return frame.format(cp=cp, f=CONV[c["variant"]]["factor"] if "variant" in c else "", ref=c.get("ref", ""), R=c.get("origin", ""), lst=lst)


# words that would name a field other than the one a clause constrains (asserted on every rendered clause of these kinds)
FOREIGN = {"maker_in": re.compile(r"\b(?:from|origin|comes?|ships?|shipp\w*|deliver\w*|brand|seller|sold|manufactur\w*)\b", re.I),
           "region": re.compile(r"\b(?:from|origin|comes?|maker|made|seller|deliver\w*|shipping regions?)\b", re.I),
           "category": re.compile(r"\b(?:listed|listing|from|origin|maker|made|ships?|shipp\w*|deliver\w*)\b", re.I),
           "conditional": re.compile(r"\b(?:origin|maker|made|seller|ships? to|shipped to|shipping to|regions?)\b", re.I),
           "listing_age": re.compile(r"\b(?:available|availability|release\w*|stocked|handling|manufactur\w*|ship\w*)\b", re.I),
           "date_gap": re.compile(r"\b(?:listing|listed|release\w*|available|availability|stocked|handling|online|live)\b", re.I),
           "ready_by": re.compile(r"\b(?:manufactur\w*|shipping|shipped|listing|listed|release\w*|available|availability|online|live)\b", re.I)}


def day_notes(rng, kinds):
    """the sentences that state how days are counted, for the day-count kinds present in a request (none otherwise)"""
    notes = []
    if "date_gap" in kinds or "listing_age" in kinds:
        notes.append(rng.choice(COUNT_NOTES))
    if "ready_by" in kinds:
        notes.append(rng.choice(ADD_NOTES))
    return notes


def render_request2(clauses, layout, notes=()):
    cap = lambda s: s[0].upper() + s[1:]
    if layout == 0:
        return " ".join([LAYOUT_LEAD2[0] + "; ".join(clauses[:-1]) + "; and " + clauses[-1] + "."] + list(notes))
    if layout == 1:
        return "\n".join([LAYOUT_LEAD2[1]] + [f"- {cap(x)}" for x in clauses] + list(notes))
    if layout == 2:
        return "\n".join([LAYOUT_LEAD2[2]] + [f"{n}) {cap(x)}" for n, x in enumerate(clauses, 1)] + list(notes))
    return " ".join([LAYOUT_LEAD2[3] + " ".join(f"{cap(x)}." for x in clauses)] + list(notes))


# --------------------------------------------------------------------- check (v2): the answer from the rendered text alone
NUMLAB2 = "|".join(re.escape(v["label"]) for v in sorted(NUM2.values(), key=lambda v: -len(v["label"])) if v["field"] not in ("weight_kg", "capacity_l"))
FIELD_OF2 = {v["label"]: v["field"] for v in NUM2.values()}
FIELD_OF2.update({DATES[k]["label"]: DATES[k]["field"] for k in DATES})
NUMV2 = rf"(?P<v>\d+(?:\.\d+)?)(?: (?:{UNITS_RE}|dB))?"


def cmp_rx(v):
    """the sixteen comparator phrases for a value pattern v (what each wording means is written out here, not taken from the renderer)"""
    return [("<=", rf"at most {v}"), ("<=", rf"no more than {v}"), ("<=", rf"{v} or less"), ("<=", rf"not above {v}"),
            ("<", rf"less than {v}"), ("<", rf"under {v}"), ("<", rf"below {v}"), ("<", rf"lower than {v}"),
            (">=", rf"at least {v}"), (">=", rf"no less than {v}"), (">=", rf"{v} or more"), (">=", rf"not below {v}"),
            (">", rf"more than {v}"), (">", rf"over {v}"), (">", rf"above {v}"), (">", rf"higher than {v}")]


NUM_PATTERNS2 = [(op, pre + rf"(?P<lab>{NUMLAB2})" + mid + cp) for pre, mid in
                 [("the ", " is "), ("the ", " must be "), ("its ", " is "), ("it has a ", " that is ")] for op, cp in cmp_rx(NUMV2)]
V_MONEY = r"(?P<v>\d+(?:\.\d+)?) (?:EUR|USD|GBP|CHF|SEK)"
V_PCT = r"(?P<v>\d+) percent"
V_DAYS = r"(?P<v>\d+) days"
V_INT = r"(?P<v>\d+)"
CERT_RX = r"[A-Z]{3}-[A-Z0-9]"
SLOTS = {"{ref}": r"(?P<ref>\d{4}-\d\d-\d\d)", "{lst}": rf"(?P<lst>{CERT_RX}(?:, {CERT_RX})*(?: and {CERT_RX}))", "{R}": REGV, "{R=}": r"(?P=r)",
         "{f}": r"(?P<f>\d+(?:\.\d+)?)"}
FRAME_RX = {   # kind -> (value pattern, frames written as patterns)
    "unit_price_max": (V_MONEY, [r"the price per unit \(bundle price divided by bundle size\) is {cp}",
                                 r"dividing the bundle price by the bundle size gives a unit price that is {cp}",
                                 r"each unit costs {cp}, counting the bundle price divided by the bundle size",
                                 r"the unit price, worked out as bundle price divided by bundle size, is {cp}"]),
    "discount_min": (V_PCT, [r"the price is {cp} below the list price, worked out exactly",
                             r"the discount from the list price to the price, worked out exactly as a share of the list price, is {cp}",
                             r"the price has been cut by {cp} from the list price, worked out exactly",
                             r"the price is lower than the list price by {cp}, worked out exactly"]),
    "total_max": (V_MONEY, [r"the price plus the shipping fee is {cp}", r"price and shipping fee together come to {cp}",
                            r"the total of the price and the shipping fee is {cp}", r"paying the price and the shipping fee costs {cp} in all"]),
    "date_gap": (V_DAYS, [r"the number of days between the manufacturing date and the shipping date is {cp}",
                          r"the shipping date falls {cp} after the manufacturing date", r"the gap from the manufacturing date to the shipping date is {cp}",
                          r"the item waits {cp} between the manufacturing date and the shipping date"]),
    "listing_age": (V_DAYS, [r"as of {ref}, the listing has been online for {cp}, counted from the listing date",
                             r"on {ref}, the age of the listing in days, counted from the listing date, is {cp}",
                             r"the number of days from the listing date to {ref} is {cp}",
                             r"as of {ref}, the listing has been live for {cp}, counted from the listing date"]),
    "certs_k_of_n": (V_INT, [r"{cp} of these certifications are held: {lst}", r"the record lists {cp} of the certifications {lst}",
                             r"the number of certifications held among {lst} is {cp}", r"among the certifications {lst}, {cp} are held"]),
    "conditional": (V_DAYS, [r"if the item ships from outside {R}, the delivery time is {cp} \(items that ship from {R=} have no delivery limit\)",
                             r"an item that ships from anywhere other than {R} must have a delivery time of {cp}, and items shipped from {R=} have no limit",
                             r"when the item does not ship from {R}, the delivery time is {cp}, and when it ships from {R=}, no delivery limit applies",
                             r"delivery takes {cp} for items shipped from outside {R}, and there is no limit for items shipped from {R=}"]),
}
CONV_RX = {   # variant -> (value pattern, frames)
    "weight": (r"(?P<v>\d+(?:\.\d+)?) kg", [r"the weight is {cp} \(the record gives weights in grams, and 1 kg = {f} g\)",
                                            r"the weight must be {cp}, the record showing weights in grams at {f} g to the kg",
                                            r"it weighs {cp} \(weights in the record are in grams, {f} g making 1 kg\)",
                                            r"its weight, converted from the grams of the record at {f} g per kg, is {cp}"]),
    "length": (r"(?P<v>\d+) inch(?:es)?", [r"the length is {cp} \(the record gives lengths in centimetres, and 1 inch = {f} cm\)",
                                      r"the length must be {cp}, the record showing lengths in centimetres at {f} cm to the inch",
                                      r"it measures {cp} in length \(lengths in the record are in centimetres, {f} cm making 1 inch\)",
                                      r"its length, converted from the centimetres of the record at {f} cm per inch, is {cp}"]),
    "volume": (r"(?P<v>\d+(?:\.\d+)?) litres?", [r"the volume is {cp} \(the record gives volumes in millilitres, and 1 litre = {f} ml\)",
                                                r"the volume must be {cp}, the record showing volumes in millilitres at {f} ml to the litre",
                                                r"it holds {cp} \(volumes in the record are in millilitres, {f} ml making 1 litre\)",
                                                r"its volume, converted from the millilitres of the record at {f} ml per litre, is {cp}"]),
    "runtime": (r"(?P<v>\d+(?:\.\d+)?) hours?", [r"the run time is {cp} \(the record gives run times in minutes, and 1 hour = {f} minutes\)",
                                                r"the run time must be {cp}, the record showing run times in minutes at {f} minutes to the hour",
                                                r"it runs for {cp} \(run times in the record are in minutes, {f} minutes making 1 hour\)",
                                                r"its run time, converted from the minutes of the record at {f} minutes per hour, is {cp}"])}
READY_RX = [r"the stocked date plus the handling time in days is {cp}", r"adding the handling days to the stocked date gives a date that is {cp}",
            r"the ready date, which is the stocked date plus the handling days, is {cp}", r"the item is ready {cp}, counting the stocked date plus the handling days"]


def _fill(frame, cp):
    s = frame.replace("{cp}", cp)
    for k, v in SLOTS.items():
        s = s.replace(k, v)
    return re.compile(s)


COMPUTED_RX = []                                                    # (kind, variant, operator, compiled pattern)
for _k, (_v, _frames) in FRAME_RX.items():
    COMPUTED_RX += [(_k, None, op, _fill(fr, cp)) for fr in _frames for op, cp in cmp_rx(_v)]
for _var, (_v, _frames) in CONV_RX.items():
    COMPUTED_RX += [("conv", _var, op, _fill(fr, cp)) for fr in _frames for op, cp in cmp_rx(_v)]
COMPUTED_RX += [("ready_by", None, op, _fill(fr, cp)) for fr in READY_RX for op, cp in DATE_CP]
OTHER_PATTERNS2 = ([(k, p) for k, p in OTHER_PATTERNS if k not in ("category", "region", "maker_in")]
                   + [("category", rf"its category is {CATV}"), ("category", rf"it is filed under the category {CATV}"),
                      ("category", rf"it belongs to the category {CATV}"), ("category", rf"the category must be {CATV}"),
                      ("region", rf"it ships to {REGV}"), ("region", rf"shipping to {REGV} is possible"),
                      ("region", rf"{REGV} is one of the regions it ships to"), ("region", rf"it can be shipped to {REGV}"),
                      ("maker_in", rf"it is made by {MAKV}"), ("maker_in", rf"its maker is one of {MAKV2}"),
                      ("maker_in", rf"the maker is {MAKV}"), ("maker_in", rf"it was made by {MAKV}")])
SIMPLE_RX = ([("num", None, op, re.compile(p)) for op, p in NUM_PATTERNS2] + [("date", None, op, re.compile(p)) for op, p in DATE_PATTERNS]
             + [(k, None, None, re.compile(p)) for k, p in OTHER_PATTERNS2])
# the notes that say how days are counted, written out again (the renderer's tables are not used): each says that a count of days is the plain difference of two dates
# (the same day is 0 days) or that a date plus N days is the date N days later; the check takes the offset (0) from the note it finds and refuses a request without one
NOTE_RX = [("count", re.compile(p)) for p in (
    r"Day counts are the difference between the two dates \(the same day counts as 0 days\)\.",
    r"Days between two dates are counted as the plain difference of the dates, so the same day is 0 days\.",
    r"A count of days is the difference between the two dates; two identical dates are 0 days apart\.",
    r"Counting days means subtracting one date from the other \(the same day counts as 0 days\)\.")] + [("add", re.compile(p)) for p in (
    r"A date plus N days is the date N days later \(adding 0 days gives the same date\)\.",
    r"Adding days to a date moves it forward by exactly that many days \(adding 0 days gives the same date\)\.",
    r"Adding N days to a date gives the date N days after it; the date itself is day 0\.",
    r"A date plus N days means N days later on the calendar \(the date itself counts as day 0\)\.")]


def split_notes(req):
    """-> (the request without its closing notes, {'count': offset, 'add': offset}); the offset of a count of days / of a date plus N days is 0 in every note"""
    found = {}
    while True:
        for what, rx in NOTE_RX:
            m = re.search(r"(?:\n| )" + rx.pattern + r"\Z", req)
            if m:
                found[what] = 0
                req = req[:m.start()]
                break
        else:
            return req, found


def split_clauses_v2(req):
    lines = req.split("\n")
    if req.startswith(LAYOUT_LEAD2[0]):
        parts = req[len(LAYOUT_LEAD2[0]):]
        assert parts.endswith(".")
        parts = parts[:-1].split("; ")
        parts[-1] = re.sub(r"^and ", "", parts[-1])
    elif lines[0] == LAYOUT_LEAD2[1]:
        parts = [re.sub(r"^- ", "", ln) for ln in lines[1:]]
    elif lines[0] == LAYOUT_LEAD2[2]:
        parts = [re.sub(r"^\d+\) ", "", ln) for ln in lines[1:]]
    else:
        assert req.startswith(LAYOUT_LEAD2[3]) and req.endswith(".")
        parts = req[len(LAYOUT_LEAD2[3]):-1].split(". ")
    return [p if re.match(r"[A-Z][a-z]+-(?:North|South|East|West) ", p) else p[0].lower() + p[1:] for p in parts]


def parse_clause_v2(cl):
    hits = []
    for kind, variant, op, rx in COMPUTED_RX + SIMPLE_RX:
        m = rx.fullmatch(cl)
        if not m:
            continue
        g = m.groupdict()
        if kind in ("num", "date"):
            hits.append({"kind": kind, "op": op, "field": FIELD_OF2[g["lab"]], "limit": g["v"]})
        elif kind == "maker_in":
            hits.append({"kind": kind, "values": re.split(r", | or ", g["m"])})
        elif kind in CATEGORICAL2:
            hits.append({"kind": kind, "value": g.get("c") or g.get("t") or g.get("r")})
        else:
            hits.append({"kind": kind, "variant": variant, "op": op, **g})
    assert len(hits) == 1, f"clause parsed {len(hits)} times: {cl!r}"
    return hits[0]


def check_v2(item):
    """the answer (True / False) recomputed from the rendered state alone"""
    st = item["state"]
    rec = json.loads(json.dumps(st["record"]))
    F = lambda x: Fraction(D(x)) if not isinstance(x, Fraction) else x
    cmpf = lambda x, op, lim: {"<=": x <= lim, "<": x < lim, ">=": x >= lim, ">": x > lim}[op]
    request, conv = split_notes(st["request"])
    clauses = [parse_clause_v2(x) for x in split_clauses_v2(request)]
    kinds = {c["kind"] for c in clauses}                            # days are counted: the request must say how (also when an earlier clause already fails)
    assert "count" in conv or not kinds & {"date_gap", "listing_age"}, "days are counted but the request does not say how"
    assert "add" in conv or "ready_by" not in kinds, "a date plus days is used but the request does not say how"
    for c in clauses:
        k = c["kind"]
        if k == "num":
            ok = cmpf(F(rec[c["field"]]), c["op"], F(c["limit"]))
        elif k == "date":
            ok = cmpf(rec[c["field"]], c["op"], c["limit"])
        elif k == "category":
            ok = rec["category"] == c["value"]
        elif k == "excluded_tag":
            ok = c["value"] not in rec["tags"]
        elif k == "required_tag":
            ok = c["value"] in rec["tags"]
        elif k == "region":
            ok = c["value"] in rec["ships_to"]
        elif k == "maker_in":
            ok = rec["maker"] in c["values"]
        elif k == "unit_price_max":
            ok = cmpf(F(rec["bundle_price"]) / rec["bundle_size"], c["op"], F(c["v"]))
        elif k == "discount_min":                                   # the discount as a share of the list price, exactly, against the stated percentage
            ok = cmpf((F(rec["list_price"]) - F(rec["price"])) * 100 / F(rec["list_price"]), c["op"], F(c["v"]))
        elif k == "total_max":
            ok = cmpf(F(rec["price"]) + F(rec["shipping_fee"]), c["op"], F(c["v"]))
        elif k == "conv":
            field = {"weight": "weight_g", "length": "length_cm", "volume": "volume_ml", "runtime": "runtime_min"}[c["variant"]]
            ok = cmpf(F(rec[field]), c["op"], F(c["v"]) * F(c["f"]))      # the record's figure against the stated limit times the stated factor
        elif k == "date_gap":
            assert "count" in conv, "days are counted but the request does not say how"
            ok = cmpf((datetime.date.fromisoformat(rec["shipped_on"]) - datetime.date.fromisoformat(rec["manufactured_on"])).days + conv["count"], c["op"], int(c["v"]))
        elif k == "ready_by":
            assert "add" in conv, "a date plus days is used but the request does not say how"
            ready = datetime.date.fromisoformat(rec["stocked_on"]) + datetime.timedelta(days=rec["handling_days"] + conv["add"])
            ok = cmpf(ready.isoformat(), c["op"], c["v"])
        elif k == "listing_age":
            assert "count" in conv, "days are counted but the request does not say how"
            ok = cmpf((datetime.date.fromisoformat(c["ref"]) - datetime.date.fromisoformat(rec["listed_on"])).days + conv["count"], c["op"], int(c["v"]))
        elif k == "certs_k_of_n":
            ok = cmpf(len(set(rec["certifications"]) & set(re.split(r", | and ", c["lst"]))), c["op"], int(c["v"]))
        else:                                                       # conditional
            ok = True if rec["ships_from"] == c["r"] else cmpf(rec["delivery_days"], c["op"], int(c["v"]))
        if not ok:
            return False
    return True


# ------------------------------------------------------------------------------------------------------- building a pair (v2)
def choose_kinds(rng, planted, n, ctx):
    """the planted kind and n - 1 others, all different, computed kinds a little more often; at most one kind that reads the price; only kinds the category can carry
    (no run time limit on a desk, no noise limit on a cable)"""
    kinds = [planted]
    weight = {k: (3 if k in KINDS_COMPUTED else 2) for k in KINDS2}
    while len(kinds) < n:
        cand = [k for k in KINDS2 if k not in kinds and not (k in PRICE_GROUP and PRICE_GROUP & set(kinds)) and usable_on(ctx["dom"], ctx["cat"], k)]
        kinds.append(rng.choices(cand, [weight[k] for k in cand])[0])
    rng.shuffle(kinds)
    return kinds


def default_fields(rng, ctx):
    """a value for every field of the record; the constraints of the request then fix their own fields.  The specs lie inside the ranges of the category; the fields
    that depend on the price (list price, shipping fee, bundle) are set once the price is final (see _make_pair_v2)"""
    dom, R = ctx["dom"], ctx["R"]
    price = draw_spec(rng, "price", *R["price"])
    rec = {"price": price, "rating": D(rng.randint(25, 50)) / 10}
    for f in dom["features"]:
        s = NUM2[f]
        if s["field"] in R:
            rec[s["field"]] = draw_spec(rng, s["field"], *R[s["field"]])
        elif f in ("warranty", "stock"):
            rec[s["field"]] = snap_to(D(str(round(rng.uniform(s["lo"], s["hi"]), 2))), s["step"])
    for field in ("weight_g", "length_cm", "volume_ml", "runtime_min"):
        if field in R:
            rec[field] = draw_spec(rng, field, *R[field])
    m = ordinal("2025-09-01") + rng.randrange(180)
    rec.update(manufactured_on=iso(m), shipped_on=iso(m + rng.randint(1, 50)), stocked_on=iso(ordinal("2026-01-10") + rng.randrange(100)),
               handling_days=rng.randint(1, 20), listed_on=iso(ordinal("2025-12-01") + rng.randrange(270)))
    for s in DATES.values():
        rec[s["field"]] = iso(rng.randint(ordinal(s["lo"]), ordinal(s["hi"])))
    rec.update(ships_from=rng.choice(ctx["regions"]), ships_to=rng.sample(ctx["regions"], rng.randint(2, 4)), delivery_days=rng.randint(1, 25),
               certifications=rng.sample(CERT_POOL, rng.randint(2, 4)), category=ctx["cat"], maker=rng.choice(ctx["makers"]))
    return rec


def sibling_regions(ctx, region):
    base = region.split("-")[0]
    return [r for r in ctx["regions"] if r.startswith(base + "-") and r != region]


def listed_certs(rng, c, h, total):
    """a certification list that holds exactly h of the listed certifications and has `total` entries"""
    others = [x for x in CERT_POOL if x not in c["listed"]]
    held = rng.sample(c["listed"], h)
    lst = held + rng.sample(others, total - h)
    rng.shuffle(lst)
    return lst, held, others


def planted_fields(rng, c, pattern, ctx):
    """-> (the fields of the positive record for the planted constraint, the single field that changes in the negative)"""
    k = c["kind"]
    if k == "category":
        return {"category": c["value"]}, {"category": ctx["alt"]}
    if k == "region":
        ships = rng.sample([r for r in ctx["regions"] if r != c["value"]], rng.randint(2, 3))
        ships.insert(rng.randrange(len(ships) + 1), c["value"])
        sib = [r for r in sibling_regions(ctx, c["value"]) if r not in ships]
        if not sib:
            raise RuntimeError("no sibling region")
        return {"ships_to": ships}, {"ships_to": [rng.choice(sib) if r == c["value"] else r for r in ships]}
    if k == "maker_in":
        return {"maker": rng.choice(c["values"])}, {"maker": rng.choice([m for m in ctx["makers"] if m not in c["values"]])}
    if k in ("excluded_tag", "required_tag"):
        return {}, None                                             # the tags are built once all constraints are known
    if k == "certs_k_of_n":
        h_pos, h_neg = planted_x(c, pattern)
        pos, held, others = listed_certs(rng, c, int(h_pos), rng.randint(max(int(h_pos), 2), 4))
        gone = rng.sample(held, int(h_pos - h_neg))
        fresh = rng.sample([x for x in others if x not in pos], len(gone))
        return {"certifications": pos}, {"certifications": [fresh[gone.index(x)] if x in gone else x for x in pos]}
    if k == "conditional":
        sib = sibling_regions(ctx, c["origin"])
        if pattern == "switch":                                     # the same record, shipped from inside the region (no limit) or from its sibling (limit applies)
            return {"ships_from": c["origin"], "delivery_days": c["limit"] + rng.randint(3, 10)}, {"ships_from": rng.choice(sib)}
        x_pos, x_neg = planted_x(c, pattern)
        return {"ships_from": rng.choice(sib + [r for r in ctx["regions"] if r != c["origin"]]), "delivery_days": int(x_pos)}, {"delivery_days": int(x_neg)}
    x_pos, x_neg = planted_x(c, pattern)
    pos, neg = fields_of(c, x_pos), fields_of(c, x_neg)
    diff = {f: v for f, v in neg.items() if pos[f] != v}
    assert len(diff) == 1, (k, pos, neg)
    return pos, diff


def free_fields(rng, c, ctx):
    """record fields that satisfy a (non-planted) constraint: on its limit or one step inside in half of the cases, else well inside"""
    k = c["kind"]
    near = rng.random() < 0.5
    if k == "category":
        return {"category": c["value"]}
    if k == "region":
        ships = rng.sample([r for r in ctx["regions"] if r != c["value"]], rng.randint(2, 3))
        ships.insert(rng.randrange(len(ships) + 1), c["value"])
        return {"ships_to": ships}
    if k == "maker_in":
        return {"maker": rng.choice(c["values"])}
    if k in ("excluded_tag", "required_tag"):
        return {}
    if k == "certs_k_of_n":
        h = int(free_x(rng, c, near))
        return {"certifications": listed_certs(rng, c, h, rng.randint(max(h, 2), 4))[0]}
    if k == "conditional":
        if rng.random() < 0.5:                                      # no limit applies: shipped from inside the region, however long delivery takes
            return {"ships_from": c["origin"], "delivery_days": rng.randint(1, 30)}
        return {"ships_from": rng.choice([r for r in ctx["regions"] if r != c["origin"]]), "delivery_days": int(free_x(rng, c, near))}
    return fields_of(c, free_x(rng, c, near))


def make_pair_v2(i, plan):
    """-> (positive spec, negative spec, info); retries with fresh random draws until the pair is valid"""
    for attempt in range(600):
        rng = rng_for("v2-pair", i, attempt)
        try:
            return _make_pair_v2(rng, plan)
        except (RuntimeError, ValueError, AssertionError, KeyError):
            continue
    raise RuntimeError(f"pair {i}: no valid draw")


def choose_category(rng, dom, planted):
    """the category of the record (for a planted category also the sibling of the negative) and the ranges of the specs that are plausible for it (for both
    categories of a planted pair)"""
    cats = [c for c in dom["cats"] if usable_on(dom, c, planted)]
    if planted == "category":
        cats = [c for c in cats if any(twin_ranges(c, x) for x in dom["cats"] if x != c)]
    cat = rng.choice(cats)
    if planted != "category":
        return cat, None, dict(PROFILE[cat])
    alt = rng.choice([x for x in dom["cats"] if x != cat and twin_ranges(cat, x)])
    return cat, alt, twin_ranges(cat, alt)


def check_plausible(rec):
    """a record the way a catalogue reader expects it: the price and every spec inside the range of its category and no spec the category does not have, never
    wider than long, list price >= price, a bundle at 0.70 to 0.95 of the price per unit, a shipping fee of at most 15 % of the price (and 31 euros)"""
    p = PROFILE[rec["category"]]
    scale = CURRENCY_SCALE[rec["currency"]]
    have = {f for f in SPEC_FIELDS if f in rec}
    assert have == set(p) - {"price"}, (rec["category"], sorted(have), sorted(p))
    for f in p:
        lo, hi = p[f] if f != "price" else (p[f][0] * scale, p[f][1] * scale)
        assert lo <= rec[f] <= hi, (rec["category"], f, rec[f])
    assert rec.get("width_cm", 0) <= rec["length_cm"]
    fr = lambda x: Fraction(str(x))
    assert fr(rec["list_price"]) >= fr(rec["price"]) * Fraction(105, 100), (rec["list_price"], rec["price"])
    ratio = fr(rec["bundle_price"]) / rec["bundle_size"] / fr(rec["price"])
    assert Fraction(70, 100) <= ratio <= Fraction(95, 100), (rec["bundle_price"], rec["bundle_size"], rec["price"])
    assert 0 <= fr(rec["shipping_fee"]) <= min(fr(rec["price"]) * Fraction(15, 100), 31 * scale), (rec["shipping_fee"], rec["price"])


def _make_pair_v2(rng, plan):
    dom = DOMAINS2[plan["domain"]]
    n_con, planted, pattern = plan["constraints"], plan["kind"], plan["pattern"]
    bases = []
    while len(bases) < 3:
        b = coin(rng)
        if b not in bases:
            bases.append(b)
    makers = []
    while len(makers) < 6:
        m = coin(rng)
        if m not in makers:
            makers.append(m)
    cat, alt, R = choose_category(rng, dom, planted)
    currency = rng.choice(CURRENCIES)
    R = dict(R, price=tuple(v * CURRENCY_SCALE[currency] for v in R["price"]))        # the price range is in euros: scaled to the currency of the record
    max_fs = [f for f in dom["max"] if feature_ok(f, R)]
    ctx = {"dom": dom, "currency": currency, "regions": [f"{b}-{d}" for b in bases for d in DIRECTIONS], "makers": makers,
           "cat": cat, "alt": alt, "R": R, "min_f": rng.choice([f for f in dom["min"] if feature_ok(f, R)]), "max_f": rng.choice(max_fs) if max_fs else None,
           "excluded": [], "required": []}
    kinds = choose_kinds(rng, planted, n_con, ctx)
    cons = [setup_v2(rng, k, ctx, pattern if k == planted else "free") for k in kinds if k != "unit_price_max"]
    rec = default_fields(rng, ctx)
    neg_change = None
    for c in cons:
        if c["kind"] == planted:
            pos_f, neg_change = planted_fields(rng, c, pattern, ctx)
        else:
            pos_f = free_fields(rng, c, ctx)
        rec.update(pos_f)
    price = D(rec["price"])                                         # the price is final: the fields that depend on it follow (list price above it, a shipping fee of a few
    if "discount_min" not in kinds:                                 # percent, a bundle at 0.70 to 0.95 of the price per unit)
        rec["list_price"] = (price * D(str(round(rng.uniform(1.08, 1.6), 2)))).quantize(D("0.01"))
    if "total_max" not in kinds:
        rec["shipping_fee"] = min(D(rng.randint(0, 2500)) / 100 * CURRENCY_SCALE[ctx["currency"]], price * D("0.12")).quantize(D("0.01"))
    if "unit_price_max" in kinds:
        c = setup_unit_price(rng, ctx, pattern if planted == "unit_price_max" else "free", price)
        cons.append(c)
        if planted == "unit_price_max":
            pos_f, neg_change = planted_fields(rng, c, pattern, ctx)
        else:
            pos_f = free_fields(rng, c, ctx)
        rec.update(pos_f)
    else:
        pack = rng.choice([p for p in PACKS if p * price <= 6000 * CURRENCY_SCALE[ctx["currency"]]])
        rec["bundle_size"] = pack
        rec["bundle_price"] = (price * D(str(round(rng.uniform(0.72, 0.93), 3)))).quantize(D("0.01")) * pack
    filler_pool = [t for t in EXCLUDABLE + REQUIRABLE if t not in ctx["excluded"] and t not in ctx["required"]]
    fillers = rng.sample(filler_pool, rng.randint(1, 2))
    tags = list(ctx["required"]) + fillers
    rng.shuffle(tags)
    rec["tags"] = tags
    for c in cons:                                                  # the tag of a planted tag constraint takes the place of a filler tag / of the required tag
        if c["kind"] == planted == "excluded_tag":
            i_f = tags.index(rng.choice(fillers))
            neg_change = {"tags": [c["value"] if j == i_f else t for j, t in enumerate(tags)]}
        if c["kind"] == planted == "required_tag":
            neg_change = {"tags": [rng.choice([t for t in filler_pool if t not in tags]) if t == c["value"] else t for t in tags]}
    n_id = rng.randint(10000, 99999)
    rec.update({"id": f"L-{n_id}", "title": f"{coin(rng)} {rng.choice(['S', 'X', 'M', 'Pro', 'Mini', 'Plus'])}-{rng.randint(100, 999)}",
                "seller": f"{coin(rng)} {rng.choice(['Outlet', 'Shop', 'Direct', 'Store', 'Depot'])}", "currency": ctx["currency"],
                "colour": rng.choice(["black", "white", "grey", "green", "blue", "red", "sand", "orange"]), "reviews": rng.randint(3, 4000),
                "listing_status": "active"})
    order = (["id", "title", "category", "maker", "seller", "price", "currency", "list_price", "shipping_fee", "bundle_size", "bundle_price", "rating"]
             + [NUM2[f]["field"] for f in dom["features"]]
             + ["weight_g", "length_cm", "volume_ml", "runtime_min", "manufactured_on", "shipped_on", "stocked_on", "handling_days", "listed_on",
                "release_date", "available_from", "ships_from", "ships_to", "delivery_days", "tags", "certifications", "colour", "reviews", "listing_status"])
    conv = lambda f, v: jnum(f, v) if isinstance(v, (Decimal, int)) and not isinstance(v, bool) else v
    pos_rec = {f: conv(f, rec[f]) for f in order if f in rec}        # a spec the category does not have is not in the record
    neg_rec = dict(pos_rec)
    assert neg_change and len(neg_change) == 1, neg_change
    for f, v in neg_change.items():
        neg_rec[f] = conv(f, v)
    changed = [f for f in pos_rec if pos_rec[f] != neg_rec[f]]
    assert len(changed) == 1, changed
    for c in cons:
        if c["kind"] == "discount_min":
            assert pos_rec["list_price"] == jnum("list_price", c["list"])
    check_plausible(pos_rec)
    check_plausible(neg_rec)
    rng.shuffle(cons)                                               # the order of the constraints in the request
    layout = rng.randrange(4)
    clauses = [clause_v2(c, rng, ctx) for c in cons]
    for c, text in zip(cons, clauses):                              # no wording that names another field
        assert not (c["kind"] in FOREIGN and FOREIGN[c["kind"]].search(text)), (c["kind"], text)
    request = render_request2(clauses, layout, day_notes(rng, kinds))
    planted_c = next(c for c in cons if c["kind"] == planted)
    return ({"constraints": cons, "record": pos_rec, "request": request}, {"constraints": cons, "record": neg_rec, "request": request},
            {"planted": planted_c, "changed": changed[0], "change": [changed[0], neg_rec[changed[0]], pos_rec[changed[0]]],
             "currency": ctx["currency"], "domain": dom["name"], "pattern": pattern})


# ------------------------------------------------------------------------------------------------------------- plan (v2)
def make_plan_v2():
    """300 pairs: constraints 6 / 9 / 12 x twenty kinds (the ten computed kinds 7 per level, the ten simple ones 3 per level); the kinds
    with a distance to a limit get the patterns edge_pos / edge_neg / mirror equally often (the conditional kind also 'switch'), so that
    exactly as many positives as negatives sit on a limit"""
    rng = rng_for("v2-plan")
    plan = []
    for n_con in CONSTRAINTS2:
        for kind in KINDS2:
            plan += [{"constraints": n_con, "kind": kind} for _ in range(7 if kind in KINDS_COMPUTED else 3)]
    for kind in KINDS2:
        idx = [k for k, p in enumerate(plan) if p["kind"] == kind]
        if kind in CATEGORICAL2:
            pats = ["none"] * len(idx)
        elif kind == "discount_min":
            pats = ["adjacent"] * len(idx)
        elif kind == "conditional":
            pats = ["edge_pos"] * 6 + ["edge_neg"] * 6 + ["mirror"] * 3 + ["switch"] * 6
        else:
            pats = ["edge_pos", "edge_neg", "mirror"] * (len(idx) // 3)
        assert len(pats) == len(idx)
        rng.shuffle(pats)
        for k, pat in zip(idx, pats):
            plan[k]["pattern"] = pat
    doms = [k % 4 for k in range(PAIRS)]
    rng.shuffle(doms)
    for p, d in zip(plan, doms):
        p["domain"] = d
    rng.shuffle(plan)
    return plan


MARGIN2 = {"edge_pos": ("at_limit", "one_step"), "edge_neg": ("one_step", "at_limit"), "mirror": ("one_step", "one_step"),
           "switch": ("switch", "switch"), "adjacent": ("one_step", "one_step"), "none": ("categorical", "categorical")}


def to_item_v2(n, pair, spec, info, dev):
    c = info["planted"]
    pos_neg = 1 if dev else 0
    kinds = sorted(x["kind"] for x in spec["constraints"])
    meta = {"source_id": f"{n:05d}", "pair": pair, "level": LEVEL_OF[len(spec["constraints"])], "constraints": len(spec["constraints"]), "deviation": dev or "none",
            "planted_kind": c["kind"], "planted_field": info["changed"], "domain": info["domain"], "category": spec["record"]["category"], "kinds": kinds,
            "pattern": info["pattern"], "margin": MARGIN2[info["pattern"]][pos_neg],
            "day_convention": "difference between the two dates (the same day is 0 days)" if any(k in DAY_KINDS for k in kinds) else None}
    if c["kind"] == "discount_min":                                  # the wording of a discount limit ("at least" / "more than") does not change the truth: no price is on it
        meta["limit_wording"] = "inclusive" if c["text_op"] == ">=" else "exclusive"
    elif "inclusive" in c:
        meta["limit_wording"] = "inclusive" if c["inclusive"] else "exclusive"
    meta["spec"] = {"constraints": jsonable(spec["constraints"]), "change": jsonable(info["change"]) if dev else None}
    return {"id": f"{TASK}:{n:05d}", "state": {"request": spec["request"], "record": spec["record"]},
            "questions": {"q": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": dict(OPTIONS)}},
            "gold": "no" if dev else "yes", "soft": None, "group": f"{TASK}:pair:{pair:03d}", "meta": meta}


def main_v2():
    plan = make_plan_v2()
    built = []
    for i, p in enumerate(plan):
        pos, neg, info = make_pair_v2(i, p)
        built.append((i, p, pos, info, None))
        built.append((i, p, neg, info, p["kind"]))
    rng_for("order").shuffle(built)
    rows = []
    for n, (pair, p, spec, info, dev) in enumerate(built, 1):
        it = to_item_v2(n, pair, spec, info, dev)
        # ---- truth twice
        assert truth_v2(spec) == (dev is None), f"{it['id']}: truth {truth_v2(spec)} but planted deviation {dev}"
        assert check_v2(it) == truth_v2(spec), f"{it['id']}: check {check_v2(it)} != truth {truth_v2(spec)}"
        # ---- exactly one constraint fails, and it is the planted one
        failing = [c for c in spec["constraints"] if not holds2(c, spec["record"])]
        assert [c["kind"] for c in failing] == ([] if dev is None else [dev]), (it["id"], [c["kind"] for c in failing])
        assert len(spec["constraints"]) == p["constraints"] and len({c["kind"] for c in spec["constraints"]}) == p["constraints"]
        # ---- the conventions are written in the request (the check refuses a request that counts days without saying how), the record is plausible, the level is set
        kinds = [c["kind"] for c in spec["constraints"]]
        stated = split_notes(spec["request"])[1]
        assert ("count" in stated) == any(k in ("date_gap", "listing_age") for k in kinds) and ("add" in stated) == ("ready_by" in kinds), (it["id"], kinds, stated)
        check_plausible(spec["record"])
        assert it["meta"]["level"] == LEVEL_OF[it["meta"]["constraints"]]
        it["_class"] = it["gold"]
        rows.append(it)
    rows.sort(key=lambda r: r["id"])
    assign_orders(rows)
    by_pair = collections.defaultdict(dict)
    for it in rows:
        by_pair[it["meta"]["pair"]][it["gold"]] = it
    for k, d in by_pair.items():                                     # the pair differs in exactly one field of the record, the request is the same
        a, b = d["yes"]["state"]["record"], d["no"]["state"]["record"]
        assert [f for f in a if a[f] != b[f]] == [d["no"]["meta"]["planted_field"]], k
        assert d["yes"]["state"]["request"] == d["no"]["state"]["request"] and list(a) == list(b)
    # ---- balance and dials
    cls = collections.Counter(r["gold"] for r in rows)
    assert cls == {"yes": 300, "no": 300}, cls
    nc = collections.Counter(r["meta"]["constraints"] for r in rows)
    assert set(nc.values()) == {200} and set(nc) == set(CONSTRAINTS2), nc
    lv = collections.Counter((r["meta"]["level"], r["gold"]) for r in rows)
    assert lv == {(l, g): 100 for l in (1, 2, 3) for g in ("yes", "no")}, lv
    dev = collections.Counter(r["meta"]["deviation"] for r in rows)
    assert dev["none"] == 300 and all(dev[k] == (21 if k in KINDS_COMPUTED else 9) for k in KINDS2), dev
    per = collections.Counter((r["meta"]["constraints"], r["meta"]["deviation"]) for r in rows)
    assert all(per[(n, k)] == (7 if k in KINDS_COMPUTED else 3) for n in CONSTRAINTS2 for k in KINDS2), per
    margin = collections.Counter((r["gold"], r["meta"]["margin"]) for r in rows)
    for m in ("at_limit", "one_step", "switch", "categorical"):
        assert margin[("yes", m)] == margin[("no", m)], (m, margin)
    computed_share = [sum(1 for c in r["meta"]["kinds"] if c in KINDS_COMPUTED) / r["meta"]["constraints"] for r in rows]
    tested, worst = vocabulary_test(rows, ["yes", "no"])
    lengths = [len(state_text(r)) for r in rows]
    for r in rows:
        del r["_class"]
    d = f"{HERE}/tasks/{TASK}"
    os.makedirs(d, exist_ok=True)
    with open(f"{d}/items.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(rows, key=lambda r: r["id"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    task = {"task": TASK, "layer": "G", "title": "Generated catalogue requests: does the record satisfy every constraint?",
            "decision": "whether a catalogue record satisfies every constraint of a request (yes) or violates one of them by at most one step of the quantity it compares (no)",
            "source": {"name": f"generator build/gen_{TASK}.py", "url": "", "files": [], "split": "generated, seed 20261007, DIFFICULTY v2",
                       "version": "gen_v4, 2026-10-08: day-count convention stated in every request that counts days; field wording that cannot be read as another field; "
                                  "plausible records (list price >= price, bundle at 0.70-0.95 of the unit price, price and physical specs inside per-category ranges); meta.level 1/2/3 = 6/9/12 constraints "
                                  "(script of 2026-10-07, harder dials v2; DIFFICULTY = \"v1\" regenerates the first version)"},
            "licence": "generated by the benchmark's script (no third-party text)", "redistribution": "items included",
            "labels": "programmatic", "item_source": "generated", "metric": "accuracy", "chance": 0.5, "rows": len(rows),
            "groups": PAIRS, "question_type": "choice", "options": 2,
            "notes": ("Version v2 (harder than the first version, which is regenerated with DIFFICULTY = \"v1\"). 600 items = 300 contrast pairs (meta.pair, group): "
                      "one request with a record that satisfies all constraints (yes) and the same record with one field changed so that exactly one constraint fails "
                      "(no). The compared quantity of the planted constraint is ON the limit named in the request or ONE step from it in both members of a pair (a step is one cent, "
                      "one gram, one day, one certification, ...): in the negative on the limit (a wording that does not count it) or one step beyond it, in the positive on the "
                      "limit (a wording that counts it) or one step inside it. "
                      "Dial: constraints (6, 9, 12), twenty kinds of which ten need a small computation on the record (price per unit, discount from the list price, price plus "
                      "shipping, a unit conversion with the factor stated, days between two dates, a date plus days, the age of the listing on a stated day, at least k of n "
                      "certifications, a delivery limit that only applies to items shipped from outside a region); meta.margin and meta.pattern say how the planted constraint "
                      "sits to its limit. The metric is item accuracy; the group allows a pair analysis. Everything is invented and every answer is computed "
                      "twice (specification and a parser of the rendered request); the README lists the ten computed kinds with the step of each. State length %d to %d characters (median %d). "
                      "gen_v4 (2026-10-08): a request that counts days says how (the difference between the two dates, the same day is 0 days; a date plus N days is N days later), no "
                      "wording can be read as another field of the record (the maker is only 'made by', a region only 'ships to'), the records are plausible (list price above the price, a "
                      "bundle at 0.70 to 0.95 of the unit price, the price and every physical spec inside the range of its category, the width below the length) and meta.level is 1 / 2 / 3 for 6 / 9 / 12 constraints."
                      % (min(lengths), max(lengths), sorted(lengths)[300]))}
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
    write_readme_v2(d, rows, dev, per, margin, lengths, val, aud, tested, worst, sum(computed_share) / len(computed_share))
    print("vocabulary test:", tested, "tokens with frequency >= 20, worst ratio %.2f (%s)" % worst)
    print("counts per class", dict(cls), "| constraints", dict(nc))
    print("deviation", dict(sorted(dev.items())))
    print("margin (class, label)", sorted(margin.items()))
    print("computed kinds per request: %.2f of the constraints" % (sum(computed_share) / len(computed_share)))
    print("state length", min(lengths), max(lengths), "median", sorted(lengths)[300])


def write_readme_v2(d, rows, dev, per, margin, lengths, val, aud, tested, worst, computed_share):
    by_id = sorted(rows, key=lambda x: x["id"])
    partner = lambda x: next(r for r in by_id if r["group"] == x["group"] and r["id"] != x["id"])
    day = lambda x: any(k in DAY_KINDS for k in x["meta"]["kinds"])
    pick = lambda lvl, pred: next(x for x in by_id if x["meta"]["level"] == lvl and pred(x) and day(x))
    ex = [pick(1, lambda x: x["gold"] == "no" and x["meta"]["deviation"] == "conv_min" and x["meta"]["pattern"] == "edge_pos"),
          pick(2, lambda x: x["gold"] == "yes" and x["meta"]["planted_kind"] == "listing_age" and "ready_by" in x["meta"]["kinds"]),
          pick(3, lambda x: x["gold"] == "no" and x["meta"]["deviation"] == "unit_price_max" and "date_gap" in x["meta"]["kinds"])]
    notes_n = collections.Counter(w for r in rows for w in split_notes(r["state"]["request"])[1])
    n_fields = [len(r["state"]["record"]) for r in rows]
    fr = lambda v: Fraction(str(v))
    ratios = [fr(r["state"]["record"]["bundle_price"]) / r["state"]["record"]["bundle_size"] / fr(r["state"]["record"]["price"]) for r in rows]
    dash = lambda p, f: "%s to %s" % (f"{p[f][0]:,}", f"{p[f][1]:,}") if f in p else "-"
    prof_rows = "\n".join("| %s | %s |" % (c, " | ".join(dash(PROFILE[c], f) for f in ["price"] + SPEC_FIELDS)) for dom in DOMAINS2 for c in dom["cats"])

    def show(x):
        p, f = partner(x), x["meta"]["planted_field"]
        first, *rest = fmt_item(x).split("\n")
        note = (f"Planted constraint `{x['meta']['planted_kind']}` (pattern `{x['meta']['pattern']}`). Its pair partner `{p['id']}` (gold **{p['gold']}**) has the same request and the same "
                f"record except `{f}`: {json.dumps(p['state']['record'][f])} there, {json.dumps(x['state']['record'][f])} here.")
        return "\n".join([first, "", note] + rest)

    doc = [   # kind, what the request states, what has to be worked out, one step (what the negative changes)
        ("price_max", "the price is at most / less than a limit", "-", "0.01 (one cent)"),
        ("feature_min", "rating, warranty months, stock units, power or battery capacity at least / more than a limit", "-", "the field's own step: 0.1 (rating), 10 (mAh), else 1"),
        ("feature_max", "width or noise level at most / less than a limit", "-", "1 cm / 1 dB"),
        ("category", "the category is X", "-", "a sibling category of the same product family"),
        ("excluded_tag", "the tag X must be absent", "-", "the tag is present"),
        ("required_tag", "the tag X must be present", "-", "the tag is missing"),
        ("region", "it ships to X", "-", "a sibling region (`Orsk-North` for `Orsk-South`)"),
        ("date_max", "the availability date on or before / before a date", "-", "1 day"),
        ("date_min", "the release date on or after / after a date", "-", "1 day"),
        ("maker_in", "made by A, B or C", "-", "a maker that is not listed"),
        ("unit_price_max", "bundle price divided by bundle size is at most / less than a limit near the price (bundle sizes 2 to 50, a bundle costs at most 6,000)", "a division by the bundle size (the quotient is exact to the cent)",
         "0.01 of the unit price (the bundle price moves by 0.01 times the bundle size)"),
        ("discount_min", "the price is at least / more than P percent below the list price, worked out exactly", "P percent of the list price; the limit is never a whole number of cents, so no price is on it",
         "0.01 of the price (the highest price that is discounted enough and the next cent)"),
        ("total_max", "price plus shipping fee is at most / less than a limit", "a sum", "0.01 (the shipping fee moves)"),
        ("conv_max", "weight in kg (the record has grams, 1 kg = 1000 g) or length in inches (the record has centimetres, 1 inch = 2.54 cm) at most / less than a limit",
         "a conversion with the factor stated in the request", "1 g / 0.1 cm"),
        ("conv_min", "volume in litres (the record has millilitres, 1 litre = 1000 ml) or run time in hours (the record has minutes, 1 hour = 60 minutes) at least / more than a limit (only for the categories that have the spec)",
         "a conversion with the factor stated in the request", "1 ml / 1 minute"),
        ("date_gap", "days between the manufacturing date and the shipping date at most / at least N", "the difference of two dates", "1 day"),
        ("ready_by", "the stocked date plus the handling days is on or before / before a date", "a date plus a number of days", "1 handling day"),
        ("listing_age", "as of a day named in the request, the listing has been online for at most / at least N days", "the difference between the listing date and the stated day", "1 day"),
        ("certs_k_of_n", "at least k (or more than k) of 3 or 4 listed certifications are held", "a count of the certifications of the record that are on the list", "1 certification"),
        ("conditional", "if the item ships from outside R, the delivery time is at most / less than N days (items shipped from R have no limit)",
         "the limit applies only after the shipping origin is read", "1 day, or the origin itself (`switch`)")]
    assert [k for k, *_ in doc] == KINDS2
    pairs = [r for r in by_id if r["gold"] == "yes"]
    pat = collections.Counter(r["meta"]["pattern"] for r in pairs)
    level_computed = {n: sum(1 for r in rows if r["meta"]["constraints"] == n for c in r["meta"]["kinds"] if c in KINDS_COMPUTED) / sum(1 for r in rows if r["meta"]["constraints"] == n)
                      for n in CONSTRAINTS2}
    wording = collections.Counter((r["gold"], r["meta"]["limit_wording"]) for r in rows if "limit_wording" in r["meta"])
    mt = lambda g, m: margin[(g, m)]
    txt = f"""# {TASK}

Generated catalogue requests: does the record satisfy every constraint? (layer G, generated, programmatic truth; version v2 with the gen_v4 fixes of 2026-10-08)

- Decision: whether a catalogue record satisfies every constraint of a request (yes) or violates one of them by at most ONE step of the quantity it compares (no).
- Source: generator `build/gen_{TASK}.py` (standard library only, `random.Random(20261007)` and sub-generators; the output is identical on every run); no third-party text.
- Version: this directory holds **v2**, the harder dials. The first version (3 / 5 / 7 constraints, ten kinds that read one field each, hosted reference 0.997) is regenerated by setting `DIFFICULTY = "v1"` at the top of the script (or `BENCH_DIFFICULTY=v1`), which rewrites this directory.
- Licence: generated by the benchmark's script (no third-party text); items included.
- Rows: {len(rows)} in {PAIRS} contrast pairs (300 yes, 300 no); metric: accuracy (chance 0.5).
- Rebuild: `python3 build/gen_{TASK}.py`
- gen_v4 (2026-10-08), four fixes of defects found by the human audit: (1) every request that counts days states how (section "Conventions written in the request"); (2) no wording can be read as another field of the record ("Wording of the fields"); (3) the records are plausible ("Plausible records"); (4) `meta.level` = 1 / 2 / 3 for 6 / 9 / 12 constraints. The pair design, patterns, margins and balances are those of v2.

## What is generated

A request in words with 6, 9 or 12 constraints (one of four layouts, each with a lead-in sentence; four phrasings per constraint kind and per conversion; sixteen comparator phrases that say in words whether the limit itself counts)
and the catalogue record of an invented product as a JSON object of {min(n_fields)} to {max(n_fields)} fields (id, title, category, maker, seller, price, currency, list price, shipping fee, bundle size and price, rating, up to three domain features,
weight in grams, length in centimetres, volume in millilitres and run time in minutes where the category has them, six dates, handling days, shipping origin, shipping regions, delivery days, tags, certifications, colour, reviews, status).
Four domains (outdoor, audio, kitchen, office) with five sibling categories each and region families. A spec that a category does not have is not in its records (an audio cable has no battery, an office desk no run time), and a request never constrains a spec the category lacks.
The answer is yes when the record satisfies every constraint.
The constraints of a request are all of different kinds (twenty kinds; at most one of `price_max`, `discount_min`, `total_max`, which all read the price), the computed kinds drawn a little more often ({computed_share:.2f} of the constraints on average).
The order of the two options is drawn per item (`meta.order`; exactly half of the positives and half of the negatives list `yes` first).

Twenty constraint kinds, the values of `meta.deviation`: ten read one field of the record, ten need a small computation on it. Every conversion factor is stated in the request itself, every limit says in words whether it counts.

| `meta.deviation` | what the request states | what has to be worked out | one step (what the negative changes) |
|---|---|---|---|
""" + "\n".join(f"| `{k}` | {a} | {b} | {c} |" for k, a, b, c in doc) + f"""

**Pairs.** The positive and the negative of a pair share the request and every field of the record but one (`meta.planted_field`), a minimal contrast. In the negative that field puts the compared quantity of exactly one
constraint (`meta.deviation`) ON the limit named in the request, when the wording does not count the limit ("less than", "more than", "before", "after"), or ONE step beyond it, never further (one step: right column); in the positive
it sits ON the limit, when the wording counts it, or one step inside. For the computed kinds the quantity is the worked-out value, not the raw field: the unit price moves by one cent (the bundle price by one cent times the bundle size), the discount by one cent of the price, the shipping date by one day.

**Near the limits on both sides.** The planted constraint is on its limit or one step from it in BOTH members of a pair (`meta.pattern` of the pair, `meta.margin` of the item):

| `meta.pattern` | positive | negative | pairs |
|---|---|---|---|
| `edge_pos` | exactly on an inclusive limit | one step beyond it | {pat['edge_pos']} |
| `edge_neg` | one step inside an exclusive limit | exactly on it | {pat['edge_neg']} |
| `mirror` | one step inside | one step outside | {pat['mirror']} |
| `adjacent` (`discount_min`) | the highest price that is discounted enough | the next cent | {pat['adjacent']} |
| `switch` (`conditional`) | the item ships from inside R, no limit, however long delivery takes | the item ships from the sibling region of R and takes longer than the limit | {pat['switch']} |
| `none` | categorical kinds (no distance) | | {pat['none']} |

| `meta.margin` (planted constraint) | yes | no |
|---|---|---|
| at_limit (value exactly on the limit) | {mt('yes', 'at_limit')} | {mt('no', 'at_limit')} |
| one_step (one step from the limit) | {mt('yes', 'one_step')} | {mt('no', 'one_step')} |
| switch | {mt('yes', 'switch')} | {mt('no', 'switch')} |
| categorical | {mt('yes', 'categorical')} | {mt('no', 'categorical')} |

Positives and negatives sit on a limit equally often ({mt('yes', 'at_limit')} each) and one step from it equally often ({mt('yes', 'one_step')} each). The limit wording of the planted numeric constraints is inclusive in {wording[('no', 'inclusive')]} negatives and exclusive in {wording[('no', 'exclusive')]} (positives {wording[('yes', 'inclusive')]} / {wording[('yes', 'exclusive')]}).
The other numeric constraints of the request are satisfied in both members: on their limit or within two steps of it in half of the cases, else by a wide margin. The cents of every money limit are drawn at random, so the digits of a value one cent from a limit say nothing about the class.

## Conventions written in the request

A request that counts days between two dates (`date_gap`, `listing_age`) ends with a sentence that says how: a count of days is the plain difference between the two dates, the same day is 0 days (four phrasings; {notes_n['count']} items). A request with `ready_by` also says that a date plus N days is the date N days later, the date itself being day 0 (four phrasings; {notes_n['add']} items). `check_v2` reads these sentences, takes the offset from them and refuses a request that counts days without one, so the key follows exactly the stated convention (with a one-day-longer count the planted values on a limit would change class). The limits of the date kinds `date_max`, `date_min` and `ready_by` say in words whether the date itself counts, as before.

## Wording of the fields

The wording of a constraint never names or paraphrases another field of the record: the maker is only "made by", "its maker is one of", "the maker is", "was made by" (never "comes from" or "origin", which read as the shipping origin); a region is only "ships to", "shipping to ... is possible", "one of the regions it ships to", "can be shipped to" (never "shipping regions"); the origin of the `conditional` kind is only "ships from"; the listing age is always "counted from the listing date"; a category is "filed under" (not "listed"). The generator asserts for every clause of these kinds that none of the words that would name another field occurs (`FOREIGN`).

## Plausible records

- The price lies inside the price range of its category (table, in euros; prices, shipping fees and limits in kronor are ten times as large, in the other currencies as given). The price kinds (`price_max`, `discount_min`, `total_max`) draw their limits inside this range.
- `list_price` is at least 1.05 times `price` in every record (the discount kind fixes the list price and puts the price at least 10 percent below it).
- A bundle costs `bundle_size` times a unit price of {float(min(ratios)):.2f} to {float(max(ratios)):.2f} times the price (range allowed: 0.70 to 0.95; bundle sizes are limited so that a bundle costs at most 6,000 euros). The `unit_price_max` limit lies near the price (0.78 to 0.92 times), the near misses are one cent from it.
- The shipping fee is a few percent of the price (at most 12 percent, at most 31); the `total_max` kind puts the limit at the price plus a fee of 3 to 10 percent of the total.
- Every physical spec lies inside the range of its category (same table; `check_plausible` asserts price and specs for all {len(rows)} records), the width is below the length, the specs a category lacks are absent. The limits of the spec kinds (width, noise, power, battery, weight, length, volume, run time) are drawn inside the range, the values "well inside" a limit use the room the range leaves, so the planted near misses stay one step from the limit and every value stays plausible. In a pair that changes the category, the sibling has the same specs and both categories are plausible for every value of the record.

| category | price (EUR) | weight (g) | length (cm) | volume (ml) | run time (min) | power (W) | battery (mAh) | noise (dB) | width (cm) |
|---|---|---|---|---|---|---|---|---|---|
{prof_rows}

## Dials

| dial | levels | items per level |
|---|---|---|
| `constraints` (in the request) = `meta.level` | 6, 9, 12 = level 1, 2, 3 | 200 each (100 yes, 100 no) |

Constraints that need a computation per request (mean): {level_computed[6]:.1f} / {level_computed[9]:.1f} / {level_computed[12]:.1f} at 6 / 9 / 12 constraints. `meta.level` is 1 / 2 / 3 (and `meta.constraints` 6 / 9 / 12). State length: {min(lengths)} to {max(lengths)} characters (median {sorted(lengths)[len(lengths)//2]}).

## Deviation kinds (negatives)

| `meta.deviation` | items | per dial level (6 / 9 / 12) |
|---|---|---|
""" + "\n".join(f"| `{k}` | {dev[k]} | {per[(6, k)]} / {per[(9, k)]} / {per[(12, k)]} |" for k in KINDS2) + f"""

## Checks made by the script

- `truth_v2(spec)` (structured constraints on the record, exact arithmetic) and `check_v2(item)` (parses the rendered request, including the stated limits, conversion factors and reference days, and evaluates it on the record again, with its own date and fraction arithmetic) agree on all 600 items.
- In every pair the request is identical, the records differ in exactly one field, the positive satisfies every constraint and the negative fails exactly one, the planted kind.
- Classes are exactly balanced; every dial level has 200 items; every computed kind has 21 negatives (7 per level) and every simple kind 9 (3 per level).
- Exactly as many positives as negatives sit on a limit ({mt('yes', 'at_limit')} each) and one step from it ({mt('yes', 'one_step')} each).
- Every request that counts days carries the convention sentence, no other request does; the clauses of the field kinds contain no word of another field; every record passes `check_plausible`; 100 yes and 100 no at each `meta.level`.
- Vocabulary test: {tested} tokens of frequency >= 20 are tested (numbers and dates included); none occurs in one class at more than twice the rate of the other (largest ratio {worst[0]:.2f}, `{worst[1]}`).
- Shortcut audit (`python3 audit.py {TASK}`), best length rule below 0.55:

```
{aud[0]}
{aud[1]}
```

Validator: `{val[1].strip() if len(val) > 1 else val}`

## Examples (one per level; each request counts days and so states the convention)

""" + "\n\n".join(f"### level {x['meta']['level']} ({x['meta']['constraints']} constraints), `{x['meta']['planted_kind']}`, gold {x['gold']}\n\n" + show(x) for x in ex) + """

## Independence from training generators

The items are disjoint from any training generator of the authors by construction: this is a new generator, written for the benchmark;
names, templates and records share nothing with the generators used for training.
"""
    open(f"{d}/README.md", "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    (main_v2 if DIFFICULTY == "v2" else main_v1)()
