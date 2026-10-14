"""Task dep_resolve (layer E, generated, programmatic truth): "Does the proposed set install cleanly in the target environment?"

Item design.  The state holds (a) the conventions in plain words, (b) the target environment (from level 2 with a runtime
version), (c) an index of invented packages - several versions per package, and for every version what it requires
(bounds with >=, >, <=, <, ==, != on other packages), from level 2 the runtime it accepts, at level 3 the packages it
conflicts with - and (d) the proposed set of pins (one package at one version per line).  The set installs cleanly when
every pin is a listed version, every requirement of every PINNED version names a package that is pinned at a version
inside all bounds, the runtime meets every runtime bound of every pinned version and no conflict declared by a pinned
version applies to another pin.  Versions compare number by number (1.10.0 is newer than 1.9.3).  Pins that nothing
requires are harmless.  Truth: `truth(spec)` = no entry in `violations(spec)`.

Contrast pairs.  600 items = 300 pairs (100 per level).  The two members of a pair share every character of the state
except ONE pin line.  The positive breaks nothing; the negative breaks exactly one condition (asserted):
  bound     the pin of a required package moved to the neighbouring listed version, just outside one bound of ONE
            dependant (on an excluded bound, one step past an included bound, the 1.10-versus-1.9 trap, ==, !=)
  own_req   a pin moved to a neighbouring listed version that every dependant accepts, but the entry of that version
            carries one bound that the pin of another package misses by one step
  missing   the pin line of a required package is replaced by a pin of a package that nothing requires (same length)
  runtime   (levels 2-3) a pin moved to a neighbouring version whose runtime bound the environment misses by one step
  conflict  (level 3) a pin moved to a neighbouring version so that one conflict applies (declared by another pin about
            the moved package, or declared by the moved version about another pin)
The index is the same in both members, so the look-alike entries of the other versions of every package (some of which
would fail, some of which would pass) are decoys in both classes, as are pins that sit on an included bound, pins just
inside an excluded bound, conflicts that stop one step short of a pin and conflicts about packages that are not pinned.

Levels: 1 = 4-5 pins, 1-2 versions per package, no runtime, no conflicts; 2 = 6-8 pins, 2-3 versions per package,
runtime; 3 = 9-12 pins, 3-4 versions per package, requirement chains of three links, runtime and conflicts.

Environment: BENCH_OUT=<dir> writes <dir>/dep_resolve/ instead of generated/tasks/dep_resolve/; BENCH_SEED=<int> (only together
with BENCH_OUT) replaces the root seed 20261007 for a sealed split (ids dep_resolve:s<k>:NNNNN).
    python3 generators/dep_resolve.py
"""
import collections
import json
import os
import random
import re
import sys

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated")   # items go to HERE/tasks/<family>/ (BENCH_OUT: elsewhere)
TASK = "dep_resolve"
DEFAULT_SEED = 20261007
BENCH_OUT = os.environ.get("BENCH_OUT") or None
BENCH_SEED = os.environ.get("BENCH_SEED") or None
if BENCH_SEED is not None and BENCH_OUT is None:
    sys.stderr.write("BENCH_SEED is accepted only together with BENCH_OUT (the published set is never overwritten by another seed)\n")
    sys.exit(2)
SEED = int(BENCH_SEED) if BENCH_SEED is not None else DEFAULT_SEED
SALT = random.Random(SEED).getrandbits(64)            # every generator of this script is derived from random.Random(SEED)
ID_PREFIX = TASK if BENCH_SEED is None else "%s:s%d" % (TASK, SEED)
OUT_DIR = os.path.join(BENCH_OUT, TASK) if BENCH_OUT else os.path.join(HERE, "tasks", TASK)

PAIRS_PER_LEVEL = 100
INSTRUCTIONS = "Does the proposed set install cleanly in the target environment?"
OPTIONS = {"yes": "Yes, the proposed set installs cleanly.", "no": "No, the proposed set does not install cleanly."}
LEVELS = {        # extras = further pins that nothing requires; links = length of the requirement chain from the first pin
    1: {"pins": (4, 5), "unpinned": (2, 2), "extras": (1, 1), "links": (1, 2), "nver": (1, 2), "p_edge": 0.12, "p_cross": 0.1,
        "siblings": (0, 1), "runtime": False, "conflicts": False, "kinds": ["bound", "missing", "own_req"]},
    2: {"pins": (6, 8), "unpinned": (2, 3), "extras": (1, 2), "links": (2, 2), "nver": (2, 3), "p_edge": 0.2, "p_cross": 0.1,
        "siblings": (1, 1), "runtime": True, "conflicts": False, "kinds": ["bound", "missing", "own_req", "runtime"]},
    3: {"pins": (9, 12), "unpinned": (3, 3), "extras": (2, 3), "links": (3, 3), "nver": (3, 4), "p_edge": 0.2, "p_cross": 0.1,
        "siblings": (1, 2), "runtime": True, "conflicts": True, "kinds": ["bound", "missing", "own_req", "runtime", "conflict"]},
}
KINDS = ["bound", "missing", "own_req", "runtime", "conflict"]
LAYOUTS = ["block", "table", "facts"]


class Retry(Exception):
    """an unlucky draw (no package fits the role, a name clash, ...): the pair is drawn again with the next sub-seed"""


def rng_for(*parts):
    return random.Random("%d:%s:%s" % (SALT, TASK, ":".join(str(p) for p in parts)))


def pick(rng, weighted):
    """weighted = [(weight, value), ...] -> one value"""
    return rng.choices([v for _, v in weighted], [w for w, _ in weighted])[0]


# ------------------------------------------------------------------------------------------------- invented names
SYL_A = ["tol", "brim", "sev", "quen", "zar", "kov", "hul", "fex", "dran", "mip", "yor", "plu", "grat", "vob", "wez", "jum",
         "kril", "sarn", "thub", "olm", "nib", "dax", "morv", "rell", "sork", "tav", "umb", "virn", "xan", "zeph", "gost",
         "lerm", "nuv", "ostr", "pesk", "ruk", "skel", "trov", "ulv", "yeg"]
SYL_B = ["var", "lok", "rin", "dex", "mur", "tis", "vek", "nor", "gan", "bix", "zel", "dru", "kam", "pho", "ryx", "tem",
         "ula", "ven", "wim", "zot", "aro", "eth", "iko", "osk", "urn", "ath", "enk", "ilo", "omi", "ux"]
BLOCK = {"rellenk", "peskilo", "rukilo", "sorkilo", "grattis", "sarnath", "zarrin", "nuvaro", "nuvath", "fexdex", "hulula",
         "umbaro"}
DOMAINS = {
    "pipeline": {"pkg": "plugin", "a_pkg": "a plugin", "pkgs": "plugins", "index": "plugin registry",
                 "env_kind": "pipeline runner", "a_env_kind": "a pipeline runner",
                 "suffix": ["source", "sink", "codec", "queue", "batch", "merge", "split", "audit", "cache", "relay"]},
    "firmware": {"pkg": "module", "a_pkg": "a module", "pkgs": "modules", "index": "module feed",
                 "env_kind": "field controller", "a_env_kind": "a field controller",
                 "suffix": ["drv", "hal", "boot", "bus", "adc", "pwm", "rtc", "spi", "nvm", "mux"]},
    "analysis": {"pkg": "package", "a_pkg": "a package", "pkgs": "packages", "index": "package index",
                 "env_kind": "analysis workstation", "a_env_kind": "an analysis workstation",
                 "suffix": ["fit", "plot", "stats", "io", "grid", "solve", "units", "table", "bins", "core"]},
    "gameserver": {"pkg": "extension", "a_pkg": "an extension", "pkgs": "extensions", "index": "extension catalogue",
                   "env_kind": "game server", "a_env_kind": "a game server",
                   "suffix": ["mod", "net", "chat", "maps", "loot", "rank", "save", "voice", "shop", "auth"]},
    "robot": {"pkg": "component", "a_pkg": "a component", "pkgs": "components", "index": "component depot",
              "env_kind": "robot controller", "a_env_kind": "a robot controller",
              "suffix": ["nav", "arm", "sense", "ctl", "grip", "plan", "odom", "lidar", "motor", "safety"]},
}


def new_stem(rng, used):
    for _ in range(1000):
        s = rng.choice(SYL_A) + rng.choice(SYL_B)
        if s not in BLOCK and s not in used and not re.search(r"(.)\1\1", s):
            used.add(s)
            return s
    raise Retry("no free stem")


def make_names(rng, n_packages, domain, twin=None, twin_sibling=False, n_siblings=0):
    """-> (names of the packages 0..n-1, environment name).  `twin` = (x, u): the two names get the same number of characters
    (and the same stem when `twin_sibling`).  `n_siblings` further pairs share a stem and differ in the suffix."""
    suffixes = DOMAINS[domain]["suffix"]
    used, names = set(), [None] * n_packages
    free = list(range(n_packages))
    if twin:
        x, u = twin
        free = [t for t in free if t not in twin]
        if twin_sibling:
            stem = new_stem(rng, used)
            sx = rng.choice(suffixes)
            same = [s for s in suffixes if len(s) == len(sx) and s != sx]
            if not same:
                raise Retry("no suffix of that length")
            names[x], names[u] = stem + "-" + sx, stem + "-" + rng.choice(same)
        else:
            names[x] = new_stem(rng, used) + ("-" + rng.choice(suffixes) if rng.random() < 0.7 else "")
            for _ in range(400):
                cand = new_stem(rng, set(used)) + ("-" + rng.choice(suffixes) if rng.random() < 0.7 else "")
                if len(cand) == len(names[x]) and cand.split("-")[0] != names[x].split("-")[0]:
                    used.add(cand.split("-")[0])
                    names[u] = cand
                    break
            else:
                raise Retry("no name of that length")
    rng.shuffle(free)
    while n_siblings > 0 and len(free) >= 2:
        a, b = free.pop(), free.pop()
        stem = new_stem(rng, used)
        sa, sb = rng.sample(suffixes, 2)
        names[a] = stem + "-" + sa
        names[b] = stem + ("-" + sb if rng.random() < 0.75 else "")
        n_siblings -= 1
    for t in free:
        names[t] = new_stem(rng, used) + ("-" + rng.choice(suffixes) if rng.random() < 0.7 else "")
    if len(set(names)) != n_packages:
        raise Retry("name clash")
    env = "%s-%02d" % (new_stem(rng, used), rng.randint(1, 48))
    return names, env


