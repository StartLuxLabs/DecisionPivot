"""Task perm_inherit (layer B, generated, programmatic truth): "Is the request allowed?"

EVALUATION ONLY.  The state is the access export of an invented system: the rules in plain words, the actions and the
inclusions between them, roles (own actions; from level 2 a role may extend one other role), users, groups (members:
users and, from level 2, other groups), a tree of nodes (folders / namespaces / sections / zones / collections; from
level 2 some are sealed), assignments (a role given to a user or a group AT a node), deny entries (level 3, some at
level 2) and ONE request (user, action, node).  The gold answer is yes when the rules allow the request.

Truth.  ``truth(spec)`` works on the structured specification only: the requester's principals are the user and every
group reached through nested membership; an assignment covers its node and everything below it unless a sealed node
lies below the assignment's node on the way down to the requested node (the requested node included); a role allows
its own actions and those of the roles along its extension chain; listed inclusions chain and never run backwards; a
deny entry applies when its user / group is a principal of the requester, its action is exactly the requested action
and its node is the requested node or an ancestor of it (seals do not stop it); allowed = at least one assignment
grants and no deny entry applies.

Pairs.  600 items = 300 contrast pairs (``group``): a positive whose allowing path is unique and a negative that is the
same specification with ONE planted difference - in the request line (150 pairs) or in one line of the structure (150
pairs).  Kinds (``meta.deviation``): membership, sealed, role_chain, action, scope, deny.  The script asserts for every
pair: the positive has exactly one granting assignment, one membership chain and no applicable deny entry; on the
designated path of the negative exactly the planted link is broken and every other link holds (``links``); no other
assignment grants; for the kind deny exactly one deny entry applies and the assignment still grants; the two states
have the same number of lines, differ in exactly one line and contain the same set of word tokens.

Environment: BENCH_OUT=<dir> writes <dir>/perm_inherit/ instead of generated/tasks/perm_inherit/; BENCH_SEED=<int> (only together
with BENCH_OUT) builds another item set of the same design for a sealed split.
    python3 generators/perm_inherit.py
"""
import collections
import copy
import json
import os
import random
import re
import subprocess
import sys

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated")   # items go to HERE/tasks/<family>/ (BENCH_OUT: elsewhere)
TASK = "perm_inherit"
DEFAULT_SEED = 20261007
_ENV_SEED = os.environ.get("BENCH_SEED", "").strip()
_ENV_OUT = os.environ.get("BENCH_OUT", "").strip()
if _ENV_SEED and not _ENV_OUT:
    sys.stderr.write("BENCH_SEED is accepted only together with BENCH_OUT (the published set is never overwritten by another seed)\n")
    sys.exit(2)
SEED = int(_ENV_SEED) if _ENV_SEED else DEFAULT_SEED
OUT_ROOT = os.path.abspath(_ENV_OUT) if _ENV_OUT else os.path.join(HERE, "tasks")
ID_PREFIX = f"{TASK}:s{SEED}:" if _ENV_SEED else f"{TASK}:"

INSTRUCTIONS = "Is the request allowed?"
OPTIONS = {"yes": "The request is allowed.", "no": "The request is not allowed."}
KINDS = ["membership", "sealed", "role_chain", "action", "scope", "deny"]
# pairs per level and kind: (difference in the request line, difference in one line of the structure)
PLAN = {1: {"membership": (17, 17), "action": (17, 16), "scope": (16, 17)},
        2: {"membership": (9, 8), "sealed": (8, 9), "role_chain": (9, 8), "action": (8, 9), "scope": (8, 8), "deny": (8, 8)},
        3: {"membership": (8, 8), "sealed": (8, 8), "role_chain": (8, 9), "action": (9, 8), "scope": (9, 8), "deny": (8, 9)}}
SIZES = {1: dict(users=(4, 6), groups=(2, 3), roles=(3, 4), acts=(4, 4), incl=(2, 3), assigns=(4, 6), sealed=0, nest=0, ext=(0, 0), extchain=0),
         2: dict(users=(6, 9), groups=(4, 5), roles=(4, 5), acts=(4, 5), incl=(2, 4), assigns=(5, 7), sealed=1, nest=1, ext=(1, 2), extchain=1),
         3: dict(users=(10, 14), groups=(6, 8), roles=(6, 7), acts=(5, 6), incl=(3, 5), assigns=(8, 11), sealed=2, nest=2, ext=(2, 4), extchain=2)}


def rng_for(*parts):
    return random.Random(":".join(str(p) for p in (SEED, TASK) + parts))


# ------------------------------------------------------------------------------------------------ invented worlds
# actions are listed from the weakest to the strongest; a listed inclusion always runs from a later to an earlier action
DOMAINS = {
    "workspace": {"node": "folder", "nodes": "folders", "what": "document workspace", "tops": ["all-files", "main-drive", "team-space"],
                  "actions": ["view", "comment", "export", "edit", "share", "archive"],
                  "bases": ["contracts", "drafts", "invoices", "minutes", "designs", "tenders", "reports", "templates", "briefs", "plans",
                            "budgets", "hiring", "travel", "suppliers", "press", "legal", "research", "handbook", "pricing", "onboarding",
                            "letters", "audits", "events", "vendors", "training", "policies", "forecasts", "assets"],
                  "twins": [("-a", "-b"), ("-2025", "-2026"), ("-north", "-south"), ("-old", "-new")]},
    "codehost": {"node": "namespace", "nodes": "namespaces", "what": "code hosting service", "tops": ["all-code", "main-org", "eng-root"],
                 "actions": ["read", "clone", "comment", "push", "merge", "release"],
                 "bases": ["platform", "billing", "mobile", "infra", "search", "docs", "sdk", "gateway", "ingest", "auth", "web", "tools",
                           "models", "pipelines", "qa", "sandbox", "legacy", "firmware", "console", "payments",
                           "cli", "cache", "metrics", "plugins", "router", "scheduler", "storage", "widgets"],
                 "twins": [("-api", "-svc"), ("-v1", "-v2"), ("-ios", "-web"), ("-lib", "-app")]},
    "records": {"node": "section", "nodes": "sections", "what": "records system", "tops": ["all-records", "main-registry", "full-archive"],
                "actions": ["lookup", "annotate", "export", "amend", "transfer", "purge"],
                "bases": ["admissions", "claims", "permits", "licences", "tenancy", "pensions", "appeals", "census", "grants", "audits",
                          "personnel", "deeds", "surveys", "tariffs", "inspections", "complaints", "payroll", "leases", "rosters", "incidents",
                          "births", "marriages", "vehicles", "zoning", "elections", "fisheries", "harbour", "schools"],
                "twins": [("-east", "-west"), ("-1998", "-2004"), ("-open", "-held"), ("-a", "-b")]},
    "building": {"node": "zone", "nodes": "zones", "what": "building access system", "tops": ["whole-site", "campus", "main-site"],
                 "actions": ["enter", "escort", "inspect", "service", "unlock", "rekey"],
                 "bases": ["lobby", "dock", "lab", "plantroom", "storeroom", "serverhall", "workshop", "canteen", "cleanroom", "roof",
                           "basement", "wing", "annex", "gatehouse", "yard", "vault", "mezzanine", "garage", "atrium", "bay",
                           "corridor", "stairwell", "boilerroom", "laundry", "library", "pantry", "studio", "hangar"],
                 "twins": [("-1", "-2"), ("-north", "-south"), ("-a", "-b"), ("-upper", "-lower")]},
    "catalog": {"node": "collection", "nodes": "collections", "what": "data catalogue", "tops": ["all-data", "main-lake", "catalog-root"],
                "actions": ["query", "sample", "export", "load", "alter", "drop"],
                "bases": ["sales", "telemetry", "crm", "ledger", "clicks", "inventory", "pricing", "returns", "shipments", "weather",
                          "sensors", "surveys", "forecasts", "tickets", "staffing", "campaigns", "fraud", "geo", "sessions", "tariffs",
                          "orders", "payments", "refunds", "devices", "visits", "leads", "churn", "budget"],
                "twins": [("_raw", "_std"), ("_2025", "_2026"), ("_eu", "_us"), ("_day", "_hrs")]},
}
DOMAIN_ORDER = ["workspace", "codehost", "records", "building", "catalog"]
GROUP_A = ["ops", "audit", "field", "desk", "intake", "review", "relief", "core", "duty", "shift", "crew", "staff", "guard", "admin",
           "support", "visitor", "vendor", "intern"]
GROUP_B = ["east", "west", "red", "blue", "green", "amber", "alpha", "beta", "day", "late", "one", "two"]
ONS = ["b", "d", "f", "g", "h", "j", "k", "l", "m", "n", "p", "r", "s", "t", "v", "z", "br", "dr", "gr", "kr", "st", "tr"]
MID = ["lv", "rn", "sk", "nd", "mb", "lk", "vr", "zd", "ld", "nt", "rv", "lm", "rz", "sp", "ft", "ng", "lt", "rk"]
VOW = ["a", "e", "i", "o", "u"]
COD = ["k", "th", "sh", "rn", "sk", "lt", "rd", "v", "z", "ph", "ck", "gh"]
INITIALS = "abcdefghjklmnprstvw"
BLOCK = {"sandoz", "bandit", "mandrak", "kalvish", "bangkok", "hendrik", "pentark", "tampik", "randolph", "rudolph", "bismark"}

# ------------------------------------------------------------------------------------------------ the rules in words
WHO_FLAT = [
    "An assignment gives one role to one user or to one group. An assignment to a group counts for every user on that group's member list and for nobody else.",
    "Each assignment names a role and either a user or a group. If it names a group, exactly the users listed as members of that group hold the role.",
    "A role is held by the user an assignment names or, when the assignment names a group, by each user listed in that group. Users who are not listed in the group get nothing from it.",
]
WHO_NESTED = [
    "An assignment gives one role to one user or to one group. An assignment to a group counts for every member of the group. Membership passes through nested groups: when group X is listed as a member of group Y, all members of X (also those X has through its own nested groups) are members of Y. It does not pass the other way: a user listed directly in Y is not thereby a member of X.",
    "Each assignment names a role and either a user or a group; if it names a group, every member of the group holds the role. Groups may list other groups as members. A user belongs to a group if the group lists the user or lists a group the user belongs to, over any number of steps. Belonging never runs downward: the users listed in an outer group do not belong to the groups listed inside it.",
    "A role is held by the user an assignment names or, when it names a group, by every member of that group. The members of a group are the users on its list plus all members of each group on its list, and so on through further nesting. A group that is nested inside another gains no members from the group that contains it.",
]
WHERE = [
    "An assignment is made at one {node}. It covers that {node} and every {node} below it (directly or further down), and nothing else.",
    "The role of an assignment is valid on the {node} named in the assignment and on all {nodes} below that {node} at any depth, not on any other {node}.",
    "Assignments reach downward only: the {node} where an assignment is made and everything below it, however deep, are covered; {nodes} beside it or above it are not.",
]
SEAL = [
    "A sealed {node} blocks assignments from above: an assignment made at a higher {node} covers neither the sealed {node} nor anything below it. An assignment made at the sealed {node} itself, or at a {node} below it, is not affected by that seal, and {nodes} outside the sealed {node} are not affected either.",
    "Exception for sealed {nodes}: an assignment never passes into a sealed {node} from a {node} above it, so the sealed {node} and everything below it stay out of its reach. A seal does nothing to an assignment made at the sealed {node} or below it, and nothing to {nodes} that are not inside the sealed {node}.",
    "Sealing cuts off what comes from above. If the requested {node} is a sealed {node} or lies below one, an assignment made above that sealed {node} does not cover it. Assignments made at the sealed {node} or below it work as usual, and a sealed {node} elsewhere in the tree has no effect.",
]
ROLE_FLAT = ["A role allows the actions listed for it.", "The actions a role allows are the ones listed for that role.",
             "Holding a role permits the actions on that role's list."]
