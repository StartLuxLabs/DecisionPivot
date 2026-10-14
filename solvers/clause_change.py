"""Independent second implementation for the task clause_change (label audit of gen_v3).

Written from the rendered text alone.  Method: parse both versions clause by clause (type, figure, counting wording),
match the clauses of A and B by their subject (taken from the CONTENT, a label is only cross-checked), parse the case
facts and the point at issue (or a request with two conditions), decide the point under A and under B separately and
map the pair of answers to the option whose text describes it.  Anything not recognised raises ValueError.

Python 3.9, standard library only.
"""
import re
from collections import OrderedDict


class Unparsed(ValueError):
    pass


ROLE_WORDS = ["Provider", "Client", "Carrier", "Shipper", "Supplier", "Buyer", "Lessor", "Lessee",
              "Contractor", "Operator", "Manufacturer", "Distributor"]
R = "(?:%s)" % "|".join(ROLE_WORDS)

# ----------------------------------------------------------------------------------------------------------------
# limit wordings: the direction comes from the plain meaning of the words; whether the stated figure itself counts is
# read from the reading rule printed in the state (see parse_counting_rule).
LIM_FRONT = ["no later than", "no fewer than", "no less than", "no more than", "at least", "at most", "more than",
             "fewer than", "less than", "over", "under", "below"]
LIM_BACK = ["or more", "or fewer", "or less"]
LOWER_WORDS = {"at least", "no fewer than", "no less than", "more than", "over", "or more"}      # value >= / > figure
UPPER_WORDS = {"at most", "no more than", "fewer than", "less than", "under", "below", "or fewer", "or less"}
FRONT_RE = re.compile(r"\b(%s) (\d+)\b" % "|".join(sorted(LIM_FRONT, key=len, reverse=True)))
BACK_RE = re.compile(r"\b(\d+) ([a-z]+) (%s)\b" % "|".join(LIM_BACK))

# ----------------------------------------------------------------------------------------------------------------
# the twelve numeric clause types: sentence frames (limit expression replaced by <L>, the unit kept after it),
# the unit and the side ("before" / "after" / None) the figure refers to
OBJ = r"(?P<obj>[a-z][a-z -]*?)"
CLAUSE_FRAMES = OrderedDict([
    ("response", ("hours", "after", [
        r"For the response time to be met, a %s must be answered <L> hours after it is received\." % OBJ,
        r"The (?P<role>%s) meets the response time when it answers a %s <L> hours after receipt\." % (R, OBJ),
        r"The response time is met if the (?P<role>%s) answers a %s <L> hours after receiving it\." % (R, OBJ)])),
    ("credit", ("hours", None, [
        r"A service credit is due for a calendar month in which the %s is unavailable for <L> hours\." % OBJ,
        r"The (?P<role>%s) owes a service credit for a calendar month if the %s is down for <L> hours in that month\." % (R, OBJ),
        r"Where the %s is unavailable for <L> hours during one calendar month, a service credit is due for that month\." % OBJ])),
    ("liability", (None, None, [
        r"A claim for damages against the (?P<role>%s) is payable in full when the amount claimed is <L> (?P<cur>[a-z]+)\." % R,
        r"The (?P<role>%s) pays a claim for damages in full if the amount claimed is <L> (?P<cur>[a-z]+)\." % R,
        r"Where the amount claimed as damages is <L> (?P<cur>[a-z]+), the (?P<role>%s) must pay the claim in full\." % R])),
    ("warranty", ("months", "after", [
        r"A defect is covered by the warranty when it is reported <L> months after delivery\.",
        r"The warranty covers a defect if the (?P<role>%s) reports it <L> months after delivery\." % R,
        r"Warranty cover applies to a defect that is reported <L> months after delivery\."])),
    ("payment", ("days", "after", [
        r"A payment is made in time if the (?P<role>%s) receives it <L> days after its due date\." % R,
        r"An invoice is paid in time when the money reaches the (?P<role>%s) <L> days after the due date\." % R,
        r"The (?P<role>%s) pays in time if its payment arrives <L> days after the due date of the invoice\." % R])),
    ("returns", ("days", "after", [
        r"A return of %s is in time when they are sent back <L> days after receipt\." % OBJ,
        r"The (?P<role>%s) may return %s if it sends them back <L> days after receiving them\." % (R, OBJ),
        r"The (?P<role>%s) must accept returned %s that were sent back <L> days after receipt\." % (R, OBJ)])),
    ("termination", ("days", "before", [
        r"A written notice of termination is in time only if it is given <L> days before the intended end date\.",
        r"Either party may end this agreement by written notice given <L> days before the intended end date\.",
        r"To end this agreement, a party must give written notice <L> days before the intended end date\."])),
    ("price", ("percent", None, [
        r"A yearly price increase is permitted if it amounts to <L> percent\.",
        r"Once in each contract year the (?P<role>%s) may increase its prices by <L> percent\." % R,
        r"The (?P<role>%s) may raise its prices once per contract year by <L> percent\." % R])),
    ("volume", ("units", None, [
        r"An order qualifies for the reduced unit price if it covers <L> units\.",
        r"The (?P<role>%s) is charged the reduced unit price for any single order of <L> units\." % R,
        r"The reduced unit price applies to a single order of <L> units\."])),
    ("deposit", ("percent", None, [
        r"An order becomes binding once the (?P<role>%s) has paid a deposit of <L> percent of the order value\." % R,
        r"An order is binding if a deposit of <L> percent of its value has been paid\.",
        r"The (?P<role>%s) is bound by an order when it has received a deposit of <L> percent of the order value\." % R])),
    ("late", ("days", None, [
        r"An order may be cancelled by the (?P<role>%s) once its delivery is late by <L> days\." % R,
        r"The (?P<role>%s) may cancel an order if its delivery is late by <L> days\." % R,
        r"Where the delivery of an order is late by <L> days, the (?P<role>%s) has the right to cancel it\." % R])),
    ("records", ("months", None, [
        r"Destroying the %s is allowed only after the (?P<role>%s) has kept them for <L> months from the end of this agreement\." % (OBJ, R),
        r"The (?P<role>%s) may destroy the %s once it has kept them for <L> months after the end of this agreement\." % (R, OBJ),
        r"The %s may be destroyed when they have been kept for <L> months after the end of this agreement\." % OBJ])),
])
CLAUSE_RES = [(t, u, side, re.compile("^" + f + "$")) for t, (u, side, fr) in CLAUSE_FRAMES.items() for f in fr]