# ------------------------------------------------------------------------------------------- versions and bounds
def vstr(v):
    return ".".join(str(x) for x in v)


def holds(v, op, b):
    """does version v meet the bound (op, b)?  Versions are tuples of whole numbers: number-by-number comparison."""
    v, b = tuple(v), tuple(b)
    assert len(v) == len(b), (v, b)
    if op == ">=":
        return v >= b
    if op == ">":
        return v > b
    if op == "<=":
        return v <= b
    if op == "<":
        return v < b
    if op == "==":
        return v == b
    if op == "!=":
        return v != b
    raise ValueError(op)


def lex_holds(v, op, b):
    """the bound as a reader sees it who compares the written versions as text (so that 1.10.0 sorts before 1.9.3)"""
    v, b = vstr(v), vstr(b)
    return {">=": v >= b, ">": v > b, "<=": v <= b, "<": v < b, "==": v == b, "!=": v != b}[op]


def inverted(a, b):
    """a is older than b, but as text a sorts after b (1.9.3 / 1.10.0): the pair on which the text comparison goes wrong"""
    return tuple(a) < tuple(b) and vstr(a) > vstr(b)


def make_versions(rng, k, cross):
    """k versions of one package, oldest first.  cross = None: no two versions form an inverted pair and all are written with
    the same number of characters; cross = a: versions a and a + 1 are the only NEIGHBOURS that form an inverted pair."""
    for _ in range(2000):
        M = rng.randint(0, 7)
        if cross is None:
            style = rng.choice(["minor", "minor", "minor2", "patch", "major", "mixed"])
            if style == "minor":
                ms = [rng.randint(0, 4)]
                while len(ms) < k:
                    ms.append(ms[-1] + rng.choice([1, 1, 2]))
                vs = [(M, m, rng.randint(0, 6)) for m in ms]
            elif style == "minor2":
                m0 = rng.randint(11, 15)
                vs = [(M, m0 + t, rng.randint(0, 6)) for t in range(k)]
            elif style == "patch":
                m, ps = rng.randint(0, 9), [rng.randint(0, 3)]
                while len(ps) < k:
                    ps.append(ps[-1] + rng.choice([1, 1, 2]))
                vs = [(M, m, p) for p in ps]
            elif style == "major":
                vs = [(M + t, rng.randint(0, 6), rng.randint(0, 4)) for t in range(k)]
            else:
                m, p = rng.randint(0, 7), rng.randint(0, 5)
                seq = [(M, m, p), (M, m, p + 1), (M, m + 1, 0), (M, m + 1, 1 + rng.randint(0, 2)), (M + 1, 0, 0), (M + 1, 0, 1)]
                first = rng.randint(0, len(seq) - k)
                vs = seq[first:first + k]
            if any(x > 9 for v in vs for x in v) and style != "minor2":
                continue
        else:
            style = rng.choice(["minor9", "minor9", "patch9", "gap", "major9"])
            lo_n, hi_n = cross + 1, k - cross - 1
            if style == "minor9":
                vs = ([(M, 9 - t, rng.randint(0, 5)) for t in range(lo_n - 1, -1, -1)]
                      + [(M, 10 + t, rng.randint(0, 3)) for t in range(hi_n)])
            elif style == "patch9":
                m = rng.randint(0, 9)
                vs = [(M, m, 9 - t) for t in range(lo_n - 1, -1, -1)] + [(M, m, 10 + t) for t in range(hi_n)]
            elif style == "gap":
                a1, b1 = rng.randint(max(2, lo_n - 1), 8), rng.randint(10, 14)
                vs = ([(M, a1 - t, rng.randint(0, 5)) for t in range(lo_n - 1, -1, -1)]
                      + [(M, b1 + t, rng.randint(0, 4)) for t in range(hi_n)])
            else:
                vs = ([(9 - t, rng.randint(0, 6), rng.randint(0, 4)) for t in range(lo_n - 1, -1, -1)]
                      + [(10 + t, rng.randint(0, 4), rng.randint(0, 3)) for t in range(hi_n)])
        if len(vs) != k or any(not x < y for x, y in zip(vs, vs[1:])):
            continue
        if cross is None:
            if any(inverted(vs[s], vs[t]) for s in range(k) for t in range(s + 1, k)) or len({len(vstr(v)) for v in vs}) != 1:
                continue
        elif [t for t in range(k - 1) if inverted(vs[t], vs[t + 1])] != [cross]:
            continue
        return vs
    raise RuntimeError("no version list")


def floor_below(vs, lo):
    """an unlisted version below vs[lo] and above the listed version before it (1.9.3 -> 1.9.0), or None"""
    v = vs[lo]
    for c in ((v[0], v[1], 0), (v[0], 0, 0)):
        if c < v and (lo == 0 or c > vs[lo - 1]):
            return c
    return None


def ceil_above(rng, vs, hi):
    """an unlisted version above vs[hi] and below the listed version after it (1.9.3 -> 1.10.0 / 2.0.0 / 1.9.4), or None"""
    v = vs[hi]
    ok = [c for c in ((v[0], v[1] + 1, 0), (v[0] + 1, 0, 0), (v[0], v[1], v[2] + 1))
          if c > v and (hi == len(vs) - 1 or c < vs[hi + 1])]
    return rng.choice(ok) if ok else None


def lower_cands(vs, lo):
    """lower bounds met by vs[lo] and by everything newer; the tight ones weigh most"""
    c = [(3, (">=", vs[lo]))]
    if lo > 0:
        c += [(3, (">", vs[lo - 1])), (1, (">=", vs[lo - 1]))]
    f = floor_below(vs, lo)
    if f:
        c.append((2, (">=", f)))
    return c


def upper_cands(rng, vs, hi):
    """upper bounds met by vs[hi] and by everything older"""
    c = [(3, ("<=", vs[hi]))]
    if hi + 1 < len(vs):
        c += [(3, ("<", vs[hi + 1])), (1, ("<=", vs[hi + 1]))]
    u = ceil_above(rng, vs, hi)
    if u:
        c.append((2, ("<", u)))
    return c


def passing(rng, vs, acc):
    """one requirement (1 or 2 bounds) on a package with the versions vs that every version index in acc meets"""
    lo, hi = min(acc), max(acc)
    pats = [(35, "lower"), (35, "both"), (10, "upper")]
    if lo == hi:
        pats.append((10, "eq"))
    if hi + 1 < len(vs):
        pats.append((6, "lower_ne"))
    if lo > 0:
        pats.append((6, "upper_ne"))
    pat = pick(rng, pats)
    if pat == "eq":
        return [("==", vs[lo])]
    out = []
    if pat in ("lower", "both", "lower_ne"):
        out.append(pick(rng, lower_cands(vs, lo)))
    if pat in ("upper", "both", "upper_ne"):
        out.append(pick(rng, upper_cands(rng, vs, hi)))
    if pat == "lower_ne":
        out.append(("!=", vs[hi + 1]))
    if pat == "upper_ne":
        out.append(("!=", vs[lo - 1]))
    if len(out) == 2 and out[0][1] == out[1][1] and out[0][0] == ">=" and out[1][0] == "<=":
        return [("==", out[0][1])]
    assert all(holds(vs[a], op, b) for a in acc for op, b in out)
    return out


def companion(rng, vs, i, clause, p=0.45):
    """[clause] or clause plus one bound on its other side that vs[i] meets (so the number of bounds vs[i] misses is unchanged)"""
    op = clause[0]
    if op == "==" or rng.random() > p:
        return [clause]
    if op in (">", ">="):
        t = i + 1 if (i + 1 < len(vs) and not holds(vs[i], op, clause[1])) else i
        cands = [c for c in upper_cands(rng, vs, t) if holds(vs[t], op, clause[1]) or c[1][0] == "<"]
        out = [clause, pick(rng, cands)] if cands else [clause]
    elif op in ("<", "<="):
        t = i - 1 if (i > 0 and not holds(vs[i], op, clause[1])) else i
        out = [pick(rng, lower_cands(vs, t)), clause]
    else:
        out = [pick(rng, lower_cands(vs, i)), clause]
    if len(out) == 2 and not nonempty(out):
        return [clause]
    return out


def nonempty(bounds):
    """a lower and an upper bound that leave room for a version between them (no '>=1.2.0,<1.2.0'), and not '>=V,<=V'"""
    (lo_op, lo), (up_op, up) = bounds
    if lo_op not in (">", ">=") or up_op not in ("<", "<="):
        return True
    return tuple(lo) < tuple(up)


