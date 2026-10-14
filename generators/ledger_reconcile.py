"""Task ledger_reconcile (layer F, generated, programmatic truth): which entry of ledger A does not reconcile with ledger B?

Item design.  The state holds two ledgers of one period (a cash book against a bank statement, a purchase ledger against
a supplier statement, a stock system against a receiving log, a timesheet against a client hours log, a dispatch register
against a weighbridge record), the matching conventions of the level written out in numbered sentences, and the sentence
that at most one entry of A fails.  The options are five entry labels of A (for example "A07") and `none`.
    level 1  8 entries: pairing by reference, equal amounts, B in another order, dates not compared
    level 2  14 entries: + date tolerance of D days, an entry may appear in B as two lines that add up, B reverses signs
    level 3  22 entries: + entries of a marked channel reach B less a fixed deduction per line, entries that share a batch
             number appear in B as one line with their total (a line short by exactly one entry's amount leaves that entry out)
Planted failures (meta.deviation): amount (two digits transposed or one digit changed), missing (a look-alike reference
instead of the true one), date (one day beyond the tolerance), split_sum, sign, fee, batch_total.
gen_v4 (2026-10-08) fixes two defects the reviewers named:
  * one name per ledger: the introduction, the table title and the conventions call ledger A and ledger B by the same noun
    phrase (DOM[...]["a_short"] / ["b_short"]); the introduction only varies who keeps the ledger (asserted for every state);
  * the per-line deduction of level 3 is written for both signs: "the figure on the B line is F smaller in size than the figure
    in A, with the sign reversed" (size = the figure without its sign).  Entries of the marked channel now carry plus and minus
    amounts like every other entry, and the truth takes the deduction off the size (failures(): a - sign(a) * F, then reversed).
    Batch entries stay plus figures, so the batch sentences need no sign clause.
Groups of three items on one base (66 per level) plus one group of two per level: the members differ only in the planted
lines of B; `none` is the gold of 100 items, every gold position holds 100 items.  All arithmetic in integer units.
    python3 generators/ledger_reconcile.py
Environment: BENCH_OUT=<dir> writes <dir>/ledger_reconcile/ instead of generated/tasks/ledger_reconcile/; BENCH_SEED=<k> (only with
BENCH_OUT) replaces the root seed 20261007 by k and marks ids, groups and meta with the seed.
"""
import collections
import datetime
import json
import math
import os
import random
import re
import sys

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated")   # items go to HERE/tasks/<family>/ (BENCH_OUT: elsewhere)
TASK = "ledger_reconcile"
DEFAULT_SEED = 20261007
_SEED_ENV = os.environ.get("BENCH_SEED")
_OUT_ENV = os.environ.get("BENCH_OUT")
if _SEED_ENV is not None and not _OUT_ENV:
    sys.stderr.write("error: BENCH_SEED is accepted only together with BENCH_OUT (the published set keeps seed 20261007)\n")
    sys.exit(2)
SEED = int(_SEED_ENV) if _SEED_ENV is not None else DEFAULT_SEED
OUT = os.path.join(_OUT_ENV, TASK) if _OUT_ENV else os.path.join(HERE, "tasks", TASK)
PFX = f"{TASK}:s{SEED}:" if _SEED_ENV is not None else f"{TASK}:"

INSTRUCTIONS = "Which entry of ledger A does not reconcile with ledger B?"
NONE_TEXT = "None: every entry of ledger A reconciles"
LEVEL_N = {1: 8, 2: 14, 3: 22}
KINDS = {1: ["amount", "missing"], 2: ["amount", "missing", "date", "split_sum", "sign"],
         3: ["amount", "missing", "date", "split_sum", "sign", "fee", "batch_total"]}
