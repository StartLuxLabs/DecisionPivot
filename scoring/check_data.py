"""Check a copy of the DecisionPivot items against the published hashes (EVALUATION ONLY: the items are never a training source).

    python3 scoring/check_data.py [--root DIR] [--version 1.1|1.3]

For every task of the release (releases/v<version>/index.json; default 1.1, the version on the Hugging Face dataset) the script compares
the SHA-256 and the number of lines of DIR/tasks/<task>/items.jsonl (default DIR: data/ of the repository) with the published values and
reports a task folder that is missing.  The 13 reference tasks that are distributed as rebuild scripts only are reported as missing until
they are rebuilt with reference/rebuild.py.  Exit status 1 when a task that is present differs from the release.
"""
import hashlib
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    argv = sys.argv[1:]
    root, version = os.path.join(REPO, "data"), "1.1"
    if "--root" in argv:
        root = os.path.abspath(argv[argv.index("--root") + 1])
    if "--version" in argv:
        version = argv[argv.index("--version") + 1]
    p = os.path.join(REPO, "releases", f"v{version}", "index.json")
    if not os.path.isfile(p):
        sys.exit(f"no release {version} (releases/v{version}/index.json)")
    rel = json.load(open(p, encoding="utf-8"))
    ok = differ = missing = 0
    print(f"release {version}: {len(rel['tasks'])} tasks, {rel['items']:,} items; checking {root}/tasks/")
    for t, e in sorted(rel["tasks"].items(), key=lambda kv: (kv[1]["track"] != "core", kv[1]["layer"], kv[0])):
        f = os.path.join(root, "tasks", t, "items.jsonl")
        if not os.path.isfile(f):
            missing += 1
            hint = " (rebuild with reference/rebuild.py)" if e.get("redistribution") == "rebuild script only" else ""
            print(f"  {e['track']:9s} {e['layer']} {t:28s} missing{hint}")
            continue
        n = sum(1 for _ in open(f, encoding="utf-8"))
        same = sha256_file(f) == e["items_sha256"] and n == e["rows"]
        ok += same
        differ += not same
        if not same:
            print(f"  {e['track']:9s} {e['layer']} {t:28s} DIFFERS ({n} lines, release {e['rows']})")
    print(f"identical: {ok}, different: {differ}, missing: {missing}")
    sys.exit(1 if differ else 0)


if __name__ == "__main__":
    main()
