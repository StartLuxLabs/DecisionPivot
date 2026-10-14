"""Task clause_change (layer E, generated, programmatic truth):
"Does the change between the two versions alter the answer to the point at issue?"

State.  One text string: an opening line (agreement, two invented parties), five reading rules, VERSION A and
VERSION B of a short agreement (numbered clauses, one clause per line) and a CASE (one fact per line, then one line
"Point at issue: ...?").  Options (fixed texts): `same`, `yes_only_A`, `yes_only_B`.

Clauses.  Twelve parameterised clause types (notice period, grace period for payment, liability cap, warranty period,
return window, volume threshold, cancellation for late delivery, yearly price rise, service credit, retention of
records, response time, deposit).  Every type is a rule "status holds  <=>  fact (>=, >, <=, <) limit": a direction
(floor or ceiling), a number and a limit wording that either counts the stated figure ("at least 30 days", "30 days or
more", "no later than 30 days") or does not ("more than 30 days", "under 30 days").  `clause_ok` implements exactly
that; the flag "counts / does not count" of every wording is cross-checked against the word lists that the reading
rule prints in the state.  Plain clauses without a number fill the agreement.

Version pair.  One clause became stricter from A to B and one looser (kinds: only the number changed, only the limit
wording changed, both).  From level 2 a third clause changed too (no point at issue depends on it; the case carries
one background fact about it) and one unchanged clause stands in another place, so that the numbers of the two live
clauses differ between the versions.  At level 3 a clause is inserted in B and the point at issue is a request with
two conditions (one on a live clause, one on an unchanged clause; both must hold).

Groups.  Three cases on one version pair (the versions are identical in the members; only the case lines differ and
their number is the same): the answer is yes under A only, yes under B only, the same under both.  The point at issue
is asked in two polarities ("was the notice given in time?" / "was the notice given too late?"), so a stricter clause
gives `yes_only_A` for one polarity and `yes_only_B` for the other: for every clause type and direction of change
the three classes are balanced.  `same` cases are near misses: the fact lies one step outside the band between the
old and the new limit (or on a limit where the wording keeps the answer), or - level 3 - inside the band while the
other condition of the request fails.

600 items: 201 version pairs (67 per level); one pair per level has two cases instead of three so that every level
has exactly 200 items and every class exactly 200 (200 is not a multiple of 3).

Environment: BENCH_OUT=<dir> writes <dir>/clause_change/ instead of generated/tasks/clause_change/; BENCH_SEED=<int> (only with
BENCH_OUT) builds a second set of the same design from another seed (ids "clause_change:s<seed>:<5-digit>").
    python3 generators/clause_change.py
"""
import collections
import itertools
import json
import os
import random
import re
import sys

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated")   # items go to HERE/tasks/<family>/ (BENCH_OUT: elsewhere)
TASK = "clause_change"
DEFAULT_SEED = 20261007
_ENV_SEED, _ENV_OUT = os.environ.get("BENCH_SEED"), os.environ.get("BENCH_OUT")
if _ENV_SEED is not None and not _ENV_OUT:
    sys.stderr.write("gen_clause_change.py: BENCH_SEED is accepted only together with BENCH_OUT (the published set is never "
                     "overwritten by another seed); nothing was written.\n")
    sys.exit(2)
SEED = int(_ENV_SEED) if _ENV_SEED is not None else DEFAULT_SEED
SEALED = _ENV_SEED is not None
OUT_DIR = os.path.join(_ENV_OUT, TASK) if _ENV_OUT else os.path.join(HERE, "tasks", TASK)
ID_PREFIX = f"{TASK}:s{SEED}" if SEALED else TASK
ROOT = random.Random(SEED)
SALT = ROOT.getrandbits(64)                        # every generator of the script is derived from random.Random(SEED)

INSTRUCTIONS = "Does the change between the two versions alter the answer to the point at issue?"
OPTIONS = {"same": "The answer to the point at issue is the same under version A and under version B (yes under both, or no under both).",
           "yes_only_A": "The answer to the point at issue is yes under version A and no under version B.",
           "yes_only_B": "The answer to the point at issue is no under version A and yes under version B."}
CLASSES = ["same", "yes_only_A", "yes_only_B"]
KINDS = ["number", "wording", "number_and_wording"]
GROUPS_PER_LEVEL = 67


def rng_for(*parts):
    return random.Random(f"{SALT}:{TASK}:" + ":".join(str(p) for p in parts))


# ------------------------------------------------------------------------------------------------ limit wordings
# (template, the stated figure counts).  Floor sets: the fact must reach the limit; ceiling sets: it must stay in it.
LIMS = {
    "floor_count": [("at least {n} {u}", True), ("{n} {u} or more", True), ("no fewer than {n} {u}", True),
                    ("more than {n} {u}", False), ("over {n} {u}", False)],
    "floor_before": [("at least {n} {u}", True), ("{n} {u} or more", True), ("no fewer than {n} {u}", True),
                     ("no later than {n} {u}", True), ("more than {n} {u}", False), ("over {n} {u}", False)],
    "floor_share": [("at least {n} {u}", True), ("{n} {u} or more", True), ("no less than {n} {u}", True),
                    ("more than {n} {u}", False), ("over {n} {u}", False)],
    "ceil_after": [("no later than {n} {u}", True), ("at most {n} {u}", True), ("no more than {n} {u}", True),
                   ("{n} {u} or fewer", True), ("fewer than {n} {u}", False), ("less than {n} {u}", False),
                   ("under {n} {u}", False)],
    "ceil_amount": [("at most {n} {u}", True), ("no more than {n} {u}", True), ("{n} {u} or less", True),
                    ("less than {n} {u}", False), ("under {n} {u}", False), ("below {n} {u}", False)],
    "ceil_share": [("at most {n} {u}", True), ("no more than {n} {u}", True), ("{n} {u} or less", True),
                   ("less than {n} {u}", False), ("under {n} {u}", False)],
}
# the word lists of the reading rule on limits (printed in every state); LIMS is checked against them below
INCL_WORDS = ["at least", "at most", "no more than", "no fewer than", "no less than", "no later than", "or more", "or fewer", "or less"]
EXCL_WORDS = ["more than", "fewer than", "less than", "over", "under", "below"]
FLOOR_WORDS = ["at least", "no fewer than", "no less than", "or more", "more than", "over"]
CEIL_WORDS = ["at most", "no more than", "or fewer", "or less", "fewer than", "less than", "under", "below"]


def _words_in(expr, words):
    """the listed wordings an expression is built from; "no more than" is not "more than" (longest wording wins)"""
    hit = [w for w in words if re.search(r"\b" + w + r"\b", expr)]
    return [w for w in hit if not any(w != v and w in v and re.search(r"\b" + v + r"\b", expr) for v in INCL_WORDS + EXCL_WORDS)]


def check_lims():
    for name, exprs in LIMS.items():
        assert sum(i for _, i in exprs) >= 3 and sum(not i for _, i in exprs) >= 2, name
        for tpl, incl in exprs:
            e = tpl.replace("{n}", "30").replace("{u}", "days")
            inc, exc = _words_in(e, INCL_WORDS), _words_in(e, EXCL_WORDS)
            assert len(inc) + len(exc) == 1 and bool(inc) == incl, (name, tpl, inc, exc)
            w = (inc + exc)[0]
            if w == "no later than":
                assert name in ("floor_before", "ceil_after")
            else:
                assert (w in FLOOR_WORDS) == name.startswith("floor") and (w in CEIL_WORDS) == name.startswith("ceil"), (name, tpl)


