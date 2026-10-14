"""Task state_goal (layer D, generated): "after these operations, are all goal conditions satisfied?"
    python3 generators/state_goal.py                (standard library only; no argument, no input file, no download)

ITEM.  `state` is one text: a line saying what kind of store it is, a true statement of what every step did (see PREAMBLE), the files
of a small folder tree at the start (6 to 15 files, each with a one-word status as content), what the five kinds of step do (`set`,
`delete`, `rename`, `copy`, `move`; one line each, including what happens when the target path is already taken), a goal written as a
list of conditions on the final tree, and a numbered trace of the steps that an agent ran (5, 15 or 25 steps).  Question: "After
these operations, are all goal conditions satisfied?"  yes / no.
PREAMBLE (gen_v4).  "Every delete, rename, copy and move found its source file; set creates the file or replaces its content; every
step changed the store."  (four phrasings).  The script asserts this for every step of every trace of all 600 items, and `check`
asserts it again on the parsed text; there are no failed or empty steps, so a wrong step can never be recognised by looking odd.
Conditions: `exists`, `absent`, `content` (a file holds a given word), `count` (a folder holds N files directly inside it, not
counting sub-folders) and `same` (two files hold the same word).  Every condition of a goal is *sensitive*: it changes its truth
value when at least one step of the trace is left out, so each goal reaches into the trace.

NATURAL CONTENT (gen_v4).  Five domains (office reports, software project, data analysis, website, course material), each with its
own small vocabulary of ordinary folder and file names (reports/q3_summary.md, data/customers_2026.csv, logs/app.log, releases/v2.1,
...) and status words as contents (draft, review, approved, final, outdated, archived, v1, v2, raw, clean, ...).  Renames stay inside
one file family (q3_summary_draft.md -> q3_summary_final.md) and keep the extension.  The trace is built from goal-directed
*macros* of one to three steps (archive an old file, publish a final version, rename a draft to final, clean up temporary files,
back up before overwriting, restore from the backup, rotate a log, make a new version, advance a status, create a new file, move an
incoming file where it belongs); every step of every trace belongs to a macro.  Steps that no goal condition looks at are
distractors, and they are macros as well.  Goal conditions preferably describe what a macro was meant to achieve (the archived file
exists and the old path is gone, the published copy holds `final`, the backup and the restored file have the same content).
Every operation of every trace, planted deviations included, is *plausible*: a file is only moved into a folder that takes files of
its kind, a rename keeps the file family and the extension, a copy keeps the family, a content word fits the kind of file.
Every trace, planted deviations included, is also *macro-coherent*: `coherent(ops, files0, ctx)` cuts it into whole macros (the
preconditions of the macros are written out once more as a recognizer).  So the planted change is a wrong choice inside valid
macros (the wrong file archived, the wrong status written, two macros in the wrong order, a macro left out), never a broken macro,
and a deviation cannot be found by looking at the structure of the trace.  (Without this filter a recognizer separated the classes
at about 84 per cent.)
Two more cues are closed.  (a) Every file or folder that a goal condition names is touched by some step of the trace, in both classes
(`untouched_conditions`; the left-out step of `step_missing` is never the only toucher of the failing condition's target, and the inserted
step never touches it) - before, 22 per cent of the negatives failed on a target that no step touches and no positive had one.  (b) The
two members of a pair have the same number of dead steps (`dead_steps`: steps outside the dependency cone of every goal condition).

DESIGN.  The items come in matched pairs.  A *base* is a trace of macros that reaches the goal (gold yes; the goal is chosen from
its final tree).  Its twin is the same item with one operation of the trace changed, searched so that *exactly one* goal condition
fails and every step still runs and changes the tree (gold no):
    wrong_target   (v0: wrong_key)    one step acts on the wrong target: one path (source, destination, new name or folder) of one
                                      step is replaced by another path or name of the same kind that occurs in the item (a sibling
                                      file, the same file name in another folder, another folder that takes such files); the
                                      failing goal can be of any type, a folder count included
    wrong_content  (v0: wrong_value)  the content word of one `set` step is replaced by another word that fits the file
    steps_swapped  (v0: swap)         two steps (at most four places apart) exchange their places and the order matters
    step_missing   (v0: missing)      one step is left out and an unrelated single-step macro is inserted elsewhere, so the trace
                                      keeps its length (the inserted step is checked to be irrelevant: the failing condition is the
                                      same without it)
Both members of a pair share the start, the goal, the phrasing and all other steps, so positives and negatives have the same
distribution of sizes, vocabulary and kinds of step by construction; a pair is two independent rows (`meta.pair`, also `group`).  No change adds
or removes a word: the set of words of the state is the same in both members of a pair, and every word of the goal also occurs in
the start list or the trace (so a goal that names a file that no step could have produced cannot give a negative away).

DIAL.  `meta.level` = 1, 2, 3 = number of steps 5, 15, 25 (`meta.steps` keeps the number; 100 pairs per level, 25 per deviation kind
and level; 200 rows per level).  Start size grows with the level (6-8, 8-12, 11-15 files) as does the goal (3, 5, 7 conditions).

TRUTH TWICE.  `truth(spec)` simulates the trace on the structured specification (a dict of path -> content).  `check(item)` parses
the rendered state text (the file list in one of four layouts, the goal in one of four wordings, the trace in one of four notations
and four numbering styles) and re-simulates it on a different data structure (folder -> {name: content}), asserting the preamble on
the way.  The script asserts that both agree on all 600 items; that the negative differs from its twin by exactly one change, fails
exactly one condition (recorded in `meta.failed_condition`) and still runs every step; that every operation is plausible and every
rename keeps its extension; that the classes, the levels, the domains and the deviation kinds are exactly balanced; and the
vocabulary test (no word of frequency >= 20 at more than twice the rate in one class)."""
import collections
import copy
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))                    # generators/
ROOT = os.path.join(os.path.dirname(HERE), "generated")              # the items are written to ROOT/tasks/<family>/
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "audits"))    # validate.py and audit.py (run on ROOT/tasks/<family>/)
TASK, SEED = "state_goal", 20261007
OUT = os.path.join(ROOT, "tasks", TASK)
LEVELS = [5, 15, 25]
LEVEL_OF = {5: 1, 15: 2, 25: 3}
KINDS = ["wrong_target", "wrong_content", "steps_swapped", "step_missing"]
OLD_NAME = {"wrong_target": "wrong_key", "wrong_content": "wrong_value", "steps_swapped": "swap", "step_missing": "missing"}
PER_CELL = [25, 25, 25, 25]
N_ENTRIES = {5: (6, 8), 15: (8, 12), 25: (11, 15)}
N_CONDS = {5: 3, 15: 5, 25: 7}
QUESTION = {"type": "choice", "instructions": "After these operations, are all goal conditions satisfied?",
            "criteria": {"yes": "Every goal condition holds after the last step.",
                         "no": "At least one goal condition does not hold after the last step."}}


def sub(label):
    """a sub-generator derived from the master generator random.Random(20261007) and a label (deterministic)"""
    return random.Random(f"{random.Random(SEED).getrandbits(64)}/{label}")


def dirname(p):
    return p.rsplit("/", 1)[0]


def basename(p):
    return p.rsplit("/", 1)[1]


def ext_of(name):
    return name.rsplit(".", 1)[1]


# ----------------------------------------------------------------------------------------------------------------
# vocabulary: five domains; each folder has a role, each file name belongs to a kind and a family (topic)
# ----------------------------------------------------------------------------------------------------------------
# roles: work (where the live files of the kind are kept), draft, pub (published), arch (archive), bak (backup), tmp, inbox, log, cfg
DOMAINS = {
    "office": {
        "about": "the quarterly reports and working papers of a small office",
        "dirs": {"work": ["reports", "reports/2026"], "draft": ["drafts"], "pub": ["published"], "arch": ["archive", "archive/2025"],
                 "bak": ["backup"], "tmp": ["tmp"], "inbox": ["inbox"]},
        "kinds": {"doc": (["q1_summary.md", "q2_summary.md", "q3_summary.md", "budget_review.md", "meeting_notes.txt", "project_plan.md",
                           "risk_register.md", "status_update.txt", "sales_report.md", "team_roster.txt"],
                          ["work", "draft", "pub", "arch", "bak", "inbox"]),
                  "data": (["budget_2026.csv", "expenses_2026.csv", "headcount.csv", "invoices_2026.csv", "sales_q3.csv"],
                           ["work", "arch", "bak", "inbox"]),
                  "temp": (["cache.tmp", "scratch.tmp", "upload_queue.tmp", "export_part.tmp"], ["tmp"])}},
    "software": {
        "about": "the documentation, settings and release files of a small software project",
        "dirs": {"work": ["docs", "build"], "pub": ["releases/v2.1"], "arch": ["archive", "archive/2025"], "bak": ["backup"],
                 "tmp": ["tmp"], "log": ["logs"], "cfg": ["config"]},
        "kinds": {"doc": (["notes.txt", "changelog.md", "readme.md", "release_notes.md", "install_guide.md", "known_issues.md",
                           "upgrade_guide.md"], ["work", "pub", "arch", "bak"]),
                  "cfg": (["settings.json", "defaults.json", "features.json", "limits.json", "deploy.json"], ["cfg", "bak", "arch"]),
                  "log": (["app.log", "error.log", "build.log", "deploy.log", "access.log"], ["log", "bak", "arch"]),
                  "temp": (["cache.tmp", "build_cache.tmp", "partial.tmp"], ["tmp"])}},
    "data": {
        "about": "the data files, results and notes of a small analysis project",
        "dirs": {"work": ["data/raw", "data/clean"], "draft": ["notes"], "pub": ["results"], "arch": ["archive", "archive/2025"],
                 "bak": ["backup"], "tmp": ["tmp"], "inbox": ["incoming"]},
        "kinds": {"data": (["customers_2026.csv", "orders_2026.csv", "sales_q3.csv", "survey_2025.csv", "products.csv", "returns_2026.csv",
                            "visits_2026.csv"], ["work", "pub", "arch", "bak", "inbox"]),
                  "doc": (["summary.md", "findings.md", "method_notes.md", "readme.md", "data_dictionary.md"], ["draft", "pub", "arch", "bak"]),
                  "temp": (["cache.tmp", "scratch.tmp", "partial.tmp"], ["tmp"])}},
    "website": {
        "about": "the pages, settings and logs of a small company website",
        "dirs": {"work": ["pages", "pages/blog"], "draft": ["drafts"], "pub": ["live"], "arch": ["archive"], "bak": ["backup"],
                 "tmp": ["tmp"], "log": ["logs"], "cfg": ["config"]},
        "kinds": {"doc": (["home.md", "about.md", "pricing.md", "contact.md", "faq.md", "careers.md", "press.md"],
                          ["work", "draft", "pub", "arch", "bak"]),
                  "cfg": (["site.json", "menu.json", "redirects.json", "theme.json"], ["cfg", "bak", "arch"]),
                  "log": (["access.log", "error.log", "deploy.log"], ["log", "bak", "arch"]),
                  "temp": (["cache.tmp", "preview.tmp", "upload.tmp"], ["tmp"])}},
    "course": {
        "about": "the teaching material and grade lists of a university course",
        "dirs": {"work": ["lectures", "assignments"], "draft": ["drafts"], "pub": ["handouts"], "arch": ["archive", "archive/2025"],
                 "bak": ["backup"], "tmp": ["tmp"], "inbox": ["submissions"]},
        "kinds": {"doc": (["lecture_01.md", "lecture_02.md", "lecture_03.md", "syllabus.md", "exam_plan.md", "reading_list.md",
                           "lab_guide.md", "assignment_1.md", "assignment_2.md"], ["work", "draft", "pub", "arch", "bak", "inbox"]),
                  "data": (["grades.csv", "attendance.csv", "roster.csv"], ["work", "arch", "bak", "inbox"]),
                  "temp": (["cache.tmp", "scratch.tmp", "preview.tmp"], ["tmp"])}},
}
DOMAIN_NAMES = ["office", "software", "data", "website", "course"]
ROLE = {d: {f: r for r, fs in v["dirs"].items() for f in fs} for d, v in DOMAINS.items()}
CONTENTS = {"doc": ["draft", "review", "approved", "final", "outdated", "archived", "v1", "v2"],
            "data": ["raw", "clean", "validated", "outdated", "archived", "v1", "v2"],
            "cfg": ["default", "custom", "stable", "outdated", "archived", "v1", "v2"],
            "log": ["empty", "debug", "warnings", "errors", "outdated", "archived"],
            "temp": ["cache", "partial", "stale", "scratch"]}