ROLE_EXT = [
    "A role allows the actions listed for it. A role that extends another role also allows everything the other role allows, including what that role gets from a role it extends. Extension works one way only: the extended role gains nothing.",
    "Holding a role permits the actions on its own list and, when the role extends a second role, every action the second role permits (its own list and whatever it takes over by extension). The second role takes over nothing from the first.",
    "The actions a role allows are its own actions plus the actions of the role it extends, plus those of the role that one extends, and so on. Nothing is passed in the opposite direction, from the extending role to the extended one.",
]
INCL = [
    "The inclusion list says which action includes which. If X includes Y, a role that allows X allows Y as well; inclusions chain, so if Y in turn includes Z, then X includes Z. Only the listed inclusions exist, and none works in reverse.",
    "Actions can include other actions, exactly as listed. Being allowed an action means being allowed every action it includes, directly or through a chain of listed inclusions. An inclusion is never read backwards, and actions without a listed link do not include each other.",
    "Where the inclusion list states that one action includes another, permission for the first counts as permission for the second, and likewise onward along several such lines. There are no unlisted inclusions, and the included action never brings the including one.",
]
DENY = [
    "A deny entry names a user or a group, one action and one {node}. It applies to a request when the requester is that user or a member of that group (nested membership counts), the requested action is exactly the named action, and the requested {node} is the named {node} or lies below it; a seal does not stop a deny entry. A deny entry that applies beats every assignment. It affects no other action: denying X does not block Y, even if X includes Y or Y includes X.",
    "Deny entries win over assignments. An entry blocks its action for the user it names, or for every member of the group it names (members through nested groups included), on its {node} and on everything below that {node}, sealed or not. It blocks that single action only; requests for other actions are judged as if the entry were not there, also when the actions are linked by an inclusion.",
    "A deny entry forbids one action to one user, or to all direct and nested members of one group, on one {node} and all {nodes} below it; seals make no difference to deny entries. When an entry matches the requester, the exact action and the {node}, the request is refused whatever the assignments say. An entry for a different action never matches, and inclusions between actions are ignored for deny entries.",
]
DECIDE = [
    "A request is allowed if at least one assignment gives the requester a role that allows the requested action and covers the requested {node}{d0}. Otherwise it is not allowed.",
    "Decision: a request is allowed when some assignment that counts for the requester covers the requested {node} with a role that allows the requested action{d1}. In every other case it is not allowed.",
    "A request is allowed only when an assignment whose role the requester holds covers the requested {node} and that role allows the requested action{d2}.",
]
DECIDE_DENY = {"d0": ", and no deny entry applies", "d1": ", unless a deny entry applies", "d2": "; in addition no deny entry may apply"}


# ------------------------------------------------------------------------------------------------ truth on the specification
def up(spec, node):
    """the node, its parent, ... up to the top"""
    out = [node]
    while out[-1] in spec["parent"]:
        out.append(spec["parent"][out[-1]])
    return out


def groups_of(spec, user):
    """every group the user is a member of, directly or through nested groups"""
    out, todo = [], [user]
    while todo:
        x = todo.pop()
        for g in spec["groups"]:
            if x in g["members"] and g["name"] not in out:
                out.append(g["name"])
                todo.append(g["name"])
    return out


def principals(spec, user):
    return [user] + groups_of(spec, user)


def covers(spec, at, node):
    """an assignment at `at` covers `node`: `at` is the node or an ancestor, and no sealed node lies below `at` on the way down to `node` (inclusive)"""
    path = up(spec, node)
    return at in path and not any(n in spec["sealed"] for n in path[:path.index(at)])


def role_chain(spec, role):
    by = {r["name"]: r for r in spec["roles"]}
    out = [role]
    while by[out[-1]]["extends"] is not None:
        if by[out[-1]]["extends"] in out:
            raise ValueError("extension cycle")
        out.append(by[out[-1]]["extends"])
    return out


def own_actions(spec, role):
    return next(r["actions"] for r in spec["roles"] if r["name"] == role)


def closure(spec, acts):
    out, todo = list(acts), list(acts)
    while todo:
        x = todo.pop()
        for a, b in spec["includes"]:
            if a == x and b not in out:
                out.append(b)
                todo.append(b)
    return out


def role_allows(spec, role):
    return closure(spec, [a for r in role_chain(spec, role) for a in own_actions(spec, r)])


def allow_paths(spec):
    rq = spec["request"]
    pr = principals(spec, rq["user"])
    return [i for i, a in enumerate(spec["assignments"])
            if a["who"] in pr and covers(spec, a["at"], rq["node"]) and rq["action"] in role_allows(spec, a["role"])]


def deny_hits(spec):
    rq = spec["request"]
    pr, path = principals(spec, rq["user"]), up(spec, rq["node"])
    return [i for i, d in enumerate(spec["denies"]) if d["who"] in pr and d["action"] == rq["action"] and d["at"] in path]


def truth(spec):
    return bool(allow_paths(spec)) and not deny_hits(spec)


def links(spec, des):
    """the six links of the designated path (assignment des['assign'], role des['carrier'] carries the action): which of them hold"""
    rq, a = spec["request"], spec["assignments"][des["assign"]]
    scope = a["at"] in up(spec, rq["node"])
    return {"membership": a["who"] in principals(spec, rq["user"]),
            "scope": scope,
            "sealed": covers(spec, a["at"], rq["node"]) if scope else True,
            "role_chain": des["carrier"] in role_chain(spec, a["role"]),
            "action": rq["action"] in closure(spec, own_actions(spec, des["carrier"])),
            "deny": not deny_hits(spec)}


def member_paths(spec, user, group):
    """lengths of all distinct membership chains from the user up to the group"""
    by = {g["name"]: g["members"] for g in spec["groups"]}

    def walk(g):
        res = []
        for m in by[g]:
            if m == user:
                res.append(1)
            elif m in by:
                res += [k + 1 for k in walk(m)]
        return res
    return walk(group)


def incl_dist(spec, acts, target):
    """smallest number of inclusion lines needed to get from one of the actions to the target (None: not reachable)"""
    seen, layer, d = list(acts), list(acts), 0
    while layer:
        if target in layer:
            return d
        nxt = []
        for x in layer:
            for a, b in spec["includes"]:
                if a == x and b not in seen:
                    seen.append(b)
                    nxt.append(b)
        layer, d = nxt, d + 1
    return None


def nest_depth(spec):
    by = {g["name"]: g["members"] for g in spec["groups"]}

    def dep(g, stack):
        if g in stack:
            raise ValueError("group cycle")
        return max([1 + dep(m, stack + [g]) for m in by[g] if m in by] or [0])
    return max([dep(g, []) for g in by] or [0])


def apply_edit(spec, edit):
    """the planted difference: one field of the request or one element of one structure line"""
    s, k = copy.deepcopy(spec), edit[0]
    if k == "request":
        s["request"][edit[1]] = edit[2]
    elif k == "member":
        mem = next(g["members"] for g in s["groups"] if g["name"] == edit[1])
        mem[mem.index(edit[2])] = edit[3]
    elif k == "sealed":
        s["sealed"][s["sealed"].index(edit[1])] = edit[2]
    elif k == "role_ext":
        next(r for r in s["roles"] if r["name"] == edit[1])["extends"] = edit[2]
    elif k == "include":
        s["includes"][edit[1]][edit[2]] = edit[3]
    elif k == "role_action":
        acts = next(r["actions"] for r in s["roles"] if r["name"] == edit[1])
        acts[acts.index(edit[2])] = edit[3]
    elif k == "assign_at":
        s["assignments"][edit[1]]["at"] = edit[2]
    elif k == "deny":
        s["denies"][edit[1]][edit[2]] = edit[3]
    else:
        raise ValueError(k)
    return s


def structure_ok(spec, level):
    """well-formed: unique names, group and role graphs without cycles and within the limits of the level, no repeated line"""
    sz = SIZES[level]
    us, gn, rn = spec["users"], [g["name"] for g in spec["groups"]], [r["name"] for r in spec["roles"]]
    nodes = [spec["top"]] + list(spec["parent"])
    names = nodes + us + gn + rn + spec["actions"]
    if len(set(names)) != len(names):
        return False
    for g in spec["groups"]:
        m = g["members"]
        if len(set(m)) != len(m) or g["name"] in m or any(x not in us and x not in gn for x in m) or not m:
            return False
    try:
        if nest_depth(spec) > sz["nest"]:
            return False
        for r in spec["roles"]:
            if not r["actions"] or len(set(r["actions"])) != len(r["actions"]) or any(a not in spec["actions"] for a in r["actions"]):
                return False
            if r["extends"] is not None and r["extends"] not in rn:
                return False
            if len(role_chain(spec, r["name"])) - 1 > sz["extchain"]:
                return False
    except ValueError:
        return False
    if sum(r["extends"] is not None for r in spec["roles"]) > sz["ext"][1]:
        return False
    inc = [tuple(x) for x in spec["includes"]]
    if len(set(inc)) != len(inc) or any(a == b or a not in spec["actions"] or b not in spec["actions"] for a, b in inc):
        return False
    if any((b, a) in inc for a, b in inc):
        return False
    asg = [(a["role"], a["who"], a["at"]) for a in spec["assignments"]]
    if len(set(asg)) != len(asg) or any(r not in rn or (w not in us and w not in gn) or n not in nodes for r, w, n in asg):
        return False
    den = [(d["who"], d["action"], d["at"]) for d in spec["denies"]]
    if len(set(den)) != len(den) or any((w not in us and w not in gn) or a not in spec["actions"] or n not in nodes for w, a, n in den):
        return False
    if len(set(spec["sealed"])) != len(spec["sealed"]) or any(n not in spec["parent"] for n in spec["sealed"]):
        return False                                                  # the top node is never sealed
    rq = spec["request"]
    return rq["user"] in us and rq["action"] in spec["actions"] and rq["node"] in nodes


