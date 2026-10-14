"""Rebuild the reference tasks of DecisionPivot whose items this repository does not redistribute (EVALUATION ONLY).

    python3 reference/rebuild.py --list
    python3 reference/rebuild.py TASK INPUT [--version 1.1|1.3] [--out DIR]
    python3 reference/rebuild.py TASK --no-build [--version 1.1|1.3] [--out DIR]   (use the raw output of an earlier build)

INPUT is what the build script of the task reads (column "input" of --list, details in reference/README.md):
  CACHE_DIR   a download folder; the script fetches every source file it needs from a pinned commit or address into it when the file
              is not there yet, and stops when a SHA-256 differs (a changed source is never converted silently)
  RR_ITEMS    the item file of the reranking test, written by reference/build/rr_build.py from the test's repository and BEIR
  PILOT       the pilot file of the capability-boundary tasks, written by reference/build/capb_build.py from stored sampled answers

The script runs reference/build/<script> on INPUT (raw output in generated/reference/tasks/<task>/), keeps the items that the release
holds and drops the others: for release 1.1 the items listed in releases/v1.1/build_drops.json (found in the authors' training data in
the scan of 7 October 2026, or dropped with them to restore the class balance), for release 1.3 also those of
releases/v1.3/dropped_from_v1.1.json (scan of 10 October 2026).  Kept lines are copied byte for byte.  The number of items and the
SHA-256 of the result must equal those of the task card of the release (releases/v<version>/task_cards/<task>.json); only then is
DIR/tasks/<task>/ written (items.jsonl, the task card as task.json, the README.md of the build script).  Default DIR: data/ of the
repository, the folder the scorer reads.  Exit status 1 on any mismatch (nothing is written then).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_DIR = os.path.join(REPO, "reference", "build")
RAW = os.path.join(REPO, "generated", "reference", "tasks")

# task -> (build script, kind of input, extra Python packages)
BUILD = {
    "cap_boundary_card": ("build_cap_boundary.py", "PILOT", ""),
    "cap_boundary_record": ("build_cap_boundary.py", "PILOT", ""),
    "freshqa_premise": ("build_freshqa_premise.py", "CACHE_DIR", ""),
    "faithbench": ("build_faithbench.py", "CACHE_DIR", ""),
    "rewardbench": ("build_rewardbench.py", "CACHE_DIR", "pyarrow"),
    "agentreward_success": ("build_agentreward_success.py", "CACHE_DIR", ""),
    "mind2web_element": ("build_mind2web_element.py", "CACHE_DIR", "pyarrow"),
    "label_errors": ("build_label_errors.py", "CACHE_DIR", ""),
    "entity_match_abt_buy": ("build_entity_match_abt_buy.py", "CACHE_DIR", ""),
    "entity_match_amazon_google": ("build_entity_match_amazon_google.py", "CACHE_DIR", ""),
    "paws": ("build_paws.py", "CACHE_DIR", "pyarrow"),
    "rerank_nfcorpus": ("build_rerank.py", "RR_ITEMS", ""),
    "rerank_scifact": ("build_rerank.py", "RR_ITEMS", ""),
}


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def rewrite_line(line):
    """one item line as the decontamination step of release 1.0 wrote it: compact JSON, non-ASCII kept, the three characters that
    str.splitlines() takes for line ends written as escapes (the build scripts that escape them already write the same bytes)"""
    s = json.dumps(json.loads(line), ensure_ascii=False)
    return (s.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029").replace("\x85", "\\u0085") + "\n").encode("utf-8")


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    if argv[0] == "--list":
        cards = os.path.join(REPO, "releases", "v1.1", "task_cards")
        print(f"{'task':28s} {'layer':5s} {'items 1.1':>9s} {'items 1.3':>9s}  {'input':9s}  script")
        for t, (script, kind, extra) in BUILD.items():
            c11 = jload(os.path.join(cards, f"{t}.json"))
            c13 = jload(os.path.join(REPO, "releases", "v1.3", "task_cards", f"{t}.json"))
            print(f"{t:28s} {c11['layer']:5s} {c11['rows']:9d} {c13['rows']:9d}  {kind:9s}  {script}" + (f" (needs {extra})" if extra else ""))
        return
    version, out_root = "1.1", os.path.join(REPO, "data")
    if "--version" in argv:
        i = argv.index("--version")
        version = argv[i + 1]
        del argv[i:i + 2]
    if "--out" in argv:
        i = argv.index("--out")
        out_root = os.path.abspath(argv[i + 1])
        del argv[i:i + 2]
    no_build = "--no-build" in argv
    if no_build:
        argv.remove("--no-build")
    if version not in ("1.1", "1.3") or len(argv) != (1 if no_build else 2) or argv[0] not in BUILD:
        sys.exit(f"usage: rebuild.py TASK INPUT|--no-build [--version 1.1|1.3] [--out DIR]; TASK one of: {', '.join(BUILD)}")
    task = argv[0]
    script, kind, extra = BUILD[task]
    card_path = os.path.join(REPO, "releases", f"v{version}", "task_cards", f"{task}.json")
    card = jload(card_path)
    drop = set(jload(os.path.join(REPO, "releases", "v1.1", "build_drops.json")).get(task, []))
    if version == "1.3":
        drop |= set(jload(os.path.join(REPO, "releases", "v1.3", "dropped_from_v1.1.json")).get(task, []))
    raw_items = os.path.join(RAW, task, "items.jsonl")
    if not no_build:
        inp = os.path.abspath(argv[1])
        print(f"{task}: running reference/build/{script} on {inp}", flush=True)
        r = subprocess.run([sys.executable, os.path.join(BUILD_DIR, script), inp], cwd=REPO)
        if r.returncode != 0:
            sys.exit(f"{task}: the build script failed (exit {r.returncode}); nothing written")
    if not os.path.isfile(raw_items):
        sys.exit(f"{task}: no raw output in {os.path.relpath(raw_items, REPO)}; nothing written")
    with open(raw_items, "rb") as f:
        lines = f.read().splitlines(keepends=True)
    keep = [l for l in lines if json.loads(l)["id"] not in drop]
    if jload(os.path.join(REPO, "releases", "v1.1", "build_drops.json")).get(task):
        keep = [rewrite_line(l) for l in keep]           # release 1.0 rewrote the files it shortened, with this serializer
    data = b"".join(keep)
    digest = hashlib.sha256(data).hexdigest()
    print(f"{task}: {len(lines)} items built, {len(lines) - len(keep)} dropped, {len(keep)} kept; release {version}: {card['rows']} items")
    if len(keep) != card["rows"] or digest != card["items_sha256"]:
        sys.exit(f"{task}: MISMATCH with release {version} (items {len(keep)} vs {card['rows']}, sha256 {digest[:16]} vs "
                 f"{card['items_sha256'][:16]}); nothing written.  A source file may have changed upstream, see reference/README.md")
    d = os.path.join(out_root, "tasks", task)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "items.jsonl"), "wb") as f:
        f.write(data)
    shutil.copyfile(card_path, os.path.join(d, "task.json"))
    readme = os.path.join(RAW, task, "README.md")
    if os.path.isfile(readme):
        shutil.copyfile(readme, os.path.join(d, "README.md"))
    print(f"{task}: identical to release {version} (sha256 {digest[:16]}...); written to {d}")


if __name__ == "__main__":
    main()
