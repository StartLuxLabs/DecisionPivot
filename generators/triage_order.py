"""Task triage_order (gen_v4 = gen_v3 with the quality fixes of 2026-10-08; layer D, generated, programmatic truth,
EVALUATION ONLY): "Which waiting case do the rules put at the position asked for in the state?"

State: a service point (six domains with their own nouns and columns: walk-in clinic, support desk, repair workshop,
harbour berths, render farm / print room / batch cluster, citizens' counter), the current time, numbered ordering rules
applied in the order given, the conventions they need (written in words), the queue (ticket, class, arrival, flag; from
level 2 an appointment time and a duration) and the position asked for.  Options: five ticket ids of the queue.

Levels: 1 = 6 cases, two or three rules, first place: class then arrival, class then ticket, or class, arrival, ticket
(class is always rule 1: a class that is listed but ignored is never shown); 2 = 9-10 cases, one class
change (waiting limit W or a named flag) + class + one tie-break rule + ticket, first or second place; 3 = 12-14 cases,
both class changes (cumulative or not, stated), class, one or two tie-break rules (appointment due, arrival, duration),
ticket, first to third place, waits on W and 1-3 minutes either side, appointments due on the minute.

Fixes of gen_v4 (reviewer notes of 2026-10-07):
  * consistent times: an appointment time (slot / callback / pickup / window / reserved start / booked time) is never
    before the arrival time of its case, and in the workshop (pickup) never before check-in + bench time; the dependent
    time is drawn after the times it depends on, and the table of every state, parsed back from the text, is asserted;
  * no class-first shortcut: the reading "lowest LISTED class first, then earliest arrival" (adjustments, flags,
    appointments and the written rules ignored) is the key in at most one member of every group at levels 2-3 (and in at
    most 25 % of the items of a level, asserted); at level 1 class is rule 1 in every rule set - the top class always has at
    least two cases, so the second rule always decides, and "class first, ignore the second rule" (the other tie-break)
    gives a different answer in every member; the rule set arrival, ticket of gen_v3 (class shown, never used) is gone;
    level-1 flags are the neutral markers.

Groups: 66 groups of three + 1 group of two per level on one queue; the members differ in ONE element (current time,
one flag, one arrival time, one listed class at level 1, or the position asked for; asserted with diff_elements) and have
different answers among the same five options.  Options = the members' answers + the cases most misreadings point to
(readings(): no adjustment, one adjustment ignored, combination swapped, limit not counted, earliest arrival, one place
off, reversed tie-break, ...); roles in meta.option_roles.  Gold option place balanced exactly (40 per place and level),
gold rows spread evenly over the listing, listing order never a sorted order.

Truth: truth(spec) = sorted by sort_key (one key per rule); a second implementation (pairwise duels, precedes()) must
give the same strict total order.  Environment: BENCH_OUT=<dir> writes <dir>/triage_order/; BENCH_SEED=<k> (only with
BENCH_OUT) roots every generator at k (ids triage_order:s<k>:<n>).
    python3 generators/triage_order.py"""
import collections
import itertools
import json
import os
import random
import re
import sys

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated")   # items go to HERE/tasks/<family>/ (BENCH_OUT: elsewhere)
TASK = "triage_order"
DEFAULT_SEED = 20261007
ENV_SEED = os.environ.get("BENCH_SEED")
ENV_OUT = os.environ.get("BENCH_OUT")
SEED = int(ENV_SEED) if ENV_SEED not in (None, "") else DEFAULT_SEED
SEALED = ENV_SEED not in (None, "")
ID_PREFIX = f"{TASK}:s{SEED}" if SEALED else TASK
OUT_DIR = os.path.join(ENV_OUT, TASK) if ENV_OUT else os.path.join(HERE, "tasks", TASK)
SALT = random.Random(SEED).getrandbits(64)          # every generator of the script is derived from random.Random(SEED)

VERSION = ("gen_v4, 2026-10-08: consistent times (no appointment before its arrival, workshop pickup not before check-in + bench time), "
           "no class-first shortcut (level 1: class is rule 1 in every rule set; levels 2-3: capped at one member per group and 25 % of the items)")
INSTRUCTIONS = "Which waiting case do the rules put at the position asked for in the state?"
ORDINAL = {1: "first", 2: "second", 3: "third"}
LEVEL_SIZES = {1: [6], 2: [9, 10], 3: [12, 13, 14]}
TRIPLES_PER_LEVEL, PAIRS_PER_LEVEL = 66, 1          # 66 * 3 + 1 * 2 = 200 items per level
KINDS = {1: ["arrival", "class"], 2: ["clock", "flag", "arrival"], 3: ["clock", "flag", "arrival", "position"]}


def rng_for(*parts):
    return random.Random(f"{SALT}:{TASK}:" + ":".join(str(p) for p in parts))


def hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


# ------------------------------------------------------------------------------------------------ domains
# every domain has its own nouns, column names, markers and terms; the rule and note sentences take them as slots
DOMAINS = collections.OrderedDict()
DOMAINS["clinic"] = dict(
    points=["walk-in clinic {N}, reception desk {k}", "{N} minor-injuries unit, front counter {k}",
            "{N} health centre, walk-in reception {k}"],
    noun="patient", nouns="patients", prefix=["P", "K", "W"], cls="triage class",
    arr_col="arrived", arr_noun="arrival", arr_verb="arrived", arr_legend="time the patient arrived",
    flags=["frail", "infant"], decoys=["interpreter", "newfile"],
    appt_col="slot", appt_noun="booked slot", appt_legend="time of the booked slot",
    mins_col="consult", mins_noun="consultation time", mins_legend="expected consultation time in minutes")
DOMAINS["helpdesk"] = dict(
    points=["IT support desk of {N}, line {k}", "{N} service desk, team {k}", "customer support queue of {N}, shift desk {k}"],
    noun="request", nouns="requests", prefix=["R", "S", "H"], cls="priority class",
    arr_col="logged", arr_noun="logging time", arr_verb="was logged", arr_legend="time the request was logged",
    flags=["outage", "blocked"], decoys=["remote", "hardware"],
    appt_col="callback", appt_noun="callback slot", appt_legend="time of the agreed callback",
    mins_col="effort", mins_noun="estimated effort", mins_legend="estimated effort in minutes")
DOMAINS["workshop"] = dict(
    points=["{N} repair workshop, bench {k}", "appliance repair counter {N}, bay {k}", "{N} cycle and tool repairs, service bench {k}"],
    noun="job", nouns="jobs", prefix=["J", "B", "M"], cls="urgency class",
    arr_col="checkin", arr_noun="check-in", arr_verb="was checked in", arr_legend="time the job was checked in",
    flags=["safety", "courier"], decoys=["warranty", "quote"],
    appt_col="pickup", appt_noun="pickup time", appt_legend="time of the agreed pickup",
    mins_col="bench", mins_noun="bench time", mins_legend="expected bench time in minutes",
    appt_after_work=True)          # a job cannot be picked up before check-in + bench time
DOMAINS["harbour"] = dict(
    points=["berth planning at {N} harbour, quay {k}", "{N} port control, berth desk {k}", "{N} terminal, berth allocation post {k}"],
    noun="vessel", nouns="vessels", prefix=["V", "H", "N"], cls="berth class",
    arr_col="anchored", arr_noun="anchoring time", arr_verb="anchored", arr_legend="time the vessel dropped anchor",
    flags=["reefer", "tidal"], decoys=["pilot", "bunker"],
    appt_col="window", appt_noun="berth window", appt_legend="start of the booked berth window",
    mins_col="turnaround", mins_noun="turnaround time", mins_legend="expected turnaround time in minutes")
DOMAINS["renderfarm"] = dict(
    points=["render farm {N}, node pool {k}", "{N} print room, production queue {k}", "{N} batch cluster, queue {k}"],
    noun="task", nouns="tasks", prefix=["T", "Q", "G"], cls="queue class",
    arr_col="submitted", arr_noun="submission", arr_verb="was submitted", arr_legend="time the task was submitted",
    flags=["rush", "review"], decoys=["draft", "retry"],
    appt_col="reserved", appt_noun="reserved start", appt_legend="time of the reserved start",
    mins_col="runtime", mins_noun="run time", mins_legend="expected run time in minutes")
DOMAINS["counter"] = dict(
    points=["citizens' service counter {N}, window {k}", "{N} permit office, counter {k}", "{N} town hall, service desk {k}"],
    noun="visitor", nouns="visitors", prefix=["C", "D", "L"], cls="service class",
    arr_col="entered", arr_noun="entry", arr_verb="entered", arr_legend="time the visitor entered",
    flags=["mobility", "carer"], decoys=["renewal", "courier"],
    appt_col="booked", appt_noun="booked time", appt_legend="time of the booked appointment",
    mins_col="desk", mins_noun="desk time", mins_legend="expected desk time in minutes")

NAME_A = ["Tar", "Osk", "Bri", "Vel", "Mor", "Kes", "Lun", "Hav", "Dor", "Sel", "Fen", "Gry", "Pol", "Rin", "Ulm", "Wex",
          "Yar", "Zel", "Cal", "Eld", "Nor", "Quen", "Ib", "Ash", "Jor", "Tov", "Mab", "Rud"]
NAME_B = ["avenn", "ekeld", "imaro", "ostix", "uvolm", "arge", "umbe", "eska", "ivar", "onde", "urra", "enko", "anthe",
          "ilmo", "orrin", "ettra"]


def place_name(rng):
    return rng.choice(NAME_A) + rng.choice(NAME_B)