def judge(spec, **o):
    """second evaluation with switches for sloppy readings (all switches at their default = the rules as written)"""
    rq = spec["request"]
    u, by = rq["user"], {g["name"]: g["members"] for g in spec["groups"]}
    direct = [u] + [g for g in by if u in by[g]]
    nesting = o.get("nesting", "up")
    pr = list(direct) if nesting == "none" else principals(spec, u)
    if nesting == "both":                 # wrong: the users of an outer group are taken as members of the groups nested inside it
        todo = list(pr)
        while todo:
            x = todo.pop()
            for m in by.get(x, []):
                if m in by and m not in pr:
                    pr.append(m)
                    todo.append(m)
    path = up(spec, rq["node"])

    def cov(at):
        sc = o.get("scope", "down")
        if sc == "any":
            return True
        if at not in path:
            return sc == "updown" and rq["node"] in up(spec, at)
        return o.get("seal", "rule") == "none" or not any(n in spec["sealed"] for n in path[:path.index(at)])
    rb = {r["name"]: r for r in spec["roles"]}

    def allows(role):
        e = o.get("ext", "up")
        chain = [role] if e == "none" else role_chain(spec, role)
        grew = e == "both"
        while grew:                       # wrong: extension read in both directions
            grew = False
            for r in spec["roles"]:
                for p, q in ((r["extends"], r["name"]), (r["name"], r["extends"])):
                    if p in chain and q is not None and q not in chain:
                        chain.append(q)
                        grew = True
        acts = [a for r in chain for a in rb[r]["actions"]]
        i = o.get("incl", "fwd")
        if i == "none":
            return acts
        if i == "fwd":
            return closure(spec, acts)
        out, todo = list(acts), list(acts)
        while todo:                       # wrong: inclusions read in both directions
            x = todo.pop()
            for a, b in spec["includes"]:
                for p, q in ((a, b), (b, a)):
                    if p == x and q not in out:
                        out.append(q)
                        todo.append(q)
        return out
    ok = any(a["who"] in pr and cov(a["at"]) and rq["action"] in allows(a["role"]) for a in spec["assignments"])
    if o.get("seal") == "any" and any(n in spec["sealed"] for n in path):
        ok = False                        # wrong: a sealed node on the way to the requested node refuses everything
    dm = o.get("deny", "rule")
    if dm == "none" or not ok:
        return ok
    for d in spec["denies"]:
        who = d["who"] in (direct if dm == "direct" else pr)
        act = d["action"] == rq["action"]
        if dm == "any_action":
            act = True
        elif dm == "linked":              # wrong: a deny on X also blocks what X includes and what includes X
            act = rq["action"] in closure(spec, [d["action"]]) or d["action"] in closure(spec, [rq["action"]])
        node = covers(spec, d["at"], rq["node"]) if dm == "seal_stops" else d["at"] in path
        if who and act and node:
            return False
    return True

# ------------------------------------------------------------------------------------------------ building blocks
class Fail(Exception):
    pass


def depth(sp, n):
    return len(up(sp, n)) - 1


def strictly_below(sp, n):
    return [x for x in sp["parent"] if n in up(sp, x)[1:]]


def make_tree(rng, level):
    """internal node ids N0 (top), N1, ...; level 1: flat (depth 2), level 2: depth 3, level 3: depth 4"""
    parent, cnt = {}, [1]

    def new(p):
        n = "N%d" % cnt[0]
        cnt[0] += 1
        parent[n] = p
        return n
    if level == 1:
        kids = [new("N0") for _ in range(rng.randint(5, 6))]
        for k in rng.sample(kids, 2):
            for _ in range(2):
                new(k)
        return parent
    lv1 = [new("N0") for _ in range(3)]
    lv2 = [new(p) for p in lv1 for _ in range(2)]
    if level == 2:
        for p in rng.sample(lv2, rng.randint(2, 3)):
            for _ in range(rng.randint(1, 2)):
                new(p)
        return parent
    lv3 = [new(p) for p in rng.sample(lv2, 4) for _ in range(2)]
    for p in rng.sample(lv3, rng.randint(3, 4)):
        for _ in range(rng.randint(1, 2)):
            new(p)
    return parent


def new_user(sp):
    u = "U%d" % len(sp["users"])
    sp["users"].append(u)
    return u


def new_group(sp, members):
    g = "G%d" % len(sp["groups"])
    sp["groups"].append({"name": g, "members": list(members)})
    return g


def new_role(sp, actions, extends=None):
    r = "R%d" % len(sp["roles"])
    sp["roles"].append({"name": r, "actions": list(actions), "extends": extends})
    return r


def gmem(sp, g):
    return next(x["members"] for x in sp["groups"] if x["name"] == g)


def twin_of(sp, kind, x):
    for a, b in sp["_tw"][kind]:
        if x == a:
            return b
        if x == b:
            return a
    return None


def twin_user(sp, u):
    v = twin_of(sp, "user", u)
    if v is None:
        v = new_user(sp)
        sp["_tw"]["user"].append((u, v))
    return v


def twin_group(sp, g, members):
    h = twin_of(sp, "group", g)
    if h is None:
        h = new_group(sp, members)
        sp["_tw"]["group"].append((g, h))
    return h


def twin_role(sp, r, actions, extends=None):
    q = twin_of(sp, "role", r)
    if q is None:
        q = new_role(sp, actions, extends)
        sp["_tw"]["role"].append((r, q))
    return q


def twin_nodes(sp, a, b):
    if a != b and sp["top"] not in (a, b) and twin_of(sp, "node", a) is None and twin_of(sp, "node", b) is None:
        sp["_tw"]["node"].append((a, b))


def pick_users(rng, sp, n, avoid):
    pool = [x for x in sp["users"] if x not in avoid]
    rng.shuffle(pool)
    out = pool[:n]
    while len(out) < n:
        out.append(new_user(sp))
    return out


def pair_ok(P, edit, desP, desN, kind, level):
    """the whole contract of a pair: P allowed through exactly one assignment (one membership chain, one carrier, no deny);
    N = P with the planted difference: on the designated path exactly the planted link fails, no other path allows"""
    try:
        N = apply_edit(P, edit)
        if not (structure_ok(P, level) and structure_ok(N, level)):
            return False
        if allow_paths(P) != [desP["assign"]] or deny_hits(P) or not all(links(P, desP).values()):
            return False
        a, rq = P["assignments"][desP["assign"]], P["request"]
        if a["who"] != rq["user"] and len(member_paths(P, rq["user"], a["who"])) != 1:
            return False
        if sum(rq["action"] in closure(P, own_actions(P, r)) for r in role_chain(P, a["role"])) != 1:
            return False
        if [k for k, v in links(N, desN).items() if not v] != [kind]:
            return False
        if kind == "deny":
            return allow_paths(N) == [desN["assign"]] and len(deny_hits(N)) == 1
        return not allow_paths(N) and not deny_hits(N)
    except (ValueError, KeyError, StopIteration, IndexError):
        return False


# ------------------------------------------------------------------------------------------------ the designated path and the planted difference
LV = {1: {"tdepth": [1, 2, 2], "k": [0, 1, 1], "clen": [0], "m": [0, 1]},
      2: {"tdepth": [2, 3, 3], "k": [0, 1, 2, 2], "clen": [0, 1, 1], "m": [0, 1, 1, 2]},
      3: {"tdepth": [3, 4, 4], "k": [2, 3], "clen": [1, 2, 2], "m": [0, 1, 1, 2]}}
SUBS = {("membership", "structure"): ["user_link", "group_link"], ("membership", "request"): ["twin_group", "outer"],
        ("action", "structure"): ["incl", "own"], ("action", "request"): ["reverse", "unlinked"],
        ("role_chain", "structure"): ["near_link", "far_link"], ("role_chain", "request"): ["twin", "reverse"],
        ("scope", "structure"): ["side", "below", "child"], ("scope", "request"): ["twin", "above"],
        ("sealed", "structure"): ["move"], ("sealed", "request"): ["under"],
        ("deny", "structure"): ["who", "action", "at"], ("deny", "request"): ["action", "node", "user"]}


def subs_for(level, kind, variant):
    s = list(SUBS[(kind, variant)])
    if level == 1:
        s = [x for x in s if x not in ("group_link", "outer")]
    if level < 3 and kind == "role_chain":
        s = [x for x in s if x not in ("far_link", "reverse")]
    return s


def pick_decoy_seal(rng, sp, at_above, offp, exclude):
    on = [n for n in at_above if n not in exclude and n not in sp["sealed"]]
    off = [n for n in offp if n not in exclude and n not in sp["sealed"]]
    if on and (rng.random() < 0.5 or not off):
        return rng.choice(on)
    if not off:
        raise Fail("no place for a decoy seal")
    return rng.choice(off)


def non_principal(rng, s, u, gch, level, protect):
    """a user or group that looks related to the requester but does not count for the requester"""
    kinds = ["twin_user"] + (["twin_group"] if gch else []) + (["inner"] if level >= 2 and gch else [])
    kd = rng.choice(kinds)
    if kd == "twin_user":
        return twin_user(s, u)
    if kd == "twin_group":
        return twin_group(s, rng.choice(gch), pick_users(rng, s, rng.randint(1, 2), protect))
    j = rng.randint(1, len(gch) - 1) if len(gch) >= 2 else 0          # nested INSIDE a group of the requester
    gi = new_group(s, pick_users(rng, s, rng.randint(1, 2), protect))
    gmem(s, gch[j]).append(gi)
    return gi


def deny_spot(rng, sp, t):
    """a node on the way from the top to t; often above a sealed node of that way (a seal does not stop a deny)"""
    path = up(sp, t)
    pos = [i for i, n in enumerate(path) if n in sp["sealed"]]
    if pos and rng.random() < 0.6:
        return rng.choice(path[max(pos) + 1:])
    return rng.choice(path)


def deep_pick(rng, sp, pool):
    deep = max(depth(sp, n) for n in pool)
    return rng.choice([n for n in pool if depth(sp, n) == deep] if rng.random() < 0.6 else pool)


