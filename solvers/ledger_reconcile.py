"""Independent solver for ledger_reconcile (written from the rendered text alone).

    solve(state, question, options) -> option key

The state is read the way a careful clerk would read it:
  1. five paragraphs: introduction / numbered matching conventions / "at most one entry fails" sentence /
     ledger A / ledger B;
  2. every convention sentence is recognised by its own pattern (the field names - id column, channel column, batch
     column, amount column - are taken from the table headers); an unknown sentence raises;
  3. both tables are read in whatever layout they come (aligned columns, pipe table, comma separated, key: value lines);
  4. every entry of A is checked with integer arithmetic (all numbers scaled to one common number of decimals) and
     calendar dates; entries that are not offered as options are checked as well (consistency check).
     The per-line deduction of the marked channel (three phrasings, one meaning) is taken off the SIZE of the figure,
     the figure without its sign, and the sign is reversed, plus and minus alike: B shows -sign(A) * (|A| - deduction).
     Titles must name the ledgers the introduction names, and A's dates must lie in the period it names.
It raises if the text leaves anything unread or unsettled (unknown sentence, unresolved line, two failing entries, a
failing entry that is not among the options ...).
"""
import datetime
import re

# ----------------------------------------------------------------------------------------------------------------------
# numbers and dates


class Num(object):
    """A decimal number kept as (sign, digits, decimals); converted to a common integer scale later."""

    def __init__(self, text):
        t = text.strip()
        m = re.match(r"^([+-])?(\d+)(?:\.(\d+))?$", t)
        if not m:
            raise ValueError("unreadable number %r" % text)
        self.signed = m.group(1) is not None
        self.neg = m.group(1) == "-"
        self.decimals = len(m.group(3) or "")
        self.digits = int((m.group(2) or "0") + (m.group(3) or ""))

    def scaled(self, decimals):
        v = self.digits * 10 ** (decimals - self.decimals)
        return -v if self.neg else v


def parse_date(text):
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text.strip())
    if not m:
        raise ValueError("unreadable date %r" % text)
    return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


# ----------------------------------------------------------------------------------------------------------------------
# tables


def split_row_kv(line):
    out = []
    for part in line.split("; "):
        if ": " not in part:
            raise ValueError("bad key: value part %r" % part)
        k, v = part.split(": ", 1)
        out.append((k.strip(), v.strip()))
    return out


def read_table(block, first_col, count_word):
    """Return (title, header names, rows) where rows are lists of strings in header order."""
    lines = block.split("\n")
    title = lines[0]
    body = [l for l in lines[1:] if l.strip() != ""]
    m = re.search(r"(\d+) %s" % count_word, title)
    if not m:
        raise ValueError("no count in title %r" % title)
    announced = int(m.group(1))
    if not body:
        raise ValueError("empty table")
    if body[0].startswith(first_col + ": "):                        # key: value lines
        rows = []
        names = None
        for l in body:
            kv = split_row_kv(l)
            nm = [k for k, _ in kv]
            if names is None:
                names = nm
            elif nm != names:
                raise ValueError("kv rows with different keys")
            rows.append([v for _, v in kv])
    elif body[0].startswith("|"):                                    # pipe table
        def cells(l):
            if not (l.startswith("|") and l.endswith("|")):
                raise ValueError("bad pipe row %r" % l)
            return [c.strip() for c in l[1:-1].split("|")]
        names = cells(body[0])
        if not re.match(r"^\|(-+\|)+$", body[1].replace(" ", "")):
            raise ValueError("pipe table without rule line")
        rows = [cells(l) for l in body[2:]]
    elif "," in body[0] and body[0].startswith(first_col + ","):     # comma separated
        names = body[0].split(",")
        rows = [l.split(",") for l in body[1:]]
    elif re.match(r"^%s {2,}" % re.escape(first_col), body[0]):       # aligned columns (2+ spaces between columns)
        names = re.split(r" {2,}", body[0].strip())
        rows = [re.split(r" {2,}", l.strip()) for l in body[1:]]
    else:
        raise ValueError("unknown table layout: %r" % body[0][:60])
    for r in rows:
        if len(r) != len(names):
            raise ValueError("row with %d cells, header has %d: %r" % (len(r), len(names), r))
    if len(rows) != announced:
        raise ValueError("announced %d rows, found %d" % (announced, len(rows)))
    return title, names, rows


