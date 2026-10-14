"""Task paws (layer G, public test set): "do the two sentences have the same meaning?"

Source: PAWS, configuration labeled_final (PAWS-Wiki Labeled (Final)), test split, 8,000 pairs with human paraphrase
judgments (label 1 = paraphrase).  Official card: https://huggingface.co/datasets/google-research-datasets/paws
    python3 reference/build/build_paws.py CACHE_DIR
CACHE_DIR is the download cache; the parquet file is read from CACHE_DIR/paws/ and fetched from the pinned commit if
it is missing (SHA-256 checked).  Needs pyarrow.  500 paraphrase + 500 non-paraphrase pairs, sampled with
random.Random(20261007) after sorting by the source id."""
import hashlib
import json
import os
import random
import sys
import urllib.request

import pyarrow.parquet as pq

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "generated", "reference")   # writes HERE/tasks/<task>/
SEED = 20261007
TASK = "paws"
SOURCE = "paws"
COMMIT = "161ece9501cf0a11f3e48bd356eaa82de46d6a09"
FILE = "labeled_final/test-00000-of-00001.parquet"
URL = f"https://huggingface.co/datasets/google-research-datasets/paws/resolve/{COMMIT}/{FILE}"
SHA256 = "ae342ff12bb84b84b95f468abf5db6cb7c7bd578271299fe9c99be75b8132f4d"
PER_CLASS = 500
QUESTION = {"type": "choice", "instructions": "Do the two sentences have the same meaning?",
            "criteria": {"yes": "The two sentences have the same meaning.",
                         "no": "The two sentences have different meanings."}}
LICENCE = ('tag "other"; card text: "The dataset may be freely used for any purpose, although acknowledgement of '
           'Google LLC ("Google") as the data source would be appreciated. The dataset is provided "AS IS" without any '
           'warranty, express or implied."')


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


def main():
    cache = sys.argv[1].rstrip("/")
    if os.path.basename(cache) == SOURCE:
        cache = os.path.dirname(cache)
    rows = pq.read_table(fetch(cache, f"{SOURCE}/{FILE}", URL, SHA256)).to_pylist()
    rows.sort(key=lambda r: r["id"])
    assert len(rows) == 8000 and len({r["id"] for r in rows}) == 8000 and {r["label"] for r in rows} == {0, 1}
    total = {lab: sum(r["label"] == lab for r in rows) for lab in (1, 0)}
    rng = random.Random(SEED)
    pick = []
    for lab in (1, 0):                                   # paraphrases first, then non-paraphrases
        pick += rng.sample([r for r in rows if r["label"] == lab], PER_CLASS)
    pick.sort(key=lambda r: r["id"])
    items = [{"id": f"{TASK}:{r['id']}", "state": {"sentence1": r["sentence1"], "sentence2": r["sentence2"]},
              "questions": {"q": QUESTION}, "gold": "yes" if r["label"] == 1 else "no", "soft": None, "group": None,
              "meta": {"source_id": r["id"], "label": r["label"]}} for r in pick]
    d = f"{HERE}/tasks/{TASK}"
    os.makedirs(d, exist_ok=True)
    with open(f"{d}/items.jsonl", "w", encoding="utf-8") as f:
        for it in items:
            f.write(dump(it) + "\n")
    n_yes = sum(it["gold"] == "yes" for it in items)
    notes = (f"{n_yes} yes + {len(items) - n_yes} no, sampled per class (seed {SEED}) from the 8,000 test pairs "
             f"({total[1]} paraphrases, {total[0]} non-paraphrases); gold yes = source label 1. The pairs were generated "
             "by word swapping and back-translation and judged by human raters; the sentences keep the tokenised form "
             "of the source (spaces before punctuation). Licence: custom text, not one of the standard licences, hence "
             "kept as rebuild script only although the text allows free use for any purpose. The training split of the "
             "same configuration (49,401 pairs) is public: a model trained on it is in-domain.")
    tj = {"task": TASK, "layer": "G", "title": "PAWS paraphrase pairs (PAWS-Wiki, labeled_final test)",
          "decision": "whether two sentences with nearly the same words have the same meaning",
          "source": {"name": "PAWS: Paraphrase Adversaries from Word Scrambling (arXiv:1904.01130)",
                     "url": "https://huggingface.co/datasets/google-research-datasets/paws", "files": [FILE],
                     "split": "labeled_final / test (8,000 pairs)", "version": f"commit {COMMIT} (2024-01-04)"},
          "licence": LICENCE, "redistribution": "rebuild script only", "labels": "human",
          "item_source": "public test set", "metric": "accuracy", "chance": 0.5, "rows": len(items), "groups": None,
          "question_type": "choice", "options": 2, "notes": notes}
    json.dump(tj, open(f"{d}/task.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    open(f"{d}/README.md", "w", encoding="utf-8").write(
        f"# {TASK}\n\n{tj['title']}. Decision: {tj['decision']}.\n\n"
        f"- Source: {tj['source']['url']}, file `{FILE}`, {tj['source']['version']}.\n"
        f"- Rows: {len(items)} ({n_yes} yes, {len(items) - n_yes} no); metric: accuracy (chance 0.5).\n"
        f"- Licence: {LICENCE}. Redistribution: rebuild script only.\n"
        f"- Rebuild: `python3 reference/build/build_{TASK}.py CACHE_DIR` (fetches the file if it is missing, checks SHA-256).\n\n"
        f"{notes}\n")
    print(TASK, len(items), "rows;", n_yes, "yes,", len(items) - n_yes, "no")


if __name__ == "__main__":
    main()