def failing(rng, vs, i):
    """one requirement that vs[i] misses by one step (exactly one of its bounds fails)"""
    c = [(2, (">", vs[i])), (2, ("<", vs[i])), (1, ("!=", vs[i]))]
    if i + 1 < len(vs):
        c += [(3, (">=", vs[i + 1])), (1, ("==", vs[i + 1]))]
    if i > 0:
        c += [(3, ("<=", vs[i - 1])), (1, ("==", vs[i - 1]))]
    out = companion(rng, vs, i, pick(rng, c))
    assert sum(not holds(vs[i], op, b) for op, b in out) == 1
    return out


def conflict_miss(rng, vs, acc):
    """a conflict bound that none of the versions in acc meets; the near misses weigh most"""
    lo, hi = min(acc), max(acc)
    c = [(3, ("<", vs[lo])), (3, (">", vs[hi]))]
    if lo > 0:
        c += [(3, ("<=", vs[lo - 1])), (2, ("==", vs[lo - 1]))]
    if hi + 1 < len(vs):
        c += [(3, (">=", vs[hi + 1])), (2, ("==", vs[hi + 1]))]
    return pick(rng, c)


def conflict_hit(rng, vs, i):
    """a conflict bound that vs[i] meets by the smallest margin"""
    c = [(3, ("<=", vs[i])), (3, (">=", vs[i])), (2, ("==", vs[i]))]
    if i + 1 < len(vs):
        c.append((2, ("<", vs[i + 1])))
    if i > 0:
        c.append((2, (">", vs[i - 1])))
    return pick(rng, c)


def rt_passing(rng, r):
    """runtime bounds (0, 1 or 2) that the runtime r = (a, b) meets"""
    a, b = r
    lower = [(3, (">=", (a, b))), (2, (">", (a, b - 1))), (2, (">=", (a, b - 1))), (1, (">=", (a, b - 2)))]
    upper = [(3, ("<", (a, b + 1))), (2, ("<=", (a, b))), (2, ("<", (a + 1, 0))), (1, ("<=", (a, b + 1)))]
    pat = pick(rng, [(45, "lower"), (27, "both"), (10, "upper"), (10, "none"), (8, "eq")])
    if pat == "none":
        return []
    if pat == "eq":
        return [("==", r)]
    out = []
    if pat in ("lower", "both"):
        out.append(pick(rng, lower))
    if pat in ("upper", "both"):
        out.append(pick(rng, upper))
    if len(out) == 2 and out[0][1] == out[1][1] and out[0][0] == ">=" and out[1][0] == "<=":
        return [("==", r)]
    assert all(holds(r, op, x) for op, x in out)
    return out


def rt_companion(rng, r, clause, p=0.4):
    a, b = r
    op = clause[0]
    if op == "==" or rng.random() > p:
        return [clause]
    if op in (">", ">="):
        return [clause, pick(rng, [(2, ("<", (a + 1, 0))), (1, ("<=", (a, b + 2))), (1, ("<", (a, b + 3)))])]
    return [pick(rng, [(2, (">=", (a, b - 2))), (1, (">", (a, b - 2))), (1, (">=", (a, 0)))]), clause]


def rt_failing(rng, r):
    """runtime bounds that the runtime r misses by one step (exactly one bound fails)"""
    a, b = r
    bad = pick(rng, [(2, (">", r)), (2, ("<", r)), (3, (">=", (a, b + 1))), (3, ("<=", (a, b - 1))),
                     (1, ("==", (a, b + 1))), (1, ("==", (a, b - 1))), (1, ("!=", r))])
    out = rt_companion(rng, r, bad)
    assert sum(not holds(r, op, x) for op, x in out) == 1
    return out


def rt_failing_trap(rng, r):
    """a runtime bound that the runtime misses by one step although the TEXT comparison says it is met (3.9 vs >=3.10)"""
    a, b = r
    out = [(">=", (a, 10))] if b == 9 else [("<=", (a, 9))]
    assert not holds(r, *out[0]) and lex_holds(r, *out[0])
    return out


def separating(rng, vs, i, j, form):
    """a requirement that vs[i] meets and its neighbour vs[j] misses, with exactly one failing bound.
    form: included (the positive sits ON an included bound), excluded (the negative sits on an excluded bound), unlisted
    (an excluded bound between the two listed versions), eq (==), ne (!=)"""
    up = j > i
    clause = None
    if form == "unlisted":
        u = ceil_above(rng, vs, i) if up else floor_below(vs, i)
        if u is None:
            form = "excluded"
        else:
            clause = ("<", u) if up else (">=", u)
    if form == "included":
        clause = ("<=", vs[i]) if up else (">=", vs[i])
    elif form == "excluded":
        clause = ("<", vs[j]) if up else (">", vs[j])
    elif form == "eq":
        clause = ("==", vs[i])
    elif form == "ne":
        clause = ("!=", vs[j])
    out = [clause]
    if form != "eq" and rng.random() < 0.5:
        side = rng.choice(["low", "high"]) if form == "ne" else ("low" if up else "high")
        out = [pick(rng, lower_cands(vs, min(i, j))), clause] if side == "low" else [clause, pick(rng, upper_cands(rng, vs, max(i, j)))]
        if out[0][1] == out[1][1] and {out[0][0], out[1][0]} == {">=", "<="}:
            out = [clause]
    assert all(holds(vs[i], op, b) for op, b in out) and sum(not holds(vs[j], op, b) for op, b in out) == 1, (vs, i, j, out)
    return out, form


def conflict_sep(rng, vs, i, j):
    """a conflict bound that vs[j] meets and its neighbour vs[i] misses"""
    if j > i:
        b = pick(rng, [(3, (">=", vs[j])), (3, (">", vs[i])), (1, ("==", vs[j]))])
    else:
        b = pick(rng, [(3, ("<=", vs[j])), (3, ("<", vs[i])), (1, ("==", vs[j]))])
    assert holds(vs[j], *b) and not holds(vs[i], *b)
    return b


# ------------------------------------------------------------------------------------------------------- truth
def violations(spec, cmp=holds, runtime=True, conflicts=True, missing=True, line="pinned"):
    """every broken condition of the pin set, computed on the structured specification.  The keyword arguments only serve
    the shortcut readers of the report (text comparison, a skipped convention, the entry of the newest listed version read
    instead of the pinned one); the truth uses the defaults."""
    pins = {p: tuple(v) for p, v in spec["pins"]}
    out = []
    for p, v in spec["pins"]:
        pk = spec["pkgs"][p]
        if tuple(v) not in pk["vs"]:
            out.append(("unlisted", p))
            continue
        ent = pk["ent"][pk["vs"].index(tuple(v)) if line == "pinned" else len(pk["vs"]) - 1]
        for q, bounds in ent["req"]:
            if q not in pins:
                if missing:
                    out.append(("missing", p, q))
                continue
            for k, (op, b) in enumerate(bounds):
                if not cmp(pins[q], op, b):
                    out.append(("bound", p, q, k))
        if runtime and spec["runtime"] is not None:
            for k, (op, b) in enumerate(ent["rt"]):
                if not cmp(spec["runtime"], op, b):
                    out.append(("runtime", p, k))
        if conflicts:
            for q, (op, b) in ent["conf"]:
                if q in pins and cmp(pins[q], op, b):
                    out.append(("conflict", p, q))
    return out


def truth(spec):
    return not violations(spec)


def inclusive_holds(v, op, b):
    return holds(v, {">": ">=", "<": "<="}.get(op, op), b)


SHORTCUTS = [("text_compare", {"cmp": lex_holds}), ("strict_as_inclusive", {"cmp": inclusive_holds}),
             ("ignore_missing", {"missing": False}), ("ignore_runtime", {"runtime": False}),
             ("ignore_conflicts", {"conflicts": False}), ("newest_entry", {"line": "newest"})]


def planted_ok(kind, R, viol):
    """the negative breaks exactly the planted condition"""
    if len(viol) != 1:
        return False
    v = viol[0]
    if kind == "bound":
        return v[:3] == ("bound", R["D"], R["X"])
    if kind == "own_req":
        return v[:3] == ("bound", R["X"], R["Y"])
    if kind == "missing":
        return v == ("missing", R["D"], R["Y"])
    if kind == "runtime":
        return v[:2] == ("runtime", R["X"])
    if R["sub"] == "declared_by_other":
        return v == ("conflict", R["E"], R["X"])
    return v == ("conflict", R["X"], R["Y"])


def describe(spec, v):
    pk, pins = spec["pkgs"], {p: tuple(x) for p, x in spec["pins"]}
    nm = lambda p: "%s %s" % (pk[p]["name"], vstr(pins[p]))
    ent = lambda p: pk[p]["ent"][pk[p]["vs"].index(pins[p])]
    if v[0] == "missing":
        return "missing: %s requires %s, which has no pin" % (nm(v[1]), pk[v[2]]["name"])
    if v[0] == "bound":
        op, b = dict(ent(v[1])["req"])[v[2]][v[3]]
        return "bound: %s requires %s %s%s, pinned %s" % (nm(v[1]), pk[v[2]]["name"], op, vstr(b), vstr(pins[v[2]]))
    if v[0] == "runtime":
        op, b = ent(v[1])["rt"][v[2]]
        return "runtime: %s needs runtime %s%s, environment %s" % (nm(v[1]), op, vstr(b), vstr(spec["runtime"]))
    if v[0] == "conflict":
        op, b = dict(ent(v[1])["conf"])[v[2]]
        return "conflict: %s conflicts with %s %s%s, pinned %s" % (nm(v[1]), pk[v[2]]["name"], op, vstr(b), vstr(pins[v[2]]))
    return "unlisted: %s" % pk[v[1]]["name"]


