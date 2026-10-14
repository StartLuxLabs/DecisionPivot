"""Independent second implementation for the task `policy_case` (label audit of gen_v4).

Written from the rendered text alone (view of the items + the prose of the task README); the generator was never read.

What a careful reader does with the state (a JSON object with `policy` and `case`):
  1. read the case record (`key: value` lines),
  2. read the numbered rules (conditions joined by "and", one outcome), the exceptions ("Rule N does not apply when ..."),
     the precedence statement (lower or higher number wins) and the default (outcome when no rule applies),
  3. a rule APPLIES when every one of its conditions holds for the case and no exception of that rule holds
     (a rule that holds but is waived does not apply, also for the wording "a request that no rule covers"),
  4. no applicable rule -> the default; otherwise the outcomes of the applicable rules are compared pairwise and the
     precedence statement decides between two that differ (with three or more applicable rules the same statement is
     applied pair by pair; the result is the outcome of the lowest- / highest-numbered applicable rule).
Conventions taken from the words: "at least / or more / or higher / not below" count the limit, "more than / above /
exceeds / greater than" do not; "at most / or less / not more than / does not exceed" count the limit, "below / under /
less than / lower than" do not; a range counts both limits ("inclusive", "both limits included").
Anything that is not recognised raises ValueError, so that no fact can be skipped silently.
"""
import json
import re

OUTCOME_WORDS = {
    "approved": "approve", "Approve": "approve", "approve": "approve",
    "denied": "deny", "Deny": "deny", "deny": "deny",
    "escalated to a human reviewer": "escalate", "Escalate": "escalate", "escalate": "escalate",
}

# ---- the reader's dictionary: phrase used in the policy -> key of the case record -------------------------------------
# numeric: phrase -> (key, unit word that must follow the number, '' for plain counts / levels)
NUMERIC = {
    "refund amount": ("amount_eur", "EUR"),
    "claim amount": ("amount_eur", "EUR"),
    "account age": ("account_age_days", "days"),
    "time since purchase": ("days_since_purchase", "days"),
    "time since the expense": ("days_since_expense", "days"),
    "time since the last security training": ("days_since_training", "days"),
    "tenure": ("tenure_days", "days"),
    "requested access period": ("days_requested", "days"),
    "number of earlier refunds": ("previous_refunds", ""),
    "number of claims this quarter": ("claims_this_quarter", ""),
    "number of exports in the last 30 days": ("exports_last_30_days", ""),
    "export size": ("records", "records"),
    "clearance level": ("clearance_level", ""),
}
# categories: names, tiers, classes, grades (compared as words)
CATEGORY = {
    "region": "region", "data region": "data_region", "plan tier": "plan_tier", "team": "team",
    "system class": "system_class", "cost centre": "cost_centre", "grade": "grade",
}
# yes / no flags
FLAG = {
    "bank dispute": "bank_dispute", "company card use": "company_card", "consent on file": "consent_on_file",
    "contractor status": "contractor", "duplicate suspicion": "duplicate_suspected", "fraud alert": "fraud_alert",
    "item returned": "item_returned", "legal hold": "legal_hold", "manager approval": "manager_approval",
    "on-call duty": "on_call_duty", "open incident": "open_incident", "personal data": "contains_personal_data",
    "pre-approval": "pre_approved", "proof of purchase": "proof_of_purchase", "receipt attached": "receipt_attached",
    "verified requester": "requester_verified",
}
IGNORED_KEYS = ("request_id", "submitted_on", "channel")     # in the record, never a condition

HEADINGS = {
    "General provisions": "general", "GENERAL": "general", "Conflicts and default:": "general",
    "Rules": "rules", "RULES": "rules", "Rules:": "rules",
    "Exceptions": "exceptions", "EXCEPTIONS": "exceptions", "Exceptions:": "exceptions",
}

