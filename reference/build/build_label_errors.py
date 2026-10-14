"""Task label_errors (layer F, public test set): is the label that a data set gives to a text correct?
Source: cleanlab/label-errors (Northcutt, Athalye, Mueller 2021), files mturk/{imdb,amazon,20news}_mturk.json: examples that
confident learning flagged as likely label errors, each shown to five Mechanical Turk workers.  The texts are not in the
repository; every annotation names its text file on the project site (labelerrors.com/static/<data set>/<id>.txt), and the
texts are read from there (plain TXT files, no login).
    python3 reference/build/build_label_errors.py CACHE_DIR [--check-imdb]
Reads CACHE_DIR/label_errors/<set>_mturk.json and CACHE_DIR/label_errors/text/<set>/<id>.txt; missing files are downloaded
(annotations from the pinned commit); SHA-256 values are checked, for the texts as one digest over all 2,403 files.
Gold: yes if at least 3 of the 5 workers chose the given label (the paper's "non-error"), no otherwise (the paper's "error").
Dropped: 20news rows in which the votes for "both labels apply" decide the outcome, and texts longer than 20,000 characters.
Sample: equal numbers of yes and no from every (data set, given label) cell, with one cap per cell and class, the largest
that keeps the task at 500 rows per class or fewer; random.Random(20261007) after sorting by source id.  Texts are copied as
they are; only leading and trailing whitespace is removed.
--check-imdb (needs pyarrow and CACHE_DIR/imdb_hf/plain_text_test.parquet, the test split of Hugging Face stanfordnlp/imdb)
compares the IMDB texts with that official copy and changes no output."""
import collections
import concurrent.futures
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.request

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "generated", "reference")   # writes HERE/tasks/<task>/
TASK = "label_errors"
COMMIT = "6d5d6b31a13216290afc40e5c6319399c4d15c06"
REPO = f"https://raw.githubusercontent.com/cleanlab/label-errors/{COMMIT}/mturk/"
SITE = "https://labelerrors.com/static/"
SETS = {"imdb": ("imdb_mturk.json", "80c15f04208276a4433b8f3d76405203487e38e95397709f762133fa10e82486"),
        "amazon": ("amazon_mturk.json", "24ddaa631c9b57dcfff0992a22ebfa497939f65b8c12e3facd7f37d431855946"),
        "20news": ("20news_mturk.json", "0f14cda08aedfa79e883aaf6db43adfbf91b4affd5947cd832b7ccfb2d4dafc4")}
TEXTS_SHA256 = "4071af763c26e691261e909e78dcb80f495a4da94b0672c16423a24c52b82d68"
ID_SHAPE = {"imdb": r"test/(neg|pos)/\d+_\d+", "amazon": r"\d+", "20news": r"\d+"}  # only ids of these shapes are fetched
MAX_CHARS = 20000
PER_CLASS = 500
QUESTION = {"type": "choice", "instructions": "Is the given label correct for this text?",
            "criteria": {"yes": "The given label is correct.", "no": "The given label is wrong."}}


def get(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "bench-v0-build"}), timeout=120) as r:
                return r.read()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


def fetch(url, path, sha256=None):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = get(url)
        with open(path + ".part", "wb") as f:
            f.write(data)
        os.replace(path + ".part", path)
    data = open(path, "rb").read()
    if sha256 and hashlib.sha256(data).hexdigest() != sha256:
        sys.exit(f"{path}: SHA-256 differs from the file this task was built from")
    return data