def sig(e):
    return (tuple((q, tuple(b)) for q, b in e["req"]), tuple(e["rt"]), tuple(e["conf"]))


# ------------------------------------------------------------------------------------------------------ one pair
def build_pair(rng, plan):
    """-> (positive spec, negative spec, roles).  Both specs share the index; the pins differ in ONE line."""
    level, kind = plan["level"], plan["kind"]
    cfg = LEVELS[level]
    n = rng.randint(*cfg["pins"])
    NP = n + rng.randint(*cfg["unpinned"])
    links = rng.randint(*cfg["links"])
    rest = list(range(links + 1, n))
    roots = {0} | set(rng.sample(rest, min(len(rest), rng.randint(*cfg["extras"]))))
    out, deps = collections.defaultdict(list), collections.defaultdict(set)

    def edge(p, q):                      # the pinned version of p requires q (p < q: package numbers are a topological order)
        if q not in out[p]:
            out[p].append(q)
            deps[q].add(p)
    for k in range(1, links + 1):
        edge(k - 1, k)
    for q in rest:
        if q not in roots:
            edge(rng.randrange(q), q)
    for q in range(1, n):
        for p in range(q):
            if q not in roots and p not in deps[q] and len(out[p]) < 3 and rng.random() < cfg["p_edge"]:
                edge(p, q)
    nonroots = [q for q in range(1, n) if q not in roots]
    unpinned = list(range(n, NP))
    R = {"X": None, "Y": None, "D": None, "Z": None, "E": None, "sub": plan.get("sub"), "form": None}
    deep = lambda c: [q for q in c if 2 <= q <= links] if level == 3 else []
    if kind == "missing":
        cands = [q for q in nonroots if len(deps[q]) == 1]
        if not cands:
            raise Retry("no package with one dependant")
        dc = deep(cands)
        R["Y"] = rng.choice(dc if dc and rng.random() < 0.6 else cands)
        R["D"] = min(deps[R["Y"]])
        R["Z"] = rng.choice(unpinned)
        twin = (R["Y"], R["Z"])
    else:
        cands = {"bound": nonroots, "own_req": list(range(n - 1))}.get(kind, list(range(n)))
        pref = [p for p in cands if p in nonroots]
        dc = deep(pref)
        X = rng.choice(dc if dc and rng.random() < 0.6 else (pref if pref and rng.random() < 0.75 else cands))
        R["X"] = X
        if kind == "bound":
            R["D"] = rng.choice(sorted(deps[X]))
        elif kind == "own_req":
            R["Y"] = rng.choice(out[X]) if out[X] and rng.random() < 0.7 else rng.choice(list(range(X + 1, n)))
        elif kind == "conflict":
            R["E" if R["sub"] == "declared_by_other" else "Y"] = rng.choice([p for p in range(n) if p != X])
        twin = (rng.choice(nonroots), rng.choice(unpinned))
    X = R["X"]
    # versions
    nv = [rng.randint(*cfg["nver"]) for _ in range(NP)]
    if X is not None:
        nv[X] = max(2, nv[X])
    cross = [None] * NP
    pi = {p: rng.randrange(nv[p]) for p in range(n)}
    if X is not None:
        if plan.get("trap"):
            c = rng.randrange(nv[X] - 1)
            i, j = (c, c + 1) if rng.random() < 0.5 else (c + 1, c)
            cross[X] = c
        else:
            i = rng.randrange(nv[X])
            j = i + 1 if i == 0 else i - 1 if i == nv[X] - 1 else i + rng.choice([-1, 1])
        pi[X] = i
        R["i"], R["j"] = i, j
    for p in range(NP):
        if p != X and p != R["Z"] and nv[p] >= 2 and rng.random() < cfg["p_cross"]:
            cross[p] = rng.randrange(nv[p] - 1)
    vs = [make_versions(rng, nv[p], cross[p]) for p in range(NP)]
    if kind == "missing":                # the replacing pin line has the width of the replaced one
        Y, Z = R["Y"], R["Z"]
        for _ in range(100):
            if len(vstr(vs[Z][0])) == len(vstr(vs[Y][pi[Y]])):
                break
            vs[Z] = make_versions(rng, nv[Z], None)
        else:
            raise Retry("no version list of that width")
        R["vz"] = rng.randrange(nv[Z])
    rt = None
    if cfg["runtime"]:
        rt = (rng.randint(1, 4), rng.choice([9, 10]) if plan.get("rt_trap") else rng.choice([3, 4, 5, 6, 7, 12, 13, 14, 15, 16]))
    accept = {q: {pi[q]} for q in range(n)}      # versions that every requirement on q must accept
    avoid = {q: {pi[q]} for q in range(n)}       # versions that every conflict entry about q must miss
    if X is not None:
        accept[X], avoid[X] = {i, j}, {i, j}
    if kind == "missing":
        avoid[R["Z"]] = {R["vz"]}

    def conflict_entry(p):
        q = rng.choice([q for q in range(NP) if q != p])
        return (q, conflict_miss(rng, vs[q], avoid[q]) if q in avoid else conflict_hit(rng, vs[q], rng.randrange(nv[q])))

    def clean(p, targets):
        return {"req": [(q, passing(rng, vs[q], accept[q])) for q in targets],
                "rt": rt_passing(rng, rt) if rt else [],
                "conf": [conflict_entry(p)] if cfg["conflicts"] and rng.random() < 0.4 else []}

    ent = [[None] * nv[p] for p in range(NP)]
    for p in range(n):
        ent[p][pi[p]] = clean(p, list(out[p]))
    if kind == "bound":
        D = R["D"]
        bounds, R["form"] = separating(rng, vs[X], i, j, plan["form"])
        ent[D][pi[D]]["req"] = [(q, bounds if q == X else b) for q, b in ent[D][pi[D]]["req"]]
    if X is not None:                    # the entry of the version the negative pins instead
        tj = list(out[X])
        if tj and rng.random() < 0.25:
            tj.remove(rng.choice(tj))
        more = [q for q in range(X + 1, n) if q not in tj]
        if more and rng.random() < 0.25:
            tj.append(rng.choice(more))
        if kind == "own_req" and R["Y"] not in tj:
            tj.append(R["Y"])
        ej = clean(X, tj)
        if kind == "own_req":
            ej["req"] = [(q, failing(rng, vs[q], pi[q]) if q == R["Y"] else b) for q, b in ej["req"]]
        elif kind == "runtime":
            ej["rt"] = rt_failing_trap(rng, rt) if plan.get("rt_trap") else rt_failing(rng, rt)
        elif kind == "conflict" and R["sub"] == "declared_by_moved":
            Yc = R["Y"]
            ej["conf"] = [(Yc, conflict_hit(rng, vs[Yc], pi[Yc]))]
            if rng.random() < 0.7:
                ent[X][i]["conf"] = [(Yc, conflict_miss(rng, vs[Yc], {pi[Yc]}))]
        elif kind == "conflict":
            ent[R["E"]][pi[R["E"]]]["conf"] = [(X, conflict_sep(rng, vs[X], i, j))]
        ent[X][j] = ej
    if kind == "missing":                # the entry of the unneeded package the negative pins instead
        Y, Z, vz = R["Y"], R["Z"], R["vz"]
        cand = [q for q in range(n) if q != Y]
        ez = clean(Z, rng.sample(cand, rng.randint(0, min(2, len(cand)))))
        if cfg["conflicts"] and rng.random() < 0.25:
            ez["conf"] = [(Y, conflict_hit(rng, vs[Y], pi[Y]))]
        ent[Z][vz] = ez

    def decoy(p):
        """a look-alike entry of a version that neither member pins"""
        if p < n:
            targets = [q for q, _ in ent[p][pi[p]]["req"]]
            if targets and rng.random() < 0.2:
                targets.remove(rng.choice(targets))
            more = [q for q in range(NP) if q != p and q not in targets and (q >= n or q > p)]
            if more and rng.random() < 0.35:
                targets.append(rng.choice(more))
        else:
            pool = [q for q in range(NP) if q != p]
            targets = rng.sample(pool, rng.randint(0, min(2, len(pool))))
        req = []
        for q in targets:
            if q < n and rng.random() < 0.45:
                req.append((q, failing(rng, vs[q], pi[q])))
            else:
                req.append((q, passing(rng, vs[q], {pi[q] if q < n else rng.randrange(nv[q])})))
        rtb = [] if rt is None else (rt_failing(rng, rt) if rng.random() < 0.3 else rt_passing(rng, rt))
        conf = []
        if cfg["conflicts"] and rng.random() < 0.35:
            q = rng.choice([q for q in range(NP) if q != p])
            conf = [(q, conflict_hit(rng, vs[q], pi[q] if q < n else rng.randrange(nv[q])))]
        return {"req": req, "rt": rtb, "conf": conf}

    for p in range(NP):
        seen = {sig(e) for e in ent[p] if e is not None}
        for t in range(nv[p]):
            if ent[p][t] is None:
                for _ in range(40):
                    e = decoy(p)
                    if sig(e) not in seen:
                        break
                else:
                    raise Retry("look-alike entries coincide")
                ent[p][t] = e
                seen.add(sig(e))
    names, env = make_names(rng, NP, plan["domain"], twin=twin, twin_sibling=plan["sibling"],
                            n_siblings=rng.randint(*cfg["siblings"]))
    pkgs = [{"name": names[p], "vs": vs[p], "ent": ent[p]} for p in range(NP)]
    order = list(range(n))
    rng.shuffle(order)
    pins_p = [(p, vs[p][pi[p]]) for p in order]
    if kind == "missing":
        pins_n = [(R["Z"], vs[R["Z"]][R["vz"]]) if p == R["Y"] else (p, v) for p, v in pins_p]
    else:
        pins_n = [(p, vs[X][j]) if p == X else (p, v) for p, v in pins_p]
    P = {"level": level, "runtime": rt, "pkgs": pkgs, "pins": pins_p, "env": env, "roots": sorted(roots), "links": links}
    N = dict(P, pins=pins_n)
    vp, vn = violations(P), violations(N)
    assert not vp and planted_ok(kind, R, vn), (kind, vp, vn)
    R["names"] = {k: names[R[k]] for k in ("X", "Y", "D", "Z", "E") if R[k] is not None}
    return P, N, R