FLOW = {"doc": ["draft", "review", "approved", "final"], "data": ["raw", "clean", "validated"], "cfg": ["default", "custom", "stable"]}
UPDATE = {"doc": ["review", "approved", "final", "v2"], "data": ["clean", "validated", "v2"], "cfg": ["custom", "stable", "v2"]}
FINAL = {"doc": "final", "data": "validated"}
FIRST = {"doc": "draft", "data": "raw", "cfg": "default", "log": "empty"}                 # status of a newly created file
OLDER = {"doc": ["draft", "review", "v1"], "data": ["raw", "clean", "v1"], "cfg": ["default", "v1"], "log": ["debug", "warnings", "errors"]}
HOME_ROLE = {"doc": "work", "data": "work", "cfg": "cfg", "log": "log"}


def dirs(ctx, role):
    return DOMAINS[ctx["domain"]]["dirs"].get(role, [])


def role_of(ctx, folder):
    return ROLE[ctx["domain"]].get(folder)


def kind_roles(ctx, kind):
    k = DOMAINS[ctx["domain"]]["kinds"].get(kind)
    return k[1] if k else []


def accepts(ctx, folder, kind):
    return role_of(ctx, folder) in kind_roles(ctx, kind)


def register(ctx, name, kind, topic):
    ctx["names"][name] = [kind, topic]


def kind_of(ctx, path):
    return ctx["names"][basename(path)][0]


def vname(ctx, name, qual):
    """the file name of the same family with a qualifier: q3_summary.md + _final -> q3_summary_final.md (extension kept)"""
    return f"{ctx['names'][name][1]}{qual}.{ext_of(name)}"


def variant(ctx, name, qual):
    new = vname(ctx, name, qual)
    register(ctx, new, ctx["names"][name][0], ctx["names"][name][1])
    return new


def unqualified(ctx, path):
    """the file name is the plain name of its family (q3_summary.md, not q3_summary_draft.md)"""
    nm = basename(path)
    return nm == ctx["names"][nm][1] + "." + ext_of(nm)


def home_dirs(ctx, kind):
    r = HOME_ROLE.get(kind)
    return [d for d in dirs(ctx, r) if accepts(ctx, d, kind)] if r else []


# ----------------------------------------------------------------------------------------------------------------
# the store: a dict path -> content; steps are tuples ("set", path, content), ("delete", path), ("rename", path, new_name),
# ("copy", path, destination), ("move", path, folder)
# ----------------------------------------------------------------------------------------------------------------
def step(files, op):
    """tree after one step, or None when the step does not find its file or does not change the tree"""
    k = op[0]
    new = dict(files)
    if k == "set":
        if files.get(op[1]) == op[2]:
            return None
        new[op[1]] = op[2]
    elif k == "delete":
        if op[1] not in files:
            return None
        del new[op[1]]
    elif k == "rename":
        dst = dirname(op[1]) + "/" + op[2]
        if op[1] not in files or dst == op[1]:
            return None
        new[dst] = new.pop(op[1])
    elif k == "copy":
        if op[1] not in files or op[2] == op[1] or files.get(op[2]) == files[op[1]]:
            return None
        new[op[2]] = files[op[1]]
    else:                                                        # move
        dst = op[2] + "/" + basename(op[1])
        if op[1] not in files or dst == op[1]:
            return None
        new[dst] = new.pop(op[1])
    return new


def simulate(files, ops):
    for op in ops:
        files = step(files, op)
        if files is None:
            return None
    return files


def simulate_lenient(files, ops):
    for op in ops:
        files = step(files, op) or files
    return files


def assert_run(files, ops):
    """the preamble, step by step: every delete / rename / copy / move finds its source file, a set creates the file or replaces its
    content, and every step changes the store.  Returns the final tree."""
    for i, op in enumerate(ops, 1):
        if op[0] != "set":
            assert op[1] in files, ("source file missing", i, op)
        new = step(files, op)
        assert new is not None and new != files, ("step does not change the store", i, op)
        files = new
    return files


def holds(files, c):
    t = c[0]
    if t == "exists":
        return c[1] in files
    if t == "absent":
        return c[1] not in files
    if t == "content":
        return files.get(c[1]) == c[2]
    if t == "count":
        return sum(1 for p in files if dirname(p) == c[1]) == c[2]
    return c[1] in files and c[2] in files and files[c[1]] == files[c[2]]            # same


def failing(files, goal):
    return [i for i, c in enumerate(goal) if not holds(files, c)]


def effects(op):
    """(paths written, paths read) by a step; a move or rename writes its source (gone) and its target path"""
    k = op[0]
    if k in ("set", "delete"):
        return {op[1]}, set()
    if k == "rename":
        return {op[1], dirname(op[1]) + "/" + op[2]}, {op[1]}
    if k == "copy":
        return {op[2]}, {op[1]}
    return {op[1], op[2] + "/" + basename(op[1])}, {op[1]}                      # move


def touched(ops):
    """every path that some step of the trace works on (sources and, for move / rename / copy, the resolved target paths)"""
    t = set()
    for op in ops:
        w, r = effects(op)
        t |= w | r
    return t


def untouched_conditions(ops, goal):
    """indices of the goal conditions whose file or folder no step touches (a `same` condition: neither of its two files)"""
    t = touched(ops)
    dirs = {dirname(p) for p in t}
    return [i for i, c in enumerate(goal)
            if not (c[1] in dirs if c[0] == "count" else (c[1] in t or c[2] in t) if c[0] == "same" else c[1] in t)]


def dead_steps(ops, goal):
    """number of steps outside the dependency cone of every goal condition: walking back from the goal, a step is live when it writes
    a path that is needed (a file of a condition, a file read by a live step) or a path directly inside a folder of a count condition"""
    need_p, need_d = set(), set()
    for c in goal:
        if c[0] == "count":
            need_d.add(c[1])
        elif c[0] == "same":
            need_p.update([c[1], c[2]])
        else:
            need_p.add(c[1])
    dead = 0
    for op in reversed(ops):
        w, r = effects(op)
        if any(x in need_p or dirname(x) in need_d for x in w):
            need_p = (need_p - w) | r
        else:
            dead += 1
    return dead


def overwrites(files, op):
    """True when the step replaces a *different* file than the one it works on (a collision)"""
    k = op[0]
    dst = {"rename": dirname(op[1]) + "/" + op[2] if k == "rename" else None, "copy": op[2] if k == "copy" else None,
           "move": op[2] + "/" + basename(op[1]) if k == "move" else None}.get(k)
    return dst is not None and dst != op[1] and dst in files


def plausible(op, files, ctx):
    """could a purposeful agent have run this step?  A file only goes into a folder that takes files of its kind, a rename and a
    copy stay inside the file family and keep the extension, a content word fits the kind of file."""
    k, p = op[0], op[1]
    nm = basename(p)
    if nm not in ctx["names"]:
        return False
    kd, topic = ctx["names"][nm]
    if k == "set":
        return accepts(ctx, dirname(p), kd) and op[2] in CONTENTS[kd]
    if k == "delete":
        return True
    if k == "rename":
        n = op[2]
        return n != nm and n in ctx["names"] and ctx["names"][n][1] == topic and ext_of(n) == ext_of(nm)
    if k == "copy":
        qn = basename(op[2])
        return op[2] != p and qn in ctx["names"] and ctx["names"][qn][1] == topic and ext_of(qn) == ext_of(nm) \
            and accepts(ctx, dirname(op[2]), kd)
    return accepts(ctx, op[2], kd) and op[2] != dirname(p)                      # move