def dump(obj):  # one JSON line; the three line-separator characters that json leaves raw are escaped
    return json.dumps(obj, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029").replace("\x85", "\\u0085") + "\n"


cache = f"{sys.argv[1]}/label_errors"
rows = []
for ds, (name, sha) in SETS.items():
    for x in sorted(json.loads(fetch(REPO + name, f"{cache}/{name}", sha)), key=lambda x: x["id"]):
        sid, m = str(x["id"]), x["mturk"]
        assert re.fullmatch(ID_SHAPE[ds], sid) and sum(m.values()) == 5, (ds, sid)
        given, guessed = (x["given_original_label_name"], x["our_guessed_label_name"]) if ds == "20news" else (x["given_original_label"], x["our_guessed_label"])
        rows.append({"ds": ds, "sid": sid, "given": given, "guessed": guessed, "votes": m,
                     "support": m[given.lower()] if ds == "amazon" else m["given"],  # workers who chose the given label
                     "both": m.get("both", 0), "url": f"{SITE}{ds}/{sid}.txt", "path": f"{cache}/text/{ds}/{sid}.txt"})
with concurrent.futures.ThreadPoolExecutor(8) as ex:
    blobs = list(ex.map(lambda r: fetch(r["url"], r["path"]), rows))
digest = hashlib.sha256()
for r, b in sorted(zip(rows, blobs), key=lambda rb: (rb[0]["ds"], rb[0]["sid"])):
    digest.update(f"{r['ds']}/{r['sid']}\n".encode() + hashlib.sha256(b).digest())
    r["text"] = b.decode("utf-8")
if digest.hexdigest() != TEXTS_SHA256:
    sys.exit(f"the text files differ from the ones this task was built from (digest {digest.hexdigest()})")

if "--check-imdb" in sys.argv:
    import pyarrow.parquet as pq
    official = collections.defaultdict(set)
    for o in pq.read_table(f"{sys.argv[1]}/imdb_hf/plain_text_test.parquet").to_pylist():
        official[o["text"]].add(("Negative", "Positive")[o["label"]])
    imdb = [r for r in rows if r["ds"] == "imdb"]
    print("IMDB texts identical to a row of stanfordnlp/imdb test with the same label:",
          sum(official.get(r["text"]) == {r["given"]} for r in imdb), "of", len(imdb))

labels = {ds: sorted({r[k] for r in rows if r["ds"] == ds for k in ("given", "guessed")}) for ds in SETS}
pool, dropped, full = collections.defaultdict(lambda: {"yes": [], "no": []}), collections.Counter(), collections.Counter()
for r in rows:  # rows are in source id order within each data set
    r["gold"] = "yes" if r["support"] >= 3 else "no"
    if r["gold"] == "no" and r["support"] + r["both"] >= 3:
        dropped["both"] += 1
    elif len(r["text"]) > MAX_CHARS:
        dropped["long"] += 1
    else:
        pool[(r["ds"], r["given"])][r["gold"]].append(r)
        full[(r["ds"], r["gold"])] += 1
size = {c: min(len(v["yes"]), len(v["no"])) for c, v in pool.items()}
cap = max(c for c in range(1, PER_CLASS + 1) if sum(min(s, c) for s in size.values()) <= PER_CLASS)
rng = random.Random(20261007)
pick = []
for cell in sorted(pool):
    for g in ("no", "yes"):
        rng.shuffle(pool[cell][g])
        pick += pool[cell][g][:min(size[cell], cap)]
pick.sort(key=lambda r: (r["ds"], int(r["sid"]) if r["sid"].isdigit() else r["sid"]))

d = f"{HERE}/tasks/{TASK}"
os.makedirs(d, exist_ok=True)
with open(f"{d}/items.jsonl", "w", encoding="utf-8") as f:
    for r in pick:
        f.write(dump({"id": f"{TASK}:{r['ds']}/{r['sid']}",
                      "state": {"text": r["text"].strip(), "given_label": r["given"], "possible_labels": labels[r["ds"]]},
                      "questions": {"q": QUESTION}, "gold": r["gold"], "soft": None, "group": None,
                      "meta": {"source_id": f"{r['ds']}/{r['sid']}", "data_set": r["ds"], "guessed_label": r["guessed"],
                               "votes": r["votes"], "votes_for_given": r["support"]}}))
n = collections.Counter(r["gold"] for r in pick)
by = collections.Counter((r["ds"], r["gold"]) for r in pick)
close = sum(r["support"] in (2, 3) for r in pick)
title = "Label errors in text data sets"
json.dump({"task": TASK, "layer": "F", "title": title,
           "decision": "whether the label that a public data set gives to a text is correct, as judged by five crowd workers",
           "source": {"name": "cleanlab/label-errors, Mechanical Turk study: Northcutt, Athalye, Mueller, Pervasive Label Errors in Test Sets "
                              "Destabilize Machine Learning Benchmarks (NeurIPS 2021 Datasets and Benchmarks), arXiv:2103.14749",
                      "url": "https://github.com/cleanlab/label-errors",
                      "files": [REPO + name for name, _ in SETS.values()] + [f"{SITE}{{imdb,amazon,20news}}/<id>.txt ({len(rows):,} text files, one per annotation)"],
                      "sha256": dict({name: sha for name, sha in SETS.values()}, texts=TEXTS_SHA256),
                      "split": "examples flagged by confident learning in the IMDB test set (1,310 annotated), the 20 Newsgroups test set (93) "
                               "and the Amazon Reviews set, which has no test split (1,000)",
                      "version": f"annotations: commit {COMMIT} (2025-12-16); texts: labelerrors.com, files dated 2020-12-09, downloaded 2026-10-07"},
           "licence": "annotations: \"Apache License 2.0\" (repository file LICENSE); the texts are IMDB reviews, Amazon reviews and 20 Newsgroups "
                      "posts and keep the terms of those sources, which the repository does not state",
           "redistribution": "rebuild script only", "labels": "human", "item_source": "public test set",
           "metric": "accuracy", "chance": 0.5, "rows": len(pick), "groups": None, "question_type": "choice", "options": 2,
           "notes": f"{n['yes']} yes + {n['no']} no: " + "; ".join(f"{ds} {by[(ds, 'yes')]} + {by[(ds, 'no')]}" for ds in SETS) + ". "
                    "yes = at least 3 of the 5 workers chose the given label (the paper's non-errors), no = fewer than 3 did (the paper's errors: "
                    "the workers chose the label guessed by confident learning, neutral, off-topic or neither label, and need not agree with one "
                    "another). Rows before sampling (yes / no): " + "; ".join(f"{ds} {full[(ds, 'yes')]} / {full[(ds, 'no')]}" for ds in SETS) + ". "
                    f"Dropped: {dropped['both']} 20news rows in which votes for \"both labels apply\" decide the outcome (the paper counts them as "
                    f"errors), {dropped['long']} texts over {MAX_CHARS:,} characters. Sampling: equal numbers of yes and no in every (data set, given "
                    f"label) cell, at most {cap} per cell and class, so that neither the data set nor the given label predicts the answer. "
                    f"{close} of the {len(pick)} rows rest on a 3-to-2 vote (meta.votes, meta.votes_for_given). All rows were first flagged by "
                    "confident learning as likely label errors: a hard, selected subset, not a sample of the data sets. state.possible_labels lists "
                    "the label names that occur in the annotation file of the data set. Texts unchanged except leading/trailing whitespace: IMDB "
                    "reviews keep their <br /> tags, 20 Newsgroups posts keep their headers with the senders' names and e-mail addresses. The "
                    "1,310 IMDB texts are identical to rows of the test split of Hugging Face stanfordnlp/imdb with the same label (checked "
                    "2026-10-07, option --check-imdb); the Amazon and 20 Newsgroups texts were not compared with another copy."},
          open(f"{d}/task.json", "w"), indent=1)
open(f"{d}/README.md", "w").write(
    f"# {TASK}\n\n{title} (layer F): is the label that the data set gives to this text correct?\n\n"
    "- Source: cleanlab/label-errors, <https://github.com/cleanlab/label-errors>, files `mturk/{imdb,amazon,20news}_mturk.json`, commit "
    f"`{COMMIT[:12]}` (licence \"Apache License 2.0\"); texts from <https://labelerrors.com> (`static/<data set>/<id>.txt`), which keep the terms "
    "of IMDB, Amazon Reviews and 20 Newsgroups.\n"
    f"- Rows: {len(pick):,} ({n['yes']} yes = at least 3 of 5 workers confirm the given label, {n['no']} no); "
    + ", ".join(f"{ds} {by[(ds, 'yes')] + by[(ds, 'no')]}" for ds in SETS) + "; metric accuracy, chance 0.5.\n"
    f"- Rebuild: `python3 reference/build/build_{TASK}.py CACHE_DIR` (downloads the three annotation files and {len(rows):,} text files into "
    "`CACHE_DIR/label_errors/` if they are missing).\n"
    "- The items are not for redistribution (rebuild script only).\n\n"
    "See `task.json` for the notes on the gold rule, the sampling and what was dropped.\n")
print(TASK, len(pick), "rows", dict(n), "| per set", dict(by), "| cap", cap, "| dropped", dict(dropped))