def build_core(rng, level, kind, variant, sub, dom):
    sz, lv = SIZES[level], LV[level]
    names = DOMAINS[dom]["actions"]
    acts = [names[i] for i in sorted(rng.sample(range(6), rng.randint(*sz["acts"])))]
    sp = {"domain": dom, "top": "N0", "parent": make_tree(rng, level), "sealed": [], "users": [], "groups": [], "roles": [],
          "actions": acts, "includes": [], "assignments": [], "denies": [], "request": {},
          "_tw": {"user": [], "group": [], "role": [], "node": []}}
    # ---- the requested action is reached from the carrier's own action x through m listed inclusions
    m = rng.choice(lv["m"])
    if kind == "action" and variant == "structure" and sub == "incl":
        m = max(m, 1)
    m = min(m, len(acts) - 2)
    idx = sorted(rng.sample(range(len(acts)), m + 1), reverse=True)
    for i, j in zip(idx, idx[1:]):
        sp["includes"].append([acts[i], acts[j]])
    x, act = acts[idx[0]], acts[idx[-1]]
    free = [z for z in acts if act not in closure(sp, [z])]
    # ---- role chain R0 -> R1 -> ...; the carrier (index c) holds x, the other roles of the chain hold free actions only
    clen = rng.choice(lv["clen"])
    if kind == "role_chain":
        clen = 1 if sub == "reverse" else max(clen, 2 if sub == "far_link" else 1)
        c = clen if sub == "far_link" else rng.randint(1, clen)
    else:
        c = rng.randint(0, clen)
    chain = [None] * (clen + 1)
    for j in range(clen, -1, -1):
        own = [x] if j == c else []
        for z in rng.sample(free, min(len(free), rng.randint(0 if j == c else 1, 1 if level == 1 else 2))):
            own.append(z)
        if not own:
            raise Fail("role without action")
        chain[j] = new_role(sp, own, chain[j + 1] if j < clen else None)
    # ---- membership chain u -> g1 -> ... -> gk; the assignment goes to gk (to u itself when k = 0)
    k = rng.choice(lv["k"])
    if kind == "membership" or (kind == "deny" and sub == "user"):
        k = max(k, 1)
    if kind == "membership" and sub == "group_link":
        k = max(k, 2)
    if kind == "membership" and sub == "outer":
        k = min(k, sz["nest"])
    u = new_user(sp)
    gch, prev = [], u
    for _ in range(k):
        prev = new_group(sp, [prev])
        gch.append(prev)
    who = gch[-1] if k else u
    # ---- requested node t and the node a of the designated assignment (t or an ancestor of t)
    dd = rng.choice(lv["tdepth"])
    t = rng.choice([n for n in sp["parent"] if depth(sp, n) == dd])
    path = up(sp, t)
    cands = []
    for a in path:
        dist = path.index(a)
        off = [n for n in strictly_below(sp, a) if n not in path]
        if (kind == "scope" and a == sp["top"]) or (level == 3 and dist == 0):
            continue
        if kind == "sealed" and variant == "structure" and dist == 0:
            continue
        if ((kind == "sealed" and variant == "request") or (kind == "deny" and sub == "node")) and not off:
            continue
        if kind == "scope" and sub == "child" and not [n for n in sp["parent"] if sp["parent"][n] == a and n not in path]:
            continue
        if kind == "scope" and sub == "below" and not strictly_below(sp, t):
            continue
        if kind == "scope" and sub == "above" and depth(sp, a) < 2:
            continue
        cands.append(a)
    if not cands:
        raise Fail("no node for the assignment")
    a = rng.choice(cands)
    dist = path.index(a)
    sp["assignments"].append({"role": chain[0], "who": who, "at": a})
    sp["request"] = {"user": u, "action": act, "node": t}
    desP = {"assign": 0, "carrier": chain[c]}
    between = path[:dist]
    at_above = [n for n in path[dist:] if n != sp["top"]]
    offp = [n for n in sp["parent"] if n not in path]
    protect = [u]
    t2, opts = None, []
    # ---- seals (levels 2 and 3): the planted one for the kind sealed, decoys never between a and the requested node
    if kind == "sealed" and variant == "structure":
        s_new = rng.choice(between)
        s_old = pick_decoy_seal(rng, sp, at_above, offp, [s_new])
        sp["sealed"].append(s_old)
        opts = [(("sealed", s_old, s_new), dict(desP))]
    elif kind == "sealed":
        s = rng.choice([n for n in strictly_below(sp, a) if n not in path])
        t2 = deep_pick(rng, sp, [s] + strictly_below(sp, s))
        sp["sealed"].append(s)
        opts = [(("request", "node", t2), dict(desP))]
    excl = list(between) + ([n for n in up(sp, t2) if a in up(sp, n)[1:]] if t2 else [])
    while len(sp["sealed"]) < sz["sealed"]:
        sp["sealed"].append(pick_decoy_seal(rng, sp, at_above, offp, excl))
    # ---- the planted difference of the other kinds
    if kind == "membership":
        if variant == "structure":
            j = 0 if sub == "user_link" else rng.randint(1, k - 1)
            low = u if j == 0 else gch[j - 1]
            rep = twin_user(sp, u) if j == 0 else twin_group(sp, low, pick_users(rng, sp, rng.randint(1, 2), [u]))
            opts = [(("member", gch[j], low, rep), dict(desP))]
        else:
            u2 = twin_user(sp, u)
            protect.append(u2)
            if sub == "outer":
                mem = [who, u2]
                rng.shuffle(mem)
                new_group(sp, mem)
            else:
                h = twin_group(sp, gch[0], [u2] + pick_users(rng, sp, rng.randint(0, 1), protect))
                if u2 not in gmem(sp, h):
                    gmem(sp, h).append(u2)
                if k >= 2 and rng.random() < 0.7:          # a look-alike chain of the same length that ends in an unassigned group
                    for j in range(1, k):
                        h = twin_group(sp, gch[j], [h] + pick_users(rng, sp, rng.randint(0, 1), protect))
            opts = [(("request", "user", u2), dict(desP))]
    elif kind == "action":
        allowed = role_allows(sp, chain[0])
        if variant == "structure" and sub == "incl":
            li = rng.randrange(m)
            s0, d0 = sp["includes"][li]
            opts = [(("include", li, 1, z), dict(desP)) for z in acts if acts.index(z) < acts.index(s0) and z != d0]
            opts += [(("include", li, 0, z), dict(desP)) for z in acts if acts.index(z) > acts.index(d0) and z != s0]
        elif variant == "structure":
            opts = [(("role_action", chain[c], x, z), dict(desP)) for z in free if z not in own_actions(sp, chain[c])]
        else:
            outside = [z for z in acts if z not in allowed]
            if sub == "reverse":
                pairs = [(z, y) for z in outside for y in allowed if acts.index(y) < acts.index(z)]
                if not pairs:
                    raise Fail("no stronger action")
                z, y = rng.choice(pairs)
                if [z, y] not in sp["includes"]:
                    sp["includes"].append([z, y])
                opts = [(("request", "action", z), dict(desP))]
            else:
                cand = [z for z in outside if not set(closure(sp, [z])) & set(allowed)]
                weak = [z for z in cand if acts.index(z) < acts.index(act)]
                opts = [(("request", "action", z), dict(desP)) for z in (weak if weak and rng.random() < 0.7 else cand)]
        rng.shuffle(opts)
    elif kind == "role_chain":
        if variant == "structure":
            j = 1 if sub == "far_link" else 0
            rz = twin_role(sp, chain[j + 1], rng.sample(free, min(len(free), rng.randint(1, 2))), None)
            opts = [(("role_ext", chain[j], rz), dict(desP))]
        else:
            outside = [z for z in acts if z not in role_allows(sp, chain[0])]
            if not outside:
                raise Fail("the role allows everything")
            weak = [z for z in outside if acts.index(z) < acts.index(act)]
            z = rng.choice(weak if weak and rng.random() < 0.6 else outside)
            rn = new_role(sp, [z], chain[0]) if sub == "reverse" else twin_role(sp, chain[rng.randint(1, clen)], [z], None)
            opts = [(("request", "action", z), {"assign": 0, "carrier": rn})]
    elif kind == "scope":
        if variant == "structure":
            if sub == "side":
                pool = [n for n in sp["parent"] if depth(sp, n) == depth(sp, a) and n not in path]
            elif sub == "below":
                pool = strictly_below(sp, t)
            else:
                pool = [n for n in sp["parent"] if sp["parent"][n] == a and n not in path]
            if not pool:
                raise Fail("no node for the scope difference")
            a2 = rng.choice(pool)
            if sub == "side":
                twin_nodes(sp, a, a2)
            opts = [(("assign_at", 0, a2), dict(desP))]
        else:
            if sub == "twin":
                pool = [n for n in sp["parent"] if depth(sp, n) == depth(sp, t) and a not in up(sp, n)]
                if not pool:
                    raise Fail("no twin node")
                t2 = rng.choice(pool)
                twin_nodes(sp, t, t2)
            else:
                t2 = rng.choice([n for n in up(sp, a)[1:] if n != sp["top"]])
            opts = [(("request", "node", t2), dict(desP))]
    elif kind == "deny":
        whoA = rng.choice(gch[1:]) if len(gch) >= 2 and rng.random() < 0.5 else rng.choice([u] + gch)
        atA = deny_spot(rng, sp, t)
        if variant == "structure":
            dn = {"who": whoA, "action": act, "at": atA}
            if sub == "who":
                dn["who"] = non_principal(rng, sp, u, gch, level, protect)
            elif sub == "action":
                linked = [z for z in acts if z != act and (act in closure(sp, [z]) or z in closure(sp, [act]))]
                dn["action"] = rng.choice(linked if linked and rng.random() < 0.7 else [z for z in acts if z != act])
            else:
                bl = strictly_below(sp, t)
                pool = bl if bl and rng.random() < 0.4 else [n for n in offp if t not in up(sp, n)]
                dn["at"] = rng.choice(pool)
            sp["denies"].append(dn)
            opts = [(("deny", 0, sub, {"who": whoA, "action": act, "at": atA}[sub]), dict(desP))]
        elif sub == "action":
            others = [z for z in role_allows(sp, chain[0]) if z != act]
            if not others:
                raise Fail("the role allows one action only")
            z = rng.choice(others)
            sp["denies"].append({"who": whoA, "action": z, "at": atA})
            car = next(r for r in role_chain(sp, chain[0]) if z in closure(sp, own_actions(sp, r)))
            opts = [(("request", "action", z), {"assign": 0, "carrier": car})]
        elif sub == "node":
            pool = [n for n in strictly_below(sp, a) if n not in path and covers(sp, a, n)]
            if not pool:
                raise Fail("no second node")
            t2 = deep_pick(rng, sp, pool)
            dnode = rng.choice([n for n in up(sp, t2) if n not in path and a in up(sp, n)])
            sp["denies"].append({"who": whoA, "action": act, "at": dnode})
            opts = [(("request", "node", t2), dict(desP))]
        else:
            u3 = new_user(sp)
            protect.append(u3)
            gmem(sp, gch[rng.randrange(k)]).append(u3)
            dw = u3 if rng.random() < 0.5 else new_group(sp, [u3] + pick_users(rng, sp, rng.randint(1, 2), protect))
            sp["denies"].append({"who": dw, "action": act, "at": atA})
            opts = [(("request", "user", u3), dict(desP))]
    for e, dN in opts:
        if pair_ok(sp, e, desP, dN, kind, level):
            break
    else:
        raise Fail("no planted difference passes")
    facts = k + 1 + (c + 1) + m + dist
    if level == 3 and facts < 6:
        raise Fail("level 3 path too short")
    ctx = {"u": u, "act": act, "x": x, "t": t, "a": a, "gch": gch, "chain": chain, "protect": protect}
    info = {"sub": sub, "k": k, "clen": clen, "c": c, "m": m, "dist": dist, "path_facts": facts}
    return sp, e, desP, dN, ctx, info