# ----------------------------------------------------------------------------------------------------------------
# generating a base: start tree, macros, goal
# ----------------------------------------------------------------------------------------------------------------
def make_world(rng, level, domain):
    dom = DOMAINS[domain]
    ctx = {"domain": domain, "names": {}}
    n = rng.randint(*N_ENTRIES[level])
    base = {}
    for kd, (names, roles) in sorted(dom["kinds"].items()):
        take = {"doc": rng.randint(4, 6), "data": rng.randint(3, 4), "cfg": rng.randint(3, 4), "log": rng.randint(2, 3),
                "temp": rng.randint(2, 3)}[kd]
        base[kd] = rng.sample(names, min(take, len(names)))
        for b in base[kd]:
            register(ctx, b, kd, b.rsplit(".", 1)[0])

    def folder(kd, where):
        roles = dom["kinds"][kd][1]
        if where == "home":
            for r in ("work", "cfg", "log", "draft"):
                if r in roles and dirs(ctx, r):
                    return rng.choice(dirs(ctx, r))
            return None
        if where == "draft_or_home":
            return folder(kd, "draft") if "draft" in roles and dirs(ctx, "draft") else folder(kd, "home")
        return rng.choice(dirs(ctx, where)) if where in roles and dirs(ctx, where) else None

    def pat(kd, where, qual, contents):
        if kd not in base:
            return None
        d = folder(kd, where)
        if d is None:
            return None
        b = rng.choice(base[kd])
        nm = variant(ctx, b, qual) if qual else b
        return d + "/" + nm, rng.choice(contents)

    def backup_copy(files):
        pool = [p for p in sorted(files) if kind_of(ctx, p) in OLDER and role_of(ctx, dirname(p)) in ("work", "cfg", "log", "draft")]
        if not pool or not dirs(ctx, "bak"):
            return None
        p = rng.choice(pool)
        kd = kind_of(ctx, p)
        old = [c for c in OLDER[kd] if c != files[p]]
        return rng.choice(dirs(ctx, "bak")) + "/" + basename(p), rng.choice(old)
    pats = [(3.0, lambda f: pat("doc", "home", None, ["review", "approved", "final", "v1", "v2"])),
            (3.0, lambda f: pat("doc", "draft_or_home", "_draft", ["draft", "draft", "draft", "review", "approved", "final"])),
            (1.5, lambda f: pat("doc", "home", "_old", ["outdated"])),
            (1.5, lambda f: pat("doc", "pub", None, ["v1", "final", "approved"])),
            (1.2, lambda f: pat("doc", "arch", None, ["archived"])),
            (1.0, lambda f: pat("doc", "inbox", None, ["draft", "review"])),
            (3.0, lambda f: pat("data", "home", None, ["raw", "clean", "validated", "v1", "v2"])),
            (1.2, lambda f: pat("data", "inbox", None, ["raw"])),
            (1.0, lambda f: pat("data", "arch", None, ["archived"])),
            (1.2, lambda f: pat("data", "pub", None, ["validated", "v1"])),
            (3.0, lambda f: pat("cfg", "home", None, ["default", "custom", "stable", "v1", "v2"])),
            (2.5, lambda f: pat("log", "home", None, ["debug", "warnings", "errors", "empty"])),
            (0.8, lambda f: pat("log", "arch", "_old", ["archived"])),
            (2.2, lambda f: pat("temp", "tmp", None, CONTENTS["temp"])),
            (1.8, backup_copy)]
    for _ in range(300):
        files = {}
        for _try in range(400):
            if len(files) >= n:
                break
            got = rng.choices(pats, weights=[w for w, _f in pats])[0][1](files)
            if got and got[0] not in files:
                files[got[0]] = got[1]
        if len(files) == n and len({dirname(p) for p in files}) >= 3:
            return dict(sorted(files.items())), ctx
    return None


# --- macros: purposeful sequences of one to three steps; each returns (ops, tag, intended goal conditions) or None ----------
def live_pool(files, ctx, kinds, roles, pred=None):
    return [p for p in sorted(files) if kind_of(ctx, p) in kinds and role_of(ctx, dirname(p)) in roles and (pred is None or pred(p))]


def m_archive(rng, files, ctx, room):
    """archive an old or finished file: move it into the archive (sometimes after marking it archived, or as copy + delete)"""
    arch = dirs(ctx, "arch")
    pool = live_pool(files, ctx, ("doc", "data", "log", "cfg"), ("work", "draft", "pub", "log", "cfg", "inbox"),
                     lambda q: q not in ctx.get("fresh", []))               # a file created a moment ago is not archived at once
    if not arch or not pool:
        return None
    p = rng.choices(pool, weights=[3.0 if files[q] in ("outdated", "v1") or "_old" in q else 1.0 for q in pool])[0]
    d, nm, r = rng.choice(arch), basename(p), rng.random()
    if room >= 2 and r < 0.35 and files[p] != "archived":
        ops, ints = [("set", p, "archived"), ("move", p, d)], [("content", d + "/" + nm, "archived")]
    elif room >= 2 and r < 0.55:
        ops, ints = [("copy", p, d + "/" + nm), ("delete", p)], []
    else:
        ops, ints = [("move", p, d)], []
    return ops, "archive", ints + [("exists", d + "/" + nm), ("absent", p)]


def m_publish(rng, files, ctx, room):
    """publish a final version: mark it final and copy it to the publication folder, or move (rename and move) a finished file there"""
    pubs = dirs(ctx, "pub")
    pool = live_pool(files, ctx, ("doc", "data"), ("work", "draft"),
                     lambda q: files[q] not in ("outdated", "archived") and pubs and accepts(ctx, pubs[0], kind_of(ctx, q)))
    if not pubs or not pool:
        return None
    p = rng.choice(pool)
    kd, nm, d = kind_of(ctx, p), basename(p), rng.choice(pubs)
    fin, c = FINAL[kd], files[p]
    opts = []
    if c != fin and room >= 2:
        opts.append("set_copy")
    if c == fin:
        opts += ["copy", "move"]
    if kd == "doc" and "_draft" in nm and room >= 2 + (c != fin):
        opts.append("rename_move")
    if not opts:
        return None
    o = rng.choice(opts)
    if o == "set_copy":
        return [("set", p, fin), ("copy", p, d + "/" + nm)], "publish", [("exists", d + "/" + nm), ("content", d + "/" + nm, fin),
                                                                       ("same", p, d + "/" + nm)]
    if o == "copy":
        return [("copy", p, d + "/" + nm)], "publish", [("exists", d + "/" + nm), ("same", p, d + "/" + nm)]
    if o == "move":
        return [("move", p, d)], "publish", [("exists", d + "/" + nm), ("absent", p)]
    new = variant(ctx, nm, "_final")
    np_ = dirname(p) + "/" + new
    ops = [("rename", p, new)] + ([("set", np_, fin)] if c != fin else []) + [("move", np_, d)]
    return ops, "publish", [("exists", d + "/" + new), ("absent", p), ("absent", np_)]


def m_finalize(rng, files, ctx, room):
    """rename a draft to final (q3_summary_draft.md -> q3_summary_final.md) and mark it final"""
    pool = live_pool(files, ctx, ("doc",), ("work", "draft", "inbox"), lambda q: "_draft" in basename(q) and files[q] not in ("outdated", "archived")
                     and (room >= 2 or files[q] == "final"))
    if not pool:
        return None
    p = rng.choice(pool)
    new = variant(ctx, basename(p), "_final")
    np_ = dirname(p) + "/" + new
    ops = [("rename", p, new)] + ([("set", np_, "final")] if files[p] != "final" else [])
    return ops, "finalize", [("exists", np_), ("absent", p), ("content", np_, "final")]


def m_cleanup(rng, files, ctx, room):
    """clean up temporary files: delete one to three of them"""
    pool = live_pool(files, ctx, ("temp",), ("tmp",))
    if not pool:
        return None
    k = min(len(pool), room, rng.choice([1, 2, 2, 3]))
    chosen = rng.sample(pool, k)
    return [("delete", p) for p in chosen], "cleanup", [("absent", p) for p in chosen] + [("count", dirname(chosen[0]), None)]


def m_obsolete(rng, files, ctx, room):
    """remove a file whose content says it is outdated"""
    pool = [p for p in sorted(files) if files[p] == "outdated" and kind_of(ctx, p) != "temp"
            and role_of(ctx, dirname(p)) in ("work", "draft", "inbox", "pub", "cfg", "log")]
    if not pool:
        return None
    p = rng.choice(pool)
    return [("delete", p)], "obsolete", [("absent", p), ("count", dirname(p), None)]


def m_backup(rng, files, ctx, room):
    """back up before overwriting: copy the file to the backup folder, then write the new version"""
    baks = dirs(ctx, "bak")
    pool = live_pool(files, ctx, ("doc", "data", "cfg"), ("work", "draft", "cfg"), lambda q: files[q] not in ("outdated", "archived"))
    if not baks or not pool or room < 2:
        return None
    p = rng.choice(pool)
    kd, nm, c = kind_of(ctx, p), basename(p), files[p]
    b = rng.choice(baks) + "/" + nm
    fl = FLOW[kd]
    ups = [x for x in UPDATE[kd] if x != c and not (x in fl and c in fl and fl.index(x) < fl.index(c))]       # never backwards along the flow
    nc = rng.choice(ups)
    return [("copy", p, b), ("set", p, nc)], "backup", [("content", b, c), ("content", p, nc), ("exists", b)]


def m_restore(rng, files, ctx, room):
    """restore a file from the backup folder"""
    pool = live_pool(files, ctx, ("doc", "data", "cfg", "log"), ("bak",))
    if not pool:
        return None
    q = rng.choice(pool)
    kd, nm = kind_of(ctx, q), basename(q)
    homes = home_dirs(ctx, kd)
    if not homes:
        return None
    same_name = [h for h in homes if h + "/" + nm in files]
    h = rng.choice(same_name) if same_name and rng.random() < 0.8 else rng.choice(homes)
    return [("copy", q, h + "/" + nm)], "restore", [("same", q, h + "/" + nm), ("exists", h + "/" + nm)]


def m_rotate(rng, files, ctx, room):
    """rotate a log: rename it to name_old.log and start an empty one"""
    pool = live_pool(files, ctx, ("log",), ("log",), lambda q: files[q] != "empty" and unqualified(ctx, q))
    if not pool or room < 2:
        return None
    p = rng.choice(pool)
    old = variant(ctx, basename(p), "_old")
    d = dirname(p)
    return [("rename", p, old), ("set", p, "empty")], "rotate", [("exists", d + "/" + old), ("content", p, "empty"),
                                                                 ("content", d + "/" + old, files[p])]


def m_version(rng, files, ctx, room):
    """make a new version: copy the file to name_v2.ext and mark the copy"""
    pool = live_pool(files, ctx, ("doc", "data", "cfg"), ("work", "cfg"), lambda q: files[q] not in ("outdated", "archived")
                     and unqualified(ctx, q))
    if not pool:
        return None
    p = rng.choice(pool)
    kd = kind_of(ctx, p)
    new = variant(ctx, basename(p), "_v2")
    d = dirname(p)
    ops, ints = [("copy", p, d + "/" + new)], [("exists", d + "/" + new)]
    if room >= 2 and rng.random() < 0.75:
        nc = FIRST["doc"] if kd == "doc" else "v2"
        ops.append(("set", d + "/" + new, nc))
        ints.append(("content", d + "/" + new, nc))
    return ops, "version", ints


def m_status(rng, files, ctx, room):
    """advance the status of a file along its flow (draft - review - approved - final, raw - clean - validated, ...)"""
    pool = [p for p in sorted(files) if kind_of(ctx, p) in FLOW and role_of(ctx, dirname(p)) in ("work", "draft", "cfg", "inbox")
            and files[p] in FLOW[kind_of(ctx, p)][:-1]]
    if not pool:
        return None
    p = rng.choice(pool)
    fl = FLOW[kind_of(ctx, p)]
    later = fl[fl.index(files[p]) + 1:]
    nc = later[0] if rng.random() < 0.6 else rng.choice(later)
    return [("set", p, nc)], "status", [("content", p, nc)]


