"""Regenerate core families of DecisionPivot from their seeds and verify them (EVALUATION ONLY: the items are never a training source).

    python3 generators/regenerate.py [FAMILY ...] [--check] [--install DIR]
    python3 generators/regenerate.py FAMILY ... --seed K [--seed K2 ...] [--check]

Without --seed, every named family (default: all 13) is generated with the published seed 20261007 by generators/<family>.py into
generated/tasks/<family>/, and the SHA-256 of its items.jsonl is compared with the hash of release 1.1 (releases/v1.1/index.json).

--check also runs, on the generated files, the independent solver (audits/solve_all.py, 100% agreement required), the format check
(audits/validate.py), the content-blind rules (audits/audit.py, no flag) and the balance of the keys per level (audits/key_balance.py).

--install DIR copies every family whose hash matches release 1.1 into DIR/tasks/<family>/ (items.jsonl, README.md) with the task card
of release 1.1 as task.json (releases/v1.1/task_cards/<family>.json), so that the core track can be scored from DIR without the download.

--seed K draws a new set of 600 items with the root seed K (only the seven families whose generator takes a seed: clause_change,
dep_resolve, ledger_reconcile, perm_inherit, record_rule, sched_conflict, triage_order) into generated/seed_K/tasks/<family>/, with ids
"<family>:s<K>:...".  Such a set is not release 1.1, so no hash is compared; --check runs the same checks on it.

The output of every generator goes to generated/logs/.  Python 3.9 or newer, standard library only (audit_v3.py, which needs numpy, is
not run here).  Exit status 1 if any family fails a check.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAMILIES = ["answerable_facts", "perm_inherit", "policy_case", "log_count_check", "sched_conflict", "state_goal", "toolcall_valid",
            "triage_order", "clause_change", "dep_resolve", "ledger_reconcile", "record_rule", "filter_match"]
SEEDED = ["clause_change", "dep_resolve", "ledger_reconcile", "perm_inherit", "record_rule", "sched_conflict", "triage_order"]


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def run(cmd, log=None, env=None):
    r = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True)
    if log:
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "w", encoding="utf-8") as f:
            f.write(r.stdout + r.stderr)
    return r


def checks(root, family):
    """-> dict of check name -> (ok, short text) on root/tasks/<family>/"""
    out = {}
    py = [sys.executable, "-I"]
    r = run(py + ["audits/solve_all.py", "--root", root, family])
    line = next((l for l in r.stdout.splitlines() if l.startswith(family + " ")), "")
    parts = line.split()
    out["solver"] = (r.returncode == 0, f"{parts[2]}/{parts[1]}" if len(parts) >= 3 else "no result")
    r = run(py + ["audits/validate.py", "--root", root, family])
    out["validate"] = (r.returncode == 0, "OK" if r.returncode == 0 else "ERRORS")
    r = run(py + ["audits/audit.py", "--root", root, family])
    flagged = any(l.startswith(tuple("ABCDEFG")) and l.rstrip().endswith("*") for l in r.stdout.splitlines())
    out["audit"] = (r.returncode == 0 and not flagged, "flag" if flagged else "no flag")
    r = run(py + ["audits/key_balance.py", "--root", root, family])
    out["keys"] = (r.returncode == 0, "PASS" if r.returncode == 0 else "FAIL")
    return out


def main():
    argv = sys.argv[1:]
    seeds, install, do_check = [], None, False
    while "--seed" in argv:
        i = argv.index("--seed")
        seeds.append(int(argv[i + 1]))
        del argv[i:i + 2]
    if "--install" in argv:
        i = argv.index("--install")
        install = os.path.abspath(argv[i + 1])
        del argv[i:i + 2]
    if "--check" in argv:
        do_check = True
        argv.remove("--check")
    bad_args = [a for a in argv if a.startswith("--") or a not in FAMILIES]
    if bad_args:
        sys.exit(f"unknown argument or family: {bad_args}; families: {', '.join(FAMILIES)}")
    fams = argv or (SEEDED if seeds else FAMILIES)
    if seeds and [f for f in fams if f not in SEEDED]:
        sys.exit(f"--seed works only for the families whose generator takes a seed: {', '.join(SEEDED)}")
    if seeds and install:
        sys.exit("--install takes the published seed only")
    index = json.load(open(os.path.join(REPO, "releases", "v1.1", "index.json"), encoding="utf-8"))["tasks"]
    failures = 0
    jobs = [(f, None) for f in fams] if not seeds else [(f, k) for k in seeds for f in fams]
    print(f"{'family':18s} {'seed':>9s} {'seconds':>7s}  {'items':>5s}  {'release 1.1 hash':16s}" + ("  solver     validate audit    keys" if do_check else ""))
    for fam, seed in jobs:
        env = dict(os.environ)
        if seed is None:
            root = os.path.join(REPO, "generated")
            out_dir = os.path.join(root, "tasks", fam)
            env.pop("BENCH_SEED", None)
            env.pop("BENCH_OUT", None)
        else:
            root = os.path.join(REPO, "generated", f"seed_{seed}")
            out_dir = os.path.join(root, "tasks", fam)
            env["BENCH_OUT"] = os.path.join(root, "tasks")
            env["BENCH_SEED"] = str(seed)
        if os.path.isdir(out_dir):
            shutil.rmtree(out_dir)
        log = os.path.join(REPO, "generated", "logs", f"{fam}{'' if seed is None else f'_seed_{seed}'}.log")
        t0 = time.time()
        r = run([sys.executable, "-I", os.path.join("generators", f"{fam}.py")], log=log, env=env)
        secs = time.time() - t0
        items = os.path.join(out_dir, "items.jsonl")
        if r.returncode != 0 or not os.path.isfile(items):
            failures += 1
            print(f"{fam:18s} {seed if seed is not None else 'published':>9} {secs:7.1f}  generator failed (exit {r.returncode}), see {os.path.relpath(log, REPO)}")
            continue
        n = sum(1 for _ in open(items, encoding="utf-8"))
        if seed is None:
            same = sha256_file(items) == index[fam]["items_sha256"]
            hash_txt = "identical" if same else "DIFFERENT"
            failures += not same
        else:
            same, hash_txt = True, "(new draw)"
        row = f"{fam:18s} {seed if seed is not None else 'published':>9} {secs:7.1f}  {n:5d}  {hash_txt:16s}"
        if do_check:
            c = checks(root, fam)
            failures += sum(not ok for ok, _ in c.values())
            row += "  " + "  ".join(f"{txt:9s}" if ok else f"{txt + ' !':9s}" for ok, txt in c.values())
        print(row, flush=True)
        if install and seed is None and same:
            d = os.path.join(install, "tasks", fam)
            os.makedirs(d, exist_ok=True)
            shutil.copyfile(items, os.path.join(d, "items.jsonl"))
            shutil.copyfile(os.path.join(out_dir, "README.md"), os.path.join(d, "README.md"))
            shutil.copyfile(os.path.join(REPO, "releases", "v1.1", "task_cards", f"{fam}.json"), os.path.join(d, "task.json"))
    if install:
        print(f"installed the families with the release hash into {install}/tasks/")
    print("ALL CHECKS PASSED" if not failures else f"{failures} CHECK(S) FAILED")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