# ------------------------------------------------------------------------------------------------ clause types
# dir: floor = the status holds when the fact is >= (or >) the limit, ceiling = when it is <= (or <) the limit.
# k: range of limit / step; steps: grid of the facts; widths: distance old limit - new limit in steps.
W_STD, W_SMALL = (2, 3, 4, 5, 6, 8, 10, 12), (2, 3, 4, 5)
TYPES = {
    "notice": dict(dir="floor", unit="days", lims="floor_before", head="Termination", fam="notice", k=(14, 75), steps=(1,), widths=W_STD,
        frames=["Either party may end this agreement by written notice given {LIM} before the intended end date.",
                "A written notice of termination is in time only if it is given {LIM} before the intended end date.",
                "To end this agreement, a party must give written notice {LIM} before the intended end date."],
        facts=["The {actor} gave written notice of termination {x} days before the intended end date.",
               "Written notice of termination was given by the {actor} {x} days before the intended end date.",
               "{x} days before the intended end date, the {actor} gave written notice of termination."],
        qpos=["was the notice of termination given in time?", "does the notice of termination meet the notice period?"],
        qneg=["was the notice of termination given too late?", "does the notice of termination fall short of the notice period?"],
        cond="the notice of termination was given in time"),
    "grace": dict(dir="ceiling", unit="days", lims="ceil_after", head="Payment", fam="payment", k=(6, 40), steps=(1,), widths=W_STD,
        frames=["A payment is made in time if the {P1} receives it {LIM} after its due date.",
                "An invoice is paid in time when the money reaches the {P1} {LIM} after the due date.",
                "The {P2} pays in time if its payment arrives {LIM} after the due date of the invoice."],
        facts=["The {P1} received the {P2}'s payment of an invoice {x} days after its due date.",
               "The {P2} paid an invoice, and the money reached the {P1} {x} days after the due date.",
               "{x} days after the due date of an invoice, the {P2}'s payment arrived."],
        qpos=["was the payment made in time?", "did the {P2} pay the invoice in time?"],
        qneg=["was the payment late?", "did the {P2} pay the invoice too late?"],
        cond="the payment was made in time"),
    "cap": dict(dir="ceiling", unit="{cur}", lims="ceil_amount", head="Liability", fam="claim", k=(20, 120), steps=(100, 250, 500), widths=W_STD,
        frames=["The {P1} pays a claim for damages in full if the amount claimed is {LIM}.",
                "A claim for damages against the {P1} is payable in full when the amount claimed is {LIM}.",
                "Where the amount claimed as damages is {LIM}, the {P1} must pay the claim in full."],
        facts=["The {P2} claims damages of {x} {cur} from the {P1}.",
               "A claim for damages of {x} {cur} has been made against the {P1}.",
               "The {P2} has claimed {x} {cur} in damages from the {P1}."],
        qpos=["is the claim for damages payable in full?", "must the {P1} pay the whole amount claimed?"],
        qneg=["is the amount claimed too high to be paid in full?", "may the {P1} decline to pay the claim in full?"],
        cond="the claim for damages is payable in full"),
    "warranty": dict(dir="ceiling", unit="months", lims="ceil_after", head="Warranty", fam="defect", k=(6, 36), steps=(1,), widths=W_STD,
        frames=["The warranty covers a defect if the {P2} reports it {LIM} after delivery.",
                "A defect is covered by the warranty when it is reported {LIM} after delivery.",
                "Warranty cover applies to a defect that is reported {LIM} after delivery."],
        facts=["The {P2} reported a defect {x} months after delivery.",
               "A defect was reported to the {P1} {x} months after delivery.",
               "{x} months after delivery, the {P2} reported a defect."],
        qpos=["is the defect covered by the warranty?", "was the defect reported in time for the warranty?"],
        qneg=["is the defect outside the warranty?", "was the defect reported too late for the warranty?"],
        cond="the defect is covered by the warranty"),
    "returns": dict(dir="ceiling", unit="days", lims="ceil_after", head="Returns", fam="return", k=(7, 45), steps=(1,), widths=W_STD,
        frames=["The {P2} may return {items} if it sends them back {LIM} after receiving them.",
                "A return of {items} is in time when they are sent back {LIM} after receipt.",
                "The {P1} must accept returned {items} that were sent back {LIM} after receipt."],
        facts=["The {P2} sent {items} back {x} days after receiving them.",
               "Some {items} were sent back to the {P1} {x} days after receipt.",
               "{x} days after receipt, the {P2} sent {items} back to the {P1}."],
        qpos=["was the return made in time?", "is the {P2} entitled to make this return?"],
        qneg=["was the return made too late?", "is the {P2} no longer entitled to make this return?"],
        cond="the return was made in time"),
    "volume": dict(dir="floor", unit="units", lims="floor_count", head="Volume pricing", fam="order", k=(20, 80), steps=(1, 5, 10, 25), widths=W_STD,
        frames=["The reduced unit price applies to a single order of {LIM}.",
                "An order qualifies for the reduced unit price if it covers {LIM}.",
                "The {P2} is charged the reduced unit price for any single order of {LIM}."],
        facts=["The {P2} placed a single order of {x} units.",
               "A single order of {x} units was placed by the {P2}.",
               "The {P2} ordered {x} units in a single order."],
        qpos=["does the reduced unit price apply to the order?", "does the order qualify for the reduced unit price?"],
        qneg=["is the order too small for the reduced unit price?", "does the order miss the reduced unit price?"],
        cond="the order qualifies for the reduced unit price"),
    "latecancel": dict(dir="floor", unit="days", lims="floor_count", head="Late delivery", fam="order", k=(6, 40), steps=(1,), widths=W_STD,
        frames=["The {P2} may cancel an order if its delivery is late by {LIM}.",
                "An order may be cancelled by the {P2} once its delivery is late by {LIM}.",
                "Where the delivery of an order is late by {LIM}, the {P2} has the right to cancel it."],
        facts=["The delivery of an order reached the {P2} {x} days late.",
               "The {P1} delivered an order {x} days late.",
               "An order was delivered to the {P2} {x} days late."],
        qpos=["may the {P2} cancel the order?", "does the delay give the {P2} the right to cancel the order?"],
        qneg=["is the delay too short for the {P2} to cancel the order?", "must the {P2} keep the order despite the delay?"],
        cond="the {P2} may cancel the order"),
    "pricerise": dict(dir="ceiling", unit="percent", lims="ceil_share", head="Price changes", fam="price", k=(6, 15), steps=(1,), widths=W_SMALL,
        frames=["The {P1} may raise its prices once per contract year by {LIM}.",
                "A yearly price increase is permitted if it amounts to {LIM}.",
                "Once in each contract year the {P1} may increase its prices by {LIM}."],
        facts=["The {P1} announced a price increase of {x} percent for the coming contract year.",
               "For the coming contract year the {P1} raised its prices by {x} percent.",
               "A price increase of {x} percent for the coming contract year was announced by the {P1}."],
        qpos=["is the price increase permitted?", "may the {P1} raise its prices by that much?"],
        qneg=["is the price increase too high?", "does the price increase go beyond what the agreement permits?"],
        cond="the price increase is permitted"),
    "credit": dict(dir="floor", unit="hours", lims="floor_count", head="Service credits", fam="downtime", k=(6, 40), steps=(1,), widths=W_STD,
        frames=["A service credit is due for a calendar month in which {system} is unavailable for {LIM}.",
                "The {P1} owes a service credit for a calendar month if {system} is down for {LIM} in that month.",
                "Where {system} is unavailable for {LIM} during one calendar month, a service credit is due for that month."],
        facts=["During the last calendar month {system} was unavailable for {x} hours.",
               "In the last calendar month {system} was down for {x} hours in total.",
               "The downtime of {system} in the last calendar month came to {x} hours."],
        qpos=["is a service credit due for that month?", "does the {P1} owe a service credit for that month?"],
        qneg=["does that month pass without a service credit?", "was the downtime too short for a service credit?"],
        cond="a service credit is due for that month"),
    "retention": dict(dir="floor", unit="months", lims="floor_count", head="Records", fam="records", k=(12, 96), steps=(1,), widths=W_STD,
        frames=["The {P1} may destroy the {records} once it has kept them for {LIM} after the end of this agreement.",
                "The {records} may be destroyed when they have been kept for {LIM} after the end of this agreement.",
                "Destroying the {records} is allowed only after the {P1} has kept them for {LIM} from the end of this agreement."],
        facts=["After the agreement ended, the {P1} kept the {records} for {x} months and then destroyed them.",
               "The {P1} destroyed the {records} after keeping them for {x} months from the end of the agreement.",
               "The {records} were kept for {x} months after the end of the agreement and were then destroyed."],
        qpos=["was the {P1} allowed to destroy the {records} at that time?", "had the {records} been kept long enough?"],
        qneg=["were the {records} destroyed too early?", "did the {P1} destroy the {records} before it was allowed to?"],
        cond="the {records} had been kept long enough"),
    "response": dict(dir="ceiling", unit="hours", lims="ceil_after", head="Response time", fam="response", k=(6, 60), steps=(1,), widths=W_STD,
        frames=["The response time is met if the {P1} answers a {ticket} {LIM} after receiving it.",
                "The {P1} meets the response time when it answers a {ticket} {LIM} after receipt.",
                "For the response time to be met, a {ticket} must be answered {LIM} after it is received."],
        facts=["The {P1} answered a {ticket} {x} hours after receiving it.",
               "A {ticket} was answered by the {P1} {x} hours after receipt.",
               "{x} hours after receiving a {ticket}, the {P1} answered it."],
        qpos=["was the response time met?", "did the {P1} answer in time?"],
        qneg=["was the response time missed?", "did the {P1} answer too late?"],
        cond="the response time was met"),
    "deposit": dict(dir="floor", unit="percent", lims="floor_share", head="Deposit", fam="order", k=(10, 45), steps=(1,), widths=W_STD,
        frames=["An order becomes binding once the {P2} has paid a deposit of {LIM} of the order value.",
                "An order is binding if a deposit of {LIM} of its value has been paid.",
                "The {P1} is bound by an order when it has received a deposit of {LIM} of the order value."],
        facts=["The {P2} paid a deposit of {x} percent of the order value.",
               "For an order, a deposit of {x} percent of its value was paid by the {P2}.",
               "The {P1} received a deposit of {x} percent of the order value from the {P2}."],
        qpos=["has the order become binding?", "is the deposit large enough to make the order binding?"],
        qneg=["is the order still not binding?", "is the deposit too small to make the order binding?"],
        cond="the order has become binding"),
}
TYPE_NAMES = list(TYPES)

