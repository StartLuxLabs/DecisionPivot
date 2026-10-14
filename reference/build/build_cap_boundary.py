"""Tasks cap_boundary_card / cap_boundary_record (layer A, new labels on public inputs): "will this model answer this
question correctly?"  The truth is a probability: the share of 16 or 32 sampled answers of a public chat model that
match the gold answer.  Built from the pilot file written by reference/build/capb_build.py
(questions: evaluation-only sets with gold answers; answering models: Gemma 3 4B / 12B, Phi-4-mini, Phi-4).
    python3 reference/build/build_cap_boundary.py PILOT_ITEMS.jsonl
Samples 1,000 rows per task, balanced over (domain, answering model)."""
import collections
import json
import os
import random
import sys

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "generated", "reference")   # writes HERE/tasks/<task>/
src = sys.argv[1]
rows = [json.loads(l) for l in open(src)]
for form, task, title in (("zero", "cap_boundary_card", "Capability boundary from a model card"),
                          ("shot", "cap_boundary_record", "Capability boundary from a track record")):
    pool = collections.defaultdict(list)
    for r in sorted((r for r in rows if r["form"] == form), key=lambda r: r["id"]):
        pool[(r["domain"], r["model"])].append(r)
    rng = random.Random(20261007)
    per = 1000 // len(pool)
    pick = []
    for k in sorted(pool):
        rng.shuffle(pool[k])
        pick += pool[k][:per]
    d = f"{HERE}/tasks/{task}"
    os.makedirs(d, exist_ok=True)
    with open(f"{d}/items.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(pick, key=lambda r: r["id"]):
            f.write(json.dumps({"id": f"{task}:{r['domain']}:{r['model']}:{r['pid']}", "state": r["state"], "questions": r["questions"],
                                "gold": None, "soft": {"yes": r["rate"], "no": round(1 - r["rate"], 4)}, "group": None,
                                "meta": {"source_id": r["pid"], "domain": r["domain"], "set": r["set"], "answering_model": r["model"],
                                         "n": r["n"], "k": r["k"]}}, ensure_ascii=False) + "\n")
    json.dump({"task": task, "layer": "A", "title": title,
               "decision": "whether a given public chat model will answer a given question correctly (asked before the model is called)",
               "source": {"name": "stored sampled answers of four public chat models on evaluation-only question sets (own runs)",
                          "url": "", "files": [os.path.basename(src)], "split": "evaluation questions of NQ, PopQA, WebQuestions, TriviaQA; "
                          "BBH tasks, StrategyQA, FOLIO, ProofWriter, DROP; SVAMP, ASDiv, GSM-Hard, GSM-Plus, MAWPS", "version": "2026-10-06"},
               "licence": "labels: own; question texts keep the licences of their sources [[to be listed per source]]",
               "redistribution": "rebuild script only", "labels": "programmatic", "item_source": "new labels on public inputs",
               "metric": "mse_soft", "chance": None, "rows": len(pick), "groups": None, "question_type": "choice", "options": 2,
               "notes": "soft.yes = k / n correct among n sampled answers (meta.n, meta.k); "
                        + ("the state holds the model's name and size only" if form == "zero" else
                           "the state also holds eight other questions of the same domain with that model's results")},
              open(f"{d}/task.json", "w"), indent=1)
    open(f"{d}/README.md", "w").write(f"# {task}\n\n{title}. See `task.json`; built by `build/build_cap_boundary.py` from the pilot item file.\n")
    print(task, len(pick), "rows from", len(pool), "cells")