# ----------------------------------------------------------------------------------------------------------------------
# conventions


class Rules(object):
    pass


def sentence_patterns(idn, chn, bn, amn):
    """Every sentence the conventions may contain, with the field names of this item filled in.  The key is the kind."""
    I = re.escape(idn)
    A = re.escape(amn)
    C = re.escape(chn) if chn else r"(?!)"
    B = re.escape(bn) if bn else r"(?!)"
    NUM = r"(?P<d>\d+)"
    P = []

    def add(kind, rx):
        P.append((kind, re.compile("^" + rx + "$")))

    # pairing -------------------------------------------------------------------------------------------------------
    add("pair", r"Each entry of A is matched only with the lines of B that carry exactly the same %s\." % I)
    add("pair", r"An entry of A and a line of B belong together when their %s values are identical, character for character\." % I)
    add("pair", r"Pairing goes by %s alone: an entry of A goes with the B line or lines showing the very same %s\." % (I, I))
    # order of B ----------------------------------------------------------------------------------------------------
    add("order", r"B lists its lines in its own order, not in the order of A\.")
    add("order", r"The order of the lines in B carries no meaning and differs from the order of A\.")
    add("order", r"Lines in B are not sorted the way A is; their position tells nothing\.")
    # lines that belong to nothing ---------------------------------------------------------------------------------
    add("ignore", r"B may hold extra lines with a %s that A does not have; they play no part\." % I)
    add("ignore", r"Lines of B whose %s belongs to no entry of A relate to other business and are ignored\." % I)
    add("ignore", r"A line of B that carries no %s of A is left aside; it affects no entry\." % I)
    add("ignore_b", r"A line of B that carries no %s and no %s number of A is left aside; it affects no entry\." % (I, B))
    add("ignore_b", r"Lines of B whose %s is neither a %s of A nor a %s number of A relate to other business and are ignored\." % (I, I, B))
    add("ignore_b", r"B may hold extra lines whose %s matches nothing in A \(no entry, no %s number\); they play no part\." % (I, B))
    # level 1: equal amount, same sign, no dates ------------------------------------------------------------------
    add("same", r"An entry of A is in order when its B line shows the identical %s, with the same sign\." % A)
    add("same", r"An entry reconciles when B has a line with its %s that shows exactly the same %s, sign included\." % (I, A))
    add("same", r"A pair agrees when the %s figure in B equals the %s figure in A to the last digit, sign included\." % (A, A))
    add("nodate", r"The dates of the two ledgers may differ freely; they are not part of the check\.")
    add("nodate", r"Dates are not compared; only the %s and the %s matter\." % (I, A))
    add("nodate", r"No date check applies: a pair is judged on %s and %s alone\." % (I, A))
    # level 2/3: opposite sign ----------------------------------------------------------------------------------------
    add("opp", r"B is kept by the other side, so every %s figure appears there with the opposite sign: a plus in A is a minus in B and the other way round\." % A)
    add("opp", r"All %s figures in B carry the sign opposite to the one in A\." % A)
    add("opp", r"Signs are mirrored between the two ledgers: what is positive in A is negative in B, and what is negative in A is positive in B\.")
    # level 2/3: the main statement (sign reversed, date rule) - three phrasings, two endings each ----------------------
    add("main2", r"An entry reconciles when the %s figure on its B line is its own %s figure with the sign reversed and the date rule holds\. Split entries follow the two-line rule below\." % (A, A))
    add("main2", r"An entry of A is in order when its B line shows the same size of %s figure with the opposite sign, inside the date tolerance\. Entries split over two lines are handled by the rule below\." % A)
    add("main2", r"A pair agrees when the B %s figure equals the A %s figure multiplied by -1 and the dates are within the tolerance\. The two-line rule below covers split entries\." % (A, A))
    add("main3", r"An entry reconciles when the %s figure on its B line is its own %s figure with the sign reversed and the date rule holds\. Split entries, entries with %s (?P<mv>\w+) and entries with a %s(?: number)? follow their own rules below\." % (A, A, C, B))
    add("main3", r"An entry of A is in order when its B line shows the same size of %s figure with the opposite sign, inside the date tolerance\. Exceptions follow below for split entries, for %s (?P<mv>\w+) and for entries with a %s(?: number)?\." % (A, C, B))
    add("main3", r"A pair agrees when the B %s figure equals the A %s figure multiplied by -1 and the dates are within the tolerance\. The rules below cover the exceptions: split entries, %s (?P<mv>\w+) entries and %s entries\." % (A, A, C, B))
    # date tolerance ----------------------------------------------------------------------------------------------------
    add("tol", r"The date of a B line may be up to %s days? earlier or later than the date of its A entry; a gap of more than (?P<d2>\d+) days? means the entry does not reconcile\." % NUM)
    add("tol", r"A B line dated more than %s days? before or after its A entry is not a valid match, so that entry does not reconcile; (?P<d2>\d+) days? or less is fine\." % NUM)
    add("tol", r"Dates may differ by at most %s days? in either direction; a gap of exactly (?P<d2>\d+) days? is still accepted, a larger one is not\." % NUM)
    # split -------------------------------------------------------------------------------------------------------------
    add("split", r"B sometimes splits one entry into two lines with the same %s; together they must give the entry's %s with the opposite sign, and each line must be inside the date tolerance\." % (I, A))
    add("split", r"An entry of A may appear in B as two lines with its %s; it then reconciles when the two %s figures add up to its %s with the sign reversed and both lines pass the date rule\." % (I, A, A))
    add("split", r"Two B lines with the same %s stand for one entry of A; the entry reconciles when their sum equals its %s multiplied by -1 and neither line breaks the date rule\." % (I, A))
    # level 3: deduction ------------------------------------------------------------------------------------------------
    # The three phrasings all say the same thing, in plain words: for an entry of the marked channel the deduction is
    # taken off the SIZE of the figure (the figure without its sign) and the sign is reversed, plus and minus alike:
    # B shows  -sign(A) * (|A| - deduction).   (The older wording, in which the deduction was taken off the signed
    # figure and said nothing about negative figures, is deliberately not recognised any more: it would mean
    # something different.)  Number and unit occur two or three times per sentence; they are compared in read_rules.
    def NU(i):
        return r"(?P<dv%s>\d+(?:\.\d+)?)(?: (?P<u%s>kg|h|units))?" % (i, i)
    add("ded", r"A line for an entry with %s (?P<val>\w+) is %s smaller in size in B \((?P<nm>[a-z ]+); size means the figure without its sign\) "
               r"than in A and carries the opposite sign: a plus of size S in A shows as a minus of size S less %s in B, "
               r"and a minus of size S in A as a plus of size S less %s\. Other %s values carry no deduction\."
        % (C, NU(""), NU("2"), NU("3"), C))
    add("ded", r"Entries of A with %s (?P<val>\w+) reach B less an? (?P<nm>[a-z ]+?) of %s each: the %s figure on the B line is %s smaller in size "
               r"than the %s figure in A \(the size of a figure is its value without the sign\), and its sign is reversed\. "
               r"This holds for plus and minus figures alike\. No other %s has a deduction\."
        % (C, NU(""), A, NU("2"), A, C))
    add("ded", r"For every A entry whose %s is (?P<val>\w+), B takes a fixed (?P<nm>[a-z ]+?) of %s per line off the size of the figure "
               r"\(the figure without its sign\), whether it is a plus or a minus: the size of the B figure is the size of the A figure less %s, "
               r"and the sign is the opposite one\. Entries with any other %s are not reduced\."
        % (C, NU(""), NU("2"), C))
    # level 3: batch lines --------------------------------------------------------------------------------------------
    add("batch", r"Entries of A that share a %s number appear in B as one line whose %s is that number and whose %s figure is their total with the sign reversed; the date rule compares that line with the date the entries share\." % (B, I, A))
    add("batch", r"B combines the A entries of one %s number into one line with that number as %s and their summed %s, sign reversed; their own %s values do not appear in B, and the line must be within the date tolerance of their common date\." % (B, I, A, I))
    add("batch", r"Several A entries with the same %s number are shown in B as a single line carrying that number in the %s column, for the total of those entries with the opposite sign \(date rule as usual, against their common date\)\." % (B, I))
    add("short", r"A combined line that is short by the exact %s of one of its entries means that this one entry is missing from it and does not reconcile, while the rest of the %s is fine\." % (A, B))
    add("short", r"If such a combined line falls short of that total, in size, by exactly the %s of one entry of the %s, that entry was left out and does not reconcile; the other entries of the %s reconcile\." % (A, B, B))
    add("short", r"When a combined line is smaller in size than the total by precisely the %s of one of its entries, only that entry fails to reconcile\." % A)
    return P


