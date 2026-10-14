"""Derive release 1.3 of DecisionPivot from a copy of release 1.1 (EVALUATION ONLY: the items are never a training source).

    python3 scoring/derive_v13.py [--root DIR] [--out DIR13]

Release 1.3 (10 October 2026) keeps the core track of release 1.1 and removes from 28 reference tasks 1,871 items: those found in the
training data of the final StartLux-Decision-27B models (scan of 10 October 2026), and those dropped with them to keep a group whole or
the classes balanced (releases/v1.3/dropped_from_v1.1.json).  The paper reports the reference track on release 1.3 (32,233 items).
Every kept line is copied byte for byte from DIR/tasks/<task>/items.jsonl (default DIR: data/), the result is checked against the
hashes of releases/v1.3/index.json, and the task card of release 1.3 is written as task.json (it accepts answer files made on the
release 1.1 items: field accepts_items_sha256).  Tasks that are absent from DIR are skipped and reported.  Default DIR13: data_v13/.
Exit status 1 when a derived task does not match release 1.3 (its folder is then not written).
"""
import hashlib
import json
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    argv = sys.argv[1:]
    root, out = os.path.join(REPO, "data"), os.path.join(REPO, "data_v13")
    if "--root" in argv:
        root = os.path.abspath(argv[argv.index("--root") + 1])
    if "--out" in argv:
        out = os.path.abspath(argv[argv.index("--out") + 1])
    rel = json.load(open(os.path.join(REPO, "releases", "v1.3", "index.json"), encoding="utf-8"))["tasks"]
    dropped = json.load(open(os.path.join(REPO, "releases", "v1.3", "dropped_from_v1.1.json"), encoding="utf-8"))
    done = bad = skipped = 0
    for t in sorted(rel):
        src = os.path.join(root, "tasks", t)
        if not os.path.isfile(os.path.join(src, "items.jsonl")):
            skipped += 1
            print(f"  {t:28s} not in {root}/tasks (skipped)")
            continue
        drop = set(dropped.get(t, []))
        with open(os.path.join(src, "items.jsonl"), "rb") as f:
            lines = f.read().splitlines(keepends=True)
        keep = [l for l in lines if json.loads(l)["id"] not in drop]
        data = b"".join(keep)
        if hashlib.sha256(data).hexdigest() != rel[t]["items_sha256"] or len(keep) != rel[t]["rows"]:
            bad += 1
            print(f"  {t:28s} DOES NOT MATCH release 1.3 ({len(keep)} items kept, release {rel[t]['rows']}); not written")
            continue
        d = os.path.join(out, "tasks", t)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "items.jsonl"), "wb") as f:
            f.write(data)
        shutil.copyfile(os.path.join(REPO, "releases", "v1.3", "task_cards", f"{t}.json"), os.path.join(d, "task.json"))
        if os.path.isfile(os.path.join(src, "README.md")):
            shutil.copyfile(os.path.join(src, "README.md"), os.path.join(d, "README.md"))
        done += 1
    print(f"release 1.3 written to {out}/tasks: {done} tasks identical to the release, {bad} mismatches, {skipped} skipped")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