# ------------------------------------------------------------------------------------------------------- rendering
REQ_LABEL = ["requires", "needs", "depends on"]
RT_LABEL = ["runtime", "runtime range", "supported runtime"]
CONF_LABEL = ["conflicts with", "clashes with", "cannot be combined with"]
INTRO = ["{A_env} called {env} is to receive {pkgs} from the {index}.",
         "Proposed install on {env}, {a_env}: the {pkgs} pinned at the end, taken from the {index} below.",
         "{env} ({a_env}) should get the {pkgs} listed under the pins, drawn from the {index}."]
RULES_HEAD = ["Conventions:", "Rules of this check:", "How to read the entries and when a set is clean:"]
CMP = ["Versions are compared number by number from the left, each number as a whole number: 1.10.0 is newer than 1.9.3, "
       "and 2.0.0 is newer than 1.12.7.",
       "To order two versions, compare the first numbers, then the second, then the third, always as whole numbers, so 0.10.1 "
       "comes after 0.9.8 and 1.2.10 after 1.2.9.",
       "Versions are ordered part by part as integers, not as text: 3.10.0 is later than 3.9.9, and 2.0.0 is later than 1.15.2."]
CMP_RT = ["Runtime versions have two numbers and are compared the same way (3.10 is newer than 3.9).",
          "The same holds for the two-part runtime versions: 2.10 comes after 2.9.",
          "Runtime versions (two parts) follow the same order, so 4.11 is later than 4.9."]
NOTA = ["After {a_pkg} name come one or more bounds separated by commas, and every bound must hold: >=V at least V, >V newer "
        "than V, <=V at most V, <V older than V, ==V exactly V, !=V any version except V.",
        "Bounds read as follows: >= at least, > strictly newer, <= at most, < strictly older, == exactly this version, != "
        "anything but this version; where several bounds follow one name, all of them apply.",
        "Each bound is an operator and a version: >= (that version or newer), > (newer only), <= (that version or older), < "
        "(older only), == (only that version), != (every version but that one); a list of bounds is met only when each bound is met."]
CLEAN_HEAD = ["The proposed set installs cleanly when ", "A clean install needs all of the following: ", "The set is clean only if "]
CLEAN_PARTS = {
    "listed": ["every pinned version is listed in the {index}", "each pin is a version that the {index} lists",
               "the {index} lists every pinned version"],
    "req": ["every requirement of every pinned version names {a_pkg} that is pinned at a version meeting all of its bounds",
            "for each pinned version, each {pkg} it {rl} is pinned too, at a version inside the stated bounds",
            "every requirement of a pinned version is met by the pin of the required {pkg}"],
    "rt": ["the runtime of the target environment meets every runtime bound of every pinned version",
           "the runtime of the environment satisfies the runtime bounds of all pinned versions",
           "each runtime bound of a pinned version holds for the environment's runtime"],
    "cf": ["no conflict entry of a pinned version applies to another pin",
           "no pinned version has a '{cl}' entry that applies to another pin",
           "none of the pinned versions has a conflict entry that applies to another pin"]}
ONLY = ["Only the entries of the pinned versions count; what the {index} says about other versions plays no part.",
        "Entries of versions that are not pinned are irrelevant.",
        "Requirements and other entries of versions without a pin do not matter."]
MISS = ["Nothing is installed besides the pins, so a requirement on {a_pkg} without a pin is not met.",
        "Only pinned {pkgs} get installed; a required {pkg} that has no pin counts as unmet.",
        "No {pkg} is added automatically: if a pinned version requires {a_pkg} that has no pin, that requirement fails."]
HARM = ["A pin that no pinned version requires does no harm by itself; its own entry is checked like that of every other pin.",
        "Pinning {a_pkg} that nothing needs is allowed, but the entry of that pinned version must still be met.",
        "Extra pins are fine: a pinned {pkg} that nothing requires is harmless as long as its own entry is satisfied."]
RTR = ["A runtime bound of a pinned version is met when the runtime of the target environment satisfies it; 'any' sets no runtime bound.",
       "The environment's runtime must satisfy each runtime bound of each pinned version ('any' means no bound).",
       "Runtime bounds are checked against the runtime of the target environment; a version marked 'any' runs on every runtime."]
CONF = ["An entry '{cl} P B' under a pinned version means that the set fails when P is pinned at a version meeting the bound B; "
        "it does not matter which of the two lists it, and an entry about {a_pkg} without a pin, or whose pin misses B, does no harm.",
        "If a pinned version has a '{cl}' entry naming another {pkg} and that {pkg} is pinned at a version inside the given bound, the set is not clean "
        "(whichever side lists it); entries about {pkgs} that are not pinned, or whose pin lies outside the bound, are harmless.",
        "Conflicts ('{cl}'): a pinned version that names {a_pkg} P with a bound blocks the set exactly when P is pinned at a version "
        "meeting that bound; if P has no pin, or its pin misses the bound, nothing happens."]
ENV = ["Target environment: {env}{rt}.", "Environment: {env} ({env_kind}){rt}.", "Install target: {env}{rt}."]
ENV_RT = [", runtime {r}", "; runtime version {r}", ", running runtime {r}"]
IHEAD = ["{Index} (one entry per listed version):", "Entries of the {index}:", "The {index} lists these versions:"]
PHEAD = ["Proposed pins:", "The proposal pins exactly these {pkgs}:", "Pins to install:"]
PIN = ["{name} {ver}", "{name} = {ver}", "{name} at {ver}"]
LEGEND = {"block": ["Each version line gives its entries separated by '|'.", "Entries of one version are separated by '|'.",
                    "On a version line, '|' separates the entries."],
          "table": ["A '-' in a cell means none.", "Cells with '-' are empty.", "'-' marks an empty cell."],
          "facts": ["Every line states one fact about one listed version{cf}.", "One fact per line{cf}.",
                    "Each line holds a single fact about a version{cf}."]}
LEGEND_CF = ["; a version without a '{cl}' line has no such entry", ", and a version with no '{cl}' line declares none",
             "; no '{cl}' line means none"]
TCOL = [("package", "version", "package", "pinned version"), ("name", "version", "name", "pin"),
        ("{pkg}", "version", "{pkg}", "pinned at")]


def make_look(rng, spec, plan):
    """every rendering choice of a pair (shared by its two members)"""
    lk = {k: rng.randrange(3) for k in ("intro", "head", "cmp", "cmp_rt", "nota", "clean", "only", "miss", "harm", "rtr", "conf",
                                         "env", "ihead", "phead", "pin", "legend", "lcf", "tcol", "rl", "tl", "cl")}
    lk["layout"], lk["domain"] = plan["layout"], plan["domain"]
    lk["vorder"] = rng.choice(["asc", "desc", "mixed"])
    lk["pkg_order"] = list(range(len(spec["pkgs"])))
    rng.shuffle(lk["pkg_order"])
    lk["vperm"] = []
    for pk in spec["pkgs"]:
        perm = list(range(len(pk["vs"])))
        rng.shuffle(perm)
        lk["vperm"].append(perm)
    return lk