# plain clauses (no figure); R stands for a party role
PLAIN = {
    "Changes to this agreement are valid only if both parties sign them in writing.": "Written form",
    "Each party keeps the business information of the other party confidential and uses it only for the purposes of this agreement.": "Confidentiality",
    "Each party names a contact person and promptly informs the other party of any change.": "Contact persons",
    "If one clause of this agreement proves invalid, the remaining clauses stay in force.": "Severability",
    "Neither party is in breach while an event beyond its reasonable control prevents performance.": "Unforeseeable events",
    "Neither party may transfer its rights under this agreement to a third party without the written consent of the other party.": "Assignment",
    "The R keeps adequate insurance cover for its activities under this agreement.": "Insurance",
    "The R may use subcontractors but remains responsible for their work.": "Subcontractors",
    "The parties cooperate in good faith and share the information needed to perform this agreement.": "Cooperation",
    "The parties try to settle any dispute by talks between their managers before taking any further step.": "Disputes",
    "This agreement is drawn up in one language, and its text prevails over any translation.": "Language",
    "This agreement replaces all earlier arrangements between the parties on the same subject.": "Entire agreement",
}
LABEL_TO_KIND = {"Records": "records", "Response time": "response", "Returns": "returns", "Price changes": "price",
                 "Liability": "liability", "Service credits": "credit", "Payment": "payment", "Warranty": "warranty",
                 "Volume pricing": "volume", "Termination": "termination", "Deposit": "deposit",
                 "Late delivery": "late"}
for _k in PLAIN.values():
    LABEL_TO_KIND[_k] = "plain:" + _k