def m_newfile(rng, files, ctx, room):
    """create a new file with its first status (a draft, a data file, a log, a setting)"""
    dom = DOMAINS[ctx["domain"]]
    kd = rng.choice(sorted(k for k in dom["kinds"] if k in FIRST))
    names, roles = dom["kinds"][kd]
    present = {basename(p) for p in files}
    free = [b for b in names if b not in present]
    wanted = {"doc": ["draft", "work"], "data": ["inbox", "work"], "cfg": ["cfg"], "log": ["log"]}[kd]
    rs = [r for r in wanted if r in roles and dirs(ctx, r)]
    if not free or not rs:
        return None
    b = rng.choice(free)
    register(ctx, b, kd, b.rsplit(".", 1)[0])
    nm = variant(ctx, b, "_draft") if kd == "doc" and rng.random() < 0.4 else b
    p = rng.choice(dirs(ctx, rng.choice(rs) if kd == "data" else rs[0])) + "/" + nm
    if p in files:                                                      # a new file, not an overwrite
        return None
    return [("set", p, FIRST[kd])], "newfile", [("exists", p), ("content", p, FIRST[kd])]


def m_consolidate(rng, files, ctx, room):
    """move an incoming file to the folder where files of its kind are kept"""
    pool = live_pool(files, ctx, ("doc", "data"), ("inbox",))
    if not pool:
        return None
    p = rng.choice(pool)
    homes = home_dirs(ctx, kind_of(ctx, p))
    if not homes:
        return None
    d = rng.choice(homes)
    return [("move", p, d)], "consolidate", [("exists", d + "/" + basename(p)), ("absent", p)]


MACROS = {"archive": m_archive, "publish": m_publish, "finalize": m_finalize, "cleanup": m_cleanup, "obsolete": m_obsolete,
          "backup": m_backup, "restore": m_restore, "rotate": m_rotate, "version": m_version, "status": m_status,
          "newfile": m_newfile, "consolidate": m_consolidate}
MACRO_NAMES = list(MACROS)
MACRO_WEIGHTS = [3.0, 3.0, 2.2, 2.2, 1.2, 2.2, 1.5, 1.2, 1.2, 2.0, 1.6, 1.2]
MACRO_TEXT = {"archive": "archive an old or finished file that was there at the start: move it into the archive folder (sometimes after setting its content to `archived`, or as copy + delete)",
              "publish": "publish a final version: set the content to `final` (or `validated` for data) and copy the file to the publication folder, copy or move a file that is already final, or rename a draft to final and move it there",
              "finalize": "rename `name_draft.ext` to `name_final.ext` and set the content to `final`",
              "cleanup": "clean up temporary files: delete one to three `.tmp` files",
              "obsolete": "remove a file whose content says `outdated`",
              "backup": "back up before overwriting: copy the file to the backup folder, then write a newer content to the original",
              "restore": "copy a file back from the backup folder to the folder where it is kept (replacing the file there)",
              "rotate": "rotate a log: rename `x.log` to `x_old.log`, then create an empty `x.log`",
              "version": "make a new version: copy the file to `name_v2.ext` and mark the copy (`draft` for documents, `v2` otherwise)",
              "status": "advance the status of a file along draft - review - approved - final (raw - clean - validated, default - custom - stable)",
              "newfile": "create a new file with its first status (a draft, a raw data file, a default setting, an empty log)",
              "consolidate": "move an incoming file to the folder where files of its kind are kept"}


# --- macro coherence: can the trace be cut into macros?  (the planted deviation must keep it so) ---------------------------
ARCH_SRC = ("work", "draft", "pub", "log", "cfg", "inbox")


def macro_lengths(f, ops, i, ctx):
    """lengths of the macro instances that start at step i when the tree is f (the preconditions of the macros above)"""
    o = ops[i]
    k, p = o[0], o[1]
    nm = basename(p)
    out = set()
    if nm not in ctx["names"]:
        return out
    o2 = ops[i + 1] if i + 1 < len(ops) else None
    o3 = ops[i + 2] if i + 2 < len(ops) else None
    kd, topic = ctx["names"][nm]
    role, c, exists = role_of(ctx, dirname(p)), f.get(p), p in f
    pubs, arch, baks = dirs(ctx, "pub"), dirs(ctx, "arch"), dirs(ctx, "bak")
    pubable = kd in ("doc", "data") and role in ("work", "draft") and c not in ("outdated", "archived") and exists
    fin = FINAL.get(kd)
    if k == "move" and exists:
        d = o[2]
        if kd in ("doc", "data", "log", "cfg") and role in ARCH_SRC and d in arch:
            out.add(1)                                                                  # archive
        if pubable and c == fin and d in pubs and accepts(ctx, d, kd):
            out.add(1)                                                                  # publish
        if kd in ("doc", "data") and role == "inbox" and d in home_dirs(ctx, kd):
            out.add(1)                                                                  # consolidate
    elif k == "set":
        nc = o[2]
        if exists:
            fl = FLOW.get(kd)
            if fl and role in ("work", "draft", "cfg", "inbox") and c in fl[:-1] and nc in fl[fl.index(c) + 1:]:
                out.add(1)                                                              # status
            if nc == "archived" and c != "archived" and kd in ("doc", "data", "log", "cfg") and role in ARCH_SRC \
                    and o2 and o2[0] == "move" and o2[1] == p and o2[2] in arch:
                out.add(2)                                                              # archive, marked first
            if pubable and nc == fin and c != fin and o2 and o2[0] == "copy" and o2[1] == p and dirname(o2[2]) in pubs \
                    and basename(o2[2]) == nm and accepts(ctx, dirname(o2[2]), kd):
                out.add(2)                                                              # publish, marked first
        elif nc == FIRST.get(kd) and kd in FIRST:
            base = topic + "." + ext_of(nm)
            names, roles = DOMAINS[ctx["domain"]]["kinds"][kd]
            wanted = {"doc": ["draft", "work"], "data": ["inbox", "work"], "cfg": ["cfg"], "log": ["log"]}[kd]
            rs = [r for r in wanted if r in roles and dirs(ctx, r)]
            ok_role = role in rs if kd == "data" else bool(rs) and role == rs[0]
            if base in names and base not in {basename(q) for q in f} and ok_role and (nm == base or (kd == "doc" and nm == vname(ctx, base, "_draft"))):
                out.add(1)                                                              # newfile
    elif k == "rename" and exists:
        n_ = o[2]
        np_ = dirname(p) + "/" + n_
        if kd == "doc" and "_draft" in nm and role in ("work", "draft", "inbox") and c not in ("outdated", "archived") \
                and n_ == vname(ctx, nm, "_final"):
            if c == "final":
                out.add(1)                                                              # finalize
            elif o2 and o2[0] == "set" and o2[1] == np_ and o2[2] == "final":
                out.add(2)
            if role in ("work", "draft") and pubs and accepts(ctx, pubs[0], "doc"):
                if c == "final" and o2 and o2[0] == "move" and o2[1] == np_ and o2[2] in pubs:
                    out.add(2)                                                          # publish after the rename
                if c != "final" and o2 and o3 and o2[0] == "set" and o2[1] == np_ and o2[2] == "final" and o3[0] == "move" \
                        and o3[1] == np_ and o3[2] in pubs:
                    out.add(3)
        if kd == "log" and role == "log" and c != "empty" and unqualified(ctx, p) and n_ == vname(ctx, nm, "_old") \
                and o2 and o2[0] == "set" and o2[1] == p and o2[2] == "empty":
            out.add(2)                                                                  # rotate
    elif k == "copy" and exists:
        q = o[2]
        qd, qn = dirname(q), basename(q)
        if kd in ("doc", "data", "log", "cfg") and role in ARCH_SRC and qd in arch and qn == nm and o2 and o2[0] == "delete" and o2[1] == p:
            out.add(2)                                                                  # archive as copy + delete
        if pubable and c == fin and qd in pubs and qn == nm and accepts(ctx, qd, kd):
            out.add(1)                                                                  # publish
        if kd in ("doc", "data", "cfg") and role in ("work", "draft", "cfg") and c not in ("outdated", "archived") and qd in baks \
                and qn == nm and o2 and o2[0] == "set" and o2[1] == p and o2[2] in UPDATE[kd] and o2[2] != c:
            fl = FLOW[kd]
            if not (o2[2] in fl and c in fl and fl.index(o2[2]) < fl.index(c)):
                out.add(2)                                                              # back up before overwriting
        if role == "bak" and kd in ("doc", "data", "cfg", "log") and qd in home_dirs(ctx, kd) and qn == nm:
            out.add(1)                                                                  # restore
        if kd in ("doc", "data", "cfg") and role in ("work", "cfg") and unqualified(ctx, p) and c not in ("outdated", "archived") \
                and q == dirname(p) + "/" + vname(ctx, nm, "_v2"):
            out.add(1)                                                                  # new version
            if o2 and o2[0] == "set" and o2[1] == q and o2[2] == (FIRST["doc"] if kd == "doc" else "v2"):
                out.add(2)
    elif k == "delete" and exists:
        if kd == "temp" and role == "tmp":
            out.add(1)                                                                  # clean up
        if c == "outdated" and kd != "temp" and role in ("work", "draft", "inbox", "pub", "cfg", "log"):
            out.add(1)                                                                  # remove an obsolete file
    return out


def coherent(ops, files0, ctx):
    """True when every step of the trace belongs to a macro and the trace can be cut into whole macros (a trace of the generator
    always can; so can the twin of a pair: the planted deviation is a wrong choice inside the macros, not a broken macro)"""
    states = [files0]
    for op in ops:
        nxt = step(states[-1], op)
        if nxt is None:
            return False
        states.append(nxt)
    reach = [True] + [False] * len(ops)
    for i in range(len(ops)):
        if reach[i]:
            for ln in macro_lengths(states[i], ops, i, ctx):
                reach[i + ln] = True
    return reach[len(ops)]


def walk(rng, files0, ctx, n_steps):
    """a trace of exactly n_steps steps made of macros; returns (ops, macro tag of each step, intended conditions)"""
    files, ops, tags, intents = files0, [], [], []
    ctx["fresh"] = []                                                       # paths created by this trace (set, copy, move; not rename)
    seen = set()                                                            # no macro instance is run twice
    while len(ops) < n_steps:
        room = n_steps - len(ops)
        for _try in range(80):
            name = rng.choices(MACRO_NAMES, weights=MACRO_WEIGHTS)[0]
            got = MACROS[name](rng, files, ctx, room)
            if got is None or len(got[0]) > room:
                continue
            m_ops, tag, ints = got
            if tuple(m_ops) in seen:
                continue
            cur, ok, collide, made = files, True, False, []
            for op in m_ops:
                assert plausible(op, cur, ctx), (tag, op)
                collide = collide or overwrites(cur, op)
                nxt = step(cur, op)
                if nxt is not None and op[0] != "rename":                      # a path that did not exist before: fresh
                    made += sorted(set(nxt) - set(cur))
                cur = nxt
                if cur is None:
                    ok = False
                    break
            if not ok or (collide and rng.random() > 0.3):
                continue
            break
        else:
            return None
        ops += m_ops
        tags += [tag] * len(m_ops)
        intents += ints
        ctx["fresh"] = sorted(set(ctx["fresh"]) | set(made))
        seen.add(tuple(m_ops))
        files = cur
    assert coherent(ops, files0, ctx), ops
    return ops, tags, intents