# plain clauses (no number, never changed, no point at issue depends on them)
PLAIN = [("written_form", "Written form", "Changes to this agreement are valid only if both parties sign them in writing."),
         ("assignment", "Assignment", "Neither party may transfer its rights under this agreement to a third party without the written consent of the other party."),
         ("confidentiality", "Confidentiality", "Each party keeps the business information of the other party confidential and uses it only for the purposes of this agreement."),
         ("severability", "Severability", "If one clause of this agreement proves invalid, the remaining clauses stay in force."),
         ("entire", "Entire agreement", "This agreement replaces all earlier arrangements between the parties on the same subject."),
         ("disputes", "Disputes", "The parties try to settle any dispute by talks between their managers before taking any further step."),
         ("subcontractors", "Subcontractors", "The {P1} may use subcontractors but remains responsible for their work."),
         ("insurance", "Insurance", "The {P1} keeps adequate insurance cover for its activities under this agreement."),
         ("contacts", "Contact persons", "Each party names a contact person and promptly informs the other party of any change."),
         ("events", "Unforeseeable events", "Neither party is in breach while an event beyond its reasonable control prevents performance."),
         ("cooperation", "Cooperation", "The parties cooperate in good faith and share the information needed to perform this agreement."),
         ("language", "Language", "This agreement is drawn up in one language, and its text prevails over any translation.")]
PLAIN_BY_KEY = {k: (h, s) for k, h, s in PLAIN}

DOMAINS = {
    "supply": dict(title="Supply agreement", P1="Supplier", P2="Buyer", items="goods", system="the ordering portal", records="delivery records", ticket="fault report"),
    "software": dict(title="Software services agreement", P1="Provider", P2="Client", items="devices", system="the hosted platform", records="usage logs", ticket="support ticket"),
    "lease": dict(title="Equipment lease agreement", P1="Lessor", P2="Lessee", items="leased units", system="the remote monitoring service", records="inspection records", ticket="breakdown report"),
    "distribution": dict(title="Distribution agreement", P1="Manufacturer", P2="Distributor", items="products", system="the dealer portal", records="sales records", ticket="dealer query"),
    "maintenance": dict(title="Maintenance agreement", P1="Contractor", P2="Operator", items="spare parts", system="the service hotline", records="maintenance records", ticket="call-out request"),
    "logistics": dict(title="Logistics services agreement", P1="Carrier", P2="Shipper", items="pallets", system="the tracking system", records="shipment records", ticket="damage report"),
}
DOMAIN_NAMES = list(DOMAINS)
CURRENCIES = ["dalmars", "soltins", "krevs", "pellins", "tovars", "ruvels"]
NAME_A = ["Bren", "Cald", "Dorv", "Elv", "Fosk", "Gral", "Hest", "Ilm", "Jorv", "Kest", "Lorn", "Mavr", "Nelt", "Orv", "Prask", "Quen",
          "Rost", "Sarn", "Tolv", "Ulm", "Varn", "Wex", "Yelt", "Zorn"]
NAME_B = ["ane", "ora", "eth", "um", "ari", "olt", "ine", "ond", "ura", "ivo", "esk", "arn"]
NAME_C = ["Works", "Trading", "Systems", "Supply", "Logistics", "Industries", "Partners", "Group", "Services", "Holdings"]

INTROS = ['{title} between {n1} ("the {P1}") and {n2} ("the {P2}"). Two versions of its text are set out below, followed by a case.',
          'Parties: {n1} ("the {P1}") and {n2} ("the {P2}"). Document: {title}, in two versions (A and B), with a case at the end.',
          'Below are version A and version B of an agreement ({title}) between {n1} ("the {P1}") and {n2} ("the {P2}"), and then a case.']
RULE_HEADS = ["Reading rules:", "How to read the texts:", "Conventions:"]
_INC = ", ".join('"%s"' % w for w in INCL_WORDS[:-1]) + ' or "%s"' % INCL_WORDS[-1]
_EXC = ", ".join('"%s"' % w for w in EXCL_WORDS[:-1]) + ' or "%s"' % EXCL_WORDS[-1]
RULES = [
    ["Version A and version B are two texts of one agreement; the case is decided once under version A alone and once under version B alone.",
     "The case is to be decided twice: under version A as if it were the only text, and under version B as if it were the only text.",
     "Treat each version as a complete text of the agreement and decide the case under each of them separately."],
    ["Clause numbers may differ between the versions (a clause can be moved or added); a clause is identified by its subject, not by its number.",
     "A clause may carry another number in version B than in version A, because clauses can be moved or added; match clauses by their subject.",
     "The numbering can shift from one version to the other when a clause is moved or added, so clauses correspond by subject and not by number."],
    ["Each clause states its condition in full: what it provides applies when the condition is met and does not apply otherwise.",
     "The condition written in a clause is complete: if it is met, what the clause provides applies, and if it is not met, it does not apply.",
     "Read every clause as complete: its consequence follows exactly when its stated condition is fulfilled, and in no other situation."],
    ["Limits are literal. The stated figure itself satisfies a limit worded with " + _INC + "; it does not satisfy a limit worded with " + _EXC + ".",
     "A value equal to the stated figure meets a limit that uses " + _INC + ", and fails a limit that uses " + _EXC + ".",
     "Whether the stated figure itself counts follows from the words: it counts with " + _INC + ", and it does not count with " + _EXC + "."],
    ["A point at issue, and each condition of a request, is decided by the clause on its subject alone; facts about other subjects have no bearing on it.",
     "Only the clause on the subject of a point at issue (or of a condition of a request) decides it; facts that belong to other subjects do not matter for it.",
     "Each point at issue and each condition of a request depends on one clause, the one on its subject; other facts of the case leave it untouched."],
]
BLOCKS = [("VERSION A", "VERSION B", "CASE"), ("--- Version A ---", "--- Version B ---", "--- Case ---"),
          ("Version A:", "Version B:", "Case:"), ("[Version A]", "[Version B]", "[Case]")]
LAYOUTS = ["{n}. {head}. {text}", "Clause {n} - {head}: {text}", "({n}) {text}", "Art. {n}: {text}"]
REQ_FRAMES = ["A request is under review. It succeeds if both of the following hold and fails if at least one of them does not: (a) {c1}; (b) {c2}.",
              "A request has been made. Both of the following must hold for it to succeed; if either one does not hold, it fails: (a) {c1}; (b) {c2}.",
              "A request is to be decided. It is successful when (a) and (b) both hold and unsuccessful in every other situation: (a) {c1}; (b) {c2}."]
REQ_QPOS = ["does the request succeed?", "is the request successful?"]
REQ_QNEG = ["does the request fail?", "is the request unsuccessful?"]
POINT = "Point at issue: "


DROP = {1: "yes_only_B", 2: "same", 3: "yes_only_A"}      # the class that the one group of two of each level leaves out
N_CLAUSES = {1: (8, 8), 2: (10, 11), 3: (12, 13)}          # clauses of version A (version B: one more at level 3)
N_SILENT = {1: (2, 2), 2: (2, 3), 3: (2, 3)}               # limit clauses that no fact of the case is about
ON_TARGET = 0.55                                            # share of topic facts that sit ON a stated figure, every class


