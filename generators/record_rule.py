"""Task record_rule (layer F, generated): "which integrity rule does the batch violate?"
    python3 generators/record_rule.py               (standard library only; no argument, no input file, no download)

ITEM.  `state` is one text: a short description of a data pipeline and of the record type (field list), 4 to 7 numbered integrity
rules R1 ... R7 (each written in one sentence that also fixes the convention: inclusive ranges, "filled in" = present and not
null, strict or non-strict date order), the reference list that a reference rule refers to (shown only in schemas that have such a rule), and a batch of 6, 10 or 14 records as JSON
lines.  Question: "Which rule does the batch violate?"  Options: one key per rule of the schema (R1 ... Rk, each with the one-line
text of that rule as its option text) and `none` ("no rule is violated").  A batch breaks at most one rule; only the listed rules
count (stated in the state).  Gold = the key of the broken rule, or `none`.

RULE KINDS (6; `meta.violated_kind`).  unique (a key field has no duplicate in the batch) - reference (a field is a key of the
reference list) - range (a number lies in [lo, hi], both included) - conditional (when a field has a value another field must be
present and not null) - date_order (one date is not later than / strictly before another; both variants occur) - allowed (a field
takes one of a short list of values).  A schema has 4, 5, 6 or 7 rules: 4 or 5 distinct kinds, all 6, or all 6 and a second
range or allowed rule on another field (k = 7).  Eight invented record types (orders, staff, sensor readings, library loans,
support tickets, parcels, course enrolments, invoices) with 10 fields each; thresholds, allowed lists and phrasing are drawn per item.

DESIGN.  Every batch is built valid first.  The violated item has exactly one planted violation in one record (a duplicate key, a
reference key with one digit changed that is not in the list, a number one step or a few steps outside the range, a conditional
field emptied on a record that triggers it, a late date one day (or more) before the early one, a value outside the allowed list);
the other rules hold, which the script verifies.  Hard cases are hard for the right reason: valid batches contain boundary values
(exactly lo or hi, equal dates under a non-strict rule, first and last key of the reference list), near-identical ids and keys,
and non-triggered records with an empty conditional field; in half of the items that have a free kind, one *unlisted* oddity
(a duplicate key, a reversed date pair or an empty conditional field under a rule kind that this schema does not have) is planted in another
record - it is not a violation, because only the listed rules count (`meta.distractor`).

CLASSES AND DIAL.  600 items: `none` 86 (one seventh), and each of the 6 kinds 86, 86, 86, 86, 85, 85 (the nearest to equal
that 600 allows; 200 items per dial level and 28 or 29 per class and level).  Dial `records` = 6, 10, 14.  The number of rules k = 4 ... 7 is
spread evenly as well (`meta.rules`).  The key of the violated rule is spread evenly over R1 ... Rk for every k, and the position of
the gold option in the listed options is spread evenly over 0 ... k (the option order is drawn per item and recorded in
`meta.option_order`), so the "first option" rule of audit.py stays at chance.  The `none` items are chosen among the generated batches
by a greedy balancing of the tokens of the states (herding, then exchanges within a dial level until every token of frequency >= 14
has about its share of occurrences among the `none` items), and a planted value that makes a token too frequent among the violating
items is drawn again; this keeps the vocabulary test of rule 4 (no token of frequency >= 20 at more than twice the rate in one class)
satisfied for words and for all tokens, which the script asserts.

TRUTH TWICE.  `truth(spec)` checks every rule on the structured records.  `check(item)` parses the rule sentences (28 phrasings),
the reference list and the JSON lines from the state text and re-checks every rule with a different implementation (pairwise
loops).  The script asserts that both agree with the gold key on all 600 items, that a violating item breaks exactly the gold
rule and a `none` item breaks no rule, the exact class counts, the dial counts and the vocabulary test.
Invented content: identifiers, names and keys come from syllable generators and code-like patterns.

GEN_V4 (2026-10-08; the default version v2 only, version v1 is unchanged and still regenerates byte for byte).  Three fixes after the blind review of
the v2 set: (1) CONSISTENT BACKGROUND - outside the planted violation and the one or two deliberate oddities (meta.oddities) every record keeps the
relations between its own fields (tax = round(net x tax_rate / 100), stored totals, second date not before the first) and a record that names an earlier
record (a recheck, a credit, a reopened ticket ...) is dated after it; the references are drawn before the dates, a planted violation changes the cells
that its own rule needs and the cells that must follow (the tax and gross of a planted tax_rate), and `stray_breaks2` asserts it for all 600 items;
(2) the STATUS CONVENTION is written in every state that shows a status column of a reference list (a rule that only asks for a key accepts every key
whatever its status, only a rule that names a status requires it); (3) the share of `none` (0.12 at every level) is asserted against 1 / mean number
of options."""
import collections
import copy
import datetime
import json
import os
import random
import re
import sys

sys.dont_write_bytecode = True                           # the script imports validate / audit from audits/: leave no cache there
HERE = os.path.dirname(os.path.abspath(__file__))                    # generators/
ROOT = os.path.join(os.path.dirname(HERE), "generated")              # the items are written to ROOT/tasks/<family>/
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "audits"))    # validate.py and audit.py (run on ROOT/tasks/<family>/)
TASK, SEED = "record_rule", 20261007
OUT = os.path.join(ROOT, "tasks", TASK)
DIFFICULTY = "v2"        # "v2": the harder second version (default, what the task directory holds) | "v1": the first version, byte for byte
DIFFICULTY = os.environ.get("BENCH_DIFFICULTY", DIFFICULTY)             # e.g. BENCH_DIFFICULTY=v1 python3 generators/record_rule.py
assert DIFFICULTY in ("v1", "v2"), DIFFICULTY
BENCH_OUT, BENCH_SEED = os.environ.get("BENCH_OUT"), os.environ.get("BENCH_SEED")
SEED_TAG = ""                                            # "s<k>:" in the ids and groups of a set made with BENCH_SEED=k
if BENCH_SEED is not None:                               # another item set of the same design (sealed split); version v2 only
    if not BENCH_OUT:
        sys.exit("BENCH_SEED is accepted only together with BENCH_OUT: the published item set is never overwritten by another seed")
    if DIFFICULTY != "v2":
        sys.exit("BENCH_SEED applies to version v2 only (the first version exists for the seed 20261007 alone)")
    if not re.fullmatch(r"-?\d+", BENCH_SEED.strip()):
        sys.exit(f"BENCH_SEED must be an integer, not {BENCH_SEED!r}")
    SEED = int(BENCH_SEED)
    SEED_TAG = f"s{SEED}:"
if BENCH_OUT:                                            # write <BENCH_OUT>/<task>/ and touch nothing under ROOT/tasks
    OUT = os.path.join(os.path.abspath(BENCH_OUT), TASK)
LEVELS = [6, 10, 14]                                     # records per batch (the dial)
KINDS = ["unique", "reference", "range", "conditional", "date_order", "allowed"]
CLASSES = ["none"] + KINDS
# per level: items per class (none, then the six kinds); rotated so that the totals are 86 86 86 86 86 85 85
QUOTA = {6: [29, 29, 29, 29, 28, 28, 28], 10: [29, 28, 28, 28, 29, 29, 29], 14: [28, 29, 29, 29, 29, 28, 28]}
QUESTION = {"type": "choice", "instructions": "Which rule does the batch violate?"}
N_NONE = sum(QUOTA[lv][0] for lv in LEVELS)                  # 86 items without a violation, 514 with one
N_VIOL = sum(sum(QUOTA[lv]) for lv in LEVELS) - N_NONE
NONE_TEXT = "No rule is violated: the batch satisfies every rule."
DISTRACTOR_RATE = 0.5          # share of the items with a free rule kind that get an unlisted oddity (0 switches the distractors off)

SYL = ("ka ke ki ko la le li lo ma me mi mo na ne ni no ra re ri ro sa se si so ta te ti to va ve vi vo za ze zi zo "
       "dor kel mar ven tor quin fal gor hal jor nil pel rud sev tas bren dar").split()
SUFFIX = ["Lines", "Freight", "Express", "Logistics", "Transit"]


def sub(label):
    """a sub-generator derived from the master generator random.Random(20261007) and a label (deterministic)"""
    return random.Random(f"{random.Random(SEED).getrandbits(64)}/{label}")


def word(rng, lo=2, hi=3):
    return "".join(rng.choice(SYL) for _ in range(rng.randint(lo, hi)))


def person(rng):
    return word(rng).capitalize() + " " + word(rng).capitalize()


# ----------------------------------------------------------------------------------------------------------------
# record types: key field, reference field (with its list), two numeric fields, two fields with a short vocabulary, a date
# pair, a trigger field (yes/no), the field that is required when the trigger is "yes" and whether that field may also be
# filled on a record that does not trigger it (an unpaid invoice has no payment date, a non-express order may name a carrier)
# ----------------------------------------------------------------------------------------------------------------
def D(name, noun, key, ref, nums, enums, dates, cond):
    return dict(name=name, noun=noun, key=key, ref=ref, nums=nums, enums=enums, dates=dates, cond=cond)


DOMAINS = [
    D("orders", "order", ("order_id", "ORD", 4), ("customer", "customers", "CU", 3),
      [("quantity", [1, 2, 5], [20, 24, 30, 40, 48]), ("unit_price", [5, 10, 20], [300, 400, 500, 900])],
      [("status", ["new", "paid", "packed", "shipped", "cancelled", "returned", "held"]), ("channel", ["web", "phone", "store", "partner", "kiosk"])],
      ("placed_on", "shipped_on"), ("express", "carrier", "company", True)),
    D("staff", "staff", ("emp_id", "E", 4), ("dept", "departments", "DP", 2),
      [("weekly_hours", [8, 10, 16], [40, 45, 48, 60]), ("grade", [1, 2], [6, 8, 9, 12])],
      [("contract", ["permanent", "fixed_term", "intern", "contractor", "seasonal", "casual", "agency"]), ("site", ["north", "south", "harbor", "campus", "remote", "depot"])],
      ("start_on", "probation_end"), ("on_call", "phone_ext", "code:ext", True)),
    D("readings", "sensor reading", ("reading_id", "RD", 5), ("sensor", "sensors", "SN", 3),
      [("humidity", [5, 10, 20], [80, 90, 95, 100]), ("battery", [0, 5, 10], [90, 95, 100])],
      [("mode", ["auto", "manual", "test", "idle", "calibration", "sleep"]), ("quality", ["good", "fair", "poor", "unknown", "stale"])],
      ("taken_on", "uploaded_on"), ("alarm", "alarm_code", "code:AL", False)),
    D("loans", "library loan", ("loan_id", "LN", 5), ("member", "members", "MB", 4),
      [("copies", [1], [3, 4, 5, 6]), ("renewals", [0], [2, 3, 4])],
      [("format", ["print", "audio", "large_print", "ebook", "map", "journal"]), ("branch", ["central", "harbor", "campus", "north", "mobile", "annex"])],
      ("borrowed_on", "due_on"), ("damaged", "damage_note", "phrase:torn_cover|water_stain|loose_binding|missing_page|scratched_disc", False)),
    D("tickets", "support ticket", ("ticket_id", "TK", 5), ("team", "teams", "TM", 2),
      [("hours_spent", [0, 1], [40, 60, 80]), ("severity", [1], [4, 5])],
      [("status", ["open", "waiting", "resolved", "closed", "reopened", "parked"]), ("channel", ["mail", "phone", "chat", "portal", "walk_in"])],
      ("opened_on", "closed_on"), ("escalated", "manager", "person", True)),
    D("parcels", "parcel", ("parcel_id", "PK", 6), ("depot", "depots", "DP", 3),
      [("weight_kg", [1, 2], [20, 25, 30, 40]), ("declared_value", [10, 20, 50], [500, 800, 1000, 2000])],
      [("service", ["standard", "express", "overnight", "economy", "freight"]), ("packaging", ["box", "envelope", "crate", "tube", "pallet"])],
      ("sent_on", "delivered_on"), ("signature", "receiver", "person", True)),
    D("enrolments", "course enrolment", ("enrol_id", "EN", 5), ("course", "courses", "CR", 3),
      [("credits", [1, 2, 3], [6, 8, 10, 12]), ("seat", [1], [60, 80, 100, 120])],
      [("mode", ["online", "onsite", "hybrid", "evening", "intensive"]), ("level", ["intro", "core", "advanced", "seminar", "capstone"])],
      ("starts_on", "ends_on"), ("needs_lab", "lab_slot", "code:L", False)),
    D("invoices", "invoice", ("invoice_no", "INV", 5), ("vendor", "vendors", "VN", 3),
      [("amount", [10, 20, 50], [5000, 9000, 9500]), ("tax_rate", [0], [19, 21, 25])],
      [("currency", ["EUR", "USD", "GBP", "CHF", "SEK"]), ("terms", ["net15", "net30", "net45", "prepaid", "on_receipt"])],
      ("issued_on", "due_on"), ("paid", "paid_on", "date", False)),
]
DOM = {d["name"]: d for d in DOMAINS}

# ----------------------------------------------------------------------------------------------------------------
# rule sentences: four phrasings per kind (date order: four non-strict and four strict)
# ----------------------------------------------------------------------------------------------------------------
RULE_TEXT = {
    "unique": ["`{f}` must be unique: no two records of the batch may have the same `{f}`.",
               "Every record needs its own `{f}`; a value of `{f}` that occurs twice in the batch is not allowed.",
               "`{f}` identifies a record, so two records must never share a `{f}`.",
               "The values of `{f}` are pairwise different within the batch."],
    "reference": ["`{f}` must be a key listed in the reference list `{L}`.",
                  "Every `{f}` has to appear in the reference list `{L}`.",
                  "`{f}` refers to an entry of `{L}`; a value that is not in that list is not allowed.",
                  "The value of `{f}` must exist in the reference list `{L}` given below."],
    "range": ["`{f}` must be a number from {lo} to {hi}, both included.",
              "`{f}` lies between {lo} and {hi}, including both.",
              "The value of `{f}` may not be below {lo} or above {hi}.",
              "`{f}` is at least {lo} and at most {hi}."],
    "conditional": ["If `{c}` is \"{v}\", then `{t}` must be filled in (present and not null).",
                    "When `{c}` equals \"{v}\", the field `{t}` is required: it must be present and not null.",
                    "A record with `{c}` = \"{v}\" must also give `{t}` (present and not null).",
                    "`{t}` is required for every record whose `{c}` is \"{v}\" (present and not null); other records may leave it out."],
    "date_order": ["`{a}` must not be later than `{b}`; the same day is fine.",
                   "`{b}` may not be earlier than `{a}`; equal dates are allowed.",
                   "In every record `{a}` comes on or before `{b}`.",
                   "`{a}` has to be the same day as `{b}` or earlier."],
    "date_strict": ["`{a}` must be earlier than `{b}`; the same day is not allowed.",
                    "`{b}` has to come strictly after `{a}`; equal dates are not allowed.",
                    "In every record `{a}` comes before `{b}`, never on the same day.",
                    "`{a}` must be at least one day before `{b}`."],
    "allowed": ["`{f}` must be one of: {values}.",
                "The only allowed values of `{f}` are {values}.",
                "`{f}` takes one of these values: {values}.",
                "Allowed values for `{f}`: {values}; any other value is invalid."]}
INTRO = ["A data pipeline receives a batch of {n} {noun} records and checks it against the integrity rules below.",
         "The batch below holds {n} {noun} records. A pipeline validates every batch against the rules listed here.",
         "Before loading, a pipeline checks each batch of {noun} records against a set of integrity rules; this batch has {n} records.",
         "{n} {noun} records arrived in one batch. The rules below describe what a valid batch looks like."]
CONV = ["A batch breaks at most one of these rules; only the listed rules count, so other oddities in the data are not violations.",
        "At most one rule is broken by a batch. Anything the rules do not mention is not a violation.",
        "Only the listed rules are checked, and a batch breaks at most one of them.",
        "At most one of the rules is violated in any batch; data that none of the rules covers is not an error."]
GEN_RX = {"{f}": r"(?P<f>\w+)", "{L}": r"(?P<L>\w+)", "{c}": r"(?P<c>\w+)", "{t}": r"(?P<t>\w+)", "{a}": r"(?P<a>\w+)",
          "{b}": r"(?P<b>\w+)", "{lo}": r"(?P<lo>\d+)", "{hi}": r"(?P<hi>\d+)", "{v}": r"(?P<v>\w+)",
          "{values}": r"(?P<values>\w+(?:, \w+)*)"}


def tmpl_regex(t):
    """regular expression of a rule sentence; a placeholder that occurs twice becomes a back-reference"""
    seen, out = set(), []
    for part in re.split(r"(\{[A-Za-z]+\})", t):
        if part in GEN_RX:
            name = part[1:-1]
            out.append(f"(?P={name})" if name in seen else GEN_RX[part])
            seen.add(name)
        else:
            out.append(re.escape(part))
    return re.compile("^" + "".join(out) + "$")


RULE_RX = [(kind, i, tmpl_regex(t)) for kind, ts in RULE_TEXT.items() for i, t in enumerate(ts)]


def rule_sentence(r):
    k = r["kind"]
    if k == "unique":
        return RULE_TEXT[k][r["variant"]].format(f=r["field"])
    if k == "reference":
        return RULE_TEXT[k][r["variant"]].format(f=r["field"], L=r["list"])
    if k == "range":
        return RULE_TEXT[k][r["variant"]].format(f=r["field"], lo=r["lo"], hi=r["hi"])
    if k == "conditional":
        return RULE_TEXT[k][r["variant"]].format(c=r["if_field"], v=r["if_value"], t=r["then_field"])
    if k == "date_order":
        return RULE_TEXT["date_strict" if r["strict"] else "date_order"][r["variant"]].format(a=r["first"], b=r["second"])
    return RULE_TEXT[k][r["variant"]].format(f=r["field"], values=", ".join(r["values"]))


# ----------------------------------------------------------------------------------------------------------------
# values
# ----------------------------------------------------------------------------------------------------------------
DATE0 = datetime.date(2026, 1, 5)


def iso(d):
    return d.isoformat()


def gen_id(rng, prefix, digits):
    return f"{prefix}-{rng.randrange(10 ** (digits - 1), 10 ** digits)}"


def near_key(rng, key):
    pre, dig = key.rsplit("-", 1)
    for _ in range(60):
        d = list(dig)
        if rng.random() < 0.5:
            i = rng.randrange(len(d))
            d[i] = rng.choice([c for c in "0123456789" if c != d[i] and not (i == 0 and c == "0")])
        else:
            i = rng.randrange(len(d) - 1)
            d[i], d[i + 1] = d[i + 1], d[i]
        if d[0] != "0" and "".join(d) != dig:
            return f"{pre}-{''.join(d)}"
    raise AssertionError("near key")


def dep_value(rng, spec, early):
    kind = spec
    if kind == "company":
        return word(rng).capitalize() + " " + rng.choice(SUFFIX)
    if kind == "person":
        return person(rng)
    if kind == "date":
        return iso(early + datetime.timedelta(days=rng.randrange(0, 25)))
    if kind.startswith("code:"):
        return f"{kind[5:]}-{rng.randrange(10, 99)}" if kind[5:] != "ext" else f"ext-{rng.randrange(1000, 9999)}"
    return rng.choice(kind.split(":")[1].split("|")).replace("_", " ")


# ----------------------------------------------------------------------------------------------------------------
# a valid base: rules, reference list, records
# ----------------------------------------------------------------------------------------------------------------
def make_rules(rng, d, k):
    kinds = rng.sample(KINDS, k) if k <= 6 else KINDS + [rng.choice(["range", "allowed"])]
    rules, used_num, used_enum = [], [], []
    for kind in kinds:
        r = {"kind": kind, "variant": rng.randrange(4)}
        if kind == "unique":
            r["field"] = d["key"][0]
        elif kind == "reference":
            r["field"], r["list"] = d["ref"][0], d["ref"][1]
        elif kind == "range":
            j = rng.choice([x for x in (0, 1) if x not in used_num])
            used_num.append(j)
            f, los, his = d["nums"][j]
            r.update(field=f, lo=rng.choice(los), hi=rng.choice(his))
        elif kind == "conditional":
            r.update(if_field=d["cond"][0], if_value="yes", then_field=d["cond"][1])
        elif kind == "date_order":
            r.update(first=d["dates"][0], second=d["dates"][1], strict=rng.random() < 0.5)
        else:
            j = rng.choice([x for x in (0, 1) if x not in used_enum])
            used_enum.append(j)
            f, vocab = d["enums"][j]
            size = rng.choice([3, 3, 4]) if len(vocab) > 5 else rng.choice([2, 3, 3])
            chosen = rng.sample(vocab, size)
            r.update(field=f, values=[v for v in vocab if v in chosen], vocab=vocab)
        rules.append(r)
    return rules