# ----------------------------------------------------------------------------------------------------------------
# facts of the case: one figure per line
FACT_FRAMES = OrderedDict([
    ("response", [
        r"A %s was answered by the (?P<role>%s) (?P<n>\d+) hours after receipt\." % (OBJ, R),
        r"(?P<n>\d+) hours after receiving a %s, the (?P<role>%s) answered it\." % (OBJ, R),
        r"The (?P<role>%s) answered a %s (?P<n>\d+) hours after receiving it\." % (R, OBJ)]),
    ("liability", [
        r"A claim for damages of (?P<n>\d+) (?P<cur>[a-z]+) has been made against the (?P<role>%s)\." % R,
        r"The (?P<role2>%s) claims damages of (?P<n>\d+) (?P<cur>[a-z]+) from the (?P<role>%s)\." % (R, R),
        r"The (?P<role2>%s) has claimed (?P<n>\d+) (?P<cur>[a-z]+) in damages from the (?P<role>%s)\." % (R, R)]),
    ("warranty", [
        r"A defect was reported to the (?P<role>%s) (?P<n>\d+) months after delivery\." % R,
        r"(?P<n>\d+) months after delivery, the (?P<role2>%s) reported a defect\." % R,
        r"The (?P<role2>%s) reported a defect (?P<n>\d+) months after delivery\." % R]),
    ("price", [
        r"A price increase of (?P<n>\d+) percent for the coming contract year was announced by the (?P<role>%s)\." % R,
        r"For the coming contract year the (?P<role>%s) raised its prices by (?P<n>\d+) percent\." % R,
        r"The (?P<role>%s) announced a price increase of (?P<n>\d+) percent for the coming contract year\." % R]),
    ("volume", [
        r"A single order of (?P<n>\d+) units was placed by the (?P<role2>%s)\." % R,
        r"The (?P<role2>%s) ordered (?P<n>\d+) units in a single order\." % R,
        r"The (?P<role2>%s) placed a single order of (?P<n>\d+) units\." % R]),
    ("records", [
        r"After the agreement ended, the (?P<role>%s) kept the %s for (?P<n>\d+) months and then destroyed them\." % (R, OBJ),
        r"The (?P<role>%s) destroyed the %s after keeping them for (?P<n>\d+) months from the end of the agreement\." % (R, OBJ),
        r"The %s were kept for (?P<n>\d+) months after the end of the agreement and were then destroyed\." % OBJ]),
    ("late", [
        r"An order was delivered to the (?P<role2>%s) (?P<n>\d+) days late\." % R,
        r"The (?P<role>%s) delivered an order (?P<n>\d+) days late\." % R,
        r"The delivery of an order reached the (?P<role2>%s) (?P<n>\d+) days late\." % R]),
    ("credit", [
        r"During the last calendar month the %s was unavailable for (?P<n>\d+) hours\." % OBJ,
        r"In the last calendar month the %s was down for (?P<n>\d+) hours in total\." % OBJ,
        r"The downtime of the %s in the last calendar month came to (?P<n>\d+) hours\." % OBJ]),
    ("deposit", [
        r"For an order, a deposit of (?P<n>\d+) percent of its value was paid by the (?P<role2>%s)\." % R,
        r"The (?P<role2>%s) paid a deposit of (?P<n>\d+) percent of the order value\." % R,
        r"The (?P<role>%s) received a deposit of (?P<n>\d+) percent of the order value from the (?P<role2>%s)\." % (R, R)]),
    ("returns", [
        r"(?P<n>\d+) days after receipt, the (?P<role2>%s) sent %s back to the (?P<role>%s)\." % (R, OBJ, R),
        r"Some %s were sent back to the (?P<role>%s) (?P<n>\d+) days after receipt\." % (OBJ, R),
        r"The (?P<role2>%s) sent %s back (?P<n>\d+) days after receiving them\." % (R, OBJ)]),
    ("payment", [
        r"(?P<n>\d+) days after the due date of an invoice, the (?P<role2>%s)'s payment arrived\." % R,
        r"The (?P<role2>%s) paid an invoice, and the money reached the (?P<role>%s) (?P<n>\d+) days after the due date\." % (R, R),
        r"The (?P<role>%s) received the (?P<role2>%s)'s payment of an invoice (?P<n>\d+) days after its due date\." % (R, R)]),
    ("termination", [
        r"(?P<n>\d+) days before the intended end date, the (?P<role2>%s) gave written notice of termination\." % R,
        r"The (?P<role2>%s) gave written notice of termination (?P<n>\d+) days before the intended end date\." % R,
        r"Written notice of termination was given by the (?P<role2>%s) (?P<n>\d+) days before the intended end date\." % R]),
])
FACT_RES = [(t, re.compile("^" + f + "$")) for t, fr in FACT_FRAMES.items() for f in fr]