def pick_goal(rng, files0, ops, n, intents):
    final = simulate(files0, ops)
    ever = set(files0)
    f = files0
    for op in ops:
        f = step(f, op)
        ever |= set(f)
    cands = []
    for p in sorted(ever):
        cands += [("exists", p), ("content", p, final[p])] if p in final else [("absent", p)]
    for d in sorted({dirname(p) for p in ever}):
        cands.append(("count", d, sum(1 for q in final if dirname(q) == d)))
    cands += [("same", op[1], op[2]) for op in ops if op[0] == "copy" and op[1] in final and op[2] in final and final[op[1]] == final[op[2]]]
    by_name = collections.defaultdict(list)
    for p in sorted(final):
        by_name[basename(p)].append(p)
    for nm in sorted(by_name):
        ps = by_name[nm]
        cands += [("same", ps[a], ps[b]) for a in range(len(ps)) for b in range(a + 1, len(ps)) if final[ps[a]] == final[ps[b]]]
    cands = sorted(set(cands))
    wanted = {("count", i[1], sum(1 for q in final if dirname(q) == i[1])) if i[0] == "count" else tuple(i) for i in intents}
    ablated = [simulate_lenient(files0, ops[:i] + ops[i + 1:]) for i in range(len(ops))]
    sens = {c: frozenset(i for i, a in enumerate(ablated) if not holds(a, c)) for c in cands}
    cands = [c for c in cands if sens[c] and not untouched_conditions(ops, [c])]

    def key(c):
        return ("dir:" + c[1]) if c[0] == "count" else ("same:" + c[1] + c[2] if c[0] == "same" else c[1])
    chosen, covered = [], set()
    while len(chosen) < n:
        pool = [c for c in cands if key(c) not in {key(x) for x in chosen}]
        if not pool:
            return None
        best = max(pool, key=lambda c: len(sens[c] - covered) + rng.random() * 0.9 + (0.6 if c[0] not in {x[0] for x in chosen} else 0)
                   + (0.6 if c in wanted else 0) + (0.45 if c[0] == "count" else 0))
        chosen.append(best)
        covered |= sens[best]
    rng.shuffle(chosen)
    return chosen


# ----------------------------------------------------------------------------------------------------------------
# the planted deviation: one operation of the trace is changed
# ----------------------------------------------------------------------------------------------------------------
def item_tokens(files0, ops, goal):
    """alphanumeric words of every path, name, folder and content of the item (the content-bearing part of the state text)"""
    parts = list(files0) + list(files0.values())
    for op in ops:
        parts += list(op[1:])
    for c in goal:
        parts += [x for x in c[1:] if isinstance(x, str)]
    return set(re.findall(r"[A-Za-z0-9]+", " ".join(parts)))


def goal_only_tokens(files0, ops, goal):
    """words that the goal mentions and neither the start list nor the trace does (a name that no step could have produced)"""
    return item_tokens({}, [], goal) - item_tokens(files0, ops, [])


def occurring(files0, ops, goal):
    """folders, file names and content words that occur in the item; mutations and inserted steps use only these"""
    paths = set(files0) | {op[1] for op in ops} | {op[2] for op in ops if op[0] == "copy"} | {c[1] for c in goal if c[0] != "count"} \
        | {c[2] for c in goal if c[0] == "same"}
    folders = {dirname(p) for p in paths} | {op[2] for op in ops if op[0] == "move"} | {c[1] for c in goal if c[0] == "count"}
    names = {basename(p) for p in paths} | {op[2] for op in ops if op[0] == "rename"}
    contents = set(files0.values()) | {op[2] for op in ops if op[0] == "set"} | {c[2] for c in goal if c[0] == "content"}
    return {"paths": sorted(paths), "folders": sorted(folders), "names": sorted(names), "contents": sorted(contents)}


def alternatives(op, slot, state, uni):
    k = op[0]
    cur = op[slot]
    if slot == 1 and k in ("delete", "rename", "copy", "move"):
        return [p for p in sorted(state) if p != cur]
    if slot == 1:                                                           # set: any other path of the item
        return [p for p in uni["paths"] if p != cur]
    if k == "rename":
        return [n for n in uni["names"] if n != cur]
    if k == "move":
        return [f for f in uni["folders"] if f != cur]
    p = op[1]                                                               # copy destination
    out = {q for q in uni["paths"]} | {dirname(cur) + "/" + n for n in uni["names"]} | {f + "/" + basename(cur) for f in uni["folders"]}
    return sorted(q for q in out if q != cur and q != p)


def single_ops(rng, state, ctx, tokens, avoid):
    """a plausible single step of one macro on this state that uses only words of the item and is not a step of the trace
    already -> (op, tag) or None"""
    for _ in range(60):
        got = MACROS[rng.choices(MACRO_NAMES, weights=MACRO_WEIGHTS)[0]](rng, state, ctx, 1)
        if not got or len(got[0]) != 1:
            continue
        op = got[0][0]
        if op in avoid or overwrites(state, op) or step(state, op) is None or not plausible(op, state, ctx):
            continue
        if not set(re.findall(r"[A-Za-z0-9]+", " ".join(op[1:]))) <= tokens:
            continue
        return op, got[1]
    return None


def mutate(rng, files0, ctx, ops, tags, goal, kind):
    """-> (ops', tags', detail) with exactly one failing condition, every step running, every step plausible and the same words in
    the state, or None"""
    n = len(ops)
    states = [files0]
    for op in ops:
        states.append(step(states[-1], op))
    uni = occurring(files0, ops, goal)
    base_tokens = item_tokens(files0, ops, goal)
    base_dead = dead_steps(ops, goal)

    def verdict(new_ops):
        sim = simulate(files0, new_ops)
        if sim is None or item_tokens(files0, new_ops, goal) != base_tokens or goal_only_tokens(files0, new_ops, goal):
            return None
        f = failing(sim, goal)
        if len(f) != 1 or untouched_conditions(new_ops, goal) or dead_steps(new_ops, goal) != base_dead:
            return None                     # one failing condition, every target touched by a step, as many dead steps as the base
        return f if coherent(new_ops, files0, ctx) else None

    cands = []
    if kind == "wrong_target":
        for i, op in enumerate(ops):
            for slot in range(1, len(op)):
                if op[0] == "set" and slot == 2:
                    continue
                for alt in alternatives(op, slot, states[i], uni):
                    cands.append((i, slot, alt))
        rng.shuffle(cands)
        tried = 0
        for i, slot, alt in cands:
            new_op = tuple(alt if j == slot else v for j, v in enumerate(ops[i]))
            if slot == 1 and kind_of(ctx, alt) != kind_of(ctx, ops[i][1]):
                continue
            if not plausible(new_op, states[i], ctx):
                continue
            tried += 1
            if tried > 400:
                break
            new = list(ops)
            new[i] = new_op
            f = verdict(new)
            if f is not None:
                return new, list(tags), {"kind": kind, "step": i + 1, "slot": slot, "failed": f[0]}
    elif kind == "wrong_content":
        for i, op in enumerate(ops):
            if op[0] == "set":
                cands += [(i, c) for c in uni["contents"] if c != op[2]]
        rng.shuffle(cands)
        for i, c in cands:
            new_op = ("set", ops[i][1], c)
            if not plausible(new_op, states[i], ctx):
                continue
            new = list(ops)
            new[i] = new_op
            f = verdict(new)
            if f is not None:
                return new, list(tags), {"kind": kind, "step": i + 1, "slot": 2, "failed": f[0]}
    elif kind == "steps_swapped":
        cands = [(i, j) for i in range(n) for j in range(i + 1, min(n, i + 5))]
        rng.shuffle(cands)
        for i, j in cands:
            new, nt = list(ops), list(tags)
            new[i], new[j] = ops[j], ops[i]
            nt[i], nt[j] = tags[j], tags[i]
            f = verdict(new)
            if f is not None:
                return new, nt, {"kind": kind, "step": i + 1, "step2": j + 1, "failed": f[0]}
    else:                                                                   # step_missing + an unrelated single step elsewhere
        order = list(range(n))
        rng.shuffle(order)
        for i in order:
            rest = ops[:i] + ops[i + 1:]
            sim = simulate(files0, rest)
            if sim is None or len(failing(sim, goal)) != 1 or untouched_conditions(rest, goal):
                continue                    # the left-out step must not be the only one that touches the failing condition's target
            f0 = failing(sim, goal)
            for _ in range(40):
                pos = rng.randrange(len(rest) + 1)
                state = simulate(files0, rest[:pos])
                if state is None:
                    continue
                got = single_ops(rng, state, ctx, base_tokens, set(ops))
                if got is None or untouched_conditions([got[0]], [goal[f0[0]]]) == []:
                    continue                # the inserted step is unrelated: it does not touch the failing condition's target
                new = rest[:pos] + [got[0]] + rest[pos:]
                if new != ops and verdict(new) == f0:
                    nt = tags[:i] + tags[i + 1:]
                    return new, nt[:pos] + [got[1]] + nt[pos:], {"kind": kind, "removed": i + 1, "inserted": pos + 1, "failed": f0[0]}
    return None


# ----------------------------------------------------------------------------------------------------------------
# rendering: four layouts of the file list, four wordings of the goal, four notations of the trace, four numberings
# ----------------------------------------------------------------------------------------------------------------
INTRO = ["An agent changed a small file store by running the steps of the trace below.",
         "The trace below lists the steps that an agent ran on a small file store.",
         "A small file store was edited step by step by an agent; the trace shows every step.",
         "Below are the starting files of a small file store, the goal an agent was given, and the steps it ran."]
RAN = ["Every delete, rename, copy and move found its source file; set creates the file or replaces its content; every step changed the store.",
       "Each delete, rename, copy and move was run on a file that existed at that moment, a set either creates its file or overwrites its content, and no step left the store as it was.",
       "No step failed: deletes, renames, copies and moves always found their source file, sets create or overwrite their file, and every step made the store different from before.",
       "All steps ran. The source file of every delete, rename, copy and move was in the store when the step started, a set writes its file whether or not it exists yet, and each step changed the store."]
H_START = ["Files at the start, with their content:", "Store before the first step (one file per line, with its content):",
           "Initial content of the store:", "At the start the store holds these files and contents:"]