def make_records(rng, d, rules, n):
    key_f, key_p, key_d = d["key"]
    ref_f, list_name, ref_p, ref_d = d["ref"]
    keys = []
    while len(keys) < n:
        k = gen_id(rng, key_p, key_d)
        if k not in keys:
            keys.append(k)
    if rng.random() < 0.4 and n >= 2:                                   # a near-duplicate pair of keys (valid: they differ)
        keys[1] = near_key(rng, keys[0])
    ref_keys = []
    for _ in range(rng.randint(6, 9) + n // 3):
        k = gen_id(rng, ref_p, ref_d)
        if k not in ref_keys:
            ref_keys.append(k)
    if rng.random() < 0.3:
        extra = near_key(rng, ref_keys[0])
        if extra not in ref_keys:
            ref_keys.append(extra)
    ref_keys.sort()
    rng_ranges = {r["field"]: (r["lo"], r["hi"]) for r in rules if r["kind"] == "range"}
    allowed = {r["field"]: r["values"] for r in rules if r["kind"] == "allowed"}
    strict = next((r["strict"] for r in rules if r["kind"] == "date_order"), False)
    trig_f, dep_f, dep_kind, dep_free = d["cond"]
    n_yes = max(2, round(n * 0.35))
    yes_idx = set(rng.sample(range(n), n_yes))
    recs = []
    for i in range(n):
        rec = {key_f: keys[i], ref_f: rng.choice(ref_keys)}
        for f, los, his in d["nums"]:
            lo, hi = rng_ranges.get(f, (min(los), max(his)))
            rec[f] = rng.choice([lo, hi]) if rng.random() < 0.12 else rng.randint(lo, hi)
        for f, vocab in d["enums"]:
            rec[f] = rng.choice(allowed.get(f, vocab))
        a = DATE0 + datetime.timedelta(days=rng.randrange(0, 300))
        delta = rng.choice([0, 0, 1, 2, 3, 5, 8, 13, 21, 34]) if not strict else rng.choice([1, 1, 2, 3, 5, 8, 13, 21, 34])
        rec[d["dates"][0]], rec[d["dates"][1]] = iso(a), iso(a + datetime.timedelta(days=delta))
        rec[trig_f] = "yes" if i in yes_idx else "no"
        if i in yes_idx or (dep_free and rng.random() < 0.4):
            rec[dep_f] = dep_value(rng, dep_kind, a)
        elif rng.random() < 0.5:
            rec[dep_f] = None
        recs.append(rec)
    ref_first, ref_last = ref_keys[0], ref_keys[-1]
    if rng.random() < 0.5:                                              # first and last key of the list are used
        recs[rng.randrange(n)][ref_f] = ref_first
        recs[rng.randrange(n)][ref_f] = ref_last
    return recs, ref_keys


def field_order(d):
    return [d["key"][0], d["ref"][0], d["nums"][0][0], d["nums"][1][0], d["enums"][0][0], d["enums"][1][0], d["dates"][0], d["dates"][1],
            d["cond"][0], d["cond"][1]]


def make_base(rng, d, n, k):
    for _ in range(100):
        rules = make_rules(rng, d, k)
        recs, ref_keys = make_records(rng, d, rules, n)
        spec = {"domain": d["name"], "n": n, "rules": rules, "lists": {d["ref"][1]: ref_keys}, "records": recs,
                "phrasing": {"intro": rng.randrange(4), "conv": rng.randrange(4)}, "planted": None, "distractor": None}
        if not any(broken(r, recs, spec["lists"]) for r in rules):
            return spec
    raise RuntimeError("no valid base")


# ----------------------------------------------------------------------------------------------------------------
# planting
# ----------------------------------------------------------------------------------------------------------------
def plant(rng, d, spec, rule, avoid=()):
    """plants one violation of `rule` (a rule dict or a pseudo rule) in one record; returns the record index"""
    recs, kind = spec["records"], rule["kind"]
    ok = [i for i in range(len(recs)) if i not in avoid]
    trig_f, dep_f = d["cond"][:2]
    if kind == "unique":
        i, j = rng.sample(ok, 2)
        recs[i][rule["field"]] = recs[j][rule["field"]]
    elif kind == "reference":
        i = rng.choice(ok)
        keys = spec["lists"][rule["list"]]
        while True:
            bad = near_key(rng, rng.choice(keys))
            if bad not in keys:
                break
        recs[i][rule["field"]] = bad
    elif kind == "range":
        i = rng.choice(ok)
        lo, hi = rule["lo"], rule["hi"]
        r = rng.random()
        recs[i][rule["field"]] = hi + 1 if r < 0.4 else (lo - 1 if r < 0.65 and lo >= 1 else hi + rng.randint(2, max(3, hi // 5)))
    elif kind == "conditional":
        i = rng.choice([x for x in ok if recs[x][trig_f] == "yes"])
        if rng.random() < 0.5:
            recs[i][dep_f] = None
        else:
            del recs[i][dep_f]
    elif kind == "date_order":
        i = rng.choice(ok)
        a = datetime.date.fromisoformat(recs[i][rule["first"]])
        back = 0 if rule["strict"] and rng.random() < 0.5 else rng.choice([1, 1, 2, 3, 7, 10, 30])
        recs[i][rule["second"]] = iso(a - datetime.timedelta(days=back))
    else:
        i = rng.choice(ok)
        recs[i][rule["field"]] = rng.choice([v for v in rule["vocab"] if v not in rule["values"]])
    return i


def pseudo_rule(d, kind):
    if kind == "unique":
        return {"kind": kind, "field": d["key"][0]}
    if kind == "date_order":
        return {"kind": kind, "first": d["dates"][0], "second": d["dates"][1], "strict": False}
    return {"kind": kind, "if_field": d["cond"][0], "then_field": d["cond"][1]}


# ----------------------------------------------------------------------------------------------------------------
# truth (on the structured records) and check (on the state text)
# ----------------------------------------------------------------------------------------------------------------
def broken(rule, recs, lists):
    k = rule["kind"]
    if k == "unique":
        c = collections.Counter(r.get(rule["field"]) for r in recs)
        return any(v > 1 for v in c.values())
    if k == "reference":
        return any(r.get(rule["field"]) not in lists[rule["list"]] for r in recs)
    if k == "range":
        return any(not (rule["lo"] <= r[rule["field"]] <= rule["hi"]) for r in recs)
    if k == "conditional":
        return any(r.get(rule["if_field"]) == rule["if_value"] and r.get(rule["then_field"]) is None for r in recs)
    if k == "date_order":
        for r in recs:
            a, b = datetime.date.fromisoformat(r[rule["first"]]), datetime.date.fromisoformat(r[rule["second"]])
            if (a >= b) if rule["strict"] else (a > b):
                return True
        return False
    return any(r[rule["field"]] not in rule["values"] for r in recs)


def truth(spec):
    hit = [i for i, r in enumerate(spec["rules"], 1) if broken(r, spec["records"], spec["lists"])]
    assert len(hit) <= 1, hit
    return f"R{hit[0]}" if hit else "none"


def parse_state(text):
    pre, rec_txt = text.split("\n\nRecords (one JSON object per line):\n")
    parts = pre.split("\n\n")
    assert parts[2].startswith("Rules:\n") and len(parts) in (3, 4)
    rules_txt = parts[2][len("Rules:\n"):]
    lists = {}
    if len(parts) == 4:
        m = re.match(r"^Reference list `(\w+)` \((\d+) keys\): (.*)$", parts[3])
        lists[m.group(1)] = m.group(3).split(", ")
        assert len(lists[m.group(1)]) == int(m.group(2))
    rules = []
    for i, line in enumerate(rules_txt.split("\n"), 1):
        mm = re.match(r"^R(\d+)\. (.*)$", line)
        assert mm and int(mm.group(1)) == i, line
        hits = [(kind, rx.match(mm.group(2))) for kind, _, rx in RULE_RX]
        hits = [(kind, m2.groupdict()) for kind, m2 in hits if m2]
        assert len(hits) == 1, ("rule sentence not understood", line, hits)
        kind, g = hits[0]
        if kind == "date_strict":
            kind, g["strict"] = "date_order", True
        elif kind == "date_order":
            g["strict"] = False
        rules.append((kind, g))
    recs = [json.loads(l) for l in rec_txt.split("\n")]
    return rules, lists, recs


def check(item):
    """key of the violated rule read from the state text, with a second implementation of the rules (pairwise loops)"""
    rules, lists, recs = parse_state(item["state"])
    out = []
    for idx, (kind, g) in enumerate(rules, 1):
        bad = False
        if kind == "unique":
            vals = [r.get(g["f"]) for r in recs]
            bad = any(vals[i] == vals[j] for i in range(len(vals)) for j in range(i + 1, len(vals)))
        elif kind == "reference":
            keys = lists[g["L"]]
            bad = any(r.get(g["f"]) not in keys for r in recs)
        elif kind == "range":
            bad = any(r[g["f"]] < int(g["lo"]) or r[g["f"]] > int(g["hi"]) for r in recs)
        elif kind == "conditional":
            for r in recs:
                if r.get(g["c"]) == g["v"] and (g["t"] not in r or r[g["t"]] is None):
                    bad = True
        elif kind == "date_order":
            for r in recs:
                a, b = r[g["a"]], r[g["b"]]                                  # ISO dates compare like strings
                if (a >= b) if g["strict"] else (a > b):
                    bad = True
        else:
            allowed = g["values"].split(", ")
            bad = any(r[g["f"]] not in allowed for r in recs)
        if bad:
            out.append(idx)
    assert len(out) <= 1, out
    return f"R{out[0]}" if out else "none"


# ----------------------------------------------------------------------------------------------------------------
# rendering
# ----------------------------------------------------------------------------------------------------------------
def field_types(d):
    t = {}
    for f in field_order(d):
        t[f] = "text"
    for f, _, _ in d["nums"]:
        t[f] = "integer"
    for f in d["dates"]:
        t[f] = "date, YYYY-MM-DD"
    if d["cond"][2] == "date":
        t[d["cond"][1]] = "date, YYYY-MM-DD"
    return t


def render_state(spec):
    d = DOM[spec["domain"]]
    ph = spec["phrasing"]
    types = field_types(d)
    lines = [INTRO[ph["intro"]].format(n=spec["n"], noun=d["noun"]) + " " + CONV[ph["conv"]], "",
             f"Fields of a record: " + ", ".join(f"{f} ({types[f]})" for f in field_order(d)) + ".", "", "Rules:"]
    lines += [f"R{i}. " + rule_sentence(r) for i, r in enumerate(spec["rules"], 1)]
    for r in spec["rules"]:
        if r["kind"] == "reference":
            keys = spec["lists"][r["list"]]
            lines += ["", f"Reference list `{r['list']}` ({len(keys)} keys): " + ", ".join(keys)]
    lines += ["", "Records (one JSON object per line):"]
    lines += [json.dumps(r) for r in spec["records"]]
    return "\n".join(lines)


def make_criteria(spec, order):
    texts = {f"R{i}": rule_sentence(r) for i, r in enumerate(spec["rules"], 1)}
    texts["none"] = NONE_TEXT
    return {k: texts[k] for k in order}


# ----------------------------------------------------------------------------------------------------------------
# balancing: herding of the words of the states for the `none` items, kinds for the others, positions
# ----------------------------------------------------------------------------------------------------------------
TOKEN_RX = r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]"


def herd(feats, m, rng, min_df=8, swaps=6000):
    """choose m of the items so that every token occurs in the chosen set about m/N times as often as in all items"""
    N = len(feats)
    df = collections.Counter(t for f in feats for t in f)
    toks = sorted(t for t, c in df.items() if c >= min_df)
    tid = {t: i for i, t in enumerate(toks)}
    vec = [[tid[t] for t in sorted(f) if t in tid] for f in feats]
    frac = m / N
    mu = [df[t] * frac for t in toks]
    w = [1.0 / max(df[t] * frac * (1 - frac), 0.5) for t in toks]
    cnt = [0.0] * len(toks)
    chosen, rest = [], set(range(N))
    for s in range(1, m + 1):
        best, bc = None, None
        for i in sorted(rest):
            c = sum(w[t] * (2 * (cnt[t] - s * mu[t] / m) + 1) for t in vec[i]) + rng.random() * 1e-6
            if bc is None or c < bc:
                best, bc = i, c
        chosen.append(best)
        rest.discard(best)
        for t in vec[best]:
            cnt[t] += 1
    chosen_set, rest = set(chosen), sorted(rest)
    for _ in range(swaps):                                              # local search: exchange a chosen and an unchosen item
        a, b = rng.choice(sorted(chosen_set)), rng.choice(rest)
        delta = collections.Counter()
        for t in vec[a]:
            delta[t] -= 1
        for t in vec[b]:
            delta[t] += 1
        gain = sum(w[t] * ((cnt[t] + x - mu[t]) ** 2 - (cnt[t] - mu[t]) ** 2) for t, x in delta.items() if x)
        if gain < -1e-9:
            for t, x in delta.items():
                cnt[t] += x
            chosen_set.discard(a)
            chosen_set.add(b)
            rest[rest.index(b)] = a
    return sorted(chosen_set)


def balance_none(bases, quota, rng, sweeps=60000):
    """choose the `none` bases: per dial level quota[level] of them.  Start from a herding per level, then exchange none and
    violating bases of the same level until no token with frequency >= 14 has a count among the none items outside the band
    [0.8, 1.3] x its expectation (so that the rate of the token in the none class stays within a factor 2 of its rate in the
    violating class, the limit of the vocabulary test, even after the planted values are added)."""
    N = len(bases)
    feats = [set(re.findall(TOKEN_RX, b["text"])) for b in bases]
    df = collections.Counter(t for f in feats for t in f)
    toks = sorted(t for t, c in df.items() if c >= 14)
    tid = {t: i for i, t in enumerate(toks)}
    vec = [[tid[t] for t in sorted(f) if t in tid] for f in feats]
    total = sum(quota.values())
    e = [df[t] * total / N for t in toks]
    lo = [max(0.0, 0.8 * x - 0.5) for x in e]
    hi = [1.3 * x + 0.5 for x in e]

    def pen(t, c):
        return max(0.0, lo[t] - c) ** 2 + max(0.0, c - hi[t]) ** 2
    chosen = {}
    for lv in LEVELS:
        idx = [i for i, b in enumerate(bases) if b["level"] == lv]
        for j in herd([feats[i] for i in idx], quota[lv], sub(f"herd/{lv}")):
            chosen[idx[j]] = lv
    cnt = [0] * len(toks)
    for i in chosen:
        for t in vec[i]:
            cnt[t] += 1
    bad = sum(pen(t, cnt[t]) for t in range(len(toks)))
    pool = {lv: [i for i, b in enumerate(bases) if b["level"] == lv and i not in chosen] for lv in LEVELS}
    for it in range(sweeps):
        if bad == 0:
            break
        lv = rng.choice(LEVELS)
        a = rng.choice(sorted(i for i, l in chosen.items() if l == lv))
        k = rng.randrange(len(pool[lv]))
        b = pool[lv][k]
        delta = collections.Counter()
        for t in vec[a]:
            delta[t] -= 1
        for t in vec[b]:
            delta[t] += 1
        gain = sum(pen(t, cnt[t] + x) - pen(t, cnt[t]) for t, x in delta.items() if x)
        if gain < 0:
            for t, x in delta.items():
                cnt[t] += x
            del chosen[a]
            chosen[b] = lv
            pool[lv][k] = a
            bad += gain
    print(f"balancing of the none items: {len(toks)} tokens, remaining penalty {bad:.2f}")
    return sorted(chosen)


def cycle_list(rng, values, n):
    """n values with every value used equally often (the last round is a random subset)"""
    out = []
    while len(out) < n:
        block = list(values)
        rng.shuffle(block)
        out += block
    out = out[:n]
    rng.shuffle(out)
    return out


def vocab_test(states, labels, min_freq=20, max_ratio=2.0, pattern=r"[a-z]+", classes=("none", "viol")):
    n = collections.Counter(labels)
    df = {c: collections.Counter() for c in classes}
    for s, g in zip(states, labels):
        df[g].update(set(re.findall(pattern, s.lower() if pattern == r"[a-z]+" else s)))
    bad, tested, worst = [], 0, 1.0
    for t in set(df[classes[0]]) | set(df[classes[1]]):
        a, b = df[classes[0]][t], df[classes[1]][t]
        if a + b < min_freq:
            continue
        tested += 1
        ra, rb = a / n[classes[0]], b / n[classes[1]]
        ratio = max(ra, rb) / min(ra, rb) if min(ra, rb) > 0 else float("inf")
        worst = max(worst, ratio)
        if ratio > max_ratio:
            bad.append((t, a, b))
    return sorted(bad), tested, worst


def dumps(item):
    return (json.dumps(item, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
            .replace("\x85", "\\u0085"))


def make_bases(master):
    """valid bases: 200 per dial level, k = 4..7 and the 8 record types spread evenly"""
    bases = []
    for lv in LEVELS:
        ks = cycle_list(master, [4, 5, 6, 7], 200)
        doms = cycle_list(master, [d["name"] for d in DOMAINS], 200)
        for k, dn in zip(ks, doms):
            seed = master.getrandbits(64)
            b = {"level": lv, "k": k, "seed": seed, "spec": make_base(random.Random(seed), DOM[dn], lv, k)}
            b["text"] = render_state(b["spec"])
            bases.append(b)
    return bases


def assign_classes(bases):
    """`none` by herding the tokens of the base texts, the six kinds by quota (most constrained bases first)"""
    cls = [None] * len(bases)
    for i in balance_none(bases, {lv: QUOTA[lv][0] for lv in LEVELS}, sub("balance")):
        cls[i] = "none"
    for lv in LEVELS:
        rest = [i for i, b in enumerate(bases) if b["level"] == lv and cls[i] is None]
        quota = {k: q for k, q in zip(KINDS, QUOTA[lv][1:])}
        assert sum(quota.values()) == len(rest)
        for attempt in range(200):
            r = sub(f"kinds/{lv}/{attempt}")
            order = sorted(rest, key=lambda i: (len({x["kind"] for x in bases[i]["spec"]["rules"]}), r.random()))
            left, got = dict(quota), {}
            for i in order:
                avail = [k for k in {x["kind"] for x in bases[i]["spec"]["rules"]} if left[k] > 0]
                if not avail:
                    break
                top = max(left[k] for k in avail)
                got[i] = r.choice(sorted(k for k in avail if left[k] == top))
                left[got[i]] -= 1
            else:
                break
        else:
            raise RuntimeError("kinds cannot be assigned")
        for i, k in got.items():
            cls[i] = k
    return cls


def positions(bases, cls):
    """balanced position of the violated rule among R1..Rk and of the gold option among the k + 1 options, per k"""
    by_k = collections.defaultdict(list)
    for i, b in enumerate(bases):
        by_k[b["k"]].append(i)
    rule_pos, opt_pos = {}, {}
    for k, idx in by_k.items():
        viol = [i for i in idx if cls[i] != "none"]
        for i, p in zip(viol, cycle_list(sub(f"rule-position/{k}"), list(range(k)), len(viol))):
            rule_pos[i] = p
        for i, p in zip(idx, cycle_list(sub(f"option-position/{k}"), list(range(k + 1)), len(idx))):
            opt_pos[i] = p
    return rule_pos, opt_pos


def finalize(b, kind, rule_pos, opt_pos, attempt=0):
    """plants the violation (and maybe an unlisted oddity) in a copy of the base, orders the rules and the options"""
    rng = random.Random(b["seed"] + 1 + 7919 * attempt)
    spec, d = copy.deepcopy(b["spec"]), DOM[b["spec"]["domain"]]
    rules = spec["rules"]
    gold_rule = rng.choice([x for x in rules if x["kind"] == kind]) if kind != "none" else None
    free = [k for k in ("unique", "date_order", "conditional") if k not in {x["kind"] for x in rules}]
    avoid = ()
    if free and rng.random() < DISTRACTOR_RATE:                          # an unlisted oddity in another record: not a violation
        dk = rng.choice(free)
        di = plant(rng, d, spec, pseudo_rule(d, dk))
        spec["distractor"] = {"kind": dk, "record": di + 1}
        avoid = (di,)
    if gold_rule is not None:
        ri = plant(rng, d, spec, gold_rule, avoid)
        spec["planted"] = {"kind": kind, "record": ri + 1}
    others = [x for x in rules if x is not gold_rule]
    rng.shuffle(others)
    if gold_rule is not None:
        others.insert(rule_pos, gold_rule)
    spec["rules"] = others
    gold = f"R{others.index(gold_rule) + 1}" if gold_rule is not None else "none"
    keys = [f"R{j}" for j in range(1, len(others) + 1)] + ["none"]
    rest = [x for x in keys if x != gold]
    rng.shuffle(rest)
    rest.insert(opt_pos, gold)
    spec["option_order"] = rest
    return spec, gold


def build_all(attempts=None):
    master = random.Random(SEED)
    bases = make_bases(master)
    cls = assign_classes(bases)
    rule_pos, opt_pos = positions(bases, cls)
    attempts = attempts or [0] * len(bases)
    fin = [finalize(b, cls[i], rule_pos.get(i, 0), opt_pos[i], attempts[i]) for i, b in enumerate(bases)]
    return bases, cls, rule_pos, opt_pos, fin


def offenders(fin, pattern):
    states = [render_state(spec) for spec, _ in fin]
    labels = ["none" if g == "none" else "viol" for _, g in fin]
    return vocab_test(states, labels, pattern=pattern), states


def main_v1():
    bases, cls, rule_pos, opt_pos, fin = build_all()
    attempts = [0] * len(bases)
    # repair: a planted value that makes a token much more frequent among the violating items is drawn again
    for rnd in range(400):
        (bad, tested, worst), states = offenders(fin, TOKEN_RX)
        if not bad:
            break
        t, a, b_ = max(bad, key=lambda x: max(x[1] / N_NONE, x[2] / N_VIOL) / max(min(x[1] / N_NONE, x[2] / N_VIOL), 1e-9))
        over_viol = (b_ / N_VIOL) > (a / N_NONE)
        cand = [i for i, (spec, g) in enumerate(fin)
                if (g != "none") == over_viol and t in set(re.findall(TOKEN_RX, states[i])) and t not in set(re.findall(TOKEN_RX, bases[i]["text"]))]
        if not cand:
            print("no planted cause for", t, a, b_)
            break
        i = sub(f"repair/{rnd}").choice(cand)
        attempts[i] += 1
        fin[i] = finalize(bases[i], cls[i], rule_pos.get(i, 0), opt_pos[i], attempts[i])
    print(f"repairs: {sum(attempts)}")
    items = [(b, spec, gold) for b, (spec, gold) in zip(bases, fin)]
    sub("shuffle").shuffle(items)
    out = []
    for n, (b, spec, gold) in enumerate(items, 1):
        state = render_state(spec)
        q = dict(QUESTION)
        q["criteria"] = make_criteria(spec, spec["option_order"])
        meta = {"source_id": f"{n:05d}", "domain": spec["domain"], "records": spec["n"], "rules": len(spec["rules"]),
                "deviation": spec["planted"]["kind"] if spec["planted"] else None,
                "violated": gold if gold != "none" else None, "violated_kind": spec["planted"]["kind"] if spec["planted"] else None,
                "record": spec["planted"]["record"] if spec["planted"] else None,
                "distractor": spec["distractor"], "option_order": spec["option_order"], "spec": spec}
        item = {"id": f"{TASK}:{n:05d}", "state": state, "questions": {"q": q}, "gold": gold, "soft": None, "group": None, "meta": meta}
        assert truth(spec) == gold == check(item), (item["id"], truth(spec), gold, check(item))
        out.append(item)
    items = out
    gold_kind = collections.Counter((it["meta"]["violated_kind"] or "none") for it in items)
    assert gold_kind["none"] == N_NONE == 86 and sorted(gold_kind.values()) == [85, 85, 86, 86, 86, 86, 86], gold_kind
    for lv in LEVELS:
        assert sum(1 for it in items if it["meta"]["records"] == lv) == 200
        for c, q in zip(CLASSES, QUOTA[lv]):
            assert sum(1 for it in items if it["meta"]["records"] == lv and (it["meta"]["violated_kind"] or "none") == c) == q
    labels = ["none" if it["gold"] == "none" else "viol" for it in items]
    states = [it["state"] for it in items]
    for pat, name in ((r"[a-z]+", "words"), (TOKEN_RX, "all tokens")):
        bad, tested, worst = vocab_test(states, labels, pattern=pat)
        print(f"vocabulary test ({name}, none vs violating): {tested} tokens with frequency >= 20, worst rate ratio {worst:.2f}, offenders {bad[:12]}")
        assert not bad, bad
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "items.jsonl"), "w", encoding="utf-8") as f:
        for it in items:
            f.write(dumps(it) + "\n")
    lens = [len(it["state"]) for it in items]
    write_task_files(items, min(lens), max(lens))
    report(items, lens)


def write_task_files(items, lo, hi):
    chance = sum(1 / len(it["questions"]["q"]["criteria"]) for it in items) / len(items)
    tj = {"task": TASK, "layer": "F", "title": "Generated record batches: which integrity rule does the batch violate?",
          "decision": "which of the listed integrity rules (unique key, reference to a list, numeric range, conditional requirement, date order, allowed values) a batch of records violates, or none",
          "source": {"name": f"generator build/gen_{TASK}.py", "url": "", "files": [], "split": "generated, random.Random(20261007)",
                     "version": "benchmark v0, 7 October 2026"},
          "licence": "generated by the benchmark's script (no third-party text)", "redistribution": "items included",
          "labels": "programmatic", "item_source": "generated", "metric": "accuracy", "chance": round(chance, 6), "rows": len(items),
          "groups": None, "question_type": "choice", "options": max(len(it["questions"]["q"]["criteria"]) for it in items),
          "notes": ("Options differ per item: one key per rule of the schema (R1 ... Rk, k = 4..7; the option text is the one-line text of the rule) plus none; "
                    "options = the maximum (8), chance = the mean of 1 / number of options. 86 none items (one seventh) and 86, 86, 86, 86, 85, 85 items for the six violated "
                    "rule kinds (unique, reference, range, conditional, date_order, allowed); a batch breaks at most one rule, the others hold (verified). "
                    "Dial meta.records = 6, 10, 14 records (200 items each); meta.rules = k, spread evenly. The key of the violated rule is spread evenly over "
                    "R1..Rk for every k; the option order is drawn per item (meta.option_order) with the gold option spread evenly over the positions. "
                    "In part of the items with a free kind one unlisted oddity is planted in another record (meta.distractor); it is not a violation because only the listed rules count. "
                    "The none items are chosen among the generated batches by a greedy balancing of the tokens of the states so that no word is much more frequent in one class (vocabulary test). "
                    f"8 invented record types, 28 rule phrasings. State length {lo} to {hi} characters. Truth by truth(spec) on the records; recomputed by check(item) from the state text "
                    "alone (rule sentences, reference list and JSON lines parsed, pairwise-loop implementation).")}
    with open(os.path.join(OUT, "task.json"), "w", encoding="utf-8") as f:
        json.dump(tj, f, indent=1, ensure_ascii=False)


def audit_lines():
    import audit as audit_mod
    audit_mod.HERE = ROOT
    r = audit_mod.audit(TASK)
    head = f"{'layer':5s} {'task':28s} {'rows':>5s} {'chance':>6s} {'major.':>6s} {'first':>6s} {'length':>6s}  rule"
    ln = f"{r['length']:6.3f}" if r["length"] is not None else f"{'':6s}"
    line = (f"{r['layer']:5s} {TASK:28s} {r['rows']:5d} {r['chance']:6.3f} {r['majority']:6.3f} {r['first']:6.3f} {ln}  "
            f"{r['length_rule']}{'   *' if r['flag'] else ''}")
    return head, line, r


def example_text(it):
    q = it["questions"]["q"]
    opts = "\n".join(f"  {k}: {v}" for k, v in q["criteria"].items())
    return f"STATE:\n{it['state']}\n\nQUESTION: {q['instructions']}\nOPTIONS:\n{opts}\nGOLD: {it['gold']}"


def report(items, lens):
    head, line, r = audit_lines()
    import validate as validate_mod
    validate_mod.HERE = ROOT
    tj, errs = validate_mod.check(TASK)
    status = "OK" if not errs else "ERRORS " + "; ".join(errs[:3])
    cell = collections.Counter((it["meta"]["records"], it["meta"]["violated_kind"] or "none") for it in items)
    kk = collections.Counter((it["meta"]["rules"], it["meta"]["records"]) for it in items)
    ex = []
    for lv, kind in zip(LEVELS, ["date_order", "conditional", "range"]):
        ex.append([it for it in items if it["meta"]["records"] == lv and it["meta"]["violated_kind"] == kind][0])
    lines = [f"# {TASK}", "", "Generated record batches: which integrity rule does the batch violate?", "",
             "- Decision: which of the listed integrity rules a batch of records violates, or none (a batch breaks at most one rule).",
             f"- Item source: generated by `build/gen_{TASK}.py` (`random.Random(20261007)`, standard library only, no input file); labels programmatic; licence: generated by the benchmark's script (no third-party text); items included.",
             f"- Rows: {len(items)}; options: R1 ... Rk (k = 4..7, option text = the rule's sentence) and none, so {tj['options']} at most; metric: accuracy (chance {tj['chance']:.4f}, the mean of 1 / number of options). Rebuild: `python3 build/gen_{TASK}.py`.", "",
             "## What is generated", "",
             "Each state describes a data pipeline and a record type (10 fields), lists 4 to 7 numbered integrity rules, the reference list that a reference rule refers to (shown only in schemas that have such a rule), and a batch of 6, 10 or 14 records as JSON lines. "
             "The six rule kinds are: a key is unique in the batch; a field is a key of the reference list; a number lies in an inclusive range; when a field has a value another field is required (present and not null); one date is not later than (or strictly before) another; a field takes one of an allowed list of values. "
             "Eight invented record types, 28 rule sentences (four for each kind, four more for the strict date order), thresholds and allowed lists drawn per item. Valid batches contain the hard cases of each rule (boundary values, equal dates, the first and last key of the list, near-identical ids, empty conditional fields on records that do not trigger it). "
             "In 600 items, 86 are valid (`none`) and 514 carry one planted violation in one record (a duplicate key, a reference key with one digit changed, a number one step or a few steps outside, an emptied conditional field on a record that triggers it, a late date one or more days before the early one, a value outside the allowed list). "
             "The options differ per item: R1 ... Rk with the one-line text of each rule, and `none`; their order is drawn per item.", "",
             "## Dials", "", "`meta.records` = records in the batch: 6, 10, 14 (200 items each). `meta.rules` = number of rules k = 4, 5, 6, 7 (spread evenly; `meta.violated` names the broken rule R1 ... Rk).", "",
             "## Classes (`meta.violated_kind`) per dial level", "", "| class | records 6 | records 10 | records 14 | total |", "|---|---|---|---|---|"]
    for c in CLASSES:
        lines.append(f"| {c} | " + " | ".join(str(cell[(lv, c)]) for lv in LEVELS) + f" | {sum(cell[(lv, c)] for lv in LEVELS)} |")
    dist = sum(1 for it in items if it["meta"]["distractor"])
    lines += ["", f"Items with an unlisted oddity planted in another record (`meta.distractor`, not a violation): {dist}.",
              f"State length: {min(lens)} to {max(lens)} characters (median {sorted(lens)[len(lens) // 2]}).", "",
              "## Checks run by the script", "",
              "- `truth(spec)` on the structured records and `check(item)` on the state text alone (28 rule phrasings, reference list and JSON lines parsed; pairwise-loop implementation) agree with the gold key on all 600 items; a violating item breaks exactly the gold rule, a `none` item breaks no rule.",
              "- Exact class counts as above; 200 items per dial level; the position of the gold option and of the violated rule spread evenly.",
              "- Vocabulary test (none vs violating items): no word (and no token) of frequency >= 20 is more than twice as frequent in one class as in the other.", "",
              "## Audit (`python3 audit.py " + TASK + "`)", "", "```", head, line, "```", "", f"`python3 validate.py {TASK}`: {status}.", "",
              "## Examples (one per dial level)", ""]
    for lv, it in zip(LEVELS, ex):
        lines += [f"### records = {lv} ({it['id']}, violated {it['meta']['violated']} = {it['meta']['violated_kind']}, record {it['meta']['record']})", "", "```", example_text(it), "```", ""]
    lines += ["## Relation to the authors' training data", "",
              "The items are disjoint from any training generator of the authors by construction: this is a new generator, written for this benchmark "
              "(its own templates and its own invented vocabulary), and every identifier and name is invented."]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"validate: {status}")
    print(head)
    print(line)
    print("classes:", dict(collections.Counter(it["meta"]["violated_kind"] or "none" for it in items)))
    print("per dial level:", dict(collections.Counter(it["meta"]["records"] for it in items)))
    print("per number of rules:", dict(sorted(collections.Counter(it["meta"]["rules"] for it in items).items())))
    print("gold keys:", dict(sorted(collections.Counter(it["gold"] for it in items).items())))
    print("gold position in the options:", dict(sorted(collections.Counter(it["meta"]["option_order"].index(it["gold"]) for it in items).items())))
    print(f"state length: {min(lens)} to {max(lens)} characters; items with a distractor: {dist}")
    print("example (hardest level):")
    print(example_text(ex[-1]))


# ================================================================================================================
# VERSION v2 (DIFFICULTY = "v2", the default).  Everything below is used by v2 only; the code above is the first version.
# ================================================================================================================
N2 = {1: 10, 2: 16, 3: 24}                                    # meta.level -> records per batch (the dial)
K2 = [6, 7, 8, 9]                                             # rules per schema
KINDS_NEW = ["composite", "ref_active", "dep_range", "xor", "derived", "sequence", "self_ref"]
KINDS2 = KINDS + KINDS_NEW                                    # the six kinds of v1 and seven that need a computation, two records or two lists
ODDITY_KINDS2 = ["unique", "composite", "date_order", "conditional", "xor", "derived", "sequence", "self_ref"]
BASES2, HOSTS2, GROUP2 = 50, 24, 4                            # batches per level, batches per level that also give the none item, items per batch
N_NONE2 = 3 * HOSTS2                                          # 72 items without a violation
N_VIOL2 = 3 * BASES2 * GROUP2 - N_NONE2                       # 528 items with one
FIELD_CAP2 = 17                                               # fields per record at most (keeps the longest state below 14,000 characters)
ODDITY_RATE2 = 0.5                                            # chance that an unlisted kind whose fields are shown gets an oddity
LAYOUTS2 = ["json", "table"]
LIST_FORMATS2 = ["inline", "lines"]
STATUS2 = [("active", ["inactive", "suspended"]), ("open", ["closed", "paused"]), ("approved", ["pending", "revoked"]),
           ("current", ["expired", "draft"])]
DATE2 = datetime.date(2025, 9, 1)
# gen_v4 (2026-10-08): the background of a batch is consistent.  Outside the planted violation and the one or two deliberate oddities every record keeps
# the relations between its own fields (tax = round(net * tax_rate / 100), stored total = operation on its operands, second date not before the first) and
# a record that names an earlier record (recheck_of, credit_for, ...) is dated after it - after its SECOND date where that date closes the named record
REF_SECOND2 = {"tickets", "parcels"}                          # a reopened ticket is dated after the closing of the ticket, a forwarded parcel after its delivery
STATUS_ODD2 = 0.75                                            # chance that a plain reference rule over a list with a status column meets a key of unusual status: 0.6 was drawn in gen_v3
                                                              # (0.78 as it came out, 156 items); 0.75 keeps about as many items (144) for the convention that the state now spells out
TAX_RATES2 = [7, 10, 19, 21, 25]                              # the rates of a batch that shows no tax_rate field (its tax is still a plausible share of the net)
REL_OF2 = {"derived": "total", "date_order": "pair", "self_ref": "ref"}   # the one relation that a planted violation or an oddity of this kind may break
FILL_ORDER2 = ["unique", "self_ref", "reference", "range", "conditional", "date_order", "allowed", "composite", "ref_active", "dep_range", "xor",
               "derived", "sequence"]                         # the named records before the dates (the dates follow the references); the rate before the tax
STATUS_NOTE2 = ["Statuses in a reference list: a rule that only asks for a key of the list accepts every key the list holds, whatever its status; "
                "only a rule that names a status requires it.",
                "Note on statuses: a plain look-up rule (one that names no status) accepts any key of the list, with any status; a status is required "
                "only by a rule that names it.",
                "The status written beside a key counts only for a rule that names a status. Every other rule that refers to the list accepts all of its "
                "keys, whatever their status.",
                "A listed key is a listed key, whatever its status: only a rule that names a status asks for it, and any other rule that refers to the "
                "list accepts all of its keys."]


def D2(name, noun, key, ref, act, pair, seq, der, num, dep, enum, dates, cond, xor, selfref):
    return dict(name=name, noun=noun, key=key, ref=ref, act=act, pair=pair, seq=seq, der=der, num=num, dep=dep, enum=enum,
                dates=dates, cond=cond, xor=xor, selfref=selfref)


# record types of v2.  key (field, prefix, digits) - ref: plain reference (field, list, prefix, digits) - act: reference to a list with a
# status column - pair: the two fields of the composite key - seq: running number - der: derived total (operation, two operands, total,
# operand ranges) - num: (field, lower limits, upper limits) - dep: (field, branch field, lower branch, upper branch, limits lo_a hi_a
# lo_b hi_b with lo_a < lo_b <= hi_a < hi_b) - enum: (field with an allowed list, sibling field without one, vocabulary) - dates - cond:
# (trigger, required field, kind of value) - xor: the two fields of which exactly one is filled - selfref: names the key of an earlier record
# gen_v4: no field names a quantity that the date pair would have to reproduce (a loan period, payment days) and no shipping mode repeats the name of the pickup / delivery fields
DOMAINS2 = [
    D2("order_lines", "order line", ("line_id", "OL", 5), ("customer", "customers", "CU", 3), ("warehouse", "warehouses", "WH", 2),
       (("order_no", "ON", 3), ("sku", "SK", 4)), "line_no", ("prod", "quantity", "unit_price", "line_total", (2, 12), (3, 95)),
       ("weight_kg", [1, 2, 5], [20, 25, 30, 40]), ("discount_pct", "tier", "retail", "trade", [(0, 10, 5, 30), (0, 12, 8, 35), (0, 15, 10, 40)]),
       ("ship_mode", "return_mode", ["standard", "express", "economy", "freight", "courier", "rail"]),
       ("placed_on", "shipped_on"), ("gift", "gift_note", "code:GN"), (("pickup_point", "PP", 3), ("delivery_zone", "DZ", 2)), "replaces"),
    D2("shifts", "shift entry", ("entry_id", "SE", 5), ("employee", "employees", "EM", 3), ("site", "sites", "ST", 2),
       (("roster", "RO", 2), ("slot", "SL", 3)), "row_no", ("sum", "base_min", "extra_min", "paid_min", (240, 540), (5, 180)),
       ("break_min", [10, 15, 20], [45, 60, 75, 90]), ("hourly_rate", "grade", "junior", "senior", [(12, 20, 18, 45), (11, 22, 19, 48), (13, 24, 20, 52)]),
       ("role", "cover_role", ["picker", "packer", "driver", "loader", "checker", "cleaner", "lead"]),
       ("worked_on", "approved_on"), ("overnight", "allowance_code", "code:AW"), (("cost_centre", "CC", 3), ("project_code", "PJ", 3)), "corrects"),
    D2("readings", "sensor reading", ("reading_id", "RD", 5), ("sensor", "sensors", "SN", 3), ("gateway", "gateways", "GW", 2),
       (("probe", "PB", 2), ("cycle", "CY", 3)), "frame_no", ("sum", "valid_samples", "void_samples", "all_samples", (120, 900), (3, 95)),
       ("humidity", [5, 10, 20], [80, 90, 95]), ("temp_c", "zone", "chilled", "ambient", [(0, 8, 5, 35), (1, 9, 6, 32), (2, 10, 7, 38)]),
       ("mode", "prior_mode", ["auto", "manual", "test", "idle", "calibration", "sleep"]),
       ("taken_on", "uploaded_on"), ("alarm", "alarm_code", "code:AL"), (("operator", "OP", 3), ("script_id", "SC", 3)), "recheck_of"),
    D2("loans", "library loan", ("loan_id", "LN", 5), ("member", "members", "MB", 4), ("branch", "branches", "BR", 2),
       (("card", "CD", 3), ("copy", "CP", 4)), "slip_no", ("prod", "days_late", "daily_fee", "fine", (2, 12), (3, 45)),
       ("renewals", [0], [2, 3, 4, 5]), ("deposit", "item_type", "media", "book", [(3, 10, 7, 28), (2, 9, 6, 30), (3, 14, 10, 42)]),
       ("condition_out", "condition_in", ["new", "good", "worn", "marked", "damaged", "repaired"]),
       ("borrowed_on", "due_on"), ("reserved", "reserve_code", "code:RS"), (("desk", "DK", 2), ("kiosk", "KS", 3)), "renewal_of"),
    D2("tickets", "support ticket", ("ticket_id", "TK", 5), ("team", "teams", "TM", 2), ("product", "products", "PR", 3),
       (("account", "AC", 3), ("case_no", "CN", 2)), "queue_pos", ("sum", "remote_min", "onsite_min", "billed_min", (15, 480), (10, 240)),
       ("severity", [1], [4, 5, 6]), ("response_hours", "plan", "premium", "basic", [(1, 24, 8, 72), (1, 12, 4, 48), (2, 30, 12, 96)]),
       ("channel", "reply_channel", ["mail", "phone", "chat", "portal", "walk_in", "fax"]),
       ("opened_on", "closed_on"), ("escalated", "manager", "person"), (("contact_ext", "EX", 4), ("contact_box", "BX", 3)), "reopens"),
    D2("parcels", "parcel", ("parcel_id", "PK", 6), ("depot", "depots", "DP", 3), ("route", "routes", "RT", 2),
       (("manifest", "MF", 3), ("bag", "BG", 2)), "scan_no", ("prod", "pieces", "piece_weight", "gross_weight", (2, 12), (3, 60)),
       ("declared_value", [10, 20, 50], [500, 800, 1000, 2000]), ("length_cm", "service", "letter", "freight", [(10, 35, 30, 240), (12, 40, 30, 200), (10, 45, 40, 180)]),
       ("packaging", "outer_packaging", ["box", "envelope", "crate", "tube", "pallet", "sack"]),
       ("sent_on", "delivered_on"), ("signature", "receiver", "person"), (("locker_id", "LK", 3), ("door_code", "DC", 4)), "forwarded_from"),
    D2("enrolments", "course enrolment", ("enrol_id", "EN", 5), ("course", "courses", "CR", 3), ("tutor", "tutors", "TU", 2),
       (("student", "SD", 4), ("module", "MD", 2)), "list_pos", ("sum", "tuition", "materials", "amount_due", (150, 900), (5, 120)),
       ("credits", [1, 2, 3], [6, 8, 10, 12]), ("weekly_hours", "mode", "part_time", "full_time", [(4, 16, 15, 40), (3, 18, 16, 38), (5, 20, 18, 45)]),
       ("level", "prior_level", ["intro", "core", "advanced", "seminar", "capstone", "bridge"]),
       ("starts_on", "ends_on"), ("needs_lab", "lab_slot", "code:LB"), (("grant_id", "GR", 3), ("invoice_ref", "IR", 4)), "transfer_of"),
    D2("invoice_lines", "invoice line", ("line_ref", "IL", 5), ("vendor", "vendors", "VN", 3), ("cost_unit", "cost_units", "KU", 2),
       (("invoice_no", "IV", 4), ("item_code", "IT", 2)), "page_line", ("sum", "net", "tax", "gross", (40, 900), (4, 190)),
       ("tax_rate", [0], [19, 21, 25]), ("handling_fee", "terms", "prepaid", "credit", [(0, 7, 5, 60), (0, 10, 7, 45), (0, 14, 10, 90)]),
       ("currency", "settle_currency", ["EUR", "USD", "GBP", "CHF", "SEK", "NOK"]),
       ("issued_on", "due_on"), ("disputed", "dispute_code", "code:DS"), (("po_number", "PO", 4), ("contract_no", "CT", 3)), "credit_for"),
]
DOM2 = {d["name"]: d for d in DOMAINS2}

# rule sentences of v2: four phrasings per kind, written for this version.  Fields and lists stand in backticks, text values in double
# quotes; every sentence states its own convention (limits included or not, same day allowed or not, what may repeat)
RULE_TEXT2 = {
    "unique": ["No two records of the batch may carry the same `{f}`.",
               "`{f}` is the record key: a value may occur only once in the batch.",
               "Each `{f}` appears at most once in the batch; a repeated `{f}` breaks this rule.",
               "Within the batch, all values of `{f}` differ from one another."],
    "composite": ["The pair (`{f}`, `{g}`) may occur only once in the batch; either field on its own may repeat.",
                  "No two records agree in both `{f}` and `{g}`; agreeing in just one of the two is fine.",
                  "`{f}` and `{g}` together identify a record: two records with the same `{f}` must differ in `{g}`.",
                  "A combination of `{f}` and `{g}` that turns up in two records is not allowed, although each of the two fields may repeat by itself."],
    "reference": ["`{f}` must be one of the keys of the reference list `{L}`.",
                  "Each `{f}` has to be found among the keys of the reference list `{L}`.",
                  "A `{f}` that is not a key of the reference list `{L}` is not allowed.",
                  "The reference list `{L}` must contain every value of `{f}`."],
    "ref_active": ["`{f}` must be a key of the reference list `{L}` whose status there is \"{s}\".",
                   "Each `{f}` has to appear in the reference list `{L}` with the status \"{s}\"; an entry with any other status does not count.",
                   "A `{f}` is valid only if the reference list `{L}` holds it and marks it \"{s}\".",
                   "Every value of `{f}` must be an entry of the reference list `{L}` that is marked \"{s}\"."],
    "range": ["`{f}` must be a whole number from {lo} to {hi}; {lo} and {hi} themselves are allowed.",
              "`{f}` is never smaller than {lo} and never larger than {hi}.",
              "The lowest allowed `{f}` is {lo}, the highest is {hi}.",
              "`{f}` stays within {lo} to {hi}, limits included."],
    "dep_range": ["`{f}` must be from {lo1} to {hi1} when `{b}` is \"{v1}\" and from {lo2} to {hi2} when `{b}` is \"{v2}\"; the limits are included.",
                  "For a record with `{b}` = \"{v1}\", `{f}` lies between {lo1} and {hi1}; for a record with `{b}` = \"{v2}\", between {lo2} and {hi2} (limits included in both cases).",
                  "The allowed span of `{f}` depends on `{b}`: {lo1} to {hi1} for \"{v1}\", {lo2} to {hi2} for \"{v2}\", limits included.",
                  "If `{b}` is \"{v1}\", `{f}` is at least {lo1} and at most {hi1}; if `{b}` is \"{v2}\", at least {lo2} and at most {hi2}."],
    "conditional": ["Whenever `{c}` is \"{v}\", `{t}` must be filled in.",
                    "A record whose `{c}` is \"{v}\" needs a filled-in `{t}`; for other records `{t}` is optional.",
                    "`{t}` may be empty only if `{c}` is not \"{v}\".",
                    "If `{c}` equals \"{v}\", an empty `{t}` is not allowed."],
    "xor": ["Exactly one of `{a}` and `{b}` must be filled in: never both, never neither.",
            "Each record fills in either `{a}` or `{b}`, but not both and not neither.",
            "Of the two fields `{a}` and `{b}`, one is filled in and the other is empty, in every record.",
            "`{a}` and `{b}` exclude each other, and one of them is always filled in."],
    "date_order": ["`{a}` is never after `{b}`; both on the same day is acceptable.",
                   "`{b}` falls on the day of `{a}` or on a later day.",
                   "No record has a `{b}` that lies before its `{a}`; the two may coincide.",
                   "`{a}` precedes `{b}` or equals it."],
    "date_strict": ["`{a}` lies strictly before `{b}`: the same day breaks the rule.",
                    "`{b}` falls at least one day after `{a}`.",
                    "No record has a `{b}` on or before its `{a}`.",
                    "`{a}` precedes `{b}`, and the two never coincide."],
    "allowed": ["`{f}` must be one of the following: {values}.",
                "No value of `{f}` other than {values} is accepted.",
                "`{f}` is restricted to this list: {values}.",
                "Accepted values of `{f}`: {values}; nothing else."],
    "derived_prod": ["`{t}` must equal `{a}` multiplied by `{b}`.",
                     "In every record, `{a}` times `{b}` gives exactly `{t}`.",
                     "`{t}` is the product of `{a}` and `{b}`; any other stored value breaks the rule.",
                     "The stored `{t}` has to match `{a}` x `{b}`."],
    "derived_sum": ["`{t}` must equal `{a}` plus `{b}`.",
                    "In every record, `{a}` and `{b}` add up to exactly `{t}`.",
                    "`{t}` is the sum of `{a}` and `{b}`; any other stored value breaks the rule.",
                    "The stored `{t}` has to match `{a}` + `{b}`."],
    "sequence": ["`{f}` rises by exactly 1 from each record to the next one in the batch; the first record may carry any number.",
                 "Going down the batch, each `{f}` is the `{f}` of the record before it plus 1 (the starting number is free).",
                 "The values of `{f}` are consecutive in batch order: no number is skipped or repeated, wherever the count starts.",
                 "Every record after the first has a `{f}` that is one higher than that of the record just before it."],
    "self_ref": ["When `{f}` is filled in, it must be the `{k}` of a record that stands earlier in the batch.",
                 "A filled-in `{f}` names the `{k}` of another record of this batch, and that record comes before the one that names it.",
                 "`{f}` may be empty; otherwise it holds a `{k}` found in one of the records above it.",
                 "Each `{f}` that is given must match the `{k}` of a preceding record of the batch."]}
INTRO2 = ["An import job checks every batch of {noun} records against the integrity rules below before it is loaded; this batch has {n} records.",
          "Below are the integrity rules for {noun} records and one batch of {n} records to be checked against them.",
          "{n} {noun} records were delivered as one batch and are validated against the numbered rules that follow.",
          "A loader validates {noun} records batch by batch; the rules it applies and the next batch ({n} records) are shown below."]
CONV2 = ["At most one rule is broken, and only in one place. A rule asks for exactly what its sentence says; whatever no listed rule covers is not a violation, however odd it looks.",
         "The batch breaks one of the rules at most, and then at a single spot. Only the listed rules are checked and each is read literally: data that looks odd but is covered by no rule does not count.",
         "No batch breaks more than one rule, and a broken rule is broken once. Judge the batch by the listed rules alone, reading each one literally; anything they do not mention is acceptable.",
         "Either every rule holds or exactly one is broken, at one spot. Nothing is a violation unless a listed rule, taken literally, forbids it."]
FIELDS2 = ["Record fields: ", "Each record has these fields: ", "Fields per record: "]
RULES_HEAD2 = ["Rules:", "Integrity rules:", "Rules to check:"]
REC_JSON2 = ["Records in batch order, one JSON object per line (a field that is missing or null is empty):",
             "The batch from first to last record, as JSON lines (an empty field is left out or set to null):",
             "Batch records in the order received, one JSON object each (null or a missing field means that the field is empty):"]
REC_TABLE2 = ["Records in batch order, one row each, cells separated by \" | \" (a cell that holds only \"-\" is empty):",
              "The batch from first to last record, as a table with \" | \" between the cells (an empty field is shown as \"-\"):",
              "Batch records in the order received, one row per record with \" | \" between cells (\"-\" alone means that the field is empty):"]

for _d in DOMAINS2:                                           # every record type offers both branches a region of their own and an overlap
    assert all(a < c <= b < e and c - a >= 2 and e - b >= 2 for a, b, c, e in _d["dep"][4]), _d["name"]
    assert len({_d["key"][0], _d["ref"][0], _d["act"][0], _d["pair"][0][0], _d["pair"][1][0], _d["seq"], *_d["der"][1:4], _d["num"][0], *_d["dep"][:2],
                *_d["enum"][:2], *_d["dates"], *_d["cond"][:2], _d["xor"][0][0], _d["xor"][1][0], _d["selfref"]}) == 21, _d["name"]      # 21 different fields


def kind_quota2(level):
    """violating items per kind in one level: 176 = 13 x 13 + 7; the seven kinds that get 14 rotate, which gives 41 (8 kinds) or 40 in all"""
    extra = {KINDS2[(7 * (level - 1) + j) % len(KINDS2)] for j in range(7)}
    return {kd: 14 if kd in extra else 13 for kd in KINDS2}


def kind_fields2(d, kind):
    return {"unique": [d["key"][0]], "reference": [d["ref"][0]], "ref_active": [d["act"][0]], "composite": [d["pair"][0][0], d["pair"][1][0]],
            "sequence": [d["seq"]], "derived": list(d["der"][1:4]), "range": [d["num"][0]], "dep_range": [d["dep"][1], d["dep"][0]],
            "allowed": [d["enum"][0]], "date_order": list(d["dates"]), "conditional": list(d["cond"][:2]),
            "xor": [d["xor"][0][0], d["xor"][1][0]], "self_ref": [d["selfref"]]}[kind]


def field_types2(d):
    t = collections.defaultdict(lambda: "text")
    for f in [d["seq"], d["num"][0], d["dep"][0]] + list(d["der"][1:4]):
        t[f] = "whole number"
    for f in d["dates"]:
        t[f] = "date, YYYY-MM-DD"
    return t


def rule_sentence2(r):
    k, v = r["kind"], r["variant"]
    if k in ("unique", "range", "sequence"):
        return RULE_TEXT2[k][v].format(f=r["field"], lo=r.get("lo"), hi=r.get("hi"))
    if k == "composite":
        return RULE_TEXT2[k][v].format(f=r["fields"][0], g=r["fields"][1])
    if k == "reference":
        return RULE_TEXT2[k][v].format(f=r["field"], L=r["list"])
    if k == "ref_active":
        return RULE_TEXT2[k][v].format(f=r["field"], L=r["list"], s=r["status"])
    if k == "dep_range":
        (v1, lo1, hi1), (v2, lo2, hi2) = r["branches"]
        return RULE_TEXT2[k][v].format(f=r["field"], b=r["by"], v1=v1, lo1=lo1, hi1=hi1, v2=v2, lo2=lo2, hi2=hi2)
    if k == "conditional":
        return RULE_TEXT2[k][v].format(c=r["if_field"], v=r["if_value"], t=r["then_field"])
    if k == "xor":
        return RULE_TEXT2[k][v].format(a=r["fields"][0], b=r["fields"][1])
    if k == "date_order":
        return RULE_TEXT2["date_strict" if r["strict"] else "date_order"][v].format(a=r["first"], b=r["second"])
    if k == "allowed":
        return RULE_TEXT2[k][v].format(f=r["field"], values=", ".join(f'"{x}"' for x in r["values"]))
    if k == "derived":
        return RULE_TEXT2["derived_" + r["op"]][v].format(a=r["a"], b=r["b"], t=r["total"])
    return RULE_TEXT2[k][v].format(f=r["field"], k=r["key"])


# ----------------------------------------------------------------------------------------------------------------
# v2: values
# ----------------------------------------------------------------------------------------------------------------
def is_near2(x, y):
    """two keys of one pattern that differ in one digit or by two neighbouring digits exchanged"""
    if x == y or len(x) != len(y) or x.rsplit("-", 1)[0] != y.rsplit("-", 1)[0]:
        return False
    diff = [i for i in range(len(x)) if x[i] != y[i]]
    return len(diff) == 1 or (len(diff) == 2 and diff[1] == diff[0] + 1 and x[diff[0]] == y[diff[1]] and x[diff[1]] == y[diff[0]])


def make_keys2(rng, prefix, digits, n, twins):
    """n different keys, `twins` of them near-identical to another one (one digit changed or two neighbouring digits exchanged)"""
    keys = []
    while len(keys) < n - twins:
        k = gen_id(rng, prefix, digits)
        if k not in keys:
            keys.append(k)
    for _ in range(twins):
        for _ in range(400):
            t = near_key(rng, rng.choice(keys))
            if t not in keys:
                keys.append(t)
                break
        else:
            raise AssertionError("no near key")
    rng.shuffle(keys)
    return keys


def transpositions2(v):
    """the numbers that arise from v when two neighbouring, different digits change places (no leading zero)"""
    s, out = str(v), []
    for i in range(len(s) - 1):
        if s[i] != s[i + 1] and not (i == 0 and s[i + 1] == "0"):
            out.append(int(s[:i] + s[i + 1] + s[i] + s[i + 2:]))
    return out


def set_cell2(spec, i, f, value):
    """fills or empties one cell after the batch was built (in the JSON layout the field is then written out, with its value or null)"""
    spec["records"][i][f] = value
    if [i, f] in spec["omitted"]:
        spec["omitted"].remove([i, f])


def tax_of2(net, rate):
    """round(net * rate / 100), half up; the batches never draw a net and a rate that end on exactly one half"""
    return (net * rate + 50) // 100


def months_after2(day, k):
    """the first day of the month that lies k months after the month of `day`"""
    m = day.year * 12 + day.month - 1 + k
    return datetime.date(m // 12, m % 12 + 1, 1)


def parent_of2(d, spec, i):
    """index of the earlier record whose key record i names in its self-reference field (None: the field is not shown, empty, or names no earlier record)"""
    f, kf, recs = d["selfref"], d["key"][0], spec["records"]
    if f not in spec["fields"] or recs[i][f] is None:
        return None
    for j in range(i):
        if recs[j][kf] == recs[i][f]:
            return j
    return None


def ref_date2(d, spec, j, new_first=None):
    """the date of the named record j that a naming record must come after: its first date, or for tickets and parcels the later of its two dates (the
    closing / delivery date; in a pair that was reversed on purpose, the later one still); `new_first` replaces the first date of record j"""
    fa, fb = d["dates"]
    first, second = new_first or spec["records"][j][fa], spec["records"][j][fb]
    first, second = (datetime.date.fromisoformat(x) if isinstance(x, str) else x for x in (first, second))
    return max(first, second) if d["name"] in REF_SECOND2 else first


def kids_stay_after2(d, spec, i, new_first=None):
    """do the records that name record i stay dated after it (record i may get the first date `new_first`)?"""
    if d["dates"][0] not in spec["fields"] or d["selfref"] not in spec["fields"]:
        return True
    recs, fa, ref = spec["records"], d["dates"][0], ref_date2(d, spec, i, new_first)
    return all(datetime.date.fromisoformat(recs[c][fa]) > ref for c in range(i + 1, spec["n"]) if parent_of2(d, spec, c) == i)


def background_breaks2(spec):
    """the relations that the background of a valid batch keeps, and where they fail: {record index: [relation]}.  total: a stored total is the
    operation on its operands; tax: the tax is round(net * tax_rate / 100) where tax_rate is shown, else at most a quarter of the net; pair: the second
    date is not before the first; ref: a record that names an earlier record is dated after it"""
    d, recs, fields, out = DOM2[spec["domain"]], spec["records"], spec["fields"], collections.defaultdict(list)
    for ru in spec["rules"] + spec["hidden"]:
        if ru["kind"] == "derived":
            for i, r in enumerate(recs):
                if r[ru["total"]] != (r[ru["a"]] * r[ru["b"]] if ru["op"] == "prod" else r[ru["a"]] + r[ru["b"]]):
                    out[i].append("total")
            if ru["b"] == "tax":
                for i, r in enumerate(recs):
                    if "tax_rate" in fields:
                        if r["tax"] != tax_of2(r["net"], r["tax_rate"]):
                            out[i].append("tax")
                    elif r["tax"] * 4 > r["net"] + 3:
                        out[i].append("tax")
    fa, fb = d["dates"]
    if fa in fields and fb in fields:
        for i, r in enumerate(recs):
            if datetime.date.fromisoformat(r[fb]) < datetime.date.fromisoformat(r[fa]):
                out[i].append("pair")
            j = parent_of2(d, spec, i)
            if j is not None and datetime.date.fromisoformat(r[fa]) <= ref_date2(d, spec, j):
                out[i].append("ref")
    return out


def stray_breaks2(spec):
    """breaks of the background outside the places where a break is wanted: the planted record and the records of the oddities may break the one relation
    of their own kind (a wrong total, a reversed date pair, a reference out of order) and no other"""
    perm = collections.defaultdict(set)
    for o in spec["oddities"]:
        perm[o["record"] - 1].add(REL_OF2.get(o["kind"]))
    if spec["planted"]:
        perm[spec["planted"]["record"] - 1].add(REL_OF2.get(spec["planted"]["kind"]))
    return [(i, rel) for i, rels in sorted(background_breaks2(spec).items()) for rel in rels if rel not in perm[i]]


def background_links2(spec):
    """the relations that hold in the background of this batch (listed in meta.background)"""
    d, fields, out = DOM2[spec["domain"]], spec["fields"], []
    for ru in spec["rules"] + spec["hidden"]:
        if ru["kind"] == "derived":
            out.append(f"{ru['total']} = {ru['a']} {'x' if ru['op'] == 'prod' else '+'} {ru['b']}")
            if ru["b"] == "tax":
                out.append("tax = round(net x tax_rate / 100)" if "tax_rate" in fields else "tax at most a quarter of net")
    fa, fb = d["dates"]
    if fa in fields and fb in fields:
        out.append(f"{fa} <= {fb}")
        if d["selfref"] in fields:
            out.append(f"{d['selfref']}: dated after the {'closing' if d['name'] in REF_SECOND2 else 'first'} date of the named record")
    return out


def make_rule2(rng, d, kind):
    """the rule of one kind for a record type (thresholds, lists, strictness and phrasing drawn); the status of a ref_active rule is set with its list"""
    r = {"kind": kind, "variant": rng.randrange(4)}
    if kind == "unique":
        r["field"] = d["key"][0]
    elif kind in ("composite", "xor"):
        r["fields"] = kind_fields2(d, kind)
        if rng.random() < 0.5:
            r["fields"].reverse()
    elif kind == "reference":
        r.update(field=d["ref"][0], list=d["ref"][1])
    elif kind == "ref_active":
        r.update(field=d["act"][0], list=d["act"][1], status=None)
    elif kind == "range":
        f, los, his = d["num"]
        r.update(field=f, lo=rng.choice(los), hi=rng.choice(his))
    elif kind == "dep_range":
        f, by, va, vb, spans = d["dep"]
        lo_a, hi_a, lo_b, hi_b = rng.choice(spans)
        r.update(field=f, by=by, branches=[[va, lo_a, hi_a], [vb, lo_b, hi_b]])
        if rng.random() < 0.5:
            r["branches"].reverse()                               # the order in which the sentence names the two branches
    elif kind == "conditional":
        r.update(if_field=d["cond"][0], if_value="yes", then_field=d["cond"][1])
    elif kind == "date_order":
        r.update(first=d["dates"][0], second=d["dates"][1], strict=rng.random() < 0.5)
    elif kind == "allowed":
        f, _, vocab = d["enum"]
        r.update(field=f, values=rng.sample(vocab, rng.choice([3, 3, 4])), vocab=vocab)
    elif kind == "derived":
        r.update(op=d["der"][0], a=d["der"][1], b=d["der"][2], total=d["der"][3])
    elif kind == "sequence":
        r["field"] = d["seq"]
    else:
        r.update(field=d["selfref"], key=d["key"][0])
    return r


# ----------------------------------------------------------------------------------------------------------------
# v2: the columns of a valid batch, each with the valid look-alikes of its rule kind
# ----------------------------------------------------------------------------------------------------------------
def fill_unique2(rng, d, spec, rule):
    f, pre, dig = d["key"]
    for r, k in zip(spec["records"], make_keys2(rng, pre, dig, spec["n"], spec["level"])):       # 1, 2 or 3 near-identical pairs of keys
        r[f] = k


def fill_reference2(rng, d, spec, rule):
    f, name, pre, dig = d["ref"]
    n, level, recs = spec["n"], spec["level"], spec["records"]
    m = rng.randint(*[(8, 10), (10, 12), (12, 15)][level - 1])
    keys = sorted(make_keys2(rng, pre, dig, m, [1, 2, 2][level - 1]))
    status, good, off = None, None, []
    if rng.random() < 0.5:                                        # a status column that this rule does not ask about
        good, others = rng.choice(STATUS2)
        off = sorted(rng.sample(keys, max(2, round(m * rng.choice([0.25, 0.35])))))
        status = [rng.choice(others) if k in off else good for k in keys]
    usable = [k for k in keys if k not in off]
    for r in recs:
        r[f] = rng.choice(usable)
    twins = [x for x in usable if any(is_near2(x, y) for y in keys)]
    if twins:
        recs[rng.randrange(n)][f] = rng.choice(twins)             # a key in use has a near-identical neighbour in the list
    if rng.random() < 0.5:
        recs[rng.randrange(n)][f] = usable[0]
        recs[rng.randrange(n)][f] = usable[-1]
    spec["lists"][name] = {"keys": keys, "status": status, "good": good}
    if status is not None and rng.random() < STATUS_ODD2:         # not a violation: the rule only asks for a key of the list (and the state says so)
        for i in rng.sample(range(n), rng.choice([1, 1, 2])):
            recs[i][f] = rng.choice(off)
            spec["oddities"].append({"kind": "list_status", "record": i + 1, "variant": "status_not_asked"})


def fill_ref_active2(rng, d, spec, rule):
    f, name, pre, dig = d["act"]
    n, level, recs = spec["n"], spec["level"], spec["records"]
    m = rng.randint(*[(7, 9), (9, 11), (11, 14)][level - 1])
    good_word, others = rng.choice(STATUS2)
    n_off = max(2, round(m * rng.choice([0.3, 0.4])))
    n_tw = [1, 1, 2][level - 1]
    good, off = make_keys2(rng, pre, dig, m - n_off, 0), []
    for want in (n_tw, n_off):                                    # first the near-identical neighbours of active keys, then other keys
        for _ in range(2000):
            if len(off) >= want:
                break
            t = near_key(rng, rng.choice(good)) if want == n_tw else gen_id(rng, pre, dig)
            if t not in good and t not in off:
                off.append(t)
    assert len(off) == n_off
    keys = sorted(good + off)
    for r in recs:
        r[f] = rng.choice(good)
    for b in off[:n_tw]:                                          # the active neighbour of an inactive key is in use
        recs[rng.randrange(n)][f] = rng.choice([g for g in good if is_near2(g, b)])
    rule["status"] = good_word
    spec["lists"][name] = {"keys": keys, "status": [good_word if k in good else rng.choice(others) for k in keys], "good": good_word}


def fill_composite2(rng, d, spec, rule):
    (f1, p1, d1), (f2, p2, d2) = d["pair"]
    a, b = rng.choice({1: [(4, 4), (4, 5), (5, 4)], 2: [(5, 5), (5, 6), (6, 5)], 3: [(6, 6), (6, 7), (7, 6)]}[spec["level"]])
    pool1, pool2 = make_keys2(rng, p1, d1, a, 1), make_keys2(rng, p2, d2, b, 1)
    cells = rng.sample([(x, y) for x in pool1 for y in pool2], spec["n"])       # all pairs differ; every single value repeats
    for r, (x, y) in zip(spec["records"], cells):
        r[f1], r[f2] = x, y


def fill_sequence2(rng, d, spec, rule):
    n, u = spec["n"], rng.random()
    if u < 0.2:
        start = 100 - rng.randint(1, n - 1)                       # the count passes from 99 to 100 inside the batch
    elif u < 0.35:
        start = 10 - rng.randint(1, min(8, n - 1))                # ... from 9 to 10
    elif u < 0.7:
        start = rng.randint(11, 70)
    else:
        start = rng.randint(101, 880)
    for i, r in enumerate(spec["records"]):                       # never starts at 1
        r[d["seq"]] = start + i


def fill_derived2(rng, d, spec, rule):
    op, a, b, t, (alo, ahi), (blo, bhi) = d["der"]
    rated = b == "tax" and "tax_rate" in spec["fields"]           # invoice lines: the tax is the net times the rate of the record (the rate is filled before)
    rates = rng.sample(TAX_RATES2, 2) if b == "tax" else None     # without a rate field the batch still has plausible taxes: one of two usual rates
    for r in spec["records"]:
        x, y = rng.randint(alo, ahi), rng.randint(blo, bhi)
        if b == "tax":
            rate = r["tax_rate"] if rated else rng.choice(rates)
            while (x * rate) % 100 == 50:                         # no tie between two roundings
                x = rng.randint(alo, ahi)
            y = tax_of2(x, rate)
        r[a], r[b], r[t] = x, y, (x * y if op == "prod" else x + y)


def fill_range2(rng, d, spec, rule):
    f, lo, hi, n = rule["field"], rule["lo"], rule["hi"], spec["n"]
    vals = [rng.choice([lo, lo + 1, hi - 1, hi]) if rng.random() < 0.25 else rng.randint(lo, hi) for _ in range(n)]
    i, j = rng.sample(range(n), 2)
    vals[i] = hi                                                  # exactly on a limit
    if spec["level"] >= 2 or rng.random() < 0.5:
        vals[j] = lo
    if f == "tax_rate":                                           # a rate of 0 stays possible, but a batch of mostly untaxed lines would look odd
        for x in [x for x in range(n) if vals[x] == lo][2:]:
            vals[x] = rng.randint(lo + 1, hi)
    for r, v in zip(spec["records"], vals):
        r[f] = v


def fill_dep_range2(rng, d, spec, rule):
    f, by, n, recs = rule["field"], rule["by"], spec["n"], spec["records"]
    (va, lo_a, hi_a), (vb, lo_b, hi_b) = sorted(rule["branches"], key=lambda x: x[1])
    idx = list(range(n))
    rng.shuffle(idx)
    cut = rng.randint(n // 2 - 1, n // 2 + 1)
    low, high = idx[:cut], idx[cut:]
    for i in low:                                                 # half of the values are legal under their own branch only
        recs[i][by], recs[i][f] = va, (rng.randint(lo_a, lo_b - 1) if rng.random() < 0.5 else rng.randint(lo_b, hi_a))
    for i in high:
        recs[i][by], recs[i][f] = vb, (rng.randint(hi_a + 1, hi_b) if rng.random() < 0.5 else rng.randint(lo_b, hi_a))
    recs[low[0]][f], recs[low[1]][f] = hi_a, rng.randint(lo_a, lo_b - 1)        # on the limit of its branch; outside the other branch
    recs[high[0]][f], recs[high[1]][f] = lo_b, rng.randint(hi_a + 1, hi_b)


def fill_allowed2(rng, d, spec, rule):
    f, sib, vocab = d["enum"]
    n, values, recs = spec["n"], rule["values"], spec["records"]
    single = rng.choice(values)                                   # an allowed value that occurs once only
    col = [rng.choice([v for v in values if v != single]) for _ in range(n)]
    col[rng.randrange(n)] = single
    for r, v in zip(recs, col):
        r[f] = v
    if sib in spec["fields"]:                                     # the sibling field has no rule: words outside the list are fine there
        col = [rng.choice(vocab) for _ in range(n)]
        for i in rng.sample(range(n), 2):
            col[i] = rng.choice([v for v in vocab if v not in values])
        for r, v in zip(recs, col):
            r[sib] = v


def fill_date_order2(rng, d, spec, rule):
    """the date pairs, record by record in batch order: a record that names an earlier record (the references are filled first) is dated after it,
    so the references never run backwards in time; the pair on the limit of the rule and the pair across a month end are kept"""
    (fa, fb), strict, n = d["dates"], rule["strict"], spec["n"]
    day = datetime.timedelta
    gaps = [1, 1, 2, 3, 5, 8, 13, 21, 34] if strict else [0, 0, 1, 2, 3, 5, 8, 13, 21, 34]
    lags = [0, 0, 1, 2, 4, 7, 12, 20, 33, 54]                     # days between the earliest allowed date of a naming record and its date
    par = [parent_of2(d, spec, k) for k in range(n)]
    i, j = rng.sample(range(n), 2)
    month_row = spec["level"] >= 2 or rng.random() < 0.6
    rows = [None] * n
    for k in range(n):
        lo = None                                                 # earliest first date of this record
        if par[k] is not None:
            pa, pb = rows[par[k]]
            lo = (pb if d["name"] in REF_SECOND2 else pa) + day(days=1)
        if k == j and month_row:                                  # across a month end: the later date has the smaller day number
            if lo is None:
                m = 8 + rng.randrange(15)
                first = datetime.date(2025 + (m + 1) // 12, (m + 1) % 12 + 1, 1)
            else:                                                 # the first of a month at least four days after `lo`, so that the earlier date stays after it
                edge = lo + day(days=4)
                first = months_after2(edge, 1 if edge.day > 1 else 0)
                first = months_after2(first, rng.randrange(4))
            rows[k] = (first - day(days=rng.randint(1, 4)), first + day(days=rng.randint(0, 6)))
            continue
        a = DATE2 + day(days=rng.randrange(0, 480)) if lo is None else lo + day(days=rng.choice(lags))
        rows[k] = (a, a + day(days=(1 if strict else 0) if k == i else rng.choice(gaps)))     # k == i: on the limit of the rule
    for r, (a, b) in zip(spec["records"], rows):
        r[fa], r[fb] = iso(a), iso(b)


def fill_conditional2(rng, d, spec, rule):
    (c, t, kind), n, recs = d["cond"], spec["n"], spec["records"]
    yes = set(rng.sample(range(n), max(2, round(n * 0.35))))
    for i, r in enumerate(recs):
        r[c] = "yes" if i in yes else "no"
        if i in yes or rng.random() < 0.3:
            r[t] = person(rng) if kind == "person" else f"{kind[5:]}-{rng.randrange(100, 1000)}"
        else:
            r[t] = None
    for i in rng.sample([i for i in range(n) if i not in yes], 2):                               # empty where nothing asks for it
        recs[i][t] = None


def fill_xor2(rng, d, spec, rule):
    ((fa, pa, da), (fb, pb, db)), n = d["xor"], spec["n"]
    first = set(rng.sample(range(n), rng.randint(n // 2 - 1, n // 2 + 1)))
    for i, r in enumerate(spec["records"]):
        r[fa], r[fb] = (gen_id(rng, pa, da), None) if i in first else (None, gen_id(rng, pb, db))


def fill_self_ref2(rng, d, spec, rule):
    f, kf, n, recs = d["selfref"], d["key"][0], spec["n"], spec["records"]
    keys, vals = [r[kf] for r in recs], [None] * n
    for i in range(1, n):
        if rng.random() < 0.4:
            vals[i] = keys[i - 1] if rng.random() < 0.3 else keys[rng.randrange(i)]
    i = rng.randrange(1, n)
    vals[i] = keys[i - 1]                                         # the record just before: as late as an earlier record can be
    for a in range(n):                                            # an earlier key is named although its near-identical neighbour comes later
        for b in range(a + 2, n):
            if is_near2(keys[a], keys[b]) and rng.random() < 0.7:
                vals[rng.randrange(a + 1, b)] = keys[a]
    while sum(v is not None for v in vals) < [3, 5, 7][spec["level"] - 1]:
        i = rng.randrange(1, n)
        vals[i] = keys[rng.randrange(i)]
    for r, v in zip(recs, vals):
        r[f] = v


FILL2 = {"unique": fill_unique2, "reference": fill_reference2, "ref_active": fill_ref_active2, "composite": fill_composite2,
         "sequence": fill_sequence2, "derived": fill_derived2, "range": fill_range2, "dep_range": fill_dep_range2, "allowed": fill_allowed2,
         "date_order": fill_date_order2, "conditional": fill_conditional2, "xor": fill_xor2, "self_ref": fill_self_ref2}


def make_base2(rng, plan):
    """a valid batch for one plan: the listed rules, up to two unlisted kinds whose fields are shown as well (room for oddities that no
    rule covers), the reference lists, the records with the look-alikes of every kind, and the oddities"""
    d = DOM2[plan["domain"]]
    n, level, listed = plan["n"], plan["level"], plan["kinds"]
    room = FIELD_CAP2 - 1 - sum(len(kind_fields2(d, kd)) for kd in listed if kd != "unique")
    pool = [kd for kd in ODDITY_KINDS2 if kd not in listed and kd != "unique"]
    rng.shuffle(pool)
    extras = []
    for kd in pool:
        if len(extras) < 2 and len(kind_fields2(d, kd)) <= room:
            extras.append(kd)
            room -= len(kind_fields2(d, kd))
    sibling = "allowed" in listed and room >= 1 and rng.random() < 0.7
    present = sorted(set(listed) | set(extras) | {"unique"}, key=KINDS2.index)
    rules = {kd: make_rule2(rng, d, kd) for kd in present}
    fields = [f for kd in present if kd != "unique" for f in kind_fields2(d, kd)] + ([d["enum"][1]] if sibling else [])
    rng.shuffle(fields)
    fields = [d["key"][0]] + fields
    spec = {"version": "v2", "domain": d["name"], "level": level, "n": n, "layout": plan["layout"], "list_format": plan["list_format"],
            "fields": fields, "rules": [rules[kd] for kd in listed], "hidden": [rules[kd] for kd in present if kd not in listed],
            "lists": {}, "records": [dict() for _ in range(n)], "omitted": [],
            "phrasing": {"intro": rng.randrange(4), "conv": rng.randrange(4), "fields": rng.randrange(3), "rules": rng.randrange(3),
                         "records": rng.randrange(3), "status": rng.randrange(len(STATUS_NOTE2))},
            "oddities": [], "planted": None}
    for kd in sorted(present, key=FILL_ORDER2.index):
        FILL2[kd](rng, d, spec, rules[kd])
    spec["records"] = [{f: r[f] for f in fields} for r in spec["records"]]
    if spec["layout"] == "json":
        spec["omitted"] = [[i, f] for i, r in enumerate(spec["records"]) for f in fields if r[f] is None and rng.random() < 0.5]
    hidden = [kd for kd in present if kd not in listed and kd in ODDITY_KINDS2]
    rng.shuffle(hidden)
    taken = [o["record"] - 1 for o in spec["oddities"]]
    for kd in hidden:                                             # something odd under a kind that this schema does not list: no violation
        if len(spec["oddities"]) >= 2 or rng.random() >= ODDITY_RATE2:
            continue
        info = plant2(rng, spec, rules[kd], taken)
        if info is not None:
            spec["oddities"].append({"kind": kd, "record": info["record"], "variant": info["variant"]})
            taken += info["touched"]
    return spec


# ----------------------------------------------------------------------------------------------------------------
# v2: truth on the structured records, look-alikes, planting
# ----------------------------------------------------------------------------------------------------------------
def places2(rule, spec):
    """the places where the batch breaks the rule: records (0-based), pairs of records, or the later record of a broken step"""
    recs, lists, k = spec["records"], spec["lists"], rule["kind"]
    n, f = len(recs), rule.get("field")
    if k == "unique":
        return [(i, j) for i in range(n) for j in range(i + 1, n) if recs[i][f] == recs[j][f]]
    if k == "composite":
        f, g = rule["fields"]
        return [(i, j) for i in range(n) for j in range(i + 1, n) if recs[i][f] == recs[j][f] and recs[i][g] == recs[j][g]]
    if k == "reference":
        return [i for i in range(n) if recs[i][f] not in lists[rule["list"]]["keys"]]
    if k == "ref_active":
        L = lists[rule["list"]]
        live = {key for key, s in zip(L["keys"], L["status"]) if s == rule["status"]}
        return [i for i in range(n) if recs[i][f] not in live]
    if k == "range":
        return [i for i in range(n) if not rule["lo"] <= recs[i][f] <= rule["hi"]]
    if k == "dep_range":
        span = {v: (lo, hi) for v, lo, hi in rule["branches"]}
        return [i for i in range(n) if not span[recs[i][rule["by"]]][0] <= recs[i][f] <= span[recs[i][rule["by"]]][1]]
    if k == "conditional":
        return [i for i in range(n) if recs[i][rule["if_field"]] == rule["if_value"] and recs[i][rule["then_field"]] is None]
    if k == "xor":
        a, b = rule["fields"]
        return [i for i in range(n) if (recs[i][a] is None) == (recs[i][b] is None)]
    if k == "date_order":
        out = []
        for i, r in enumerate(recs):
            a, b = datetime.date.fromisoformat(r[rule["first"]]), datetime.date.fromisoformat(r[rule["second"]])
            if (a >= b) if rule["strict"] else (a > b):
                out.append(i)
        return out
    if k == "allowed":
        return [i for i in range(n) if recs[i][f] not in rule["values"]]
    if k == "derived":
        return [i for i, r in enumerate(recs)
                if r[rule["total"]] != (r[rule["a"]] * r[rule["b"]] if rule["op"] == "prod" else r[rule["a"]] + r[rule["b"]])]
    if k == "sequence":
        return [i for i in range(1, n) if recs[i][f] - recs[i - 1][f] != 1]
    return [i for i in range(n) if recs[i][f] is not None and not any(recs[j][rule["key"]] == recs[i][f] for j in range(i))]


def truth2(spec):
    """key of the rule that the batch breaks, or none; a broken rule is broken in exactly one place"""
    hit = [(j, p) for j, p in ((j, places2(r, spec)) for j, r in enumerate(spec["rules"], 1)) if p]
    assert len(hit) <= 1 and all(len(p) == 1 for _, p in hit), hit
    return f"R{hit[0][0]}" if hit else "none"


def lookalike2(rule, spec):
    """does the batch hold a VALID look-alike of the rule: a record on its limit, or one that a sloppy reading takes for a violation"""
    d, recs, lists, k = DOM2[spec["domain"]], spec["records"], spec["lists"], rule["kind"]
    n, f = len(recs), rule.get("field")
    if k == "unique":                                             # near-identical keys
        return any(is_near2(recs[i][f], recs[j][f]) for i in range(n) for j in range(i + 1, n))
    if k == "composite":                                          # records that share one of the two fields
        f, g = rule["fields"]
        one = [(recs[i][f] == recs[j][f], recs[i][g] == recs[j][g]) for i in range(n) for j in range(i + 1, n)]
        return (True, False) in one and (False, True) in one
    if k == "reference":                                          # a key in use with a near-identical neighbour in the list
        return any(is_near2(r[f], x) for r in recs for x in lists[rule["list"]]["keys"])
    if k == "ref_active":                                         # the active neighbour of an inactive key is in use; unused inactive keys
        L = lists[rule["list"]]
        off = [key for key, s in zip(L["keys"], L["status"]) if s != rule["status"]]
        return any(is_near2(r[f], x) for r in recs for x in off) and any(all(r[f] != x for r in recs) for x in off)
    if k == "range":                                              # a value exactly on a limit
        return any(r[f] in (rule["lo"], rule["hi"]) for r in recs)
    if k == "dep_range":                                          # a value on a limit of its branch; a value that the other branch forbids
        (va, lo_a, hi_a), (vb, lo_b, hi_b) = sorted(rule["branches"], key=lambda x: x[1])
        by = rule["by"]
        edge = any((r[by] == va and r[f] == hi_a) or (r[by] == vb and r[f] == lo_b) for r in recs)
        return edge and any(r[by] == va and r[f] < lo_b for r in recs) and any(r[by] == vb and r[f] > hi_a for r in recs)
    if k == "conditional":                                        # an empty field on a record that does not need it
        return any(r[rule["if_field"]] != rule["if_value"] and r[rule["then_field"]] is None for r in recs)
    if k == "xor":                                                # both ways of filling exactly one field
        a, b = rule["fields"]
        return any(r[a] is not None and r[b] is None for r in recs) and any(r[a] is None and r[b] is not None for r in recs)
    if k == "date_order":                                         # the same day (allowed) or exactly one day apart (strict rule)
        gap = [(datetime.date.fromisoformat(r[rule["second"]]) - datetime.date.fromisoformat(r[rule["first"]])).days for r in recs]
        return (1 if rule["strict"] else 0) in gap
    if k == "allowed":                                            # an allowed value that occurs once only
        count = collections.Counter(r[f] for r in recs)
        return any(count[v] == 1 for v in rule["values"])
    if k == "derived":                                            # every record needs the computation; there is no limit to sit on
        return True
    if k == "sequence":                                           # the count does not start at 1
        return recs[0][f] != 1
    return any(recs[i][f] == recs[i - 1][rule["key"]] for i in range(1, n))        # the record just before is named


def plant2(rng, spec, rule, avoid=()):
    """one near-miss violation of `rule` in the batch (for a listed rule: the violation; for a hidden rule: an oddity that no listed rule
    covers).  Returns the record (1-based), the variant and the records touched, or None when the batch offers no place for it"""
    d, recs, kind = DOM2[spec["domain"]], spec["records"], rule["kind"]
    n, f = len(recs), rule.get("field")
    ok = [i for i in range(n) if i not in avoid]
    if kind == "unique":                                          # the key of another record, not a neighbour; keys that a record names stay unique
        named = {r[d["selfref"]] for r in recs} if d["selfref"] in spec["fields"] else set()
        free = [i for i in ok if recs[i][f] not in named]
        pairs = [(i, j) for i in free for j in free if abs(i - j) >= 2]
        if not pairs:
            return None
        i, j = rng.choice(pairs)
        recs[i][f] = recs[j][f]
        return {"record": i + 1, "variant": "duplicate", "touched": [i, j]}
    if kind == "composite":                                       # two records that shared one field now share both
        f, g = rule["fields"]
        cand = [(i, j, g if recs[i][f] == recs[j][f] else f) for i in ok for j in range(n)
                if j != i and j not in avoid and (recs[i][f] == recs[j][f]) != (recs[i][g] == recs[j][g])]
        if not cand:
            return None
        i, j, change = rng.choice(cand)
        recs[i][change] = recs[j][change]
        return {"record": i + 1, "variant": "pair_repeated", "touched": [i, j]}
    if kind == "reference":                                       # one digit changed or two digits exchanged: not in the list
        keys, i = spec["lists"][rule["list"]]["keys"], rng.choice(ok)
        for _ in range(400):
            bad = near_key(rng, recs[i][f] if rng.random() < 0.5 else rng.choice(keys))
            if bad not in keys:
                recs[i][f] = bad
                return {"record": i + 1, "variant": "key_one_off", "touched": [i]}
        return None
    if kind == "ref_active":                                      # a key that is in the list but not with the required status
        L = spec["lists"][rule["list"]]
        off = [key for key, s in zip(L["keys"], L["status"]) if s != rule["status"]]
        twin = [(i, x) for i in ok for x in off if is_near2(recs[i][f], x)]
        i, x = rng.choice(twin) if twin and rng.random() < 0.6 else (rng.choice(ok), rng.choice(off))
        variant = "inactive_neighbour" if is_near2(recs[i][f], x) else "inactive_key"
        recs[i][f] = x
        return {"record": i + 1, "variant": variant, "touched": [i]}
    if kind == "range":                                           # one step outside
        up = rule["lo"] == 0 or rng.random() < 0.55
        new = rule["hi"] + 1 if up else rule["lo"] - 1
        taxed = f == "tax_rate" and "net" in spec["fields"] and "tax" in spec["fields"]
        i = rng.choice([x for x in ok if not (taxed and (recs[x]["net"] * new) % 100 == 50)] or ok)
        recs[i][f] = new
        if taxed:                                                 # the tax and the gross follow the rate: the record breaks the range and nothing else
            recs[i]["tax"] = tax_of2(recs[i]["net"], new)
            if "gross" in spec["fields"]:
                recs[i]["gross"] = recs[i]["net"] + recs[i]["tax"]
        return {"record": i + 1, "variant": "one_above" if up else "one_below", "touched": [i]}
    if kind == "dep_range":                                       # a value that only the other branch allows
        (va, lo_a, hi_a), (vb, lo_b, hi_b) = sorted(rule["branches"], key=lambda x: x[1])
        by, mode = rule["by"], rng.choice(["one_step", "one_step", "inside_other", "branch_changed"])
        if mode == "branch_changed":
            cand = [i for i in ok if (recs[i][by] == va and recs[i][f] < lo_b) or (recs[i][by] == vb and recs[i][f] > hi_a)]
            if not cand:
                return None
            i = rng.choice(cand)
            recs[i][by] = vb if recs[i][by] == va else va
        else:
            i = rng.choice(ok)
            if recs[i][by] == va:
                recs[i][f] = hi_a + 1 if mode == "one_step" else rng.randint(hi_a + 2, hi_b)
            else:
                recs[i][f] = lo_b - 1 if mode == "one_step" else rng.randint(lo_a, lo_b - 2)
        return {"record": i + 1, "variant": mode, "touched": [i]}
    if kind == "conditional":                                     # the required field emptied, or the trigger set on a record without it
        c, v, t = rule["if_field"], rule["if_value"], rule["then_field"]
        need = [i for i in ok if recs[i][c] == v and recs[i][t] is not None]
        idle = [i for i in ok if recs[i][c] != v and recs[i][t] is None]
        if idle and (not need or rng.random() < 0.5):
            i = rng.choice(idle)
            recs[i][c] = v
            return {"record": i + 1, "variant": "trigger_set", "touched": [i]}
        if not need:
            return None
        i = rng.choice(need)
        set_cell2(spec, i, t, None)
        return {"record": i + 1, "variant": "field_emptied", "touched": [i]}
    if kind == "xor":                                             # both fields filled, or neither
        (fa, pa, da), (fb, pb, db) = d["xor"]
        if rng.random() < 0.5:                                    # (a field that the JSON layout writes as null is preferred: the line keeps its fields)
            shown = [i for i in ok if not any(c[0] == i and c[1] in (fa, fb) for c in spec["omitted"])]
            i = rng.choice(shown or ok)
            fx, px, dx = (fa, pa, da) if recs[i][fa] is None else (fb, pb, db)
            set_cell2(spec, i, fx, gen_id(rng, px, dx))
            return {"record": i + 1, "variant": "both_filled", "touched": [i]}
        i = rng.choice(ok)
        set_cell2(spec, i, fa if recs[i][fa] is not None else fb, None)
        return {"record": i + 1, "variant": "both_empty", "touched": [i]}
    if kind == "date_order":                                      # the same day under a strict rule, or the later date a day or a few days early
        a, b, i = rule["first"], rule["second"], rng.choice(ok)
        if rule["strict"] and rng.random() < 0.5:
            back, variant = 0, "same_day"
        else:
            back = rng.choice([1, 1, 1, 2, 3])
            variant = "one_day_early" if back == 1 else "few_days_early"
        late = datetime.date.fromisoformat(recs[i][b]) + datetime.timedelta(days=back)      # the first date moved behind the second
        if rng.random() < 0.5 or not kids_stay_after2(d, spec, i, late):       # (not when a record that names this one would then come first)
            recs[i][b] = iso(datetime.date.fromisoformat(recs[i][a]) - datetime.timedelta(days=back))
        else:
            recs[i][a] = iso(late)
        return {"record": i + 1, "variant": variant, "touched": [i]}
    if kind == "allowed":                                         # a word of the same vocabulary that is not on the list
        sib, count = d["enum"][1], collections.Counter(r[f] for r in recs)
        cand = [i for i in ok if count[recs[i][f]] > 1]
        out = [x for x in rule["vocab"] if x not in rule["values"]]
        seen = [x for x in out if sib in spec["fields"] and any(r[sib] == x for r in recs)]
        if not cand:
            return None
        i = rng.choice(cand)
        recs[i][f] = rng.choice(seen or out)
        return {"record": i + 1, "variant": "word_of_sibling_field" if seen else "word_not_listed", "touched": [i]}
    if kind == "derived":                                         # two digits of the total exchanged, or the total off by 1, 2 or 10
        t = rule["total"]
        swaps = [(i, x) for i in ok for x in transpositions2(recs[i][t])]
        if swaps and rng.random() < 0.5:
            i, x = rng.choice(swaps)
            recs[i][t] = x
            return {"record": i + 1, "variant": "digits_exchanged", "touched": [i]}
        i = rng.choice(ok)
        delta = rng.choice([x for x in (-10, -2, -1, 1, 2, 10) if recs[i][t] + x > 0])
        recs[i][t] += delta
        return {"record": i + 1, "variant": f"off_by_{abs(delta)}", "touched": [i]}
    if kind == "sequence":                                        # one number skipped or repeated between record p and record p + 1
        p, variant = rng.randrange(1, n), rng.choice(["number_skipped", "number_repeated"])
        s = 1 if variant == "number_skipped" else -1
        if p >= n - p:
            for i in range(p, n):
                recs[i][f] += s
        else:
            for i in range(p):
                recs[i][f] -= s
        return {"record": p + 1, "variant": variant, "touched": [p - 1, p]}
    kf, filled = rule["key"], [i for i in ok if recs[i][f] is not None]                          # self_ref
    if rng.random() < 0.7:                                        # the key of a record further down (not also the key of an earlier one)
        cand = [(i, j) for i in filled for j in range(i + 1, n) if not any(recs[x][kf] == recs[j][kf] for x in range(i))]
        if not cand:
            return None
        if d["dates"][0] in spec["fields"]:                       # the dates stay in order as well: the naming record is dated after the named one, which only stands further down
            good = [(i, j) for i, j in cand if datetime.date.fromisoformat(recs[i][d["dates"][0]]) > ref_date2(d, spec, j)]
            cand = good or cand
        nxt = [c for c in cand if c[1] == c[0] + 1]
        i, j = rng.choice(nxt) if nxt and rng.random() < 0.4 else rng.choice(cand)
        recs[i][f] = recs[j][kf]
        return {"record": i + 1, "variant": "later_record", "touched": [i, j]}
    if not filled:
        return None
    i, keys = rng.choice(filled), {r[kf] for r in recs}
    for _ in range(400):                                          # one digit of the named key changed: no record has it
        bad = near_key(rng, recs[i][f])
        if bad not in keys:
            recs[i][f] = bad
            return {"record": i + 1, "variant": "key_one_off", "touched": [i]}
    return None


# ----------------------------------------------------------------------------------------------------------------
# v2: rendering (two layouts of the records, two formats of the lists) and the read-back of the data block
# ----------------------------------------------------------------------------------------------------------------
def render_list2(name, L, fmt):
    keys = L["keys"]
    if L["status"] is None:
        if fmt == "inline":
            return [f"Reference list `{name}` with {len(keys)} keys: " + ", ".join(keys)]
        return [f"Reference list `{name}` with {len(keys)} keys, one per line:"] + keys
    entries = [f"{k}: {s}" for k, s in zip(keys, L["status"])]
    if fmt == "inline":
        return [f"Reference list `{name}` with {len(keys)} entries (key: status): " + "; ".join(entries)]
    return [f"Reference list `{name}` with {len(keys)} entries, one per line (key: status):"] + entries


def has_status2(spec):
    """does the state show a reference list with a status column (then it also says what a status counts for)?"""
    return any(spec["lists"][r["list"]]["status"] is not None for r in spec["rules"] if "list" in r)


def render_state2(spec):
    d, ph, types = DOM2[spec["domain"]], spec["phrasing"], field_types2(DOM2[spec["domain"]])
    out = [INTRO2[ph["intro"]].format(n=spec["n"], noun=d["noun"]) + " " + CONV2[ph["conv"]], "",
           FIELDS2[ph["fields"]] + ", ".join(f"{f} ({types[f]})" for f in spec["fields"]) + ".", "", RULES_HEAD2[ph["rules"]]]
    out += [f"R{i}. " + rule_sentence2(r) for i, r in enumerate(spec["rules"], 1)]
    for r in spec["rules"]:                                       # the lists in the order of the rules that use them
        if "list" in r:
            out += [""] + render_list2(r["list"], spec["lists"][r["list"]], spec["list_format"])
    if has_status2(spec):                                         # the convention for the status column, written out
        out += ["", STATUS_NOTE2[ph["status"]]]
    out.append("")
    if spec["layout"] == "json":
        gone = {(i, f) for i, f in spec["omitted"]}
        out.append(REC_JSON2[ph["records"]])
        out += [json.dumps({f: r[f] for f in spec["fields"] if (i, f) not in gone}) for i, r in enumerate(spec["records"])]
    else:
        out.append(REC_TABLE2[ph["records"]])
        out.append(" | ".join(spec["fields"]))
        out += [" | ".join("-" if r[f] is None else str(r[f]) for f in spec["fields"]) for r in spec["records"]]
    return "\n".join(out)


def reread2(state, spec):
    """fidelity of the rendering: the records and the lists read back from the text equal the specification (this is no solver of the rules)"""
    blocks = state.split("\n\n")
    data = blocks[-1].split("\n")
    if spec["layout"] == "json":
        rows = [json.loads(line) for line in data[1:]]
        assert [{f: row.get(f) for f in spec["fields"]} for row in rows] == spec["records"], "records"
        assert all(list(row) == [f for f in spec["fields"] if f in row] for row in rows)
        assert sorted([i, f] for i, row in enumerate(rows) for f in spec["fields"] if f not in row) == sorted(spec["omitted"]), "omitted"
    else:
        assert data[1].split(" | ") == spec["fields"] and not spec["omitted"]
        assert [line.split(" | ") for line in data[2:]] == [["-" if r[f] is None else str(r[f]) for f in spec["fields"]] for r in spec["records"]], "rows"
    assert all(spec["records"][i][f] is None for i, f in spec["omitted"]), "only empty fields are left out"
    shown, lists = {}, blocks[3:-1]
    if has_status2(spec):                                         # the status convention stands after the last list, in the phrasing drawn for the batch
        assert lists[-1] == STATUS_NOTE2[spec["phrasing"]["status"]], "status note"
        lists = lists[:-1]
    else:
        assert not any(b in STATUS_NOTE2 for b in lists), "status note without a status column"
    for b in lists:
        lines = b.split("\n")
        m = re.match(r"^Reference list `(\w+)` with (\d+) (?:keys|entries)(?:, one per line)?(?: \(key: status\))?:(?: (.*))?$", lines[0])
        entries = lines[1:] if m.group(3) is None else re.split(r", |; ", m.group(3))
        assert int(m.group(2)) == len(entries), lines[0]
        shown[m.group(1)] = entries
    want = {r["list"]: spec["lists"][r["list"]] for r in spec["rules"] if "list" in r}
    assert shown == {nm: (L["keys"] if L["status"] is None else [f"{k}: {s}" for k, s in zip(L["keys"], L["status"])]) for nm, L in want.items()}, shown
    assert set(spec["lists"]) == set(want)


# ----------------------------------------------------------------------------------------------------------------
# v2: the plan (150 batches), the batches that also give the none item, the violated kinds, the order of the rules and options
# ----------------------------------------------------------------------------------------------------------------
def plan2():
    """150 batch plans, 50 per level.  A level has 6 or 7 batches in each cell (number of rules, layout), 6 or 7 per record type and 25 per
    list format.  The share of the new kinds in a schema is 7 / 13 on average for every number of rules (3 or 4 new kinds of 6 or 7 rules,
    4 or 5 of 8 or 9), and the kinds are taken least-used-first, so that every kind is listed in the same number of batches"""
    rng = sub("v2/plan")
    seven = {1: [(6, "json"), (7, "table")], 2: [(8, "json"), (9, "table")], 3: [(6, "table"), (8, "json")]}
    names, plans = [d["name"] for d in DOMAINS2], []
    for level in (1, 2, 3):
        cells = [(k, lay) for k in K2 for lay in LAYOUTS2 for _ in range(7 if (k, lay) in seven[level] else 6)]
        doms = names * 6 + names[2 * (level - 1): 2 * level]
        fmts = LIST_FORMATS2 * (BASES2 // 2)
        assert len(cells) == len(doms) == len(fmts) == BASES2
        rng.shuffle(doms)
        rng.shuffle(fmts)
        plans += [{"level": level, "n": N2[level], "k": k, "layout": lay, "list_format": fm, "domain": dn}
                  for (k, lay), dn, fm in zip(cells, doms, fmts)]
    more = {6: 9, 7: 28, 8: 12, 9: 31}                            # batches with the larger number of new kinds, per number of rules
    for k in K2:
        idx = [i for i, p in enumerate(plans) if p["k"] == k]
        low = 3 if k <= 7 else 4
        nn = [low + 1] * more[k] + [low] * (len(idx) - more[k])
        rng.shuffle(nn)
        for i, x in zip(idx, nn):
            plans[i]["new_kinds"] = x
    in_level, total = collections.Counter(), collections.Counter()
    order = list(range(len(plans)))
    rng.shuffle(order)
    for i in order:
        p = plans[i]
        kinds = []
        for pool, m in ((KINDS_NEW, p["new_kinds"]), (KINDS, p["k"] - p["new_kinds"])):
            kinds += sorted(pool, key=lambda kd: (in_level[(p["level"], kd)], total[kd], rng.random()))[:m]
        for kd in kinds:
            in_level[(p["level"], kd)] += 1
            total[kd] += 1
        p["kinds"] = sorted(kinds, key=KINDS2.index)
    return plans


def build_base2(i, plan):
    for attempt in range(400):
        spec = make_base2(random.Random(f"{SEED}/v2/batch/{i}/{attempt}"), plan)
        assert not any(places2(r, spec) for r in spec["rules"]), (i, attempt)       # valid under its listed rules, oddities included
        if all(lookalike2(r, spec) for r in spec["rules"]) and not stray_breaks2(spec):    # with a valid look-alike of every listed rule; consistent background
            if all(plant_violation2(i, spec, r["kind"]) is not None for r in spec["rules"]):   # and room for the violation of every listed rule (the draws of the final items)
                return spec
    raise RuntimeError(f"no batch for plan {i}")


def host_band2(m, c):
    """host counts h of a word found in m batches for which its rate among the none items, (h / 72), and among the violating items,
    ((4 m - h) / 528), differ by a factor c at most"""
    return 4 * m * N_NONE2 / (c * N_VIOL2 + N_NONE2), 4 * c * m * N_NONE2 / (N_VIOL2 + c * N_NONE2)


def choose_hosts2(plans, bases):
    """the batches that also give the none item (hosts): 3 per cell (level, number of rules, layout), so 24 per level and 18 per number of
    rules.  Inside the cells hosts and non-hosts are exchanged until no word that stands in 4 or more batches is more than 1.6 times as
    frequent among the none items as among the violating items or the reverse (the test of the final items allows a factor 2), and until
    every record type has 3 hosts per level where that can be had as well"""
    rng = sub("v2/hosts")
    words = [sorted(set(re.findall(r"[a-z]+", render_state2(b).lower()))) for b in bases]
    df = collections.Counter(w for ws in words for w in ws)
    toks = sorted(w for w, c in df.items() if c >= 4)
    tid = {w: j for j, w in enumerate(toks)}
    vec = [[tid[w] for w in ws if w in tid] for ws in words]
    band = [host_band2(df[w], 1.6) for w in toks]
    cells = collections.defaultdict(list)
    for i, p in enumerate(plans):
        cells[(p["level"], p["k"], p["layout"])].append(i)
    keys = sorted(cells)
    host = set()
    for key in keys:
        host |= set(rng.sample(cells[key], 3))
    cnt = [0] * len(toks)
    for i in sorted(host):
        for t in vec[i]:
            cnt[t] += 1
    dom = collections.Counter((plans[i]["level"], plans[i]["domain"]) for i in host)

    def pen(t, c):
        return max(0.0, band[t][0] - c) ** 2 + max(0.0, c - band[t][1]) ** 2

    def dpen(c):
        return 0.05 * (c - 3) ** 2
    vocab = sum(pen(t, cnt[t]) for t in range(len(toks)))
    spread = sum(dpen(dom[(lv, d["name"])]) for lv in (1, 2, 3) for d in DOMAINS2)
    start = vocab
    for step in range(40000):
        if vocab < 1e-9 and (spread < 1e-9 or step >= 6000):
            break
        key = rng.choice(keys)
        a = rng.choice([i for i in cells[key] if i in host])
        b = rng.choice([i for i in cells[key] if i not in host])
        delta = collections.Counter()
        for t in vec[a]:
            delta[t] -= 1
        for t in vec[b]:
            delta[t] += 1
        gv = sum(pen(t, cnt[t] + x) - pen(t, cnt[t]) for t, x in delta.items() if x)
        da, db = (plans[a]["level"], plans[a]["domain"]), (plans[b]["level"], plans[b]["domain"])
        gs = 0.0 if da == db else dpen(dom[da] - 1) + dpen(dom[db] + 1) - dpen(dom[da]) - dpen(dom[db])
        if gv + gs < -1e-12:
            for t, x in delta.items():
                cnt[t] += x
            host.remove(a)
            host.add(b)
            dom[da] -= 1
            dom[db] += 1
            vocab += gv
            spread += gs
    print(f"hosts of the none items: {len(toks)} words in 4 or more batches, penalty {start:.2f} -> {max(vocab, 0.0):.2f}; "
          f"hosts per record type and level {min(dom[(lv, d['name'])] for lv in (1, 2, 3) for d in DOMAINS2)} to {max(dom.values())}")
    return host


def assign_violated2(plans, host):
    """the violated kinds of every batch (3 for a host, 4 otherwise, all listed in its schema), so that every level has 13 or 14 violating
    items of every kind: batches in random order take the kinds with the largest quota left; drawn again until the quotas come out"""
    out = {}
    for level in (1, 2, 3):
        idx = [i for i, p in enumerate(plans) if p["level"] == level]
        for attempt in range(2000):
            rng = sub(f"v2/violated/{level}/{attempt}")
            left, got = kind_quota2(level), {}
            for i in sorted(idx, key=lambda _: rng.random()):
                need = 3 if i in host else 4
                avail = sorted((kd for kd in plans[i]["kinds"] if left[kd] > 0), key=lambda kd: (-left[kd], rng.random()))
                if len(avail) < need:
                    break
                got[i] = avail[:need]
                for kd in got[i]:
                    left[kd] -= 1
            if len(got) == len(idx) and not any(left.values()):
                break
        else:
            raise RuntimeError(f"violated kinds of level {level} cannot be assigned")
        out.update(got)
    return out


def order_rules2(plans, bases, violated):
    """final order of the rules of every batch: its violated rules take the rule numbers used least so far among the batches with the same
    number of rules (so the key of the violated rule is spread evenly over R1 .. Rk), the other rules fill the rest at random"""
    for k in K2:
        rng = sub(f"v2/rule-order/{k}")
        idx = [i for i, p in enumerate(plans) if p["k"] == k]
        rng.shuffle(idx)
        used = [0] * k
        for i in idx:
            pos = sorted(range(k), key=lambda p: (used[p], rng.random()))[:len(violated[i])]
            rng.shuffle(pos)
            order = dict(zip(pos, violated[i]))
            rest = [r["kind"] for r in bases[i]["rules"] if r["kind"] not in violated[i]]
            rng.shuffle(rest)
            by_kind = {r["kind"]: r for r in bases[i]["rules"]}
            bases[i]["rules"] = [by_kind[order[p] if p in order else rest.pop()] for p in range(k)]
            for p in pos:
                used[p] += 1
        assert max(used) - min(used) <= 1, used


def plant_violation2(i, base, kind, attempts=400):
    """a copy of the batch with one planted violation of the listed rule of this kind: exactly that rule is broken, in one place, every listed rule
    still has its valid look-alike and the background of the batch is untouched (None when none of the draws makes it)"""
    no = [r["kind"] for r in base["rules"]].index(kind) + 1
    avoid = [o["record"] - 1 for o in base["oddities"]]
    for attempt in range(attempts):
        rng = random.Random(f"{SEED}/v2/plant/{i}/{kind}/{attempt}")
        spec = copy.deepcopy(base)
        info = plant2(rng, spec, spec["rules"][no - 1], avoid)
        if info is None:
            continue
        hits = [(j, places2(r, spec)) for j, r in enumerate(spec["rules"], 1)]
        if [j for j, p in hits if p] != [no] or len(hits[no - 1][1]) != 1:
            continue
        if not all(lookalike2(r, spec) for r in spec["rules"]):
            continue
        spec["planted"] = {"kind": kind, "rule": f"R{no}", "record": info["record"], "variant": info["variant"]}
        if stray_breaks2(spec):                                   # the planted record breaks its rule only: no other relation of the background
            spec["planted"] = None
            continue
        return spec
    return None


def finalize2(i, base, kind):
    spec = plant_violation2(i, base, kind)
    if spec is None:
        raise RuntimeError(f"no violation of {kind} in batch {i}")
    return spec


def option_orders2(built, plans):
    """order of the options of every item: per number of rules k the gold option stands at each of the k + 1 positions equally often (+- 1),
    among the none items and among all items"""
    orders = [None] * len(built)
    for k in K2:
        rng = sub(f"v2/option-position/{k}")
        idx = [x for x, (i, _, _) in enumerate(built) if plans[i]["k"] == k]
        pool = cycle_list(rng, list(range(k + 1)), len(idx))
        none_idx = [x for x in idx if built[x][2] == "none"]
        none_pos = cycle_list(rng, list(range(k + 1)), len(none_idx))
        for p in none_pos:
            pool.remove(p)
        rng.shuffle(pool)
        for x, p in list(zip(none_idx, none_pos)) + list(zip([x for x in idx if built[x][2] != "none"], pool)):
            rest = [key for key in [f"R{j}" for j in range(1, k + 1)] + ["none"] if key != built[x][2]]
            rng.shuffle(rest)
            rest.insert(p, built[x][2])
            orders[x] = rest
    return orders


def checks_read_output():
    """validate.py and audit.py read ROOT/tasks/<task>.  When BENCH_OUT sends the files elsewhere, their reads are redirected there, so the
    self-checks of both versions look at the files of this run and nothing under ROOT/tasks is read or written"""
    home = os.path.join(ROOT, "tasks", TASK) + os.sep
    if os.path.abspath(OUT) + os.sep == home:
        return
    import builtins
    real = builtins.open

    def redirected(file, *args, **kwargs):
        if isinstance(file, str) and os.path.abspath(file).startswith(home):
            file = os.path.join(OUT, os.path.abspath(file)[len(home):])
        return real(file, *args, **kwargs)
    builtins.open = redirected


def check_items2(items, base_text):
    """the invariants of the item set; returns the counts that task.json and the README report"""
    st = {}
    assert len(items) == 3 * BASES2 * GROUP2 == 600 and len({it["id"] for it in items}) == 600
    assert collections.Counter(it["meta"]["level"] for it in items) == {1: 200, 2: 200, 3: 200}
    st["cell"] = cell = collections.Counter((it["meta"]["level"], it["meta"]["deviation"] or "none") for it in items)
    for level in (1, 2, 3):                                       # classes and kinds per level
        assert cell[(level, "none")] == HOSTS2 and all(cell[(level, kd)] == q for kd, q in kind_quota2(level).items()), (level, cell)
    st["total"] = total = collections.Counter(it["meta"]["deviation"] or "none" for it in items)
    assert total["none"] == N_NONE2 and sorted(total[kd] for kd in KINDS2) == [40] * 5 + [41] * 8, total
    st["chance"] = chance = sum(1 / len(it["questions"]["q"]["criteria"]) for it in items) / len(items)       # the designed share of none: about 1 / mean number of options
    st["mean_options"] = mean_options = sum(len(it["questions"]["q"]["criteria"]) for it in items) / len(items)
    st["none_share"] = {lv: cell[(lv, "none")] / sum(cell[(lv, c)] for c in ["none"] + KINDS2) for lv in (1, 2, 3)}
    st["none_share_all"] = total["none"] / len(items)
    assert all(abs(s - 1 / mean_options) <= 0.005 and abs(s - chance) <= 0.005 for s in [*st["none_share"].values(), st["none_share_all"]]), \
        (st["none_share"], st["none_share_all"], 1 / mean_options, chance)       # none is keyed in 1 / mean number of options of the items, at every level
    st["listed"] = listed = collections.Counter(r["kind"] for it in items for r in it["meta"]["spec"]["rules"])
    share = [total[kd] / listed[kd] for kd in KINDS2]             # how often a listed rule of a kind is the broken one: the same for every kind
    assert max(share) / min(share) < 1.12, share
    st["share"] = (min(share), max(share))
    for it in items:                                              # schema, options, size
        m, spec = it["meta"], it["meta"]["spec"]
        kinds = [r["kind"] for r in spec["rules"]]
        assert len(kinds) == len(set(kinds)) == m["rules"] and m["rules"] in K2 and m["new_kinds"] >= 3, it["id"]
        assert m["records"] == N2[m["level"]] == len(spec["records"]) and len(spec["fields"]) <= FIELD_CAP2
        assert list(it["questions"]["q"]["criteria"]) == m["order"] and sorted(m["order"]) == sorted([f"R{j}" for j in range(1, m["rules"] + 1)] + ["none"])
        assert it["questions"]["q"]["criteria"]["none"] == NONE_TEXT and it["questions"]["q"]["instructions"] == QUESTION["instructions"]
        assert 600 <= len(it["state"]) < 14000, (it["id"], len(it["state"]))
        assert (m["violated"] or "none") == it["gold"] and (m["violated_kind"] is None) == (it["gold"] == "none")
        if m["violated"]:
            assert spec["rules"][int(m["violated"][1:]) - 1]["kind"] == m["violated_kind"] == m["deviation"]
    groups = collections.defaultdict(list)
    for it in items:
        groups[it["group"]].append(it)
    assert len(groups) == 3 * BASES2 and len(set(base_text.values())) == 3 * BASES2
    st["changed_lines"], st["length_diff"] = collections.Counter(), []
    for g, members in groups.items():                             # four items on one batch: one planted difference each
        base = base_text[g].split("\n")
        assert len(members) == GROUP2 and len({m["gold"] for m in members}) == GROUP2, g
        assert len({json.dumps(m["questions"]["q"]["criteria"], sort_keys=True) for m in members}) == 1
        assert len({(m["meta"]["level"], m["meta"]["rules"], m["meta"]["domain"], m["meta"]["layout"]) for m in members}) == 1
        for m in members:
            lines = m["state"].split("\n")
            assert len(lines) == len(base), g                     # the same number of lines
            diff = [x for x in range(len(lines)) if lines[x] != base[x]]
            first_record = len(lines) - m["meta"]["records"]
            assert all(x >= first_record for x in diff), g        # only records differ
            if m["gold"] == "none":
                assert not diff
            elif m["meta"]["deviation"] == "sequence":            # one broken step: the numbers of the shorter side of the batch move by one
                assert 1 <= len(diff) <= m["meta"]["records"] // 2, (g, len(diff))
            else:
                assert len(diff) == 1, (g, m["meta"]["deviation"], diff)
            if m["gold"] != "none":
                st["changed_lines"][len(diff)] += 1
                st["length_diff"].append(len(m["state"]) - len(base_text[g]))
    st["hosts"] = sum(1 for members in groups.values() if any(m["gold"] == "none" for m in members))
    assert st["hosts"] == N_NONE2
    st["gold_pos"], st["rule_no"], st["none_k"] = {}, {}, {}
    for k in K2:                                                  # positions
        sel = [it for it in items if it["meta"]["rules"] == k]
        pos = collections.Counter(it["meta"]["order"].index(it["gold"]) for it in sel)
        num = collections.Counter(it["gold"] for it in sel if it["gold"] != "none")
        assert max(pos.values()) - min(pos[p] for p in range(k + 1)) <= 1, (k, pos)
        assert max(num.values()) - min(num[f"R{j}"] for j in range(1, k + 1)) <= 1, (k, num)
        st["gold_pos"][k], st["rule_no"][k] = [pos[p] for p in range(k + 1)], [num[f"R{j}"] for j in range(1, k + 1)]
        st["none_k"][k] = (sum(it["gold"] == "none" for it in sel), len(sel))
        assert st["none_k"][k][0] == N_NONE2 // len(K2)
    states = [it["state"] for it in items]
    assert len(set(states)) == len(states)                        # no duplicate state
    st["links"], st["rows"], st["status_note"] = collections.Counter(), 0, 0
    for it in items:                                              # consistent background: nothing breaks a relation outside the planted record and the oddities
        spec = it["meta"]["spec"]
        stray = stray_breaks2(spec)
        assert not stray, (it["id"], stray)
        st["rows"] += spec["n"]
        st["links"].update(background_links2(spec))
        assert it["meta"]["background"] == background_links2(spec)
        assert len(spec["oddities"]) <= 2 and spec["oddities"] == it["meta"]["oddities"]
        assert has_status2(spec) == (STATUS_NOTE2[spec["phrasing"]["status"]] in it["state"].split("\n\n")), it["id"]
        st["status_note"] += has_status2(spec)
    odd = [it for it in items if any(o["kind"] == "list_status" for o in it["meta"]["oddities"])]
    st["status_odd"] = len(odd)                                   # a plain reference rule meets a key of unusual status
    st["status_decides"] = sum(it["meta"]["deviation"] != "reference" for it in odd)    # ... and the answer is not that rule: the status reading would be wrong
    assert all(has_status2(it["meta"]["spec"]) for it in odd)
    labels = ["none" if it["gold"] == "none" else "viol" for it in items]
    st["vocab"] = {}
    for pat, name in ((r"[a-z]+", "words"), (TOKEN_RX, "all tokens")):
        bad, tested, worst = vocab_test(states, labels, pattern=pat)
        st["vocab"][name] = (tested, worst, bad)
    assert not st["vocab"]["words"][2], st["vocab"]["words"][2][:12]       # no word marks the none items or the violating items
    st["lengths"] = {lv: sorted(len(it["state"]) for it in items if it["meta"]["level"] == lv) for lv in (1, 2, 3)}
    st["variants"] = collections.Counter((it["meta"]["deviation"], it["meta"]["variant"]) for it in items if it["meta"]["deviation"])
    st["oddities"] = collections.Counter(o["kind"] for members in groups.values() for o in members[0]["meta"]["oddities"])
    st["odd_batches"] = sum(1 for members in groups.values() if members[0]["meta"]["oddities"])
    st["layout"] = collections.Counter((it["meta"]["layout"], it["gold"] == "none") for it in items)
    st["domain"] = collections.Counter((it["meta"]["domain"], it["gold"] == "none") for it in items)
    st["fields"] = sorted(len(it["meta"]["spec"]["fields"]) for it in items)
    return st


def write_task_json_v2(items, st):
    chance = sum(1 / len(it["questions"]["q"]["criteria"]) for it in items) / len(items)
    lens = sorted(len(it["state"]) for it in items)
    split = f"generated, random.Random({SEED}), DIFFICULTY v2" + (" (item set made with BENCH_SEED, same design as the published set)" if BENCH_SEED is not None else "")
    none_lv = " / ".join(f"{st['none_share'][lv]:.3f}" for lv in (1, 2, 3))
    tj = {"task": TASK, "layer": "F", "title": "Generated record batches, second version: which integrity rule does the batch violate?",
          "decision": "which of the 6 to 9 listed integrity rules a batch of records breaks (in one place, by a near miss), or none",
          "source": {"name": f"generator build/gen_{TASK}.py", "url": "", "files": [], "split": split,
                     "version": "gen_v4, 2026-10-08: consistent background data (tax, totals, dates, dated references), status convention written in the state, "
                                "none share asserted; second version (v2) of 2026-10-07, DIFFICULTY = \"v1\" regenerates the first version byte for byte"},
          "licence": "generated by the benchmark's script (no third-party text)", "redistribution": "items included",
          "labels": "programmatic", "item_source": "generated", "metric": "accuracy", "chance": round(chance, 6), "rows": len(items),
          "groups": len({it["group"] for it in items}), "question_type": "choice",
          "options": max(len(it["questions"]["q"]["criteria"]) for it in items),
          "skill": "check a batch of records against 6 to 9 integrity rules (keys and pairs that must not repeat, look-ups in reference lists with a status, "
                   "limits that depend on another field, stored totals, running numbers, references between records) and name the one broken rule, or none",
          "knobs": "records per batch 10 / 16 / 24 (meta.level 1 / 2 / 3); 6 to 9 rules, 3 to 5 of them of the kinds that need a computation, two records or two lists; "
                   "violations one step from valid; valid look-alikes of every listed rule; oddities that no listed rule covers",
          "notes": ("gen_v4 (2026-10-08): outside the planted violation and the one or two deliberate oddities (meta.oddities) every record keeps the relations between its own fields "
                    "(tax = round(net x tax_rate / 100), stored totals, second date not before the first) and a record that names an earlier record is dated after it (meta.background lists "
                    "them); a state with a status column says what a status counts for; the share of none is asserted (" + none_lv + " at levels 1 / 2 / 3, about 1 / mean number of options). "
                    "Version v2 (harder than the first version, which is regenerated byte for byte with DIFFICULTY = \"v1\"). 600 items = 150 batches x 4 (group): the same batch "
                    "with four different answers - one planted violation each of three or four different rules, and in 72 batches the untouched batch (none; 0.12 of the items, about "
                    "1 / mean number of options). Options differ per item: one key per rule (R1 ... Rk, k = 6..9, option text = the sentence of the rule) plus none; options = the "
                    "maximum (10), chance = the mean of 1 / number of options. Thirteen rule kinds (meta.deviation, 40 or 41 violating items each, 13 or 14 per level): the six of v1 "
                    "(unique, reference, range, conditional, date_order, allowed) and composite (a pair of fields is unique), ref_active (key in a list AND with a status there), "
                    "dep_range (limits depend on another field), xor (exactly one of two fields filled), derived (stored total = product or sum), sequence (a number rises by one from "
                    "record to record), self_ref (names the key of an EARLIER record); every schema lists 3 to 5 of the seven new kinds. Violations are near misses (meta.variant); "
                    "every batch holds a valid look-alike of every listed rule, and most hold oddities that no listed rule covers (meta.oddities), which are not violations. "
                    "meta.level 1 / 2 / 3 = 10 / 16 / 24 records (200 items each); two layouts of the records (JSON lines, table) and two of the lists. The key of the violated rule and "
                    "the position of the gold option are spread evenly per number of rules; a listed rule of any kind is the broken one equally often. "
                    f"State length {lens[0]} to {lens[-1]} characters (median {lens[len(lens) // 2]}). The truth is computed on the structured records (meta.spec); the script asserts that "
                    "a violating item breaks exactly the gold rule in exactly one place and a none item nothing.")}
    with open(os.path.join(OUT, "task.json"), "w", encoding="utf-8") as f:
        json.dump(tj, f, indent=1, ensure_ascii=False)


KIND_DOC2 = [   # kind, what the rule says, what has to be worked out, the planted near miss, the valid look-alike in every batch that lists the rule
    ("unique", "a key field has no duplicate in the batch", "compare every key with every other key",
     "the key of another record that stands at least two records away",
     "1 / 2 / 3 pairs of near-identical keys at level 1 / 2 / 3 (one digit changed or two neighbouring digits exchanged)"),
    ("reference", "a field is a key of a reference list (a status column of that list is not asked about)", "look every value up in the list",
     "a key with one digit changed or two digits exchanged that the list does not hold",
     "a key in use whose near-identical neighbour is in the list too; half of these lists show a status, and then entries of any status may be in use"),
    ("range", "a whole number lies between two limits, both included", "compare with both limits", "one step above the upper or below the lower limit",
     "a value exactly on a limit"),
    ("conditional", "when a yes/no field says \"yes\", a second field must be filled in", "read the trigger, then the second field",
     "the second field emptied on a record that needs it, or the trigger set on a record whose second field is empty",
     "records without the trigger whose second field is empty"),
    ("date_order", "one date is not after another (same day allowed) or strictly before it (same day not allowed); the sentence says which",
     "compare two dates", "the later date one day (or two to three days) early; under a strict rule also the same day",
     "the same day under a rule that allows it, exactly one day apart under a strict rule; from level 2 a pair across a month end, where the later date has the smaller day number"),
    ("allowed", "a field takes one of three or four listed words", "compare with the list",
     "another word of the same vocabulary, where possible one that the sibling field uses in the same batch",
     "an allowed word that occurs once only; in most batches a sibling field without a rule that uses the other words"),
    ("composite", "the PAIR of two fields occurs once; each of the two fields repeats", "compare two fields across pairs of records",
     "a record that shared one of the two fields with another record now shares both",
     "records that share the first field only and records that share the second field only, with near-identical values among them"),
    ("ref_active", "a field is a key of a reference list AND the list marks that key with the status named in the rule",
     "find the key in the list, then read its status",
     "a key that the list holds with another status; often the near-identical neighbour of the key the record had",
     "the active neighbour of an inactive key is in use; inactive entries that no record names"),
    ("dep_range", "the limits of a number depend on a second field (two branches whose spans overlap in part)", "read the branch, take its limits, compare",
     "a value one step outside its branch (or further) that the other branch allows, or the branch field changed on a record whose value only the old branch allows",
     "values on a limit of their branch, and in both branches values that the other branch forbids"),
    ("xor", "exactly one of two fields is filled in", "read both fields", "both filled in, or both empty",
     "records that fill only the first field and records that fill only the second"),
    ("derived", "a stored total equals the product (three record types) or the sum (five record types) of two other fields",
     "one multiplication or addition per record", "two neighbouring digits of the total exchanged, or the total off by 1, 2 or 10",
     "none of its own: every record needs the computation"),
    ("sequence", "a number rises by exactly one from each record to the next; the first number is free", "compare neighbours down the batch",
     "one number skipped or repeated at one step (the numbers on the shorter side of the step move by one, so there is one broken step)",
     "the count never starts at 1; in about a third of the batches it passes from 9 to 10 or from 99 to 100"),
    ("self_ref", "a field that, when filled in, names the key of a record that stands EARLIER in the batch", "find the named key among the records, compare the two places",
     "the key of a record further down, or the named key with one digit changed (a key that no record has)",
     "the record just before is named; where the batch has room for it, an earlier key is named although a near-identical key follows later")]


def write_readme_v2(items, st):
    head, line, r = audit_lines()
    assert not r["flag"], r
    import validate as validate_mod
    validate_mod.HERE = ROOT
    tj, errs = validate_mod.check(TASK)
    assert not errs, errs
    assert [k for k, *_ in KIND_DOC2] == KINDS2
    by_id = sorted(items, key=lambda it: it["id"])
    lens = sorted(len(it["state"]) for it in items)
    variants = collections.defaultdict(list)
    for (kd, v), c in sorted(st["variants"].items()):
        variants[kd].append(f"`{v}` {c}")
    words = st["vocab"]["words"]
    ld = sorted(st["length_diff"])
    one_line = st["changed_lines"][1]
    ex = [next(it for it in by_id if it["meta"]["level"] == 1 and it["meta"]["layout"] == "json" and it["meta"]["deviation"] in KINDS_NEW),
          next(it for it in by_id if it["meta"]["level"] == 2 and it["meta"]["layout"] == "table" and it["gold"] == "none"),
          None]
    ex[2] = next(it for it in by_id if it["meta"]["level"] == 3 and it["meta"]["layout"] == "table" and it["meta"]["deviation"] in KINDS_NEW
                 and it["meta"]["deviation"] != ex[0]["meta"]["deviation"])
    seed_note = (f" This item set was made with `BENCH_SEED={SEED}`: the same design as the published set, other items." if BENCH_SEED is not None else "")
    none_lv = " / ".join(f"{st['none_share'][lv]:.3f}" for lv in (1, 2, 3))
    L = [f"# {TASK}", "", "Generated record batches, second version: which integrity rule does the batch violate? (layer F, generated, programmatic truth; version v2, set gen_v4 of 2026-10-08)", "",
         "- gen_v4 (2026-10-08) changes three things of the v2 set and nothing else in its design: (1) the background of every batch is consistent - outside the planted violation and the one or two "
         "deliberate oddities, tax = round(net x tax_rate / 100) and every stored total holds, the second date is not before the first, and a record that names an earlier record (a recheck, a credit, a "
         "reopened ticket ...) is dated after it; (2) a state with a status column in a reference list says what a status counts for; (3) the share of `none` is asserted at every level. "
         "See \"Background data\" below.",
         "- Decision: which of the 6 to 9 listed integrity rules a batch of records breaks - in one place, by a near miss - or none.",
         f"- Source: generator `build/gen_{TASK}.py` (standard library only, `random.Random({SEED})` and generators derived from it; two runs give identical files); no third-party text.{seed_note}",
         "- Version: this directory holds **v2**, the harder second version. The first version (6 / 10 / 14 records, 4 to 7 rules of six kinds that read one field or one record; "
         "strong models reach 0.98 to 1.00 on it) is regenerated byte for byte by setting `DIFFICULTY = \"v1\"` at the top of the script (or `BENCH_DIFFICULTY=v1`), which rewrites this directory. "
         "`BENCH_OUT=<dir>` writes to `<dir>/" + TASK + "/` instead; `BENCH_SEED=<k>` (v2 only, together with `BENCH_OUT`) makes another item set of the same design.",
         "- Licence: generated by the benchmark's script (no third-party text); items included.",
         f"- Rows: {len(items)} = {len({it['group'] for it in items})} batches x {GROUP2} items (`group`); options: R1 ... Rk (k = 6..9, option text = the sentence of the rule) and `none`, "
         f"{tj['options']} at most; metric: accuracy (chance {tj['chance']:.4f}, the mean of 1 / number of options).",
         f"- Rebuild: `python3 build/gen_{TASK}.py`", "",
         "## What is generated", "",
         "A state is one text: a lead-in with the two general conventions, the field list of the record type, 6 to 9 numbered integrity rules, the reference lists that the rules use, and a batch of "
         "10, 16 or 24 records. The question is \"Which rule does the batch violate?\"; the options are the keys R1 ... Rk, each with the sentence of its rule as option text, and `none`; their order is drawn per item (`meta.order`). "
         "A batch breaks at most one rule, in one place. Gold = the key of the broken rule, or `none`.", "",
         "Eight invented record types (order lines, shift entries, sensor readings, library loans, support tickets, parcels, course enrolments, invoice lines) with 21 fields each. A state shows "
         f"{st['fields'][0]} to {st['fields'][-1]} of them: the key, the fields of the listed rules and the fields of up to two kinds that the schema does NOT list (room for oddities that no rule covers). "
         "The field order is drawn per batch. Two layouts of the records (JSON lines; a table with \" | \" between the cells) and two of the reference lists (on one line; one entry per line), "
         "four phrasings of every rule kind (sixteen kinds of sentence: thirteen rule kinds, the strict date order, product and sum), four lead-ins, four wordings of the general conventions, three of every header. "
         "Thresholds, allowed lists, list sizes, statuses and strictness are drawn per batch; identifiers and names are code-like patterns or come from a syllable generator.", "",
         "Thirteen rule kinds: the six of the first version and seven that need a computation, a second record or a second list. A schema lists 6, 7, 8 or 9 rules of different kinds, 3 to 5 of them of the seven new kinds "
         "(the share of the new kinds is 7 / 13 for every number of rules, and every kind is listed in the same number of batches).", "",
         "| kind (`meta.deviation`) | the rule | what has to be worked out | the planted near miss | valid look-alike in every batch that lists the rule |", "|---|---|---|---|---|"]
    L += [f"| `{k}` | {a} | {b} | {c} | {e} |" for k, a, b, c, e in KIND_DOC2]
    L += ["", "The first six kinds are those of the first version; their sentences are new, and their violations are now near misses as well.", "",
          "## Conventions written into every state", "",
          "- General (four wordings): at most one rule is broken, and only in one place; a rule asks for exactly what its sentence says; whatever no listed rule covers is not a violation.",
          "- Every rule sentence carries its own convention: limits included; the same day allowed or not; which field may repeat; the first number of a running count is free; a named record must stand earlier in the batch; "
          "the status that a list entry must have.",
          "- The header of the records says that they stand in batch order and how an empty field looks: in the JSON layout a field that is missing or null, in the table a cell that holds only \"-\". \"Filled in\" is the opposite of empty.",
          "- A reference list with statuses is written `key: status`. A paragraph after the lists says what a status counts for (gen_v4; four wordings, one per batch, in the "
          f"{st['status_note']} states that show a status column): a plain reference rule - one that only asks for a key of the list - accepts every key the list holds, whatever its status, and only a rule that "
          f"names a status (`ref_active`) requires it. In {st['status_odd']} items a record names a key of unusual status under a plain reference rule (`list_status` among the oddities); "
          f"a reader who asked a status of that rule would find a violation that is not there (or a second one) in {st['status_decides']} of them.",
          "- Fields and list names stand in backticks inside the rules, text values in double quotes, numbers and dates (YYYY-MM-DD) bare.", "",
          "## Background data (gen_v4)", "",
          "Everything in a batch that no listed rule asks about still behaves like data. Outside the planted violation and the one or two deliberate oddities, every record keeps the following relations "
          f"(the script checks all of them on all {st['rows']} records of the 600 items: `stray_breaks2`, 0 breaks outside the places named below). `meta.background` lists the relations that hold in a batch.", "",
          "| relation | where | how it is kept |", "|---|---|---|",
          "| a stored total is the product or the sum of its operands (`derived`, listed or shown as an extra kind) | every record type that shows the three fields | drawn that way; the planted `derived` violation changes the total and nothing else |",
          "| tax = round(net x tax_rate / 100), never a tie between two roundings; gross = net + tax | invoice lines that show `tax_rate`, `net` and `tax` | the tax follows the rate of its own record; the planted `range` violation on `tax_rate` "
          "moves the tax and the gross with the rate, so that the record breaks the range and nothing else. Without a `tax_rate` field the batch draws its taxes from two usual rates (7, 10, 19, 21 or 25 per cent): the tax is at most a quarter of the net |",
          "| the second date is not before the first (an upload on or after its reading, a delivery after the dispatch ...) | every record type that shows the date pair | gaps of 0 or more days (1 or more under a strict rule) |",
          "| a record that names an earlier record (`recheck_of`, `credit_for`, `replaces`, `corrects`, `renewal_of`, `reopens`, `forwarded_from`, `transfer_of`) is dated after it: a recheck after the reading, a credit after the invoice line | "
          "every record type that shows the reference field and the date pair | the references are drawn first and the dates follow record by record: the first date lies at least one day after the first date of the named record "
          "(after the closing date for tickets, after the delivery date for parcels); the planted `date_order` violation moves the date that cannot put a naming record before it, and the `self_ref` violation 'a later record' picks, where the batch allows it, a record whose date is in order with the later one it names |", "",
          "The places where a relation may break are the deliberate oddities of the batch (`meta.oddities`, up to two; "
          f"{st['odd_batches']} of {len({it['group'] for it in items})} batches have one or two) and the planted record, and each only for the relation of its own kind: a wrong total (`derived`), a reversed date pair (`date_order`), "
          "a reference to a later record (`self_ref`). Every other oddity (a repeated key or pair, a skipped number, an empty required field, both or neither of two fields, a key of unusual status) "
          "leaves the relations above intact. No field of a record type suggests a relation that the batch does not keep: a loan period or the payment days of an invoice would have to match the date pair, "
          "so the limited fields of those two record types are a `deposit` and a `handling_fee`, and the shipping modes of order lines contain no `pickup` next to the pickup / delivery fields.", "",
          "## Levels", "", "| `meta.level` | records | pairs of near-identical record keys | keys in a plain list | entries in a status list | state characters min / median / max |", "|---|---|---|---|---|---|"]
    for lv, a, b in ((1, "8-10", "7-9"), (2, "10-12", "9-11"), (3, "12-15", "11-14")):
        v = st["lengths"][lv]
        L.append(f"| {lv} | {N2[lv]} | {lv} | {a} | {b} | {v[0]} / {v[len(v) // 2]} / {v[-1]} |")
    L += ["", "The number of rules (6 to 9) and the mix of kinds are the same at every level; the level is the size of the batch (and of the lists).", "",
          "**What makes level 3 hard.** 24 records with up to 17 fields and 6 to 9 rules: every rule has to be cleared on every record, and 3 to 5 of the rules cannot be cleared from one cell. "
          "One rule check of a new kind combines at least three facts from different places: for `ref_active` the status named in the rule, the key in the record and the entry of that key among 11 to 14 entries with near-identical neighbours; "
          "for `dep_range` the two branches of the rule, the branch field of the record and its value; for `self_ref` the named key, the place of the record that carries this key and the place of the record that names it; "
          "for `derived` two operands, one multiplication or addition and the stored total, 24 times; for `composite` two fields of two records among 276 pairs of records; for `sequence` 23 steps. "
          "The single violation is one step from valid and may sit anywhere in the batch, valid records sit on the same limits, and most batches also hold something odd that no listed rule covers. "
          "Answering `none` needs all of these checks to come out clean.", "",
          "## Groups and classes", "",
          f"{len({it['group'] for it in items})} batches (50 per level), each used for {GROUP2} items (`group`, `meta.batch`). In {st['hosts']} batches (24 per level, 18 per number of rules) one item is the untouched batch (`none`) and three items "
          "carry one planted violation each, of three different rules; in the other 78 batches four different rules are violated. The states of a group have the same number of lines and are identical apart from the planted record "
          f"({one_line} of {N_VIOL2} violating items differ from their batch in one line; a `sequence` violation moves the numbers on the shorter side of the broken step, 1 to 12 lines). "
          f"A violating state is between {-ld[0]} characters shorter and {ld[-1]} longer than its batch (median {ld[len(ld) // 2]:+d}, mean {sum(ld) / len(ld):+.2f}). "
          f"`none` is {st['total']['none']} of {len(items)} items = {st['total']['none'] / len(items):.3f}; the designed share is about 1 / (mean number of options) = {1 / st['mean_options']:.3f} "
          f"(mean number of options {st['mean_options']:.2f}, chance {tj['chance']:.3f}). Per level `none` is {none_lv} (level 1 / 2 / 3; {HOSTS2} of 200 at every level), and the script asserts that the share at every level and overall lies "
          "within 0.005 of 1 / (mean number of options) and of the chance.", "",
          "| class (`meta.deviation`) | level 1 | level 2 | level 3 | total | variants (`meta.variant`) |", "|---|---|---|---|---|---|"]
    for c in ["none"] + KINDS2:
        L.append(f"| {c} | " + " | ".join(str(st["cell"][(lv, c)]) for lv in (1, 2, 3)) + f" | {st['total'][c]} | {', '.join(variants[c])} |")
    L += ["", "Balance: 200 items per level; 13 or 14 violating items of every kind per level and 40 or 41 in all; a listed rule of a given kind is the broken one in "
          f"{st['share'][0]:.3f} to {st['share'][1]:.3f} of the items that list it, for every kind; per number of rules k, the key of the violated rule is spread evenly over R1 ... Rk and the gold option over the k + 1 positions "
          "(differences of one item at most), among the `none` items as well.", "",
          "| rules k | items | none | gold option at position 1 ... k + 1 | violated rule R1 ... Rk |", "|---|---|---|---|---|"]
    for k in K2:
        L.append(f"| {k} | {st['none_k'][k][1]} | {st['none_k'][k][0]} | {' '.join(map(str, st['gold_pos'][k]))} | {' '.join(map(str, st['rule_no'][k]))} |")
    L += ["", f"**Oddities that no listed rule covers** (`meta.oddities`; {st['odd_batches']} of {len({it['group'] for it in items})} batches have one or two, the same in all four items of the batch): "
          + ", ".join(f"{k} {c}" for k, c in sorted(st["oddities"].items())) + ". They are planted like violations (a repeated key, a repeated pair, a date a day early, an empty required field, both or neither of two fields, "
          "a total that is off, a skipped number, a reference to a later record) but under a kind that the schema does not list, so they are not violations; `list_status` is a record that names a list entry whose status is not "
          "the usual one, under a rule that asks only for a key of the list.", "",
          "## Checks made by the script", "",
          "- `truth2(spec)` evaluates every listed rule on the structured records and returns the places where it is broken: a violating item breaks exactly the gold rule in exactly one place, a `none` item breaks nothing.",
          "- Every batch, and every item made from it, holds a valid look-alike of every listed rule (last column of the table of kinds); a batch or a planted violation without them is drawn again.",
          "- The records and the reference lists read back from the rendered text equal the specification (`meta.spec`); the status paragraph stands in exactly the states that show a status column.",
          f"- Consistent background (gen_v4): `stray_breaks2` finds no broken relation (total, tax, date pair, dated reference) outside the planted record and the oddity records, in any of the {len(items)} items; a base batch or a "
          "planted violation that breaks one is drawn again.",
          f"- Share of `none`: {none_lv} at levels 1 / 2 / 3, asserted within 0.005 of 1 / (mean number of options) at every level and overall.",
          "- The four states of a group have the same number of lines and differ from their batch in the planted record only; their options are the same and their gold keys differ.",
          "- Counts: levels, classes and kinds per level, hosts of the `none` items per number of rules, positions of the gold option and of the violated rule, the same chance for every kind to be the broken one among the listed ones; no duplicate state; "
          f"every state below 14,000 characters ({lens[0]} to {lens[-1]}, median {lens[len(lens) // 2]}).",
          f"- Vocabulary (the `none` items against the violating items): {words[0]} words occur in 20 or more states; none is more than twice as frequent in one class as in the other (largest ratio {words[1]:.2f}). "
          "The batches that give the `none` items are chosen for this (3 per cell of level, number of rules and layout, exchanged inside the cells until the words are spread evenly). "
          "Numbers are not part of the test: one number stands in a handful of batches, and a batch brings its four items along.",
          f"- `python3 validate.py {TASK}`: OK. `python3 audit.py {TASK}`:", "", "```", head, line, "```", "",
          f"`audit_v3.py {TASK}` (needs numpy) and the independent solver of the benchmark (`solve_all.py`, a second implementation that reads the rendered text alone) are run outside this script.", "",
          "## Examples (one per level)", ""]
    for it in ex:
        m = it["meta"]
        what = "none" if it["gold"] == "none" else f"violated {m['violated']} = `{m['violated_kind']}`, variant `{m['variant']}`, record {m['record']}"
        odd = "; ".join(f"`{o['kind']}` in record {o['record']}" for o in m["oddities"]) or "none"
        L += [f"### level {m['level']}: {m['records']} records, {m['rules']} rules, {m['layout']} layout ({it['id']}, {what}; oddities that are not violations: {odd})", "", "```", example_text(it), "```", ""]
    L += ["## Independence from training generators", "",
          "The items are disjoint from any training generator of the authors by construction: this generator was written for the benchmark alone and shares no template, sentence or vocabulary list with a generator used for training; "
          "every identifier, name and number is drawn by the script."]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("validate: OK")
    print(head)
    print(line)
    print("class x level:", {c: [st["cell"][(lv, c)] for lv in (1, 2, 3)] for c in ["none"] + KINDS2})
    print("items that list a kind:", {kd: st["listed"][kd] for kd in KINDS2}, "| share of them with that rule broken: %.3f to %.3f" % st["share"])
    print("gold position per k:", st["gold_pos"])
    print("violated rule number per k:", st["rule_no"])
    print("state characters per level (min, median, max):", {lv: (v[0], v[len(v) // 2], v[-1]) for lv, v in st["lengths"].items()})
    print("fields per record (min, median, max):", st["fields"][0], st["fields"][len(st["fields"]) // 2], st["fields"][-1])
    print("lines changed by a planted violation:", dict(sorted(st["changed_lines"].items())), "| length difference to the batch: min", ld[0], "median", ld[len(ld) // 2], "max", ld[-1])
    print("oddities:", dict(sorted(st["oddities"].items())), "| batches with one:", st["odd_batches"])
    print(f"none share per level: {none_lv} | overall {st['none_share_all']:.3f} | 1 / mean number of options {1 / st['mean_options']:.3f}, chance {st['chance']:.3f}")
    kinds = {"stored total": lambda s: " = " in s and "tax = " not in s and "at most" not in s, "tax = round(net x rate)": lambda s: s.startswith("tax = round"),
             "tax share": lambda s: "at most a quarter" in s, "date pair": lambda s: "<=" in s, "dated reference": lambda s: "dated after" in s}
    print(f"background: {st['rows']} records checked, 0 breaks outside the planted record and the oddities | items that keep each relation: "
          f"{ {k: sum(c for s, c in st['links'].items() if f(s)) for k, f in kinds.items()} }")
    print(f"status paragraph in {st['status_note']} states; items with a plain reference rule over a key of unusual status: {st['status_odd']} (wrong reading would fail {st['status_decides']})")
    print("layout x none:", dict(sorted(st["layout"].items())), "| record type: none items", sorted({v for (d, n), v in st["domain"].items() if n}),
          "violating items", sorted({v for (d, n), v in st["domain"].items() if not n}))
    for name, (tested, worst, bad) in st["vocab"].items():
        print(f"vocabulary, none against violating ({name}): {tested} tokens in 20 or more states, largest ratio {worst:.2f}, above 2: {len(bad)}")
    print("variants:", {kd: v for kd, v in variants.items()})


def main_v2():
    plans = plan2()
    bases = [build_base2(i, p) for i, p in enumerate(plans)]
    host = choose_hosts2(plans, bases)
    violated = assign_violated2(plans, host)
    order_rules2(plans, bases, violated)
    built = []                                                    # (batch, specification, gold key)
    for i, base in enumerate(bases):
        assert truth2(base) == "none"
        if i in host:
            built.append((i, copy.deepcopy(base), "none"))
        for kind in violated[i]:
            spec = finalize2(i, base, kind)
            built.append((i, spec, spec["planted"]["rule"]))
    orders = option_orders2(built, plans)
    group_no = list(range(len(bases)))
    sub("v2/groups").shuffle(group_no)
    rows = [(i, spec, gold, order) for (i, spec, gold), order in zip(built, orders)]
    sub("v2/shuffle").shuffle(rows)
    items = []
    for n, (i, spec, gold, order) in enumerate(rows, 1):
        state = render_state2(spec)
        texts = {f"R{j}": rule_sentence2(r) for j, r in enumerate(spec["rules"], 1)}
        texts["none"] = NONE_TEXT
        pl = spec["planted"]
        meta = {"source_id": f"{n:05d}", "level": spec["level"], "domain": spec["domain"], "deviation": pl["kind"] if pl else None, "order": order,
                "records": spec["n"], "rules": len(spec["rules"]), "new_kinds": sum(r["kind"] in KINDS_NEW for r in spec["rules"]),
                "violated": pl["rule"] if pl else None, "violated_kind": pl["kind"] if pl else None, "variant": pl["variant"] if pl else None,
                "record": pl["record"] if pl else None, "oddities": spec["oddities"], "background": background_links2(spec),
                "layout": spec["layout"], "list_format": spec["list_format"], "batch": group_no[i] + 1, "spec": spec}
        if BENCH_SEED is not None:
            meta["seed"] = SEED
        item = {"id": f"{TASK}:{SEED_TAG}{n:05d}", "state": state, "questions": {"q": dict(QUESTION, criteria={key: texts[key] for key in order})},
                "gold": gold, "soft": None, "group": f"{TASK}:{SEED_TAG}g{group_no[i] + 1:04d}", "meta": meta}
        assert truth2(spec) == gold == (pl["rule"] if pl else "none"), item["id"]
        reread2(state, spec)
        items.append(item)
    stats = check_items2(items, {f"{TASK}:{SEED_TAG}g{group_no[i] + 1:04d}": render_state2(b) for i, b in enumerate(bases)})
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "items.jsonl"), "w", encoding="utf-8") as f:
        for it in items:
            f.write(dumps(it) + "\n")
    write_task_json_v2(items, stats)
    write_readme_v2(items, stats)


if __name__ == "__main__":
    if BENCH_OUT:
        checks_read_output()
    (main_v2 if DIFFICULTY == "v2" else main_v1)()
