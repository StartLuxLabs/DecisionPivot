"""Task freshqa_premise (layer A, public test set): does a question rest on a false premise?
Source: FreshQA (Vu et al. 2023), GitHub freshllms/freshqa.  The repository holds no data file; its README links one Google
Sheet per dated snapshot.  Used: the sheet "FreshQA April 21, 2026" (the latest one listed), tab `freshqa`, exported as CSV
without a login.  The label is the column `false_premise` of the rows with split TEST.
    python3 reference/build/build_freshqa_premise.py CACHE_DIR
Reads CACHE_DIR/freshqa/FreshQA_v042126-freshqa.csv; a missing file is downloaded from the export address of that sheet; the
SHA-256 is checked (a changed sheet stops the build).  Source id = column `id`.  All TEST rows are kept (classes as they are,
no sampling).  Question texts are copied as they are; only leading and trailing whitespace is removed."""
import collections
import csv
import hashlib
import io
import json
import os
import sys
import urllib.request

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "generated", "reference")   # writes HERE/tasks/<task>/
TASK = "freshqa_premise"
REPO_COMMIT = "7d2d3683991916f3633e480548a6aa5c9a62e3db"  # README that lists the sheet
SHEET = "https://docs.google.com/spreadsheets/d/1_8mi-yuK30mvoDJu1KQXD6ODem7MKMcIgVAwDSzJkjM"
URL = f"{SHEET}/export?format=csv&gid=334049794"  # tab `freshqa`
FILE = "FreshQA_v042126-freshqa.csv"  # the name the export gives the file
SHA256 = "3769244f66bb2666fe5160c8cc235339b7c54c61fc88d360995aa91d4c904789"
QUESTION = {"type": "choice", "instructions": "As of 21 April 2026, does this question rest on a false premise?",
            "criteria": {"yes": "The question rests on a false premise.", "no": "The question does not rest on a false premise."}}


def fetch(url, path, sha256):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "bench-v0-build"}), timeout=120) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
    data = open(path, "rb").read()
    if hashlib.sha256(data).hexdigest() != sha256:
        sys.exit(f"{path}: SHA-256 differs from the file this task was built from")
    return data


def dump(obj):  # one JSON line; the three line-separator characters that json leaves raw are escaped
    return json.dumps(obj, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029").replace("\x85", "\\u0085") + "\n"


cache = sys.argv[1]
table = list(csv.reader(io.StringIO(fetch(URL, f"{cache}/freshqa/{FILE}", SHA256).decode("utf-8"), newline="")))
head = next(i for i, row in enumerate(table) if row[:3] == ["id", "split", "question"])  # two rows of notes come first
notice = " ".join(c for row in table[:head] for c in row if c.strip())
rows = [dict(zip(table[head], row)) for row in table[head + 1:]]
splits = collections.Counter(r["split"] for r in rows)
test = sorted((r for r in rows if r["split"] == "TEST"), key=lambda r: int(r["id"]))
assert len({r["id"] for r in rows}) == len(rows) and all(r["false_premise"] in ("TRUE", "FALSE") for r in rows)
assert len({" ".join(r["question"].lower().split()) for r in test}) == len(test)
gold = {"TRUE": "yes", "FALSE": "no"}

d = f"{HERE}/tasks/{TASK}"
os.makedirs(d, exist_ok=True)
with open(f"{d}/items.jsonl", "w", encoding="utf-8") as f:
    for r in test:
        f.write(dump({"id": f"{TASK}:{r['id']}", "state": {"question": r["question"].strip()}, "questions": {"q": QUESTION},
                      "gold": gold[r["false_premise"]], "soft": None, "group": None,
                      "meta": {"source_id": r["id"], "fact_type": r["fact_type"], "num_hops": r["num_hops"],
                               "effective_year": r["effective_year"]}}))
n = collections.Counter(gold[r["false_premise"]] for r in test)
fact = collections.Counter(r["fact_type"] for r in test if r["false_premise"] == "TRUE")
stripped = sum(r["question"] != r["question"].strip() for r in test)
title = "Question with a false premise"
json.dump({"task": TASK, "layer": "A", "title": title,
           "decision": "whether a question rests on a false premise, judged from the question alone at the date of the snapshot",
           "source": {"name": "FreshQA: Vu et al., FreshLLMs: Refreshing Large Language Models with Search Engine Augmentation (2023), arXiv:2310.03214",
                      "url": "https://github.com/freshllms/freshqa", "files": [URL], "sha256": {FILE: SHA256},
                      "split": f"TEST ({splits['TEST']} of {len(rows)} questions; the other {splits['DEV']} are DEV)",
                      "version": f"sheet \"FreshQA April 21, 2026\" (file name {FILE}), linked from the README at commit {REPO_COMMIT} "
                                 "(2026-05-01); exported 2026-10-07"},
           "licence": "repository \"Apache License 2.0\" (file LICENSE); the question sheet is a Google Sheet linked from the README and "
                      "carries no licence statement of its own",
           "redistribution": "rebuild script only", "labels": "human", "item_source": "public test set",
           "metric": "auroc", "chance": 0.5, "rows": len(test), "groups": None, "question_type": "choice", "options": 2,
           "notes": f"Classes as they are: {n['yes']} yes (false_premise TRUE) + {n['no']} no (FALSE); no sampling. The flag describes the "
                    "world at the date of the snapshot, so the question sentence names that date; the authors revise questions, flags and "
                    "answers, and other snapshots differ (false-premise questions by fact_type in this one: "
                    f"{', '.join(f'{k} {v}' for k, v in sorted(fact.items()))}; meta keeps fact_type, num_hops, effective_year). "
                    "Redistribution is set to the rebuild script because the Apache licence is stated for the repository and the questions "
                    "are not in the repository. The file opens with a notice of the authors: \"" + notice + "\" "
                    f"Text unchanged except leading/trailing whitespace ({stripped} rows)."},
          open(f"{d}/task.json", "w"), indent=1)
open(f"{d}/README.md", "w").write(
    f"# {TASK}\n\n{title} (layer A): as of 21 April 2026, does the question rest on a false premise?\n\n"
    f"- Source: FreshQA, <https://github.com/freshllms/freshqa>; the README links the Google Sheet \"FreshQA April 21, 2026\", whose tab "
    f"`freshqa` is exported as `{FILE}`; repository licence \"Apache License 2.0\", none stated on the sheet.\n"
    f"- Rows: {len(test):,} (all TEST questions: {n['yes']} yes = false premise, {n['no']} no); metric AUROC, chance 0.5.\n"
    f"- Rebuild: `python3 reference/build/build_{TASK}.py CACHE_DIR` (exports the sheet into `CACHE_DIR/freshqa/` if the file is missing; no login).\n"
    "- The items are not for redistribution (rebuild script only).\n\n"
    "See `task.json` for the notes on the snapshot date and the authors' notice.\n")
print(TASK, len(test), "rows", dict(n), "| splits", dict(splits))