H_SEM = ["What the steps do:", "Meaning of the steps (arguments in the order given in the trace):", "Step semantics:",
         "How each kind of step works:"]
H_GOAL = ["Goal (all conditions must hold after the last step; a folder's file count includes only the files directly inside it):",
          "The agent was asked to reach these conditions, and every one of them must hold after the last step (file counts refer to the files directly inside a folder, not those in sub-folders):",
          "Goal conditions, to be true after the final step; a count only includes files directly in the named folder:",
          "After the last step the store has to satisfy every one of these conditions; file counts ignore sub-folders:"]
H_TRACE = ["Trace:", "Steps run by the agent, in order:", "Operations, first to last:", "Log of the agent's steps:"]
SEM = {"set": ["set: writes the content to the path; the file is created if it is missing and its content is replaced if it exists.",
               "set: stores the given content under the path, creating the file or replacing the content of the existing one.",
               "set: the file at the path gets the given content (a new file if there was none, otherwise the old content is overwritten).",
               "set: puts the content into the file at the path, whether or not the file exists yet; an existing file loses its old content."],
       "delete": ["delete: removes the file at the path.", "delete: the file at the path is gone afterwards.",
                  "delete: erases the file at the path from the store.", "delete: takes the file at the path out of the store."],
       "rename": ["rename: gives the file a new name inside its folder; if a file with that name is already there it is replaced.",
                  "rename: changes the file's name but not its folder; a file already holding the new name is overwritten.",
                  "rename: the file keeps its folder and content and takes the new name; an existing file of that name is lost.",
                  "rename: new name, same folder; when the new name is taken, the other file is replaced."],
       "copy": ["copy: writes the content of the source file to the destination path; a file already at the destination is replaced and the source stays.",
                "copy: the destination path receives the source's content (replacing any file there); the source is not changed.",
                "copy: duplicates the source file to the destination, overwriting a file that is there; the source remains.",
                "copy: creates or overwrites the destination with the content of the source, which stays in place."],
       "move": ["move: puts the file into the target folder under the same name; a file of that name in the folder is replaced, and the old path is gone.",
                "move: relocates the file to the folder, keeping its file name; an existing file with that name in the folder is overwritten.",
                "move: the file leaves its folder for the target folder and keeps its name; whatever file had that path there is lost.",
                "move: transfers the file into the target folder with the same name, replacing a file of that name if present; nothing is left at the old path."]}
LISTING = ["{p} = {c}", "{p}: {c}", "{p} ({c})", '"{p}": "{c}"']
GOAL = [{"exists": "{p} exists", "absent": "{p} does not exist", "content": "{p} contains {c}",
         "count": "folder {d} holds {n} file{s}", "same": "{p} and {q} have the same content"},
        {"exists": "the file {p} is present", "absent": "the file {p} is absent", "content": "the content of {p} is {c}",
         "count": "{d} contains exactly {n} file{s}", "same": "{p} has the same content as {q}"},
        {"exists": "there is a file {p}", "absent": "there is no file {p}", "content": "{p} holds {c}",
         "count": "there {be} {n} file{s} in {d}", "same": "{p} and {q} are identical in content"},
        {"exists": "{p} is in the tree", "absent": "{p} is not in the tree", "content": "{p} reads {c}",
         "count": "the folder {d} has {n} file{s}", "same": "the contents of {p} and {q} match"}]
NUMBERING = ["{i}. ", "step {i}: ", "[{i}] ", "#{i} "]
NOTATION = [{"set": 'set("{p}", "{c}")', "delete": 'delete("{p}")', "rename": 'rename("{p}", "{n}")',
             "copy": 'copy("{p}", "{q}")', "move": 'move("{p}", "{f}")'},
            {"set": "set {p} {c}", "delete": "delete {p}", "rename": "rename {p} {n}", "copy": "copy {p} {q}", "move": "move {p} {f}"},
            {"set": "Set {p} to {c}.", "delete": "Delete {p}.", "rename": "Rename {p} to {n}.", "copy": "Copy {p} to {q}.",
             "move": "Move {p} into {f}."},
            {"set": '{{"op": "set", "path": "{p}", "content": "{c}"}}', "delete": '{{"op": "delete", "path": "{p}"}}',
             "rename": '{{"op": "rename", "path": "{p}", "new_name": "{n}"}}',
             "copy": '{{"op": "copy", "source": "{p}", "destination": "{q}"}}',
             "move": '{{"op": "move", "path": "{p}", "folder": "{f}"}}'}]
PATH, WORD = r"[A-Za-z0-9_./\-]+", r"[a-z][a-z0-9]*"


def tmpl_regex(tmpl):
    """regular expression of a template with {p} {q} {c} {d} {n} {f} {s} {be} placeholders"""
    out = []
    for part in re.split(r"(\{[a-z]+\})", tmpl.replace("{{", "\x00").replace("}}", "\x01")):
        g = {"{p}": PATH, "{q}": PATH, "{c}": WORD, "{d}": PATH, "{f}": PATH, "{n}": PATH}
        if part in ("{p}", "{c}", "{d}", "{f}", "{n}", "{q}"):
            out.append("(?P<%s>%s)" % (part[1], g[part]))
        elif part == "{s}":
            out.append("s?")
        elif part == "{be}":
            out.append("(?:is|are)")
        else:
            out.append(re.escape(part).replace("\x00", r"\{").replace("\x01", r"\}"))
    return re.compile("^" + "".join(out) + "$")


def render_op(op, style):
    k = op[0]
    slots = {"set": dict(p=op[1], c=op[2] if k == "set" else ""), "delete": dict(p=op[1]),
             "rename": dict(p=op[1], n=op[2] if k == "rename" else ""), "copy": dict(p=op[1], q=op[2] if k == "copy" else ""),
             "move": dict(p=op[1], f=op[2] if k == "move" else "")}[k]
    return NOTATION[style][k].format(**slots)


def render_cond(c, style):
    t = c[0]
    n = c[2] if t == "count" else 0
    return GOAL[style][t].format(p=c[1], q=c[2] if t == "same" else "", c=c[2] if t == "content" else "", d=c[1], n=n,
                                 s="" if n == 1 else "s", be="is" if n == 1 else "are")


def render_state(spec):
    st = spec["style"]
    about = DOMAINS[spec["domain"]]["about"]
    lines = [INTRO[st["intro"]] + f" The store holds {about}. " + RAN[st["ran"]], "", H_START[st["h_start"]]]
    lines += ["  " + LISTING[st["listing"]].format(p=p, c=c) for p, c in sorted(spec["files0"].items())]
    lines += ["", H_SEM[st["h_sem"]]] + ["  " + SEM[k][st["sem"][k]] for k in ("set", "delete", "rename", "copy", "move")]
    lines += ["", H_GOAL[st["h_goal"]]] + [f"  G{i}. " + render_cond(c, st["goal"]) for i, c in enumerate(spec["goal"], 1)]
    lines += ["", H_TRACE[st["h_trace"]]]
    lines += ["  " + NUMBERING[st["numbering"]].format(i=i) + render_op(op, st["notation"]) for i, op in enumerate(spec["ops"], 1)]
    return "\n".join(lines)


# ----------------------------------------------------------------------------------------------------------------
# truth and check
# ----------------------------------------------------------------------------------------------------------------
def truth(spec):
    ops = [tuple(o) for o in spec["ops"]]
    goal = [tuple(c) for c in spec["goal"]]
    final = simulate(spec["files0"], ops)
    assert final is not None, "a step of the trace does not run"
    return "yes" if not failing(final, goal) else "no"


LIST_RX = [re.compile(r"^(?P<p>%s) = (?P<c>%s)$" % (PATH, WORD)), re.compile(r"^(?P<p>%s): (?P<c>%s)$" % (PATH, WORD)),
           re.compile(r"^(?P<p>%s) \((?P<c>%s)\)$" % (PATH, WORD)), re.compile(r'^"(?P<p>%s)": "(?P<c>%s)"$' % (PATH, WORD))]
GOAL_RX = [{t: tmpl_regex(s) for t, s in g.items()} for g in GOAL]
NUM_RX = [re.compile(r"^(\d+)\. (.*)$"), re.compile(r"^step (\d+): (.*)$"), re.compile(r"^\[(\d+)\] (.*)$"), re.compile(r"^#(\d+) (.*)$")]
OP_RX = [{k: tmpl_regex(s) for k, s in n.items()} for n in NOTATION]


def parse_state(text):
    blocks = text.split("\n\n")
    assert len(blocks) == 5, len(blocks)
    start = [l[2:] for l in blocks[1].split("\n")[1:]]
    listing = None
    for rx in LIST_RX:
        got = [rx.match(l) for l in start]
        if all(got):
            listing = {m.group("p"): m.group("c") for m in got}
            break
    assert listing is not None and len(listing) == len(start), "file list not understood"
    glines = [l[2:] for l in blocks[3].split("\n")[1:]]
    goal = []
    for i, l in enumerate(glines, 1):
        m = re.match(r"^G%d\. (.*)$" % i, l)
        assert m, l
        hit = None
        for sx in range(4):
            for t, rx in GOAL_RX[sx].items():
                mm = rx.match(m.group(1))
                if mm:
                    assert hit is None, ("ambiguous goal line", l)
                    hit = (t, mm.groupdict())
        assert hit, ("goal line not understood", l)
        t, g = hit
        goal.append({"exists": ("exists", g.get("p")), "absent": ("absent", g.get("p")), "content": ("content", g.get("p"), g.get("c")),
                     "count": ("count", g.get("d"), int(g.get("n", 0))), "same": ("same", g.get("p"), g.get("q"))}[t])
    ops = []
    for i, l in enumerate([l[2:] for l in blocks[4].split("\n")[1:]], 1):
        body = None
        for rx in NUM_RX:
            m = rx.match(l)
            if m:
                assert int(m.group(1)) == i
                body = m.group(2)
                break
        assert body is not None, l
        hit = []
        for sx in range(4):
            for k, rx in OP_RX[sx].items():
                mm = rx.match(body)
                if mm:
                    g = mm.groupdict()
                    hit.append({"set": ("set", g.get("p"), g.get("c")), "delete": ("delete", g.get("p")), "rename": ("rename", g.get("p"), g.get("n")),
                                "copy": ("copy", g.get("p"), g.get("q")), "move": ("move", g.get("p"), g.get("f"))}[k])
        assert len(hit) == 1, ("step not understood", body, hit)
        ops.append(hit[0])
    return listing, goal, ops