# ------------------------------------------------------------------------------------------------ sentences
# three phrasings per sentence type; the rule kinds keep their own key words (class number / waited, waiting / flag /
# due / earlier / shorter, fewer minutes / ticket number), so a rule can be recognised whatever the phrasing
RULE_TEXT = {
    "wait": ["A {noun} that has waited at least {W} minutes moves up one class.",
             "Once the waiting time of a {noun} is at least {W} minutes, it is moved up one class.",
             "Waiting at least {W} minutes lifts a {noun} by one class."],
    "flag": ["A {noun} with the flag \"{F}\" counts one class more urgent.",
             "The flag \"{F}\" moves a {noun} up one class.",
             "Any {noun} carrying the flag \"{F}\" is lifted by one class."],
    "class": ["Lower class number first.",
              "A {noun} with a lower class number goes before a {noun} with a higher class number.",
              "The {nouns} are taken class by class, smallest class number first."],
    "appt": ["Within the same class, {nouns} whose {appt_noun} is due go first.",
             "Among {nouns} of one class, a {noun} with a due {appt_noun} is ahead of a {noun} without a due one.",
             "Inside a class, every {noun} whose {appt_noun} is due precedes every {noun} whose {appt_noun} is not due."],
    "arrival": ["Earlier {arr_noun} first.",
                "The {noun} that {arr_verb} earlier goes first.",
                "Of two {nouns}, the one with the earlier time under \"{arr_col}\" is ahead."],
    "mins": ["Shorter {mins_noun} first.",
             "The {noun} with the shorter {mins_noun} goes first.",
             "Of two {nouns}, the one with fewer minutes under \"{mins_col}\" is ahead."],
    "ticket": ["Lower ticket number first.",
               "Last tie-break: the {noun} with the lower ticket number goes first.",
               "If {nouns} are still level, the lower ticket number is ahead."],
}
NOTE_TEXT = {
    "order": ["The rules are applied in the order given: a rule decides only between {nouns} that all rules before it leave level.",
              "Read the rules from top to bottom; a later rule is used only to separate {nouns} that every earlier rule leaves level.",
              "An earlier rule always outranks a later one; a later rule only breaks ties that remain after the rules above it."],
    "classword1": ["Rule 1 changes the class of a {noun} and is applied to every {noun} before anything is compared; in the rules after it, \"class\" means the class after this change.",
                   "First apply rule 1 to each {noun}; from rule 2 on, the word \"class\" stands for the changed class.",
                   "Rule 1 does not order anything by itself: it sets the class that the later rules use."],
    "classword2": ["Rules 1 and 2 change the class of a {noun} and are applied to every {noun} before anything is compared; in the rules after them, \"class\" means the class after these changes.",
                   "First apply rules 1 and 2 to each {noun}; from rule 3 on, the word \"class\" stands for the changed class.",
                   "Rules 1 and 2 do not order anything by themselves: they set the class that the later rules use."],
    "up": ["Moving up one class means that the class number becomes one smaller (class 3 becomes class 2).",
           "\"Up one class\" is the class number minus 1; for example, class 4 turns into class 3.",
           "A {noun} that moves up one class gets the next smaller class number, for instance 3 instead of 4."],
    "floor": ["Class 1 is the top: a {noun} never moves above class 1.",
              "No {noun} can go higher than class 1; a {noun} of class 1 stays in class 1 whatever applies to it.",
              "There is no class above class 1, so a change that would lead above class 1 stops at class 1."],
    "moved": ["After a class change a {noun} is treated like every other {noun} of its new class.",
              "A {noun} that has moved up is an ordinary member of its new class; nothing else about it changes.",
              "Once moved, a {noun} competes inside its new class on equal terms with the {nouns} already there."],
    "wait": ["Waiting time = current time minus the time under \"{arr_col}\", in minutes (same day, 24-hour clock).",
             "The waiting time of a {noun} is counted in minutes from the time under \"{arr_col}\" to the current time; all times are today, on a 24-hour clock.",
             "To get the waiting time, subtract the \"{arr_col}\" time from the current time (in minutes; same day; 24-hour clock)."],
    "atleast": ["A wait of exactly {W} minutes counts as at least {W} minutes.",
                "\"At least {W} minutes\" includes exactly {W} minutes; {W1} minutes are not enough.",
                "The limit itself counts: {W} minutes of waiting are enough, one minute less is not."],
    "add": ["Rules 1 and 2 add up: a {noun} that meets both moves up two classes (but never above class 1).",
            "Both class changes can apply to the same {noun}; it then moves up two classes in total, stopping at class 1.",
            "The two class changes are cumulative: meeting rule 1 and rule 2 means two classes up, with class 1 as the limit."],
    "single": ["Rules 1 and 2 do not add up: a {noun} that meets both still moves up one class only.",
               "A {noun} moves up at most one class in total, even when both rule 1 and rule 2 apply to it.",
               "The two class changes are not cumulative: meeting rule 1 and rule 2 counts the same as meeting one of them."],
    "due": ["A {appt_noun} is due when its time is the current time or earlier; a later one is not due yet.",
            "Due means that the time under \"{appt_col}\" has been reached: it is equal to the current time or before it.",
            "A {appt_noun} counts as due from its own minute on, that is, when it is not later than the current time."],
    "due2": ["The {nouns} with a due {appt_noun} are level with each other under this rule (the times under \"{appt_col}\" are not compared), and so are the {nouns} without a due one.",
             "The rule only separates due from not due: how early the {appt_noun} was does not matter, and \"-\" or a later time counts as not due.",
             "Two {nouns} that are both due, or both not due (no {appt_noun}, or one that is still to come), stay level under this rule."],
    "snapshot": ["The order is worked out once, for all waiting {nouns}, at the current time; first, second and third are positions in this one order.",
                 "All positions (first, second, third) refer to a single order computed at the current time; the clock is not moved in between.",
                 "Rank every waiting {noun} once, as things stand at the current time; the position asked for is a place in that ranking."],
    "unused": ["Columns and flags that no rule mentions have no effect on the order.",
               "Whatever the list shows that no rule uses (a column, a flag) is for information only.",
               "Only what the rules name counts; any other column or flag changes nothing."],
    "distinct": ["No two {nouns} in the list have the same time under \"{arr_col}\".",
                 "The times under \"{arr_col}\" are all different, so the last rule never leaves two {nouns} level.",
                 "Every {noun} in the list has its own \"{arr_col}\" time; no two are equal."],
    "ticket": ["The ticket number is the number after the dash; no two {nouns} have the same one.",
               "Ticket numbers are the digits after the dash, compared as numbers, and they are unique.",
               "Every {noun} has its own ticket number: the number that follows the dash in the identifier."],
}
LEGEND_TEXT = {
    "ticket": ["ticket: identifier of the {noun}", "ticket: the code under which the {noun} is queued", "ticket: queue identifier of the {noun}"],
    "class": ["class: {cls}, class 1 being the most urgent", "class: the {cls} (1 = most urgent)",
              "class: {cls}; a smaller number means more urgent"],
    "arr": ["{arr_col}: {arr_legend} (today, 24-hour clock)", "{arr_col}: {arr_legend}, as HH:MM on today's 24-hour clock",
            "{arr_col}: {arr_legend}; all times are today's, 24-hour clock"],
    "flag": ["flag: marker of the {noun}, \"-\" if none", "flag: a marker noted for the {noun}; \"-\" means no marker",
             "flag: at most one marker per {noun} (\"-\" = none)"],
    "appt": ["{appt_col}: {appt_legend}, \"-\" if there is none", "{appt_col}: {appt_legend}; \"-\" means none",
             "{appt_col}: {appt_legend} (\"-\" = none)"],
    "mins": ["{mins_col}: {mins_legend}", "{mins_col}: the {mins_legend}", "{mins_col}: {mins_legend}, whole minutes"],
}
HEAD_TEXT = {
    "point": ["Service point: {point}", "Location: {point}", "Queue of: {point}"],
    "now": ["Current time: {t}", "Time now: {t}", "Clock at the moment of the decision: {t}"],
    "rules": ["Rules, applied in the order given:", "Ordering rules (apply them in this order):",
              "The order is fixed by these rules, taken in the order given:"],
    "notes": ["How to read the rules:", "Conventions:", "Notes on the rules:"],
    "queue": ["Waiting {nouns} ({n}), in no particular order:", "{n} {nouns} are waiting; the list is not sorted in any meaningful way:",
              "List of the {n} waiting {nouns} (the listing order means nothing):"],
    "legend": ["Fields of the list:", "What the list shows:", "Meaning of the fields:"],
    "ask": ["Position asked for: {ord}", "Asked: the {noun} that is {ord} in the order",
            "Wanted: the {noun} standing {ord} in the order worked out at the current time"],
}
N_PHRASINGS = 3


# ------------------------------------------------------------------------------------------------ truth
# spec = {"now": minutes, "ask": 1 | 2 | 3, "combine": "add" | "single" | None,
#         "rules": [{"kind": "wait", "minutes": W} | {"kind": "flag", "flag": name} | {"kind": "class" | "appt" | "arrival" | "mins" | "ticket"}],
#         "cases": [{"id", "num", "cls", "arr", "flag", "appt", "mins"}]  (in the order of the list in the state)}
ADJ = ("wait", "flag")


def rule_kinds(spec):
    return [r["kind"] for r in spec["rules"]]


def earliest_appt(c, after_work):
    """earliest time at which the appointment time of a case may stand: its arrival time, and in a domain where the
    appointment is the end of the work (workshop: pickup) arrival + the work time"""
    return c["arr"] + (c["mins"] if after_work else 0)


def times_ok(spec, after_work):
    """no time contradicts another: arrival before the current time, appointment not before the time it depends on"""
    return all(c["arr"] < spec["now"] and (c["appt"] is None or c["appt"] >= earliest_appt(c, after_work)) for c in spec["cases"])


def class_first_order(spec):
    """the class-first shortcut: LISTED class (adjustments, flags, appointments and the written rules ignored), earliest
    arrival, ticket"""
    return [c["id"] for c in sorted(spec["cases"], key=lambda c: (c["cls"], c["arr"], c["num"]))]


def top_class_size(spec):
    top = min(c["cls"] for c in spec["cases"])
    return sum(c["cls"] == top for c in spec["cases"])


def effective_class(spec, c):
    """class used for ordering: the listed class, one step up (number minus 1) per class-changing rule that applies
    (waiting time >= W; the flag named by the rule), one step at most unless the rules add up, never above class 1"""
    steps = 0
    for r in spec["rules"]:
        if r["kind"] == "wait" and spec["now"] - c["arr"] >= r["minutes"]:
            steps += 1
        elif r["kind"] == "flag" and c["flag"] == r["flag"]:
            steps += 1
    if spec["combine"] != "add":
        steps = min(steps, 1)
    return max(1, c["cls"] - steps)


def sort_key(spec, c):
    key = []
    for r in spec["rules"]:
        k = r["kind"]
        if k == "class":
            key.append(effective_class(spec, c))
        elif k == "appt":
            key.append(0 if (c["appt"] is not None and c["appt"] <= spec["now"]) else 1)
        elif k == "arrival":
            key.append(c["arr"])
        elif k == "mins":
            key.append(c["mins"])
        elif k == "ticket":
            key.append(c["num"])
    return tuple(key)


def is_total(spec):
    keys = [sort_key(spec, c) for c in spec["cases"]]
    if spec["rules"][-1]["kind"] == "arrival":          # the state then says that no two arrival times are equal: it must be true
        arr = [c["arr"] for c in spec["cases"]]
        if len(set(arr)) != len(arr):
            return False
    return len(set(keys)) == len(keys)


