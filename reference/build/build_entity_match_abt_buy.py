"""Tasks entity_match_abt_buy / entity_match_amazon_google (layer G, public test sets): "do the two product records
describe the same product?"

Source: the DeepMatcher versions of Abt-Buy and Amazon-Google (labelled candidate pairs with a fixed 3:1:1 split),
listed in https://github.com/anhaidgroup/deepmatcher/blob/master/Datasets.md; the records come from the Leipzig
benchmark page https://dbs.uni-leipzig.de/research/projects/benchmark-datasets-for-entity-resolution
    python3 reference/build/build_entity_match_abt_buy.py CACHE_DIR
    python3 reference/build/build_entity_match_amazon_google.py CACHE_DIR      (imports build() from this file)
CACHE_DIR is the download cache; the zip archive is read from CACHE_DIR/deepmatcher/ and fetched if it is missing
(SHA-256 checked).  Test split, natural class ratio: 1,000 pairs, matches and non-matches drawn in the proportion of
the test split with random.Random(20261007) after sorting by the source ids."""
import csv
import hashlib
import io
import json
import os
import random
import sys
import urllib.request
import zipfile

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "generated", "reference")   # writes HERE/tasks/<task>/
SEED = 20261007
SOURCE = "deepmatcher"
DATASETS_MD = "a89ffe6cd246f690afd2772e47eb071741160f16"     # commit of Datasets.md that lists the archives
BASE = "http://pages.cs.wisc.edu/~anhai/data1/deepmatcher_data"
SETS = {
    "abt_buy": {"name": "Abt-Buy", "zip": "abt_buy_exp_data.zip", "url": f"{BASE}/Textual/Abt-Buy/abt_buy_exp_data.zip",
                "sha256": "cd806d925aca21e6ab942b239353a10ee88904c59d3d3e3da6a74e364e9200a1", "prefix": "exp_data/",
                "kind": "textual", "pairs": 1916, "extra": ""},
    "amazon_google": {"name": "Amazon-Google", "zip": "amazon_google_exp_data.zip",
                      "url": f"{BASE}/Structured/Amazon-Google/amazon_google_exp_data.zip",
                      "sha256": "9b19c85c98c6289f38969e4961cb944bdf986123fc42f6bf17283ac6eb502e61", "prefix": "",
                      "kind": "structured", "pairs": 2293,
                      "extra": " This is the structured version: DeepMatcher removed the long description attribute "
                               "of the original records."},
}
ROWS = 1000
QUESTION = {"type": "choice", "instructions": "Do the two records describe the same product?",
            "criteria": {"yes": "The two records describe the same product.",
                         "no": "The two records describe different products."}}
LICENCE = ('DeepMatcher Datasets.md: no licence stated for the data (repository code: BSD 3-Clause); origin of the '
           'records, Leipzig benchmark page: "These datasets are made available by the database group of Prof. Erhard '
           'Rahm under the Creative Commons license" (link target: https://creativecommons.org/licenses/by/4.0/)')


def fetch(cache, rel, url, sha256):
    """Path of a source file in the cache; downloaded from the pinned URL if missing; SHA-256 checked."""
    path = os.path.join(cache, rel)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with urllib.request.urlopen(url, timeout=300) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
    got = hashlib.sha256(open(path, "rb").read()).hexdigest()
    assert got == sha256, f"{path}: sha256 {got}, expected {sha256}"
    return path