NONE_GROUPS = {1: 33, 2: 33, 3: 34}          # groups that contain the `none` member: 100 in all
PAIR_TYPE = {1: "full", 2: "none", 3: "full"}  # which kind of group is the one group of two in each level
GROUPS_PER_LEVEL = 67                          # 66 groups of three + 1 group of two = 200 items
TOLS = [1, 2, 3, 5]
LAYOUTS = ["aligned", "pipe", "csv", "kv"]
DOMAIN_KEYS = ["bank", "payables", "stock", "hours", "weight"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


class Retry(Exception):
    pass


def rng_for(*parts):
    return random.Random(":".join(str(p) for p in (SEED, TASK) + parts))


# ------------------------------------------------------------------------------------------------ domains and names
DOM = {
    "bank": {"dec": 2, "lo": 1500, "hi": 900000, "gran": 1, "neg": 0.45, "refp": ["TX", "BK", "RC"], "batchp": "LDG",
             "tags": ["CARD", "TRANSFER", "CHEQUE", "DIRECT"], "feetag": "CARD", "fees": [15, 20, 25, 30, 35, 40, 45, 55, 65],
             "unit": "", "fee_word": "processing fee", "cols": ("reference", "amount", "channel", "lodgement"),
             "a_short": "cash book", "b_short": "bank statement",
             "a_desc": ["the cash book of {org}", "the cash book kept by {org}"],
             "b_desc": ["the bank statement issued by {bank}", "the bank statement that {bank} sent to {org}"]},
    "payables": {"dec": 2, "lo": 4000, "hi": 2500000, "gran": 1, "neg": 0.5, "refp": ["INV", "DOC", "PI"], "batchp": "RUN",
                 "tags": ["WIRE", "SEPA", "CHEQUE", "NETTING"], "feetag": "WIRE", "fees": [50, 75, 90, 120, 150, 180, 250],
                 "unit": "", "fee_word": "transfer charge", "cols": ("doc number", "amount", "method", "payment run"),
                 "a_short": "purchase ledger", "b_short": "supplier statement",
                 "a_desc": ["the purchase ledger of {org} for the supplier {sup}", "the purchase ledger kept by {org} for the supplier {sup}"],
                 "b_desc": ["the supplier statement sent by {sup}", "the supplier statement that {sup} issued to {org}"]},
    "stock": {"dec": 0, "lo": 40, "hi": 6000, "gran": 1, "neg": 0.45, "refp": ["MV", "GM", "SM"], "batchp": "PAL",
              "tags": ["TRUCK", "VAN", "SAMPLE", "RAIL"], "feetag": "SAMPLE", "fees": [1, 2, 3, 4, 5],
              "unit": " units", "fee_word": "retained test sample", "cols": ("movement id", "quantity", "route", "pallet"),
              "a_short": "stock system", "b_short": "receiving log",
              "a_desc": ["the stock system of the {site} store", "the stock system in which the {site} store books its movements"],
              "b_desc": ["the receiving log kept at the {site2} depot", "the receiving log of the {site2} depot"]},
    "hours": {"dec": 2, "lo": 100, "hi": 4000, "gran": 25, "neg": 0.35, "refp": ["TS", "WS"], "batchp": "WK",
              "tags": ["ONSITE", "REMOTE", "TRAVEL", "OFFICE"], "feetag": "TRAVEL", "fees": [25, 50, 75],
              "unit": " h", "fee_word": "travel deduction", "cols": ("sheet id", "hours", "mode", "roll-up"),
              "a_short": "timesheet", "b_short": "client hours log",
              "a_desc": ["the timesheet of the {team} team", "the timesheet kept by the {team} team"],
              "b_desc": ["the client hours log approved by {client}", "the client hours log signed off by {client}"]},
    "weight": {"dec": 1, "lo": 800, "hi": 240000, "gran": 5, "neg": 0.4, "refp": ["DN", "WN"], "batchp": "LOAD",
               "tags": ["PALLET", "LOOSE", "CRATE", "DRUM"], "feetag": "PALLET", "fees": [125, 150, 185, 200, 225, 250],
               "unit": " kg", "fee_word": "pallet tare", "cols": ("note id", "weight", "packing", "load"),
               "a_short": "dispatch register", "b_short": "weighbridge record",
               "a_desc": ["the dispatch register of the {site} plant", "the dispatch register kept at the {site} plant"],
               "b_desc": ["the weighbridge record of the haulier {carrier}", "the weighbridge record kept by the haulier {carrier}"]},
}
SYL1 = ["Bral", "Cosk", "Dulv", "Ferm", "Galt", "Hosk", "Jelv", "Karv", "Lusk", "Mern", "Nolv", "Orst", "Prel", "Quor",
        "Rask", "Selv", "Tarn", "Ulst", "Vasm", "Welk", "Yorv", "Zelt"]
SYL2 = ["ada", "ela", "ion", "ora", "uma", "eth", "ivo", "ansa", "ont", "ure", "ik", "olm", "ast", "evi", "and"]
ORG_SUFFIX = ["Trading", "Works", "Supplies", "Instruments", "Foods", "Textiles", "Components", "Ceramics"]


def word(rng):
    return rng.choice(SYL1) + rng.choice(SYL2)


def make_names(rng):
    w = []
    while len(w) < 8:
        x = word(rng)
        if x not in w:
            w.append(x)
    return {"org": f"{w[0]} {rng.choice(ORG_SUFFIX)}",
            "bank": rng.choice(["{} Savings Bank", "{} Cooperative Bank", "Bank of {}"]).format(w[1]),
            "sup": f"{w[2]} {rng.choice(ORG_SUFFIX)}", "site": w[3], "site2": w[4], "team": w[5],
            "client": f"{w[6]} {rng.choice(ORG_SUFFIX)}", "carrier": f"{w[7]} {rng.choice(['Haulage', 'Freight', 'Transport'])}"}


# ------------------------------------------------------------------------------------------------ numbers
def fmt_num(v, dec, signed=True):
    m = abs(v)
    s = f"{m // 10 ** dec}.{m % 10 ** dec:0{dec}d}" if dec else str(m)
    return (("+" if v >= 0 else "-") + s) if signed else s


def iso(o):
    return datetime.date.fromordinal(o).isoformat()


def ordinal(s):
    return datetime.date.fromisoformat(s).toordinal()


def digit_variants(m, dec):
    """(transpositions, single-digit changes) of the magnitude m; the shown digit count never changes"""
    s = str(m).rjust(dec + 1, "0")
    trans, single = [], []
    for i in range(len(s) - 1):
        if s[i] != s[i + 1]:
            t = s[:i] + s[i + 1] + s[i] + s[i + 2:]
            if t[0] != "0" or s[0] == "0":
                trans.append(int(t))
    for i in range(len(s)):
        for dg in "0123456789":
            if dg != s[i] and not (i == 0 and dg == "0" and s[0] != "0"):
                single.append(int(s[:i] + dg + s[i + 1:]))
    return [x for x in trans if x > 0], [x for x in single if x > 0]


def change_mag(m, dec, rng, g=1):
    """a planted size change that stays on the grid of the domain (quarter hours, half kilograms), so no value stands out"""
    trans, single = [[x for x in v if x % g == 0] for v in digit_variants(m, dec)]
    if trans and rng.random() < 0.5:
        return "transposed", rng.choice(trans)
    return "digit", rng.choice(single)


def lookalike(ref, rng, taken):
    p, num = ref.split("-")
    trans, single = [], []
    for i in range(len(num) - 1):
        if num[i] != num[i + 1]:
            trans.append(num[:i] + num[i + 1] + num[i] + num[i + 2:])
    for i in range(len(num)):
        for dg in "0123456789":
            if dg != num[i] and not (i == 0 and dg == "0"):
                single.append(num[:i] + dg + num[i + 1:])
    trans = [f"{p}-{x}" for x in trans if x[0] != "0" and f"{p}-{x}" not in taken]
    single = [f"{p}-{x}" for x in single if f"{p}-{x}" not in taken]
    pool = trans if trans and rng.random() < 0.6 else single
    if not pool:
        raise Retry("no look-alike")
    return rng.choice(pool)


# ------------------------------------------------------------------------------------------------ truth
def failures(spec, ignore=()):
    """label -> reason for every entry of A that does not reconcile under the written conventions of the spec.
    The per-line deduction F comes off the SIZE of the A figure (written: "the figure on the B line is F smaller in size than the
    figure in A, with the sign reversed"), so a minus figure -100 with F = 0.90 shows as +99.10 in B and a plus figure 100 as -99.10.
    ignore (diagnostics only): 'date' skips the date rule, 'sign' compares sizes only, 'fee' forgets the deduction,
    'signedfee' takes the deduction off the signed figure instead of its size, 'split' reads only the first B line of a reference."""
    flip, D, fee = spec["sign_reversed"], spec["tolerance_days"], spec["fee"]
    byref = collections.defaultdict(list)
    for ln in spec["b"]:
        byref[ln["ref"]].append(ln)

    def date_ok(ad, lns):
        if D is None or "date" in ignore:
            return True
        tol = D - 1 if "strict" in ignore else D
        return all(abs(ordinal(l["date"]) - ad) <= tol for l in lns)

    def same(x, y):
        return abs(x) == abs(y) if "sign" in ignore else x == y

    out, batches = {}, collections.defaultdict(list)
    for e in spec["a"]:
        if e["batch"]:
            batches[e["batch"]].append(e)
            continue
        tagged = fee is not None and e["tag"] == fee["tag"]
        lns = byref.get(e["ref"], [])
        if "split" in ignore:
            lns = lns[:1]
        w = e["amount"]
        if tagged and "fee" not in ignore:
            w -= fee["value"] if (w > 0 or "signedfee" in ignore) else -fee["value"]      # off the size, whatever the sign
        w = -w if flip else w
        got = sum(l["amount"] for l in lns)
        if not lns:
            out[e["label"]] = "missing"
        elif len(lns) > 2:
            out[e["label"]] = "extra_lines"
        elif not same(got, w):
            out[e["label"]] = ("split_sum" if len(lns) == 2 else "fee" if tagged else
                               "sign" if (flip and got == -w) else "amount")
        elif not date_ok(ordinal(e["date"]), lns):
            out[e["label"]] = "date"
    for bref in sorted(batches):
        es = batches[bref]
        lns = byref.get(bref, [])
        total = sum(e["amount"] for e in es)
        if len(lns) != 1:
            for e in es:
                out[e["label"]] = "batch_line"
            continue
        got = lns[0]["amount"]
        g = abs(got) if "sign" in ignore else (-got if flip else got)
        if not date_ok(ordinal(es[0]["date"]), lns):
            for e in es:
                out[e["label"]] = "batch_date"
        elif g != total:
            hit = [e for e in es if total - g == e["amount"]]
            if len(hit) == 1:
                out[hit[0]["label"]] = "batch_total"
            else:
                for e in es:
                    out[e["label"]] = "batch_other"
    return out


def truth(spec):
    f = failures(spec)
    assert len(f) <= 1, f"more than one entry fails: {f}"
    if not f:
        return "none", None
    (lab, why), = f.items()
    return lab, why


def sloppy_score(spec, ignore, cands, gold):
    """expected accuracy of a reader who applies the conventions except `ignore` and guesses among the flagged candidates"""
    f = failures(spec, ignore)
    flagged = [c for c in cands if c in f]
    if not flagged:
        return 1.0 if gold == "none" else 0.0
    return 1.0 / len(flagged) if gold in flagged else 0.0


# ------------------------------------------------------------------------------------------------ one base and its members
TYPE_OF = {"amount": "plain", "missing": "plain", "date": "plain", "sign": "plain", "split_sum": "split", "fee": "tag",
           "batch_total": "batch", "lookalike": "plain", "twin": "plain", "plain": "plain", "date_limit": "plain",
           "split_ok": "split", "fee_ok": "tag", "batch_ok": "batch"}
DECOYS = {1: ["lookalike", "twin", "plain"], 2: ["lookalike", "twin", "date_limit", "split_ok"],
          3: ["date_limit", "split_ok", "fee_ok", "batch_ok", "lookalike", "twin"]}
COVER = {"date": "date", "date_limit": "date", "split_sum": "split", "split_ok": "split", "fee": "fee", "fee_ok": "fee",
         "batch_total": "batch", "batch_ok": "batch"}
NEED = {1: [], 2: ["date", "split"], 3: ["fee", "batch", "split", "date"]}


def choose_decoys(rng, lv, slots, n_dec):
    """near-miss decoys among the candidates: first those that bring a convention of the level the planted slots do not touch"""
    menu = DECOYS[lv][:]
    rng.shuffle(menu)
    need = NEED[lv][:]
    rng.shuffle(need)
    covered = [COVER[k] for k in slots if k in COVER]
    out = []
    for nd in need:
        if len(out) < n_dec and nd not in covered:
            out.append([x for x in menu if COVER.get(x) == nd][0])
            covered.append(nd)
    for dk in menu:
        if len(out) < n_dec and dk not in out:
            out.append(dk)
    assert len(out) == n_dec
    return out


def build_group(rng, lv, dk, members):
    d = DOM[dk]
    n, dec, g = LEVEL_N[lv], d["dec"], d["gran"]
    slots = [k for k in members if k]
    D = None if lv == 1 else rng.choice(TOLS)
    F = rng.choice(d["fees"]) if lv == 3 else None
    decoys = choose_decoys(rng, lv, slots, 5 - len(slots))
    ents = [{"role": "slot", "kind": k, "si": i, "etype": TYPE_OF[k]} for i, k in enumerate(slots)]
    ents += [{"role": "decoy", "kind": k, "etype": TYPE_OF[k]} for k in decoys]
    cnt = collections.Counter(e["etype"] for e in ents)
    if lv >= 2:
        for _ in range(max(2, cnt["split"]) + rng.randint(0, 1) - cnt["split"]):
            ents.append({"role": "filler", "kind": "split", "etype": "split"})
    nb = []
    if lv == 3:
        for _ in range(max(3, cnt["tag"] + 1) - cnt["tag"]):
            ents.append({"role": "filler", "kind": "tag", "etype": "tag"})
        nb = [3, rng.choice([3, 4])]
        rng.shuffle(nb)
        bs = [e for e in ents if e["etype"] == "batch" and e["role"] == "slot"]
        if len(bs) > 2:
            raise Retry("three batch slots")
        for j, e in enumerate(bs):
            e["bi"] = j
        for e in [e for e in ents if e["etype"] == "batch" and e["role"] == "decoy"]:
            e["bi"] = rng.choice([j for j in range(2) if sum(1 for x in ents if x.get("bi") == j) < nb[j]])
        for j in range(2):
            for _ in range(nb[j] - sum(1 for x in ents if x.get("bi") == j)):
                ents.append({"role": "filler", "kind": "batch", "etype": "batch", "bi": j})
    while len(ents) < n:
        ents.append({"role": "filler", "kind": "plain", "etype": "plain"})
    if len(ents) != n:
        raise Retry("too many entries")
    # ---- dates (batch entries share one date) and labels in date order
    year, month = rng.choice([2025, 2026]), rng.randint(1, 12)
    first = datetime.date(year, month, 1).toordinal()
    ndays = datetime.date(year + month // 12, month % 12 + 1, 1).toordinal() - first
    bday = [rng.randrange(ndays) for _ in nb]
    for e in ents:
        e["day"] = bday[e["bi"]] if e["etype"] == "batch" else rng.randrange(ndays)
        e["tie"] = rng.random()
    ents.sort(key=lambda e: (e["day"], e["tie"]))
    for i, e in enumerate(ents):
        e["label"], e["date"] = f"A{i + 1:02d}", first + e["day"]
    # ---- references (one dense number range, so neighbours look alike) and batch numbers
    prefix, base = rng.choice(d["refp"]), rng.randint(10000, 98000)
    taken = set()

    def fresh():
        for _ in range(2000):
            r = f"{prefix}-{base + rng.randint(0, 1500)}"
            if r not in taken:
                taken.add(r)
                return r
        raise Retry("refs")
    for e in ents:
        e["ref"] = fresh()
    brefs = []
    while len(brefs) < len(nb):
        r = f"{d['batchp']}-{rng.randint(1000, 9999)}"
        if r not in taken:
            taken.add(r)
            brefs.append(r)
    # ---- sizes (integer units), signs, twins, tags
    used = set()

    def draw(lo):
        for _ in range(2000):
            m = max(lo, int(round(math.exp(rng.uniform(math.log(lo), math.log(d["hi"]))) / g)) * g)
            if m not in used and m <= d["hi"]:
                used.add(m)
                return m
        raise Retry("sizes")
    for e in ents:
        lo = max(d["lo"], 8 * F) if e["etype"] == "tag" else max(d["lo"], 5 * 10 ** dec) if e["etype"] == "split" else d["lo"]
        e["mag"] = draw(lo)
        # batch entries stay plus figures (the batch sentences carry no sign clause); every other entry, the marked-channel
        # entries included, is minus with the domain's share, so the deduction sentence is exercised on both signs
        e["sign"] = 1 if e["etype"] == "batch" else (-1 if rng.random() < d["neg"] else 1)
    for e in ents:
        if e["kind"] != "twin":
            continue
        partners = [p for p in ents if p is not e and p["etype"] in ("plain", "split") and p["kind"] != "twin"]
        rng.shuffle(partners)
        for p in partners:
            tr = [x for x in digit_variants(p["mag"], dec)[0] if x not in used and d["lo"] <= x <= d["hi"] and x % g == 0]
            if tr:
                used.discard(e["mag"])
                e["mag"] = rng.choice(tr)
                used.add(e["mag"])
                e["sign"], e["twin_of"] = p["sign"], p["label"]
                break
        else:
            raise Retry("no twin")
    other_tags = [t for t in d["tags"] if t != d["feetag"]]
    for e in ents:
        e["tag"] = (d["feetag"] if e["etype"] == "tag" else rng.choice(other_tags)) if lv == 3 else rng.choice(d["tags"])
        e["batch"] = brefs[e["bi"]] if e["etype"] == "batch" else None
        e["amt"] = e["sign"] * e["mag"]
    for e in ents:
        if e["role"] == "slot" and e["kind"] == "missing":
            e["miss_ref"] = lookalike(e["ref"], rng, taken)
            taken.add(e["miss_ref"])
    # ---- ledger B (all lines reconcile in this base)
    sgn = -1 if lv >= 2 else 1

    def expect(e):
        return sgn * (e["amt"] - (e["sign"] * F if (lv == 3 and e["etype"] == "tag") else 0))      # the deduction comes off the size

    def off(kind="any"):
        if lv == 1:
            return rng.choice([-1, 0, 0, 1, 2])
        if kind == "limit":
            return rng.choice([-D, D])
        r = rng.random()
        return 0 if r < 0.35 else rng.choice([-D, D]) if r < 0.65 else rng.randint(-D, D)
    lines = []
    for e in ents:
        if e["etype"] == "batch":
            continue
        w = expect(e)
        if e["etype"] == "split":
            m = abs(w)
            p1 = min(max(int(round(m * rng.uniform(0.25, 0.75) / g)) * g, g), m - g)
            if p1 < 10 ** dec or m - p1 < 10 ** dec:
                raise Retry("small part")
            for p in (p1, m - p1):
                lines.append({"ref": e["ref"], "date": e["date"] + off(), "amount": (1 if w > 0 else -1) * p, "owner": e["label"]})
        else:
            if e["kind"] == "date" and e["role"] == "slot":       # on the limit or one day inside it
                o = rng.choice([-1, 1]) * (D if (D == 1 or rng.random() < 0.6) else D - 1)
            else:
                o = off("limit" if e["kind"] == "date_limit" else "any")
            lines.append({"ref": e["ref"], "date": e["date"] + o, "amount": w, "owner": e["label"]})
    for j in range(len(nb)):
        es = [e for e in ents if e.get("bi") == j]
        lines.append({"ref": brefs[j], "date": es[0]["date"] + off(), "amount": sgn * sum(e["amt"] for e in es), "owner": f"batch{j}"})
    looks = [e for e in ents if e["kind"] == "lookalike"]
    for e in looks:
        r = lookalike(e["ref"], rng, taken)
        taken.add(r)
        lines.append({"ref": r, "date": e["date"] + off(), "amount": expect(e), "owner": None})
    fill = [e for e in ents if e["role"] == "filler" and e["etype"] == "plain"]
    n_orph = max(len(looks), rng.choice([1, 2]) if lv == 1 else rng.choice([2, 3]))
    while sum(1 for l in lines if l["owner"] is None) < n_orph:
        if fill and rng.random() < 0.4:
            e = rng.choice(fill)
            r = lookalike(e["ref"], rng, taken)
            taken.add(r)
            amt = expect(e) if rng.random() < 0.5 else rng.choice([1, -1]) * draw(d["lo"])
            lines.append({"ref": r, "date": e["date"] + off(), "amount": amt, "owner": None})
        else:
            lines.append({"ref": fresh(), "date": first + rng.randrange(ndays), "amount": rng.choice([1, -1]) * draw(d["lo"]), "owner": None})
    rng.shuffle(lines)
    owners = [l["owner"] for l in lines if l["owner"] and l["owner"].startswith("A")]
    if owners == sorted(owners):
        raise Retry("B in the order of A")
    for i, l in enumerate(lines):
        l["label"] = f"B{i + 1:02d}"
    # ---- the failing version of every planted slot (same lines, values changed)
    variants = {}
    for e in ents:
        if e["role"] != "slot":
            continue
        k = e["kind"]
        own = f"batch{e['bi']}" if k == "batch_total" else e["label"]
        idx = [i for i, l in enumerate(lines) if l["owner"] == own]
        new = [dict(lines[i]) for i in idx]
        how = k
        if k == "amount":
            how, m2 = change_mag(abs(new[0]["amount"]), dec, rng, g)
            new[0]["amount"] = (1 if new[0]["amount"] > 0 else -1) * m2
        elif k == "missing":
            new[0]["ref"] = e["miss_ref"]
        elif k == "date":
            new[0]["date"] = e["date"] + (1 if new[0]["date"] > e["date"] else -1) * (D + 1)
        elif k == "sign":
            new[0]["amount"] = -new[0]["amount"]
        elif k == "split_sum":
            j = rng.randrange(2)
            how, m2 = change_mag(abs(new[j]["amount"]), dec, rng, g)
            new[j]["amount"] = (1 if new[j]["amount"] > 0 else -1) * m2
        elif k == "fee":
            how = rng.choice(["no_deduction", "deducted_twice", "other_deduction", "added_not_deducted"])
            if how == "no_deduction":
                v = e["mag"]
            elif how == "added_not_deducted":      # for a minus figure this is the result of taking F off the signed figure
                v = e["mag"] + F
            elif how == "deducted_twice":
                v = e["mag"] - 2 * F
            else:
                step = 25 if dk in ("hours", "weight") else 10 if dec == 2 else 1
                alt = [x for x in digit_variants(F, dec)[0] if x != F and x < 3 * F and x % g == 0] + [F + step] + ([F - step] if F > step else [])
                v = e["mag"] - rng.choice(alt)
            new[0]["amount"] = sgn * e["sign"] * v      # v is a size; the B line carries the sign opposite to the one in A
        elif k == "batch_total":
            new[0]["amount"] = sgn * (sum(x["amt"] for x in ents if x.get("bi") == e["bi"]) - e["amt"])
        assert all(l["amount"] % g == 0 for l in new), "planted value off the grid of the domain"
        assert [(l["ref"], l["date"], l["amount"]) for l in new] != [(lines[i]["ref"], lines[i]["date"], lines[i]["amount"]) for i in idx]
        variants[e["si"]] = (idx, new, how, e["label"])
    # ---- the members
    common = {"level": lv, "domain": dk, "period": f"{MONTHS[month - 1]} {year}", "decimals": dec,
              "tolerance_days": D, "sign_reversed": lv >= 2, "fee": {"tag": d["feetag"], "value": F} if lv == 3 else None,
              "a": [{"label": e["label"], "date": iso(e["date"]), "ref": e["ref"], "tag": e["tag"], "batch": e["batch"],
                     "amount": e["amt"]} for e in ents],
              "candidates": sorted(e["label"] for e in ents if e["role"] in ("slot", "decoy"))}

    def as_spec(blines):
        s = dict(common)
        s["b"] = [{"label": l["label"], "date": iso(l["date"]), "ref": l["ref"], "amount": l["amount"]} for l in blines]
        return s
    assert truth(as_spec(lines)) == ("none", None), "the base must reconcile completely"
    out, si = [], 0
    for k in members:
        b, planted = [dict(l) for l in lines], None
        if k is not None:
            idx, new, how, lab = variants[si]
            si += 1
            for i, nl in zip(idx, new):
                b[i] = nl
            planted = {"entry": lab, "variant": how, "b_lines": [lines[i]["label"] for i in idx]}
        spec = as_spec(b)
        gold, why = truth(spec)
        assert gold == (planted["entry"] if planted else "none") and why == k, (gold, why, k, planted)
        assert gold == "none" or gold in common["candidates"]
        out.append({"spec": spec, "gold": gold, "kind": k, "planted": planted})
    roles = {e["label"]: e["kind"] if e["role"] != "filler" else "filler" for e in ents}
    return out, roles


# ------------------------------------------------------------------------------------------------ text
INTRO = ["Reconciliation for {period}. Ledger A is {a_desc}; ledger B is {b_desc}.",
         "The two records below cover {period}: ledger A, {a_desc}, and ledger B, {b_desc}.",
         "Period under review: {period}. Ledger A is {a_desc}, and ledger B is {b_desc}."]
CONV_HEAD = ["Matching conventions:", "How the two ledgers are matched:", "Conventions for this reconciliation:"]
NUMBERING = ["{i}. ", "({i}) ", "Rule {i}: "]
R_PAIR = ["Each entry of A is matched only with the lines of B that carry exactly the same {ref}.",
          "An entry of A and a line of B belong together when their {ref} values are identical, character for character.",
          "Pairing goes by {ref} alone: an entry of A goes with the B line or lines showing the very same {ref}."]
R_ORDER = ["B lists its lines in its own order, not in the order of A.",
           "The order of the lines in B carries no meaning and differs from the order of A.",
           "Lines in B are not sorted the way A is; their position tells nothing."]
R_ORPHAN = ["Lines of B whose {ref} belongs to no entry of A relate to other business and are ignored.",
            "A line of B that carries no {ref} of A is left aside; it affects no entry.",
            "B may hold extra lines with a {ref} that A does not have; they play no part."]
R_ORPHAN3 = ["Lines of B whose {ref} is neither a {ref} of A nor a {batch} number of A relate to other business and are ignored.",
             "A line of B that carries no {ref} and no {batch} number of A is left aside; it affects no entry.",
             "B may hold extra lines whose {ref} matches nothing in A (no entry, no {batch} number); they play no part."]
R_EQ1 = ["An entry reconciles when B has a line with its {ref} that shows exactly the same {amt}, sign included.",
         "A pair agrees when the {amt} figure in B equals the {amt} figure in A to the last digit, sign included.",
         "An entry of A is in order when its B line shows the identical {amt}, with the same sign."]
R_NODATE = ["Dates are not compared; only the {ref} and the {amt} matter.",
            "The dates of the two ledgers may differ freely; they are not part of the check.",
            "No date check applies: a pair is judged on {ref} and {amt} alone."]
R_SIGN = ["B is kept by the other side, so every {amt} figure appears there with the opposite sign: a plus in A is a minus in B and the other way round.",
          "All {amt} figures in B carry the sign opposite to the one in A.",
          "Signs are mirrored between the two ledgers: what is positive in A is negative in B, and what is negative in A is positive in B."]
R_EQ2 = ["An entry reconciles when the {amt} figure on its B line is its own {amt} figure with the sign reversed and the date rule holds.",
         "A pair agrees when the B {amt} figure equals the A {amt} figure multiplied by -1 and the dates are within the tolerance.",
         "An entry of A is in order when its B line shows the same size of {amt} figure with the opposite sign, inside the date tolerance."]
R_DATE = ["The date of a B line may be up to {D} {days} earlier or later than the date of its A entry; a gap of more than {D} {days} means the entry does not reconcile.",
          "Dates may differ by at most {D} {days} in either direction; a gap of exactly {D} {days} is still accepted, a larger one is not.",
          "A B line dated more than {D} {days} before or after its A entry is not a valid match, so that entry does not reconcile; {D} {days} or less is fine."]
R_SPLIT = ["An entry of A may appear in B as two lines with its {ref}; it then reconciles when the two {amt} figures add up to its {amt} with the sign reversed and both lines pass the date rule.",
           "B sometimes splits one entry into two lines with the same {ref}; together they must give the entry's {amt} with the opposite sign, and each line must be inside the date tolerance.",
           "Two B lines with the same {ref} stand for one entry of A; the entry reconciles when their sum equals its {amt} multiplied by -1 and neither line breaks the date rule."]
# the deduction is taken off the SIZE of the figure (the figure without its sign), so the sentences hold for plus and minus
# figures alike; every variant says what "size" means and what happens to the sign
R_FEE = ["Entries of A with {tag} {fee_tag} reach B less a {fee_word} of {F} each: the {amt} figure on the B line is {F} smaller in size than the {amt} figure in A (the size of a figure is its value without the sign), and its sign is reversed. This holds for plus and minus figures alike. No other {tag} has a deduction.",
         "For every A entry whose {tag} is {fee_tag}, B takes a fixed {fee_word} of {F} per line off the size of the figure (the figure without its sign), whether it is a plus or a minus: the size of the B figure is the size of the A figure less {F}, and the sign is the opposite one. Entries with any other {tag} are not reduced.",
         "A line for an entry with {tag} {fee_tag} is {F} smaller in size in B ({fee_word}; size means the figure without its sign) than in A and carries the opposite sign: a plus of size S in A shows as a minus of size S less {F} in B, and a minus of size S in A as a plus of size S less {F}. Other {tag} values carry no deduction."]
R_BATCH = ["Entries of A that share a {batch} number appear in B as one line whose {ref} is that number and whose {amt} figure is their total with the sign reversed; the date rule compares that line with the date the entries share.",
           "Several A entries with the same {batch} number are shown in B as a single line carrying that number in the {ref} column, for the total of those entries with the opposite sign (date rule as usual, against their common date).",
           "B combines the A entries of one {batch} number into one line with that number as {ref} and their summed {amt}, sign reversed; their own {ref} values do not appear in B, and the line must be within the date tolerance of their common date."]
R_SHORT = ["If such a combined line falls short of that total, in size, by exactly the {amt} of one entry of the {batch}, that entry was left out and does not reconcile; the other entries of the {batch} reconcile.",
           "When a combined line is smaller in size than the total by precisely the {amt} of one of its entries, only that entry fails to reconcile.",
           "A combined line that is short by the exact {amt} of one of its entries means that this one entry is missing from it and does not reconcile, while the rest of the {batch} is fine."]
EQ2_EXC = [["Split entries follow the two-line rule below.", "The two-line rule below covers split entries.",
            "Entries split over two lines are handled by the rule below."],
           ["Split entries, entries with {tag} {fee_tag} and entries with a {batch} number follow their own rules below.",
            "The rules below cover the exceptions: split entries, {tag} {fee_tag} entries and {batch} entries.",
            "Exceptions follow below for split entries, for {tag} {fee_tag} and for entries with a {batch} number."]]
assert all("size" in r and "plus" in r and "minus" in r for r in R_FEE), "every deduction sentence must cover both signs"
AT_MOST = ["At most one entry of A fails to reconcile.", "No more than one entry of A can fail; possibly none does.",
           "Either exactly one entry of A does not reconcile, or every entry does."]
HEAD_A = ["Ledger A ({a_short}), {n} entries:", "LEDGER A - {a_short} - {n} entries", "Ledger A: {a_short} ({n} entries)"]
HEAD_B = ["Ledger B ({b_short}), {n} lines:", "LEDGER B - {b_short} - {n} lines", "Ledger B: {b_short} ({n} lines)"]


def make_look(rng):
    look = {k: rng.randrange(3) for k in ("intro", "head", "num", "pair", "order", "orphan", "eq", "nodate", "sign", "date",
                                          "split", "fee", "batch", "short", "most", "hdr")}
    look.update({"desc_a": rng.randrange(2), "desc_b": rng.randrange(2), "tail": rng.randrange(2)})
    return look


def table_rows(spec):
    d = DOM[spec["domain"]]
    ref, amt, tag, bat = d["cols"]
    dec = spec["decimals"]
    ha = ["entry", "date", ref, tag] + ([bat] if spec["level"] == 3 else []) + [amt]
    ra = [[e["label"], e["date"], e["ref"], e["tag"]] + ([e["batch"] or "-"] if spec["level"] == 3 else []) + [fmt_num(e["amount"], dec)]
          for e in spec["a"]]
    hb = ["line", "date", ref, amt]
    rb = [[l["label"], l["date"], l["ref"], fmt_num(l["amount"], dec)] for l in spec["b"]]
    return ha, ra, hb, rb


def table(header, rows, layout, widths):
    if layout == "csv":
        return [",".join(header)] + [",".join(r) for r in rows]
    if layout == "pipe":
        return ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"] + ["| " + " | ".join(r) + " |" for r in rows]
    if layout == "kv":
        return ["; ".join(f"{h}: {v}" for h, v in zip(header, r)) for r in rows]
    last = len(header) - 1
    return ["  ".join(v.rjust(widths[i]) if i == last else v.ljust(widths[i]) for i, v in enumerate(r)).rstrip() for r in [header] + rows]


def render(spec, look, names, layout, widths):
    d = DOM[spec["domain"]]
    lv, D = spec["level"], spec["tolerance_days"]
    ref, amt, tag, bat = d["cols"]
    fill = {"ref": ref, "amt": amt, "tag": tag, "batch": bat, "D": D, "days": "day" if D == 1 else "days",
            "fee_tag": d["feetag"], "fee_word": d["fee_word"],
            "F": (fmt_num(spec["fee"]["value"], spec["decimals"], signed=False) + d["unit"]) if spec["fee"] else ""}
    rules = [R_PAIR[look["pair"]]]
    if lv == 1:
        rules += [R_EQ1[look["eq"]], R_NODATE[look["nodate"]]]
    else:
        rules += [R_SIGN[look["sign"]], R_EQ2[look["eq"]] + " " + EQ2_EXC[lv - 2][look["eq"]], R_DATE[look["date"]], R_SPLIT[look["split"]]]
    if lv == 3:
        rules += [R_FEE[look["fee"]], R_BATCH[look["batch"]], R_SHORT[look["short"]]]
    side = [R_ORDER[look["order"]], (R_ORPHAN3 if lv == 3 else R_ORPHAN)[look["orphan"]]]
    rules = (rules[:1] + side + rules[1:]) if look["tail"] else (rules + side)
    intro = INTRO[look["intro"]].format(period=spec["period"], a_desc=d["a_desc"][look["desc_a"]].format(**names),
                                        b_desc=d["b_desc"][look["desc_b"]].format(**names))
    ha, ra, hb, rb = table_rows(spec)
    out = [intro, "", CONV_HEAD[look["head"]]]
    out += [NUMBERING[look["num"]].format(i=i + 1) + r.format(**fill) for i, r in enumerate(rules)]
    out += ["", AT_MOST[look["most"]], "", HEAD_A[look["hdr"]].format(a_short=d["a_short"], n=len(ra))]
    out += table(ha, ra, layout, widths["a"])
    out += ["", HEAD_B[look["hdr"]].format(b_short=d["b_short"], n=len(rb))]
    out += table(hb, rb, layout, widths["b"])
    return "\n".join(out)


def check_names(text, dk):
    """one name per ledger: the introduction and the table titles use the noun phrases a_short / b_short of the domain, and no
    name of any other domain's ledgers occurs anywhere in the state (the conventions only say A and B)"""
    d = DOM[dk]
    lines = text.split("\n")
    assert d["a_short"] in lines[0] and d["b_short"] in lines[0], (dk, lines[0])
    ta = [l for l in lines if l.startswith(("Ledger A", "LEDGER A"))]
    tb = [l for l in lines if l.startswith(("Ledger B", "LEDGER B"))]
    assert len(ta) == 1 and len(tb) == 1 and d["a_short"] in ta[0] and d["b_short"] in tb[0], (ta, tb)
    low = text.lower()
    for k2, d2 in DOM.items():
        if k2 != dk:
            assert d2["a_short"] not in low and d2["b_short"] not in low, (dk, k2)


def group_widths(specs):
    w = {"a": None, "b": None}
    for s in specs:
        ha, ra, hb, rb = table_rows(s)
        for key, rows in (("a", [ha] + ra), ("b", [hb] + rb)):
            cur = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
            w[key] = cur if w[key] is None else [max(x, y) for x, y in zip(w[key], cur)]
    return w


# ------------------------------------------------------------------------------------------------ second check from the text
NUM = re.compile(r"^(?:\d+\. |\(\d+\) |Rule \d+: )")


def parse_table(lines):
    """rows of one rendered ledger table as dicts (any of the four layouts); `lines` are the lines after the title"""
    first = lines[0]
    if first.startswith("|"):
        cells = [[c.strip() for c in l.strip("|").split("|")] for l in lines if not re.match(r"^\|[-|]+\|$", l)]
    elif "; " in first and ": " in first:
        return [{kv.split(": ", 1)[0]: kv.split(": ", 1)[1] for kv in l.split("; ")} for l in lines]
    elif "," in first and not re.search(r"\s{2,}", first):
        cells = [l.split(",") for l in lines]
    else:
        cells = [re.split(r"\s{2,}", l.strip()) for l in lines]
    return [dict(zip(cells[0], r)) for r in cells[1:]]


def check_text(item):
    """answer key recomputed from the rendered state and the options ALONE (no spec): reads the numbered conventions (date
    tolerance, whether signs are mirrored, the marked channel and its deduction, which must be written for plus and minus
    figures), parses both tables and applies the rules; the deduction comes off the size of the figure as written"""
    blocks = item["state"].split("\n\n")
    conv = [NUM.sub("", l) for l in blocks[1].split("\n")[1:]]
    tabs = {}
    for b in blocks:
        ls = b.split("\n")
        for side in "AB":
            if ls[0].startswith((f"Ledger {side}", f"LEDGER {side}")):
                tabs[side] = parse_table(ls[1:])
    ha, hb = list(tabs["A"][0]), list(tabs["B"][0])
    decs = set()

    def amount(x):
        t = x.lstrip("+-")
        if "." in t:
            decs.add(len(t.split(".")[1]))
        return (-1 if x.startswith("-") else 1) * int(t.replace(".", ""))
    dated = [r for r in conv if re.search(r"\d+ days?", r)]
    D = int(re.search(r"(\d+) days?", dated[0]).group(1)) if dated else None
    flip = not any(("Dates are not compared" in r or "may differ freely" in r or "No date check applies" in r) for r in conv)
    fee_rule = [r for r in conv if re.search(r"\b[A-Z]{3,}\b", r) and re.search(r"\d", r)
                and not re.search(r"follow their own rules|exceptions|Exceptions|Split entries", r)]
    ref_col, amt_col, tag_col = hb[2], hb[3], ha[3]
    batch_col = ha[4] if len(ha) == 6 else None
    ents = [dict(label=r["entry"], date=ordinal(r["date"]), ref=r[ref_col], tag=r[tag_col], amt=amount(r[ha[-1]]),
                 batch=(r[batch_col] if batch_col and r[batch_col] != "-" else None)) for r in tabs["A"]]
    lns = [dict(ref=r[ref_col], date=ordinal(r["date"]), amt=amount(r[amt_col])) for r in tabs["B"]]
    dec = max(decs) if decs else 0
    fee = F = None
    if fee_rule:
        r = fee_rule[0]
        assert "size" in r and "plus" in r and "minus" in r, r
        fee = re.search(r"\b([A-Z]{3,})\b", r).group(1)
        n = re.search(r"(\d+(?:\.\d+)?)", r).group(1)
        F = int(n.replace(".", "")) if "." in n else int(n) * 10 ** dec
    byref = collections.defaultdict(list)
    for l in lns:
        byref[l["ref"]].append(l)
    bad, batches = [], collections.defaultdict(list)
    for e in ents:
        if e["batch"]:
            batches[e["batch"]].append(e)
            continue
        ls = byref.get(e["ref"], [])
        a = e["amt"]
        if fee and e["tag"] == fee:
            a = a - F if a > 0 else a + F            # F smaller in size, whatever the sign
        exp = -a if flip else a
        if not ls or len(ls) > 2 or sum(l["amt"] for l in ls) != exp:
            bad.append(e["label"])
        elif D is not None and any(abs(l["date"] - e["date"]) > D for l in ls):
            bad.append(e["label"])
    for b, es in batches.items():
        ls = byref.get(b, [])
        tot = sum(e["amt"] for e in es)
        if len(ls) != 1:
            bad += [e["label"] for e in es]
            continue
        got = -ls[0]["amt"] if flip else ls[0]["amt"]
        if D is not None and abs(ls[0]["date"] - es[0]["date"]) > D:
            bad += [e["label"] for e in es]
        elif got != tot:
            bad += [e["label"] for e in es if e["amt"] == tot - got]
    crit = item["questions"]["q"]["criteria"]
    if not bad:
        return next(k for k, v in crit.items() if v == NONE_TEXT)
    assert len(bad) == 1, bad
    return next(k for k, v in crit.items() if v == f"Entry {bad[0]}")


# ------------------------------------------------------------------------------------------------ plan and balance
def make_plan():
    rng = rng_for("plan")
    plan = []
    for lv in (1, 2, 3):
        types = ["none"] * NONE_GROUPS[lv] + ["full"] * (GROUPS_PER_LEVEL - NONE_GROUPS[lv])
        rng.shuffle(types)
        pair_i = rng.choice([i for i, t in enumerate(types) if t == PAIR_TYPE[lv]])
        groups = []
        for i, t in enumerate(types):
            size = 2 if i == pair_i else 3
            groups.append({"level": lv, "type": t, "members": ([None] + ["?"] * (size - 1)) if t == "none" else ["?"] * size})
        nfail = sum(m == "?" for gr in groups for m in gr["members"])
        order = KINDS[lv][:]
        rng.shuffle(order)
        q, r = divmod(nfail, len(order))
        pool = [kd for j, kd in enumerate(order) for _ in range(q + (1 if j < r else 0))]
        rng.shuffle(pool)
        it = iter(pool)
        for gr in groups:
            gr["members"] = [next(it) if m == "?" else None for m in gr["members"]]
        for gr in groups:                       # a base has two batches: at most two batch_total members per group
            while gr["members"].count("batch_total") > 2:
                i = gr["members"].index("batch_total")
                cand = [(h, j) for h in groups if h is not gr and h["members"].count("batch_total") < 2
                        for j, m in enumerate(h["members"]) if m not in (None, "batch_total")]
                h, j = rng.choice(cand)
                gr["members"][i], h["members"][j] = h["members"][j], "batch_total"
        doms = [DOMAIN_KEYS[i % len(DOMAIN_KEYS)] for i in range(GROUPS_PER_LEVEL)]
        lays = [LAYOUTS[i % len(LAYOUTS)] for i in range(GROUPS_PER_LEVEL)]
        rng.shuffle(doms)
        rng.shuffle(lays)
        for gr, dm, la in zip(groups, doms, lays):
            gr["domain"], gr["layout"] = dm, la
        plan += groups
    return plan


def assign_positions(plan):
    """per level 33 rounds of the six positions, each round cut into two triples (distinct positions inside a group), and one
    pair; the two pair positions of the three levels are disjoint, so every position holds exactly 100 golds overall"""
    rng = rng_for("positions")
    extra = list(range(6))
    rng.shuffle(extra)
    for li, lv in enumerate((1, 2, 3)):
        chunks = []
        for _ in range(33):
            p = list(range(6))
            rng.shuffle(p)
            chunks += [p[:3], p[3:]]
        rng.shuffle(chunks)
        it = iter(chunks)
        for gr in [gr for gr in plan if gr["level"] == lv]:
            ch = list(extra[2 * li: 2 * li + 2]) if len(gr["members"]) == 2 else list(next(it))
            rng.shuffle(ch)
            gr["gold_pos"] = ch


SLOPPY = {"date": "ignores the date rule", "strict": "rejects a gap of exactly D days", "sign": "compares sizes only (ignores the sign rule)",
          "split": "reads only the first B line of a reference", "fee": "forgets the per-line deduction",
          "signedfee": "takes the deduction off the signed figure instead of its size"}
SLOPPY_LEVELS = {"date": (2, 3), "strict": (2, 3), "sign": (2, 3), "split": (2, 3), "fee": (3,), "signedfee": (3,)}


def main():
    plan = make_plan()
    assign_positions(plan)
    rows, sloppy = [], collections.defaultdict(list)
    for gi, gr in enumerate(plan):
        for attempt in range(500):
            try:
                members, roles = build_group(rng_for("group", gi, attempt), gr["level"], gr["domain"], gr["members"])
                break
            except Retry:
                continue
        else:
            raise RuntimeError(f"group {gi} could not be built")
        lrng = rng_for("look", gi)
        look, names = make_look(lrng), make_names(lrng)
        widths = group_widths([m["spec"] for m in members])
        cands = members[0]["spec"]["candidates"]
        golds = [m["gold"] for m in members]
        assert len(set(golds)) == len(golds) and all(m["spec"]["candidates"] == cands for m in members)
        order = [None] * 6
        for gk, p in zip(golds, gr["gold_pos"]):
            order[p] = gk
        rest = [k for k in cands + ["none"] if k not in golds]
        rng_for("fill", gi).shuffle(rest)
        it = iter(rest)
        order = [k if k is not None else next(it) for k in order]
        texts = []
        for m in members:
            spec = m["spec"]
            spec["render"] = {"layout": gr["layout"], "look": look, "names": names}
            texts.append(render(spec, look, names, gr["layout"], widths))
            check_names(texts[-1], gr["domain"])
        assert len({t.count("\n") for t in texts}) == 1, "members must have the same number of lines"
        assert len({len(m["spec"]["b"]) for m in members}) == 1
        assert max(map(len, texts)) - min(map(len, texts)) <= 8, [len(t) for t in texts]
        for m, text in zip(members, texts):
            for key, lvls in SLOPPY_LEVELS.items():
                if gr["level"] in lvls:
                    sloppy[(key, gr["level"])].append(sloppy_score(m["spec"], (key,), cands, m["gold"]))
            rows.append({"id": None, "state": text,
                         "questions": {"q": {"type": "choice", "instructions": INSTRUCTIONS,
                                             "criteria": {k: (NONE_TEXT if k == "none" else f"Entry {k}") for k in order}}},
                         "gold": m["gold"], "soft": None, "group": gi,
                         "meta": {"source_id": None, "level": gr["level"], "domain": gr["domain"], "deviation": m["kind"],
                                  "ledger_names": {"A": DOM[gr["domain"]]["a_short"], "B": DOM[gr["domain"]]["b_short"]},
                                  "order": order, "layout": gr["layout"], "seed": SEED,
                                  "group_type": "none + 2 failing" if None in gr["members"] else f"{len(gr['members'])} failing",
                                  "candidates": cands, "candidate_roles": {c: roles[c] for c in cands},
                                  "planted": m["planted"], "spec": m["spec"]}})
    # ---- ids: items shuffled, then numbered; groups numbered in order of first appearance
    rng_for("order").shuffle(rows)
    gnum = {}
    for n, r in enumerate(rows, 1):
        gnum.setdefault(r["group"], len(gnum) + 1)
        r["id"], r["meta"]["source_id"] = f"{PFX}{n:05d}", f"{n:05d}"
        r["group"] = f"{PFX}g{gnum[r['group']]:04d}"
    # ---- balance and uniqueness
    lv_of = lambda r: r["meta"]["level"]
    assert len(rows) == 600 and all(sum(lv_of(r) == lv for r in rows) == 200 for lv in (1, 2, 3))
    for lv in (1, 2, 3):
        assert sum(r["gold"] == "none" and lv_of(r) == lv for r in rows) == NONE_GROUPS[lv]
        kc = collections.Counter(r["meta"]["deviation"] for r in rows if lv_of(r) == lv and r["gold"] != "none")
        assert set(kc) == set(KINDS[lv]) and max(kc.values()) - min(kc.values()) <= 1, kc
        pc = collections.Counter(list(r["questions"]["q"]["criteria"]).index(r["gold"]) for r in rows if lv_of(r) == lv)
        assert sorted(pc.values()) == [33, 33, 33, 33, 34, 34], pc
    pos = collections.Counter(list(r["questions"]["q"]["criteria"]).index(r["gold"]) for r in rows)
    assert all(pos[p] == 100 for p in range(6)), pos
    assert sum(r["gold"] == "none" for r in rows) == 100
    assert len({r["state"] for r in rows}) == 600, "duplicate state"
    assert len({r["group"] for r in rows}) == 3 * GROUPS_PER_LEVEL
    for r in rows:
        assert truth(r["meta"]["spec"])[0] == r["gold"]
    for r in rows:                              # second check: the answer from the rendered text and the options alone
        assert check_text(r) == r["gold"], r["id"]
    # ---- files
    os.makedirs(OUT, exist_ok=True)
    rows.sort(key=lambda r: r["id"])
    with open(os.path.join(OUT, "items.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    lens = {lv: sorted(len(r["state"]) for r in rows if lv_of(r) == lv) for lv in (1, 2, 3)}
    kinds = {lv: collections.Counter(r["meta"]["deviation"] or "none" for r in rows if lv_of(r) == lv) for lv in (1, 2, 3)}
    posl = {lv: collections.Counter(list(r["questions"]["q"]["criteria"]).index(r["gold"]) for r in rows if lv_of(r) == lv) for lv in (1, 2, 3)}
    slop = {k: sum(v) / len(v) for k, v in sloppy.items()}
    split = "generated, seed %d" % SEED
    task = {"task": TASK, "layer": "F", "title": "Generated ledgers: which entry of ledger A does not reconcile with ledger B?",
            "decision": "which of five listed entries of ledger A fails to reconcile with ledger B under the written matching conventions, or none",
            "source": {"name": f"generator build/gen_{TASK}.py", "url": "", "files": [], "split": split, "version": "gen_v4, 2026-10-08: one name per ledger in introduction and table titles; per-line deduction written on the size for plus and minus figures, marked-channel entries of both signs"},
            "licence": "generated by the benchmark's script (no third-party text)", "redistribution": "items included",
            "labels": "programmatic", "item_source": "generated", "metric": "accuracy", "chance": 1 / 6, "rows": len(rows),
            "groups": len({r["group"] for r in rows}), "question_type": "choice", "options": 6,
            "skill": "match two ledgers under written conventions (reference pairing, sign reversal, date tolerance, split lines, per-line deductions, batch totals) and name the one entry that fails",
            "knobs": "entries per ledger 8 / 14 / 22; conventions 3 / 6 / 9 sentences; date tolerance 1-5 days; split, deduction (plus and minus figures) and batch lines; near-miss decoys on the limit",
            "notes": ("600 items, 200 per level. Groups of items on one base that differ only in the planted lines of B (same line count): "
                      "per level 66 groups of three and one group of two (groups of three cannot fill 200 exactly), 201 groups in all; "
                      "100 groups are {none, X, Y} (or {none, X}) and 101 are {X, Y, Z} (or {X, Y}), so `none` is the gold of 100 items "
                      "(33 / 33 / 34 per level). The option order is the same inside a group; every gold position holds 100 items. "
                      "Options: five entry labels of A (key = label, text 'Entry A07') and `none`. Truth is computed on the structured "
                      "specification (meta.spec) in integer units. Level-3 batch rule: a combined B line that is short by exactly the "
                      "amount of one entry of its batch leaves that entry out (written in the state). gen_v4 (2026-10-08): the introduction, the table "
                      "titles and the conventions name each ledger the same way (cash book / bank statement, purchase ledger / supplier statement, "
                      "stock system / receiving log, timesheet / client hours log, dispatch register / weighbridge record), and the level-3 deduction "
                      "sentence says that the B figure is smaller in size by the deduction with the sign reversed, so marked-channel entries now carry "
                      "plus and minus amounts like all others and still exactly one entry fails. State length %d to %d characters."
                      % (min(min(v) for v in lens.values()), max(max(v) for v in lens.values())))}
    json.dump(task, open(os.path.join(OUT, "task.json"), "w"), indent=1)
    write_readme(rows, lens, kinds, posl, slop)
    # ---- summary
    print(f"wrote {len(rows)} items to {OUT}")
    print("kind x level:", {lv: dict(sorted(kinds[lv].items())) for lv in (1, 2, 3)})
    print("gold position x level:", {lv: [posl[lv][p] for p in range(6)] for lv in (1, 2, 3)})
    print("chars min/median/max:", {lv: (v[0], v[len(v) // 2], v[-1]) for lv, v in lens.items()})
    print("sloppy readers (expected accuracy):", {f"{k}@L{lv}": round(v, 3) for (k, lv), v in sorted(slop.items())})
    print("domains:", dict(collections.Counter(r["meta"]["domain"] for r in rows)), "layouts:", dict(collections.Counter(r["meta"]["layout"] for r in rows)))


def fmt_item(it):
    out = [f"id `{it['id']}` (group `{it['group']}`, level {it['meta']['level']}, domain `{it['meta']['domain']}`, "
           f"deviation `{it['meta']['deviation']}`, gold **{it['gold']}**)", "", "```", it["state"], "```", "",
           f"question: {it['questions']['q']['instructions']}", ""]
    out += [f"- `{k}`: {v}" for k, v in it["questions"]["q"]["criteria"].items()]
    return "\n".join(out)


def write_readme(rows, lens, kinds, posl, slop):
    ex = []
    for lv, kd in ((1, "missing"), (2, "date"), (3, "batch_total")):
        ex.append(next(r for r in rows if r["meta"]["level"] == lv and r["meta"]["deviation"] == kd))
    allk = ["none"] + KINDS[3]
    ktab = "\n".join(f"| `{k}` | " + " | ".join(str(kinds[lv].get(k, 0)) for lv in (1, 2, 3)) + f" | {sum(kinds[lv].get(k, 0) for lv in (1, 2, 3))} |" for k in allk)
    ptab = "\n".join(f"| {p + 1} | " + " | ".join(str(posl[lv][p]) for lv in (1, 2, 3)) + f" | {sum(posl[lv][p] for lv in (1, 2, 3))} |" for p in range(6))
    stab = "\n".join(f"| {SLOPPY[k]} | " + " | ".join(f"{slop[(k, lv)]:.3f}" if (k, lv) in slop else "-" for lv in (1, 2, 3)) + " |" for k in SLOPPY)
    ltab = "\n".join(f"| {lv} | {v[0]} | {v[len(v) // 2]} | {v[-1]} |" for lv, v in lens.items())
    l3 = [r["meta"]["spec"] for r in rows if r["meta"]["level"] == 3]
    fe = [[e for e in sp["a"] if e["tag"] == sp["fee"]["tag"]] for sp in l3]
    feeinfo = (f"Marked-channel entries carry plus and minus amounts like all other entries: over the {len(l3)} level-3 states "
               f"{sum(len(x) for x in fe)} marked-channel entries, {sum(e['amount'] < 0 for x in fe for e in x)} of them minus figures; "
               f"{sum(any(e['amount'] < 0 for e in x) for x in fe)} states hold at least one. Batch entries are plus figures.")
    txt = f"""# {TASK}

Generated ledgers: which entry of ledger A does not reconcile with ledger B? (layer F, generated, programmatic truth)

- Decision: which of five listed entries of ledger A fails to reconcile with ledger B under the matching conventions written in the state, or `none`.
- Source: generator `build/gen_{TASK}.py` (standard library only, `random.Random` seeded from {SEED}; identical output on every run); no third-party text.
- Licence: generated by the benchmark's script (no third-party text); items included.
- Rows: 600 (200 per level) in 201 groups; metric: accuracy; chance 1/6 (six options).
- Rebuild: `python3 build/gen_{TASK}.py` (`BENCH_OUT=<dir>` writes elsewhere; `BENCH_SEED=<k>`, only with `BENCH_OUT`, builds a sealed set of the same design).

## What is generated

Two ledgers of one month: a cash book against a bank statement (`bank`), a purchase ledger against a supplier statement (`payables`),
a stock system against a receiving log (`stock`, whole units), a timesheet against a client hours log (`hours`, hundredths of an hour)
and a dispatch register against a weighbridge record (`weight`, tenths of a kilogram). Each ledger has one name per item: the
introduction ("ledger A is the cash book kept by ...; ledger B is the bank statement issued by ...") and the table titles
("Ledger B (bank statement), 10 lines:") use the same noun phrase, and the conventions refer to the ledgers only as A and B; the script asserts for every
state that the introduction and the table titles carry the same name and that no ledger name of another domain occurs
(`meta.ledger_names`). Invented names (syllable generator), references
from one dense number range per item (neighbouring references look alike), four layouts drawn per group (aligned columns, pipe table,
comma-separated, `key: value` lines), three phrasings for every sentence type. Ledger A lists entries `A01`... in date order (entry,
date, reference, channel or similar tag, at level 3 a batch number, signed amount); ledger B lists lines `B01`... in its own order
(line, date, reference, signed amount), including lines that belong to no entry of A. All values are integers in the smallest unit.

The options are five entry labels of A (key = label, text `Entry A07`) and `none`. The five candidates are the entries that fail in
some member of the group plus near-miss decoys that do reconcile: a look-alike reference line beside the true one, an amount whose
digits are a transposition of another entry's amount, a date exactly on the tolerance, a split that adds up, a deduction line that
nets correctly, a member of a batch whose combined line is right (or of the short batch, but not the left-out entry). Non-candidate
entries carry the same features.

## Conventions written into the state (numbered sentences, by level)

- all levels: pairing by reference only (character for character); B in its own order; B lines whose reference matches nothing in A
  are ignored; at most one entry of A fails.
- level 1: an entry reconciles when its B line shows the same amount, sign included; dates are not compared.
- level 2: B shows every amount with the opposite sign; the B date may differ by at most D days either way (D in 1, 2, 3, 5; exactly D
  is accepted); an entry may appear as two B lines with its reference whose amounts add up to it (sign reversed), both inside the tolerance.
- level 3: in addition, entries of one marked channel (plus and minus figures alike) reach B less a fixed deduction per line (fee,
  charge, retained sample, travel deduction, pallet tare); the written rule says that the B figure is smaller in size than the A
  figure by the deduction (size = the figure without its sign) and that its sign is reversed, so -100.00 with a deduction of 0.90
  shows as +99.10 in B and +100.00 as -99.10; entries that share a batch number (all plus figures) appear in B as one line under that number for their total
  (sign reversed, date rule against their common date); a combined line that is short, in size, by exactly the amount of one entry of
  its batch leaves that entry out (it fails; the other entries of the batch reconcile).

{feeinfo}

## Levels

| level | entries in A | lines in B | planted kinds | conventions |
|---|---|---|---|---|
| 1 | 8 | 9-10 | amount, missing | reference, equal amount, extra lines, no date check |
| 2 | 14 | 18-21 | + date, split_sum, sign | + opposite sign, date tolerance, splits |
| 3 | 22 | 21-25 | + fee, batch_total | + per-line deduction of one channel, batch lines |

What makes level 3 hard: every one of the five candidates has to be checked under a different convention, and the deciding check
takes several steps from different places. A deduction line: read the channel in A, the deduction in the rules, take it off the size of the figure (also for
a minus figure), reverse the sign, find the B line by reference and compare, then compare the dates against the tolerance. A batch: collect the 3-4 entries of A
with the batch number (spread over the table), add them, find the combined line in B, reverse its sign, take the difference and find the
one entry whose amount equals it. A split: find both B lines, add them, reverse, compare, check both dates. `none` requires all five
checks to pass. Readers that skip one convention fall to (expected accuracy, guessing among the flagged candidates):

| reader | level 1 | level 2 | level 3 |
|---|---|---|---|
{stab}

## Gold answers

| `meta.deviation` | level 1 | level 2 | level 3 | all |
|---|---|---|---|---|
{ktab}

Gold position (place of the gold key in the option list):

| position | level 1 | level 2 | level 3 | all |
|---|---|---|---|---|
{ptab}

Groups: per level 66 groups of three and one group of two on one base each (200 items; groups of three alone cannot fill 200).
100 groups hold the `none` member (the base) and one or two failing members, 101 groups hold failing members only. The members of a
group share everything but the planted lines of B (same number of lines, the same option order); the planted change is a value:
two digits transposed or one digit changed (`amount`; one part of a split for `split_sum`), a look-alike reference (`missing`), the date
moved from on or one inside the tolerance to one day beyond it (`date`), the sign of A kept (`sign`), no deduction, a double deduction,
another deduction or the deduction added instead of taken off (`fee`; for a minus figure the last one is what taking the deduction off
the signed figure gives), a combined line short by one entry (`batch_total`).

State length (characters):

| level | min | median | max |
|---|---|---|---|
{ltab}

## Checks made by the script

- Names: for every state the introduction contains the name of ledger A and of ledger B that the table titles carry, and no name of
  another domain's ledgers occurs anywhere in the state.
- Deduction sentences: each of the three phrasings names the size of the figure and says what happens to plus and minus figures
  (asserted when the script starts); the truth takes the deduction off the size and still finds at most one failing entry in every
  item, and exactly the planted one in every failing member.
- Text check: `check_text(item)` solves every item again from the rendered state and the options alone (it reads the numbered
  conventions, parses both tables in the layout of the item and applies the written rules, the deduction included) and must give the key.
- `truth(spec)` reconciles every entry of A on the structured specification (integer arithmetic, calendar dates) and asserts that at most
  one entry fails; the base of every group reconciles completely; every failing member fails exactly at its planted entry for exactly the
  planted reason (amount, missing, date, split_sum, sign, fee, batch_total) and nowhere else; the gold is one of the five candidates.
- Inside a group: same candidates, same option order, same number of lines in the state and in B, state lengths within 8 characters,
  the planted lines differ from the base.
- Balance: 200 items per level; `none` = 33 / 33 / 34 items; kinds per level differ by at most one; every gold position holds 100 items
  (33 or 34 per level); no two states are equal; the truth of every written item is recomputed.

## Examples (one per level)

""" + "\n\n".join(fmt_item(x) for x in ex) + """

## Independence from training generators

This generator is new and was written for the benchmark only; it shares no template, sentence, name list or number scheme with the
authors' training-data generators, and no item comes from an existing data set.
"""
    open(os.path.join(OUT, "README.md"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