# ------------------------------------------------------------------------------------------------ the rule of a limit clause
def eff(d, k, incl):
    """first (floor) or last (ceiling) value of the grid of the facts that satisfies the limit"""
    if incl:
        return k
    return k + 1 if d == "floor" else k - 1


def holds(d, n, incl, x):
    """the status a limit clause gives the fact x (direction d, stated figure n, wording that counts the figure or not)"""
    if d == "floor":
        return x >= n if incl else x > n
    return x <= n if incl else x < n


def plan_change(rng, t, role, kind):
    """stated figures (in grid steps) and counting flags of a changed limit clause; stricter = fewer facts satisfy it in B"""
    T = TYPES[t]
    d, (klo, khi) = T["dir"], T["k"]
    for _ in range(1000):
        if kind == "wording":
            kA = kB = rng.randint(klo + 1, khi - 1)
            iA = role == "stricter"
            iB = not iA
        else:
            w = rng.choice(T["widths"])
            up = (role == "stricter") == (d == "floor")
            kA = rng.randint(klo, khi)
            kB = kA + w if up else kA - w
            if not klo <= kB <= khi:
                continue
            iA = rng.random() < 0.5
            iB = iA if kind == "number" else not iA
        eA, eB = eff(d, kA, iA), eff(d, kB, iB)
        if eA != eB and ((eB > eA) == (d == "floor")) == (role == "stricter"):
            return kA, iA, kB, iB
    raise RuntimeError((t, role, kind))


def lim_index(rng, t, incl):
    return rng.choice([j for j, (_, f) in enumerate(LIMS[TYPES[t]["lims"]]) if f == incl])


def unit_of(t, cur):
    u = TYPES[t]["unit"]
    return cur if u == "{cur}" else u


def make_limit_clause(rng, t, change=None):
    T = TYPES[t]
    c = {"key": t, "kind": "limit", "dir": T["dir"], "step": rng.choice(T["steps"]), "frame": rng.randrange(len(T["frames"])),
         "change": change}
    if change:
        kA, iA, kB, iB = plan_change(rng, t, *change)
        lA = lim_index(rng, t, iA)
        lB = lA if iA == iB else lim_index(rng, t, iB)
    else:
        kA = kB = rng.randint(*T["k"])
        iA = iB = rng.random() < 0.5
        lA = lB = lim_index(rng, t, iA)
    c["A"], c["B"] = {"k": kA, "incl": iA, "lim": lA}, {"k": kB, "incl": iB, "lim": lB}
    return c


def cands_of(c):
    """grid values next to the two stated figures, by region: band (the versions disagree), true_both, false_both"""
    d, a, b = c["dir"], c["A"], c["B"]
    out = collections.defaultdict(list)
    for i in sorted({a["k"] - 1, a["k"], a["k"] + 1, b["k"] - 1, b["k"], b["k"] + 1}):
        ha, hb = holds(d, a["k"], a["incl"], i), holds(d, b["k"], b["incl"], i)
        out["band" if ha != hb else ("true_both" if ha else "false_both")].append(i)
    return out


def on_limit(c, i):
    return i in (c["A"]["k"], c["B"]["k"])


def clause_text(c, v, ctx):
    if c["kind"] == "plain":
        head, s = PLAIN_BY_KEY[c["key"]]
        return head, s.format(**ctx)
    T = TYPES[c["key"]]
    tpl = LIMS[T["lims"]][c[v]["lim"]][0]
    lim = tpl.format(n=c[v]["k"] * c["step"], u=unit_of(c["key"], ctx["cur"]))
    return T["head"], T["frames"][c["frame"]].format(LIM=lim, **ctx)


def clause_spec(c, v, ctx):
    if c["kind"] == "plain":
        return {"key": c["key"], "plain": True}
    tpl, incl = LIMS[TYPES[c["key"]]["lims"]][c[v]["lim"]]
    assert incl == c[v]["incl"]
    return {"key": c["key"], "dir": c["dir"], "n": c[v]["k"] * c["step"], "incl": incl,
            "wording": tpl.split("{n}")[0].strip() or tpl.split("{u}")[1].strip(), "unit": unit_of(c["key"], ctx["cur"])}


# ------------------------------------------------------------------------------------------------ truth from the specification
def answer(spec, v, count_rule=None):
    """yes/no answer to the point at issue under version v; count_rule forces a reading of every wording (sloppy readers)"""
    cl = {}
    for c in spec["versions"][v]:
        assert c["key"] not in cl
        cl[c["key"]] = c
    val = {f["key"]: f["value"] for f in spec["case"]["facts"]}
    ok = all(holds(cl[k]["dir"], cl[k]["n"], cl[k]["incl"] if count_rule is None else count_rule, val[k])
             for k in spec["case"]["conditions"])
    return ok if spec["case"]["polarity"] == "pos" else not ok


def truth(spec, count_rule=None):
    a, b = answer(spec, "A", count_rule), answer(spec, "B", count_rule)
    return "same" if a == b else ("yes_only_A" if a else "yes_only_B")


def party_names(rng):
    while True:
        a, b = rng.choice(NAME_A) + rng.choice(NAME_B), rng.choice(NAME_A) + rng.choice(NAME_B)
        if a[:3] != b[:3]:
            return a + " " + rng.choice(NAME_C), b + " " + rng.choice(NAME_C)


# ------------------------------------------------------------------------------------------------ plan of the 201 groups
def make_plan():
    rng = rng_for("plan")
    G = GROUPS_PER_LEVEL
    total = 3 * G

    def cycle(n):
        out = []
        while len(out) < n:
            c = TYPE_NAMES[:]
            rng.shuffle(c)
            out += c
        return out[:n]
    S, L = cycle(total), cycle(total)

    def bad(j):
        return L[j] == S[j] or TYPES[L[j]]["fam"] == TYPES[S[j]]["fam"]
    for j in range(total):
        tries = 0
        while bad(j):
            m = rng.randrange(total)
            L[j], L[m] = L[m], L[j]
            if bad(j) or bad(m):
                L[j], L[m] = L[m], L[j]
            tries += 1
            assert tries < 100000
    doms = {lv: rng.sample(DOMAIN_NAMES, len(DOMAIN_NAMES)) for lv in (1, 2, 3)}
    cell, pol_cnt, top_cnt, kind_cnt, same_cnt = (collections.Counter() for _ in range(5))
    half = (G + 1) // 2
    plans = []
    for j in range(total):
        level, jl = j // G + 1, j % G
        special = jl == G - 1
        present = [c for c in CLASSES if not (special and c == DROP[level])]
        s, l = S[j], L[j]
        best = None
        for P in rng.sample(["pos", "neg"], 2):
            if pol_cnt[(level, P)] >= half:
                continue
            cs, cl_ = ("yes_only_A", "yes_only_B") if P == "pos" else ("yes_only_B", "yes_only_A")
            sc = (cell[(s, "stricter", cs)] if cs in present else 0) + (cell[(l, "looser", cl_)] if cl_ in present else 0)
            if best is None or sc < best[0]:
                best = (sc, P, cs, cl_)
        _, P, cs, cl_ = best
        pol_cnt[(level, P)] += 1
        for t, role, c in ((s, "stricter", cs), (l, "looser", cl_)):
            if c in present:
                cell[(t, role, c)] += 1
        same = None
        if "same" in present:
            opts = []
            for role, t in rng.sample([("stricter", s), ("looser", l)], 2):
                if top_cnt[(level, role)] >= half:
                    continue
                lag = (cell[(t, role, "yes_only_A")] + cell[(t, role, "yes_only_B")]) / 2.0 - cell[(t, role, "same")]
                opts.append((-lag, role, t))
            _, role, t = min(opts, key=lambda o: o[0])
            top_cnt[(level, role)] += 1
            cell[(t, role, "same")] += 1
            kind = "out"
            if level == 3:
                kind = "out" if same_cnt[("kind", "out")] <= same_cnt[("kind", "cond")] else "cond"
                same_cnt[("kind", kind)] += 1
            outcome = "yes_both" if same_cnt["yes_both"] <= same_cnt["no_both"] else "no_both"
            same_cnt[outcome] += 1
            if kind == "cond":                       # the request fails under both versions
                Q = "neg" if outcome == "yes_both" else "pos"
            elif same_cnt[(level, "pos")] != same_cnt[(level, "neg")]:
                Q = "pos" if same_cnt[(level, "pos")] < same_cnt[(level, "neg")] else "neg"
            else:
                Q = rng.choice(["pos", "neg"])
            same_cnt[(level, Q)] += 1
            same = {"role": role, "topic": t, "kind": kind, "outcome": outcome, "Q": Q}
        best = None
        for ks in rng.sample(KINDS, 3):
            for kl in rng.sample(KINDS, 3):
                add = collections.Counter()
                if cs in present:
                    add[ks] += 1
                if cl_ in present:
                    add[kl] += 1
                if same:
                    add[ks if same["role"] == "stricter" else kl] += 1
                sc = sum((kind_cnt[(level, k)] + add[k]) ** 2 for k in KINDS)
                if best is None or sc < best[0]:
                    best = (sc, ks, kl, add)
        _, ks, kl, add = best
        for k, v in add.items():
            kind_cnt[(level, k)] += v
        plans.append({"gid": j, "level": level, "present": present, "S": s, "L": l, "kS": ks, "kL": kl, "P": P, "cS": cs,
                      "cL": cl_, "same": same, "domain": doms[level][jl % len(DOMAIN_NAMES)]})
    return plans, cell