MARK = re.compile(r"^(?:\((\d+)\)|(\d+)\.|Rule (\d+):)\s+(.*)$")


def read_rules(par, idn, chn, bn, amn):
    lines = par.split("\n")
    if lines[0] not in ("How the two ledgers are matched:", "Matching conventions:", "Conventions for this reconciliation:"):
        raise ValueError("unknown conventions heading %r" % lines[0])
    pats = sentence_patterns(idn, chn, bn, amn)
    kinds = []
    R = Rules()
    R.tol = None
    R.ded = None
    R.ded_val = None
    expected_no = 1
    for l in lines[1:]:
        m = MARK.match(l)
        if not m:
            raise ValueError("convention line without number marker: %r" % l[:80])
        no = int([g for g in m.groups()[:3] if g is not None][0])
        if no != expected_no:
            raise ValueError("convention numbering jumps: %d, expected %d" % (no, expected_no))
        expected_no += 1
        text = m.group(4)
        hit = None
        for kind, rx in pats:
            mm = rx.match(text)
            if mm:
                hit = (kind, mm)
                break
        if hit is None:
            raise ValueError("unrecognised convention sentence: %r" % text[:120])
        kind, mm = hit
        gd = mm.groupdict()
        if kind == "tol":
            if gd["d"] != gd["d2"]:
                raise ValueError("tolerance numbers differ in %r" % text)
            if R.tol is not None and R.tol != int(gd["d"]):
                raise ValueError("two different tolerances")
            R.tol = int(gd["d"])
            # grammar check: "1 day" vs "2 days"
        if kind == "ded":
            dvs = [gd[k] for k in ("dv", "dv2", "dv3") if gd.get(k) is not None]
            uns = [gd[k] for k in ("u", "u2", "u3") if k in gd]          # None when the figure has no unit
            if len(set(dvs)) != 1 or len(set(uns)) != 1:
                raise ValueError("deduction number or unit differs inside %r" % text)
            want_unit = {"amount": None, "hours": "h", "weight": "kg", "quantity": "units"}.get(amn, "?")
            if want_unit == "?" or uns[0] != want_unit:
                raise ValueError("unit %r does not fit the figure %r in %r" % (uns[0], amn, text))
            if R.ded is not None:
                raise ValueError("two deduction sentences")
            R.ded = Num(dvs[0])
            R.ded_val = gd["val"]
        if kind == "main3":
            R.main3_val = gd["mv"]
        kinds.append(kind)
    R.kinds = kinds
    if R.ded is not None and getattr(R, "main3_val", R.ded_val) != R.ded_val:
        raise ValueError("main statement names %s as the exceptional value, deduction rule names %s" % (R.main3_val, R.ded_val))
    return R