def check(item):
    """re-simulates the trace of the state text on a second data structure: folder -> {name: content}; asserts on the way what the
    preamble of the state claims (every delete / rename / copy / move finds its source file, every step changes the store)"""
    listing, goal, ops = parse_state(item["state"])
    tree = collections.defaultdict(dict)
    for p, c in listing.items():
        f, nm = p.rsplit("/", 1)
        tree[f][nm] = c

    def snap():
        return {f: dict(d) for f, d in tree.items() if d}
    for i, op in enumerate(ops, 1):
        before = snap()
        f, nm = op[1].rsplit("/", 1)
        if op[0] != "set":
            assert nm in tree[f], ("source file missing", i, op)
        if op[0] == "set":
            tree[f][nm] = op[2]
        elif op[0] == "delete":
            del tree[f][nm]
        elif op[0] == "rename":
            c = tree[f].pop(nm)
            tree[f][op[2]] = c
        elif op[0] == "copy":
            g, nm2 = op[2].rsplit("/", 1)
            tree[g][nm2] = tree[f][nm]
        else:
            c = tree[f].pop(nm)
            tree[op[2]][nm] = c
        assert snap() != before, ("step does not change the store", i, op)

    def get(p):
        f, nm = p.rsplit("/", 1)
        return tree[f].get(nm)
    ok = True
    for c in goal:
        if c[0] == "exists":
            ok &= get(c[1]) is not None
        elif c[0] == "absent":
            ok &= get(c[1]) is None
        elif c[0] == "content":
            ok &= get(c[1]) == c[2]
        elif c[0] == "count":
            ok &= len(tree[c[1]]) == c[2]
        else:
            ok &= get(c[1]) is not None and get(c[1]) == get(c[2])
    return "yes" if ok else "no"


# ----------------------------------------------------------------------------------------------------------------
# a pair
# ----------------------------------------------------------------------------------------------------------------
def make_style(rng):
    return {"intro": rng.randrange(4), "ran": rng.randrange(4), "h_start": rng.randrange(4), "listing": rng.randrange(4),
            "h_sem": rng.randrange(4), "sem": {k: rng.randrange(4) for k in SEM}, "h_goal": rng.randrange(4),
            "goal": rng.randrange(4), "h_trace": rng.randrange(4),
            "numbering": rng.randrange(4), "notation": rng.randrange(4)}


def make_pair(rng, level, kind, domain):
    for attempt in range(1500):
        w = make_world(rng, level, domain)
        if w is None:
            continue
        files0, ctx = w
        got = walk(rng, files0, ctx, level)
        if got is None:
            continue
        ops, tags, intents = got
        goal = pick_goal(rng, files0, ops, N_CONDS[level], intents)
        if goal is None or goal_only_tokens(files0, ops, goal):
            continue
        assert not untouched_conditions(ops, goal), (ops, goal)
        mut = mutate(rng, files0, ctx, ops, tags, goal, kind)
        if mut is None:
            continue
        new_ops, new_tags, detail = mut
        style = make_style(rng)
        base = {"domain": domain, "files0": files0, "ops": [list(o) for o in ops], "macros": tags, "goal": [list(c) for c in goal],
                "style": style, "ctx": ctx, "steps": level, "deviation": None}
        dev = copy.deepcopy(base)
        dev["ops"] = [list(o) for o in new_ops]
        dev["macros"] = new_tags
        detail["failed_type"] = goal[detail["failed"]][0]
        detail["failed"] += 1                                               # 1-based index of the failing condition
        dev["deviation"] = detail
        return base, dev, attempt + 1
    raise RuntimeError(f"no pair for level {level} kind {kind} domain {domain}")


def vocab_test(states, gold, min_freq=20, max_ratio=2.0, pattern=r"[a-z]+"):
    n = collections.Counter(gold)
    df = {c: collections.Counter() for c in n}
    for s, g in zip(states, gold):
        df[g].update(set(re.findall(pattern, s.lower())))
    bad, tested, worst = [], 0, 1.0
    for t in set(df["yes"]) | set(df["no"]):
        a, b = df["yes"][t], df["no"][t]
        if a + b < min_freq:
            continue
        tested += 1
        ra, rb = a / n["yes"], b / n["no"]
        ratio = max(ra, rb) / min(ra, rb) if min(ra, rb) > 0 else float("inf")
        worst = max(worst, ratio)
        if ratio > max_ratio:
            bad.append((t, a, b))
    return sorted(bad), tested, worst


def dumps(item):
    return (json.dumps(item, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
            .replace("\x85", "\\u0085"))


def kind_counts(per_level=100):
    """deviation kinds of one level: 25 each"""
    return [k for k, c in zip(KINDS, PER_CELL) for _ in range(c)]


def main():
    master = random.Random(SEED)
    cells = [(lv, k) for lv in LEVELS for k in kind_counts()]
    seeds = [master.getrandbits(64) for _ in cells]
    rows, attempts = [], []
    for no, ((level, kind), seed) in enumerate(zip(cells, seeds), 1):
        domain = DOMAIN_NAMES[(no - 1) % len(DOMAIN_NAMES)]
        base, dev, att = make_pair(random.Random(seed), level, kind, domain)
        attempts.append(att)
        for spec, gold in ((base, "yes"), (dev, "no")):
            assert truth(spec) == gold, (no, kind, gold)
            rows.append({"pair": no, "level": level, "gold": gold, "spec": spec, "state": render_state(spec)})
    sub("shuffle").shuffle(rows)
    items = []
    for i, r in enumerate(rows, 1):
        spec = r["spec"]
        dv = spec["deviation"]
        item = {"id": f"{TASK}:{i:05d}", "state": r["state"], "questions": {"q": copy.deepcopy(QUESTION)}, "gold": r["gold"],
                "soft": None, "group": f"{TASK}:g{r['pair']:04d}",
                "meta": {"source_id": f"{i:05d}", "pair": f"{r['pair']:05d}", "level": LEVEL_OF[r["level"]], "steps": r["level"],
                         "domain": spec["domain"], "entries": len(spec["files0"]), "conditions": len(spec["goal"]),
                         "deviation": dv["kind"] if dv else None,
                         "failed_condition": dv["failed"] if dv else None, "failed_type": dv["failed_type"] if dv else None,
                         "changed": ({k: v for k, v in dv.items() if k in ("step", "step2", "removed", "inserted", "slot")} if dv else None),
                         "spec": spec}}
        assert check(item) == item["gold"] == truth(spec), item["id"]
        listing, goal, ops = parse_state(item["state"])
        ctx = spec["ctx"]
        assert listing == spec["files0"] and [list(o) for o in ops] == spec["ops"], item["id"]
        final = assert_run(listing, ops)                                    # the preamble holds for every step
        assert coherent(ops, listing, ctx), item["id"]                      # the trace can be cut into whole macros
        assert not untouched_conditions(ops, goal), item["id"]              # every file / folder of a condition is touched by a step
        assert len(spec["macros"]) == len(ops) and all(t in MACROS for t in spec["macros"]), item["id"]
        cur = listing
        for op in ops:                                                      # plausible steps, extensions kept on rename
            assert plausible(op, cur, ctx), (item["id"], op)
            if op[0] == "rename":
                assert ext_of(op[1]) == ext_of(op[2]), (item["id"], op)
            cur = step(cur, op)
        if dv:                                                              # exactly one failing condition, every step runs
            assert failing(final, goal) == [dv["failed"] - 1], item["id"]
        else:
            assert failing(final, goal) == [], item["id"]
        items.append(item)
    # pairs differ by exactly one change
    pairs = collections.defaultdict(dict)
    for it in items:
        pairs[it["meta"]["pair"]][it["gold"]] = it
    for p, d in pairs.items():
        a, b = d["yes"]["meta"]["spec"], d["no"]["meta"]["spec"]
        assert a["files0"] == b["files0"] and a["goal"] == b["goal"] and a["style"] == b["style"] and len(a["ops"]) == len(b["ops"])
        assert dead_steps(a["ops"], a["goal"]) == dead_steps(b["ops"], b["goal"]), p      # as many steps outside every cone in both members
        diff = sum(1 for x, y in zip(a["ops"], b["ops"]) if x != y)
        assert diff == (1 if b["deviation"]["kind"] in ("wrong_target", "wrong_content") else 2 if b["deviation"]["kind"] == "steps_swapped" else diff) and diff >= 1, (p, diff)
    dead = collections.defaultdict(list)
    for it in items:
        sp = it["meta"]["spec"]
        dead[(it["gold"], it["meta"]["level"])].append(dead_steps(sp["ops"], sp["goal"]))
    stats = {k: sum(v) / len(v) for k, v in dead.items()}
    gold = [it["gold"] for it in items]
    assert collections.Counter(gold) == {"yes": 300, "no": 300}
    for lv in LEVELS:
        assert collections.Counter(it["gold"] for it in items if it["meta"]["steps"] == lv) == {"yes": 100, "no": 100}
        assert all(it["meta"]["level"] == LEVEL_OF[lv] for it in items if it["meta"]["steps"] == lv)
        assert sum(1 for it in items if it["meta"]["level"] == LEVEL_OF[lv]) == 200
        for k in KINDS:
            assert sum(1 for it in items if it["meta"]["steps"] == lv and it["meta"]["deviation"] == k) == 25
        for dm in DOMAIN_NAMES:
            assert sum(1 for it in items if it["meta"]["steps"] == lv and it["meta"]["domain"] == dm) == 40
    for pat, name in ((r"[a-z]+", "words"), (r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]", "all tokens")):
        bad, tested, worst = vocab_test([it["state"] for it in items], gold, pattern=pat)
        print(f"vocabulary test ({name}): {tested} tokens with frequency >= 20, worst rate ratio {worst:.2f}, offenders {bad[:10]}")
        assert not bad
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "items.jsonl"), "w", encoding="utf-8") as f:
        for it in items:
            f.write(dumps(it) + "\n")
    lens = [len(it["state"]) for it in items]
    write_task_files(items, min(lens), max(lens))
    report(items, lens, stats)
    print(f"attempts per pair: mean {sum(attempts) / len(attempts):.1f}, max {max(attempts)}")