# ------------------------------------------------------------------------------------------------ decoys and background
DECOYS = {1: ["twin_group", "twin_user", "side", "below", "weak"],
          2: ["nest_dir", "twin_group", "twin_user", "side", "below", "blocked", "weak", "rev_ext"],
          3: ["nest_dir", "twin_group", "twin_user", "side", "below", "blocked", "weak", "rev_ext"]}
N_DECOY = {1: (2, 3), 2: (3, 4), 3: (4, 6)}
DENY_DECOYS = ["other_action", "sibling", "below", "other_who"]


def decorate(rng, sp, level, kind, edit, desP, desN, ctx):
    """near-miss assignments (each fails in one link), deny entries that do not apply, background; the decoys are built around
    the request of the positive or of the negative (drawn per decoy), and every addition is kept only when the pair still passes"""
    sz = SIZES[level]
    protect = ctx["protect"]
    FP = dict(sp["request"])
    FN = dict(apply_edit(sp, edit)["request"])
    foci = [FP] if FP == FN else [FP, FN]
    kept = {"decoys": [], "deny_decoys": []}

    def attempt(fn, focus=None):
        s2 = copy.deepcopy(sp)
        try:
            fn(s2, focus or (foci[-1] if rng.random() < 0.65 else foci[0]))
        except (Fail, IndexError, ValueError, StopIteration):
            return False
        if not pair_ok(s2, edit, desP, desN, kind, level):
            return False
        sp.clear()
        sp.update(s2)
        return True

    def cov(s, F):
        return [y for y in up(s, F["node"]) if covers(s, y, F["node"])]

    def stable(s, r):
        """the planted difference does not change what this role allows for the request(s)"""
        try:
            sN = apply_edit(s, edit)
            return all((F_["action"] in role_allows(s, r)) == (F_["action"] in role_allows(sN, r)) for F_ in foci)
        except (ValueError, StopIteration, KeyError, IndexError):
            return False

    def act_role(s, F):
        rs = [q["name"] for q in s["roles"] if F["action"] in role_allows(s, q["name"]) and stable(s, q["name"])]
        if rs and rng.random() < 0.75:
            return rng.choice(rs)
        if rng.random() < 0.5:
            return new_role(s, [F["action"]])
        return new_role(s, [rng.choice([z for z in s["actions"] if F["action"] in closure(s, [z])])])

    def principal(s, F):
        return rng.choice(principals(s, F["user"]))

    def side_nodes(s, F):
        return [n for n in s["parent"] if n not in up(s, F["node"]) and F["node"] not in up(s, n)]

    def fgroups(s, F):
        return groups_of(s, F["user"])

    def d_nest_dir(s, F):
        gs = fgroups(s, F)
        if level < 2 or not gs:
            raise Fail
        gi = new_group(s, pick_users(rng, s, rng.randint(1, 2), protect))
        gmem(s, rng.choice(gs)).append(gi)
        s["assignments"].append({"role": act_role(s, F), "who": gi, "at": rng.choice(cov(s, F))})

    def d_twin_group(s, F):
        gs = fgroups(s, F)
        if not gs:
            raise Fail
        h = twin_group(s, rng.choice(gs), pick_users(rng, s, rng.randint(1, 2), protect))
        s["assignments"].append({"role": act_role(s, F), "who": h, "at": rng.choice(cov(s, F))})

    def d_twin_user(s, F):
        s["assignments"].append({"role": act_role(s, F), "who": twin_user(s, F["user"]), "at": rng.choice(cov(s, F))})

    def d_side(s, F):
        n = rng.choice(side_nodes(s, F))
        same = [p for p in up(s, F["node"]) if depth(s, p) == depth(s, n)]
        if same and rng.random() < 0.5:
            twin_nodes(s, same[0], n)
        s["assignments"].append({"role": act_role(s, F), "who": principal(s, F), "at": n})

    def d_below(s, F):
        s["assignments"].append({"role": act_role(s, F), "who": principal(s, F), "at": rng.choice(strictly_below(s, F["node"]))})

    def d_blocked(s, F):
        p = up(s, F["node"])
        pos = [i for i, n in enumerate(p) if n in s["sealed"]]
        if not pos:
            raise Fail
        s["assignments"].append({"role": act_role(s, F), "who": principal(s, F), "at": rng.choice(p[min(pos) + 1:])})

    def d_weak(s, F):
        rs = [q["name"] for q in s["roles"] if F["action"] not in role_allows(s, q["name"])]
        if rs and rng.random() < 0.6:
            r = rng.choice(rs)
        else:
            fr = [z for z in s["actions"] if F["action"] not in closure(s, [z])]
            r = new_role(s, rng.sample(fr, min(len(fr), rng.randint(1, 2))))
        s["assignments"].append({"role": r, "who": principal(s, F), "at": rng.choice(cov(s, F))})

    def d_rev_ext(s, F):
        if level < 2:
            raise Fail
        ry = new_role(s, [rng.choice([z for z in s["actions"] if F["action"] not in closure(s, [z])])])
        new_role(s, [rng.choice([z for z in s["actions"] if F["action"] in closure(s, [z])])], ry)
        s["assignments"].append({"role": ry, "who": principal(s, F), "at": rng.choice(cov(s, F))})

    def x_other_action(s, F):
        a0 = F["action"]
        linked = [z for z in s["actions"] if z != a0 and (a0 in closure(s, [z]) or z in closure(s, [a0]))]
        pool = linked if linked and rng.random() < 0.7 else [z for z in s["actions"] if z != a0]
        s["denies"].append({"who": principal(s, F), "action": rng.choice(pool), "at": deny_spot(rng, s, F["node"])})

    def x_sibling(s, F):
        s["denies"].append({"who": principal(s, F), "action": F["action"], "at": rng.choice(side_nodes(s, F))})

    def x_below(s, F):
        s["denies"].append({"who": principal(s, F), "action": F["action"], "at": rng.choice(strictly_below(s, F["node"]))})

    def x_other_who(s, F):
        w = non_principal(rng, s, F["user"], fgroups(s, F), level, protect)
        s["denies"].append({"who": w, "action": F["action"], "at": deny_spot(rng, s, F["node"])})

    def b_user(s, F):
        v = new_user(s)
        gs = [g["name"] for g in s["groups"]]
        for g in rng.sample(gs, min(len(gs), rng.randint(1, 2))):
            gmem(s, g).append(v)

    def b_group(s, F):
        mem = pick_users(rng, s, rng.randint(1, 3), protect)
        if level >= 2 and rng.random() < 0.35:
            pr = principals(s, F["user"])
            gs = [g["name"] for g in s["groups"] if g["name"] not in pr]
            if gs:
                mem.append(rng.choice(gs))
        g = new_group(s, mem)
        if level >= 2 and rng.random() < 0.3:
            gmem(s, rng.choice([h["name"] for h in s["groups"] if h["name"] != g])).append(g)

    def b_role(s, F):
        ext = rng.choice([r["name"] for r in s["roles"]]) if level >= 2 and rng.random() < 0.35 else None
        new_role(s, rng.sample(s["actions"], rng.randint(1, 2)), ext)

    def b_assign(s, F):
        rs = [r["name"] for r in s["roles"]]
        st = [r for r in rs if stable(s, r)]
        s["assignments"].append({"role": rng.choice(st if st and rng.random() < 0.8 else rs),
                                 "who": rng.choice(s["users"] + [g["name"] for g in s["groups"]]),
                                 "at": rng.choice([s["top"]] + list(s["parent"]))})

    def b_include(s, F):
        i, j = sorted(rng.sample(range(len(s["actions"])), 2), reverse=True)
        s["includes"].append([s["actions"][i], s["actions"][j]])

    def b_req(user):
        def fn(s, F):
            gs = [g["name"] for g in s["groups"] if g["name"] not in groups_of(s, user)]
            if gs and rng.random() < 0.8:
                gmem(s, rng.choice(gs)).append(user)
            else:
                new_group(s, [user] + pick_users(rng, s, rng.randint(1, 2), protect))
        return fn

    dfn = {"nest_dir": d_nest_dir, "twin_group": d_twin_group, "twin_user": d_twin_user, "side": d_side, "below": d_below,
           "blocked": d_blocked, "weak": d_weak, "rev_ext": d_rev_ext}
    xfn = {"other_action": x_other_action, "sibling": x_sibling, "below": x_below, "other_who": x_other_who}
    n_dec, tries = rng.randint(*N_DECOY[level]), 0
    while len(kept["decoys"]) < n_dec and tries < 8 * n_dec:
        tries += 1
        nm = rng.choice(DECOYS[level])
        if attempt(dfn[nm]):
            kept["decoys"].append(nm)
    if level == 3:
        n_den = rng.randint(2, 3)
    elif level == 2 and (kind == "deny" or rng.random() < 0.4):
        n_den = rng.randint(1, 2)
    else:
        n_den = 0
    tries = 0
    while len(sp["denies"]) < n_den and tries < 30:
        tries += 1
        nm = rng.choice(DENY_DECOYS)
        if attempt(xfn[nm]):
            kept["deny_decoys"].append(nm)
    for user in sorted({FP["user"], FN["user"]}):
        for _ in range(8):
            if attempt(b_req(user)):
                break
    target = {key: rng.randint(*sz[key]) for key in ("users", "groups", "roles", "assigns", "incl")}
    count = {"users": lambda: len(sp["users"]), "groups": lambda: len(sp["groups"]), "roles": lambda: len(sp["roles"]),
             "assigns": lambda: len(sp["assignments"]), "incl": lambda: len(sp["includes"])}
    bfn = {"users": b_user, "groups": b_group, "roles": b_role, "assigns": b_assign, "incl": b_include}
    for _ in range(120):
        need = [key for key in target if count[key]() < target[key]]
        if not need:
            break
        attempt(bfn[rng.choice(need)])
    # when the two requests differ: the negative's requester has as many groups, its action as many roles and assignments
    # that allow it, as the positive's (so that these counts do not tell the classes apart)
    n_pr = lambda s, F: len(principals(s, F["user"]))
    n_ro = lambda s, F: sum(F["action"] in role_allows(s, r["name"]) for r in s["roles"])
    n_as = lambda s, F: sum(F["action"] in role_allows(s, a["role"]) for a in s["assignments"])
    for _ in range(16 if FP != FN else 0):
        gaps = []
        for what, fn in (("pr", n_pr), ("ro", n_ro), ("as", n_as)):
            dlt = fn(sp, FP) - fn(sp, FN)
            if dlt:
                gaps.append((what, FN if dlt > 0 else FP))
        if not gaps:
            break
        what, F = rng.choice(gaps)
        if what == "pr":
            attempt(b_req(F["user"]), F)
        elif what == "ro":
            attempt(lambda s, F_: new_role(s, [F_["action"]] if rng.random() < 0.6 else rng.sample(s["actions"], 1) + [F_["action"]]), F)
        else:
            attempt(dfn[rng.choice(["side", "below", "twin_user", "twin_group", "nest_dir", "blocked"])], F)
    for _ in range(rng.randint(1, 3)):                     # more look-alike names (naming only)
        pool = [n for n in sp["parent"] if twin_of(sp, "node", n) is None]
        if len(pool) < 2:
            break
        n1 = rng.choice(pool)
        same = [n for n in pool if n != n1 and depth(sp, n) == depth(sp, n1) and sp["parent"][n] != sp["parent"][n1]]
        if same:
            twin_nodes(sp, n1, rng.choice(same))
    assert pair_ok(sp, edit, desP, desN, kind, level)
    return kept