# points at issue: (question text, subject, polarity); polarity True = "yes" means the clause is satisfied
PAI_LIST = [
    ("was the notice of termination given in time", "termination", True),
    ("was the notice of termination given too late", "termination", False),
    ("does the notice of termination meet the notice period", "termination", True),
    ("does the notice of termination fall short of the notice period", "termination", False),
    ("is the deposit large enough to make the order binding", "deposit", True),
    ("is the deposit too small to make the order binding", "deposit", False),
    ("is the order still not binding", "deposit", False),
    ("has the order become binding", "deposit", True),
    ("is the price increase too high", "price", False),
    ("is the price increase permitted", "price", True),
    ("does the price increase go beyond what the agreement permits", "price", False),
    ("may the (?P<role>%s) raise its prices by that much" % R, "price", True),
    ("must the (?P<role>%s) pay the whole amount claimed" % R, "liability", True),
    ("is the amount claimed too high to be paid in full", "liability", False),
    ("may the (?P<role>%s) decline to pay the claim in full" % R, "liability", False),
    ("is the claim for damages payable in full", "liability", True),
    ("is the defect covered by the warranty", "warranty", True),
    ("was the defect reported too late for the warranty", "warranty", False),
    ("was the defect reported in time for the warranty", "warranty", True),
    ("is the defect outside the warranty", "warranty", False),
    ("must the (?P<role>%s) keep the order despite the delay" % R, "late", False),
    ("may the (?P<role>%s) cancel the order" % R, "late", True),
    ("does the delay give the (?P<role>%s) the right to cancel the order" % R, "late", True),
    ("is the delay too short for the (?P<role>%s) to cancel the order" % R, "late", False),
    ("was the return made too late", "returns", False),
    ("was the return made in time", "returns", True),
    ("is the (?P<role>%s) entitled to make this return" % R, "returns", True),
    ("is the (?P<role>%s) no longer entitled to make this return" % R, "returns", False),
    ("did the (?P<role>%s) answer in time" % R, "response", True),
    ("was the response time missed", "response", False),
    ("did the (?P<role>%s) answer too late" % R, "response", False),
    ("was the response time met", "response", True),
    ("does the (?P<role>%s) owe a service credit for that month" % R, "credit", True),
    ("does that month pass without a service credit", "credit", False),
    ("is a service credit due for that month", "credit", True),
    ("was the downtime too short for a service credit", "credit", False),
    ("did the (?P<role>%s) pay the invoice too late" % R, "payment", False),
    ("did the (?P<role>%s) pay the invoice in time" % R, "payment", True),
    ("was the payment made in time", "payment", True),
    ("was the payment late", "payment", False),
    ("is the order too small for the reduced unit price", "volume", False),
    ("does the reduced unit price apply to the order", "volume", True),
    ("does the order qualify for the reduced unit price", "volume", True),
    ("does the order miss the reduced unit price", "volume", False),
    ("were the %s destroyed too early" % OBJ, "records", False),
    ("was the (?P<role>%s) allowed to destroy the %s at that time" % (R, OBJ), "records", True),
    ("had the %s been kept long enough" % OBJ, "records", True),
    ("did the (?P<role>%s) destroy the %s before it was allowed to" % (R, OBJ), "records", False),
]
PAI_RES = [(re.compile("^" + p + r"\?$"), s, pol) for p, s, pol in PAI_LIST]

REQ_PAI = [("does the request fail", False), ("is the request successful", True),
           ("is the request unsuccessful", False), ("does the request succeed", True)]

# conditions of a request: all are stated positively
COND_LIST = [
    ("the notice of termination was given in time", "termination"),
    ("the order has become binding", "deposit"),
    ("the price increase is permitted", "price"),
    ("the response time was met", "response"),
    ("the claim for damages is payable in full", "liability"),
    ("the return was made in time", "returns"),
    ("the (?P<role>%s) may cancel the order" % R, "late"),
    ("the defect is covered by the warranty", "warranty"),
    ("a service credit is due for that month", "credit"),
    ("the order qualifies for the reduced unit price", "volume"),
    ("the payment was made in time", "payment"),
    ("the %s had been kept long enough" % OBJ, "records"),
]
COND_RES = [(re.compile("^" + p + "$"), s) for p, s in COND_LIST]