_U = r"(?: (?P<unit>EUR|days|records))?"
NUM_PREDICATES = [      # (regex over what follows the attribute phrase, kind)
    (r"does not exceed (?P<a>\d+)" + _U, "le"),
    (r"exceeds (?P<a>\d+)" + _U, "gt"),
    (r"is (?P<a>\d+)" + _U + r" or (?:higher|more)", "ge"),
    (r"is (?P<a>\d+)" + _U + r" or less", "le"),
    (r"is above (?P<a>\d+)" + _U, "gt"),
    (r"is at least (?P<a>\d+)" + _U, "ge"),
    (r"is at most (?P<a>\d+)" + _U, "le"),
    (r"is below (?P<a>\d+)" + _U, "lt"),
    (r"is greater than (?P<a>\d+)" + _U, "gt"),
    (r"is less than (?P<a>\d+)" + _U, "lt"),
    (r"is lower than (?P<a>\d+)" + _U, "lt"),
    (r"is more than (?P<a>\d+)" + _U, "gt"),
    (r"is not below (?P<a>\d+)" + _U, "ge"),
    (r"is not more than (?P<a>\d+)" + _U, "le"),
    (r"is under (?P<a>\d+)" + _U, "lt"),
    (r"is between (?P<a>\d+) and (?P<b>\d+)" + _U + r" inclusive", "range"),
    (r"is from (?P<a>\d+) to (?P<b>\d+)" + _U + r" inclusive", "range"),
    (r"is within (?P<a>\d+) to (?P<b>\d+)" + _U + r" with both limits included", "range"),
    (r"lies in the range (?P<a>\d+) to (?P<b>\d+)" + _U + r" inclusive", "range"),
]
NUM_PREDICATES = [(re.compile(r"^" + p + r"$"), k) for p, k in NUM_PREDICATES]

CAT_PREDICATES = [
    (re.compile(r"^is (?:not one of|not among|not any of|none of) (?P<l>.+)$"), "notin"),
    (re.compile(r"^is (?:one of|among|any of|either) (?P<l>.+)$"), "in"),
    (re.compile(r"^(?:is not|differs from|is anything other than) (?P<v>\S+)$"), "ne"),
    (re.compile(r"^(?:is|equals) (?P<v>\S+)$"), "eq"),
]

FLAG_PATTERNS = [       # four ways to say "flag F has value yes / no"
    re.compile(r"^the (?P<f>.+?) flag is set to (?P<v>yes|no)$"),
    re.compile(r"^the case has the (?P<f>.+?) flag set to (?P<v>yes|no)$"),
    re.compile(r"^the record shows (?P<v>yes|no) for the (?P<f>.+?) flag$"),
    re.compile(r"^the (?P<f>.+?) flag is (?P<v>yes|no)$"),
]

OUT = r"(?P<out>approved|denied|escalated to a human reviewer)"
IMP = r"(?P<imp>Approve the request|Deny the request|Escalate the request to a human reviewer)"
RULE_FRAMES = [         # five frames of a rule (after the number)
    re.compile(r"^A request for which (?P<c>.+) is " + OUT + r"\.$"),
    re.compile(r"^If (?P<c>.+), the request is " + OUT + r"\.$"),
    re.compile(r"^When (?P<c>.+): " + IMP + r"\.$"),
    re.compile(r"^" + IMP + r" when (?P<c>.+)\.$"),
    re.compile(r"^The request must be " + OUT + r" (?:when|if) (?P<c>.+)\.$"),
]
RULE_NUMBER = [         # three ways to number a rule
    re.compile(r"^Rule (?P<n>\d+)\. (?P<body>.+)$"),
    re.compile(r"^\((?P<n>\d+)\) (?P<body>.+)$"),
    re.compile(r"^(?P<n>\d+)\. (?P<body>.+)$"),
]
EXC_FRAMES = [          # four frames of an exception
    re.compile(r"^Rule (?P<n>\d+) does not apply when (?P<c>.+)\.$"),
    re.compile(r"^Rule (?P<n>\d+) is waived if (?P<c>.+)\.$"),
    re.compile(r"^If (?P<c>.+), Rule (?P<n>\d+) does not apply\.$"),
    re.compile(r"^Exception to Rule (?P<n>\d+): it is not applied when (?P<c>.+)\.$"),
]
PRECEDENCE = [
    (re.compile(r"^When rules conflict, the rule with the lower number wins\.$"), "low"),
    (re.compile(r"^When rules conflict, the rule with the higher number wins\.$"), "high"),
    (re.compile(r"^If two applicable rules lead to different outcomes, the lower-numbered rule decides\.$"), "low"),
    (re.compile(r"^If two applicable rules lead to different outcomes, the higher-numbered rule decides\.$"), "high"),
    (re.compile(r"^Conflicting rules are resolved in favour of the rule with the smaller number\.$"), "low"),
    (re.compile(r"^Conflicting rules are resolved in favour of the rule with the larger number\.$"), "high"),
    (re.compile(r"^In a conflict between rules, the earlier rule in the list prevails\.$"), "low"),
    (re.compile(r"^In a conflict between rules, the later rule in the list prevails\.$"), "high"),
]
DEFAULTS = [
    re.compile(r"^A request that no rule covers is (?P<o>approved|denied|escalated to a human reviewer)\.$"),
    re.compile(r"^When none of the rules applies, (?P<o>approve|deny|escalate) the request(?: to a human reviewer)?\.$"),
    re.compile(r"^If no rule applies, the request is (?P<o>approved|denied|escalated to a human reviewer)\.$"),
    re.compile(r"^By default a request is (?P<o>approved|denied|escalated to a human reviewer) unless a rule says otherwise\.$"),
]