# ------------------------------------------------------------------------------------------------ names, order, text
ROLE_END = ["an", "en", "or", "is", "ex", "um", "al", "id"]
GROUP_B_BY_LEN = {3: ["red", "day", "one", "two"], 4: ["east", "west", "blue", "beta", "late"], 5: ["green", "amber", "alpha"]}


def syll(rng, used, role=False):
    for _ in range(2000):
        w = rng.choice(ONS) + rng.choice(VOW) + rng.choice(MID) + (rng.choice(VOW) + rng.choice(COD) if not role else "")
        if w not in used and w not in BLOCK:
            used.add(w)
            return w
    raise Fail("out of names")


def assign_names(rng, sp):
    D, tw, mp, used = DOMAINS[sp["domain"]], sp["_tw"], {}, set()
    for a, b in tw["user"]:
        s = syll(rng, used)
        i1, i2 = rng.sample(INITIALS, 2)
        mp[a], mp[b] = i1 + "." + s, i2 + "." + s
    for x in sp["users"]:
        if x not in mp:
            mp[x] = rng.choice(INITIALS) + "." + syll(rng, used)
    for a, b in tw["role"]:
        st = syll(rng, used, True)
        e1, e2 = rng.sample(ROLE_END, 2)
        mp[a], mp[b] = st + e1, st + e2
    for r in sp["roles"]:
        if r["name"] not in mp:
            mp[r["name"]] = syll(rng, used, True) + rng.choice(ROLE_END)
    gnames = [g["name"] for g in sp["groups"]]
    firsts = list(GROUP_A)
    rng.shuffle(firsts)
    if len(gnames) - len(tw["group"]) > len(firsts):
        raise Fail("too many groups")
    for a, b in tw["group"]:
        f = firsts.pop()
        s1, s2 = rng.sample(GROUP_B_BY_LEN[rng.choice([3, 4, 5])], 2)
        mp[a], mp[b] = f + "-" + s1, f + "-" + s2
    for g in gnames:
        if g not in mp:
            mp[g] = firsts.pop() + "-" + rng.choice(GROUP_B)
    bases = list(D["bases"])
    rng.shuffle(bases)
    if len(sp["parent"]) - len(tw["node"]) > len(bases):
        raise Fail("too many nodes")
    for a, b in tw["node"]:
        base = bases.pop()
        s1, s2 = rng.choice(D["twins"])
        if rng.random() < 0.5:
            s1, s2 = s2, s1
        mp[a], mp[b] = base + s1, base + s2
    for n in sp["parent"]:
        if n not in mp:
            base = bases.pop()
            mp[n] = base + rng.choice(rng.choice(D["twins"])) if rng.random() < 0.2 else base
    mp[sp["top"]] = rng.choice(D["tops"])
    assert len(set(mp.values())) == len(mp), "name clash"
    return mp


def rename(obj, mp):
    if isinstance(obj, str):
        return mp.get(obj, obj)
    if isinstance(obj, (list, tuple)):
        return type(obj)(rename(x, mp) for x in obj)
    if isinstance(obj, dict):
        return {rename(k, mp): rename(v, mp) for k, v in obj.items()}
    return obj


def shuffle_spec(rng, sp, edit, desP, desN):
    """one random order of every list for both members of the pair; indices in the edit and the paths are remapped"""
    perm = {}
    for key in ("assignments", "denies", "includes", "groups", "roles", "users", "sealed"):
        order = list(range(len(sp[key])))
        rng.shuffle(order)
        sp[key] = [sp[key][i] for i in order]
        perm[key] = {old: new for new, old in enumerate(order)}
    for g in sp["groups"]:
        rng.shuffle(g["members"])
    for r in sp["roles"]:
        r["actions"].sort(key=sp["actions"].index)
    items = list(sp["parent"].items())
    rng.shuffle(items)
    sp["parent"] = dict(items)
    e = list(edit)
    if e[0] in ("include", "assign_at", "deny"):
        e[1] = perm[{"include": "includes", "assign_at": "assignments", "deny": "denies"}[e[0]]][e[1]]
    dP, dN = dict(desP), dict(desN)
    dP["assign"] = perm["assignments"][desP["assign"]]
    dN["assign"] = perm["assignments"][desN["assign"]]
    return tuple(e), dP, dN


HEADERS = ["Access export of an invented {what}. The rules in this export decide every request.",
           "Permission data of a fictional {what}, followed by the rules that govern it.",
           "What follows are the access rules and the current permission records of an invented {what}."]
TITLES = {"rules": ["Rules:", "How access is decided:", "Access rules (they apply exactly as written):"],
          "actions": ["Actions:", "Actions of this system:", "Known actions:"],
          "includes": ["Listed inclusions (only these exist):", "Inclusions between actions:", "Inclusion list:"],
          "roles": ["Roles:", "Role definitions:", "Roles and what they allow:"],
          "users": ["Users:", "User accounts:", "People with an account:"],
          "groups": ["Groups:", "Groups and their members:", "Group membership lists:"],
          "sealed": ["Sealed {nodes}:", "{Nodes} marked as sealed:", "Seals:"],
          "assign": ["Assignments:", "Role assignments:", "Who holds which role where:"],
          "deny": ["Deny entries:", "Denials:", "Explicit deny entries:"]}
TREE_TITLES = ["{Nodes} (each line: a {node} and the {node} it lies in):", "{Node} tree (each line: a {node} and its parent):",
               "{Nodes} as full paths from the top {node} (parts separated by /):"]
REQUESTS = ["Request: user {user} asks to {action} at the {node} {n}.",
            "Request under review: {user} wants to {action} on {node} {n}.",
            "The request: may user {user} {action} in the {node} {n}?"]


def render(sp, level, look):
    D = DOMAINS[sp["domain"]]
    node, nodes = D["node"], D["nodes"]
    fill = {"node": node, "nodes": nodes, "Node": node.capitalize(), "Nodes": nodes.capitalize()}
    users = set(sp["users"])
    kind = lambda w: "user" if w in users else "group"
    T = lambda key: TITLES[key][look["t_" + key]].format(**fill)
    rec = look["rec"]
    rules = [(WHO_FLAT if level == 1 else WHO_NESTED)[look["who"]], WHERE[look["where"]]]
    if level >= 2:
        rules.append(SEAL[look["seal"]])
    rules += [(ROLE_FLAT if level == 1 else ROLE_EXT)[look["role"]], INCL[look["incl"]]]
    if sp["denies"]:
        rules.append(DENY[look["deny"]])
    dk = {k: (v if sp["denies"] else "") for k, v in DECIDE_DENY.items()}
    rules.append(DECIDE[look["decide"]].format(**dk, **fill))
    rules = [r.format(**fill) for r in rules]
    sec = {"header": [HEADERS[look["header"]].format(what=D["what"])],
           "rules": [T("rules")] + [("%d. " % (i + 1) if look["num"] == 0 else "- ") + r for i, r in enumerate(rules)]}
    sep = ", " if rec == 0 else " | "
    sec["actions"] = [T("actions") + " " + sep.join(sp["actions"])]
    sec["includes"] = [T("includes")] + [("- %s includes %s" if rec == 0 else "inclusion: %s includes %s") % (a, b) for a, b in sp["includes"]]
    rl = [T("roles")]
    for r in sp["roles"]:
        if rec == 0:
            rl.append("- role %s: allows %s" % (r["name"], ", ".join(r["actions"])) + ("; extends role %s" % r["extends"] if r["extends"] else ""))
        else:
            rl.append("role: %s | allows: %s" % (r["name"], ", ".join(r["actions"])) + (" | extends: %s" % (r["extends"] or "none") if level >= 2 else ""))
    sec["roles"] = rl
    sec["users"] = [T("users") + " " + sep.join(sp["users"])]
    gl = [T("groups")]
    for g in sp["groups"]:
        mem = ", ".join("%s %s" % (kind(m), m) for m in g["members"])
        gl.append(("- group %s: members %s" if rec == 0 else "group: %s | members: %s") % (g["name"], mem))
    sec["groups"] = gl
    tl = [TREE_TITLES[look["tree"]].format(**fill)]
    if look["tree"] == 0:
        tl.append("- %s is the top %s" % (sp["top"], node))
        tl += ["- %s lies in %s" % (n, p) for n, p in sp["parent"].items()]
    elif look["tree"] == 1:
        tl.append("- %s (top %s, no parent)" % (sp["top"], node))
        tl += ["- %s (parent: %s)" % (n, p) for n, p in sp["parent"].items()]
    else:
        tl.append("- " + sp["top"])
        tl += ["- " + "/".join(reversed(up(sp, n))) for n in sp["parent"]]
    sec["tree"] = tl
    sec["sealed"] = ([T("sealed")] + [("- %s" if rec == 0 else "sealed " + node + ": %s") % s for s in sp["sealed"]]) if level >= 2 else []
    al = [T("assign")]
    for a in sp["assignments"]:
        if rec == 0:
            al.append("- role %s given to %s %s at %s %s" % (a["role"], kind(a["who"]), a["who"], node, a["at"]))
        else:
            al.append("assignment: role %s | holder: %s %s | %s: %s" % (a["role"], kind(a["who"]), a["who"], node, a["at"]))
    sec["assign"] = al
    dl = [T("deny")] if sp["denies"] else []
    for d in sp["denies"]:
        if rec == 0:
            dl.append("- deny %s to %s %s at %s %s" % (d["action"], kind(d["who"]), d["who"], node, d["at"]))
        else:
            dl.append("deny: action %s | for: %s %s | %s: %s" % (d["action"], kind(d["who"]), d["who"], node, d["at"]))
    sec["deny"] = dl
    rq = sp["request"]
    sec["request"] = [REQUESTS[look["req"]].format(user=rq["user"], action=rq["action"], node=node, n=rq["node"])]
    order = (["header", "rules", "actions", "includes", "roles", "users", "groups", "tree", "sealed", "assign", "deny", "request"]
             if look["order"] == 0 else
             ["header", "request", "rules", "tree", "sealed", "users", "groups", "actions", "includes", "roles", "assign", "deny"])
    return "\n\n".join("\n".join(sec[k]) for k in order if sec[k])