def true_order(spec):
    keys = {c["id"]: sort_key(spec, c) for c in spec["cases"]}
    assert len(set(keys.values())) == len(keys), "the written rules leave a tie"
    return sorted(keys, key=lambda i: keys[i])


def truth(spec):
    """id of the case that the written rules put at the position asked for"""
    return true_order(spec)[spec["ask"] - 1]


def precedes(spec, a, b):
    """second implementation: is a ahead of b?  The rules are walked one by one for the two cases."""
    wait = [r for r in spec["rules"] if r["kind"] == "wait"]
    flag = [r for r in spec["rules"] if r["kind"] == "flag"]

    def cls(c):
        hit_w = bool(wait) and spec["now"] - c["arr"] >= wait[0]["minutes"]
        hit_f = bool(flag) and c["flag"] == flag[0]["flag"]
        up = 0
        if hit_w or hit_f:
            up = 2 if (hit_w and hit_f and spec["combine"] == "add") else 1
        return max(1, c["cls"] - up)

    def due(c):
        return c["appt"] is not None and not c["appt"] > spec["now"]

    for r in spec["rules"]:
        k = r["kind"]
        if k in ADJ:
            continue
        if k == "class":
            x, y = cls(a), cls(b)
        elif k == "appt":
            x, y = (0 if due(a) else 1), (0 if due(b) else 1)
        elif k == "arrival":
            x, y = a["arr"], b["arr"]
        elif k == "mins":
            x, y = a["mins"], b["mins"]
        else:
            x, y = a["num"], b["num"]
        if x != y:
            return x < y
    raise AssertionError("two cases are level under every rule")


def order_by_duels(spec):
    cs = spec["cases"]
    wins = {c["id"]: sum(precedes(spec, c, d) for d in cs if d is not c) for c in cs}
    assert sorted(wins.values()) == list(range(len(cs))), "the duels do not form one strict order"
    return sorted(wins, key=lambda i: -wins[i])


def decided_by(spec):
    """the deepest ordering rule needed to separate the answer from its neighbours in the order (kind, 1-based number)"""
    order, p = true_order(spec), spec["ask"]
    by_id = {c["id"]: c for c in spec["cases"]}
    seq = [(n, r["kind"]) for n, r in enumerate(spec["rules"], 1) if r["kind"] not in ADJ]
    deepest = 0
    for q in (p - 2, p):
        if 0 <= q < len(order):
            ka, kb = sort_key(spec, by_id[order[p - 1]]), sort_key(spec, by_id[order[q]])
            deepest = max(deepest, next(i for i in range(len(ka)) if ka[i] != kb[i]))
    return {"rule": seq[deepest][0], "kind": seq[deepest][1], "depth": deepest}


# ------------------------------------------------------------------------------------------------ misreadings
def order_under(spec, skip=(), strict=False, floor=True, combine=None, any_flag=False, near=0, appt="rule", reverse=(), rules=None):
    """the order obtained by a reader who departs from the written rules in the stated way"""
    now = spec["now"]
    comb = combine or spec["combine"]
    seq = rules or [k for k in rule_kinds(spec) if k not in ADJ]
    adj = {r["kind"]: r for r in spec["rules"] if r["kind"] in ADJ}

    def cls(c):
        steps = 0
        if "wait" in adj and "wait" not in skip:
            w, lim = now - c["arr"], adj["wait"]["minutes"] - near
            steps += int(w > lim) if strict else int(w >= lim)
        if "flag" in adj and "flag" not in skip:
            steps += int(c["flag"] is not None) if any_flag else int(c["flag"] == adj["flag"]["flag"])
        if comb != "add":
            steps = min(steps, 1)
        return max(1, c["cls"] - steps) if floor else c["cls"] - steps

    def due(c):
        if c["appt"] is None:
            return 1
        if appt == "any":
            return 0
        if appt == "strict":
            return 0 if c["appt"] < now else 1
        return 0 if c["appt"] <= now else 1

    def key(c):
        out = []
        for k in seq:
            v = {"class": cls, "appt": due}[k](c) if k in ("class", "appt") else c[{"arrival": "arr", "mins": "mins", "ticket": "num"}[k]]
            out.append(-v if k in reverse else v)
        out.append(c["num"])            # a reading that drops the ticket rule still has to pick somebody
        return tuple(out)
    return [c["id"] for c in sorted(spec["cases"], key=key)]


def readings(spec):
    """name -> answer of a plausible misreading at the position asked for (may coincide with the true answer)"""
    p, kinds = spec["ask"], rule_kinds(spec)
    seq = [k for k in kinds if k not in ADJ]
    adjs = [k for k in kinds if k in ADJ]
    true = true_order(spec)
    out = collections.OrderedDict()

    def put(name, order):
        out[name] = order[p - 1]
    out["next_place"] = true[p]
    if p >= 2:
        out["previous_place"] = true[p - 2]
    if p == 3:
        out["first_place"] = true[0]
    put("earliest_arrival", order_under(spec, rules=["arrival"]))
    put("last_rule_reversed", order_under(spec, reverse=(seq[-1],)))
    put("lowest_ticket", order_under(spec, rules=["ticket"]))
    if "class" in seq:                      # readings about the class exist only where the class column is shown
        put("class_reversed", order_under(spec, reverse=("class",)))
        put("class_first_listed", class_first_order(spec))      # the class-first shortcut (listed class, then arrival)
        if adjs and seq not in (["class", "arrival", "ticket"], ["class", "arrival"]):
            put("class_then_arrival", order_under(spec, rules=["class", "arrival", "ticket"]))
        if not adjs and seq in (["class", "arrival"], ["class", "arrival", "ticket"]):
            put("class_then_ticket", order_under(spec, rules=["class", "ticket"]))     # level 1: arrival ignored, ticket instead
    if adjs:
        put("no_adjustment", order_under(spec, skip=ADJ))
        put("no_floor", order_under(spec, floor=False))
    if len(adjs) == 2:
        put("wait_rule_ignored", order_under(spec, skip=("wait",)))
        put("flag_rule_ignored", order_under(spec, skip=("flag",)))
        put("combination_swapped", order_under(spec, combine="single" if spec["combine"] == "add" else "add"))
    if "wait" in adjs:
        put("limit_not_counted", order_under(spec, strict=True))
        put("near_wait_counted", order_under(spec, near=3))
    if "flag" in adjs:
        put("any_flag_counted", order_under(spec, any_flag=True))
    if "appt" in seq:
        put("appointment_any_time", order_under(spec, appt="any"))
        put("appointment_ignored", order_under(spec, rules=[k for k in seq if k != "appt"]))
        put("appointment_before_class", order_under(spec, rules=["appt"] + [k for k in seq if k != "appt"]))
        put("appointment_minute_not_due", order_under(spec, appt="strict"))
    for k in ("arrival", "mins"):
        if k in seq and seq[-1] != k:
            put(f"{k}_reversed", order_under(spec, reverse=(k,)))
    mid = [k for k in seq if k not in ("class", "ticket")]
    if len(mid) == 2 and "class" in seq:
        sw = list(seq)
        i, j = sw.index(mid[0]), sw.index(mid[1])
        sw[i], sw[j] = sw[j], sw[i]
        put("rules_swapped", order_under(spec, rules=sw))
    return out


WEIGHT = {"no_adjustment": 6, "wait_rule_ignored": 4, "flag_rule_ignored": 4, "earliest_arrival": 4, "next_place": 4,
          "class_then_arrival": 4, "limit_not_counted": 3, "near_wait_counted": 3, "no_floor": 3, "combination_swapped": 3,
          "any_flag_counted": 3, "appointment_any_time": 3, "appointment_ignored": 3, "appointment_before_class": 2,
          "appointment_minute_not_due": 3, "last_rule_reversed": 3, "arrival_reversed": 2, "mins_reversed": 2,
          "rules_swapped": 3, "class_reversed": 2, "previous_place": 2, "first_place": 2, "lowest_ticket": 1,
          "class_first_listed": 3, "class_then_ticket": 3}


# ------------------------------------------------------------------------------------------------ queues
W_CHOICES = [20, 25, 30, 35, 40, 45, 50, 60, 75, 90]
MINS_CHOICES = [5, 10, 10, 15, 15, 20, 20, 25, 30, 40]
# level 1: the top class always has three or four of the six cases, so that the second rule has to decide among at least
# three candidates (and still among two after a planted class change)
L1_CLASS_PATTERNS = [[1, 1, 1, 2, 2, 3], [1, 1, 1, 2, 3, 3], [1, 1, 1, 1, 2, 3], [1, 1, 1, 2, 2, 2], [1, 1, 1, 1, 2, 2]]


def draw_appt(rng, now, arr, mins, after_work, rule_uses_appt):
    """appointment time of one case, drawn AFTER the times it depends on: never before the arrival (in the workshop never
    before arrival + bench time).  Offsets round the current time as before (due earlier / due on the minute / due within
    three minutes after now / later); an offset that would break the time order is drawn again, and a case that cannot be
    due gets a later time."""
    lo = earliest_appt({"arr": arr, "mins": mins}, after_work) - now
    for _ in range(16):
        if rule_uses_appt:
            off = rng.choices([rng.randint(-40, -1), 0, rng.randint(1, 3), rng.randint(4, 45)], weights=[30, 20, 20, 30])[0]
        else:
            off = rng.randint(-40, 45)
        if off >= lo:
            return now + off
    return now + rng.randint(max(lo, 4), 45)