def render(spec, lk):
    pk, level, lay = spec["pkgs"], spec["level"], lk["layout"]
    d = DOMAINS[lk["domain"]]
    rl, tl, cl = REQ_LABEL[lk["rl"]], RT_LABEL[lk["tl"]], CONF_LABEL[lk["cl"]]
    f = {"env": spec["env"], "a_env": d["a_env_kind"], "A_env": d["a_env_kind"][0].upper() + d["a_env_kind"][1:],
         "env_kind": d["env_kind"], "pkg": d["pkg"], "a_pkg": d["a_pkg"], "pkgs": d["pkgs"], "index": d["index"],
         "Index": d["index"][0].upper() + d["index"][1:], "rl": rl, "cl": cl}
    parts = ["listed", "req"] + (["rt"] if level >= 2 else []) + (["cf"] if level >= 3 else [])
    ptxt = [CLEAN_PARTS[k][lk["clean"]].format(**f) for k in parts]
    if lk["clean"] == 1:
        body = "; ".join(ptxt)
    elif len(ptxt) == 2:
        body = ptxt[0] + " and " + ptxt[1]
    else:
        body = ", ".join(ptxt[:-1]) + ", and " + ptxt[-1]
    clean = CLEAN_HEAD[lk["clean"]] + body + "."
    rules = [CMP[lk["cmp"]] + (" " + CMP_RT[lk["cmp_rt"]] if level >= 2 else ""), NOTA[lk["nota"]].format(**f), clean,
             ONLY[lk["only"]].format(**f), MISS[lk["miss"]].format(**f), HARM[lk["harm"]].format(**f)]
    if level >= 2:
        rules.append(RTR[lk["rtr"]])
    if level >= 3:
        rules.append(CONF[lk["conf"]].format(**f))
    lines = [INTRO[lk["intro"]].format(**f), "", RULES_HEAD[lk["head"]]]
    for k, r in enumerate(rules, 1):
        lines.append({"block": "- ", "table": "%d. " % k, "facts": "* "}[lay] + r)
    rt = ENV_RT[lk["env"]].format(r=vstr(spec["runtime"])) if spec["runtime"] else ""
    lines += ["", ENV[lk["env"]].format(rt=rt, **f), "", IHEAD[lk["ihead"]].format(**f)]
    lcf = LEGEND_CF[lk["lcf"]].format(cl=cl) if level >= 3 else ""
    lines.append(LEGEND[lay][lk["legend"]].format(cf=lcf))
    cols = [c.format(**f) for c in TCOL[lk["tcol"]]]

    def vorder(p):
        idx = list(range(len(pk[p]["vs"])))
        return idx[::-1] if lk["vorder"] == "desc" else lk["vperm"][p] if lk["vorder"] == "mixed" else idx

    def texts(e):
        req = ["%s %s" % (pk[q]["name"], ",".join(op + vstr(b) for op, b in bs)) for q, bs in e["req"]]
        rtb = ",".join(op + vstr(b) for op, b in e["rt"])
        conf = ["%s %s%s" % (pk[q]["name"], op, vstr(b)) for q, (op, b) in e["conf"]]
        return req, rtb, conf

    if lay == "table":
        head = cols[:2] + [rl] + ([tl] if level >= 2 else []) + ([cl] if level >= 3 else [])
        lines += ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for p in lk["pkg_order"]:
        if lay == "block":
            lines.append(pk[p]["name"] + ":")
        for t in vorder(p):
            req, rtb, conf = texts(pk[p]["ent"][t])
            ver = vstr(pk[p]["vs"][t])
            if lay == "block":
                fl = ["%s: %s" % (rl, "; ".join(req) or "nothing")]
                if level >= 2:
                    fl.append("%s: %s" % (tl, rtb or "any"))
                if level >= 3:
                    fl.append("%s: %s" % (cl, "; ".join(conf) or "none"))
                lines.append("  %s | %s" % (ver, " | ".join(fl)))
            elif lay == "table":
                cells = [pk[p]["name"], ver, "; ".join(req) or "-"] + ([rtb or "any"] if level >= 2 else []) \
                    + (["; ".join(conf) or "-"] if level >= 3 else [])
                lines.append("| " + " | ".join(cells) + " |")
            else:
                hd = "%s %s" % (pk[p]["name"], ver)
                lines += ["%s %s %s" % (hd, rl, r) for r in req] or ["%s %s nothing" % (hd, rl)]
                if level >= 2:
                    lines.append("%s %s %s" % (hd, tl, rtb or "any"))
                if level >= 3:
                    lines += ["%s %s %s" % (hd, cl, c) for c in conf]
    lines += ["", PHEAD[lk["phead"]].format(**f)]
    if lay == "table":
        lines += ["| %s | %s |" % (cols[2], cols[3]), "|---|---|"]
    for p, v in spec["pins"]:
        if lay == "table":
            lines.append("| %s | %s |" % (pk[p]["name"], vstr(v)))
        else:
            lines.append(("- " if lay == "block" else "") + PIN[lk["pin"]].format(name=pk[p]["name"], ver=vstr(v)))
    return "\n".join(lines)


# ----------------------------------------------------------------------------------------------------------- plan
BFORMS = ["included", "excluded", "unlisted", "included", "excluded", "eq", "ne"]


def make_plan():
    """per level: kinds as equal as the numbers allow, layouts, domains and look-alike names balanced; bound forms cycle
    (positive ON an included bound as often as negative ON an excluded bound); every second included / excluded / unlisted
    bound pair uses the 1.9-versus-1.10 neighbours; every third runtime pair a runtime of x.9 or x.10"""
    rng = rng_for("plan")
    plan, doms = [], sorted(DOMAINS)
    for level in (1, 2, 3):
        kinds = LEVELS[level]["kinds"]
        cols = [[kinds[t % len(kinds)] for t in range(PAIRS_PER_LEVEL)], [LAYOUTS[t % 3] for t in range(PAIRS_PER_LEVEL)],
                [doms[t % len(doms)] for t in range(PAIRS_PER_LEVEL)], [t % 2 == 0 for t in range(PAIRS_PER_LEVEL)]]
        for c in cols:
            rng.shuffle(c)
        rows = [{"level": level, "kind": k, "layout": la, "domain": d, "sibling": s} for k, la, d, s in zip(*cols)]
        forms = [BFORMS[t % len(BFORMS)] for t in range(sum(r["kind"] == "bound" for r in rows))]
        rng.shuffle(forms)
        seen = collections.Counter()
        for r, fm in zip([r for r in rows if r["kind"] == "bound"], forms):
            r["form"], r["trap"] = fm, fm in ("included", "excluded", "unlisted") and seen[fm] % 2 == 0
            seen[fm] += 1
        for t, r in enumerate(r for r in rows if r["kind"] == "runtime"):
            r["rt_trap"] = t % 3 == 0
        for t, r in enumerate(r for r in rows if r["kind"] == "conflict"):
            r["sub"] = ["declared_by_other", "declared_by_moved"][t % 2]
        plan += rows
    return plan


def unrequired_pins(spec):
    """number of pins that no pinned version requires (the members of a pair must not differ in it: an independent review found
    that this count alone separated the classes when only the negative's count could move)"""
    j = spec_json(spec)
    ent = {(p["name"], v["version"]): v for p in j["packages"] for v in p["versions"]}
    req = {r[0] for n, v in j["pins"] for r in (ent[(n, v)]["requires"] if (n, v) in ent else [])}
    return sum(1 for n, _ in j["pins"] if n not in req)


def spec_json(spec):
    pk = spec["pkgs"]
    bl = lambda bounds: [[op, vstr(b)] for op, b in bounds]
    return {"level": spec["level"], "environment": spec["env"], "runtime": vstr(spec["runtime"]) if spec["runtime"] else None,
            "packages": [{"name": p["name"], "versions": [
                {"version": vstr(v), "requires": [[pk[q]["name"], bl(b)] for q, b in e["req"]], "runtime": bl(e["rt"]),
                 "conflicts": [[pk[q]["name"], [op, vstr(b)]] for q, (op, b) in e["conf"]]} for v, e in zip(p["vs"], p["ent"])]}
                for p in pk],
            "pins": [[pk[p]["name"], vstr(v)] for p, v in spec["pins"]]}


def vocabulary_test(rows, min_freq=20, max_ratio=2.0):
    """as audit_v3: no word of frequency >= 20 may occur in the states of one class at more than twice the rate of the other"""
    sets = {"yes": collections.Counter(), "no": collections.Counter()}
    for r in rows:
        sets[r["gold"]].update(set(re.findall(r"[a-z]+", r["state"].lower())))
    ny, nn = sum(r["gold"] == "yes" for r in rows), sum(r["gold"] == "no" for r in rows)
    worst = 1.0
    for w in set(sets["yes"]) | set(sets["no"]):
        a, b = sets["yes"][w], sets["no"][w]
        if a + b >= min_freq:
            ra, rb = a / ny, b / nn
            ratio = max(ra, rb) / min(ra, rb) if min(ra, rb) > 0 else float("inf")
            assert ratio <= max_ratio, (w, a, b)
            worst = max(worst, ratio)
    return worst


