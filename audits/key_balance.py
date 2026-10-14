"""Release gate of the generated families: distribution of the keys per task and level.
    python3 audits/key_balance.py [--root DIR] [TASK ...] [--json FILE]   (DIR holds tasks/<task>/; default generated/)
Fixed option keys (yes/no, approve/deny/escalate, same/yes_only_A/yes_only_B ...): count of every key per level.
Keys that differ per item (entry labels, case ids, rule keys): count of the gold POSITION per level, and the share of the
special key `none` where the task has one.  A task fails the gate when a fixed key or a gold position misses a level, or when
the share of a fixed key in a level deviates from 1 / number of keys by more than 0.10 (none of record_rule is designed at
about 1 / mean number of options and is reported, not gated)."""
import collections
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repository root (this file is audits/key_balance.py)
HERE = os.path.join(REPO, "generated")                               # the folder that holds tasks/<task>/; --root DIR changes it


def keys_of(it):
    c = it["questions"]["q"]["criteria"]
    return [str(i) for i in range(len(c))] if isinstance(c, list) else list(c)


def gate(task):
    items = [json.loads(l) for l in open(f"{HERE}/tasks/{task}/items.jsonl", encoding="utf-8")]
    lv = lambda it: (it.get("meta") or {}).get("level")
    fixed = all(set(keys_of(it)) == set(keys_of(items[0])) for it in items)
    out, fails = {"task": task, "fixed": fixed, "levels": {}}, []
    for L in sorted({lv(it) for it in items}, key=str):
        sub = [it for it in items if lv(it) == L]
        if fixed:
            ks = sorted(keys_of(items[0]))
            c = collections.Counter(str(it["gold"]) for it in sub)
            out["levels"][str(L)] = {k: c[k] for k in ks}
            for k in ks:
                if abs(c[k] / len(sub) - 1 / len(ks)) > 0.10:
                    fails.append(f"level {L}: key {k} {c[k]}/{len(sub)}")
        else:
            c = collections.Counter(keys_of(it).index(str(it["gold"])) for it in sub)
            d = {f"pos{p}": c[p] for p in range(max(len(keys_of(it)) for it in sub))}
            if any("none" in keys_of(it) for it in sub):
                d["none"] = sum(str(it["gold"]) == "none" for it in sub)
            out["levels"][str(L)] = d
            if any(v == 0 for k, v in d.items() if k.startswith("pos")):
                fails.append(f"level {L}: a gold position never occurs")
        if L is None:
            fails.append("items without meta.level")
    out["fails"] = fails
    return out


def main():
    global HERE
    if "--root" in sys.argv:                                         # --root DIR: the folder that holds tasks/<task>/
        i = sys.argv.index("--root")
        HERE = os.path.abspath(sys.argv[i + 1])
        del sys.argv[i:i + 2]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    js = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
    if js:
        args.remove(js)
    tasks = args or sorted(t for t in os.listdir(f"{HERE}/tasks") if os.path.isfile(f"{HERE}/tasks/{t}/items.jsonl"))
    res = [gate(t) for t in tasks]
    for r in res:
        print(f"{r['task']:18s} {'PASS' if not r['fails'] else 'FAIL ' + '; '.join(r['fails'][:3])}")
        for L, d in r["levels"].items():
            print(f"    level {L}: " + "  ".join(f"{k} {v}" for k, v in d.items()))
    if js:
        json.dump(res, open(js, "w"), indent=1)
    sys.exit(1 if any(r["fails"] for r in res) else 0)


if __name__ == "__main__":
    main()