def sample_level1(rng, cfg, now, nums):
    """level 1: six cases and two or three rules, class always rule 1 (the class column is never shown without a rule that
    uses it)"""
    n, kinds = cfg["n"], cfg["kinds"]
    classes = list(rng.choice(L1_CLASS_PATTERNS))
    rng.shuffle(classes)
    if rng.random() < 0.2:
        classes = [c + 1 for c in classes]
    if kinds[:2] == ["class", "arrival"] and cfg["kind"] == "arrival":
        # the cases of the top class arrive within ten minutes of each other, so that moving one arrival time by up to ten
        # minutes can change who is first (with the ticket as third rule two of them may arrive in the very same minute);
        # one other case arrived before all of them (the earliest arrival alone is wrong)
        top_idx = [i for i in range(n) if classes[i] == min(classes)]
        if len(kinds) == 3:
            offs = [0, rng.choice([0, 0, 1, 2]), rng.choice([0, 1, 2, 3, 4])] + [rng.randint(0, 6) for _ in top_idx[3:]]
            rng.shuffle(offs)
        else:
            offs = rng.sample(range(10), len(top_idx))
        base = rng.randint(30, 100)
        waits = [None] * n
        for i, off in zip(top_idx, offs):
            waits[i] = base - off
        rest = [i for i in range(n) if waits[i] is None]
        earlier = rng.choice(rest)
        waits[earlier] = base + rng.randint(3, 25)
        taken = [w for w in waits if w is not None]
        free = [w for w in range(4, 110) if w not in taken]
        others = [i for i in rest if i != earlier]
        for i, w in zip(others, rng.sample(free, len(others))):
            waits[i] = w
    else:
        waits = rng.sample(range(4, 110), n)
    cases = []
    for i in range(n):
        flag = rng.choice(cfg["markers"]) if rng.random() < 0.3 else None
        cases.append({"id": f"{cfg['prefix']}-{nums[i]}", "num": nums[i], "cls": classes[i], "arr": now - waits[i],
                      "flag": flag, "appt": None, "mins": None})
    return {"now": now, "ask": 1, "combine": None, "rules": [{"kind": k} for k in kinds], "cases": cases}


def sample_base(rng, level, cfg):
    """a random queue for the configuration cfg (rule kinds, limit W, flag names, size, identifier format)"""
    n, kinds = cfg["n"], cfg["kinds"]
    now = rng.randrange(9 * 60, 17 * 60 + 40)
    start = rng.randrange(10 ** (cfg["digits"] - 1), 10 ** cfg["digits"] - 99)
    nums = [start + x for x in rng.sample(range(99), n)]
    if level == 1:
        return sample_level1(rng, cfg, now, nums)
    cases = []
    W = cfg["W"]
    pool = rng.sample(range(5, 125), max(3, n - 3))
    for i in range(n):
        cls = rng.choices([1, 2, 3, 4], weights=[22, 38, 28, 12])[0]
        if "wait" in kinds:
            wait = W + rng.choice([-3, -2, -1, -1, 0, 0, 0, 1, 2, 3]) if rng.random() < 0.5 else rng.randint(4, 2 * W + 15)
        else:
            wait = rng.choice(pool)
        r = rng.random()
        if "flag" in kinds:
            flag = cfg["flag"] if r < 0.30 else (rng.choice(cfg["decoys"]) if r < 0.45 else None)
        else:
            flag = rng.choice(cfg["markers"]) if r < 0.3 else None
        mins = rng.choice(MINS_CHOICES)
        appt = draw_appt(rng, now, now - wait, mins, cfg["after_work"], "appt" in kinds) if rng.random() < 0.45 else None
        cases.append({"id": f"{cfg['prefix']}-{nums[i]}", "num": nums[i], "cls": cls, "arr": now - wait, "flag": flag,
                      "appt": appt, "mins": mins})
    rules = []
    for k in kinds:
        rules.append({"kind": k, "minutes": W} if k == "wait" else ({"kind": k, "flag": cfg["flag"]} if k == "flag" else {"kind": k}))
    return {"now": now, "ask": cfg["ask"], "combine": cfg["combine"], "rules": rules, "cases": cases}


def apply_change(spec, ch):
    """the same specification with ONE element replaced (ch = None: an unchanged copy)"""
    s = {"now": spec["now"], "ask": spec["ask"], "combine": spec["combine"], "rules": spec["rules"],
         "cases": [dict(c) for c in spec["cases"]]}
    if ch is None:
        return s
    if ch["element"] == "now":
        s["now"] = ch["value"]
    elif ch["element"] == "ask":
        s["ask"] = ch["value"]
    else:
        c = next(c for c in s["cases"] if c["id"] == ch["case"])
        c[{"arrival": "arr", "flag": "flag", "class": "cls"}[ch["element"]]] = ch["value"]
    return s


def candidate_changes(rng, spec, kind, cfg):
    out, now = [], spec["now"]
    if kind == "clock":
        lo = max(c["arr"] for c in spec["cases"]) + 1
        out = [{"element": "now", "value": t} for t in range(max(lo, now - 15), now + 16) if t != now]
    elif kind == "position":
        out = [{"element": "ask", "value": p} for p in (1, 2, 3) if p != spec["ask"]]
    elif kind == "arrival":
        for c in spec["cases"]:
            for d in range(-10, 11):
                moved = dict(c, arr=c["arr"] + d)
                if d and moved["arr"] <= now - 1 and (c["appt"] is None or c["appt"] >= earliest_appt(moved, cfg["after_work"])):
                    out.append({"element": "arrival", "case": c["id"], "value": moved["arr"]})
    elif kind == "flag":
        for c in spec["cases"]:
            v = rng.choice([None] + cfg["decoys"]) if c["flag"] == cfg["flag"] else cfg["flag"]
            out.append({"element": "flag", "case": c["id"], "value": v})
    elif kind == "class":
        for c in spec["cases"]:
            out += [{"element": "class", "case": c["id"], "value": v} for v in (c["cls"] - 1, c["cls"] + 1) if 1 <= v <= 4]
    return out


def member_info(spec, change):
    gold, rd = truth(spec), readings(spec)
    return {"spec": spec, "change": change, "gold": gold, "readings": rd, "wrong": [k for k, v in rd.items() if v != gold]}


def group_ok(members, level, strict):
    """hard conditions on a group: the sloppy readings must fail in most members, and the class-first shortcut (listed
    class, then arrival) must not give the key more often than chance"""
    size = len(members)
    cnt = lambda name: sum(name in m["wrong"] for m in members)
    seq = [k for k in rule_kinds(members[0]["spec"]) if k not in ADJ]
    if level == 1:
        # class is rule 1: the second rule must always be needed (the top class has at least two cases), the other tie-break
        # must never give the key ("class first, ignore the second rule"), and ignoring the class must fail in most members
        if any(top_class_size(m["spec"]) < 2 for m in members):
            return False
        other, ignore_class = ("class_first_listed", "lowest_ticket") if seq == ["class", "ticket"] else ("class_then_ticket", "earliest_arrival")
        if seq == ["class", "arrival", "ticket"] and cnt("last_rule_reversed") < 1:      # the ticket must decide in one member at least
            return False
        return cnt(other) == size and cnt(ignore_class) >= size - 1
    if cnt("no_adjustment") < (size if strict else size - 1) or cnt("earliest_arrival") < size - 1:
        return False
    if level == 3 and (cnt("wait_rule_ignored") < 1 or cnt("flag_rule_ignored") < 1):
        return False
    return size - cnt("class_first_listed") <= 1          # the class-first shortcut is the key in at most one member


def choose_options(members):
    """the five candidates of a group: the answers of its members, then the cases that most misreadings point to; a case
    that stands ahead of the answer of a member asked for the second or third place is avoided where possible, so that
    ranking only the five options does not give the answer more often than taking the best option"""
    spec0 = members[0]["spec"]
    ahead_of = [set(true_order(m["spec"])[:m["spec"]["ask"] - 1]) for m in members]
    rank = {i: r for r, i in enumerate(true_order(spec0))}
    chosen = []
    for m in members:
        assert m["gold"] not in chosen
        chosen.append(m["gold"])
    while len(chosen) < 5:
        best = None
        for c in spec0["cases"]:
            x = c["id"]
            if x in chosen:
                continue
            cover, gain = 0, 0
            for m in members:
                names = [name for name, ans in m["readings"].items() if ans == x and ans != m["gold"]]
                cover += bool(names)
                gain += sum(WEIGHT[name] for name in names)
            score = (sum(x in a for a in ahead_of), -cover, -gain, abs(rank[x] - (spec0["ask"] - 1)), rank[x])
            if best is None or score < best[0]:
                best = (score, x)
        chosen.append(best[1])
    return chosen


def option_roles(member, options, golds):
    roles = collections.OrderedDict()
    for x in options:
        if x == member["gold"]:
            roles[x] = ["answer"]
            continue
        r = [name for name, ans in member["readings"].items() if ans == x]
        if x in golds:
            r.append("answer_of_group_member")
        roles[x] = r or ["filler"]
    return roles


def find_group(rng, level, kind, cfg, size, strict, tries=400):
    """a base queue and size - 1 one-element variants of it with different answers that pass group_ok"""
    for _ in range(tries):
        base = sample_base(rng, level, cfg)
        assert times_ok(base, cfg["after_work"]), "a time of the base queue contradicts another"
        if not is_total(base):
            continue
        b = member_info(base, None)
        cands = []
        for ch in candidate_changes(rng, base, kind, cfg):
            s = apply_change(base, ch)
            assert times_ok(s, cfg["after_work"]), ("a planted change breaks the time order", ch)
            if is_total(s) and truth(s) != b["gold"]:
                cands.append(member_info(s, ch))
        rng.shuffle(cands)
        if size == 2:
            combos = [(x,) for x in cands]
        else:
            combos = [(x, y) for i, x in enumerate(cands) for y in cands[i + 1:] if x["gold"] != y["gold"]]
        for combo in combos[:60]:
            members = [b] + list(combo)
            if group_ok(members, level, strict):
                return members
    return None


# ------------------------------------------------------------------------------------------------ plan
# rule sets per level and kind of planted difference (a rule set in which the planted element cannot change the answer,
# or in which the sloppy readings cannot all be made wrong, is left out; see the README)
L1_CONFIGS = {"arrival": [("class", "arrival"), ("class", "arrival", "ticket")], "class": [("class", "arrival"), ("class", "ticket")]}
L2_CONFIGS = {"clock": [("wait", "appt", 1), ("wait", "mins", 1), ("wait", "appt", 2), ("wait", "mins", 2), ("wait", "arrival", 2),
                        ("flag", "appt", 2)],
              "flag": [("flag", "appt", 1), ("flag", "arrival", 1), ("flag", "mins", 1), ("flag", "appt", 2), ("flag", "arrival", 2),
                       ("flag", "mins", 2)],
              "arrival": [("wait", "appt", 1), ("wait", "arrival", 1), ("wait", "mins", 1), ("wait", "appt", 2), ("wait", "arrival", 2),
                          ("wait", "mins", 2), ("flag", "arrival", 2)]}
L3_MIDS = [("appt",), ("arrival",), ("mins",), ("appt", "arrival"), ("appt", "mins"), ("arrival", "mins"), ("mins", "arrival")]
OPTION_TEXT = ["{noun} {id}", "the {noun} with ticket {id}", "{id} ({noun})"]


