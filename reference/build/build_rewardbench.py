"""Task rewardbench (layer C, public test set): "which of the two responses to the prompt is the better one?"
Built from the `filtered` split of RewardBench (official Hugging Face data set allenai/reward-bench, odc-by): 2,985
rows in 23 subsets, each with a prompt, the `chosen` response and the `rejected` response.
    python3 reference/build/build_rewardbench.py CACHE_DIR      (the download cache, or its folder rewardbench/; needs pyarrow)
The source file is read from the cache (fetched once from the pinned commit if it is missing) and its checksum is
verified, so the output is the same on every run.  No item text is written or edited here."""
import collections
import hashlib
import io
import json
import os
import random
import sys
import urllib.request

import pyarrow.parquet as pq

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "generated", "reference")   # writes HERE/tasks/<task>/
TASK, SOURCE, SEED, ROWS = "rewardbench", "rewardbench", 20261007, 1000
COMMIT = "168d848cdbbea9764fae4a544dc9ca1e6cca4931"   # main, last modified 2024-09-09, read on 2026-10-07
FILES = {"filtered-00000-of-00001.parquet": (
    f"https://huggingface.co/datasets/allenai/reward-bench/resolve/{COMMIT}/data/filtered-00000-of-00001.parquet",
    "65473c20ed0627e02503557ae102c25c6b0e66b5ed69ee327e224bb95e70ca29")}
INSTRUCTIONS = "Which of the two responses to the prompt is the better one?"
CRITERIA = {"A": "Response A is the better one.", "B": "Response B is the better one."}
# licences of the parts as listed on the card (prefix of the subset name -> licence as written there)
PARTS = {"alpacaeval": "CC By NC 4.0", "mt-bench": "Apache 2.0", "llmbar": "MIT License", "donotanswer": "CC BY NC SA 4.0",
         "xstest": "CC By 4.0", "hep": "MIT License", "math-prm": "MIT License", "refusals": "MIT for now"}


def fetch(cache, name):
    """Bytes of one source file from the cache (downloaded once from the pinned official URL), checksum verified."""
    url, sha = FILES[name]
    path = os.path.join(cache, name)
    if not os.path.exists(path):
        os.makedirs(cache, exist_ok=True)
        with urllib.request.urlopen(url, timeout=300) as r, open(path + ".part", "wb") as f:
            f.write(r.read())
        os.replace(path + ".part", path)
    data = open(path, "rb").read()
    if hashlib.sha256(data).hexdigest() != sha:
        sys.exit(f"{path}: checksum differs from the file this task was built from ({url})")
    return data


