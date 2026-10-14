"""Shortcut audit of task folders: how far do rules that never read the content get?
    python3 audits/audit.py [--root DIR] [TASK ...] [--out FILE]   (DIR holds tasks/<task>/; default generated/)
For every task with a gold option:
  majority     accuracy of always giving the most frequent gold option
  first        accuracy of always giving the first listed option
  length       binary tasks: accuracy of the best single threshold on a length (characters) - of the whole state and
               of each text field of the state; the best of them is reported with its field.
               comparison tasks (state fields named like the option keys, e.g. response_A / response_B): accuracy
               of "pick the longest" and of "pick the shortest"; the better one is reported.
  flag         * when the best content-free rule is more than 10 points above chance (or above the majority rate)
A flagged task needs a length-matched or otherwise repaired sample before its score means anything."""
import collections
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repository root (this file is audits/audit.py)
HERE = os.path.join(REPO, "generated")                               # the folder that holds tasks/<task>/; --root DIR changes it


def flat_len(v):
    return len(v) if isinstance(v, str) else len(json.dumps(v, ensure_ascii=False))


def best_threshold(xs, ys):
    """best accuracy of a rule 'x > t -> positive' or its mirror; xs numbers, ys booleans"""
    order = sorted(zip(xs, ys))
    n, pos = len(order), sum(ys)
    best = max(pos, n - pos) / n
    tp_left = 0                                   # positives among the i smallest
    i = 0
    while i < n:
        j = i
        while j < n and order[j][0] == order[i][0]:
            tp_left += order[j][1]
            j += 1
        # rule A: x > t -> positive: correct = negatives on the left + positives on the right
        a = (j - tp_left) + (pos - tp_left)
        best = max(best, a / n, (n - a) / n)
        i = j
    return best


def audit(task):
    d = f"{HERE}/tasks/{task}"
    tj = json.load(open(f"{d}/task.json"))
    rows = [json.loads(l) for l in open(f"{d}/items.jsonl", encoding="utf-8")]
    if not rows or rows[0].get("gold") is None:
        return None
    n = len(rows)
    keysets = []
    for r in rows:
        c = r["questions"]["q"].get("criteria")
        keysets.append([str(i) for i in range(len(c))] if isinstance(c, list) else list(c))
    gold = [str(r["gold"]) for r in rows]
    chance = sum(1 / len(k) for k in keysets) / n
    maj = collections.Counter(gold).most_common(1)[0][1] / n
    first = sum(g == k[0] for g, k in zip(gold, keysets)) / n
    res = {"task": task, "layer": tj["layer"], "rows": n, "chance": chance, "majority": maj, "first": first,
           "length": None, "length_rule": ""}
    st0 = rows[0]["state"]
    fields = list(st0) if isinstance(st0, dict) else []
    binary = all(set(k) == {"yes", "no"} for k in keysets)
    if binary:
        ys = [g == "yes" for g in gold]
        cands = {"state": [flat_len(r["state"]) for r in rows]}
        for f in fields:
            if all(isinstance(r["state"], dict) and f in r["state"] for r in rows):
                cands[f] = [flat_len(r["state"][f]) for r in rows]
        best = max(((best_threshold(x, ys), f) for f, x in cands.items()))
        res["length"], res["length_rule"] = best[0], f"threshold on length of {best[1]}"
    else:
        # comparison: every option key K has a state field ending in _K
        def field_for(k):
            m = [f for f in fields if f.endswith("_" + k)]
            return m[0] if len(m) == 1 else None
        if fields and all(all(field_for(k) for k in ks) for ks in keysets[:50]):
            lo = hi = 0
            for r, ks, g in zip(rows, keysets, gold):
                ls = {k: flat_len(r["state"][field_for(k)]) for k in ks}
                hi += max(ks, key=lambda k: ls[k]) == g
                lo += min(ks, key=lambda k: ls[k]) == g
            res["length"], res["length_rule"] = (hi / n, "pick the longest") if hi >= lo else (lo / n, "pick the shortest")
    ref = max(chance, maj)
    best_rule = max(x for x in (first, res["length"]) if x is not None)
    res["flag"] = best_rule > ref + 0.10
    return res


def main():
    global HERE
    if "--root" in sys.argv:                                         # --root DIR: the folder that holds tasks/<task>/
        i = sys.argv.index("--root")
        HERE = os.path.abspath(sys.argv[i + 1])
        del sys.argv[i:i + 2]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
    if out:
        args.remove(out)
    tasks = args or sorted(t for t in os.listdir(f"{HERE}/tasks") if os.path.isfile(f"{HERE}/tasks/{t}/task.json"))
    lines = [f"{'layer':5s} {'task':28s} {'rows':>5s} {'chance':>6s} {'major.':>6s} {'first':>6s} {'length':>6s}  rule"]
    res = []
    for t in tasks:
        r = audit(t)
        if r is None:
            lines.append(f"{'':5s} {t:28s} (soft labels: no gold option)")
            continue
        res.append(r)
        ln = f"{r['length']:6.3f}" if r["length"] is not None else f"{'':6s}"
        lines.append(f"{r['layer']:5s} {t:28s} {r['rows']:5d} {r['chance']:6.3f} {r['majority']:6.3f} {r['first']:6.3f} {ln}  "
                     f"{r['length_rule']}{'   *' if r['flag'] else ''}")
    print("\n".join(lines))
    if out:
        json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