REQ_FRAMES = [
    re.compile(r"^A request has been made\. Both of the following must hold for it to succeed; if either one does not "
               r"hold, it fails: \(a\) (?P<a>.+); \(b\) (?P<b>.+)\.$"),
    re.compile(r"^A request is under review\. It succeeds if both of the following hold and fails if at least one of "
               r"them does not: \(a\) (?P<a>.+); \(b\) (?P<b>.+)\.$"),
    re.compile(r"^A request is to be decided\. It is successful when \(a\) and \(b\) both hold and unsuccessful in "
               r"every other situation: \(a\) (?P<a>.+); \(b\) (?P<b>.+)\.$"),
]

OPENINGS = [
    re.compile(r'^(?P<doc>[A-Za-z ]+ agreement) between (?P<n1>.+?) \("the (?P<r1>\w+)"\) and (?P<n2>.+?) \("the (?P<r2>\w+)"\)\. '
               r'Two versions of its text are set out below, followed by a case\.$'),
    re.compile(r'^Below are version A and version B of an agreement \((?P<doc>[^)]+)\) between (?P<n1>.+?) \("the (?P<r1>\w+)"\) '
               r'and (?P<n2>.+?) \("the (?P<r2>\w+)"\), and then a case\.$'),
    re.compile(r'^Parties: (?P<n1>.+?) \("the (?P<r1>\w+)"\) and (?P<n2>.+?) \("the (?P<r2>\w+)"\)\. Document: (?P<doc>[^,]+), '
               r'in two versions \(A and B\), with a case at the end\.$'),
]
HEADINGS = ("How to read the texts:", "Reading rules:", "Conventions:")
HEADER_STYLES = [("--- Version A ---", "--- Version B ---", "--- Case ---"),
                 ("Version A:", "Version B:", "Case:"),
                 ("VERSION A", "VERSION B", "CASE"),
                 ("[Version A]", "[Version B]", "[Case]")]
CLAUSE_LINE_RES = [
    re.compile(r"^Clause (?P<num>\d+) - (?P<label>[^:]+): (?P<text>.+)$"),
    re.compile(r"^\((?P<num>\d+)\) (?P<text>.+)$"),
    re.compile(r"^Art\. (?P<num>\d+): (?P<text>.+)$"),
    re.compile(r"^(?P<num>\d+)\. (?P<label>[^.]+)\. (?P<text>.+)$"),
]
QUESTION = "Does the change between the two versions alter the answer to the point at issue?"


# ----------------------------------------------------------------------------------------------------------------
RULES = OrderedDict([
    ("twice", [
        "- The case is to be decided twice: under version A as if it were the only text, and under version B as if it were the only text.",
        "- Version A and version B are two texts of one agreement; the case is decided once under version A alone and once under version B alone.",
        "- Treat each version as a complete text of the agreement and decide the case under each of them separately."]),
    ("subject", [
        "- The numbering can shift from one version to the other when a clause is moved or added, so clauses correspond by subject and not by number.",
        "- Clause numbers may differ between the versions (a clause can be moved or added); a clause is identified by its subject, not by its number.",
        "- A clause may carry another number in version B than in version A, because clauses can be moved or added; match clauses by their subject."]),
    # meaning of all three: what a clause provides applies exactly when its stated condition is met (iff)
    ("complete", [
        "- Read every clause as complete: its consequence follows exactly when its stated condition is fulfilled, and in no other situation.",
        "- Each clause states its condition in full: what it provides applies when the condition is met and does not apply otherwise.",
        "- The condition written in a clause is complete: if it is met, what the clause provides applies, and if it is not met, it does not apply."]),
    # meaning of all three: the clause on the subject decides, other facts are irrelevant
    ("alone", [
        "- A point at issue, and each condition of a request, is decided by the clause on its subject alone; facts about other subjects have no bearing on it.",
        "- Each point at issue and each condition of a request depends on one clause, the one on its subject; other facts of the case leave it untouched.",
        "- Only the clause on the subject of a point at issue (or of a condition of a request) decides it; facts that belong to other subjects do not matter for it."]),
])
PLAIN_COUNTING = {"at least", "at most", "no more than", "no fewer than", "no less than", "no later than",
                  "or more", "or fewer", "or less"}
PLAIN_NONCOUNTING = {"more than", "fewer than", "less than", "over", "under", "below"}
LIMIT_SPLIT = re.compile(r", and it does not count with|; it does not satisfy a limit worded with|, and fails a limit that uses")