# ----------------------------------------------------------------------------------------------------------- main
def main():
    plan = make_plan()
    built, retries = [], collections.Counter()
    for idx, pl in enumerate(plan):
        for attempt in range(500):
            rng = rng_for("pair", idx, attempt)
            try:
                P, N, R = build_pair(rng, pl)
            except Retry as e:
                retries[str(e)] += 1
                continue
            if unrequired_pins(P) != unrequired_pins(N):
                retries["unrequired-pin count differs within the pair"] += 1
                continue
            break
        else:
            raise RuntimeError("pair %d could not be built" % idx)
        lk = make_look(rng_for("look", idx), P, pl)
        tp, tn = render(P, lk), render(N, lk)
        lp, ln = tp.split("\n"), tn.split("\n")
        assert len(lp) == len(ln) and sum(a != b for a, b in zip(lp, ln)) == 1, idx
        assert len(P["pins"]) == len(N["pins"]) and sum(a != b for a, b in zip(P["pins"], N["pins"])) == 1
        assert abs(len(tp) - len(tn)) <= 2
        assert unrequired_pins(P) == unrequired_pins(N)
        built.append((idx, pl, P, N, R, tp, tn))
    rows = []
    for idx, pl, P, N, R, tp, tn in built:
        for member, spec, text in (("positive", P, tp), ("negative", N, tn)):
            viol = violations(spec)
            assert truth(spec) == (member == "positive") == (not viol)
            if member == "negative":
                assert planted_ok(pl["kind"], R, viol)
            meta = {"source_id": None, "seed": SEED, "level": pl["level"], "domain": pl["domain"],
                    "deviation": pl["kind"] if member == "negative" else None, "pair_kind": pl["kind"], "order": None,
                    "member": member, "layout": pl["layout"], "bound_form": R["form"], "trap": bool(pl.get("trap") or pl.get("rt_trap")),
                    "conflict_sub": R["sub"] if pl["kind"] == "conflict" else None, "roles": R["names"],
                    "violations": [describe(spec, v) for v in viol], "pins": len(spec["pins"]), "packages": len(spec["pkgs"]),
                    "listed_versions": sum(len(p["vs"]) for p in spec["pkgs"]),
                    "shortcut_wrong": [nm for nm, kw in SHORTCUTS if (not violations(spec, **kw)) != truth(spec)],
                    "spec": spec_json(spec)}
            rows.append({"_pair": idx, "state": text, "gold": "yes" if member == "positive" else "no", "meta": meta})
    rng_for("order").shuffle(rows)
    gnum = {}
    for k, r in enumerate(rows, 1):
        gnum.setdefault(r["_pair"], len(gnum) + 1)
        r["id"], r["group"] = "%s:%05d" % (ID_PREFIX, k), "%s:g%04d" % (ID_PREFIX, gnum[r["_pair"]])
        r["meta"]["source_id"] = "%05d" % k
    orng = rng_for("options")
    for level in (1, 2, 3):
        for gold in ("yes", "no"):
            idx = [k for k, r in enumerate(rows) if r["gold"] == gold and r["meta"]["level"] == level]
            flags = [True] * (len(idx) // 2) + [False] * (len(idx) - len(idx) // 2)
            orng.shuffle(flags)
            for k, yes_first in zip(idx, flags):
                rows[k]["meta"]["order"] = ["yes", "no"] if yes_first else ["no", "yes"]
    items = [{"id": r["id"], "state": r["state"],
              "questions": {"q": {"type": "choice", "instructions": INSTRUCTIONS,
                                  "criteria": {k: OPTIONS[k] for k in r["meta"]["order"]}}},
              "gold": r["gold"], "soft": None, "group": r["group"], "meta": r["meta"]} for r in rows]
    # ---- balance, duplicates, vocabulary
    cls = collections.Counter((it["meta"]["level"], it["gold"]) for it in items)
    assert all(cls[(lv, g)] == PAIRS_PER_LEVEL for lv in (1, 2, 3) for g in ("yes", "no")), cls
    dev = collections.Counter((it["meta"]["level"], it["meta"]["deviation"]) for it in items if it["meta"]["deviation"])
    for lv in (1, 2, 3):
        ks = LEVELS[lv]["kinds"]
        cnt = [dev[(lv, k)] for k in ks]
        assert sum(cnt) == PAIRS_PER_LEVEL and max(cnt) - min(cnt) <= 1, cnt
    first = collections.Counter((it["meta"]["level"], it["gold"], it["meta"]["order"][0]) for it in items)
    assert all(first[(lv, g, "yes")] == first[(lv, g, "no")] for lv in (1, 2, 3) for g in ("yes", "no")), first
    assert len({it["state"] for it in items}) == len(items), "duplicate state"
    assert len(items) == 3 * 2 * PAIRS_PER_LEVEL
    worst = vocabulary_test(rows)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "items.jsonl"), "w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")
    stats = summarise(items, built, retries, worst)
    write_task_json(stats)
    write_readme(items, stats)
    for line in stats["print"]:
        print(line)