def write_task_files(items, lo, hi):
    tj = {"task": TASK, "layer": "D", "title": "Generated file-store traces: after these operations, are all goal conditions satisfied?",
          "decision": "whether, after an agent's numbered trace of set / delete / rename / copy / move steps on a small file store, every goal condition on the final tree holds (yes) or at least one fails (no)",
          "source": {"name": f"generator build/gen_{TASK}.py", "url": "", "files": [], "split": "generated, random.Random(20261007)",
                     "version": "gen_v4, 2026-10-08: true preamble (set creates or replaces; asserted for every step), ordinary file names and status words in five domains, goal-directed macro traces (deviations keep the trace macro-coherent), self-explaining deviation names, meta.level"},
          "licence": "generated by the benchmark's script (no third-party text)", "redistribution": "items included",
          "labels": "programmatic", "item_source": "generated", "metric": "accuracy", "chance": 0.5, "rows": len(items),
          "groups": 300, "question_type": "choice", "options": 2,
          "notes": ("300 matched pairs: a trace that reaches the goal (yes) and the same item with one operation of the trace changed so that exactly one goal "
                    "condition fails (no); the pair id is meta.pair, also the group. gen_v4: the preamble is true for every step (delete / rename / copy / move find their source "
                    "file, set creates the file or replaces its content, every step changes the store), file names and contents are ordinary names and status words "
                    "of five domains (meta.domain), traces are built from goal-directed macros (every trace, planted deviations included, can be cut into whole macros, so a deviation is a wrong choice inside valid macros), and the deviation kinds are named wrong_target (v0: wrong_key), "
                    "wrong_content (wrong_value), steps_swapped (swap), step_missing (missing; 75 each; one unrelated single step is inserted so the length is unchanged). "
                    "meta.failed_condition = the failing goal condition (1-based). meta.level 1 / 2 / 3 = meta.steps 5 / 15 / 25 (200 rows each); start size 6-8, 8-12, 11-15 files; "
                    "goal of 3, 5, 7 conditions (exists, absent, content, count, same; each is sensitive to at least one step). "
                    f"State length {lo} to {hi} characters. "
                    "Truth by simulation on the specification; recomputed by check(item) from the state text alone on a second data structure. "
                    "Four layouts of the file list, four wordings of the goal, four step notations and four numberings, drawn per item.")}
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


def report(items, lens, stats):
    head, line, r = audit_lines()
    import validate as validate_mod
    validate_mod.HERE = ROOT
    tj, errs = validate_mod.check(TASK)
    status = "OK" if not errs else "ERRORS " + "; ".join(errs[:3])
    cnt = collections.Counter((it["meta"]["steps"], it["meta"]["deviation"]) for it in items if it["gold"] == "no")
    ex = []
    for lv, k in zip(LEVELS, ["wrong_target", "steps_swapped", "step_missing"]):
        ex.append([it for it in items if it["meta"]["steps"] == lv and it["gold"] == "no" and it["meta"]["deviation"] == k][0])
    what = {"wrong_target": "one step acts on the wrong target: one path, new name or folder of one step is replaced by another one of the same kind that occurs in the item (a sibling file, the same file name in another folder, another folder that takes such files) so that the step is still a valid macro step; the failing goal can be of any type, a folder count included",
            "wrong_content": "the content word of one `set` step is replaced by another word that fits the file",
            "steps_swapped": "two steps (at most four places apart) exchange their places and the order matters (the trace stays a sequence of whole macros)",
            "step_missing": "one step is left out and an unrelated single-step macro is inserted elsewhere (the trace keeps its length)"}
    mcount = collections.Counter(t for it in items if it["gold"] == "yes" for t in it["meta"]["spec"]["macros"])
    dcount = collections.Counter((it["meta"]["domain"], it["meta"]["level"]) for it in items)
    lines = [f"# {TASK}", "", "Generated file-store traces: after these operations, are all goal conditions satisfied?", "",
             "- Decision: whether, after an agent's numbered trace of set / delete / rename / copy / move steps on a small file store, every goal condition on the final tree holds (yes) or at least one fails (no).",
             f"- Item source: generated by `build/gen_{TASK}.py` (`random.Random(20261007)`, standard library only, no input file); labels programmatic; licence: generated by the benchmark's script (no third-party text); items included.",
             f"- Rows: {len(items)} (300 yes, 300 no); metric: accuracy (chance 0.5). Rebuild: `python3 build/gen_{TASK}.py`.", "",
             "## What is generated", "",
             "Each state names the kind of store (five domains, `meta.domain`: office reports, software project, data analysis, website, course material), states what every step did, "
             "shows the files of a small folder tree at the start (path and a one-word status as content), one line for each kind of step saying what it does (including what happens when the target path is taken), "
             "a goal of 3, 5 or 7 conditions on the final tree (a file exists or does not, a file holds a word, a folder holds N files directly, two files hold the same word) and a numbered trace of the steps an agent ran. "
             "Every step finds its file and changes the tree, so no step looks wrong on its own. The 300 positives reach the goal; each has a twin in which one operation of the trace is changed so that exactly one goal condition fails. "
             "The file list has four layouts, the goal four wordings, the trace four notations and four numberings. "
             "Both rows of a pair are scored as separate items; they share `group` (= `meta.pair`), so a bootstrap that resamples by `group` accounts for their correlation and the audit keeps a pair in one fold.", "",
             "## What every step did (the preamble)", "",
             "The state says, in four phrasings: *every delete, rename, copy and move found its source file; set creates the file or replaces its content; every step changed the store.* "
             "The generator asserts this for every step of all 600 traces, and `check(item)` asserts it again on the parsed text, so a solver can rely on it. "
             "(In benchmark v0 / v1 the sentence claimed that the file each step works on existed, which was false for a `set` that creates a file.)", "",
             "## Names, contents and goal-directed traces", "",
             "File and folder names are ordinary names of the domain (`reports/q3_summary.md`, `data/customers_2026.csv`, `logs/app.log`, `releases/v2.1`, `drafts/lecture_02_draft.md`); contents are status words "
             "(`draft`, `review`, `approved`, `final`, `outdated`, `archived`, `v1`, `v2`, `raw`, `clean`, `validated`, `default`, `custom`, `stable`, `empty`, `debug`, `warnings`, `errors`, `cache`, `partial`, `stale`, `scratch`). "
             "A rename stays inside one file family and keeps the extension; a file is only moved or copied into a folder that takes files of its kind (a `.tmp` file never goes to the archive); a content word fits the kind of file. "
             "The generator asserts this (`plausible`) for every step of every trace, planted deviations included, so a changed step does not look odd by itself. "
             "It also asserts that every trace, planted deviations included, can be cut into whole macros (`coherent`): the planted change is a wrong choice inside valid macros "
             "(the wrong file archived, the wrong status written, two macros in the wrong order, a macro left out), never a broken macro, so the deviation cannot be found by looking at the structure of the trace. "
             "The trace is a sequence of *macros*, short purposeful sequences of 1 to 3 steps; every step belongs to a macro (`meta.spec.macros` names the macro of each step). Steps that no goal condition looks at are macros too (distractors that look purposeful). "
             "Goal conditions preferably state what a macro was meant to achieve. Macros (number of steps in the 300 positive traces):", "",
             "| macro | what it does | steps |", "|---|---|---|"]
    for m in MACRO_NAMES:
        lines.append(f"| {m} | {MACRO_TEXT[m]} | {mcount[m]} |")
    lines += ["", "## Dial", "",
              "`meta.level` = 1, 2, 3 = `meta.steps` = number of steps of the trace: 5, 15, 25 (200 rows each, 100 yes and 100 no). The start tree has 6-8, 8-12 and 11-15 files and the goal 3, 5 and 7 conditions. "
              "Each domain has 40 rows per level.", "",
              "## Deviation kinds (`meta.deviation`, number of no-items per level)", "",
              "| kind | formerly (v0, v1) | what is changed | level 1 | level 2 | level 3 | total |", "|---|---|---|---|---|---|---|"]
    for k in KINDS:
        lines.append(f"| {k} | {OLD_NAME[k]} | {what[k]} | " + " | ".join(str(cnt[(lv, k)]) for lv in LEVELS) + f" | {sum(cnt[(lv, k)] for lv in LEVELS)} |")
    lines += ["", "`meta.failed_condition` is the number of the goal condition that fails; its type is in `meta.failed_type`. "
              "With `wrong_target` the failing condition is often a folder count or a missing file, because the step acted on another file than intended; "
              "the name says what went wrong in the trace, not which kind of condition fails.", "",
              f"State length: {min(lens)} to {max(lens)} characters (median {sorted(lens)[len(lens) // 2]}).", "",
              "## Checks run by the script", "",
              "- `truth(spec)` (simulation on a dict of paths) and `check(item)` (parses the state text and simulates on a folder tree) agree on all 600 items; every negative fails exactly one condition and still runs every step; a pair differs only in the changed operation.",
              "- The preamble holds for every step of every trace (source file found, set creates or replaces, every step changes the store); every step is plausible; every rename keeps its extension; every trace (yes and no) can be cut into whole macros.",
              "- Exact balance: 300 yes / 300 no; 100 + 100 per level; 25 deviations per kind and level; 40 rows per domain and level. No change adds or removes a word of the state; every word of a goal occurs in the start list or the trace.",
              "- Every file or folder named by a goal condition is touched by at least one step of the trace (sources and resolved move / rename / copy targets; a `same` condition: one of its two files) in all 600 items, so an untouched condition never marks a negative. The left-out step of `step_missing` is never the only step that touches the failing condition's target, and the inserted step never touches it.",
              "- The number of steps outside the dependency cone of every goal condition (walking back from the goal, a step is live when it writes a file that a condition or a live step needs, or a file directly inside a folder of a count condition) is equal in the two members of every pair; mean per item, yes / no, level 1: "
              + f"{stats[('yes', 1)]:.2f} / {stats[('no', 1)]:.2f}, level 2: {stats[('yes', 2)]:.2f} / {stats[('no', 2)]:.2f}, level 3: {stats[('yes', 3)]:.2f} / {stats[('no', 3)]:.2f}.",
              "- Vocabulary test: no word (and no token) of frequency >= 20 is more than twice as frequent in one class as in the other.", "",
              "## Audit (`python3 audit.py " + TASK + "`)", "", "```", head, line, "```", "", f"`python3 validate.py {TASK}`: {status}.", "",
              "## Examples (one per level)", ""]
    for lv, it in zip(LEVELS, ex):
        lines += [f"### level {LEVEL_OF[lv]}, steps = {lv} ({it['id']}, {it['meta']['domain']}, deviation {it['meta']['deviation']}, failing condition G{it['meta']['failed_condition']})", "", "```", example_text(it), "```", ""]
    lines += ["## Relation to the authors' training data", "",
              "The items are disjoint from any training generator of the authors by construction: this is a new generator, written for this benchmark "
              "(its own templates, its own vocabulary of ordinary file and folder names and status words, its own macros)."]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"validate: {status}")
    print(head)
    print(line)
    print("classes:", dict(collections.Counter(it["gold"] for it in items)))
    print("per level:", dict(collections.Counter(it["meta"]["level"] for it in items)))
    print("per domain:", dict(collections.Counter(it["meta"]["domain"] for it in items)))
    print("per deviation:", dict(collections.Counter(it["meta"]["deviation"] for it in items)))
    print("per level and deviation (no-items):", dict(sorted(cnt.items())))
    print("macro steps (positive traces):", dict(mcount))
    print("dead steps per item (yes / no):", {lv: (round(stats[("yes", lv)], 2), round(stats[("no", lv)], 2)) for lv in (1, 2, 3)})
    print(f"state length: {min(lens)} to {max(lens)} characters")
    print("example (hardest level):")
    print(example_text(ex[-1]))


if __name__ == "__main__":
    main()