def configs_for(level, kind):
    if level == 1:
        return [{"kinds": list(k), "ask": 1, "combine": None} for k in L1_CONFIGS[kind]]
    if level == 2:
        return [{"kinds": [a, "class", x, "ticket"], "ask": p, "combine": None} for a, x, p in L2_CONFIGS[kind]]
    return [{"kinds": ["wait", "flag", "class"] + list(m) + ["ticket"], "ask": p, "combine": c}
            for m in L3_MIDS for p in (1, 2, 3) for c in ("add", "single")]


def place_sets(rng):
    """ordered places 0-4 for the members of the 66 triples and of the pair of one level; every place is used 40 times"""
    assert TRIPLES_PER_LEVEL == 66 and PAIRS_PER_LEVEL == 1
    subs = [list(s) for _ in range(6) for s in itertools.combinations(range(5), 3)]
    subs += [[i, (i + 1) % 5, (i + 2) % 5] for i in range(5)]
    extra = sorted(rng.sample(range(5), 3))
    subs.append(extra)
    pair = [i for i in range(5) if i not in extra]
    rng.shuffle(subs)
    for s in subs + [pair]:
        rng.shuffle(s)
    cnt = collections.Counter(x for s in subs + [pair] for x in s)
    assert all(cnt[i] == 40 for i in range(5)), cnt
    return subs, pair


def make_plan():
    rng = rng_for("plan")
    plan = []
    for level in (1, 2, 3):
        kinds = KINDS[level]
        tk = [kinds[i % len(kinds)] for i in range(TRIPLES_PER_LEVEL)]
        places, pair_places = place_sets(rng)            # gold option positions
        groups = [{"kind": k, "size": 3, "places": p} for k, p in zip(tk, places)]
        groups.append({"kind": kinds[TRIPLES_PER_LEVEL % len(kinds)], "size": 2, "places": pair_places})
        rng.shuffle(groups)
        dom_seq = []
        while len(dom_seq) < len(groups):
            d = list(DOMAINS)
            rng.shuffle(d)
            dom_seq += d
        cfg_lists = {}
        for k in kinds:
            cfg_lists[k] = configs_for(level, k)
            rng.shuffle(cfg_lists[k])
        used = collections.Counter()
        for i, g in enumerate(groups):
            sizes = LEVEL_SIZES[level]
            g.update(level=level, index=i, domain=dom_seq[i], n=sizes[i % len(sizes)], strict=(level >= 2 and i % 3 != 0),
                     configs=cfg_lists[g["kind"]], cfg_start=used[g["kind"]] % len(cfg_lists[g["kind"]]))
            used[g["kind"]] += 1
            plan.append(g)
    return plan


def build_group(gp):
    """the members of one group; when a rule set gives no valid group for this draw, the next rule set of the kind is tried"""
    dom, level, configs = DOMAINS[gp["domain"]], gp["level"], gp["configs"]
    for alt in range(len(configs)):
        conf = configs[(gp["cfg_start"] + alt) % len(configs)]
        rng = rng_for("group", level, gp["index"], alt)
        flag = rng.choice(dom["flags"])
        cfg = {"n": gp["n"], "kinds": conf["kinds"], "digits": rng.choice([3, 4]), "prefix": rng.choice(dom["prefix"]),
               "W": rng.choice(W_CHOICES), "flag": flag, "decoys": dom["decoys"] + [f for f in dom["flags"] if f != flag],
               # level 1 has no rule about flags: its markers are the neutral ones (an ignored "frail" or "outage" would read oddly)
               "markers": dom["decoys"] if level == 1 else dom["flags"] + dom["decoys"],
               "ask": conf["ask"], "combine": conf["combine"], "kind": gp["kind"], "after_work": dom.get("appt_after_work", False)}
        members = find_group(rng, level, gp["kind"], cfg, gp["size"], gp["strict"], tries=120)
        if members:
            return members, alt, rng
    raise RuntimeError(f"no group for level {level}, group {gp['index']}")


def arrange(members, gp, rng, row_count):
    """option order (the gold of member i at place i of the group) and listing order of the queue: the gold cases take the
    rows used least so far by gold cases of queues of the same level and size (ties drawn), the other cases are shuffled;
    the listing is drawn again while it coincides with an order a reader could exploit"""
    golds = [m["gold"] for m in members]
    options = choose_options(members)
    order = [None] * 5
    for g, p in zip(golds, gp["places"]):
        order[p] = g
    rest = [x for x in options if x not in golds]
    rng.shuffle(rest)
    free = [i for i in range(5) if order[i] is None]
    for i, x in zip(free, rest):
        order[i] = x
    n, by = gp["n"], {c["id"]: c for c in members[0]["spec"]["cases"]}
    forbidden = [true_order(m["spec"]) for m in members]
    forbidden += [sorted(by, key=lambda i: (by[i][f], by[i]["num"])) for f in ("arr", "num", "cls")]
    for attempt in range(400):
        rows = [None] * n
        for g in golds:
            free = [r for r in range(n) if rows[r] is None]
            low = min(row_count[r] for r in free) if attempt < 100 else 0
            rows[rng.choice([r for r in free if row_count[r] <= low or attempt >= 100])] = g
        others = [i for i in by if i not in golds]
        rng.shuffle(others)
        it = iter(others)
        rows = [r if r is not None else next(it) for r in rows]
        if all(rows != f and rows != f[::-1] for f in forbidden):
            break
    else:
        raise RuntimeError("no neutral listing order")
    for g in golds:
        row_count[rows.index(g)] += 1
    for m in members:
        cs = {c["id"]: c for c in m["spec"]["cases"]}
        m["spec"]["cases"] = [cs[i] for i in rows]
    return order, rows


# ------------------------------------------------------------------------------------------------ rendering
def slots_of(dom):
    keys = ("noun", "nouns", "cls", "arr_col", "arr_noun", "arr_verb", "arr_legend", "appt_col", "appt_noun", "appt_legend",
            "mins_col", "mins_noun", "mins_legend")
    return {k: dom[k] for k in keys}


def draw_look(rng, dom):
    phr = {}
    for tag, table in (("rule", RULE_TEXT), ("note", NOTE_TEXT), ("legend", LEGEND_TEXT), ("head", HEAD_TEXT)):
        for k in table:
            phr[f"{tag}_{k}"] = rng.randrange(N_PHRASINGS)
    return {"phr": phr, "layout": rng.randrange(3), "arrangement": rng.randrange(2), "option": rng.randrange(len(OPTION_TEXT)),
            "point": rng.choice(dom["points"]).format(N=place_name(rng), k=rng.randint(1, 9))}


def note_kinds(spec, level):
    kinds = rule_kinds(spec)
    adj = [k for k in kinds if k in ADJ]
    out = ["order"]
    if adj:
        out += ["classword1" if len(adj) == 1 else "classword2", "up", "floor", "moved"]
    if "wait" in kinds:
        out += ["wait", "atleast"]
    if len(adj) == 2:
        out.append(spec["combine"])
    if "appt" in kinds:
        out += ["due", "due2"]
    if level >= 2:
        out.append("snapshot")
    out.append("unused")
    if "ticket" in kinds:
        out.append("ticket")
    elif kinds[-1] == "arrival":
        assert len({c["arr"] for c in spec["cases"]}) == len(spec["cases"]), "the state says no two arrival times are equal"
        out.append("distinct")
    return out


def table_lines(spec, dom, level, layout):
    cols = ["ticket", "class", dom["arr_col"], "flag"] + ([dom["appt_col"], dom["mins_col"]] if level >= 2 else [])
    rows = []
    for c in spec["cases"]:
        v = [c["id"], str(c["cls"]), hhmm(c["arr"]), c["flag"] or "-"]
        if level >= 2:
            v += [hhmm(c["appt"]) if c["appt"] is not None else "-", str(c["mins"])]
        rows.append(v)
    if layout == 0:
        return [" | ".join(cols)] + [" | ".join(v) for v in rows]
    if layout == 1:
        return [f"{v[0]}: " + "; ".join(f"{k} {x}" for k, x in zip(cols[1:], v[1:])) for v in rows]
    return [",".join(cols)] + [",".join(v) for v in rows]


def render(spec, look, dom, level):
    S, P = slots_of(dom), look["phr"]
    W = next((r["minutes"] for r in spec["rules"] if r["kind"] == "wait"), 0)
    head = [HEAD_TEXT["point"][P["head_point"]].format(point=look["point"]), HEAD_TEXT["now"][P["head_now"]].format(t=hhmm(spec["now"]))]
    rules = [HEAD_TEXT["rules"][P["head_rules"]]]
    for n, r in enumerate(spec["rules"], 1):
        rules.append(f"{n}. " + RULE_TEXT[r["kind"]][P["rule_" + r["kind"]]].format(W=r.get("minutes"), F=r.get("flag"), **S))
    notes = [HEAD_TEXT["notes"][P["head_notes"]]]
    notes += ["- " + NOTE_TEXT[k][P["note_" + k]].format(W=W, W1=W - 1, **S) for k in note_kinds(spec, level)]
    queue = [HEAD_TEXT["queue"][P["head_queue"]].format(n=len(spec["cases"]), **S)] + table_lines(spec, dom, level, look["layout"])
    legend = [HEAD_TEXT["legend"][P["head_legend"]]]
    legend += ["- " + LEGEND_TEXT[k][P["legend_" + k]].format(**S)
               for k in ["ticket", "class", "arr", "flag"] + (["appt", "mins"] if level >= 2 else [])]
    ask = [HEAD_TEXT["ask"][P["head_ask"]].format(ord=ORDINAL[spec["ask"]], **S)]
    blocks = [head, rules, notes, queue, legend, ask] if look["arrangement"] == 0 else [head, queue, legend, rules, notes, ask]
    return "\n\n".join("\n".join(b) for b in blocks)


def parse_queue(state, dom):
    """the queue as a reader sees it: the cases parsed back from the rendered text (all three layouts) and the current time"""
    lines = state.split("\n")

    def clock(x):
        return None if x == "-" else int(x[:2]) * 60 + int(x[3:5])

    def case(cells):
        c = {"id": cells["ticket"], "num": int(cells["ticket"].split("-")[1]),
             "cls": int(cells["class"]),
             "arr": clock(cells[dom["arr_col"]]), "flag": None if cells["flag"] == "-" else cells["flag"], "appt": None, "mins": None}
        if dom["appt_col"] in cells:
            c["appt"], c["mins"] = clock(cells[dom["appt_col"]]), int(cells[dom["mins_col"]])
        return c

    now = clock(lines[1].split(" ")[-1])             # the second line of the state is the current time
    for i, ln in enumerate(lines):
        if ln.startswith("ticket | ") or ln.startswith("ticket,"):
            sep = " | " if ln.startswith("ticket | ") else ","
            cols, cases = ln.split(sep), []
            for row in lines[i + 1:]:
                if not row.strip():
                    break
                cases.append(case(dict(zip(cols, row.split(sep)))))
            return now, cases
    cases = []
    for ln in lines:                                  # one line per case:  ID: class 1; column 09:09; flag -; ...
        m = re.match(r"^([A-Z]-\d+): (.*)$", ln)
        if m:
            cells = {"ticket": m.group(1)}
            for part in m.group(2).split("; "):
                k, v = part.split(" ", 1)
                cells[k] = v
            cases.append(case(cells))
    return now, cases


