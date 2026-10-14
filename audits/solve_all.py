"""Label audit of the generated families: every item is solved again by an independent second implementation.
    python3 audits/solve_all.py [--root DIR] [TASK ...] [--json FILE]   (DIR holds tasks/<task>/; default generated/)

solvers/<task>.py was written separately from generators/<task>.py (by another author who did not read the generator)
and exposes
    solve(state, question, options) -> option key
It receives ONLY what a decision model receives: the rendered state, the question text and the options (an ordered
dict key -> option text).  It never sees `gold`, `meta` or the item id.  This script calls it on every item and compares
the answer with `gold`.  Exit status 1 unless the agreement is 100 % for every task named."""
import collections
import importlib.util
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repository root (this file is audits/solve_all.py)
HERE = os.path.join(REPO, "generated")                               # the folder that holds tasks/<task>/; --root DIR changes it


def load_solver(task):
    p = f"{REPO}/solvers/{task}.py"
    if not os.path.exists(p):
        return None
    spec = importlib.util.spec_from_file_location(f"solve_{task}", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.solve


def run(task):
    solve = load_solver(task)
    items = [json.loads(l) for l in open(f"{HERE}/tasks/{task}/items.jsonl", encoding="utf-8")]
    r = {"task": task, "rows": len(items), "solver": solve is not None, "agree": 0, "errors": 0, "disagree": []}
    if solve is None:
        return r
    for it in items:
        q = it["questions"]["q"]
        c = q["criteria"]
        opts = collections.OrderedDict((str(i), x) for i, x in enumerate(c)) if isinstance(c, list) else collections.OrderedDict(c)
        try:
            ans = solve(json.loads(json.dumps(it["state"])), q["instructions"], opts)
        except Exception as e:                                   # a state the solver cannot read counts as a disagreement
            r["errors"] += 1
            r["disagree"].append((it["id"], f"{type(e).__name__}: {str(e)[:120]}", str(it["gold"])))
            continue
        if str(ans) == str(it["gold"]):
            r["agree"] += 1
        else:
            r["disagree"].append((it["id"], str(ans), str(it["gold"])))
    return r


def main():
    global HERE
    if "--root" in sys.argv:                                         # --root DIR: the folder that holds tasks/<task>/
        i = sys.argv.index("--root")
        HERE = os.path.abspath(sys.argv[i + 1])
        del sys.argv[i:i + 2]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
    if out:
        args.remove(out)
    tasks = args or sorted(t for t in os.listdir(f"{HERE}/tasks") if os.path.isfile(f"{HERE}/tasks/{t}/items.jsonl"))
    res, bad = [], 0
    print(f"{'task':18s} {'rows':>5s} {'agree':>6s} {'share':>7s}  status")
    for t in tasks:
        r = run(t)
        res.append(r)
        ok = r["solver"] and r["agree"] == r["rows"]
        bad += not ok
        st = "OK" if ok else ("NO SOLVER" if not r["solver"] else f"DISAGREE ({r['errors']} unreadable)")
        print(f"{t:18s} {r['rows']:5d} {r['agree']:6d} {r['agree'] / max(1, r['rows']):7.4f}  {st}")
        for x in r["disagree"][:8]:
            print("      ", x)
    if out:
        json.dump(res, open(out, "w"), indent=1)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