# ----------------------------------------------------------------------------------------------------------------------
# the solver

DIAG = {}               # facts about the last item solved (for the observations in the audit report; not used by solve)


def solve(state, question, options):
    if question.strip() != "Which entry of ledger A does not reconcile with ledger B?":
        raise ValueError("unknown question %r" % question)
    paras = state.split("\n\n")
    if len(paras) != 5:
        raise ValueError("expected 5 paragraphs, found %d" % len(paras))
    intro, conv, atmost, blockA, blockB = paras
    if atmost.strip() not in ("Either exactly one entry of A does not reconcile, or every entry does.",
                              "No more than one entry of A can fail; possibly none does.",
                              "At most one entry of A fails to reconcile."):
        raise ValueError("unknown at-most-one sentence %r" % atmost)
    if not re.match(r"^(Period under review: |Reconciliation for |The two records below cover )", intro):
        raise ValueError("unknown introduction")

    tA, namesA, rowsA = read_table(blockA, "entry", "entries")
    tB, namesB, rowsB = read_table(blockB, "line", "lines")
    if not re.match(r"^(Ledger A|LEDGER A)", tA) or not re.match(r"^(Ledger B|LEDGER B)", tB):
        raise ValueError("bad ledger titles")
    # the kind of ledger named in each title (e.g. "cash book") must be the one the introduction names, A before B
    def ledger_name(t, side):
        for rx in (r"^LEDGER %s - (.+) - \d+ (?:entries|lines)$", r"^Ledger %s \((.+)\), \d+ (?:entries|lines):$",
                   r"^Ledger %s: (.+) \(\d+ (?:entries|lines)\)$"):
            m = re.match(rx % side, t)
            if m:
                return m.group(1)
        raise ValueError("unreadable ledger title %r" % t)
    nameA, nameB = ledger_name(tA, "A"), ledger_name(tB, "B")
    if not (nameA in intro and nameB in intro and intro.index(nameA) < intro.index(nameB)):
        raise ValueError("ledger names %r / %r of the titles do not match the introduction" % (nameA, nameB))
    per = re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December) (\d{4})\b", intro)
    if not per:
        raise ValueError("no period in the introduction")
    period = (int(per.group(2)), ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                                   "October", "November", "December"].index(per.group(1)) + 1)
    # column roles
    if namesA[:2] != ["entry", "date"] or namesB[:2] != ["line", "date"]:
        raise ValueError("unexpected leading columns %r %r" % (namesA, namesB))
    if len(namesA) == 5:
        idn, chn, amn = namesA[2], namesA[3], namesA[4]
        bn = None
    elif len(namesA) == 6:
        idn, chn, bn, amn = namesA[2], namesA[3], namesA[4], namesA[5]
    else:
        raise ValueError("unexpected columns of A %r" % namesA)
    if namesB != ["line", "date", idn, amn]:
        raise ValueError("columns of B %r do not fit A %r" % (namesB, namesA))

    R = read_rules(conv, idn, chn, bn, amn)
    kinds = set(R.kinds)
    # which family of conventions is this?
    if "same" in kinds:
        if not ("nodate" in kinds and "pair" in kinds and "order" in kinds and "ignore" in kinds):
            raise ValueError("level-1 conventions incomplete: %r" % R.kinds)
        if kinds & {"opp", "tol", "split", "ded", "batch", "short", "main2", "main3", "ignore_b"} or bn:
            raise ValueError("mixed conventions %r" % R.kinds)
        sign, use_dates, has_split, has_batch = 1, False, False, False
    else:
        if "nodate" in kinds or "tol" not in kinds or "pair" not in kinds or "order" not in kinds or "split" not in kinds:
            raise ValueError("level-2/3 conventions incomplete: %r" % R.kinds)
        sign, use_dates, has_split = -1, True, True
        if "opp" not in kinds and not (kinds & {"main2", "main3"}):
            raise ValueError("no sign rule")
        if bn:
            if not ({"ded", "batch", "short", "main3", "ignore_b"} <= kinds):
                raise ValueError("level-3 conventions incomplete: %r" % R.kinds)
            has_batch = True
            if kinds & {"main2", "ignore"}:
                raise ValueError("mixed conventions %r" % R.kinds)
        else:
            if not ("main2" in kinds and "ignore" in kinds) or kinds & {"ded", "batch", "short", "main3", "ignore_b"}:
                raise ValueError("level-2 conventions inconsistent: %r" % R.kinds)
            has_batch = False

    # numbers on one integer scale ---------------------------------------------------------------------------------
    nums = []
    for r in rowsA:
        nums.append(Num(r[-1]))
    for r in rowsB:
        nums.append(Num(r[-1]))
    for n in nums:
        if not n.signed:
            raise ValueError("amount without a sign")
    if R.ded is not None:
        nums.append(R.ded)
    dec = max(n.decimals for n in nums)

    A = []
    for r in rowsA:
        e = {"label": r[0], "date": parse_date(r[1]), "id": r[2], "ch": r[3], "amt": Num(r[-1]).scaled(dec)}
        e["batch"] = None
        if bn:
            e["batch"] = None if r[4] == "-" else r[4]
        A.append(e)
    Bl = []
    for r in rowsB:
        Bl.append({"label": r[0], "date": parse_date(r[1]), "id": r[2], "amt": Num(r[-1]).scaled(dec)})
    for e in A:
        if (e["date"].year, e["date"].month) != period:
            raise ValueError("%s is dated outside the period named in the introduction" % e["label"])
    if len(set(e["label"] for e in A)) != len(A) or len(set(b["label"] for b in Bl)) != len(Bl):
        raise ValueError("repeated labels")
    if len(set(e["id"] for e in A)) != len(A):
        raise ValueError("an id occurs twice in A")
    ded = R.ded.scaled(dec) if R.ded is not None else 0

    def date_ok(da, db):
        if not use_dates:
            return True
        return abs((da - db).days) <= R.tol

    byid = {}
    for b in Bl:
        byid.setdefault(b["id"], []).append(b)

    fails = {}          # label -> reason
    etype = {}          # label -> kind of entry (diagnostics only)
    stat = {"marked": 0, "marked_neg": 0, "split": 0, "marked_fail": 0, "batches": len(set(e["batch"] for e in A if e["batch"])),
            "extra_b": 0, "n_a": len(A), "n_b": len(Bl)}

    # pass 1: plain entries and deduction entries ------------------------------------------------------------------
    batches = {}
    for e in A:
        if e["batch"] is not None:
            batches.setdefault(e["batch"], []).append(e)
    for e in A:
        if e["batch"] is not None:
            if R.ded is not None and e["ch"] == R.ded_val:
                raise ValueError("%s is both in a batch and in the deduction channel; the text does not say what then" % e["label"])
            etype[e["label"]] = "batch"
            continue
        marked = R.ded is not None and e["ch"] == R.ded_val
        d = ded if marked else 0
        etype[e["label"]] = "marked" if marked else "plain"
        if marked:
            stat["marked"] += 1
            stat["marked_neg"] += e["amt"] < 0
        if marked:
            # the deduction is taken off the SIZE of the figure (value without its sign), then the sign is reversed
            size = abs(e["amt"]) - ded
            if e["amt"] == 0 or size <= 0:
                raise ValueError("%s: figure not larger in size than the deduction; the text does not say what B shows then" % e["label"])
            want = -size if e["amt"] > 0 else size
        else:
            want = sign * e["amt"]            # what B must show (sum of the lines)
        lines = byid.get(e["id"], [])
        if len(lines) == 0:
            fails[e["label"]] = "missing"
        elif len(lines) == 1:
            b = lines[0]
            if b["amt"] != want:
                fails[e["label"]] = "amount"
            elif not date_ok(e["date"], b["date"]):
                fails[e["label"]] = "date"
        elif len(lines) == 2 and has_split:
            stat["split"] += 1
            etype[e["label"]] += "+split"
            if d:
                raise ValueError("%s: split entry in the deduction channel; the text does not say how the deduction applies" % e["label"])
            if sum(b["amt"] for b in lines) != want:
                fails[e["label"]] = "split_sum"
            elif not all(date_ok(e["date"], b["date"]) for b in lines):
                fails[e["label"]] = "date"
        else:
            raise ValueError("%s: %d lines with its id, the conventions do not cover that" % (e["label"], len(lines)))

    # pass 2: batches ------------------------------------------------------------------------------------------------
    for key, members in batches.items():
        if not has_batch:
            raise ValueError("batch values without a batch rule")
        if len(members) < 2:
            raise ValueError("batch %s has a single member" % key)
        dates = set(m["date"] for m in members)
        if len(dates) != 1:
            raise ValueError("batch %s: members do not share a date" % key)
        cd = list(dates)[0]
        if key in set(e["id"] for e in A):
            raise ValueError("batch number %s is also an entry id" % key)
        for m in members:
            if m["id"] in byid:
                raise ValueError("%s: its own id appears in B although it belongs to a batch" % m["label"])
        lines = byid.get(key, [])
        if len(lines) != 1:
            raise ValueError("batch %s: %d combined lines" % (key, len(lines)))
        b = lines[0]
        total = sum(m["amt"] for m in members)
        if not date_ok(cd, b["date"]):
            for m in members:
                fails[m["label"]] = "date"
            continue
        if b["amt"] == sign * total:
            continue
        # short by one entry?  (size: |B| = |total| - |amount of the left-out entry|, same direction as the total)
        left = [m for m in members if b["amt"] == sign * (total - m["amt"])]
        if len(left) == 1:
            if abs(b["amt"]) >= abs(total):
                raise ValueError("combined line is not smaller in size")
            fails[left[0]["label"]] = "batch_total"
        elif len(left) > 1:
            raise ValueError("batch %s: two entries have the amount that is missing, the text cannot say which one was left out" % key)
        else:
            for m in members:
                fails[m["label"]] = "batch_other"

    # lines of B that match no entry and no batch are ignored; nothing else to check
    # options ---------------------------------------------------------------------------------------------------------
    labels = set(e["label"] for e in A)
    optA = {}
    none_key = None
    for k, t in options.items():
        mm = re.match(r"^Entry (A\d+)$", t)
        if mm:
            if mm.group(1) != k:
                raise ValueError("option key %s does not match its text %r" % (k, t))
            if k not in labels:
                raise ValueError("option %s is not an entry of A" % k)
            optA[k] = True
        elif t.startswith("None: every entry of ledger A reconciles"):
            if none_key is not None:
                raise ValueError("two none options")
            none_key = k
        else:
            raise ValueError("unknown option text %r" % t)
    if none_key is None:
        raise ValueError("no none option")

    known_ids = set(e["id"] for e in A) | set(e["batch"] for e in A if e["batch"])
    stat["extra_b"] = sum(1 for b in Bl if b["id"] not in known_ids)
    stat["marked_fail"] = sum(1 for e in A if e["label"] in fails and R.ded is not None and e["ch"] == R.ded_val)
    DIAG.clear()
    DIAG.update(etype=etype, stat=stat, fails=dict(fails), kinds=list(R.kinds), tol=R.tol, ded=(R.ded_val, ded, dec), options=list(options))
    if len(fails) > 1:
        raise ValueError("more than one entry fails: %s" % ", ".join("%s(%s)" % kv for kv in sorted(fails.items())))
    if not fails:
        return none_key
    (lab, why), = fails.items()
    if lab not in optA:
        raise ValueError("the failing entry %s (%s) is not offered as an option" % (lab, why))
    return lab