def diff_elements(a, b):
    out = [k for k in ("now", "ask", "combine") if a[k] != b[k]]
    if a["rules"] != b["rules"]:
        out.append("rules")
    ca, cb = {c["id"]: c for c in a["cases"]}, {c["id"]: c for c in b["cases"]}
    assert set(ca) == set(cb)
    for i in ca:
        out += [f"{i}.{f}" for f in ("num", "cls", "arr", "flag", "appt", "mins") if ca[i][f] != cb[i][f]]
    return out


# ------------------------------------------------------------------------------------------------ main
CHANGE_FIELD = {"clock": "now", "position": "ask", "arrival": "arr", "flag": "flag", "class": "cls"}
LAYOUTS = ["table with | separators", "one line per case (field value; ...)", "comma-separated table"]
TRACKED = ["no_adjustment", "earliest_arrival", "class_first_listed", "class_then_ticket", "class_then_arrival", "wait_rule_ignored",
           "flag_rule_ignored", "combination_swapped", "limit_not_counted", "appointment_minute_not_due", "appointment_ignored",
           "last_rule_reversed", "lowest_ticket"]


def kendall(a, b):
    pos = {x: i for i, x in enumerate(b)}
    s = [pos[x] for x in a]
    n = len(s)
    c = sum((s[i] < s[j]) - (s[i] > s[j]) for i in range(n) for j in range(i + 1, n))
    return c / (n * (n - 1) / 2)