def _fail(msg):
    raise ValueError(msg)


# ---- case record ------------------------------------------------------------------------------------------------------
def parse_case(text):
    case = {}
    for ln in text.split("\n"):
        if not ln.strip():
            continue
        m = re.match(r"^([a-z0-9_]+): (\S+)$", ln)
        if not m:
            _fail("unreadable case line: %r" % ln)
        k, v = m.groups()
        if k in case:
            _fail("case key twice: " + k)
        case[k] = v
    known = set(k for k, _ in NUMERIC.values()) | set(CATEGORY.values()) | set(FLAG.values()) | set(IGNORED_KEYS)
    for k in case:
        if k not in known:
            _fail("unknown case key: " + k)
    return case


# ---- conditions -------------------------------------------------------------------------------------------------------
def make_condition(atom):
    """Return (description, predicate over the case record) for one condition text; raise if not recognised."""
    for rx in FLAG_PATTERNS:
        m = rx.match(atom)
        if m:
            phrase, want = m.group("f"), m.group("v")
            if phrase not in FLAG:
                _fail("unknown flag phrase %r in %r" % (phrase, atom))
            key = FLAG[phrase]
            return atom, (lambda case, key=key, want=want: _get(case, key, atom) == want)
    for phrase in sorted(list(NUMERIC) + list(CATEGORY), key=len, reverse=True):
        head = "the " + phrase + " "
        if not atom.startswith(head):
            continue
        rest = atom[len(head):]
        if phrase in NUMERIC:
            key, unit = NUMERIC[phrase]
            for rx, kind in NUM_PREDICATES:
                m = rx.match(rest)
                if m:
                    if (m.group("unit") or "") != unit:
                        _fail("unit %r where %r is expected: %r" % (m.group("unit"), unit, atom))
                    a = int(m.group("a"))
                    b = int(m.group("b")) if kind == "range" else None
                    if kind == "range" and a > b:
                        _fail("empty range in %r" % atom)
                    return atom, _numeric(key, kind, a, b, atom)
            _fail("unreadable numeric condition: %r" % atom)
        key = CATEGORY[phrase]
        rest = re.sub(r"^(?:on record|recorded for the case) ", "", rest)
        for rx, kind in CAT_PREDICATES:
            m = rx.match(rest)
            if m:
                if kind in ("in", "notin"):
                    vals = re.split(r", | or ", m.group("l"))
                    if len(vals) < 2 or any((not v) or " " in v for v in vals):
                        _fail("unreadable list in %r" % atom)
                else:
                    vals = [m.group("v")]
                return atom, _category(key, kind, vals, atom)
        _fail("unreadable category condition: %r" % atom)
    _fail("unrecognised condition: %r" % atom)


def _get(case, key, atom):
    if key not in case:
        _fail("case has no %r needed by %r" % (key, atom))
    return case[key]


def _numeric(key, kind, a, b, atom):
    def pred(case):
        v = _get(case, key, atom)
        if not re.match(r"^\d+$", v):
            _fail("non-integer %s=%r" % (key, v))
        v = int(v)
        if kind == "gt":
            return a < v
        if kind == "ge":
            return a <= v
        if kind == "lt":
            return v < a
        if kind == "le":
            return v <= a
        return a <= v <= b                       # range, both limits included (the text says so)
    return pred


def _category(key, kind, vals, atom):
    def pred(case):
        v = _get(case, key, atom)
        inside = v in vals
        return inside if kind in ("eq", "in") else not inside
    return pred


def parse_conditions(text):
    atoms = re.split(r" and (?=the )", text)       # a range ("between 5 and 9") is never followed by "the"
    return [make_condition(a) for a in atoms]