# ------------------------------------------------------------------------------------------------ one group (one version pair)
def build_group(gp, onl, tot):
    level, present = gp["level"], gp["present"]
    rng = rng_for("group", gp["gid"])
    dom = DOMAINS[gp["domain"]]
    ctx = {k: dom[k] for k in ("P1", "P2", "items", "system", "records", "ticket")}
    ctx["cur"] = rng.choice(CURRENCIES)
    ctx["actor"] = rng.choice([dom["P1"], dom["P2"]])
    n1, n2 = party_names(rng)
    S, L, sm = gp["S"], gp["L"], gp["same"]

    def want(cls):
        return onl[cls] < ON_TARGET * tot[cls] or (onl[cls] == ON_TARGET * tot[cls] and rng.random() < 0.5)
    w_on = {c: want(c) for c in present}
    side = None
    if sm and sm["kind"] == "out":
        side = "true_both" if (sm["outcome"] == "yes_both") == (sm["Q"] == "pos") else "false_both"
    cl = {}
    for t, role, kind in ((S, "stricter", gp["kS"]), (L, "looser", gp["kL"])):
        for _ in range(80):                          # the topic of the same case: a clause with a value ON a figure on its side, if wanted
            c = make_limit_clause(rng, t, (role, kind))
            if not (side and sm["topic"] == t and w_on["same"]) or any(on_limit(c, i) for i in cands_of(c)[side]):
                break
        cl[t] = c
    used, fams = {S, L}, {TYPES[S]["fam"], TYPES[L]["fam"]}

    def draw(distinct_fam):
        pool = [t for t in TYPE_NAMES if t not in used and not (distinct_fam and TYPES[t]["fam"] in fams)]
        t = rng.choice(pool)
        used.add(t)
        fams.add(TYPES[t]["fam"])
        return t
    T3 = U2 = inserted = None
    if level >= 2:
        T3 = draw(True)
        cl[T3] = make_limit_clause(rng, T3, (rng.choice(["stricter", "looser"]), rng.choice(KINDS)))
    U = draw(True)                       # levels 1-2: an unchanged clause with a decoy fact; level 3: the clause of condition two
    cl[U] = make_limit_clause(rng, U)
    if level == 3:
        U2 = draw(True)
        cl[U2] = make_limit_clause(rng, U2)
    fact_keys = [k for k in (S, L, T3, U, U2) if k]
    n_total = rng.randint(*N_CLAUSES[level])
    for _ in range(rng.randint(*N_SILENT[level])):
        t = draw(False)
        cl[t] = make_limit_clause(rng, t)
    for k in rng.sample([k for k, _, _ in PLAIN], n_total - len(cl)):
        cl[k] = {"key": k, "kind": "plain"}
    if level == 3:
        if rng.random() < 0.5:
            inserted = rng.choice([k for k, _, _ in PLAIN if k not in cl])
            cl[inserted] = {"key": inserted, "kind": "plain"}
        else:
            inserted = draw(False)
            cl[inserted] = make_limit_clause(rng, inserted)

    # ---- values of the facts (grid steps)
    def pick(k, pool, wanted):
        on = [i for i in pool if on_limit(cl[k], i)]
        off = [i for i in pool if not on_limit(cl[k], i)]
        if wanted is None:
            return rng.choice(pool)
        return rng.choice(on if on and (wanted or not off) else off)

    def count(cls, k, i):
        onl[cls] += on_limit(cl[k], i)
        tot[cls] += 1
    cS, cL = gp["cS"], gp["cL"]
    s_in = pick(S, cands_of(cl[S])["band"], w_on.get(cS))
    l_in = pick(L, cands_of(cl[L])["band"], w_on.get(cL))
    if cS in present:
        count(cS, S, s_in)
    if cL in present:
        count(cL, L, l_in)

    def out_any(k):
        cc = cands_of(cl[k])
        return cc["true_both"] + cc["false_both"]
    s_dec, l_dec = rng.choice(out_any(S)), rng.choice(out_any(L))
    same_vals = None
    if sm:
        X = sm["topic"]
        if sm["kind"] == "out":
            x_out = pick(X, cands_of(cl[X])[side], w_on["same"])
            if X == S:
                s_dec = x_out
                same_vals = {S: x_out, L: l_in}          # the facts of the band member of the looser clause
            else:
                l_dec = x_out
                same_vals = {S: s_in, L: x_out}          # the facts of the band member of the stricter clause
        else:
            same_vals = {S: s_in, L: l_dec} if X == S else {S: s_dec, L: l_in}
        count("same", X, same_vals[X])

    def u_pick(k, want_hold):
        c = cl[k]
        d, kk, incl = c["dir"], c["A"]["k"], c["A"]["incl"]
        pool = [i for i in (kk - 1, kk, kk + 1) if holds(d, kk, incl, i) == want_hold]
        if kk in pool and rng.random() < 0.5:
            return kk
        return rng.choice([i for i in pool if i != kk] or pool)
    base = {U: u_pick(U, True if level == 3 else rng.random() < 0.5)}
    u_fail = u_pick(U, False) if level == 3 else None
    if T3:
        cc = cands_of(cl[T3])
        base[T3] = rng.choice(cc["band"] + cc["true_both"] + cc["false_both"])
    if U2:
        base[U2] = u_pick(U2, rng.random() < 0.5)
    members, P = [], gp["P"]
    if cS in present:
        members.append({"cls": cS, "topic": S, "role": "stricter", "pol": P, "case": "band", "vals": dict(base, **{S: s_in, L: l_dec})})
    if cL in present:
        members.append({"cls": cL, "topic": L, "role": "looser", "pol": P, "case": "band", "vals": dict(base, **{S: s_dec, L: l_in})})
    if sm:
        v = dict(base, **same_vals)
        if sm["kind"] == "cond":
            v[U] = u_fail
        members.append({"cls": "same", "topic": sm["topic"], "role": sm["role"], "pol": sm["Q"], "outcome": sm["outcome"],
                        "case": "outside" if sm["kind"] == "out" else "other_condition", "vals": v})
    assert [m["cls"] for m in members] == [c for c in (cS, cL, "same") if c in present]

    # ---- order of the clauses: A shuffled; B = A with one unchanged clause moved (levels 2-3) and one inserted (level 3)
    changed = {S, L} | ({T3} if T3 else set())
    keysA = [k for k in cl if k != inserted]
    for _ in range(1000):
        A = keysA[:]
        rng.shuffle(A)
        B, moved = A[:], None
        if level >= 2:
            moved = rng.choice([k for k in A if k not in changed])
            p = B.index(moved)
            B.pop(p)
            B.insert(rng.choice([x for x in range(len(B) + 1) if x != p]), moved)
        if level == 3:
            B.insert(rng.randrange(len(B) + 1), inserted)
        shifted = sum(A.index(k) != B.index(k) for k in (S, L))
        if level == 1 or (level == 2 and shifted >= 1) or (level == 3 and shifted == 2):
            break
    else:
        raise RuntimeError("arrangement")

    # ---- rendering
    lay, blk = rng.randrange(len(LAYOUTS)), BLOCKS[rng.randrange(len(BLOCKS))]
    intro = INTROS[rng.randrange(len(INTROS))].format(title=dom["title"], n1=n1, n2=n2, P1=dom["P1"], P2=dom["P2"])
    rules = [RULE_HEADS[rng.randrange(len(RULE_HEADS))]] + ["- " + r[rng.randrange(len(r))] for r in RULES]

    def vlines(order, v):
        out = []
        for i, k in enumerate(order):
            head, text = clause_text(cl[k], v, ctx)
            out.append(LAYOUTS[lay].format(n=i + 1, head=head, text=text))
        return out
    top = [intro] + rules + [blk[0]] + vlines(A, "A") + [blk[1]] + vlines(B, "B") + [blk[2]]
    fact_order = fact_keys[:]
    rng.shuffle(fact_order)
    fidx = {k: rng.randrange(len(TYPES[k]["facts"])) for k in fact_order}
    qidx = {(k, p): rng.randrange(2) for k in (S, L) for p in ("pos", "neg")}
    rf, rq = rng.randrange(len(REQ_FRAMES)), {"pos": rng.randrange(len(REQ_QPOS)), "neg": rng.randrange(len(REQ_QNEG))}
    out = []
    for m in members:
        flines = [TYPES[k]["facts"][fidx[k]].format(x=m["vals"][k] * cl[k]["step"], **ctx) for k in fact_order]
        if level == 3:
            conds = [m["topic"], U] if rng.random() < 0.5 else [U, m["topic"]]
            req = REQ_FRAMES[rf].format(c1=TYPES[conds[0]]["cond"].format(**ctx), c2=TYPES[conds[1]]["cond"].format(**ctx))
            q = (REQ_QPOS if m["pol"] == "pos" else REQ_QNEG)[rq[m["pol"]]]
            case = flines + [req, POINT + q]
        else:
            conds = [m["topic"]]
            q = TYPES[m["topic"]]["qpos" if m["pol"] == "pos" else "qneg"][qidx[(m["topic"], m["pol"])]].format(**ctx)
            case = flines + [POINT + q]
        spec = {"level": level, "domain": gp["domain"], "seed": SEED, "parties": [n1, n2], "roles": [dom["P1"], dom["P2"]],
                "versions": {"A": [clause_spec(cl[k], "A", ctx) for k in A], "B": [clause_spec(cl[k], "B", ctx) for k in B]},
                "case": {"facts": [{"key": k, "value": m["vals"][k] * cl[k]["step"]} for k in fact_order],
                         "topic": m["topic"], "conditions": conds, "polarity": m["pol"]},
                "changes": {"stricter": S, "looser": L, "other": T3, "moved": moved, "inserted": inserted}}
        gold = truth(spec)
        assert gold == m["cls"], (gp["gid"], m, gold)
        check_member(spec, m, cl, U)
        out.append({"state": "\n".join(top + case), "gold": gold, "spec": spec, "m": m, "top": top, "case": case,
                    "deviation": cl[m["topic"]]["change"][1], "on": on_limit(cl[m["topic"]], m["vals"][m["topic"]])})
    check_versions(cl, A, B, changed, moved, inserted, ctx, level)
    assert len({len(o["state"].split("\n")) for o in out}) == 1
    assert len({re.sub(r"\d+", "#", "\n".join(o["case"][:len(fact_order)])) for o in out}) == 1
    assert len({o["state"] for o in out}) == len(out)
    return out