def main():
    if SEALED and not ENV_OUT:
        sys.stderr.write("BENCH_SEED is accepted only together with BENCH_OUT (the published set is never overwritten); nothing written\n")
        sys.exit(2)
    plan = make_plan()
    built, fallbacks, len_gaps, taus = [], 0, [], collections.defaultdict(list)
    row_counts = collections.defaultdict(collections.Counter)
    for g_no, gp in enumerate(plan, 1):
        level, dom = gp["level"], DOMAINS[gp["domain"]]
        after_work = dom.get("appt_after_work", False)
        members, alt, rng = build_group(gp)
        fallbacks += alt > 0
        order, rows = arrange(members, gp, rng, row_counts[(level, gp["n"])])
        look = draw_look(rng_for("look", level, gp["index"]), dom)
        golds = [m["gold"] for m in members]
        assert len(set(golds)) == len(golds) == gp["size"] and len(set(order)) == 5 and set(golds) <= set(order)
        assert set(order) <= {c["id"] for c in members[0]["spec"]["cases"]}
        gid = f"{ID_PREFIX}:g{g_no:04d}"
        texts = []
        for v, m in enumerate(members):
            spec = m["spec"]
            assert is_total(spec) and truth(spec) == m["gold"] == order_by_duels(spec)[spec["ask"] - 1]
            assert true_order(spec) == order_by_duels(spec)
            if v:                                          # ONE planted difference against the base member
                d = diff_elements(members[0]["spec"], spec)
                assert len(d) == 1 and d[0].split(".")[-1] == CHANGE_FIELD[gp["kind"]], (d, gp["kind"])
            assert order.index(m["gold"]) == gp["places"][v]
            text = render(spec, look, dom, level)
            texts.append(text)
            now_t, parsed = parse_queue(text, dom)               # second check, from the rendered text: what a reader sees
            assert parsed == spec["cases"] and now_t == spec["now"], "the rendered queue does not read back as the specification"
            assert times_ok({"now": now_t, "cases": parsed}, after_work), "a time of the rendered queue contradicts another"
            taus[level].append(kendall(rows, true_order(spec)))
            meta = {"source_id": None, "seed": SEED, "level": level, "domain": gp["domain"], "deviation": gp["kind"], "variant": v,
                    "change": m["change"], "order": list(order), "ask": spec["ask"], "position_asked": ORDINAL[spec["ask"]],
                    "rules": rule_kinds(spec), "combine": spec["combine"], "n_cases": gp["n"], "gold_place": order.index(m["gold"]),
                    "gold_row": rows.index(m["gold"]), "true_order": true_order(spec), "decided_by": decided_by(spec),
                    "option_roles": option_roles(m, order, golds), "readings": dict(m["readings"]),
                    "layout": LAYOUTS[look["layout"]], "block_order": ["rules first", "queue first"][look["arrangement"]],
                    "strict_group": gp["strict"], "rule_set_fallback": alt,
                    "appointment_not_before": None if level == 1 else ("arrival + " + dom["mins_noun"] if after_work else "arrival"),
                    "spec": spec}
            crit = collections.OrderedDict((k, OPTION_TEXT[look["option"]].format(noun=dom["noun"], id=k)) for k in order)
            built.append({"state": text, "questions": {"q": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": crit}},
                          "gold": m["gold"], "soft": None, "group": gid, "meta": meta})
        assert len({t.count("\n") for t in texts}) == 1, "members of a group must have the same number of lines"
        len_gaps.append(max(len(t) for t in texts) - min(len(t) for t in texts))
    rng_for("order").shuffle(built)
    rows_out = []
    for n, it in enumerate(built, 1):
        it["meta"]["source_id"] = f"{n:05d}" if not SEALED else f"s{SEED}:{n:05d}"
        rows_out.append(dict([("id", f"{ID_PREFIX}:{n:05d}")] + list(it.items())))
    stats = check_balance(rows_out)
    stats.update(fallbacks=fallbacks, len_gap_max=max(len_gaps), len_gap_mean=sum(len_gaps) / len(len_gaps),
                 tau={k: sum(v) / len(v) for k, v in taus.items()})
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "items.jsonl"), "w", encoding="utf-8") as f:
        for r in rows_out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(OUT_DIR, "task.json"), "w", encoding="utf-8") as f:
        json.dump(task_json(rows_out, stats), f, indent=1, ensure_ascii=False)
        f.write("\n")
    with open(os.path.join(OUT_DIR, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme(rows_out, stats))
    print_stats(stats)


def check_balance(rows):
    st = {"n": len(rows)}
    assert len(rows) == 600 and len({r["state"] for r in rows}) == 600, "duplicate state"
    assert len({r["questions"]["q"]["instructions"] for r in rows}) == 1
    lv = collections.Counter(r["meta"]["level"] for r in rows)
    assert all(lv[k] == 200 for k in (1, 2, 3)), lv
    st["place"] = {k: [sum(1 for r in rows if r["meta"]["level"] == k and r["meta"]["gold_place"] == p) for p in range(5)] for k in (1, 2, 3)}
    st["bin"] = {k: [sum(1 for r in rows if r["meta"]["level"] == k and 5 * r["meta"]["gold_row"] // r["meta"]["n_cases"] == b)
                     for b in range(5)] for k in (1, 2, 3)}
    for k in (1, 2, 3):
        assert st["place"][k] == [40] * 5, st["place"][k]
    st["row_spread"] = {}
    for k in (1, 2, 3):
        for n in LEVEL_SIZES[k]:
            c = collections.Counter(r["meta"]["gold_row"] for r in rows if r["meta"]["level"] == k and r["meta"]["n_cases"] == n)
            st["row_spread"][f"L{k} n={n}"] = [c[i] for i in range(n)]
            assert max(c[i] for i in range(n)) - min(c[i] for i in range(n)) <= 2, (k, n, c)
    st["dev"] = {k: dict(collections.Counter(r["meta"]["deviation"] for r in rows if r["meta"]["level"] == k)) for k in (1, 2, 3)}
    for k in (1, 2, 3):
        c = [st["dev"][k].get(x, 0) for x in KINDS[k]]
        assert max(c) - min(c) <= 3, c
    gs = collections.Counter(r["group"] for r in rows)
    st["groups"] = len(gs)
    assert sorted(collections.Counter(gs.values()).items()) == [(2, 3), (3, 198)]
    st["chars"] = {k: sorted(len(r["state"]) for r in rows if r["meta"]["level"] == k) for k in (1, 2, 3)}
    st["wrong"] = {}
    for k in (1, 2, 3):
        rs = [r for r in rows if r["meta"]["level"] == k]
        st["wrong"][k] = {}
        for name in TRACKED:
            have = [r for r in rs if name in r["meta"]["readings"]]
            if have:
                st["wrong"][k][name] = (sum(r["meta"]["readings"][name] != r["gold"] for r in have), len(have))
    for k in (2, 3):
        w, n = st["wrong"][k]["no_adjustment"]
        assert w >= 0.8 * n, ("ignoring the adjustments must give a wrong answer in most items", k, w, n)
    st["depth"] = {k: dict(sorted(collections.Counter(r["meta"]["decided_by"]["kind"] for r in rows if r["meta"]["level"] == k).items()))
                   for k in (1, 2, 3)}
    st["roles"] = collections.Counter()
    st["filler"] = {}
    for k in (1, 2, 3):
        f = 0
        for r in rows:
            if r["meta"]["level"] != k:
                continue
            for x, ro in r["meta"]["option_roles"].items():
                if x != r["gold"]:
                    st["roles"].update(ro)
                    f += ro == ["filler"]
        st["filler"][k] = f / 200
    st["rulesets"] = {k: dict(sorted(collections.Counter("-".join(r["meta"]["rules"]) for r in rows if r["meta"]["level"] == k).items()))
                      for k in (1, 2, 3)}
    st["asks"] = {k: dict(sorted(collections.Counter(r["meta"]["ask"] for r in rows if r["meta"]["level"] == k).items())) for k in (1, 2, 3)}
    st["domains"] = dict(sorted(collections.Counter(r["meta"]["domain"] for r in rows).items()))
    st["ahead"] = collections.Counter()
    for r in rows:
        m = r["meta"]
        if m["ask"] >= 2:
            k = sum(a in r["questions"]["q"]["criteria"] for a in m["true_order"][:m["ask"] - 1])
            st["ahead"][f"L{m['level']} {ORDINAL[m['ask']]}: {k} of the cases ahead listed"] += 1
    st["ahead"] = dict(sorted(st["ahead"].items()))
    # ---- the class-first shortcut (listed class, then arrival; adjustments, flags, appointments, written rules ignored)
    st["cf"] = {}
    for k in (1, 2, 3):
        rs = [r for r in rows if r["meta"]["level"] == k]
        assert all("class" in r["meta"]["rules"] for r in rs) and all(r["meta"]["rules"][0] == "class" for r in rs if k == 1)
        hit = lambda r: r["meta"]["readings"]["class_first_listed"] == r["gold"]
        d = {"items": len(rs), "hits": sum(hit(r) for r in rs),
             "in_options": sum(r["meta"]["readings"]["class_first_listed"] in r["questions"]["q"]["criteria"] for r in rs)}
        # level 1, rules class, arrival (, ticket): the class-first reading IS the written rule, its hits are not a shortcut
        written = [r for r in rs if r["meta"]["rules"][:2] == ["class", "arrival"] and k == 1]
        d["written"] = len(written)
        d["shortcut_hits"] = d["hits"] - sum(hit(r) for r in written)
        if k == 1:
            tops = [top_class_size(r["meta"]["spec"]) for r in rs]
            other = lambda r: r["meta"]["readings"]["class_first_listed" if r["meta"]["rules"] == ["class", "ticket"] else "class_then_ticket"]
            first_listed = lambda r: next(c["id"] for c in r["meta"]["spec"]["cases"] if c["cls"] == min(x["cls"] for x in r["meta"]["spec"]["cases"]))
            d.update(top_sizes=dict(sorted(collections.Counter(tops).items())), class_alone_decides=sum(t == 1 for t in tops),
                     other_tiebreak_hits=sum(other(r) == r["gold"] for r in rs), random_pick=sum(1 / t for t in tops) / len(rs),
                     first_listed_hits=sum(first_listed(r) == r["gold"] for r in rs))
            assert d["class_alone_decides"] == 0 and d["other_tiebreak_hits"] == 0 and d["shortcut_hits"] == 0, d
        else:
            assert d["hits"] <= 0.25 * d["items"], ("the class-first shortcut gives the key too often", k, d)
        st["cf"][k] = d
    # ---- the time order, read back from the finished items
    st["times"] = {}
    for k in (2, 3):
        gaps, gaps_bench = [], []
        for r in rows:
            if r["meta"]["level"] != k:
                continue
            aw = DOMAINS[r["meta"]["domain"]].get("appt_after_work", False)
            for c in r["meta"]["spec"]["cases"]:
                if c["appt"] is not None:
                    (gaps_bench if aw else gaps).append(c["appt"] - earliest_appt(c, aw))
        assert min(gaps + gaps_bench) >= 0, "an appointment time is before the time it depends on"
        st["times"][k] = {"rows": len(gaps) + len(gaps_bench), "min_gap": min(gaps + gaps_bench), "equal": sum(g == 0 for g in gaps + gaps_bench),
                          "workshop_rows": len(gaps_bench)}
    return st


def print_stats(st):
    for k in (1, 2, 3):
        ch = st["chars"][k]
        print(f"level {k}: gold place {st['place'][k]} gold row fifth {st['bin'][k]} rows {[v for a, v in st['row_spread'].items() if a.startswith(f'L{k} ')]} deviation {st['dev'][k]} "
              f"chars {ch[0]}/{ch[100]}/{ch[-1]} asks {st['asks'][k]} filler/item {st['filler'][k]:.2f} tau {st['tau'][k]:+.3f}")
        print("    wrong share:", {n: f"{w}/{t}" for n, (w, t) in st["wrong"][k].items()})
        print("    decided by:", st["depth"][k])
    for k in (1, 2, 3):
        d = st["cf"][k]
        print(f"class-first reading level {k}: key in {d['hits']}/{d['items']} items ({d['hits'] - d['shortcut_hits']} of the hits are the written rule)"
              + (f"; top class sizes {d['top_sizes']}, class alone decides {d['class_alone_decides']}, other tie-break gives the key "
                 f"{d['other_tiebreak_hits']}, random pick in the top class {d['random_pick']:.3f}, first listed of the top class "
                 f"{d['first_listed_hits']}" if k == 1 else ""))
    for k in (2, 3):
        t = st["times"][k]
        print(f"time order level {k}: {t['rows']} appointment times ({t['workshop_rows']} in the workshop), smallest gap to the time it depends on {t['min_gap']} min, equal in {t['equal']}")
    print("groups", st["groups"], "fallbacks", st["fallbacks"], "length gap in group max/mean", st["len_gap_max"], f"{st['len_gap_mean']:.1f}")
    print("domains", st["domains"])


READING_DESC = collections.OrderedDict([
    ("no_adjustment", "listed class used, every class-changing rule ignored"),
    ("wait_rule_ignored", "waiting-time rule ignored (level 3)"), ("flag_rule_ignored", "flag rule ignored (level 3)"),
    ("combination_swapped", "the two class changes combined the other way: added up instead of one step, or the reverse (level 3)"),
    ("limit_not_counted", "a wait of exactly W minutes not counted"), ("near_wait_counted", "waits up to 3 minutes short of W counted"),
    ("no_floor", "class allowed to go above class 1"), ("any_flag_counted", "any flag counted, not only the one the rule names"),
    ("earliest_arrival", "earliest arrival overall, rules ignored"), ("lowest_ticket", "lowest ticket number overall"),
    ("class_first_listed", "the class-first shortcut: the LISTED class, then the earliest arrival (adjustments, flags, appointments and the written rules ignored); at level 1 with class then ticket as the rules, the other tie-break"),
    ("class_then_ticket", "level 1, class then arrival written: the other tie-break (class, then lowest ticket)"),
    ("class_then_arrival", "adjusted class, then arrival, then ticket: the tie-break rules actually written ignored"),
    ("class_reversed", "class numbers read the wrong way round"), ("last_rule_reversed", "the last rule (the tie-break) read in reverse"),
    ("arrival_reversed", "arrival rule read in reverse"), ("mins_reversed", "duration rule read in reverse"),
    ("rules_swapped", "the two rules between class and ticket applied in swapped order"),
    ("appointment_any_time", "every case with an appointment counted as due"), ("appointment_ignored", "appointment rule ignored"),
    ("appointment_before_class", "appointment rule applied before the class rule"),
    ("appointment_minute_not_due", "an appointment at exactly the current time counted as not due"),
    ("next_place", "the case one place after the right one"), ("previous_place", "the case one place before the right one"),
    ("first_place", "the first case of the order when the third is asked"),
    ("answer_of_group_member", "the right answer of another member of the group (same queue, one element changed)"),
    ("filler", "no misreading points to it")])


def task_json(rows, st):
    split = f"generated, seed {SEED}" + (" (sealed split: BENCH_SEED)" if SEALED else "")
    ch = {k: st["chars"][k] for k in (1, 2, 3)}
    notes = ("600 items = 3 levels x (66 groups of three + 1 group of two); 200 items per level. The members of a group share one queue "
             "and differ in ONE element (current time, one flag, one arrival time, one class at level 1, or the position asked for) and have "
             "different answers among the same five options (five ticket ids of the queue: the answers of the members and the answers of "
             "plausible misreadings, recorded in meta.option_roles). Gold option place balanced exactly (40 per place and level); the row of "
             "the gold case in the listing balanced over the fifths of the list. meta.deviation is the planted kind of the group (all members), "
             "meta.variant 0 marks the base member. Truth computed twice (sort key and pairwise duels). State characters per level min/median/max: "
             + "; ".join(f"L{k} {ch[k][0]}/{ch[k][100]}/{ch[k][-1]}" for k in (1, 2, 3)) + ". gen_v4 fixes: no time column contradicts another "
             "(appointment never before arrival, workshop pickup never before check-in + bench time, asserted on the text of every state); the "
             "class-first shortcut is excluded (level 1: class is rule 1 in every rule set, the top class has at least two cases and the other "
             "tie-break never gives the key, no class column is shown without a rule that uses it; levels 2-3: the shortcut gives the key in at "
             "most one member of a group and in at most 25 % of the items).")
    return {"task": TASK, "layer": "D",
            "title": "Generated waiting queues: which case do the written ordering rules put at the asked position?",
            "decision": "which of five listed cases of a waiting queue the numbered ordering rules of the state put at the position asked for",
            "source": {"name": f"generator build/gen_{TASK}.py", "url": "", "files": [], "split": split, "version": VERSION},
            "licence": "generated by the benchmark's script (no third-party text)", "redistribution": "items included",
            "labels": "programmatic", "item_source": "generated", "metric": "accuracy", "chance": 0.2, "rows": len(rows),
            "groups": st["groups"], "question_type": "choice", "options": 5, "notes": notes,
            "skill": "apply ordered priority rules with class adjustments (waiting limit, flag, floor at class 1, cumulative or not) and tie-breaks to a queue, then read off a position",
            "knobs": "cases 6 / 9-10 / 12-14; level 1 rule sets class-arrival / class-ticket / class-arrival-ticket; rules 2-3 / 4 / 5-6; class adjustments 0 / 1 / 2 (cumulative or not); position asked 1 / 1-2 / 1-3; "
                     "limit W 20-90 min with half of the waits within 3 min of W; appointments due on the minute; 3 table layouts x 2 block orders"}


def fmt_example(r):
    m = r["meta"]
    out = [f"id `{r['id']}` (group `{r['group']}`, level {m['level']}, domain {m['domain']}, deviation `{m['deviation']}`, variant {m['variant']}, "
           f"gold **{r['gold']}**; true order {', '.join(m['true_order'][:5])}, ...; decided by rule {m['decided_by']['rule']} ({m['decided_by']['kind']}))",
           "", "```", r["state"], "```", f"question: {r['questions']['q']['instructions']}", ""]
    out += [f"- `{k}`: {v}  ({', '.join(m['option_roles'][k])})" for k, v in r["questions"]["q"]["criteria"].items()]
    return "\n".join(out)


def time_and_class_section(st):
    t2, t3 = st["times"][2], st["times"][3]
    c1 = st["cf"][1]
    out = ["## Consistent times (gen_v4)", "",
           "No time column contradicts another in any domain. The appointment time of a case (slot / callback / pickup / berth window / "
           "reserved start / booked time) is never before the arrival time of the same case, and in the workshop, where the appointment "
           "is the pickup of the repaired job, never before check-in + bench time; every arrival is before the current time. The "
           "dependent time is drawn after the times it depends on (offsets round the current time as before: due earlier, due on the "
           "minute, due up to three minutes later, later; an offset that would break the order is drawn again), and a planted arrival "
           "change that would break the order is not offered. For every item the queue is parsed back from the rendered text and checked "
           "(parsed queue = specification, arrival before the current time, appointment not before the time it depends on). "
           f"Appointment times: level 2 {t2['rows']} ({t2['workshop_rows']} in the workshop), level 3 {t3['rows']} ({t3['workshop_rows']}); "
           f"smallest gap to the time they depend on {min(t2['min_gap'], t3['min_gap'])} minutes, exactly on it in {t2['equal'] + t3['equal']} cases.", "",
           "## The class-first shortcut (gen_v4)", "",
           "The shortcut is the reading \"lowest LISTED class first, then earliest arrival, then ticket\", with the class changes, the flags, "
           "the appointments and the rules actually written all ignored (`meta.readings.class_first_listed`). The table counts the items in "
           "which this reading gives the key. Levels 2-3: the generator rejects a group in which the reading gives the key in more than one "
           "member and asserts at most 25 % of the items of a level. Level 1: class is rule 1 in every item (the class column is never shown "
           "without a rule that uses it); where the rules are class, arrival (, ticket) the reading is the written rule itself, so its hits "
           "are not a shortcut.", "",
           "| level | items | class-first reading = key | of these, the reading is the written rule (level 1) | shortcut hits | share of the items |",
           "|---|---|---|---|---|---|"]
    for k in (1, 2, 3):
        d = st["cf"][k]
        out.append(f"| {k} | {d['items']} | {d['hits']} | {d['hits'] - d['shortcut_hits']} | {d['shortcut_hits']} | {d['shortcut_hits'] / d['items']:.3f} |")
    out += ["", "Level 1, the shortcut \"class first, ignore the second rule\", is excluded in every member of every group: the top class holds at "
            f"least two cases (sizes {c1['top_sizes']}), so the class alone decides in {c1['class_alone_decides']} items; the other tie-break "
            "(ticket where arrival is written, arrival where ticket is written) gives the key in "
            f"{c1['other_tiebreak_hits']} items; picking at random in the top class would be right in {c1['random_pick']:.3f} of the items, "
            f"taking the first listed case of the top class in {c1['first_listed_hits']} of {c1['items']}. Markers of level 1 are the "
            "neutral ones (no urgent-sounding flag that no rule uses).", ""]
    return out


def readme(rows, st):
    lv = lambda k, f: f(st, k)
    lines = [f"# {TASK}", "",
             "Generated waiting queues: which case do the written ordering rules put at the position asked for? Layer D, generated, "
             "programmatic truth, EVALUATION ONLY.", "",
             "## What is generated", "",
             "Every state describes one service point (six domains with their own nouns, column names, flags and terms: walk-in clinic, IT "
             "support desk, repair workshop, berth planning in a harbour, render farm / print room / batch cluster, citizens' service counter), "
             "the current time, numbered ordering rules applied in the order given, the conventions that the rules need, the waiting queue "
             "(ticket id, class, arrival time, flag; from level 2 also an appointment time and an expected duration), the meaning of the "
             "fields and the position asked for (first; from level 2 also second; at level 3 also third). The question is the same for "
             "every item: "
             f"\"{INSTRUCTIONS}\" The options are five ticket ids of the queue. Groups of three items share one queue, differ in ONE element "
             "and have three different answers among the same five options; one group per level has two members (66 x 3 + 2 = 200).", "",
             "Truth: `truth(spec)` sorts the cases by a key built from the rules (`sort_key`); a second implementation (`precedes`, pairwise "
             "duels over the rules) must give the same strict total order for every item. The order is total by construction: the last rule "
             "is the ticket number (unique), or at level 1 an arrival time that no two cases share (stated).", "",
             "## Conventions written into the state (only those the rules of the item need)", "",
             "- rules apply in the order given; a later rule only separates cases that every earlier rule leaves level",
             "- class-changing rules are applied first to every case; afterwards \"class\" means the changed class; up one class = class "
             "number minus 1; never above class 1; a moved case is an ordinary member of its new class",
             "- waiting time = current time minus arrival time in minutes (same day, 24-hour clock); \"at least W minutes\" counts W",
             "- level 3: whether the two class changes add up (two classes up) or not (one class up at most) is stated per item",
             "- an appointment is due when its time is the current time or earlier; due cases are level with each other, and so are "
             "not-due cases (no appointment or a later one)",
             "- one order is computed at the current time; first / second / third are places in it",
             "- columns and flags that no rule names have no effect; the ticket number is the number after the dash and is unique", "",
             "## Levels", "",
             "| level | cases | rules | class changes | positions asked | rule sets (items) |", "|---|---|---|---|---|---|"]
    for k, (cases, rules, adj) in zip((1, 2, 3), (("6", "2-3 (class is rule 1)", "none"), ("9-10", "4", "one (waiting limit or flag)"),
                                                  ("12-14", "5-6", "two (waiting limit and flag)"))):
        rs = "; ".join(f"{a} ({b})" for a, b in st["rulesets"][k].items())
        lines.append(f"| {k} | {cases} | {rules} | {adj} | {st['asks'][k]} | {rs} |")
    lines += ["", "What makes level 3 hard: (1) the waiting time of every case against W, with waits on W and one to three minutes "
              "either side of it; (2) the named flag, among look-alike flags that do nothing; (3) the combination of the two class changes "
              "(cumulative or not, as stated) and the floor at class 1; (4) the comparison by changed class; (5) one or two tie-break rules "
              "(appointment due at the current time, arrival, duration) in the order written; (6) reading off the second or third place of "
              "the resulting order. Every level-3 group is built so that ignoring the waiting rule and ignoring the flag rule each give a "
              "wrong answer for at least one member, and ignoring both gives a wrong answer for (nearly) every member.", "",
              "## Planted differences (items per level)", "",
              "| kind | element changed | level 1 | level 2 | level 3 |", "|---|---|---|---|---|"]
    what = {"arrival": "one arrival time (+-1 to 10 min)", "class": "one listed class (+-1; level 1 only)", "clock": "the current time (+-1 to 15 min)",
            "flag": "one flag cell (set to the named flag, or removed / replaced by another flag)", "position": "the position asked for (level 3)"}
    for kind in ("arrival", "class", "clock", "flag", "position"):
        lines.append(f"| {kind} | {what[kind]} | " + " | ".join(str(st["dev"][k].get(kind, 0)) for k in (1, 2, 3)) + " |")
    lines += ["", "`meta.deviation` is the kind of the group for all its members; `meta.variant` 0 is the base member and `meta.change` "
              "the element changed in the other members.", ""]
    lines += time_and_class_section(st)
    lines += ["",
              "## Options and misreadings", "",
              "The five options of a group are the answers of its members plus the cases that most misreadings point to. Every wrong option of "
              "an item has its roles in `meta.option_roles` (counts over all wrong options):", ""]
    for name, desc in READING_DESC.items():
        if st["roles"].get(name):
            lines.append(f"- `{name}` ({st['roles'][name]}): {desc}")
    lines += ["", "Share of items in which a sloppy reading gives a WRONG answer (wrong / items where the reading applies):", "",
              "| reading | level 1 | level 2 | level 3 |", "|---|---|---|---|"]
    for name in TRACKED:
        cells = []
        for k in (1, 2, 3):
            w = st["wrong"][k].get(name)
            cells.append(f"{w[0]}/{w[1]}" if w else "-")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines += ["", "Second and third place: how many of the cases ahead of the answer are among the options (ranking only the five "
              "options gives the answer only when all of them are; taking the best option only when none is): "
              + "; ".join(f"{a} ({b})" for a, b in st["ahead"].items()) + "."]
    lines += ["", "Rule that separates the answer from its neighbours in the order (items per level): "
              + "; ".join(f"level {k}: {st['depth'][k]}" for k in (1, 2, 3)) + ".", "",
              "## Balance and checks run by the script", "",
              "- 600 items, 200 per level, 201 groups; gold option place per level " + ", ".join(f"L{k} {st['place'][k]}" for k in (1, 2, 3)),
              "- gold case per row of the listing (queues of one level and size): " + "; ".join(f"{a} {b}" for a, b in st["row_spread"].items())
              + "; by fifths of the list: " + ", ".join(f"L{k} {st['bin'][k]}" for k in (1, 2, 3))
              + "; mean Kendall tau between listing and true order " + ", ".join(f"L{k} {st['tau'][k]:+.3f}" for k in (1, 2, 3)),
              "- asserted for every item: the order is strict and total, `truth` equals the duel implementation, the members of a group "
              "differ in exactly the planted element, have different answers, the same number of lines (length gap max "
              f"{st['len_gap_max']} characters), all answers are among the five options; no duplicate state; one instruction string",
              "- asserted per level: gold places 40 each, gold rows spread over the rows of the listing (counts per row differ by at most 2), deviation kinds as equal as groups of three allow; at "
              "levels 2-3 ignoring the class changes gives a wrong answer in at least 80 % of the items",
              "- the listing order of a queue is redrawn while it equals the true order of a member (or its reverse) or the order by "
              "arrival, ticket or listed class",
              "- asserted for every item (gen_v4): the queue parsed back from the rendered text equals the specification; every arrival "
"is before the current time; no appointment time is before the time it depends on (arrival; workshop: arrival + bench time); "
              "levels 2-3: the class-first reading gives the key in at most 25 % of the items; level 1 (class is rule 1): the top class has "
              "at least two cases in every member and the other tie-break never gives the key",
              f"- state characters min/median/max: " + "; ".join(f"L{k} {st['chars'][k][0]}/{st['chars'][k][100]}/{st['chars'][k][-1]}" for k in (1, 2, 3)),
              "- external checks: `python3 validate.py triage_order`, `python3 audit.py triage_order`, `audit_v3.py triage_order` (numpy)", "",
              "## Sealed split", "",
              "`BENCH_OUT=<dir>` writes `<dir>/triage_order/` instead of `tasks/triage_order/`; `BENCH_SEED=<k>` (only together with "
              "BENCH_OUT) roots every generator at k instead of 20261007; ids become `triage_order:s<k>:<n>`.", "",
              "## Examples (one per level)", ""]
    for k in (1, 2, 3):
        r = next(x for x in rows if x["meta"]["level"] == k)
        lines += [f"### Level {k}", "", fmt_example(r), ""]
    lines += ["## Independence", "",
              "The generator is new: all wording, layouts, rules and names were written for this family. It shares no template, sentence "
              "or code with the authors' training-data generators or with benchmark v0, and no item comes from an existing data set. All "
              "service points, names and identifiers are invented (syllable generator and code-like ticket ids).", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