def summarise(items, built, retries, worst):
    s = {"worst_vocab": worst, "retries": sum(retries.values()), "retry_reasons": dict(retries)}
    s["dev"] = collections.Counter((it["meta"]["level"], it["meta"]["deviation"]) for it in items if it["meta"]["deviation"])
    s["len"] = {}
    for lv in (1, 2, 3):
        ls = sorted(len(it["state"]) for it in items if it["meta"]["level"] == lv)
        s["len"][lv] = (ls[0], ls[len(ls) // 2], ls[-1])
    s["forms"] = collections.Counter((pl["level"], R["form"], bool(pl.get("trap"))) for _, pl, _, _, R, _, _ in built if pl["kind"] == "bound")
    s["rt_trap"] = collections.Counter(pl["level"] for _, pl, _, _, _, _, _ in built if pl.get("rt_trap"))
    s["sub"] = collections.Counter((pl["level"], pl["sub"]) for _, pl, _, _, _, _, _ in built if pl["kind"] == "conflict")
    s["short"] = {}
    for nm, _ in SHORTCUTS:
        for lv in (1, 2, 3):
            for g in ("yes", "no"):
                s["short"][(nm, lv, g)] = sum(nm in it["meta"]["shortcut_wrong"] for it in items
                                              if it["meta"]["level"] == lv and it["gold"] == g)
    d = collections.Counter()
    for _, _, _, _, _, tp, tn in built:
        d["equal" if len(tp) == len(tn) else "positive longer" if len(tp) > len(tn) else "negative longer"] += 1
    s["lendiff"] = dict(d)
    checks, dec = [], []
    for _, pl, P, _, _, _, _ in built:
        if pl["level"] == 3:
            pins = dict(P["pins"])
            checks.append(sum(sum(len(b) for _, b in e["req"]) + len(e["rt"]) + len(e["conf"])
                              for p, v in P["pins"] for e in [P["pkgs"][p]["ent"][P["pkgs"][p]["vs"].index(v)]]))
            dec += [any(not holds(pins[q], op, b) for op, b in bs) for p in pins for t, e in enumerate(P["pkgs"][p]["ent"])
                    if P["pkgs"][p]["vs"][t] != pins[p] for q, bs in e["req"] if q in pins]
    checks.sort()
    s["checks3"] = "%d to %d, median %d" % (checks[0], checks[-1], checks[len(checks) // 2])
    s["decoy_fail3"] = 100.0 * sum(dec) / len(dec)
    s["chain"] = sum(1 for _, pl, P, _, R, _, _ in built if pl["level"] == 3
                     and 2 <= (R["Y"] if pl["kind"] == "missing" else R["X"]) <= P["links"])
    pr = ["class x level: " + "  ".join("L%d yes %d no %d" % (lv, PAIRS_PER_LEVEL, PAIRS_PER_LEVEL) for lv in (1, 2, 3))]
    pr.append("deviation x level: " + "; ".join("L%d " % lv + " ".join("%s %d" % (k, s["dev"][(lv, k)]) for k in LEVELS[lv]["kinds"])
                                                 for lv in (1, 2, 3)))
    pr.append("state chars min/median/max: " + "  ".join("L%d %d/%d/%d" % ((lv,) + s["len"][lv]) for lv in (1, 2, 3)))
    pr.append("pair length difference: %s" % s["lendiff"])
    for nm, _ in SHORTCUTS:
        pr.append("shortcut %-20s accuracy L1 %.3f  L2 %.3f  L3 %.3f  (wrong on yes/no: %d/%d)" % (
            (nm,) + tuple(1 - (s["short"][(nm, lv, "yes")] + s["short"][(nm, lv, "no")]) / (2.0 * PAIRS_PER_LEVEL) for lv in (1, 2, 3))
            + (sum(s["short"][(nm, lv, "yes")] for lv in (1, 2, 3)), sum(s["short"][(nm, lv, "no")] for lv in (1, 2, 3)))))
    pr.append("retries %d %s | vocabulary worst ratio %.2f" % (s["retries"], dict(retries), worst))
    s["print"] = pr
    return s


def write_task_json(s):
    split = "generated, seed %d" % SEED + ("" if BENCH_SEED is None else " (sealed split)")
    task = {"task": TASK, "layer": "E", "title": "Generated package indexes: does the proposed set of pinned versions install cleanly?",
            "decision": "whether every pinned version is listed, every requirement of every pinned version is met by a pin, the "
                        "runtime fits every pinned version and no conflict applies (yes), or exactly one of these fails (no)",
            "source": {"name": "generator build/gen_%s.py" % TASK, "url": "", "files": [], "split": split,
                       "version": "script of 2026-10-07"},
            "licence": "generated by the benchmark's script (no third-party text)", "redistribution": "items included",
            "labels": "programmatic", "item_source": "generated", "metric": "accuracy", "chance": 0.5,
            "rows": 6 * PAIRS_PER_LEVEL, "groups": 3 * PAIRS_PER_LEVEL, "question_type": "choice", "options": 2,
            "notes": ("600 items = 300 contrast pairs (group): the two members share every line of the state except one pin line; the "
                      "negative breaks exactly one condition (bound, missing, own_req, runtime, conflict; meta.deviation). Levels 1-3 "
                      "(meta.level, 200 items each). All package and environment names are invented; the truth is computed on the "
                      "structured specification (meta.spec). The number of pins that no pinned version requires is the same in both members of "
                      "every pair (otherwise it separates the classes without any version comparison). State length %d to %d characters."
                      % (min(v[0] for v in s["len"].values()), max(v[2] for v in s["len"].values()))),
            "skill": "find the entry of each pinned version among look-alike entries and check every requirement, runtime bound and "
                     "conflict against the pins with number-by-number version comparison",
            "knobs": "pins 4-5 / 6-8 / 9-12; versions per package 1-2 / 2-3 / 3-4; runtime from level 2; conflicts and a chain "
                     "of three requirements at level 3; 1.9-versus-1.10 neighbours; bounds on, just inside and just beyond a limit"}
    with open(os.path.join(OUT_DIR, "task.json"), "w") as fh:
        json.dump(task, fh, indent=1)


def fmt_item(it):
    m = it["meta"]
    out = ["id `%s` (group `%s`, level %d, gold **%s**, deviation `%s`, layout %s)" % (it["id"], it["group"], m["level"], it["gold"],
                                                                                       m["deviation"], m["layout"]), "", "```",
           it["state"], "```", "", "question: " + it["questions"]["q"]["instructions"], ""]
    out += ["- `%s`: %s" % kv for kv in it["questions"]["q"]["criteria"].items()]
    if m["violations"]:
        out += ["", "planted problem: " + "; ".join(m["violations"])]
    return "\n".join(out)


def write_readme(items, s):
    ex = []
    for lv, gold in ((1, "no"), (2, "yes"), (3, "no")):
        ex.append(next(it for it in items if it["meta"]["level"] == lv and it["gold"] == gold))
    dev_rows = "\n".join("| `%s` | %s |" % (k, " | ".join(str(s["dev"][(lv, k)]) if k in LEVELS[lv]["kinds"] else "-" for lv in (1, 2, 3)))
                         for k in KINDS)
    form_rows = "\n".join("| %s | %s |" % (fm, " | ".join("%d (%d with 1.9 / 1.10)" % (
        s["forms"][(lv, fm, False)] + s["forms"][(lv, fm, True)], s["forms"][(lv, fm, True)]) for lv in (1, 2, 3)))
        for fm in ("included", "excluded", "unlisted", "eq", "ne"))
    short_rows = "\n".join("| %s | %s | %d / %d |" % (nm, " | ".join("%.3f" % (1 - (s["short"][(nm, lv, "yes")] + s["short"][(nm, lv, "no")])
                                                                       / (2.0 * PAIRS_PER_LEVEL)) for lv in (1, 2, 3)),
                                                     sum(s["short"][(nm, lv, "yes")] for lv in (1, 2, 3)),
                                                     sum(s["short"][(nm, lv, "no")] for lv in (1, 2, 3))) for nm, _ in SHORTCUTS)
    txt = """# %(task)s

Generated package indexes: does the proposed set of pinned versions install cleanly in the target environment?
(layer E, generated, programmatic truth)

- Question (same for every item): "%(q)s" Options `yes` / `no` (order drawn per item, balanced inside every level and class).
- Source: generator `build/gen_%(task)s.py` (Python 3.9, standard library only, root seed %(seed)d; identical output on every run).
  `BENCH_OUT=<dir>` writes elsewhere; `BENCH_SEED=<k>` (only with `BENCH_OUT`) gives a sealed split of the same design.
- Rows: 600 = 300 contrast pairs, 200 per level, 300 yes / 300 no; metric accuracy, chance 0.5.

## What is generated

A state of four parts: the conventions in plain words; the target environment (from level 2 with its runtime version);
the index of an invented %(pkgs)s registry - every listed version of every package with its requirements (a package name and
one or more bounds `>=V`, `>V`, `<=V`, `<V`, `==V`, `!=V`), from level 2 its runtime bounds, at level 3 its conflict entries;
and the proposed pins (one package at one version per line). Three layouts (an indented block, a pipe table, one fact per
line), five domains (pipeline plugins, firmware modules, analysis packages, game-server extensions, robot components), three
phrasings for every convention sentence and every label, versions listed oldest first, newest first or mixed. Package names are
built from invented syllables; some pairs of names share a stem (look-alikes).

## Conventions written into every state

1. Versions compare number by number as whole numbers (1.10.0 is newer than 1.9.3); runtime versions have two numbers and
   compare the same way (from level 2).
2. The meaning of every operator; several bounds after one name must all hold.
3. The set installs cleanly when every pinned version is listed, every requirement of every pinned version names a package that
   is pinned at a version inside all its bounds, (level 2+) the environment's runtime meets every runtime bound of every pinned
   version, and (level 3) no conflict entry of a pinned version applies to another pin.
4. Only the entries of pinned versions count. 5. Nothing is installed besides the pins (a requirement on an unpinned package
   fails). 6. Pins that nothing requires do no harm, but their own entries are checked. 7. (level 2+) `any` = no runtime bound.
8. (level 3) a conflict applies when the named package is pinned at a version meeting its bound, whichever side lists it.

## Levels

| level | pins | unpinned packages in the index | versions per package | runtime | conflicts | requirement chain from the first pin |
|---|---|---|---|---|---|---|
| 1 | 4-5 | 2 | 1-2 | - | - | 1-2 links |
| 2 | 6-8 | 2-3 | 2-3 | yes | - | 2 links |
| 3 | 9-12 | 3 | 3-4 | yes | yes | 3 links |

State length (characters, min / median / max): level 1 %(l1)s, level 2 %(l2)s, level 3 %(l3)s.

**What makes level 3 hard.** To answer yes the reader must, for each of 9-12 pins, (1) find the entry of the pinned version
among 3-4 look-alike entries of that package (the other entries differ in their bounds, and %(decoy_fail3).0f%% of their requirements on
pinned packages would fail with the given pins), (2) look up the pin of every package it requires (1-3 per entry) and
compare versions number by number (several packages have 1.9 / 1.10 neighbours), (3) compare its runtime bounds with the
environment's runtime and (4) check its conflict entries against the pins: %(checks3)s checks per positive. A negative fails on one link that combines at least
three facts from different places: the pin of the dependant, the entry of that pinned version in the index and the pin (or the
missing pin) of the required package - for `own_req`, `runtime` and `conflict` also the entry of the moved version. In %(chain)d of the
100 level-3 pairs the moved or missing package is the second or third link of the chain of three requirements. Decoys in both classes: failing bounds and
runtime bounds under versions that are not pinned, conflicts under unpinned versions or about unpinned packages, pins that
nothing requires, pins exactly on an included bound or just inside an excluded one.

## Planted problems (negatives; the positive of the pair differs in that one pin line)

| `meta.deviation` | level 1 | level 2 | level 3 |
|---|---|---|---|
%(dev_rows)s

- `bound`: one pin moved to the neighbouring listed version, just outside the bound of ONE dependant; all other dependants accept
  it and its own entry is met. Bound forms (the positive sits ON an included bound or just inside an excluded one; the negative one
  listed step beyond):

| form | level 1 | level 2 | level 3 |
|---|---|---|---|
%(form_rows)s

- `own_req`: one pin moved to a neighbouring listed version that every dependant accepts, but one bound of its own entry misses the
  pin of another package by one step.
- `missing`: the pin line of a package that exactly one pinned version requires is replaced by a pin of a package that nothing
  requires (same number of lines, same line width; half of these pairs use look-alike names with a common stem).
- `runtime` (levels 2-3): one pin moved to a neighbouring version whose runtime bound the environment misses by one step (a third
  of these pairs use a runtime of x.9 or x.10 against x.10 / x.9: %(rt_trap)s pairs).
- `conflict` (level 3): one pin moved to a neighbouring version so that one conflict applies: declared by another pin about the
  moved package (%(sub_o)d pairs) or declared by the moved version about another pin (%(sub_m)d pairs).

## Shortcut readers (computed on the specification; accuracy per level, then wrong answers on yes / no items)

| reader | level 1 | level 2 | level 3 | wrong yes / no |
|---|---|---|---|---|
%(short_rows)s

`text_compare` compares versions as text (1.10.0 before 1.9.3); `strict_as_inclusive` reads > and < as >= and <=;
`newest_entry` reads the entry of the newest listed version instead of the pinned one; the other three skip one convention.

## Checks made by the script

- The truth is computed on the structured specification (`truth(spec)`: no entry in `violations(spec)`); the text is rendered
  from the same specification.
- Every positive has no violation; every negative has exactly one violation and it is the planted one (kind, package and side
  asserted); the two members have the same index, the same number of pins and of lines, and their states differ in exactly one
  line (length difference at most 2 characters: %(lendiff)s).
- Every bound helper asserts that a passing requirement is met by the versions it must accept and a failing one misses by
  exactly one bound; look-alike entries of a package never coincide with another entry of it.
- Classes 100 / 100 in every level; deviation kinds as equal as the numbers allow in every level; `yes` listed first in exactly
  half of the yes items and half of the no items of every level; no duplicate state; no word of frequency >= 20 occurs in one
  class at more than twice the rate of the other (worst ratio %(worst).2f).
- Retries of unlucky draws (a fresh sub-seed per attempt): %(retries)d in total.

## Examples (one per level)

%(examples)s

## Independence from training generators

This generator is new and was written for the benchmark only; its names, sentences, layouts and logic share no template with
the authors' training-data generators, and no item is taken from an existing data set.
""" % {"task": TASK, "q": INSTRUCTIONS, "seed": SEED, "pkgs": "package", "dev_rows": dev_rows, "form_rows": form_rows,
       "short_rows": short_rows, "l1": "%d / %d / %d" % s["len"][1], "l2": "%d / %d / %d" % s["len"][2],
       "l3": "%d / %d / %d" % s["len"][3], "rt_trap": " / ".join("level %d: %d" % (lv, s["rt_trap"][lv]) for lv in (2, 3)),
       "sub_o": s["sub"][(3, "declared_by_other")], "sub_m": s["sub"][(3, "declared_by_moved")], "lendiff": s["lendiff"],
       "worst": s["worst_vocab"], "chain": s["chain"], "checks3": s["checks3"], "decoy_fail3": s["decoy_fail3"], "retries": s["retries"], "examples": "\n\n".join("### level %d\n\n%s" % (it["meta"]["level"], fmt_item(it)) for it in ex)}
    with open(os.path.join(OUT_DIR, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(txt)


if __name__ == "__main__":
    main()