# ---- policy -----------------------------------------------------------------------------------------------------------
def parse_policy(text):
    rules, excs, precedence, default = [], [], [], []
    section = None
    seen_title = False
    for raw in text.split("\n"):
        ln = raw.rstrip()
        if not ln.strip():
            continue
        if not seen_title:
            seen_title = True
            if ln.endswith(".") or ln in HEADINGS:
                _fail("first line is not a title: %r" % ln)
            continue
        if ln in HEADINGS:
            section = HEADINGS[ln]
            continue
        # rule?
        done = False
        for rn in RULE_NUMBER:
            m = rn.match(ln)
            if m:
                n, body = int(m.group("n")), m.group("body")
                for fr in RULE_FRAMES:
                    f = fr.match(body)
                    if f:
                        o = f.groupdict().get("out") or f.groupdict().get("imp").split(" ")[0]
                        rules.append((n, parse_conditions(f.group("c")), OUTCOME_WORDS[o]))
                        break
                else:
                    _fail("unreadable rule: %r" % ln)
                if section not in (None, "rules"):
                    _fail("rule outside the rule section: %r" % ln)
                done = True
                break
        if done:
            continue
        bare = ln[2:] if ln.startswith("- ") else ln
        for fr in EXC_FRAMES:
            m = fr.match(bare)
            if m:
                excs.append((int(m.group("n")), parse_conditions(m.group("c"))))
                if section not in (None, "exceptions"):
                    _fail("exception outside the exception section: %r" % ln)
                done = True
                break
        if done:
            continue
        for rx, d in PRECEDENCE:
            if rx.match(bare):
                precedence.append(d)
                done = True
                break
        if done:
            if section not in (None, "general"):
                _fail("precedence outside the general section: %r" % ln)
            continue
        for rx in DEFAULTS:
            m = rx.match(bare)
            if m:
                default.append(OUTCOME_WORDS[m.group("o")])
                done = True
                break
        if done:
            if section not in (None, "general"):
                _fail("default outside the general section: %r" % ln)
            continue
        _fail("unrecognised policy line: %r" % ln)
    if not rules:
        _fail("no rules")
    if [r[0] for r in rules] != list(range(1, len(rules) + 1)):
        _fail("rules are not numbered 1..n in order: %r" % [r[0] for r in rules])
    if len(precedence) != 1:
        _fail("expected one precedence statement, found %d" % len(precedence))
    if len(default) != 1:
        _fail("expected one default, found %d" % len(default))
    for n, _ in excs:
        if not 1 <= n <= len(rules):
            _fail("exception refers to missing rule %d" % n)
    return rules, excs, precedence[0], default[0]


# ---- decision ---------------------------------------------------------------------------------------------------------
def decide(rules, excs, precedence, default, case):
    applicable = []
    for n, conds, outcome in rules:
        if not all(p(case) for _, p in conds):
            continue                                                # the rule does not hold
        if any(en == n and all(p(case) for _, p in ec) for en, ec in excs):
            continue                                                # waived by an exception that holds
        applicable.append((n, outcome))
    if not applicable:
        return default

    def beats(x, y):                                                 # does rule number x win against rule number y?
        return x < y if precedence == "low" else x > y

    # pairwise: an outcome is undefeated when, against every applicable rule with another outcome, one of its rules wins
    winners = []
    for o in sorted(set(oc for _, oc in applicable)):
        mine = [n for n, oc in applicable if oc == o]
        theirs = [n for n, oc in applicable if oc != o]
        if all(any(beats(x, y) for x in mine) for y in theirs):
            winners.append(o)
    if len(winners) != 1:
        _fail("no unique winner among %r" % applicable)
    # cross-check with the plain reading (the extreme-numbered applicable rule decides)
    pick = min(applicable) if precedence == "low" else max(applicable)
    if pick[1] != winners[0]:
        _fail("two readings of the precedence statement disagree")
    return winners[0]


def solve(state, question, options):
    if isinstance(state, str):
        try:
            state = json.loads(state)
        except ValueError:
            _fail("state is not a JSON object")
    if not isinstance(state, dict) or set(state) != {"policy", "case"}:
        _fail("state must have exactly the fields policy and case")
    if not re.match(r"^What does the policy require for this case\?$", question.strip()):
        _fail("unexpected question: %r" % question)
    # options: read what each one says
    by_outcome = {}
    for key, text in options.items():
        m = re.match(r"^The policy requires (approving|denying|escalating) the request(?: to a human reviewer)?\.$", text.strip())
        if not m:
            _fail("unreadable option %r: %r" % (key, text))
        o = {"approving": "approve", "denying": "deny", "escalating": "escalate"}[m.group(1)]
        if o in by_outcome:
            _fail("two options say the same")
        by_outcome[o] = key
    if sorted(by_outcome) != ["approve", "deny", "escalate"]:
        _fail("options are not approve / deny / escalate")
    case = parse_case(state["case"])
    rules, excs, precedence, default = parse_policy(state["policy"])
    return by_outcome[decide(rules, excs, precedence, default, case)]