def draw_look(rng):
    look = {k: rng.randrange(3) for k in ("header", "who", "where", "seal", "role", "incl", "deny", "decide", "tree", "req")}
    look.update({"t_" + k: rng.randrange(3) for k in TITLES})
    look.update({"rec": rng.randrange(2), "order": rng.randrange(2), "num": rng.randrange(2)})
    return look

# ------------------------------------------------------------------------------------------------ plan, items, checks
SLOPPY = [("membership through nesting ignored", {"nesting": "none"}), ("nesting read in both directions", {"nesting": "both"}),
          ("assignments cover every node", {"scope": "any"}), ("assignments also cover upward", {"scope": "updown"}),
          ("seals ignored", {"seal": "none"}), ("any seal on the way refuses", {"seal": "any"}),
          ("role extension ignored", {"ext": "none"}), ("extension read in both directions", {"ext": "both"}),
          ("inclusions ignored", {"incl": "none"}), ("inclusions read in both directions", {"incl": "both"}),
          ("deny entries ignored", {"deny": "none"}), ("deny entries only for direct members", {"deny": "direct"}),
          ("a deny blocks every action", {"deny": "any_action"}), ("a deny also blocks linked actions", {"deny": "linked"}),
          ("seals also stop deny entries", {"deny": "seal_stops"})]
TOK = re.compile(r"[a-z0-9_]+")


def make_plan():
    rng = rng_for("plan")
    plan = []
    for level in (1, 2, 3):
        rows = []
        for kind in KINDS:
            if kind in PLAN[level]:
                nr, ns = PLAN[level][kind]
                rows += [(kind, "request", j) for j in range(nr)] + [(kind, "structure", j) for j in range(ns)]
        doms = [DOMAIN_ORDER[j % len(DOMAIN_ORDER)] for j in range(len(rows))]
        rng.shuffle(doms)
        rng.shuffle(rows)
        plan += [{"level": level, "kind": k, "variant": v, "sub_i": j, "domain": d} for (k, v, j), d in zip(rows, doms)]
    return plan


def build_pair(i, p, avoid):
    """derived generators per attempt; when the running balance of length differences asks for it, a pair whose negative is
    longer (or shorter) than its positive is passed over up to 12 times"""
    subs = subs_for(p["level"], p["kind"], p["variant"])
    first = None
    for attempt in range(800):
        rng = rng_for("pair", i, attempt)
        sub = subs[p["sub_i"] % len(subs)] if attempt < 400 else rng.choice(subs)
        try:
            sp, edit, dP, dN, ctx, info = build_core(rng, p["level"], p["kind"], p["variant"], sub, p["domain"])
            kept = decorate(rng, sp, p["level"], p["kind"], edit, dP, dN, ctx)
            edit, dP, dN = shuffle_spec(rng, sp, edit, dP, dN)
            mp = assign_names(rng, sp)
        except Fail:
            continue
        sp.pop("_tw")
        P, edit, dP, dN = rename(sp, mp), rename(edit, mp), rename(dP, mp), rename(dN, mp)
        assert pair_ok(P, edit, dP, dN, p["kind"], p["level"]), (i, p)
        N, look = apply_edit(P, edit), draw_look(rng)
        tP, tN = render(P, p["level"], look), render(N, p["level"], look)
        sign = (len(tN) > len(tP)) - (len(tN) < len(tP))
        res = (P, N, edit, dP, dN, info, kept, tP, tN, sign)
        if avoid is None or sign != avoid:
            return res
        first = first or [res, 0]
        first[1] += 1
        if first[1] >= 12:
            return first[0]
    raise RuntimeError("pair %d (%s) could not be built" % (i, p))