def dumps(item):
    """One JSON line; the three characters that str.splitlines() takes for line ends are written as JSON escapes."""
    return (json.dumps(item, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
            .replace("\x85", "\\u0085"))


def main():
    cache = os.path.abspath(sys.argv[1])
    cache = cache if os.path.basename(cache) == SOURCE else os.path.join(cache, SOURCE)
    name = "filtered-00000-of-00001.parquet"
    rows = sorted(pq.read_table(io.BytesIO(fetch(cache, name))).to_pylist(), key=lambda r: (r["id"], r["subset"]))
    assert all(r["chosen"] != r["rejected"] for r in rows)
    n_file = len(rows)
    n_llmbar = sum(r["subset"].startswith("llmbar") for r in rows)
    rows = [r for r in rows if not r["subset"].startswith("llmbar")]        # these 419 rows are the task llmbar
    pool = collections.defaultdict(list)
    for r in rows:
        pool[r["subset"]].append(r)
    # proportional shares of ROWS over the subsets (largest remainders; ties by subset name)
    quota = {s: ROWS * len(v) // len(rows) for s, v in pool.items()}
    rest = sorted(pool, key=lambda s: (-(ROWS * len(pool[s]) % len(rows)), s))[:ROWS - sum(quota.values())]
    for s in rest:
        quota[s] += 1
    rng = random.Random(SEED)
    pick = {s: sorted(rng.sample(pool[s], quota[s]), key=lambda r: r["id"]) for s in sorted(pool)}
    items, shown = [], 0
    for s in sorted(pick):
        # position of the chosen response: first in half of the rows, overall and within each subset
        first = [(shown + i) % 2 == 0 for i in range(len(pick[s]))]
        rng.shuffle(first)
        shown += len(pick[s])
        for r, chosen_first in zip(pick[s], first):
            order = ["chosen", "rejected"] if chosen_first else ["rejected", "chosen"]
            items.append({"id": f"{TASK}:{s}:{r['id']}",
                          "state": {"prompt": r["prompt"], "response_A": r[order[0]], "response_B": r[order[1]]},
                          "questions": {"q": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": CRITERIA}},
                          "gold": "A" if chosen_first else "B", "soft": None, "group": None,
                          "meta": {"source_id": str(r["id"]), "subset": s, "chosen_model": r["chosen_model"],
                                   "rejected_model": r["rejected_model"], "order": order}})
    gold = collections.Counter(it["gold"] for it in items)
    part = collections.Counter(next(p for p in PARTS if it["meta"]["subset"].startswith(p)) for it in items)
    assert sum(part.values()) == len(items)
    human = collections.Counter((it["meta"]["chosen_model"] == "human", it["meta"]["rejected_model"] == "human") for it in items)
    tj = {"task": TASK, "layer": "C", "title": "RewardBench: which of two responses is the better one?",
          "decision": "which of two responses to a prompt is the better one (the response the data set marks as chosen)",
          "source": {"name": "RewardBench (RewardBench: Evaluating Reward Models for Language Modeling, arXiv:2403.13787)",
                     "url": "https://huggingface.co/datasets/allenai/reward-bench", "files": ["data/" + name],
                     "split": f"filtered ({n_file:,} rows; {len(rows):,} rows in {len(pool)} subsets after leaving out the llmbar-* subsets)",
                     "version": f"commit {COMMIT} (last modified 2024-09-09), downloaded 2026-10-07"},
          "licence": "odc-by; card: \"We release the RewardBench dataset under ODC-BY requiring the user to follow the "
                     "licenses of the subsequent parts\": AlpacaEval CC By NC 4.0, MT Bench Apache 2.0, LLMBar MIT License, "
                     "Do Not Answer CC BY NC SA 4.0, XSTest CC By 4.0, HumanEvalPack MIT License, PRM Math MIT License; "
                     "refusals data by AI2 \"released as MIT for now\"",
          "redistribution": "rebuild script only",
          "labels": "mixed: per subset the chosen response comes from the stronger model or has the higher rating, is the "
                    "manually curated one, is the refusal or the compliance that is called for, is working code against "
                    "buggy code, or a human reference against a model error; the card reports manual filtering",
          "item_source": "public test set", "metric": "accuracy", "chance": 0.5, "rows": len(items), "groups": None,
          "question_type": "choice", "options": 2,
          "notes": f"The {n_llmbar} rows of the llmbar-* subsets are left out: they are the instances of the task llmbar, "
                   f"with the same preferred output, and would be counted twice. {len(items)} of the remaining {len(rows):,} "
                   "rows, sampled per subset in proportion to its size with "
                   f"random.Random({SEED}) after sorting by id: " + ", ".join(f"{s} {quota[s]}" for s in sorted(quota))
                   + f". Gold A {gold['A']}, B {gold['B']}: the order of the two responses was drawn per row with the same "
                   "generator so that the chosen one is first in half of the rows of each subset; meta.order names the "
                   "source fields shown as response A and B. The id of the file is not unique (3692 occurs in two "
                   "subsets), so item ids carry the subset. Redistribution is set to rebuild script only because the card "
                   "makes the licences of the parts binding and two of them are non-commercial: rows by part in this "
                   "sample — " + ", ".join(f"{p}* {part[p]} ({PARTS[p]})" for p in PARTS if part[p]) + ". The xstest-* "
                   "subsets use the prompts of the task xstest for another decision (which response is better). Responses are "
                   f"model-written or human-written (meta.chosen_model, meta.rejected_model): chosen is `human` in "
                   f"{human[(True, True)] + human[(True, False)]} rows, rejected is `human` in "
                   f"{human[(True, True)] + human[(False, True)]} rows."}
    d = f"{HERE}/tasks/{TASK}"
    os.makedirs(d, exist_ok=True)
    with open(f"{d}/items.jsonl", "w", encoding="utf-8") as f:
        for it in items:
            f.write(dumps(it) + "\n")
    with open(f"{d}/task.json", "w", encoding="utf-8") as f:
        json.dump(tj, f, indent=1, ensure_ascii=False)
        f.write("\n")
    with open(f"{d}/README.md", "w", encoding="utf-8") as f:
        f.write(f"# {TASK}\n\n{tj['title']}\n\n- Decision: {tj['decision']}.\n- Source: {tj['source']['name']}; "
                f"{tj['source']['url']}, file `data/{name}`, {tj['source']['version']}.\n- Licence: odc-by, with the licences "
                f"of the parts binding (two are non-commercial, see `task.json`); {tj['redistribution']}.\n- Rows: "
                f"{len(items)} (gold A {gold['A']}, B {gold['B']}); subset in `meta.subset`; metric: accuracy (chance 0.5).\n"
                f"- Rebuild: `python3 reference/build/build_{TASK}.py CACHE_DIR` (needs pyarrow).\n\nSee `task.json` for the rows per "
                "subset and the licence of each part; the llmbar-* subsets are left out (task llmbar).\n")
    print(TASK, len(items), "rows; gold", dict(gold), "; parts", dict(part))


if __name__ == "__main__":
    main()
