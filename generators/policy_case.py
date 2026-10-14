"""Task policy_case (layer B, generated, programmatic truth): "what does the policy require for this case?"

Item design.  The state is a written policy for handling a request (refunds, data exports, access to an internal system,
expense claims) with 4, 8 or 12 numbered rules, and a case record of `key: value` lines.  A rule names conditions over
case attributes (a number with a unit, a region / tier / team, a yes-no flag) and an outcome; the conditions are stated in
words that say whether a limit counts ("at least 90 days" counts 90, "more than 90 days" does not; "between 50 and 200 EUR
inclusive").  Every policy also has
  exceptions     "Rule 5 does not apply when ..."  (one to four, in four phrasings),
  a precedence   "If two applicable rules lead to different outcomes, the lower-numbered (or: the higher-numbered) rule decides",
  a default      "If no rule applies, the request is escalated / denied / approved".
The question is "What does the policy require for this case?"; options approve / deny / escalate in an order drawn per item
(``meta.order``).  Truth is a rule engine: a rule applies when all its conditions hold and no exception that names it holds;
no rule applicable -> default; applicable rules that agree -> that outcome; otherwise the precedence statement decides.

``meta.needs`` says what the answer needs, proved by ablation: plain (no exception cancels an applicable rule and the applicable
rules agree), exception (switching the exceptions off changes the outcome and no conflict is left), precedence (two applicable
rules disagree and reversing the precedence changes the outcome).  A third of the items each (200).  Cases that mix the two are
not used.  ``meta.near_threshold`` is true in a third of the items (200): a numeric attribute of the case lies within 5 % of a
threshold of the policy (or on it) AND moving it to the other side of that threshold would change the outcome (asserted); in the
other items no numeric attribute is within 10 % of any threshold of the policy.

Triples.  So that the policy text cannot tell the outcome, every policy is used for ONE CASE PER OUTCOME: 198 policies give a
triple (the same policy text with a case that leads to approve, one to deny, one to escalate; the three cases need three different
things - plain, exception, precedence - in an order the generator chooses, and one of the three is a near-threshold case) and
three more policies give a pair, which makes 600 items.  ``group`` = the policy; the metric is item accuracy.  The text of the policy
is identical in the members of a group, so the vocabulary of the policy is the same in the three outcome classes by construction.

Balance (exact): 200 items per dial level (rules 4, 8, 12; ``meta.level`` = 1, 2, 3), 200 per outcome (67 / 67 / 66 inside every level),
200 per ``needs``, 200 near-threshold items; domains and precedence directions are balanced as well.

gen_v4 (2026-10-08) - policies that read like policies.  Every attribute has a direction of risk (DOMAINS: ``risk`` of a number = the
end of the scale that signals risk, of a flag = the value that signals risk).  A rule that denies or escalates reads at least one condition
that signals risk and none that signals low risk; a rule that approves reads only conditions that signal low risk; an exception to an
approving rule is a risk signal, an exception to a denying / escalating rule a mitigating condition; a flag that can signal risk is read only
where some deny / escalate rule reacts to it, and has its risk value in a case record only then.  ``make_policy`` repairs a draft until
``problems`` is empty: no rule is dead (``liveness``: the attribute space is cut into cells that no condition can tell apart, a rule decides
when it is the first applicable rule under the precedence statement and the outcome without it would be another one; exact, with the order
of the case record - DEPS - respected), no exception is dead, no two rules with the same outcome repeat each other (``duplicate_pairs``).
Limits sit in the part of the scale where they mean something (``make_atom``).
Case records keep fields in their natural order (account age >= days since purchase, training no older than tenure, ...), numbers that no
rule reads stay on the safe side of their scale, and the three cases of a policy are picked so that they carry about the same number of
risk signals (``pick_cases``, ``meta.risk_signals``): a reader who ignores the policy and calls the least risky-looking record "approve"
would otherwise be right too often.  Wording, parser and ``check`` are unchanged.
Truth twice: ``truth(spec)`` runs the rule engine on the structured policy; ``check(item)`` parses the rendered policy (rule
frames, 16 phrasings of numeric limits, 4 of ranges, lists of values, flags, exceptions, precedence, default) and the case lines
and runs a second engine on what it read.
    python3 generators/policy_case.py
"""
import collections
import itertools
import json
import math
import os
import random
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repository root (this file is generators/<family>.py)
HERE = os.path.join(REPO, "generated")                               # the items are written to HERE/tasks/<family>/
AUDITS = os.path.join(REPO, "audits")                                # validate.py and audit.py, run on HERE/tasks/<family>/
SEED = 20261007
TASK = "policy_case"
N_ITEMS = 600
OUTCOMES = ["approve", "deny", "escalate"]
NEEDS = ["plain", "exception", "precedence"]
LEVELS = [4, 8, 12]
INSTRUCTIONS = "What does the policy require for this case?"
OPTION_TEXT = {"approve": "The policy requires approving the request.", "deny": "The policy requires denying the request.",
               "escalate": "The policy requires escalating the request to a human reviewer."}
PP = {"approve": "approved", "deny": "denied", "escalate": "escalated to a human reviewer"}
VP = {"approve": "Approve the request", "deny": "Deny the request", "escalate": "Escalate the request to a human reviewer"}


def rng_for(*parts):
    return random.Random(":".join(str(p) for p in (SEED, TASK) + parts))


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


# ------------------------------------------------------------------------------------------------- the domains
def num(label, unit, lo, hi, ths, risk):
    """risk = the end of the scale that signals risk: 'high' (a large value) or 'low' (a small value)"""
    return {"kind": "num", "label": label, "unit": unit, "lo": lo, "hi": hi, "ths": ths, "risk": risk}


def cat(label, values=None):
    return {"kind": "cat", "label": label, "values": values}


def flag(label, risk, safe):
    """risk = the value (True = yes, False = no) that signals risk, or None when no value does; safe = the value that signals low risk"""
    return {"kind": "flag", "label": label, "risk": risk, "safe": safe}


AMOUNT_TH = [50, 100, 150, 200, 250, 300, 400, 500, 750, 1000, 1500]
AGE_TH = [14, 30, 60, 90, 120, 180, 270, 365, 540, 730]
# Direction of risk of every attribute (v4): a rule that denies or escalates reads a condition that signals risk (a large amount, a new
# account, a missing consent, a fraud alert ...), a rule that approves reads a condition that signals low risk; an exception to an
# approving rule is a risk signal, an exception to a denying / escalating rule is a mitigating condition.
DOMAINS = {
    "refund": {"titles": ["Refund policy", "Refund handling rules", "Rules for refund requests", "Refund approval policy"],
               "attrs": {"amount_eur": num("refund amount", "EUR", 5, 2500, AMOUNT_TH, "high"),
                         "account_age_days": num("account age", "days", 1, 1500, AGE_TH, "low"),
                         "days_since_purchase": num("time since purchase", "days", 0, 120, [7, 14, 21, 30, 45, 60, 90], "high"),
                         "previous_refunds": num("number of earlier refunds", "", 0, 8, [1, 2, 3, 4], "high"),
                         "region": cat("region"), "plan_tier": cat("plan tier", ["T1", "T2", "T3", "T4"]),
                         "item_returned": flag("item returned", False, True),
                         "proof_of_purchase": flag("proof of purchase", False, True),
                         "fraud_alert": flag("fraud alert", True, False),
                         "bank_dispute": flag("bank dispute", True, False)}},
    "export": {"titles": ["Data export policy", "Rules for data export requests", "Export request handling", "Data export approval rules"],
               "attrs": {"records": num("export size", "records", 1, 200000, [100, 500, 1000, 5000, 10000, 25000, 50000, 100000], "high"),
                         "account_age_days": num("account age", "days", 1, 1500, AGE_TH, "low"),
                         "exports_last_30_days": num("number of exports in the last 30 days", "", 0, 10, [1, 2, 3, 5], "high"),
                         "data_region": cat("data region"), "plan_tier": cat("plan tier", ["T1", "T2", "T3", "T4"]),
                         "contains_personal_data": flag("personal data", True, False),
                         "consent_on_file": flag("consent on file", False, True),
                         "legal_hold": flag("legal hold", True, False),
                         "requester_verified": flag("verified requester", False, True)}},
    "access": {"titles": ["Internal access policy", "Rules for system access requests", "System access handling", "Access approval rules"],
               "attrs": {"clearance_level": num("clearance level", "", 1, 5, [2, 3, 4], "low"),
                         "tenure_days": num("tenure", "days", 5, 2500, [30, 90, 180, 365, 730, 1095], "low"),
                         "days_requested": num("requested access period", "days", 1, 120, [3, 7, 14, 30, 60, 90], "high"),
                         "days_since_training": num("time since the last security training", "days", 0, 700, [30, 90, 180, 270, 365], "high"),
                         "team": cat("team"), "system_class": cat("system class", ["A", "B", "C", "D"]),
                         "manager_approval": flag("manager approval", False, True),
                         "open_incident": flag("open incident", True, False),
                         "on_call_duty": flag("on-call duty", None, True),
                         "contractor": flag("contractor status", True, False)}},
    "expense": {"titles": ["Expense claim policy", "Rules for expense claims", "Expense approval rules", "Expense claim handling"],
                "attrs": {"amount_eur": num("claim amount", "EUR", 5, 3000, [25, 50, 100, 150, 250, 500, 1000, 2000], "high"),
                          "days_since_expense": num("time since the expense", "days", 0, 180, [14, 30, 45, 60, 90], "high"),
                          "claims_this_quarter": num("number of claims this quarter", "", 0, 12, [2, 3, 5, 8], "high"),
                          "cost_centre": cat("cost centre", ["CC-117", "CC-204", "CC-310", "CC-455", "CC-512"]),
                          "grade": cat("grade", ["G1", "G2", "G3", "G4", "G5"]),
                          "receipt_attached": flag("receipt attached", False, True),
                          "pre_approved": flag("pre-approval", False, True),
                          "duplicate_suspected": flag("duplicate suspicion", True, False),
                          "company_card": flag("company card use", None, True)}},
}
DOMAIN_NAMES = list(DOMAINS)
# Fields of the case record with a natural order: child <= parent // ratio (a purchase cannot be older than the account, a training
# not older than the employment, no more earlier refunds than one per full week of account age, no more exports in 30 days than days)
DEPS = {"refund": [("days_since_purchase", "account_age_days", 1), ("previous_refunds", "account_age_days", 7)],
        "export": [("exports_last_30_days", "account_age_days", 1)],
        "access": [("days_since_training", "tenure_days", 1)],
        "expense": []}