def dump(obj):
    """One JSON line; the three Unicode line separators are escaped so that no reader splits a row."""
    return (json.dumps(obj, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
            .replace("\u0085", "\\u0085"))


def build(key, cache):
    s = SETS[key]
    task = f"entity_match_{key}"
    cache = cache.rstrip("/")
    if os.path.basename(cache) == SOURCE:
        cache = os.path.dirname(cache)
    zf = zipfile.ZipFile(fetch(cache, f"{SOURCE}/{s['zip']}", s["url"], s["sha256"]))

    def table(name):
        return list(csv.DictReader(io.StringIO(zf.read(s["prefix"] + name).decode("utf-8"), newline="")))

    left = {r["id"]: r for r in table("tableA.csv")}
    right = {r["id"]: r for r in table("tableB.csv")}
    test = sorted(table("test.csv"), key=lambda r: (int(r["ltable_id"]), int(r["rtable_id"])))
    assert len(test) == s["pairs"] and {r["label"] for r in test} == {"0", "1"}
    assert len({(r["ltable_id"], r["rtable_id"]) for r in test}) == len(test)
    n_match = sum(r["label"] == "1" for r in test)
    want = {"1": round(ROWS * n_match / len(test))}
    want["0"] = ROWS - want["1"]
    rng = random.Random(SEED)
    pick = []
    for lab in ("1", "0"):                                # matches first, then non-matches
        pick += rng.sample([r for r in test if r["label"] == lab], want[lab])
    pick.sort(key=lambda r: (int(r["ltable_id"]), int(r["rtable_id"])))
    items = []
    for r in pick:
        a, b = left[r["ltable_id"]], right[r["rtable_id"]]
        sid = f"{r['ltable_id']}-{r['rtable_id']}"
        items.append({"id": f"{task}:{sid}",
                      "state": {"record_a": {k: v for k, v in a.items() if k != "id"},
                                "record_b": {k: v for k, v in b.items() if k != "id"}},
                      "questions": {"q": QUESTION}, "gold": "yes" if r["label"] == "1" else "no", "soft": None,
                      "group": None,
                      "meta": {"source_id": sid, "ltable_id": r["ltable_id"], "rtable_id": r["rtable_id"],
                               "label": int(r["label"])}})
    fields = [k for k in next(iter(left.values())) if k != "id"]
    d = f"{HERE}/tasks/{task}"
    os.makedirs(d, exist_ok=True)
    with open(f"{d}/items.jsonl", "w", encoding="utf-8") as f:
        for it in items:
            f.write(dump(it) + "\n")
    notes = (f"{want['1']} matches + {want['0']} non-matches: the class ratio of the test split ({n_match} matches in "
             f"{len(test):,} pairs), drawn per class (seed {SEED}). record_a is the row of tableA.csv (left), record_b "
             f"the row of tableB.csv (right), fields {', '.join(fields)}; values are the preprocessed (lower-cased, "
             "tokenised) strings of the DeepMatcher files, empty where the source is empty." + s["extra"]
             + " The pairs are candidates that survived DeepMatcher's blocking; a pair is a match if it is in the "
             "reference mapping of the original authors, otherwise a non-match. The split is DeepMatcher's random "
             "3:1:1 split of the pairs, so the same records also occur in the public training and validation pairs. "
             "Licence: the origin (Leipzig) is under CC BY 4.0, the DeepMatcher files state none: kept as rebuild "
             "script only.")
    tj = {"task": task, "layer": "G", "title": f"{s['name']} product matching (DeepMatcher test split)",
          "decision": "whether two product records from two shops describe the same product",
          "source": {"name": f"{s['name']} (Köpcke, Thor, Rahm, VLDB 2010) in the {s['kind']} version and split of "
                             "DeepMatcher (Mudgal et al., SIGMOD 2018)",
                     "url": "https://github.com/anhaidgroup/deepmatcher/blob/master/Datasets.md",
                     "files": [f"{s['url']} (sha256 {s['sha256']}): {s['prefix']}test.csv, {s['prefix']}tableA.csv, "
                               f"{s['prefix']}tableB.csv"],
                     "split": f"test ({len(test):,} labelled pairs, {n_match} matches)",
                     "version": f"archive files dated 2018-06-04; Datasets.md at commit {DATASETS_MD}"},
          "licence": LICENCE, "redistribution": "rebuild script only",
          "labels": "mixed: matches from the reference mapping of the original authors; non-matches are blocked "
                    "candidate pairs that are not in the mapping",
          "item_source": "public test set", "metric": "auroc", "chance": 0.5, "rows": len(items), "groups": None,
          "question_type": "choice", "options": 2, "notes": notes}
    json.dump(tj, open(f"{d}/task.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    open(f"{d}/README.md", "w", encoding="utf-8").write(
        f"# {task}\n\n{tj['title']}. Decision: {tj['decision']}.\n\n"
        f"- Source: {tj['source']['url']}, archive `{s['zip']}` ({s['url']}), sha256 `{s['sha256']}`.\n"
        f"- Rows: {len(items)} ({want['1']} yes, {want['0']} no; natural class ratio); metric: auroc (chance 0.5).\n"
        f"- Licence: {LICENCE}. Redistribution: rebuild script only.\n"
        f"- Rebuild: `python3 reference/build/build_{task}.py CACHE_DIR` (fetches the archive if it is missing, checks "
        f"SHA-256).\n\n{notes}\n")
    print(task, len(items), "rows;", want["1"], "yes,", want["0"], "no; test split", len(test), "pairs,", n_match,
          "matches")


if __name__ == "__main__":
    build("abt_buy", sys.argv[1])