def check_member(spec, m, cl, U):
    """exactly one of the two live facts lies between its old and new limit; the topic fact does so for band and
    other-condition cases only; the second condition (level 3) fails only in other-condition cases"""
    vA = {c["key"]: c for c in spec["versions"]["A"]}
    vB = {c["key"]: c for c in spec["versions"]["B"]}
    val = {f["key"]: f["value"] for f in spec["case"]["facts"]}

    def in_band(k):
        a, b = vA[k], vB[k]
        return holds(a["dir"], a["n"], a["incl"], val[k]) != holds(b["dir"], b["n"], b["incl"], val[k])
    s, l = spec["changes"]["stricter"], spec["changes"]["looser"]
    assert in_band(s) + in_band(l) == 1
    assert in_band(spec["case"]["topic"]) == (m["case"] != "outside")
    if spec["level"] == 3:
        u = vA[U]
        assert vB[U]["n"] == u["n"] and vB[U]["incl"] == u["incl"]
        assert holds(u["dir"], u["n"], u["incl"], val[U]) == (m["case"] != "other_condition")
        assert set(spec["case"]["conditions"]) == {spec["case"]["topic"], U}
    if m["cls"] == "same":
        assert answer(spec, "A") == answer(spec, "B") == (m["outcome"] == "yes_both")


LIMIT_WORD_RE = re.compile(r"\d+")


def check_versions(cl, A, B, changed, moved, inserted, ctx, level):
    """unchanged clauses read the same in A and B; the changed ones differ in their limit only; directions as planned"""
    for k in A:
        ta, tb = clause_text(cl[k], "A", ctx), clause_text(cl[k], "B", ctx)
        assert (ta != tb) == (k in changed), k
        if cl[k]["kind"] == "limit":
            for t in (ta[1], tb[1]):
                assert len(LIMIT_WORD_RE.findall(t)) == 1, t
                assert len(_words_in(t, INCL_WORDS) + _words_in(t, EXCL_WORDS)) == 1, t
        else:
            assert not LIMIT_WORD_RE.search(ta[1])
    for k in changed:
        c = cl[k]
        role = c["change"][0]
        lo, hi = min(c["A"]["k"], c["B"]["k"]) - 3, max(c["A"]["k"], c["B"]["k"]) + 3
        sa = {i for i in range(lo, hi + 1) if holds(c["dir"], c["A"]["k"], c["A"]["incl"], i)}
        sb = {i for i in range(lo, hi + 1) if holds(c["dir"], c["B"]["k"], c["B"]["incl"], i)}
        assert (sb < sa) if role == "stricter" else (sa < sb), k
    rest = [k for k in B if k != inserted]
    assert sorted(rest) == sorted(A) and (inserted is None) == (level < 3) and (inserted not in A)
    if level == 1:
        assert A == B
    else:
        assert [k for k in A if k != moved] == [k for k in rest if k != moved] and A.index(moved) != rest.index(moved)