def parse_rules(bullets):
    """Check the five reading rules (four fixed rules, one on limits); return (counting words, non counting words)."""
    seen = set()
    counting = noncounting = None
    for b in bullets:
        kind = None
        for k, variants in RULES.items():
            if b in variants:
                kind = k
        if kind is None and b.startswith("- ") and "at least" in b and '"' in b:
            kind = "limit"
            parts = LIMIT_SPLIT.split(b)
            if len(parts) != 2:
                raise Unparsed("cannot split the limit rule")
            counting = set(re.findall(r'"([^"]+)"', parts[0]))
            noncounting = set(re.findall(r'"([^"]+)"', parts[1]))
            if not counting or not noncounting or counting & noncounting:
                raise Unparsed("limit rule lists unusable")
        if kind is None:
            raise Unparsed("unrecognised reading rule: %r" % b[:90])
        if kind in seen:
            raise Unparsed("reading rule %s twice" % kind)
        seen.add(kind)
    if seen != {"twice", "subject", "complete", "alone", "limit"}:
        raise Unparsed("reading rules incomplete: %s" % sorted(seen))
    # my own plain English judgement of which wordings include the stated figure must agree with the lists of the state
    if counting != PLAIN_COUNTING or noncounting != PLAIN_NONCOUNTING:
        raise Unparsed("the lists of the state differ from the plain English meaning of the wordings")
    return counting, noncounting


def split_state(state):
    lines = state.split("\n")
    m = None
    for p in OPENINGS:
        m = p.match(lines[0])
        if m:
            break
    if not m:
        raise Unparsed("opening line not recognised: %r" % lines[0][:80])
    roles = {m.group("r1"), m.group("r2")}
    if lines[1] not in HEADINGS:
        raise Unparsed("heading line not recognised: %r" % lines[1][:60])
    style = None
    for st in HEADER_STYLES:
        if all(lines.count(h) == 1 for h in st):
            style = st
            break
    if style is None:
        raise Unparsed("version/case headers not found")
    ia, ib, ic = (lines.index(h) for h in style)
    if not (2 < ia < ib < ic):
        raise Unparsed("headers out of order")
    bullets = lines[2:ia]
    if len(bullets) != 5 or not all(x.startswith("- ") for x in bullets):
        raise Unparsed("expected five reading rules, got %d" % len(bullets))
    return roles, bullets, lines[ia + 1:ib], lines[ib + 1:ic], lines[ic + 1:]


def canon_limit(body, counting, noncounting):
    """Find the single limit expression of a numeric clause; return (canonical body, op, figure, unit)."""
    fronts = FRONT_RE.findall(body)
    backs = BACK_RE.findall(body)
    if len(fronts) + len(backs) != 1:
        raise Unparsed("no unique limit wording in: %r" % body[:100])
    if fronts:
        word, n = fronts[0]
        canon = FRONT_RE.sub("<L>", body)
        unit = None
    else:
        n, unit, word = backs[0]
        canon = BACK_RE.sub(lambda mm: "<L> " + mm.group(2), body)
    if word not in counting and word not in noncounting:
        raise Unparsed("limit word %r is in neither list of the state" % word)
    inclusive = word in counting
    return canon, word, int(n), inclusive


def interval(word, n, inclusive, side):
    """Integer interval (lo, hi) admitted by the limit; None = unbounded."""
    if word == "no later than":
        if side == "before":                    # a notice given no later than N days BEFORE the end: lead time >= N
            lower = True
        elif side == "after":                   # a reply no later than N hours AFTER receipt: delay <= N
            lower = False
        else:
            raise Unparsed("'no later than' without before/after")
    elif word in LOWER_WORDS:
        lower = True
    elif word in UPPER_WORDS:
        lower = False
    else:
        raise Unparsed("direction of %r unknown" % word)
    if lower:
        return (n if inclusive else n + 1, None)
    return (None, n if inclusive else n - 1)