def assign_orders(rows):
    rng = rng_for("options")
    for level in (1, 2, 3):
        for gold in ("yes", "no"):
            idx = [i for i, r in enumerate(rows) if r["gold"] == gold and r["meta"]["level"] == level]
            flags = [True] * (len(idx) // 2) + [False] * (len(idx) - len(idx) // 2)
            rng.shuffle(flags)
            for i, first in zip(idx, flags):
                order = ["yes", "no"] if first else ["no", "yes"]
                rows[i]["questions"]["q"]["criteria"] = {k: OPTIONS[k] for k in order}
                rows[i]["meta"]["order"] = order


def vocab_test(rows):
    """the test of audit_v3: words of frequency >= 20 (states containing them); the rate in one class at most twice the other"""
    n1 = sum(r["gold"] == "yes" for r in rows)
    a, b = collections.Counter(), collections.Counter()
    for r in rows:
        (a if r["gold"] == "yes" else b).update(set(re.findall(r"[a-z]+", r["state"].lower())))
    worst, tested = (1.0, ""), 0
    for w in sorted(set(a) | set(b)):
        if a[w] + b[w] < 20:
            continue
        tested += 1
        ra, rb = a[w] / n1, b[w] / (len(rows) - n1)
        ratio = max(ra, rb) / min(ra, rb) if min(ra, rb) > 0 else float("inf")
        if ratio > worst[0]:
            worst = (ratio, w)
    assert worst[0] <= 2.0, worst
    return tested, worst


def main():
    plan = make_plan()
    built, rows, bal = [], [], 0
    for i, p in enumerate(plan):
        P, N, edit, dP, dN, info, kept, tP, tN, sign = build_pair(i, p, (bal > 0) - (bal < 0) if bal else None)
        bal += sign
        la, lb = tP.split("\n"), tN.split("\n")
        assert len(la) == len(lb) and sum(x != y for x, y in zip(la, lb)) == 1, (i, p)
        assert set(TOK.findall(tP.lower())) == set(TOK.findall(tN.lower())), (i, p, edit)
        assert truth(P) and not truth(N) and judge(P) and not judge(N)
        built.append((i, p, P, tP, None, edit, dP, info, kept))
        built.append((i, p, N, tN, p["kind"], edit, dN, info, kept))
    rng = rng_for("order")
    rng.shuffle(built)
    for n, (i, p, spec, text, dev, edit, des, info, kept) in enumerate(built, 1):
        meta = {"source_id": "%05d" % n, "level": p["level"], "domain": p["domain"], "deviation": dev, "order": None,
                "variant": p["variant"], "sub": info["sub"], "pair": i + 1, "seed": SEED, "edit": list(edit), "path": des,
                "path_facts": info["path_facts"], "membership_links": info["k"], "extension_links": info["c"],
                "inclusion_steps": info["m"], "tree_steps": info["dist"], "decoys": kept["decoys"],
                "deny_decoys": kept["deny_decoys"], "spec": spec}
        rows.append({"id": "%s%05d" % (ID_PREFIX, n), "state": text,
                     "questions": {"q": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": dict(OPTIONS)}},
                     "gold": "no" if dev else "yes", "soft": None, "group": "%sg%04d" % (ID_PREFIX, i + 1), "meta": meta})
    assign_orders(rows)
    # ---- checks over the whole set
    for r in rows:
        assert truth(r["meta"]["spec"]) == (r["gold"] == "yes") == judge(r["meta"]["spec"]), r["id"]
        assert 600 <= len(r["state"]) <= 14000, (r["id"], len(r["state"]))
    assert len({r["state"] for r in rows}) == len(rows), "duplicate state"
    cls = collections.Counter((r["meta"]["level"], r["gold"]) for r in rows)
    assert all(cls[(lv, g)] == 100 for lv in (1, 2, 3) for g in ("yes", "no")), cls
    dev = collections.Counter((r["meta"]["level"], r["meta"]["deviation"]) for r in rows if r["gold"] == "no")
    for lv in (1, 2, 3):
        for kd, (nr, ns) in PLAN[lv].items():
            assert dev[(lv, kd)] == nr + ns, (lv, kd)
    var = collections.Counter((r["meta"]["level"], r["meta"]["variant"]) for r in rows if r["gold"] == "no")
    assert all(var[(lv, v)] == 50 for lv in (1, 2, 3) for v in ("request", "structure")), var
    pos = collections.Counter((r["meta"]["level"], r["gold"], r["meta"]["order"][0]) for r in rows)
    assert all(pos[(lv, g, "yes")] == 50 for lv in (1, 2, 3) for g in ("yes", "no")), pos
    assert all(r["meta"]["path_facts"] >= 6 for r in rows if r["meta"]["level"] == 3)
    tested, worst = vocab_test(rows)
    word_count = {w: {g: sum(len(re.findall(r"\b%s\b" % w, r["state"].lower())) for r in rows if r["gold"] == g) for g in ("yes", "no")}
                  for w in ("deny", "sealed")}
    assert all(v["yes"] == v["no"] for v in word_count.values()), word_count
    by_pair = collections.defaultdict(dict)
    for r in rows:
        by_pair[r["meta"]["pair"]][r["gold"]] = len(r["state"])
    ld = collections.Counter((v["no"] > v["yes"]) - (v["no"] < v["yes"]) for v in by_pair.values())
    sloppy = []
    for name, sw in SLOPPY:
        acc = [sum(judge(r["meta"]["spec"], **sw) == (r["gold"] == "yes") for r in rows if r["meta"]["level"] == lv) / 200 for lv in (1, 2, 3)]
        sloppy.append((name, acc))
    lens = {lv: sorted(len(r["state"]) for r in rows if r["meta"]["level"] == lv) for lv in (1, 2, 3)}
    # ---- files
    d = os.path.join(OUT_ROOT, TASK)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "items.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    split = "generated, seed %d" % SEED if not _ENV_SEED else "generated, sealed split, seed %d" % SEED
    task = {"task": TASK, "layer": "B", "title": "Generated access exports: is the request allowed under the written inheritance rules?",
            "decision": ("whether one user may perform one action on one node of an invented access system, given roles with "
                         "extension, nested groups, assignments at nodes, sealed nodes, inclusions between actions and deny entries"),
            "source": {"name": "generator build/gen_%s.py" % TASK, "url": "", "files": [], "split": split, "version": "script of 2026-10-07"},
            "licence": "generated by the benchmark's script (no third-party text)", "redistribution": "items included",
            "labels": "programmatic", "item_source": "generated", "metric": "accuracy", "chance": 0.5, "rows": len(rows),
            "groups": len(by_pair), "question_type": "choice", "options": 2,
            "skill": "follow an access decision through nested groups, role extension, action inclusion, a node tree with seals and deny entries",
            "knobs": "level (1-3): nesting depth of groups 0/1/2, role extension chain 0/1/2, tree depth 2/3/4, sealed nodes 0/1/2, deny entries 0/0-2/2-3, users 4-6/6-9/10-14, near-miss decoy paths 2-3/3-4/4-6",
            "notes": ("600 items = 300 contrast pairs (group): the negative is the positive with ONE line changed - the request line "
                      "(150 pairs) or one line of the structure (150 pairs) - so that exactly one link of the only allowing path breaks "
                      "(meta.deviation: membership, sealed, role_chain, action, scope, deny). Everything is invented; truth by code on "
                      "meta.spec; the two members of a pair have the same number of lines and the same set of words.")}
    json.dump(task, open(os.path.join(d, "task.json"), "w"), indent=1)
    write_readme(d, rows, dev, var, lens, tested, worst, word_count, ld, sloppy)
    print("rows", len(rows), "| pairs", len(by_pair), "| vocabulary: %d words tested, worst ratio %.2f (%s)" % (tested, worst[0], worst[1]))
    print("length of the negative vs the positive (shorter / equal / longer):", ld[-1], ld[0], ld[1])
    for lv in (1, 2, 3):
        print("level %d: chars min %d median %d max %d" % (lv, lens[lv][0], lens[lv][100], lens[lv][-1]))
    print("deviation x level:", {"%s/%d" % (k, lv): dev[(lv, k)] for lv in (1, 2, 3) for k in KINDS if dev[(lv, k)]})
    for name, acc in sloppy:
        print("  sloppy %-40s %.3f %.3f %.3f" % (name, *acc))


def fmt_example(r):
    m = r["meta"]
    out = ["id `%s` (group `%s`, level %d, domain %s, gold **%s**, deviation `%s`, variant %s, planted edit `%s`)" %
           (r["id"], r["group"], m["level"], m["domain"], r["gold"], m["deviation"], m["variant"], json.dumps(m["edit"])),
           "", "```", r["state"], "```", "", "question: " + r["questions"]["q"]["instructions"], ""]
    out += ["- `%s`: %s" % (k, v) for k, v in r["questions"]["q"]["criteria"].items()]
    return "\n".join(out)


def write_readme(d, rows, dev, var, lens, tested, worst, word_count, ld, sloppy):
    ex = [next(r for r in rows if r["meta"]["level"] == lv and r["gold"] == g) for lv, g in ((1, "no"), (2, "yes"), (3, "no"))]
    kinds_tab = "\n".join("| `%s` | %s |" % (k, " | ".join(str(dev[(lv, k)]) for lv in (1, 2, 3))) for k in KINDS)
    slop = "\n".join("| %s | %s |" % (n, " | ".join("%.3f" % a for a in acc)) for n, acc in sloppy)
    txt = f"""# {TASK}

Generated access exports: is the request allowed? (layer B, generated, programmatic truth). EVALUATION ONLY.

- Decision: whether one user may perform one action on one node (folder, namespace, section, zone, collection) of an invented
  access system, under conventions that are written into every state.
- Source: generator `build/gen_{TASK}.py` (Python 3.9, standard library, `random.Random` generators derived from seed {SEED}; two runs give
  identical files). `BENCH_OUT=<dir>` writes elsewhere; `BENCH_SEED=<int>` (only with `BENCH_OUT`) builds a sealed split of the same design.
- Rows: {len(rows)} = 300 contrast pairs (`group`), 200 per level, 100 yes and 100 no per level. Metric: accuracy (chance 0.5).
  The option order is drawn per item (`meta.order`; half of the yes rows and half of the no rows of each level list `yes` first).

## What is generated

The state is an access export of an invented system in one of five domains (document workspace, code hosting service, records
system, building access system, data catalogue): the rules in plain words, the actions, the listed inclusions between actions, the
roles (own actions; from level 2 a role may extend one other role), the users, the groups (members are users and, from level 2,
other groups), the node tree (three layouts: "X lies in Y", "X (parent: Y)", full paths), the sealed nodes (levels 2-3), the
assignments (a role given to a user or a group AT a node), the deny entries (level 3, some items of level 2) and one request
(user, action, node). Two record layouts (sentences or `field: value | ...` records), two section orders, three phrasings of every
rule, title and request sentence. Names come from syllable generators (users `x.surname`, groups `first-second`, roles one word,
nodes domain words with suffixes); look-alike pairs (same surname / same first part / same stem / same base) are planted.

## Conventions written in every state

1. Membership: an assignment to a group counts for all its members; from level 2 membership passes upward through nested groups
   (a member of X is a member of every group that lists X), never downward.
2. Scope: an assignment covers its node and everything below it, nothing beside or above it.
3. Seals (levels 2-3): an assignment made above a sealed node covers neither that node nor anything below it; an assignment made at the
   sealed node or below it is not affected; seals elsewhere have no effect.
4. Roles: a role allows its own actions plus everything of the role it extends, along the chain, one way only.
5. Inclusions: only the listed inclusions exist; they chain and never run backwards.
6. Deny entries: a deny (user or group, action, node) applies when the requester is that user or a (nested) member of that group, the
   requested action is exactly that action and the requested node is that node or below it - seals do not stop it; it beats every
   assignment; it blocks no other action, also not one linked by an inclusion.
7. Decision: allowed when some assignment that counts for the requester covers the node with a role that allows the action, and no
   deny entry applies.

## Pairs and planted differences

The positive has exactly ONE allowing path (one assignment, one membership chain, one role of the chain that carries the action) and
no deny entry that applies. The negative is the same specification with one line changed; on the designated path exactly one link
fails and no other path allows the request (`meta.deviation`, `meta.edit`, `meta.path`):
`membership` (a member line points to a look-alike, or the request names a look-alike user who sits in a look-alike group or only in
an outer group), `sealed` (a seal moved onto the way between assignment and node, or the request names a node inside a sealed branch),
`role_chain` (an extension line points to a look-alike role, or the request asks for an action that only a look-alike or an extending
role carries), `action` (an inclusion line or a role's own action changed, or the request asks for a stronger or unlinked action),
`scope` (the assignment moved to a sibling, a child off the way or below the node, or the request names a look-alike node elsewhere
or a node above the assignment), `deny` (a deny line changed in its user/group, action or node so that it applies, or the request
changes its action, node or user into one that an existing deny entry covers while the assignment still allows it).
Request-line differences: 150 pairs (50 per level), structure-line differences: 150 pairs (50 per level).

| deviation | level 1 | level 2 | level 3 |
|---|---|---|---|
{kinds_tab}

Decoys in both classes (shared by the two members of a pair): near-miss assignments for the requester that each fail one link
(look-alike group or user, group nested INSIDE the requester's group, sibling node, node below the request, an assignment above a seal
that lies on the way, a role that lacks the action, a role that is only extended by the carrier), seals on the way at or above the
assignment and off the way, deny entries on another (often linked) action, on a sibling node, below the requested node or for a
look-alike or inner group. The words "deny" and "sealed" occur equally often in the two classes (deny: {word_count['deny']['yes']} / {word_count['deny']['no']},
sealed: {word_count['sealed']['yes']} / {word_count['sealed']['no']} occurrences in yes / no states).

## Levels

| level | groups / nesting | role extension | tree depth | sealed | deny entries | users |
|---|---|---|---|---|---|---|
| 1 | one layer, also direct assignments | none | 2 (flat) | 0 | 0 | 4-6 |
| 2 | nested, 1 layer | chains of one | 3 | 1 | 0-2 (some items) | 6-9 |
| 3 | nested, 2 layers | chains of two | 4 | 2 | 2-3 | 10-14 |

Level 3 is hard because the allowing path combines at least six facts from different sections (`meta.path_facts` >= 6: two or three
membership lines, the assignment line, one to three role lines, inclusion lines, one to three tree lines), and the reader must also
check two seals against the way from the assignment down to the node and two or three deny entries against the requester's nested
groups, the exact action and the node's ancestors. State length (characters) min / median / max: level 1 {lens[1][0]} / {lens[1][100]} / {lens[1][-1]},
level 2 {lens[2][0]} / {lens[2][100]} / {lens[2][-1]}, level 3 {lens[3][0]} / {lens[3][100]} / {lens[3][-1]}.

## Checks made by the script

- Every pair: the positive is allowed through exactly one assignment (one membership chain, one carrier role, no applicable deny);
  in the negative exactly the planted link of the designated path fails (`links`), no other assignment allows it (for `deny`: the
  assignment still allows it and exactly one deny entry applies); undoing the edit gives the positive.
- `truth` and an independently written second evaluator (`judge`, used with all switches at the written rules) agree on all items.
- The two states of a pair have the same number of lines, differ in exactly one line and contain the same set of words.
- Balance: 100 yes / 100 no per level; kinds as in the table; 50 request and 50 structure differences per level; gold position;
  no duplicate state; vocabulary test ({tested} words, worst ratio {worst[0]:.2f}); negative longer / equal / shorter than its positive:
  {ld[1]} / {ld[0]} / {ld[-1]} pairs.

Accuracy of sloppy readings (the rules with one convention misread), level 1 / 2 / 3:

| reading | level 1 | level 2 | level 3 |
|---|---|---|---|
{slop}

## Examples

""" + "\n\n".join(fmt_example(r) for r in ex) + """

## Independence

The generator is new, written for this benchmark; its wording, names and templates share nothing with the authors' training
generators or with benchmark v0.
"""
    open(os.path.join(d, "README.md"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
