"""Validate task folders against the item format (docs/SCHEMA.md) and print a registry table.
    python3 audits/validate.py [--root DIR] [TASK ...]   (default: every directory under DIR/tasks/; DIR defaults to generated/)"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repository root (this file is audits/validate.py)
HERE = os.path.join(REPO, "generated")                               # the folder that holds tasks/<task>/; --root DIR changes it
REQ_TASK = ["task", "layer", "title", "decision", "source", "licence", "redistribution", "labels", "item_source", "metric",
            "chance", "rows", "question_type", "options"]
METRICS = {"accuracy", "auroc", "ndcg@10", "pair_accuracy", "mse_soft"}


def check(task):
    d = f"{HERE}/tasks/{task}"
    errs = []
    try:
        tj = json.load(open(f"{d}/task.json"))
    except Exception as e:
        return None, [f"task.json: {e}"]
    for k in REQ_TASK:
        if k not in tj:
            errs.append(f"task.json lacks {k}")
    if tj.get("metric") not in METRICS:
        errs.append(f"unknown metric {tj.get('metric')}")
    ids, n, groups = set(), 0, set()
    for ln, line in enumerate(open(f"{d}/items.jsonl", encoding="utf-8"), 1):
        try:
            r = json.loads(line)
        except Exception as e:
            errs.append(f"line {ln}: {e}")
            continue
        n += 1
        if r.get("id") in ids:
            errs.append(f"line {ln}: duplicate id {r.get('id')}")
        ids.add(r.get("id"))
        q = (r.get("questions") or {}).get("q")
        if not q or q.get("type") not in ("choice", "score", "noul") or not q.get("instructions"):
            errs.append(f"line {ln}: bad question")
            continue
        crit = q.get("criteria")
        keys = [str(i) for i in range(len(crit))] if isinstance(crit, list) else list(crit or {})
        if q["type"] != "noul" and len(keys) < 2:
            errs.append(f"line {ln}: fewer than two options")
        if (r.get("gold") is None) == (r.get("soft") is None):
            errs.append(f"line {ln}: exactly one of gold / soft must be set")
        if r.get("gold") is not None and q["type"] != "noul" and str(r["gold"]) not in keys:
            errs.append(f"line {ln}: gold {r['gold']!r} is not an option")
        if r.get("soft") is not None and (set(r["soft"]) - set(keys) or abs(sum(r["soft"].values()) - 1) > 1e-3):
            errs.append(f"line {ln}: soft label does not match the options")
        if "state" not in r or r["state"] in ("", None):
            errs.append(f"line {ln}: empty state")
        if r.get("group"):
            groups.add(r["group"])
        if len(errs) > 20:
            break
    if tj.get("rows") != n:
        errs.append(f"task.json rows {tj.get('rows')} != {n} lines")
    if tj.get("metric") in ("ndcg@10", "pair_accuracy") and not groups:
        errs.append("metric needs groups, none found")
    tj["_rows"], tj["_groups"] = n, len(groups)
    return tj, errs


def main():
    global HERE
    if "--root" in sys.argv:                                         # --root DIR: the folder that holds tasks/<task>/
        i = sys.argv.index("--root")
        HERE = os.path.abspath(sys.argv[i + 1])
        del sys.argv[i:i + 2]
    tasks = sys.argv[1:] or sorted(t for t in os.listdir(f"{HERE}/tasks") if os.path.isdir(f"{HERE}/tasks/{t}"))
    bad = 0
    print(f"{'layer':5s} {'task':28s} {'rows':>6s} {'groups':>6s} {'metric':13s} {'labels':16s} {'licence':28s} status")
    for t in tasks:
        tj, errs = check(t)
        bad += bool(errs)
        if tj:
            print(f"{tj.get('layer', '?'):5s} {t:28s} {tj['_rows']:6d} {tj['_groups']:6d} {str(tj.get('metric')):13s} {str(tj.get('labels'))[:16]:16s} "
                  f"{str(tj.get('licence'))[:28]:28s} {'OK' if not errs else 'ERRORS'}")
        else:
            print(f"?     {t:28s} {'':6s} {'':6s} {'':13s} {'':16s} {'':28s} ERRORS")
        for e in errs[:8]:
            print("        -", e)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
