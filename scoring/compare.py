"""Paired comparison of two systems on the benchmark: difference of the layer scores and of the overall score with a
bootstrap interval.  In every resample the same items (or groups, for the grouped metrics) are drawn for both systems
in every task, the task scores are chance-corrected and floored at 0 as in score.py, layers are averaged and the
overall score is the mean of the layers.

    python3 scoring/compare.py [--root DIR] A=RUN_DIR B=RUN_DIR [--tasks T1,T2] [--resamples 1000] [--subsample FILE]
--root DIR: the benchmark folder that holds tasks/<task>/ (default: data/ of the repository).  The definitions are those of score.py
(load_task, keys_of, probs_of, unit_values, chance_of); the layer scores are those of the reference track.
prints  layer  A  B  B - A  [95% interval]  share of resamples with B > A
"""
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score as S  # noqa: E402


def task_units(task, run_dir, subsample=None):
    tj, items = S.load_task(task)
    if subsample is not None:
        keep = set(subsample.get(task, []))
        items = [i for i in items if i["id"] in keep]
    f = f"{run_dir}/{task}.jsonl"
    lines = {}
    if os.path.exists(f):
        for l in open(f, encoding="utf-8"):
            if l.endswith("\n"):
                try:
                    x = json.loads(l)
                except Exception:
                    continue
                if "error" not in x:
                    lines[x["id"]] = x
    probs = {i["id"]: S.probs_of(lines.get(i["id"]), S.keys_of(i)) for i in items}
    if not items or not any(p is not None for p in probs.values()):
        return None
    units, fn = S.unit_values(tj, items, probs)
    chance = S.chance_of(tj, items)
    scale = (lambda v: 100 * v) if tj["metric"] == "mse_soft" else (lambda v: 100 * (v - chance) / (1 - chance))
    return tj["layer"], units, fn, scale


def main():
    if "--root" in sys.argv:                                         # --root DIR: the folder that holds tasks/<task>/
        i = sys.argv.index("--root")
        S.HERE = os.path.abspath(sys.argv[i + 1])
        del sys.argv[i:i + 2]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opt = {}
    for flag in ("--tasks", "--resamples", "--subsample"):
        if flag in sys.argv:
            opt[flag] = sys.argv[sys.argv.index(flag) + 1]
            args.remove(opt[flag])
    (na, da), (nb, db) = [a.split("=", 1) for a in args[:2]]
    tasks = opt["--tasks"].split(",") if "--tasks" in opt else sorted(
        t for t in os.listdir(f"{S.HERE}/tasks") if os.path.isfile(f"{S.HERE}/tasks/{t}/task.json"))
    n_res = int(opt.get("--resamples", 1000))
    subsample = json.load(open(opt["--subsample"])) if "--subsample" in opt else None
    both = []
    for t in tasks:
        a, b = task_units(t, da, subsample), task_units(t, db, subsample)
        if a is None or b is None or len(a[1]) != len(b[1]):
            print(f"   (task {t} left out: not answered by both systems on the same units)")
            continue
        both.append((t, a, b))

    def overall(pick):
        lay = {0: collections.defaultdict(list), 1: collections.defaultdict(list)}
        for t, a, b in both:
            idx = pick(t, len(a[1]))
            for j, (layer, units, fn, scale) in enumerate((a, b)):
                v = fn([units[i] for i in idx])
                sc = scale(v) if v == v else 0.0
                lay[j][layer].append(max(0.0, sc))
        out = []
        for j in (0, 1):
            ls = {k: sum(v) / len(v) for k, v in lay[j].items()}
            ls["overall"] = sum(ls.values()) / len(ls)
            out.append(ls)
        return out

    pa, pb = overall(lambda t, n: range(n))
    rng = random.Random(S.SEED)
    diffs = collections.defaultdict(list)
    for _ in range(n_res):
        ra, rb = overall(lambda t, n: [rng.randrange(n) for _ in range(n)])
        for k in ra:
            diffs[k].append(rb[k] - ra[k])
    print(f"paired comparison on {len(both)} tasks, {n_res} resamples: A = {na}, B = {nb}")
    print(f"{'layer':8s} {'A':>6s} {'B':>6s} {'B - A':>7s}  {'95% interval':>16s}  share B > A")
    for k in sorted(pa, key=lambda x: (x == "overall", x)):
        d = sorted(diffs[k])
        lo, hi = d[int(0.025 * len(d))], d[min(len(d) - 1, int(0.975 * len(d)))]
        print(f"{k:8s} {pa[k]:6.1f} {pb[k]:6.1f} {pb[k] - pa[k]:+7.1f}  [{lo:+6.1f}, {hi:+6.1f}]  {sum(x > 0 for x in d) / len(d):.3f}")


if __name__ == "__main__":
    main()