def parse_clause(text, counting, noncounting, roles):
    t = text
    if t in PLAIN:
        return {"kind": "plain:" + PLAIN[t], "text": t}
    named = re.findall(r"\b%s\b" % R, t)
    tr = re.sub(r"\b%s\b" % R, "R", t)
    if tr in PLAIN and len(named) == 1:                  # a plain clause that names one party
        if named[0] not in roles:
            raise Unparsed("role %r is not a party" % named[0])
        return {"kind": "plain:" + PLAIN[tr], "text": t}
    nums = re.findall(r"\d+", t)
    if len(nums) != 1:
        raise Unparsed("clause with %d figures: %r" % (len(nums), t[:90]))
    canon, word, n, inclusive = canon_limit(t, counting, noncounting)
    for kind, unit, side, rx in CLAUSE_RES:
        m = rx.match(canon)
        if m:
            gd = m.groupdict()
            if unit is not None and ("<L> %s" % unit) not in canon:
                raise Unparsed("unit mismatch in %r" % t[:90])
            cur = gd.get("cur")
            ob = gd.get("obj")
            return {"kind": kind, "word": word, "n": n, "inclusive": inclusive, "side": side,
                    "iv": interval(word, n, inclusive, side), "obj": ob, "cur": cur, "role": gd.get("role"),
                    "unit": unit or cur, "text": t}
    raise Unparsed("clause sentence not recognised: %r" % t[:100])


def parse_version(lines, counting, noncounting, roles):
    out = []
    expect = 1
    for ln in lines:
        m = None
        for rx in CLAUSE_LINE_RES:
            m = rx.match(ln)
            if m:
                break
        if not m:
            raise Unparsed("clause line not recognised: %r" % ln[:80])
        if int(m.group("num")) != expect:
            raise Unparsed("clause numbering broken at %s" % m.group("num"))
        expect += 1
        label = m.groupdict().get("label")
        c = parse_clause(m.group("text"), counting, noncounting, roles)
        if label is not None:
            if label not in LABEL_TO_KIND:
                raise Unparsed("unknown clause label %r" % label)
            if LABEL_TO_KIND[label] != c["kind"]:
                raise Unparsed("label %r does not fit the clause content %r" % (label, c["kind"]))
        if c.get("role") and c["role"] not in roles:
            raise Unparsed("role %r is not a party" % c["role"])
        c["num"] = int(m.group("num"))
        out.append(c)
    return out


def by_subject(clauses):
    d = {}
    for c in clauses:
        if c["kind"] in d:
            raise Unparsed("two clauses on subject %s" % c["kind"])
        d[c["kind"]] = c
    return d


def parse_fact(line, roles):
    hits = []
    for kind, rx in FACT_RES:
        m = rx.match(line)
        if m:
            hits.append((kind, m))
    if len(hits) != 1:
        raise Unparsed("fact line %s: %r" % ("ambiguous" if hits else "not recognised", line[:90]))
    kind, m = hits[0]
    gd = m.groupdict()
    for k in ("role", "role2"):
        if gd.get(k) and gd[k] not in roles:
            raise Unparsed("role %r is not a party" % gd[k])
    return kind, {"n": int(gd["n"]), "obj": gd.get("obj"), "cur": gd.get("cur"), "line": line}


def parse_point(line, roles):
    """Return ('single', subject, polarity, obj) or ('request', positive?)."""
    pre = "Point at issue: "
    if not line.startswith(pre):
        raise Unparsed("last line is not the point at issue")
    q = line[len(pre):]
    for text, pos in REQ_PAI:
        if q == text + "?":
            return ("request", pos)
    hits = []
    for rx, subj, pol in PAI_RES:
        m = rx.match(q)
        if m:
            hits.append((subj, pol, m.groupdict().get("obj")))
    if len(hits) != 1:
        raise Unparsed("point at issue %s: %r" % ("ambiguous" if hits else "not recognised", q[:90]))
    return ("single",) + hits[0]


def parse_cond(text):
    hits = []
    for rx, subj in COND_RES:
        m = rx.match(text)
        if m:
            hits.append((subj, m.groupdict().get("obj")))
    if len(hits) != 1:
        raise Unparsed("request condition not recognised: %r" % text[:80])
    return hits[0]


def holds(clause, fact):
    """Does the fact satisfy the clause?  Membership in the integer interval admitted by the clause."""
    lo, hi = clause["iv"]
    x = fact["n"]
    # the object (report type, goods, system, records) and the currency must be the same subject in clause and fact
    if clause.get("obj") is not None and fact.get("obj") is not None and clause["obj"] != fact["obj"]:
        raise Unparsed("fact about %r, clause about %r" % (fact["obj"], clause["obj"]))
    if clause.get("cur") is not None and fact.get("cur") is not None and clause["cur"] != fact["cur"]:
        raise Unparsed("fact in %r, clause in %r" % (fact["cur"], clause["cur"]))
    return (lo is None or x >= lo) and (hi is None or x <= hi)