LEVEL_OF = {4: 1, 8: 2, 12: 3}                                       # meta.level for the dial `rules`
LABEL_KEY = {}                                                      # label -> attribute key (same key in every domain that uses the label)
for _d in DOMAINS.values():
    for _k, _a in _d["attrs"].items():
        assert LABEL_KEY.setdefault(_a["label"], _k) == _k
CHANNELS = ["web", "email", "phone", "portal", "chat"]

# ------------------------------------------------------------------------------------------------- phrases (rendering)
NUM_PH = {">": ["the {L} is more than {V}", "the {L} is above {V}", "the {L} exceeds {V}", "the {L} is greater than {V}"],
          ">=": ["the {L} is at least {V}", "the {L} is {V} or more", "the {L} is not below {V}", "the {L} is {V} or higher"],
          "<": ["the {L} is less than {V}", "the {L} is below {V}", "the {L} is under {V}", "the {L} is lower than {V}"],
          "<=": ["the {L} is at most {V}", "the {L} is {V} or less", "the {L} does not exceed {V}", "the {L} is not more than {V}"]}
RNG_PH = ["the {L} is between {A} and {B}{U} inclusive", "the {L} is from {A} to {B}{U} inclusive",
          "the {L} lies in the range {A} to {B}{U} inclusive", "the {L} is within {A} to {B}{U} with both limits included"]
EQ_PH = ["the {L} is {X}", "the {L} equals {X}", "the {L} on record is {X}", "the {L} recorded for the case is {X}"]
NE_PH = ["the {L} is not {X}", "the {L} is anything other than {X}", "the {L} differs from {X}", "the {L} on record is not {X}"]
IN_PH = ["the {L} is one of {X}", "the {L} is any of {X}", "the {L} is among {X}", "the {L} is either {X}"]
NIN_PH = ["the {L} is none of {X}", "the {L} is not one of {X}", "the {L} is not among {X}", "the {L} is not any of {X}"]
FLAG_PH = ["the {L} flag is {Y}", "the case has the {L} flag set to {Y}", "the record shows {Y} for the {L} flag", "the {L} flag is set to {Y}"]
RULE_FRAMES = ["If {C}, the request is {PP}.", "{VP} when {C}.", "When {C}: {VP}.", "A request for which {C} is {PP}.",
               "The request must be {PP} if {C}."]
NUMBERING = ["Rule {n}. ", "{n}. ", "({n}) "]
EXC_FRAMES = ["Rule {k} does not apply when {C}.", "Rule {k} is waived if {C}.", "Exception to Rule {k}: it is not applied when {C}.",
              "If {C}, Rule {k} does not apply."]
PREC_LOWER = ["If two applicable rules lead to different outcomes, the lower-numbered rule decides.",
              "When rules conflict, the rule with the lower number wins.",
              "In a conflict between rules, the earlier rule in the list prevails.",
              "Conflicting rules are resolved in favour of the rule with the smaller number."]
PREC_HIGHER = ["If two applicable rules lead to different outcomes, the higher-numbered rule decides.",
               "When rules conflict, the rule with the higher number wins.",
               "In a conflict between rules, the later rule in the list prevails.",
               "Conflicting rules are resolved in favour of the rule with the larger number."]
DEFAULT_FRAMES = ["If no rule applies, the request is {PP}.", "A request that no rule covers is {PP}.",
                  "When none of the rules applies, {vp}.", "By default a request is {PP} unless a rule says otherwise."]
LAYOUTS = [{"rules": "Rules:", "exc": "Exceptions:", "gen": "Conflicts and default:", "bullet": "- ", "order": "rules_first"},
           {"rules": "RULES", "exc": "EXCEPTIONS", "gen": "GENERAL", "bullet": "", "order": "rules_first"},
           {"rules": None, "exc": None, "gen": None, "bullet": "", "order": "rules_first"},
           {"rules": "Rules", "exc": "Exceptions", "gen": "General provisions", "bullet": "- ", "order": "general_first"}]
HEADINGS = {"Rules:", "Exceptions:", "Conflicts and default:", "RULES", "EXCEPTIONS", "GENERAL", "Rules", "Exceptions", "General provisions"}


def val_text(a, v):
    u = a["unit"]
    return f"{v} {u}" if u else f"{v}"


def list_text(vs):
    return vs[0] if len(vs) == 1 else ", ".join(vs[:-1]) + " or " + vs[-1]


def atom_text(rng, atoms_def, atom):
    a = atoms_def[atom["a"]]
    L = a["label"]
    t = atom["t"]
    if t == "num":
        return rng.choice(NUM_PH[atom["op"]]).format(L=L, V=val_text(a, atom["v"]))
    if t == "rng":
        U = f" {a['unit']}" if a["unit"] else ""
        return rng.choice(RNG_PH).format(L=L, A=atom["lo"], B=atom["hi"], U=U)
    if t == "eq":
        return rng.choice(EQ_PH).format(L=L, X=atom["v"])
    if t == "ne":
        return rng.choice(NE_PH).format(L=L, X=atom["v"])
    if t == "in":
        return rng.choice(IN_PH).format(L=L, X=list_text(atom["vs"]))
    if t == "nin":
        return rng.choice(NIN_PH).format(L=L, X=list_text(atom["vs"]))
    return rng.choice(FLAG_PH).format(L=L, Y="yes" if atom["v"] else "no")


# ------------------------------------------------------------------------------------------------ the rule engine
def cmp_op(v, op, t):
    return {">": v > t, ">=": v >= t, "<": v < t, "<=": v <= t}[op]


def atom_true(atom, case):
    v = case[atom["a"]]
    t = atom["t"]
    if t == "num":
        return cmp_op(v, atom["op"], atom["v"])
    if t == "rng":
        return atom["lo"] <= v <= atom["hi"]
    if t == "eq":
        return v == atom["v"]
    if t == "ne":
        return v != atom["v"]
    if t == "in":
        return v in atom["vs"]
    if t == "nin":
        return v not in atom["vs"]
    return (v == "yes") == atom["v"]


def decide(applicable, default, prec):
    if not applicable:
        return default
    if len({r["out"] for r in applicable}) == 1:
        return applicable[0]["out"]
    return (min if prec == "lower" else max)(applicable, key=lambda r: r["n"])["out"]


def engine(policy, case, exceptions=True, prec=None):
    """-> (outcome, rules whose conditions hold, rules that apply after the exceptions)"""
    fires = [r for r in policy["rules"] if all(atom_true(a, case) for a in r["cond"])]
    cancelled = set()
    if exceptions:
        cancelled = {e["rule"] for e in policy["exceptions"] if all(atom_true(a, case) for a in e["cond"])}
    applicable = [r for r in fires if r["n"] not in cancelled]
    return decide(applicable, policy["default"], prec or policy["prec"]), fires, applicable


def truth(spec):
    return engine(spec["policy"], spec["case"])[0]


def classify(policy, case):
    """-> (outcome, needs or None) proved by ablation"""
    out, fires, applicable = engine(policy, case)
    naive = engine(policy, case, exceptions=False)[0]
    exc_fires = len(fires) != len(applicable)
    conflict = len({r["out"] for r in applicable}) > 1
    rev = "higher" if policy["prec"] == "lower" else "lower"
    prec_matters = conflict and engine(policy, case, prec=rev)[0] != out
    if out != naive and not conflict:
        needs = "exception"
    elif prec_matters and not exc_fires:
        needs = "precedence"
    elif not exc_fires and not conflict:
        needs = "plain"
    else:
        needs = None
    return out, needs


def thresholds(policy):
    """numeric attribute -> thresholds used by the atoms of the rules and exceptions"""
    out = collections.defaultdict(list)
    atoms = [a for r in policy["rules"] for a in r["cond"]] + [a for e in policy["exceptions"] for a in e["cond"]]
    for a in atoms:
        if a["t"] == "num":
            out[a["a"]].append(a["v"])
        elif a["t"] == "rng":
            out[a["a"]] += [a["lo"], a["hi"]]
    return out


def distance(v, t):
    return abs(v - t) / max(abs(t), 1)


def is_near(v, t):
    """within 5 % of the threshold, or on it"""
    return v == t or (t >= 20 and abs(v - t) <= 0.05 * t)


def flip_value(atom, v):
    """the nearest value on the other side of the atom's threshold"""
    t = atom["t"]
    if t == "rng":
        if atom["lo"] <= v <= atom["hi"]:
            return atom["lo"] - 1 if v - atom["lo"] <= atom["hi"] - v else atom["hi"] + 1
        return atom["lo"] if v < atom["lo"] else atom["hi"]
    T, op = atom["v"], atom["op"]
    now = cmp_op(v, op, T)
    return {(">", True): T, (">", False): T + 1, (">=", True): T - 1, (">=", False): T,
            ("<", True): T, ("<", False): T - 1, ("<=", True): T + 1, ("<=", False): T}[(op, now)]


def near_report(policy, case):
    """-> (decisive near atoms [(attribute, threshold, distance)], smallest distance of any numeric attribute to any threshold)"""
    out = engine(policy, case)[0]
    decisive, dmin = [], 9.9
    atoms = [a for r in policy["rules"] for a in r["cond"]] + [a for e in policy["exceptions"] for a in e["cond"]]
    for a in atoms:
        if a["t"] not in ("num", "rng"):
            continue
        v = case[a["a"]]
        ts = [a["v"]] if a["t"] == "num" else [a["lo"], a["hi"]]
        for T in ts:
            dmin = min(dmin, distance(v, T))
            if is_near(v, T):
                other = dict(case)
                other[a["a"]] = flip_value(a, v)
                if engine(policy, other)[0] != out:
                    decisive.append((a["a"], T, round(100 * distance(v, T), 2)))
    return decisive, dmin


# ----------------------------------------------------------------------------------------------- building a policy
def risk_end(a, want):
    """the end of the scale ('high' / 'low') that a condition of the direction `want` ('risk' or 'safe') selects"""
    return a["risk"] if want == "risk" else ("low" if a["risk"] == "high" else "high")