# ------------------------------------------------------------------------------------------------ the whole set
def assign_orders(rows):
    """each class gets every option order 33 or 34 times; the gold position is balanced exactly (200 per position)"""
    rng = rng_for("options")
    perms = [list(p) for p in itertools.permutations(CLASSES)]
    extra = {"same": (0, 1), "yes_only_A": (1, 2), "yes_only_B": (2, 0)}
    for c in CLASSES:
        idx = [i for i, r in enumerate(rows) if r["gold"] == c]
        pool = [p for p in perms for _ in range(len(idx) // 6)]
        for pos in extra[c][:len(idx) - len(pool)]:
            pool.append(rng.choice([p for p in perms if p.index(c) == pos]))
        assert len(pool) == len(idx)
        rng.shuffle(pool)
        for i, p in zip(idx, pool):
            rows[i]["order"] = p


def vocab_check(states, gold):
    sets = [set(re.findall(r"[a-z]+", s.lower())) for s in states]
    worst = (1.0, "")
    for c in CLASSES:
        n1 = sum(g == c for g in gold)
        n0 = len(gold) - n1
        a, b = collections.Counter(), collections.Counter()
        for st, g in zip(sets, gold):
            (a if g == c else b).update(st)
        for t in set(a) | set(b):
            if a[t] + b[t] < 20:
                continue
            ra, rb = a[t] / n1, b[t] / n0
            ratio = max(ra, rb) / min(ra, rb) if min(ra, rb) > 0 else float("inf")
            if ratio > worst[0]:
                worst = (ratio, t)
    assert worst[0] <= 2.0, worst
    return worst


def sloppy_readers(rows):
    """accuracy of readings that skip a step (they must stay far from 1)"""
    acc = collections.Counter()
    for r in rows:
        sp, g = r["spec"], r["gold"]
        acc["every wording counts the figure"] += truth(sp, True) == g
        acc["no wording counts the figure"] += truth(sp, False) == g
        t = sp["case"]["topic"]
        band = "yes_only_A" if (t == sp["changes"]["stricter"]) == (sp["case"]["polarity"] == "pos") else "yes_only_B"
        acc["direction of the change only"] += band == g
        nA = next(c["n"] for c in sp["versions"]["A"] if c["key"] == t)
        nB = next(c["n"] for c in sp["versions"]["B"] if c["key"] == t)
        x = next(f["value"] for f in sp["case"]["facts"] if f["key"] == t)
        acc["fact between the two figures"] += (band if min(nA, nB) <= x <= max(nA, nB) else "same") == g
        one = dict(sp, case=dict(sp["case"], conditions=[t]))
        acc["topic clause only (level 3: second condition ignored)"] += truth(one) == g
    return {k: v / len(rows) for k, v in acc.items()}


def fmt_item(it):
    m = it["meta"]
    out = [f"id `{it['id']}` (group `{it['group']}`, level {m['level']}, gold **{it['gold']}**, case `{m['case']}`, topic `{m['topic']}` "
           f"({m['topic_role']} clause, change: {m['deviation']}), polarity {m['polarity']})", "", "```", it["state"], "```", "",
           f"question: {it['questions']['q']['instructions']}", ""]
    out += [f"- `{k}`: {v}" for k, v in it["questions"]["q"]["criteria"].items()]
    return "\n".join(out)


def main():
    check_lims()
    plans, cell = make_plan()
    onl, tot = collections.Counter(), collections.Counter()
    built = []
    for gp in plans:
        for o in build_group(gp, onl, tot):
            o["gid"] = gp["gid"]
            built.append(o)
    assign_orders(built)
    rng_for("shuffle").shuffle(built)
    gnum, rows = {}, []
    for n, o in enumerate(built, 1):
        gnum.setdefault(o["gid"], len(gnum) + 1)
        m, sp = o["m"], o["spec"]
        meta = {"source_id": f"{n:05d}", "level": sp["level"], "domain": sp["domain"], "deviation": o["deviation"], "order": o["order"],
                "seed": SEED, "case": m["case"], "topic": m["topic"], "topic_role": m["role"], "polarity": m["pol"],
                "same_outcome": m.get("outcome"), "fact_on_figure": o["on"],
                "clauses": [len(sp["versions"]["A"]), len(sp["versions"]["B"])], "spec": sp}
        rows.append({"id": f"{ID_PREFIX}:{n:05d}", "state": o["state"],
                     "questions": {"q": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": {k: OPTIONS[k] for k in o["order"]}}},
                     "gold": o["gold"], "soft": None, "group": f"{ID_PREFIX}:g{gnum[o['gid']]:04d}", "meta": meta})
    st = checks(rows, cell, onl, tot)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "items.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    write_task_json(rows, st)
    write_readme(rows, st)
    print(f"{TASK}: {len(rows)} items, {len(gnum)} groups -> {OUT_DIR}")
    for k, v in st["print"]:
        print(f"  {k}: {v}")


def checks(rows, cell, onl, tot):
    st, pr = {}, []
    lv_cls = collections.Counter((r["meta"]["level"], r["gold"]) for r in rows)
    for lv in (1, 2, 3):
        for c in CLASSES:
            assert lv_cls[(lv, c)] == GROUPS_PER_LEVEL - 1 + (c != DROP[lv]), (lv, c, lv_cls)
        assert sum(lv_cls[(lv, c)] for c in CLASSES) == 200
    cls = collections.Counter(r["gold"] for r in rows)
    assert all(cls[c] == 200 for c in CLASSES), cls
    gpos = collections.Counter(r["meta"]["order"].index(r["gold"]) for r in rows)
    assert all(gpos[i] == 200 for i in range(3)), gpos
    dev = collections.Counter((r["meta"]["level"], r["meta"]["deviation"]) for r in rows)
    for lv in (1, 2, 3):
        v = [dev[(lv, k)] for k in KINDS]
        assert max(v) - min(v) <= 2, (lv, v)
    case = collections.Counter((r["meta"]["level"], r["meta"]["case"]) for r in rows)
    so = collections.Counter(r["meta"]["same_outcome"] for r in rows if r["gold"] == "same")
    assert so["yes_both"] == so["no_both"] == 100, so
    assert len({r["state"] for r in rows}) == len(rows)
    tr = collections.Counter((r["meta"]["topic"], r["meta"]["topic_role"], r["gold"]) for r in rows)
    spread = max(max(tr[(t, ro, c)] for c in CLASSES) - min(tr[(t, ro, c)] for c in CLASSES)
                 for t in TYPE_NAMES for ro in ("stricter", "looser"))
    assert spread <= 4, spread
    ro_cls = collections.Counter((r["meta"]["topic_role"], r["gold"]) for r in rows)
    on = {c: sum(r["meta"]["fact_on_figure"] for r in rows if r["gold"] == c) / 200 for c in CLASSES}
    assert max(on.values()) - min(on.values()) <= 0.10, on
    pol = {c: sum(r["meta"]["polarity"] == "pos" for r in rows if r["gold"] == c) / 200 for c in CLASSES}
    assert all(0.4 <= v <= 0.6 for v in pol.values()), pol
    worst = vocab_check([r["state"] for r in rows], [r["gold"] for r in rows])
    sl = sloppy_readers([{"spec": r["meta"]["spec"], "gold": r["gold"]} for r in rows])
    for k, v in sl.items():
        if not k.startswith("topic clause only"):
            assert v <= 0.85, (k, v)
    ln = {c: sum(len(r["state"]) for r in rows if r["gold"] == c) / 200 for c in CLASSES}
    assert max(ln.values()) / min(ln.values()) < 1.03, ln
    lens = {lv: sorted(len(r["state"]) for r in rows if r["meta"]["level"] == lv) for lv in (1, 2, 3)}
    st.update(lv_cls=lv_cls, dev=dev, case=case, so=so, spread=spread, ro_cls=ro_cls, on=on, pol=pol, worst=worst, sl=sl, ln=ln,
              lens=lens, gpos=gpos)
    pr.append(("classes per level", {lv: [lv_cls[(lv, c)] for c in CLASSES] for lv in (1, 2, 3)}))
    pr.append(("deviation (change kind of the topic clause) per level", {lv: [dev[(lv, k)] for k in KINDS] for lv in (1, 2, 3)}))
    pr.append(("case kinds per level", {lv: [case[(lv, k)] for k in ("band", "outside", "other_condition")] for lv in (1, 2, 3)}))
    pr.append(("same: yes under both / no under both", [so["yes_both"], so["no_both"]]))
    pr.append(("largest class spread per (clause type, role)", spread))
    pr.append(("fact on a stated figure, share per class", {c: round(v, 3) for c, v in on.items()}))
    pr.append(("positive polarity, share per class", {c: round(v, 3) for c, v in pol.items()}))
    pr.append(("vocabulary: worst rate ratio", (round(worst[0], 2), worst[1])))
    pr.append(("sloppy readers", {k: round(v, 3) for k, v in sl.items()}))
    pr.append(("state characters min/median/max per level", {lv: [v[0], v[len(v) // 2], v[-1]] for lv, v in lens.items()}))
    st["print"] = pr
    return st


def write_task_json(rows, st):
    lens = sorted(len(r["state"]) for r in rows)
    split = f"generated, seed {SEED}" + (" (sealed split)" if SEALED else "")
    task = {"task": TASK, "layer": "E",
            "title": "Generated agreement versions: does the change between version A and version B alter the answer for the case?",
            "decision": "for a case with a yes/no point at issue, whether the answer is the same under both versions of an agreement, "
                        "yes only under version A, or yes only under version B",
            "source": {"name": f"generator build/gen_{TASK}.py", "url": "", "files": [], "split": split, "version": "script of 2026-10-07"},
            "licence": "generated by the benchmark's script (no third-party text)", "redistribution": "items included",
            "labels": "programmatic", "item_source": "generated", "metric": "pair_accuracy", "chance": round(sum((1 / 3) ** n for n in collections.Counter(r["group"] for r in rows).values())
                                                                / len({r["group"] for r in rows}), 6), "rows": len(rows),
            "groups": len({r["group"] for r in rows}), "question_type": "choice", "options": 3,
            "skill": "compare two versions of an agreement clause by clause (numbers may shift) and decide from the exact limit "
                     "wording whether the change alters the yes/no answer for a concrete case",
            "knobs": "clauses per version 8 / 10-11 / 12-14; moved clause (levels 2-3) and inserted clause (level 3) shift the "
                     "numbering; a third changed clause and decoy facts; two-condition requests (level 3); limit wordings that count "
                     "or do not count the stated figure; facts on or one step from a stated figure",
            "notes": ("Metric pair_accuracy: a group counts as solved only when every case of it is answered correctly (chance = the "
                      "mean over groups of (1/3)^members). Reason: the direction of the change of the topic clause and the polarity of the "
                      "point at issue decide every case whose fact lies between the two limits (two thirds of the items), so a reader who "
                      "never looks at the facts of the case reaches 0.667 item accuracy, but such a reader solves no group that contains "
                      "a same case (1 of 201 groups). Item accuracy is still reported by score.py's calibration columns. "
                      "600 items in 201 groups: per level 66 groups of three cases (one per class) on one version pair and one group "
                      "of two (200 items is not a multiple of 3; level 1 leaves out yes_only_B, level 2 same, level 3 yes_only_A), so "
                      "every class has 200 items and every level 200 (classes 67/66/67 per level). Members of a group share the two "
                      "versions and differ in the case paragraph only (same lines; values of the facts and the point at issue). Every "
                      "convention is written in the state. Answer computed from the structured specification (meta.spec). "
                      "State length %d to %d characters (median %d)." % (lens[0], lens[-1], lens[len(lens) // 2]))}
    with open(os.path.join(OUT_DIR, "task.json"), "w", encoding="utf-8") as f:
        json.dump(task, f, indent=1)


def write_readme(rows, st):
    lv_cls, dev, case, sl, lens = st["lv_cls"], st["dev"], st["case"], st["sl"], st["lens"]
    ex = [next(r for r in rows if r["meta"]["level"] == lv) for lv in (1, 2, 3)]
    T = "\n".join(f"| {lv} | " + " | ".join(str(lv_cls[(lv, c)]) for c in CLASSES) + f" | {lens[lv][0]} / {lens[lv][len(lens[lv]) // 2]} / {lens[lv][-1]} |"
                  for lv in (1, 2, 3))
    D = "\n".join(f"| {lv} | " + " | ".join(str(dev[(lv, k)]) for k in KINDS) + " | "
                  + " | ".join(str(case[(lv, k)]) for k in ("band", "outside", "other_condition")) + " |" for lv in (1, 2, 3))
    SL = "\n".join(f"| {k} | {v:.3f} |" for k, v in sl.items())
    txt = f"""# {TASK}

Generated agreement versions: does the change between version A and version B alter the answer to the point at issue?
(layer E, generated, programmatic truth)

- Decision: `same` (the answer is the same under both versions: yes under both or no under both), `yes_only_A`, `yes_only_B`.
- Source: generator `build/gen_{TASK}.py` (Python 3.9, standard library, `random.Random({SEED})` and generators derived from it;
  identical output on every run). `BENCH_OUT=<dir>` writes `<dir>/{TASK}/` instead; `BENCH_SEED=<int>` (only together with
  `BENCH_OUT`) builds a sealed set of the same design from another seed (ids `{TASK}:s<seed>:<number>`).
- Rows: {len(rows)} in {len({r['group'] for r in rows})} groups; metric pair_accuracy (a group counts only when all its cases are right; chance = mean over groups of (1/3)^members; per item the chance is 1/3, and a reader who ignores the facts of the case reaches 0.667 per item but solves 1 of 201 groups); options in fixed wording, order drawn per
  item (`meta.order`; every gold position 200 times).

## What is generated

Every state is one text: an opening line (an invented agreement between two invented companies), five reading rules, version A
and version B of the agreement (numbered clauses, one per line, in one of four layouts) and a case (one fact per line, then
`Point at issue: ...?`). Twelve clause types are parameterised limit rules (notice period, payment grace period, liability cap,
warranty period, return window, volume threshold for a reduced price, cancellation for late delivery, yearly price rise,
service credit for downtime, retention of records, response time, deposit); each has three sentence frames, three phrasings of
its fact and two of each polarity of its point at issue. A limit is a plain number of days, months, hours, units, percent or an
invented currency, with a wording that counts the stated figure (`at least`, `no later than`, `or more`, `at most`, `or less` ...)
or does not (`more than`, `over`, `fewer than`, `under`, `below` ...). Twelve plain clauses without a number fill the agreement.
Six agreement domains (supply, software services, equipment lease, distribution, maintenance, logistics).

Every version pair has one clause that became stricter from A to B and one that became looser; the change is the number only,
the wording only, or both (`meta.deviation` = the change of the clause the point at issue is about). From level 2 a third clause
changed (the case holds a fact about it, but no point at issue depends on it) and one unchanged clause stands in another place,
so the live clauses carry other numbers in B; at level 3 a clause is inserted in B as well.

## Conventions written in every state (reading rules)

1. The case is decided once under version A alone and once under version B alone.
2. Clause numbers may differ between the versions; clauses correspond by subject.
3. A clause states its condition in full: what it provides applies exactly when the condition is met.
4. Limits are literal: the stated figure satisfies a limit worded with the listed counting words and fails one worded with the
   listed non-counting words (both lists are printed in the state).
5. A point at issue (and each condition of a request) is decided by the clause on its subject alone; other facts do not matter.
Level 3 requests say in the case that they succeed only if both conditions hold.

## Groups and classes

A group is three cases on one version pair (same lines; only the values of the facts and the point at issue differ):
- band case of the stricter clause: its fact lies between the old and the new limit (the status holds under A only);
- band case of the looser clause: its fact lies between the limits (the status holds under B only);
- `same` case: the fact of the stricter or of the looser clause (both equally often) lies one step outside the band or on a
  limit where the wording keeps it outside, or (level 3) it lies in the band while the unchanged second condition fails.
Each point at issue is asked as a positive or a negative question (\"was the notice given in time?\" / \"... too late?\"), so the
band case of the stricter clause is `yes_only_A` or `yes_only_B`, and for every clause type and direction of change the three
classes are balanced (largest spread {st['spread']}). In every case exactly one of the two live facts lies inside its band (the
other one is a near miss), so counting facts in bands says nothing; a `same` case of the out-of-band kind carries the same facts
as one band case of its group and differs from it in the point at issue only. `same` = yes under both {st['so']['yes_both']} times,
no under both {st['so']['no_both']} times. Facts that sit ON a stated figure (the wording decides): share per class
{', '.join(f'{c} {v:.2f}' for c, v in st['on'].items())}.

| level | {' | '.join(CLASSES)} | state characters min / median / max |
|---|---|---|---|---|
{T}

Each level has 66 groups of three and one group of two (200 is not a multiple of 3).

| level | number | wording | number_and_wording | band | outside | other_condition |
|---|---|---|---|---|---|---|
{D}

## Levels

1. 8 clauses per version, no move; the point at issue concerns one clause; facts: the two live clauses and one unchanged clause.
2. 10-11 clauses, a third changed clause, one unchanged clause moved (numbering shifts for at least one live clause).
3. 12-13 clauses in A and one more in B (inserted clause; both live clauses change number); a request with two conditions, one on
   a live clause and one on an unchanged clause. Steps: find the clause of condition (a) in A and decide it from the wording,
   find the same clause in B under another number and decide it, find the clause of condition (b) and decide it, combine the
   conditions per version, apply the polarity, compare the two answers (at least five steps over facts from four places).

## Checks made by the script

Truth `truth(spec)` from the structured specification (clauses of each version looked up by subject); asserted for every item:
the planned class; exactly one live fact in its band; the topic fact in its band exactly for band and other-condition cases; the
second condition fails exactly in other-condition cases; unchanged clauses identical in A and B, changed clauses different, the
stricter clause admits a strict subset in B and the looser one a strict superset; one relocation (levels 2-3) and one insertion
(level 3); members of a group with the same number of lines and identical fact lines up to the numbers; no duplicate state.
Over the set: classes per level, 200 per class and per gold position, deviation kinds per level within 2, same outcomes 100/100,
class spread per clause type and role <= 4, share of facts on a figure within 0.10 across classes, polarity 40-60 % per class,
no state word (frequency >= 20) with a class rate ratio above 2 (worst {st['worst'][0]:.2f}, `{st['worst'][1]}`), mean state length
per class within 3 %. Readers that skip a step (they must stay at or below 0.85):

| reading | accuracy |
|---|---|
{SL}

## Examples (one per level)

""" + "\n\n".join(f"### level {r['meta']['level']}\n\n" + fmt_item(r) for r in ex) + """

## Independence

The generator is new, written for this benchmark; its clause frames, facts, questions, names and layouts share no template with
the authors' training generators or with any published data set. All names are invented.
"""
    with open(os.path.join(OUT_DIR, "README.md"), "w", encoding="utf-8") as f:
        f.write(txt)


if __name__ == "__main__":
    main()