def decide(state):
    roles, bullets, linesA, linesB, case = split_state(state)
    counting, noncounting = parse_rules(bullets)
    A = parse_version(linesA, counting, noncounting, roles)
    B = parse_version(linesB, counting, noncounting, roles)
    sa, sb = by_subject(A), by_subject(B)
    # clauses correspond by subject: the numeric subjects must be the same set; plain ones may be added in B
    num_a = {k for k in sa if not k.startswith("plain:")}
    num_b = {k for k in sb if not k.startswith("plain:")}
    if not num_a <= num_b or len(num_b - num_a) > 1:
        raise Unparsed("numeric subjects differ between A and B: %s" % sorted(num_a ^ num_b))
    for k in num_a:
        for f in ("obj", "cur", "unit"):
            if sa[k].get(f) != sb[k].get(f):
                raise Unparsed("subject %s changed its %s between versions" % (k, f))
    # the case
    if len(case) < 2:
        raise Unparsed("case too short")
    point = parse_point(case[-1], roles)
    facts = {}
    cond_lines = []
    for ln in case[:-1]:
        if ln.startswith("A request"):
            cond_lines.append(ln)
            continue
        kind, f = parse_fact(ln, roles)
        if kind in facts:
            raise Unparsed("two facts on subject %s" % kind)
        facts[kind] = f
    for kind, f in facts.items():                         # every fact is about a clause that exists, with the same object
        if kind not in sa:
            raise Unparsed("fact on subject %s, but version A has no such clause" % kind)
        for V in (sa, sb):
            if kind in V:
                for fld in ("obj", "cur"):
                    if V[kind].get(fld) is not None and f.get(fld) is not None and V[kind][fld] != f[fld]:
                        raise Unparsed("fact and clause differ in %s on subject %s" % (fld, kind))
    if point[0] == "request":
        if len(cond_lines) != 1:
            raise Unparsed("request announced %d times" % len(cond_lines))
        m = None
        for rx in REQ_FRAMES:
            m = rx.match(cond_lines[0])
            if m:
                break
        if not m:
            raise Unparsed("request sentence not recognised")
        conds = [parse_cond(m.group("a")), parse_cond(m.group("b"))]
        if conds[0][0] == conds[1][0]:
            raise Unparsed("both conditions on one subject")
        positive = point[1]
        topics = [(s, True, o) for s, o in conds]
    else:
        if cond_lines:
            raise Unparsed("a request is described but the point at issue is not about it")
        _, subj, pol, obj = point
        topics = [(subj, pol, obj)]
        positive = True
    res = []
    for sa_or_sb in (sa, sb):
        verdicts = []
        for subj, pol, obj in topics:
            if subj not in sa_or_sb:
                raise Unparsed("no clause on %s" % subj)
            if subj not in facts:
                raise Unparsed("no fact on %s" % subj)
            c = sa_or_sb[subj]
            if obj is not None and c.get("obj") is not None and obj != c["obj"]:
                raise Unparsed("point at issue about %r, clause about %r" % (obj, c["obj"]))
            ok = holds(c, facts[subj])
            verdicts.append(ok if pol else (not ok))
        if point[0] == "request":
            succeeded = all(verdicts)
            res.append(succeeded if positive else (not succeeded))
        else:
            res.append(verdicts[0])
    return res[0], res[1]


def map_options(options):
    pats = [("AB", re.compile(r"is yes under version A and no under version B")),
            ("BA", re.compile(r"is no under version A and yes under version B")),
            ("SAME", re.compile(r"is the same under version A and under version B"))]
    found = {}
    for k, txt in options.items():
        for tag, rx in pats:
            if rx.search(txt):
                if tag in found:
                    raise Unparsed("option kind %s twice" % tag)
                found[tag] = k
    if set(found) != {"AB", "BA", "SAME"} or len(options) != 3:
        raise Unparsed("options not recognised")
    return found


def solve(state, question, options):
    if question.strip() != QUESTION:
        raise Unparsed("question not recognised: %r" % question[:80])
    found = map_options(options)
    a, b = decide(state)
    if a == b:
        return found["SAME"]
    return found["AB"] if a else found["BA"]