def make_atom(rng, adef, key, want, pool, allow_range=True):
    """one condition on attribute `key`; want = 'risk' (the condition signals risk) or 'safe' (it signals low risk)"""
    a = adef[key]
    if a["kind"] == "num":
        ths = a["ths"]
        if want == "risk" and allow_range and len(ths) >= 3 and rng.random() < 0.15:           # a band on the risky side of the scale
            part = ths[len(ths) // 3:] if a["risk"] == "high" else ths[:len(ths) - len(ths) // 3]
            lo, hi = sorted(rng.sample(part, 2))
            return {"t": "rng", "a": key, "lo": lo, "hi": hi}
        high = risk_end(a, want) == "high"                                                  # a limit sits where it means something:
        part = ths[len(ths) // 3:] if high else ths[:len(ths) - len(ths) // 3]               # not "more than 3 days", not "at most 1500 EUR"
        op = rng.choice([">", ">="] if high else ["<", "<="])
        return {"t": "num", "a": key, "op": op, "v": rng.choice(part)}
    if a["kind"] == "cat":
        vals = pool[key]
        r = rng.random()
        if r < 0.35:
            return {"t": "eq", "a": key, "v": rng.choice(vals)}
        if r < 0.55:
            return {"t": "ne", "a": key, "v": rng.choice(vals)}
        if r < 0.85:
            return {"t": "in", "a": key, "vs": rng.sample(vals, rng.choice([2, 3]))}
        return {"t": "nin", "a": key, "vs": rng.sample(vals, rng.choice([2, 3]))}
    return {"t": "flag", "a": key, "v": a["risk"] if want == "risk" else a["safe"]}


def make_cond(rng, adef, keys, want, pool, k, allow_range=True, acted=None):
    """k conditions on distinct attributes of `keys`: at least one on a number or a flag read in the direction `want`, the others of
    that direction too or on a category.  acted = the flags with a risk value that some deny / escalate rule reacts to: a flag that can
    signal risk is only read where the policy reacts to it (None = no restriction, used for the deny / escalate rules themselves)"""
    def driver(x):
        a = adef[x]
        if a["kind"] == "num":
            return True
        if a["kind"] == "flag":
            if (a["risk"] if want == "risk" else a["safe"]) is None:
                return False
            return acted is None or a["risk"] is None or x in acted
        return False
    drv = [x for x in keys if driver(x)]
    if not drv:
        return None
    first = rng.choice(drv)
    rest = [x for x in keys if x != first and (driver(x) or adef[x]["kind"] == "cat")]
    ks = [first] + rng.sample(rest, min(k - 1, len(rest)))
    rng.shuffle(ks)
    return [make_atom(rng, adef, x, want, pool, allow_range) for x in ks]


def acted_flags(adef, rules):
    """the flags that can signal risk and that some deny / escalate rule reads: the policy reacts to them"""
    return {a["a"] for r in rules if r["out"] != "approve" for a in r["cond"] if a["t"] == "flag" and adef[a["a"]]["risk"] is not None}


def cond_attrs(cond):
    return {a["a"] for a in cond}


def redraw_rule(rng, policy, n):
    """a new condition for rule n (same outcome); it keeps away from the attributes of the exception to the rule"""
    adef = DOMAINS[policy["domain"]]["attrs"]
    r = policy["rules"][n - 1]
    taken = set()
    for e in policy["exceptions"]:
        if e["rule"] == n:
            taken |= cond_attrs(e["cond"])
    risky = r["out"] != "approve"
    cond = make_cond(rng, adef, [k for k in policy["use"] if k not in taken], "risk" if risky else "safe", policy["pool"],
                     rng.choice([1, 2, 2, 3]), allow_range=risky, acted=None if risky else acted_flags(adef, policy["rules"]))
    if cond:
        r["cond"] = cond
    return bool(cond)


def redraw_exc(rng, policy, i):
    """a new condition for exception i (same rule), on attributes the rule does not use"""
    adef = DOMAINS[policy["domain"]]["attrs"]
    e = policy["exceptions"][i]
    r = policy["rules"][e["rule"] - 1]
    free = [k for k in policy["use"] if k not in cond_attrs(r["cond"])]
    cond = make_cond(rng, adef, free, "risk" if r["out"] == "approve" else "safe", policy["pool"], rng.choice([1, 1, 2]),
                     allow_range=False, acted=acted_flags(adef, policy["rules"]))
    if cond:
        e["cond"] = cond
    return bool(cond)


def swap_rules(policy, i, j):
    """exchange the places (numbers) of rules i and j; their exceptions follow"""
    R = policy["rules"]
    R[i - 1], R[j - 1] = R[j - 1], R[i - 1]
    R[i - 1]["n"], R[j - 1]["n"] = i, j
    for e in policy["exceptions"]:
        e["rule"] = j if e["rule"] == i else (i if e["rule"] == j else e["rule"])


def draft_policy(rng, dname, L, prec, default):
    adef = DOMAINS[dname]["attrs"]
    while True:                                                      # the attributes this policy talks about
        use = rng.sample(list(adef), rng.randint(6, 8))
        kinds = collections.Counter(adef[k]["kind"] for k in use)
        if kinds["num"] >= 2 and kinds["cat"] >= 1 and kinds["flag"] >= 2:
            break
    pool = {}
    for k, a in adef.items():
        if a["kind"] == "cat":
            pool[k] = list(a["values"]) if a["values"] else [coin(rng) for _ in range(5)]
    outs = [OUTCOMES[i % 3] for i in range(L)]                       # every outcome occurs among the rules
    if L == 4:
        outs[3] = rng.choice(OUTCOMES)
    rng.shuffle(outs)
    rules = [{"n": n, "out": o, "cond": None} for n, o in enumerate(outs, 1)]
    n_exc = {4: rng.choice([1, 2]), 8: rng.choice([2, 3]), 12: rng.choice([3, 4])}[L]
    policy = {"domain": dname, "rules": rules, "exceptions": [], "prec": prec, "default": default, "pool": pool, "use": use}
    for r in rules:                                                  # the deny / escalate rules first: they decide which flags the policy reacts to
        if r["out"] != "approve":
            r["cond"] = make_cond(rng, adef, use, "risk", pool, rng.choice([1, 2, 2, 3]))
    acted = acted_flags(adef, rules)
    for r in rules:
        if r["out"] == "approve":
            r["cond"] = make_cond(rng, adef, use, "safe", pool, rng.choice([1, 2, 2, 3]), allow_range=False, acted=acted)
    if any(r["cond"] is None for r in rules):
        return None
    for t in sorted(rng.sample(range(1, L + 1), n_exc)):             # one exception per rule, on attributes the rule does not use
        policy["exceptions"].append({"rule": t, "cond": None})
    for i in range(len(policy["exceptions"])):
        if not redraw_exc(rng, policy, i) or policy["exceptions"][i]["cond"] is None:
            return None
    rng.shuffle(policy["exceptions"])
    return policy


# ----------------------------------------------------------------------- what is wrong with a policy: exact analysis of its attribute space
def atom_sig(atom):
    """(attribute, direction of the condition): what a reader sees as 'the same kind of condition'"""
    t = atom["t"]
    if t == "num":
        return (atom["a"], "hi" if atom["op"] in (">", ">=") else "lo")
    if t == "rng":
        return (atom["a"], "band")
    if t in ("eq", "in"):
        return (atom["a"], "in")
    if t in ("ne", "nin"):
        return (atom["a"], "out")
    return (atom["a"], "yes" if atom["v"] else "no")


def duplicate_pairs(policy):
    """pairs (i, j), i < j, of rules with the same outcome whose conditions have the same attributes and directions in at least half of
    their union (a rule that repeats another, or is narrower than it, with other numbers)"""
    sigs = [{atom_sig(a) for a in r["cond"]} for r in policy["rules"]]
    out = []
    for i, j in itertools.combinations(range(len(sigs)), 2):
        if policy["rules"][i]["out"] == policy["rules"][j]["out"] and 2 * len(sigs[i] & sigs[j]) >= len(sigs[i] | sigs[j]):
            out.append((i + 1, j + 1))
    return out


class Grid:
    """The attribute space of a policy cut into cells that no condition of the policy can tell apart (numbers: the intervals between the
    cut points of the conditions, categories: the values with the same answers, flags: yes / no).  Every case lies in exactly one cell and
    has the outcome of that cell, so questions about 'some case' are answered exactly by looking at the cells.  A set of cells is a Python
    integer used as a bit set.  Cells that break the order of the case record (DEPS) are left out."""

    def __init__(self, policy):
        self.policy = policy
        adef = DOMAINS[policy["domain"]]["attrs"]
        by = collections.defaultdict(list)
        for r in policy["rules"]:
            for a in r["cond"]:
                by[a["a"]].append(a)
        for e in policy["exceptions"]:
            for a in e["cond"]:
                by[a["a"]].append(a)
        self.keys = sorted(by)
        self.cells = {}
        for k in self.keys:
            d, ats = adef[k], by[k]
            if d["kind"] == "num":
                cuts = set()
                for a in ats:
                    if a["t"] == "num":
                        cuts.add(a["v"] + 1 if a["op"] in (">", "<=") else a["v"])
                    else:
                        cuts.update([a["lo"], a["hi"] + 1])
                pts = sorted({d["lo"]} | {c for c in cuts if d["lo"] < c <= d["hi"]})
                self.cells[k] = [(p, p, q - 1) for p, q in zip(pts, pts[1:] + [d["hi"] + 1])]
            elif d["kind"] == "flag":
                self.cells[k] = [("no", None, None), ("yes", None, None)]
            else:
                seen, reps = set(), []
                for v in policy["pool"][k]:
                    sig = tuple(atom_true(a, {k: v}) for a in ats)
                    if sig not in seen:
                        seen.add(sig)
                        reps.append((v, None, None))
                self.cells[k] = reps
        self.sizes = [len(self.cells[k]) for k in self.keys]
        self.total = 1
        for s in self.sizes:
            self.total *= s
        self.ALL = (1 << self.total) - 1
        self.memo = {}
        self.feasible = self.ALL
        for child, parent, ratio in DEPS[policy["domain"]]:
            if child in self.cells and parent in self.cells:
                ci, pi = self.keys.index(child), self.keys.index(parent)
                m = 0
                for ic, (_, clo, _) in enumerate(self.cells[child]):
                    for ip, (_, _, phi) in enumerate(self.cells[parent]):
                        if clo <= phi // ratio:
                            m |= self.digit(ci, (ic,)) & self.digit(pi, (ip,))
                self.feasible &= m

    def digit(self, j, allowed):
        """the cells whose j-th coordinate is one of `allowed`"""
        key = (j, allowed)
        if key not in self.memo:
            stride = 1
            for s in self.sizes[j + 1:]:
                stride *= s
            period = self.sizes[j] * stride
            block = (1 << stride) - 1
            res = 0
            for v in allowed:
                res |= block << (v * stride)
            filled = period                                          # repeat the pattern of one period over the whole space
            while filled < self.total:
                take = min(filled, self.total - filled)
                res |= (res & ((1 << take) - 1)) << filled
                filled += take
            self.memo[key] = res
        return self.memo[key]

    def atom_mask(self, atom):
        j = self.keys.index(atom["a"])
        return self.digit(j, tuple(i for i, (rep, _, _) in enumerate(self.cells[atom["a"]]) if atom_true(atom, {atom["a"]: rep})))

    def cond_mask(self, atoms):
        m = self.ALL
        for a in atoms:
            m &= self.atom_mask(a)
        return m


def outcome_cells(g, apps, order, outs, default):
    res = {o: 0 for o in OUTCOMES}
    taken = 0
    for n in order:
        res[outs[n]] |= apps[n] & ~taken & g.ALL
        taken |= apps[n]
    res[default] |= g.feasible & ~taken & g.ALL
    return res


def liveness(policy):
    """-> (rules that never decide, exceptions that never change an outcome).  A rule decides in a case when it is the first applicable
    rule under the precedence statement and the outcome without it would be another one (the next applicable rule's outcome, or the
    default)."""
    g = Grid(policy)
    rules = policy["rules"]
    outs = {r["n"]: r["out"] for r in rules}
    fires = {r["n"]: g.cond_mask(r["cond"]) & g.feasible for r in rules}
    cancel = {}
    for e in policy["exceptions"]:
        cancel[e["rule"]] = cancel.get(e["rule"], 0) | g.cond_mask(e["cond"])
    apps = {n: fires[n] & ~cancel.get(n, 0) & g.ALL for n in fires}
    order = sorted(outs) if policy["prec"] == "lower" else sorted(outs, reverse=True)
    earlier, seen = {}, 0
    for n in order:
        earlier[n] = seen
        seen |= apps[n]
    after = {o: (g.feasible if o == policy["default"] else 0) for o in OUTCOMES}      # outcome of the rules after the current one
    dead = []
    for n in reversed(order):
        if apps[n] & ~earlier[n] & ~after[outs[n]] & g.ALL == 0:
            dead.append(n)
        after = {o: ((apps[n] if outs[n] == o else 0) | (g.ALL & ~apps[n] & after[o])) for o in OUTCOMES}
    base = outcome_cells(g, apps, order, outs, policy["default"])
    dead_exc = []
    for i, e in enumerate(policy["exceptions"]):
        apps2 = dict(apps)
        apps2[e["rule"]] = fires[e["rule"]]
        alt = outcome_cells(g, apps2, order, outs, policy["default"])
        if all(alt[o] == base[o] for o in OUTCOMES):
            dead_exc.append(i)
    return sorted(dead), dead_exc


def problems(policy):
    """[(kind, index, why)]: rules ('rule', n) and exceptions ('exc', i) that make the policy read badly"""
    adef = DOMAINS[policy["domain"]]["attrs"]
    acted = acted_flags(adef, policy["rules"])
    out = []
    unacted = lambda cond: any(a["t"] == "flag" and adef[a["a"]]["risk"] is not None and a["a"] not in acted for a in cond)
    for r in policy["rules"]:
        if unacted(r["cond"]):
            out.append(("rule", r["n"], "unacted"))
    for i, e in enumerate(policy["exceptions"]):
        if unacted(e["cond"]):
            out.append(("exc", i, "unacted"))
    for i, j in duplicate_pairs(policy):
        out.append(("rule", j, "duplicate"))
    dead, dead_exc = liveness(policy)
    out += [("rule", n, "dead") for n in dead] + [("exc", i, "dead") for i in dead_exc]
    return out


def make_policy(rng, dname, L, prec, default, repairs=60):
    """a policy in which every rule reads a condition in the direction of its outcome, no rule is dead or repeats another, and every
    exception can matter; None when the repairs do not lead there"""
    policy = draft_policy(rng, dname, L, prec, default)
    if policy is None:
        return None
    for _ in range(repairs):
        probs = problems(policy)
        if not probs:
            policy["acted"] = sorted(acted_flags(DOMAINS[dname]["attrs"], policy["rules"]))
            policy["read"] = sorted({a["a"] for r in policy["rules"] for a in r["cond"]} | {a["a"] for e in policy["exceptions"] for a in e["cond"]})
            return policy
        kind, i, why = rng.choice(probs)
        if kind == "exc":
            redraw_exc(rng, policy, i)
        elif why == "dead" and rng.random() < 0.3:                   # a rule that cannot decide may sit in the wrong place
            swap_rules(policy, i, rng.choice([n for n in range(1, L + 1) if n != i]))
        else:
            redraw_rule(rng, policy, i)
    return None


def atom_dir(adef, atom):
    """'risk' / 'safe' / 'band' / None: the direction of one condition as a reader sees it"""
    a = adef[atom["a"]]
    if atom["t"] == "num":
        return "risk" if (risk_end(a, "risk") == "high") == (atom["op"] in (">", ">=")) else "safe"
    if atom["t"] == "rng":
        return "band"
    if atom["t"] == "flag":
        if a["risk"] is not None and atom["v"] == a["risk"]:
            return "risk"
        if atom["v"] == a["safe"]:
            return "safe"
    return None


def coherence(policy):
    """counts of what makes a policy read badly (all must be 0): rules against the direction of risk, exceptions against it, dead rules,
    dead exceptions, near-duplicate rules, flags that can signal risk and are read where no deny / escalate rule reacts to them"""
    adef = DOMAINS[policy["domain"]]["attrs"]
    dirs = lambda cond: [atom_dir(adef, a) for a in cond]
    c = collections.Counter()
    for r in policy["rules"]:
        d = dirs(r["cond"])
        if r["out"] == "approve":
            c["approve_rule_with_risk_or_band"] += ("risk" in d) or ("band" in d)
            c["approve_rule_without_safe"] += "safe" not in d
        else:
            c["risk_rule_with_safe"] += "safe" in d
            c["risk_rule_without_risk"] += not ("risk" in d or "band" in d)
    for e in policy["exceptions"]:
        d = dirs(e["cond"])
        if policy["rules"][e["rule"] - 1]["out"] == "approve":
            c["exception_to_approve_rule_wrong"] += ("risk" not in d) or ("safe" in d) or ("band" in d)
        else:
            c["exception_to_risk_rule_wrong"] += ("safe" not in d) or ("risk" in d) or ("band" in d)
    dead, dead_exc = liveness(policy)
    c["dead_rules"], c["dead_exceptions"] = len(dead), len(dead_exc)
    c["duplicate_pairs"] = len(duplicate_pairs(policy))
    c["unreacted_flags"] = sum(1 for p in problems(policy) if p[2] == "unacted")
    return c


def blind_risk_reader(items):
    """a reader that ignores the policy and calls the least risky-looking record of a triple 'approve': the share of triples it gets right
    (ties count 1 / number of tied records), and the share of triples whose three records carry the same number of risk signals"""
    groups = collections.defaultdict(list)
    for it in items:
        groups[it["group"]].append(it)
    hit, same, n = 0.0, 0, 0
    for g in groups.values():
        if len(g) != 3:
            continue
        sc = [(sum(it["meta"]["risk_signals"]), it["gold"]) for it in g]
        low = min(x for x, _ in sc)
        tied = [o for x, o in sc if x == low]
        hit += ("approve" in tied) / len(tied)
        same += len({x for x, _ in sc}) == 1
        n += 1
    return hit / n, same / n, n


# ----------------------------------------------------------------------------------------------- building a case
def sample_value(rng, a, ths, lo=None, hi=None):
    lo = a["lo"] if lo is None else lo
    hi = a["hi"] if hi is None else hi
    if lo > hi:
        return None
    for _ in range(200):
        v = int(round(math.exp(rng.uniform(math.log(max(lo, 1)), math.log(max(hi, 1)))))) if hi / max(lo, 1) > 20 else rng.randint(lo, hi)
        v = min(max(v, lo), hi)
        if all(distance(v, T) > 0.10 for T in ths):
            return v
    return None


def near_value(rng, T):
    c = [T, T, T - 1, T + 1] if T >= 20 else [T]
    if T >= 100:
        c += [int(round(T * (1 + rng.choice([-1, 1]) * rng.uniform(0.01, 0.05))))]
    return rng.choice(c)


def sample_case(rng, policy, near=None, p_flag=0.5, p_num=None):
    """a case record of the policy.  Fields with a natural order are drawn together (DEPS); a flag that can signal risk has its risk value
    only when some deny / escalate rule reacts to it, and a number that no rule reads stays on the safe side of its scale.  p_flag = the
    chance of a risk value for such a flag, p_num = the chance that a number that a rule reads lies on the risky half of its scale (None =
    anywhere); both vary between draws so that the candidates of the three outcomes cover every profile of risk signals"""
    dom = policy["domain"]
    adef = DOMAINS[dom]["attrs"]
    thr = thresholds(policy)
    read, acted = set(policy["read"]), set(policy["acted"])
    child_of = {c: (p, r) for c, p, r in DEPS[dom]}
    kids_of = collections.defaultdict(list)
    for c, p, r in DEPS[dom]:
        kids_of[p].append((c, r))
    first = near[0] if near else None
    order = ([first] if first else []) + [k for k in adef if k != first and k not in child_of] + [k for k in adef if k != first and k in child_of]
    case = {}
    for k in order:
        a = adef[k]
        if a["kind"] == "num":
            lo, hi = a["lo"], a["hi"]
            if k in child_of and child_of[k][0] in case:
                hi = min(hi, case[child_of[k][0]] // child_of[k][1])
            for c, r in kids_of.get(k, []):
                if c in case:
                    lo = max(lo, case[c] * r)
            if k == first:
                v = near_value(rng, near[1])
                if not lo <= v <= hi:
                    return None
            else:
                mid = a["ths"][len(a["ths"]) // 2]
                if k not in read:                                    # nobody reads it: no risk signal that the policy ignores
                    lo, hi = (lo, min(hi, mid)) if a["risk"] == "high" else (max(lo, mid), hi)
                elif p_num is not None:
                    if (a["risk"] == "high") == (rng.random() < p_num):
                        lo = max(lo, mid + 1)
                    else:
                        hi = min(hi, mid)
                v = sample_value(rng, a, thr.get(k, []), lo, hi)
                if v is None:
                    return None
            case[k] = v
        elif a["kind"] == "cat":
            case[k] = rng.choice(policy["pool"][k])
        elif a["risk"] is not None and k not in acted:
            case[k] = "yes" if a["safe"] else "no"
        elif a["risk"] is not None:
            case[k] = "yes" if (a["risk"] if rng.random() < p_flag else not a["risk"]) else "no"
        else:
            case[k] = "yes" if rng.random() < 0.5 else "no"
    return {k: case[k] for k in adef}


# ---------------------------------------------------------------------------------------------------- rendering
def render_policy(rng, policy, look):
    adef = DOMAINS[policy["domain"]]["attrs"]
    lay = LAYOUTS[look["layout"]]
    cond_text = lambda atoms: " and ".join(atom_text(rng, adef, a) for a in atoms)
    rule_lines = []
    for r in policy["rules"]:
        num_txt = NUMBERING[look["numbering"]].format(n=r["n"])
        frame = RULE_FRAMES[look["rule_frame"]]
        rule_lines.append(num_txt + frame.format(C=cond_text(r["cond"]), PP=PP[r["out"]], VP=VP[r["out"]]))
    exc_lines = [lay["bullet"] + EXC_FRAMES[look["exc_frame"]].format(k=e["rule"], C=cond_text(e["cond"])) for e in policy["exceptions"]]
    prec_line = (PREC_LOWER if policy["prec"] == "lower" else PREC_HIGHER)[look["prec_frame"]]
    vp = VP[policy["default"]][0].lower() + VP[policy["default"]][1:]
    dflt_line = DEFAULT_FRAMES[look["default_frame"]].format(PP=PP[policy["default"]], vp=vp)
    gen = [lay["bullet"] + prec_line, lay["bullet"] + dflt_line]
    lines = [look["title"], ""]
    blocks = [(lay["rules"], rule_lines), (lay["exc"], exc_lines), (lay["gen"], gen)]
    if lay["order"] == "general_first":
        blocks = [blocks[2], blocks[0], blocks[1]]
    for head, body in blocks:
        if head:
            lines.append(head)
        lines += body
        lines.append("")
    return "\n".join(lines).rstrip("\n")


DAYS = [3, 7, 11, 14, 19, 23, 27]


def render_case(rng, domain, case, pid, k):
    """the attributes of the domain plus three lines no rule uses; channel, month and day rotate with the policy and the outcome
    (k = 0, 1, 2 for approve, deny, escalate), so that these words are spread evenly over the three outcome classes"""
    adef = DOMAINS[domain]["attrs"]
    lines = [f"{key}: {case[key]}" for key in adef]
    extra = [f"request_id: RQ-{rng.randint(10000, 99999)}", f"submitted_on: 2026-{1 + (pid + 4 * k) % 9:02d}-{DAYS[(pid + 3 * k) % 7]:02d}",
             f"channel: {CHANNELS[(pid + k) % 5]}"]
    for e in extra:
        lines.insert(rng.randint(0, len(lines)), e)
    return "\n".join(lines)


# ---------------------------------------------------------- check: the answer from the rendered text alone
LAB = "|".join(re.escape(x) for x in sorted(LABEL_KEY, key=lambda x: (-len(x), x)))
UNIT = r"(?: (?:EUR|days|records))?"
V = rf"(?P<v>\d+){UNIT}"
END_ = r"(?= and |$)"
VAL = r"[A-Za-z0-9][A-Za-z0-9\-]*"
LST = rf"(?P<x>{VAL}(?:, {VAL})*(?: or {VAL})?)"
NUM_RX = [(">", rf"the (?P<l>{LAB}) is more than {V}"), (">", rf"the (?P<l>{LAB}) is above {V}"), (">", rf"the (?P<l>{LAB}) exceeds {V}"),
          (">", rf"the (?P<l>{LAB}) is greater than {V}"),
          (">=", rf"the (?P<l>{LAB}) is at least {V}"), (">=", rf"the (?P<l>{LAB}) is {V} or more"), (">=", rf"the (?P<l>{LAB}) is not below {V}"),
          (">=", rf"the (?P<l>{LAB}) is {V} or higher"),
          ("<", rf"the (?P<l>{LAB}) is less than {V}"), ("<", rf"the (?P<l>{LAB}) is below {V}"), ("<", rf"the (?P<l>{LAB}) is under {V}"),
          ("<", rf"the (?P<l>{LAB}) is lower than {V}"),
          ("<=", rf"the (?P<l>{LAB}) is at most {V}"), ("<=", rf"the (?P<l>{LAB}) is {V} or less"), ("<=", rf"the (?P<l>{LAB}) does not exceed {V}"),
          ("<=", rf"the (?P<l>{LAB}) is not more than {V}")]
RNG_RX = [rf"the (?P<l>{LAB}) is between (?P<a>\d+) and (?P<b>\d+){UNIT} inclusive", rf"the (?P<l>{LAB}) is from (?P<a>\d+) to (?P<b>\d+){UNIT} inclusive",
          rf"the (?P<l>{LAB}) lies in the range (?P<a>\d+) to (?P<b>\d+){UNIT} inclusive",
          rf"the (?P<l>{LAB}) is within (?P<a>\d+) to (?P<b>\d+){UNIT} with both limits included"]
CAT_RX = [("eq", rf"the (?P<l>{LAB}) is (?P<x>{VAL})"), ("eq", rf"the (?P<l>{LAB}) equals (?P<x>{VAL})"),
          ("eq", rf"the (?P<l>{LAB}) on record is (?P<x>{VAL})"), ("eq", rf"the (?P<l>{LAB}) recorded for the case is (?P<x>{VAL})"),
          ("ne", rf"the (?P<l>{LAB}) is not (?P<x>{VAL})"), ("ne", rf"the (?P<l>{LAB}) is anything other than (?P<x>{VAL})"),
          ("ne", rf"the (?P<l>{LAB}) differs from (?P<x>{VAL})"), ("ne", rf"the (?P<l>{LAB}) on record is not (?P<x>{VAL})"),
          ("in", rf"the (?P<l>{LAB}) is one of {LST}"), ("in", rf"the (?P<l>{LAB}) is any of {LST}"), ("in", rf"the (?P<l>{LAB}) is among {LST}"),
          ("in", rf"the (?P<l>{LAB}) is either {LST}"),
          ("nin", rf"the (?P<l>{LAB}) is none of {LST}"), ("nin", rf"the (?P<l>{LAB}) is not one of {LST}"),
          ("nin", rf"the (?P<l>{LAB}) is not among {LST}"), ("nin", rf"the (?P<l>{LAB}) is not any of {LST}")]
Y = r"(?P<y>yes|no)"
FLAG_RX = [rf"the (?P<l>{LAB}) flag is {Y}", rf"the case has the (?P<l>{LAB}) flag set to {Y}", rf"the record shows {Y} for the (?P<l>{LAB}) flag",
           rf"the (?P<l>{LAB}) flag is set to {Y}"]
OUT = r"(?P<o>approved|denied|escalated(?: to a human reviewer)?)"
VERB = r"(?P<o>Approve|Deny|Escalate)(?: the request)?(?: to a human reviewer)?"
VERB_LC = r"(?P<o>approve|deny|escalate)(?: the request)?(?: to a human reviewer)?"
ATOM_RX = ([(("num", op), re.compile(p + END_)) for op, p in NUM_RX] + [(("rng", None), re.compile(p + END_)) for p in RNG_RX]
           + [((k, None), re.compile(p + END_)) for k, p in CAT_RX] + [(("flag", None), re.compile(p + END_)) for p in FLAG_RX])
RULE_RX = [rf"If (?P<c>.+), the request is {OUT}\.", rf"{VERB} when (?P<c>.+)\.", rf"When (?P<c>.+): {VERB}\.", rf"A request for which (?P<c>.+) is {OUT}\.",
           rf"The request must be {OUT} if (?P<c>.+)\."]
EXC_RX = [rf"Rule (?P<k>\d+) does not apply when (?P<c>.+)\.", rf"Rule (?P<k>\d+) is waived if (?P<c>.+)\.",
          rf"Exception to Rule (?P<k>\d+): it is not applied when (?P<c>.+)\.", rf"If (?P<c>.+), Rule (?P<k>\d+) does not apply\."]
PREC_RX = [("lower", p) for p in map(re.escape, PREC_LOWER)] + [("higher", p) for p in map(re.escape, PREC_HIGHER)]
DEFAULT_RX = [rf"If no rule applies, the request is {OUT}\.", rf"A request that no rule covers is {OUT}\.", rf"When none of the rules applies, {VERB_LC}\.",
              rf"By default a request is {OUT} unless a rule says otherwise\."]
OUT_KEY = {"approved": "approve", "denied": "deny", "escalated": "escalate", "Approve": "approve", "Deny": "deny", "Escalate": "escalate",
           "approve": "approve", "deny": "deny", "escalate": "escalate"}


def parse_cond(text):
    """the atoms of a condition 'atom and atom and ...' as read from the words"""
    pos, atoms = 0, []
    while True:
        hits = []
        for (kind, op), rx in ATOM_RX:
            m = rx.match(text, pos)
            if m:
                hits.append((kind, op, m))
        assert len(hits) == 1, f"atom not parsed uniquely at {text[pos:]!r}: {[(h[0], h[1]) for h in hits]}"
        kind, op, m = hits[0]
        g = m.groupdict()
        key = LABEL_KEY[g["l"]]
        if kind == "num":
            atoms.append({"t": "num", "a": key, "op": op, "v": int(g["v"])})
        elif kind == "rng":
            atoms.append({"t": "rng", "a": key, "lo": int(g["a"]), "hi": int(g["b"])})
        elif kind == "flag":
            atoms.append({"t": "flag", "a": key, "v": g["y"] == "yes"})
        elif kind in ("eq", "ne"):
            atoms.append({"t": kind, "a": key, "v": g["x"]})
        else:
            atoms.append({"t": kind, "a": key, "vs": re.split(r", | or ", g["x"])})
        pos = m.end()
        if pos >= len(text):
            return atoms
        assert text.startswith(" and ", pos)
        pos += 5


def parse_policy(text):
    rules, excs, prec, default = [], [], None, None
    for i, line in enumerate(text.split("\n")):
        s = line.strip()
        if i == 0 or not s or s in HEADINGS:
            continue
        s = re.sub(r"^- ", "", s)
        m = re.match(r"^(?:Rule (\d+)\. |(\d+)\. |\((\d+)\) )(.*)$", s)
        if m and not re.match(r"^Rule \d+ (does|is)", s):
            n = int(m.group(1) or m.group(2) or m.group(3))
            body = m.group(4)
            hits = [(i2, re.fullmatch(p, body)) for i2, p in enumerate(RULE_RX)]
            hits = [(i2, mm) for i2, mm in hits if mm]
            assert len(hits) == 1, f"rule not parsed: {body!r}"
            g = hits[0][1].groupdict()
            rules.append({"n": n, "out": OUT_KEY[g["o"].split()[0]], "cond": parse_cond(g["c"])})
            continue
        hits = [mm for p in EXC_RX for mm in [re.fullmatch(p, s)] if mm]
        if hits:
            assert len(hits) == 1
            excs.append({"rule": int(hits[0]["k"]), "cond": parse_cond(hits[0]["c"])})
            continue
        hits = [d for d, p in PREC_RX if re.fullmatch(p, s)]
        if hits:
            assert len(hits) == 1 and prec is None
            prec = hits[0]
            continue
        hits = [mm for p in DEFAULT_RX for mm in [re.fullmatch(p, s)] if mm]
        assert len(hits) == 1 and default is None, f"line not parsed: {s!r}"
        default = OUT_KEY[hits[0]["o"].split()[0]]
    assert prec and default and rules and excs
    return {"rules": rules, "exceptions": excs, "prec": prec, "default": default}


def parse_case(text):
    case = {}
    for line in text.split("\n"):
        k, v = line.split(": ", 1)
        case[k] = int(v) if re.fullmatch(r"\d+", v) else v
    return case


def check(item):
    """the outcome recomputed from the rendered state alone, by a second implementation of the rules"""
    pol = parse_policy(item["state"]["policy"])
    case = parse_case(item["state"]["case"])
    seq = [r["n"] for r in pol["rules"]]
    assert seq == list(range(1, len(seq) + 1)), seq

    def holds(atom):
        v = case[atom["a"]]
        t = atom["t"]
        if t == "num":
            return {">": v > atom["v"], ">=": v >= atom["v"], "<": v < atom["v"], "<=": v <= atom["v"]}[atom["op"]]
        if t == "rng":
            return atom["lo"] <= v <= atom["hi"]
        if t == "flag":
            return v == ("yes" if atom["v"] else "no")
        if t == "eq":
            return v == atom["v"]
        if t == "ne":
            return v != atom["v"]
        return (v in atom["vs"]) if t == "in" else (v not in atom["vs"])

    live = []
    for r in pol["rules"]:
        if all(holds(a) for a in r["cond"]):
            if not any(e["rule"] == r["n"] and all(holds(a) for a in e["cond"]) for e in pol["exceptions"]):
                live.append(r)
    if not live:
        return pol["default"]
    best = live[0] if pol["prec"] == "lower" else live[-1]
    return best["out"]


# ------------------------------------------------------------------------------------------- policies with their cases
PERMS = list(itertools.permutations(NEEDS))                          # needs of (approve, deny, escalate)


def case_pool(rng, policy, n_random=1800, n_near=50):
    """cases of one policy sorted into buckets (outcome, needs, near): near = a decisive numeric attribute within 5 % of a threshold,
    not near = no numeric attribute within 10 % of any threshold"""
    pool = collections.defaultdict(list)
    thr = thresholds(policy)
    near_cands = [(k, T) for k, ts in thr.items() for T in ts if T >= 1]

    def add(case):
        out, needs = classify(policy, case)
        if needs is None:
            return
        decisive, dmin = near_report(policy, case)
        if decisive:
            pool[(out, needs, True)].append((case, decisive, dmin))
        elif dmin > 0.10:
            pool[(out, needs, False)].append((case, [], dmin))

    profile = lambda: dict(p_flag=rng.choice([0.15, 0.5, 0.85]), p_num=rng.choice([None, 0.2, 0.8]))
    for _ in range(n_random):
        case = sample_case(rng, policy, None, **profile())
        if case:
            add(case)
    for cand in near_cands:
        for _ in range(n_near):
            case = sample_case(rng, policy, cand, **profile())
            if case:
                add(case)
    return pool


def risk_signals(policy, case):
    """(flags at their risk value, numbers on the risky half of their scale) of a case record: how risky the record looks"""
    adef = DOMAINS[policy["domain"]]["attrs"]
    f = n = 0
    for k, v in case.items():
        a = adef[k]
        if a["kind"] == "flag" and a["risk"] is not None:
            f += (v == "yes") == a["risk"]
        elif a["kind"] == "num":
            mid = a["ths"][len(a["ths"]) // 2]
            n += (v > mid) if a["risk"] == "high" else (v < mid)
    return f, n


def pick_cases(rng, policy, pool, buckets, n_cand=45):
    """one case per bucket.  The cases of one policy lead to different outcomes, so a reader who ignores the policy and only asks which record
    looks the riskiest would get above chance in a coherent policy.  Among candidates the cases are therefore chosen so that the three
    records carry about the same number of risk signals (flags at their risk value, numbers on the risky half of the scale)."""
    cands = []
    for b in buckets:
        lst = pool[b]
        sub = lst if len(lst) <= n_cand else rng.sample(lst, n_cand)
        cands.append([(c, risk_signals(policy, c[0])) for c in sub])
    best, ties = None, []
    ai = next((k for k, b in enumerate(buckets) if b[0] == "approve"), None)
    want_low = rng.random() < 1 / 3          # where the records cannot be matched, the approve case is the least risky-looking one in a third
    for trio in itertools.product(*cands):
        fs, ns = [t[1][0] for t in trio], [t[1][1] for t in trio]
        tot = [a + b for a, b in zip(fs, ns)]
        obj = 4 * (max(tot) - min(tot)) + 2 * (max(fs) - min(fs)) + (max(ns) - min(ns))
        if ai is not None and len(trio) == 3:
            obj += 0 if (tot[ai] < min(t for k, t in enumerate(tot) if k != ai)) == want_low else 3
        if best is None or obj < best:
            best, ties = obj, [trio]
        elif obj == best:
            ties.append(trio)
    return [t[0] for t in rng.choice(ties)]


def make_group(i, slot, quota, variant=0):
    """-> (policy, [(outcome, needs, near, case, info)]) for one policy slot; quota = remaining permutations / near outcomes;
    variant = which draw of the cases among the candidates (the vocabulary test may ask for another one)"""
    for attempt in range(4000):
        rng = rng_for("policy", i, attempt)
        policy = make_policy(rng, slot["domain"], slot["level"], slot["prec"], rng.choice(OUTCOMES))
        if policy is None:
            continue
        pool = case_pool(rng, policy)
        if slot["size"] == 2:
            picks = []
            for (o, n), near in zip(slot["pair"], slot["pair_near"]):
                if not pool.get((o, n, near)):
                    break
                picks.append((o, n, near))
            else:
                cs = pick_cases(rng_for("pick", i, variant), policy, pool, picks)
                return policy, [(o, n, near, *c) for (o, n, near), c in zip(picks, cs)], None
            continue
        best = None
        for pi, perm in enumerate(PERMS):
            if quota["perm"][pi] <= 0:
                continue
            for o_near in range(3):
                if quota["near"][o_near] <= 0:
                    continue
                if all(pool.get((OUTCOMES[k], perm[k], k == o_near)) for k in range(3)):
                    score = quota["perm"][pi] + 0.5 * quota["near"][o_near] + rng.random() * 0.1
                    if best is None or score > best[0]:
                        best = (score, pi, o_near)
        if best:
            _, pi, o_near = best
            perm = PERMS[pi]
            buckets = [(OUTCOMES[k], perm[k], k == o_near) for k in range(3)]
            members = [(*b, *c) for b, c in zip(buckets, pick_cases(rng_for("pick", i, variant), policy, pool, buckets))]
            return policy, members, (pi, o_near)
    raise RuntimeError(f"policy slot {i}: no policy found for {slot}")


def make_slots():
    """201 policy slots: per level 66 triples and one pair; domains and precedence directions balanced"""
    rng = rng_for("plan")
    pairs = {4: ([("approve", "plain"), ("deny", "exception")], [True, False]),
             8: ([("deny", "precedence"), ("escalate", "plain")], [True, False]),
             12: ([("escalate", "exception"), ("approve", "precedence")], [False, False])}
    slots = []
    for lv in LEVELS:
        slots += [{"level": lv, "size": 3} for _ in range(66)]
        pr, nr = pairs[lv]
        slots.append({"level": lv, "size": 2, "pair": pr, "pair_near": nr})
    rng.shuffle(slots)
    doms = [DOMAIN_NAMES[k % 4] for k in range(len(slots))]
    precs = ["lower", "higher"] * (len(slots) // 2 + 1)
    rng.shuffle(doms)
    rng.shuffle(precs)
    for sl, d, pr in zip(slots, doms, precs):
        sl["domain"], sl["prec"] = d, pr
    return slots


def to_items(pid, policy, members, rng_text):
    """the items of one policy: the policy is rendered once and shared; each member has its own case, option order and extra lines"""
    look = {"layout": rng_text.randrange(4), "numbering": rng_text.randrange(3), "rule_frame": rng_text.randrange(5), "exc_frame": rng_text.randrange(4),
            "prec_frame": rng_text.randrange(4), "default_frame": rng_text.randrange(4), "title": rng_text.choice(DOMAINS[policy["domain"]]["titles"])}
    text = render_policy(rng_text, policy, look)
    items = []
    for k, (outcome, needs, near, case, decisive, dmin) in enumerate(members):
        rng = rng_for("render", pid, k)
        out, fires, applicable = engine(policy, case)
        order = OUTCOMES[:]                                          # replaced by assign_orders
        spec = {"policy": {x: policy[x] for x in ("domain", "rules", "exceptions", "prec", "default")}, "case": case}
        meta = {"policy_id": pid, "level": LEVEL_OF[len(policy["rules"])], "rules": len(policy["rules"]), "needs": needs, "near_threshold": near,
                "near_attr": decisive[0][0] if decisive else None, "near_distance_pct": decisive[0][2] if decisive else None,
                "domain": policy["domain"], "precedence": policy["prec"], "default": policy["default"], "exceptions": len(policy["exceptions"]),
                "rules_holding": [r["n"] for r in fires], "rules_applicable": [r["n"] for r in applicable], "order": order, "layout": look["layout"],
                "risk_signals": list(risk_signals(policy, case)),
                "group_size": len(members), "spec": spec}
        items.append({"id": None, "state": {"policy": text, "case": render_case(rng, policy["domain"], case, pid, OUTCOMES.index(outcome))},
                      "questions": {"q": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": {x: OPTION_TEXT[x] for x in order}}},
                      "gold": out, "soft": None, "group": f"{TASK}:policy:{pid:03d}", "meta": meta})
        assert out == outcome
    return items


def assign_orders(items):
    """the order of the three options is drawn per item; within every outcome the six orders occur 33 or 34 times, so that the
    first-listed option is the right one in a third of the items; recorded in meta.order and frozen in the file"""
    rng = rng_for("options")
    perms = list(itertools.permutations(OUTCOMES))
    for gold in OUTCOMES:
        idx = [i for i, r in enumerate(items) if r["gold"] == gold]
        orders = [perms[k % 6] for k in range(len(idx))]
        rng.shuffle(orders)
        for i, order in zip(idx, orders):
            items[i]["questions"]["q"]["criteria"] = {k: OPTION_TEXT[k] for k in order}
            items[i]["meta"]["order"] = list(order)


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
    return tested, worst, bad


# --------------------------------------------------------------------------------------------------- output
def run_tool(script, *args):
    r = subprocess.run([sys.executable, os.path.join(AUDITS, script), "--root", HERE] + list(args), capture_output=True, text=True, cwd=REPO)
    return r.stdout.strip().split("\n")


def fmt_item(it):
    m = it["meta"]
    out = [f"id `{it['id']}` (gold **{it['gold']}**, needs `{m['needs']}`, near threshold: {m['near_threshold']}"
           + (f" - `{m['near_attr']}` {m['near_distance_pct']} % from its threshold" if m["near_threshold"] else "") + ")", "",
           "state.policy:", "```", it["state"]["policy"], "```", "state.case:", "```", it["state"]["case"], "```",
           f"question: {it['questions']['q']['instructions']}", ""]
    out += [f"- `{k}`: {v}" for k, v in it["questions"]["q"]["criteria"].items()]
    return "\n".join(out)


def main(variant=0):
    slots = make_slots()
    quota = {"perm": [33] * 6, "near": [66] * 3}
    built = []
    for i, sl in enumerate(slots):
        policy, members, used = make_group(i, sl, quota, variant)
        if used:
            quota["perm"][used[0]] -= 1
            quota["near"][used[1]] -= 1
        built.append((i, policy, members))
    assert quota["perm"] == [0] * 6 and quota["near"] == [0] * 3, quota
    items = []
    for i, policy, members in built:
        items += to_items(i, policy, members, rng_for("text", i))
    rng_for("order").shuffle(items)
    for n, it in enumerate(items, 1):
        it["id"] = f"{TASK}:{n:05d}"
        it["meta"]["source_id"] = f"{n:05d}"
    assign_orders(items)
    for it in items:
        spec = it["meta"]["spec"]
        policy, case = spec["policy"], spec["case"]
        # ---- truth twice
        assert truth(spec) == it["gold"]
        assert check(it) == truth(spec), f"{it['id']}: check {check(it)} != truth {truth(spec)}"
        # ---- the structure of the item is what the plan says (proved again from the specification alone)
        out, needs = classify(policy, case)
        m = it["meta"]
        assert (out, needs) == (it["gold"], m["needs"]) and needs is not None
        assert m["rules"] == len(policy["rules"]) and m["exceptions"] >= 1
        assert sorted(it["questions"]["q"]["criteria"]) == sorted(OUTCOMES) and list(it["questions"]["q"]["criteria"]) == m["order"]
        decisive, dmin = near_report(policy, case)
        if m["near_threshold"]:
            assert decisive and all(is_near(case[a], T) for a, T, _ in decisive), it["id"]   # within 5 % of a threshold, and it decides
        else:
            assert not decisive and dmin > 0.10, (it["id"], decisive, dmin)
        rev = "higher" if policy["prec"] == "lower" else "lower"
        if needs == "exception":
            assert engine(policy, case, exceptions=False)[0] != out
        elif needs == "precedence":
            assert engine(policy, case, prec=rev)[0] != out
        else:
            assert engine(policy, case, exceptions=False)[0] == out and engine(policy, case, prec=rev)[0] == out
        it["_class"] = it["gold"]
    cnt = lambda key: collections.Counter(r["meta"][key] for r in items)
    assert len(items) == N_ITEMS
    assert collections.Counter(r["gold"] for r in items) == {o: 200 for o in OUTCOMES}
    assert set(cnt("rules").values()) == {200} and set(cnt("needs").values()) == {200}, (cnt("rules"), cnt("needs"))
    assert sum(r["meta"]["near_threshold"] for r in items) == 200
    pol_dom = {r["meta"]["policy_id"]: r["meta"]["domain"] for r in items}
    pol_prec = {r["meta"]["policy_id"]: r["meta"]["precedence"] for r in items}
    assert len(pol_dom) == 201 and set(collections.Counter(pol_dom.values()).values()) <= {50, 51}
    assert set(collections.Counter(pol_prec.values()).values()) <= {100, 101}
    cell = collections.Counter((r["gold"], r["meta"]["needs"]) for r in items)
    first = collections.Counter(next(iter(r["questions"]["q"]["criteria"])) for r in items)
    groups = collections.defaultdict(list)
    for r in items:
        groups[r["group"]].append(r)
    assert all(len({x["state"]["policy"] for x in g}) == 1 and len({x["gold"] for x in g}) == len(g) for g in groups.values())
    assert collections.Counter(len(g) for g in groups.values()) == {3: 198, 2: 3}
    # ---- the policies read like policies and the case records are consistent (v4)
    stats = collections.Counter()
    for i, policy, members in built:
        c = coherence(policy)
        assert not any(c.values()) and not problems(policy), (i, dict(c))
        stats["policies"] += 1
        stats["rules"] += len(policy["rules"])
        stats["exceptions"] += len(policy["exceptions"])
    for it in items:
        policy, case = it["meta"]["spec"]["policy"], it["meta"]["spec"]["case"]
        adef = DOMAINS[policy["domain"]]["attrs"]
        acted = acted_flags(adef, policy["rules"])
        for k, v in case.items():
            a = adef[k]
            assert not (a["kind"] == "flag" and a["risk"] is not None and k not in acted and (v == "yes") == a["risk"]), (it["id"], k)
        for child, parent, ratio in DEPS[policy["domain"]]:
            assert case[child] <= case[parent] // ratio, (it["id"], child, parent)
    stats["blind"] = blind_risk_reader(items)
    tested, worst, bad = vocabulary_test(items, OUTCOMES)
    return items, tested, worst, bad, cell, first, stats


def finish(items, tested, worst, bad, cell, first, stats):
    assert not bad, f"vocabulary cue: {bad[:10]}"
    lengths = [len(state_text(r)) for r in items]
    for r in items:
        del r["_class"]
    d = f"{HERE}/tasks/{TASK}"
    os.makedirs(d, exist_ok=True)
    with open(f"{d}/items.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(items, key=lambda r: r["id"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    task = {"task": TASK, "layer": "B", "title": "Generated policies: what does the written policy require for this case?",
            "decision": "whether a written policy requires approving, denying or escalating a request, given the case record (rules, exceptions, a precedence statement and a default)",
            "source": {"name": f"generator build/gen_{TASK}.py", "url": "", "files": [], "split": "generated, seed 20261007",
                       "version": "gen_v4, 2026-10-08: every rule reads a condition in the direction of its outcome, no dead or duplicate rules, no unread risk flags, consistent case records, meta.level"},
            "licence": "generated by the benchmark's script (no third-party text)", "redistribution": "items included",
            "labels": "programmatic", "item_source": "generated", "metric": "accuracy", "chance": round(1 / 3, 4), "rows": len(items),
            "groups": 201, "question_type": "choice", "options": 3,
            "notes": ("600 items in 201 policy groups (group, meta.policy_id): a numbered policy of 4, 8 or 12 rules with at least one exception, a precedence statement and a default, and a case record; "
                      "198 policies are used for three cases (one per outcome), three for two. The metric is item accuracy. "
                      "Outcome (approve / deny / escalate), meta.needs (plain / exception / precedence, proved by ablation) and the dial (rules) are balanced exactly; "
                      "200 items have a numeric attribute within 5 percent of a threshold of the policy that decides the outcome (meta.near_threshold). The option order "
                      "is drawn per item (meta.order). Everything is invented and every answer is computed twice (rule engine on the specification and a parser of the "
                      "rendered text with a second engine). gen_v4 (2026-10-08): the policies read like policies - a rule that denies or escalates reads a condition that signals "
                      "risk, a rule that approves one that signals low risk, exceptions mirror that; no rule is dead or repeats another; a flag that can signal risk has its risk value in the case record only where "
                      "a deny / escalate rule reads it; fields with a natural order are consistent (account age >= days since purchase, training no older than tenure); meta.level = 1 / 2 / 3 "
                      "for 4 / 8 / 12 rules. State length %d to %d characters (median %d)." % (min(lengths), max(lengths), sorted(lengths)[300]))}
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
    assert not a["flag"], a
    write_readme(d, items, cell, lengths, val, aud, tested, worst, first, stats)
    print("vocabulary test:", tested, "tokens with frequency >= 20, worst ratio %.2f (%s)" % worst)
    print("state length", min(lengths), max(lengths), "median", sorted(lengths)[300])


def write_readme(d, rows, cell, lengths, val, aud, tested, worst, first, stats):
    cnt = lambda key: collections.Counter(r["meta"][key] for r in rows)
    ex = []
    for lv, nd in ((4, "plain"), (8, "exception"), (12, "precedence")):
        ex.append(next(x for x in sorted(rows, key=lambda x: x["id"]) if x["meta"]["rules"] == lv and x["meta"]["needs"] == nd and x["meta"]["near_threshold"]))
    near_by = collections.Counter((r["meta"]["rules"], r["meta"]["near_threshold"]) for r in rows)
    by_lv = collections.Counter((r["meta"]["level"], r["gold"]) for r in rows)
    by_nd = collections.Counter((r["meta"]["level"], r["meta"]["needs"]) for r in rows)
    lv_tab = ("| `meta.level` (rules) | approve | deny | escalate | plain | exception | precedence |\n|---|---|---|---|---|---|---|\n" + "\n".join(
        f"| {lv} ({LEVELS[lv - 1]}) | " + " | ".join(str(by_lv[(lv, o)]) for o in OUTCOMES) + " | " + " | ".join(str(by_nd[(lv, n)]) for n in NEEDS) + " |" for lv in (1, 2, 3)))
    blind = stats["blind"]
    txt = f"""# {TASK}

Generated policies: what does the written policy require for this case? (layer B, generated, programmatic truth)

- Decision: whether a written policy requires approving, denying or escalating a request, given the case record (rules, exceptions, a precedence statement and a default).
- Source: generator `build/gen_{TASK}.py` (standard library only, `random.Random(20261007)` and sub-generators; the output is identical on every run); no third-party text.
- Licence: generated by the benchmark's script (no third-party text); items included.
- Rows: {len(rows)} in 201 policy groups (200 approve, 200 deny, 200 escalate); metric: accuracy (chance 0.333).
- Rebuild: `python3 build/gen_{TASK}.py`

## What is generated

A policy for handling a request in one of four domains (refund requests, data-export requests, access to an internal system, expense claims) with 4, 8 or 12 numbered rules and a case record of
`key: value` lines (the attributes of the domain plus `request_id`, `submitted_on` and `channel`, which no rule uses). A rule names one to three conditions and an outcome. Conditions are numbers with a unit
(whether a limit counts is in the words: "at least 90 days" counts 90, "more than 90 days" does not, "between 50 and 200 EUR inclusive"), regions / tiers / teams (one, one of, none of) and yes-no flags;
four phrasings per comparison, sixteen for numeric limits in all, five frames for a rule. Every policy has one to four **exceptions** (at most one per rule, on attributes the rule does not use; "Rule 5 does not apply when ..."
in four phrasings), a **precedence** statement (the lower-numbered or the higher-numbered rule decides when applicable rules lead to different outcomes; four phrasings each) and a **default** (what happens when no rule applies; four
phrasings). Names of regions and teams are invented; the policy is shown in one of four layouts (headings or not; general provisions before or after the rules). The question has the options `approve`, `deny`, `escalate` in an order drawn
per item (`meta.order`; first listed: {', '.join(f'{k} {v}' for k, v in sorted(first.items()))}).

**Policies that read like policies (gen_v4).** Every attribute has a direction of risk (a large amount, a long time since the purchase, a young account, a missing consent, a fraud alert, an open
incident, a failed check ... signal risk; a small amount, a verified requester, proof of purchase ... signal low risk). A rule that denies or escalates reads at least one condition that signals risk
(and no condition that signals low risk; a band such as "between 100 and 1000 EUR inclusive" counts as a risk condition); a rule that approves reads only conditions that signal low risk. An exception to an approving
rule is a risk signal ("Rule 3 does not apply when the fraud alert flag is yes"), an exception to a denying or escalating rule is a mitigating condition. Categories (region, tier, team, cost centre) carry no direction. Limits sit where they mean something (a risk limit in the upper two thirds of the usual limits of a quantity that grows with risk, a safe limit in the lower two thirds; never "more than 3 days" as a risk, never "at most 1500 EUR" as safe). A flag that can signal risk is read only
when some deny / escalate rule reacts to it, and in the case record it has its risk value only for those flags; a number that no rule reads stays on the safe side of its scale. Rules are checked on the whole attribute space
(the space is cut into the cells that no condition can tell apart and every cell is examined, so the check is exact, not sampled): every rule decides in some case (it is the first applicable rule under the precedence statement and the
outcome without it would be another one), every exception changes an outcome somewhere, and no two rules with the same outcome have the same kinds of conditions in at least half of their union (a rule that repeats another with other numbers).
Rules that fail are drawn again, or moved to another place in the list. The case record keeps fields in their natural order: days since the purchase <= account age, earlier refunds <= account age in days // 7,
exports in the last 30 days <= account age, days since the last security training <= tenure. The three cases of a policy are chosen so that the three records carry about the same number of risk signals (flags at their risk value,
numbers on the risky half of their scale; `meta.risk_signals`), because a reader who ignores the policy could otherwise take the least risky-looking record for the approve case.

**Triples.** Every policy is used for one case per outcome, so that the policy text cannot tell the outcome: 198 policies give a triple (the same policy text with a case that leads to `approve`, one to `deny`, one to `escalate`; the three
cases need three different things - `plain`, `exception`, `precedence` - and exactly one of the three is a near-threshold case) and three policies (one per dial level) give a pair; 201 policies, 600 items (`group` = the policy,
`meta.policy_id`, `meta.group_size`). The three cases of a triple lead to three outcomes, so a model that ignores the case and answers from the policy alone is right in one of three items of a group at most. The permutation of
`needs` over the outcomes is chosen per policy among the ones the policy can produce; every one of the six permutations is used 33 times.

**What the answer needs (`meta.needs`, 200 items each, proved by ablation).** `plain`: no exception cancels an applicable rule and the applicable rules agree. `exception`: the outcome changes when the exceptions are switched off
and no conflict remains after them. `precedence`: two applicable rules disagree and reversing the precedence statement changes the outcome. Items that mix both are not used. So two thirds of the items need an exception or the precedence statement.
In `plain` items an exception can still be present as a distractor (its rule does not hold, or its condition is false).

**Near the thresholds (`meta.near_threshold`, 200 items).** A numeric attribute of the case lies within 5 % of a threshold of the policy (or exactly on it) AND moving it to the other side of that threshold would change the outcome (asserted); the distance is
in `meta.near_distance_pct`. In the other 400 items no numeric attribute is within 10 % of any threshold of the policy.

## Dials

| dial | levels | items per level | near-threshold items per level |
|---|---|---|---|
| `rules` (numbered rules of the policy); `meta.level` = 1 / 2 / 3 | 4, 8, 12 | 200 each (66 triples and one pair of policies) | {near_by[(4, True)]} / {near_by[(8, True)]} / {near_by[(12, True)]} |

State length: {min(lengths)} to {max(lengths)} characters (median {sorted(lengths)[len(lengths)//2]}). Policies per domain: {', '.join(f'{k} {v}' for k, v in sorted(collections.Counter(dict((r['meta']['policy_id'], r['meta']['domain']) for r in rows).values()).items()))}; policies per precedence direction: {', '.join(f'{k} {v}' for k, v in sorted(collections.Counter(dict((r['meta']['policy_id'], r['meta']['precedence']) for r in rows).values()).items()))}.

## Counts

| outcome \\ `meta.needs` | plain | exception | precedence | all |
|---|---|---|---|---|
""" + "\n".join(f"| `{o}` | " + " | ".join(str(cell[(o, n)]) for n in NEEDS) + f" | {sum(cell[(o, n)] for n in NEEDS)} |" for o in OUTCOMES) + f"""
| all | """ + " | ".join(str(cnt('needs')[n]) for n in NEEDS) + f""" | {len(rows)} |

Per level (outcomes are balanced inside every level as far as 200 items allow; `needs` likewise):

{lv_tab}

(No planted deviation: the task has no negatives; the contrast is between the three cases of one policy. `meta.rules_holding` lists the rules whose conditions hold, `meta.rules_applicable` those that apply after the exceptions.)

## Checks made by the script

- `truth(spec)` (rule engine on the structured policy) and `check(item)` (parses the rendered policy and the case lines and runs a second engine) agree on all 600 items.
- Exactly one outcome per item; the outcome, `needs` and the dial are the ones the plan asked for (proved again from the specification alone); the ablations that define `needs` hold; every near-threshold item has a decisive numeric attribute within 5 % of a threshold (flipping it changes the outcome), no other item has a numeric attribute within 10 %.
- Coherence of the {stats['policies']} policies ({stats['rules']} rules, {stats['exceptions']} exceptions), asserted for every policy: 0 rules against the direction of risk, 0 exceptions against it, 0 dead rules, 0 dead exceptions, 0 pairs of near-duplicate rules,
  0 flags that signal risk and are read where no deny / escalate rule reacts to them. In the case records: 0 risk-valued flags that no deny / escalate rule reads, 0 fields against their natural order. (The previous version, v0, had
  338 of 1,608 rules against the direction of risk (556 with any condition against it), 241 of 514 exceptions against it, 294 dead rules (1.46 per policy, in 140 of 201 policies), 116 dead exceptions, 104 pairs of near-duplicate rules,
  an unread risk flag in 290 of 600 records (91 of 201 with the default approve) and 165 field pairs against their order in 137 records.)
- A reader that ignores the policy and calls the least risky-looking record of a triple the approve case is right in {blind[0]:.1%} of the {blind[2]} triples (chance 33.3 %; v0: 35.9 %); the three records carry the same number of risk signals in {blind[1]:.0%} of the triples.
- Exact balance: 200 items per outcome, per `needs`, per dial level; 200 near-threshold items; 198 triples (one case per outcome) and 3 pairs; 50 or 51 policies per domain and 100 or 101 per precedence direction.
- Vocabulary test: {tested} tokens of frequency >= 20 are tested over the three outcome classes; none occurs in one class at more than twice the rate of another (largest ratio {worst[0]:.2f}, `{worst[1]}`).
- Shortcut audit (`python3 audit.py {TASK}`): no flag (majority and first-listed rules stay at chance):

```
{aud[0]}
{aud[1]}
```

Validator: `{val[1].strip() if len(val) > 1 else val}`

## Examples (one per `rules` level; near-threshold items)

""" + "\n\n".join(f"### rules = {x['meta']['rules']}, needs `{x['meta']['needs']}`\n\n" + fmt_item(x) for x in ex) + """

## Independence from training generators

The items are disjoint from any training generator of the authors by construction: this is a new generator, written for the benchmark;
names, thresholds, templates and policies share nothing with the generators used for training.
"""
    open(f"{d}/README.md", "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    for variant in range(200):                                       # the vocabulary test is a chance event for rare numbers: draw the cases again
        built = main(variant)
        if not built[3]:
            break
    else:
        raise RuntimeError("no draw of the cases passes the vocabulary test")
    finish(*built)
