"""Task faithbench (layer C, public test set): "is the summary faithful to the source text?"
Built from the released batches of FaithBench (GitHub vectara/FaithBench; LICENSE: Attribution-NonCommercial-ShareAlike 4.0
International): 750 summaries (50 per batch, batches 1-12 and 14-16; the README lists no batch 13) written by ten LLMs for
short source texts and annotated by human experts at span level.
    python3 reference/build/build_faithbench.py CACHE_DIR      (the download cache, or its folder faithbench/)
Files: data_for_release/batch_<n>.json (the data the README names; fetched once from the pinned commit if missing, SHA-256
verified) and FaithBench.csv (used only to report how many of the summaries have a dissenting annotator; see the notes).  The
repository's scripts are not downloaded or run.
Label rule.  The README gives the taxonomy Consistent (no annotations needed) / Questionable / Hallucinated (Unwanted: intrinsic
or extrinsic; Benign) and says only that scripts/binarize.py aggregates the annotations to sample-level labels (the script is
not usable as a rule: it returns 0 both for a summary without annotations and for a hallucinated one).  Only summaries that are
clearly one or the other are used:
  yes (faithful): the summary has no annotation at all (README: Consistent = no annotations needed);
  no (hallucination): at least two different annotators left annotations and every one of them has at least one span labelled
    Unwanted (intrinsic or extrinsic) on the summary, i.e. all experts who marked the summary call a hallucination unwanted.
Everything in between (only Benign or Questionable spans, one annotator only, annotators that disagree) is dropped and counted.
The files do not say how many experts looked at a summary: an expert who finds nothing leaves no annotation, so "the majority of the
experts" cannot be computed; the rule above is the part of it that the files allow (unanimity of the annotators on record).
Sampling.  Summaries are sorted by batch and sample id.  The classes differ in length, so the sample is length-matched on the
summary: buckets of 100 characters (below 2,000), the same number of summaries from both classes in every bucket, all matched
pairs (random.Random(20261007), buckets in order).  The final row order is shuffled with the same generator.
state = {source, summary} as given; meta keeps the summarising model and the batch."""
import collections
import csv
import hashlib
import io
import json
import os
import random
import sys
import urllib.request

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "generated", "reference")   # writes HERE/tasks/<task>/
TASK, SOURCE, SEED = "faithbench", "faithbench", 20261007
REPO = "vectara/FaithBench"
COMMIT, COMMIT_DATE = "cf89797d82812c23b5d5e5c121f1d9b8983bbbce", "2025-05-12"      # main, read on 2026-10-07
BATCHES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16]
FILES = {"data_for_release/batch_1.json": "a4e7858702e741b0fb024a022a906f61fb8eb65011b7f7b138e56e080a4c8c59",
         "data_for_release/batch_2.json": "18f1b2b9eae6fbf2020f295dc5ca512ef1a7e389e763b707bc51831f58df6a70",
         "data_for_release/batch_3.json": "84b709a9d88998f478f429ee2330ea18666ae9e5340ea398ece03cec6ab54308",
         "data_for_release/batch_4.json": "c0f68bc222dd8b6e332cb6668840de8da150687ddf6f9b5bd243f389033fda42",
         "data_for_release/batch_5.json": "6be08bb37ccdf68e41e117b0174cc3c8b41ed7bf85134d00e0e89c023e96b436",
         "data_for_release/batch_6.json": "a5fd42aa64fbe15f535192ddfd3cfc72b53535cde7834cb6685ebe0a229f8587",
         "data_for_release/batch_7.json": "28e83e1487381ce317103505dab4d5679ad74f53541374a98e24e3673734343b",
         "data_for_release/batch_8.json": "5cf2b8ab42fe1d4b0018cf736448dd8a88318267b0efc2f45ea200e713932975",
         "data_for_release/batch_9.json": "4924fe2d0975890712032a128544c0619c2ebf81d5d472e99e7883f1a9720bd5",
         "data_for_release/batch_10.json": "8e5cec822516abbf74cd6796104bbe537da98628c671b64c10afa3b15bebe08c",
         "data_for_release/batch_11.json": "cf999c8fa9696f4b24d8f4b08f9fdd6603a942cfee63ad851ff6d1f265c116cc",
         "data_for_release/batch_12.json": "fda9f0e0eae69c13b79a8fc1f81d1f8a02e9f28ad8c3274619c4369bb15c818e",
         "data_for_release/batch_14.json": "72f07b9f4b91f8a49d96e7adc79a8308edb92a2e6b34babcd9ef68dc6b7b2f34",
         "data_for_release/batch_15.json": "c6608ce2edd17134674c7f8a0fdfc871e22458b432b35506889886c737eb4663",
         "data_for_release/batch_16.json": "e35ace1069bb79844b122415d3c4192f7147737a2b9ad509185fb2c1ba7090db",
         "FaithBench.csv": "b64595319c5a0673c7af00a12c9340a79aeb3437c021b097745413da42d80a09"}
QUESTION = {"type": "choice", "instructions": "Is the summary faithful to the source text?",
            "criteria": {"yes": "The summary is faithful to the source text.",
                         "no": "The summary contains a hallucination: something that the source text does not support."}}


def fetch(cache, name):
    """Bytes of one source file from the cache (downloaded once from the pinned official URL), checksum verified."""
    path = os.path.join(cache, name)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with urllib.request.urlopen(f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/{name}", timeout=300) as r, \
                open(path + ".part", "wb") as f:
            f.write(r.read())
        os.replace(path + ".part", path)
    data = open(path, "rb").read()
    if hashlib.sha256(data).hexdigest() != FILES[name]:
        sys.exit(f"{path}: SHA-256 differs from the file at commit {COMMIT}")
    return data


def dumps(item):
    """One JSON line; the three characters that str.splitlines() takes for line ends are written as JSON escapes."""
    return (json.dumps(item, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
            .replace("\x85", "\\u0085"))


def bucket(n):
    """Length bucket: 100 characters below 2,000, 1,000 above."""
    return n // 100 if n < 2000 else 20 + (n - 2000) // 1000


def best_threshold(xs, ys):
    """Best accuracy of a rule 'x > t -> yes' or its mirror (the rule of audit.py); xs numbers, ys booleans."""
    order = sorted(zip(xs, ys))
    n, pos = len(order), sum(ys)
    best, tp_left, i = max(pos, n - pos) / n, 0, 0
    while i < n:
        j = i
        while j < n and order[j][0] == order[i][0]:
            tp_left += order[j][1]
            j += 1
        a = (j - tp_left) + (pos - tp_left)
        best = max(best, a / n, (n - a) / n)
        i = j
    return best


def classify(sample):
    """('yes' | 'no' | None, why): the label of a summary by the rule in the module text; why names the dropped group."""
    ann = sample["annotations"]
    if not ann:
        return "yes", None
    by = collections.defaultdict(list)
    for a in ann:
        by[a["annotator_id"]].append([str(l) for l in a["label"]])
    unwanted = {k: any(l.startswith("Unwanted") for ls in v for l in ls) for k, v in by.items()}
    if len(by) >= 2 and all(unwanted.values()):
        return "no", None
    labels = {l.split(".")[0] for v in by.values() for ls in v for l in ls}
    if not labels:
        return None, "annotations without a label"
    if not any(unwanted.values()):
        return None, "only Benign or Questionable spans" if labels <= {"Benign", "Questionable"} else "other"
    if len(by) == 1:
        return None, "one annotator only (Unwanted)"
    return None, "annotators disagree (Unwanted by some, not by all)"


def main():
    cache = os.path.abspath(sys.argv[1])
    cache = cache if os.path.basename(cache) == SOURCE else os.path.join(cache, SOURCE)
    samples = []
    for b in BATCHES:
        for s in json.loads(fetch(cache, f"data_for_release/batch_{b}.json").decode("utf-8"))["samples"]:
            samples.append({**s, "batch": b})
    assert len(samples) == 750 and len({(s["batch"], s["sample_id"]) for s in samples}) == 750
    samples.sort(key=lambda s: (s["batch"], s["sample_id"]))
    csv_rows = {(r["source"], r["summary"]): r for r in csv.DictReader(io.StringIO(fetch(cache, "FaithBench.csv").decode("utf-8")))}
    pool, dropped = {"yes": [], "no": []}, collections.Counter()
    for s in samples:
        g, why = classify(s)
        if g:
            pool[g].append(s)
        else:
            dropped[why] += 1
    cells = {g: collections.defaultdict(list) for g in pool}
    for g in pool:
        for s in pool[g]:
            cells[g][bucket(len(s["summary"]))].append(s)
    # reference: a plain balanced draw (not used) and the length rules on it
    ref_rng = random.Random(SEED)
    ref_no = ref_rng.sample(pool["no"], len(pool["yes"]))
    ref = [(s, True) for s in pool["yes"]] + [(s, False) for s in ref_no]
    ref_cue = {f: best_threshold([len(s[f]) for s, _ in ref], [y for _, y in ref]) for f in ("summary", "source")}
    rng = random.Random(SEED)
    picked = []
    for b in sorted(set(cells["yes"]) & set(cells["no"])):
        m = min(len(cells["yes"][b]), len(cells["no"][b]))
        for g in ("yes", "no"):
            picked += [(g, s) for s in rng.sample(cells[g][b], m)]
    rng.shuffle(picked)
    items = []
    for g, s in picked:
        c = csv_rows[(s["source"], s["summary"])]
        items.append({"id": f"{TASK}:b{s['batch']:02d}-{s['sample_id']:02d}", "state": {"source": s["source"], "summary": s["summary"]},
                      "questions": {"q": QUESTION}, "gold": g, "soft": None, "group": None,
                      "meta": {"source_id": f"batch_{s['batch']}:{s['sample_id']}", "batch": s["batch"], "sample_id": s["sample_id"],
                               "summarizer": s["metadata"]["summarizer"], "n_annotators": len({a["annotator_id"] for a in s["annotations"]}),
                               "file_worst_label": c["worst-label"], "file_best_label": c["best-label"]}})
    gold = collections.Counter(it["gold"] for it in items)
    cue = {f: best_threshold([len(it["state"][f]) for it in items], [it["gold"] == "yes" for it in items]) for f in ("summary", "source")}
    mean_len = {g: sum(len(it["state"]["summary"]) for it in items if it["gold"] == g) / gold[g] for g in ("yes", "no")}
    by_model = collections.Counter((it["meta"]["summarizer"].split("/")[-1], it["gold"]) for it in items)
    models = sorted({m for m, _ in by_model})
    dissent = sum(it["gold"] == "no" and it["meta"]["file_best_label"] == "Consistent" for it in items)
    n_pool = {g: len(pool[g]) for g in pool}
    drop_txt = "; ".join(f"{n} ({k})" for k, n in sorted(dropped.items(), key=lambda kv: -kv[1]))
    tj = {"task": TASK, "layer": "C", "title": "FaithBench: is the summary faithful to the source text?",
          "decision": "whether an LLM-written summary is faithful to its source text (yes) or contains a hallucination that experts marked as unwanted (no)",
          "source": {"name": "FaithBench (FaithBench: A Diverse Hallucination Benchmark for Summarization by Modern LLMs, NAACL 2025, arXiv:2410.13210)",
                     "url": f"https://github.com/{REPO}", "files": sorted(FILES),
                     "split": "released batches 1-12 and 14-16 (750 summaries; the README lists no batch 13)",
                     "version": f"commit {COMMIT} ({COMMIT_DATE}), downloaded 2026-10-07"},
          "licence": "Attribution-NonCommercial-ShareAlike 4.0 International (file LICENSE of the repository)",
          "redistribution": "rebuild script only", "labels": "human", "item_source": "public test set", "metric": "accuracy", "chance": 0.5,
          "rows": len(items), "groups": None, "question_type": "choice", "options": 2,
          "notes": f"{gold['yes']} yes + {gold['no']} no, from 750 released summaries (10 LLMs, 75 each). LABEL RULE (the README gives a taxonomy "
                   f"and no aggregation rule; its script is not usable as a rule: it returns 0 both for a summary without annotations and for a "
                   f"hallucinated one): yes = the summary has no annotation (README: Consistent, no annotations needed): {n_pool['yes']} summaries; "
                   f"no = at least two different annotators left annotations and each of them marked a span Unwanted (intrinsic or extrinsic): "
                   f"{n_pool['no']} summaries. Dropped as in between: {drop_txt}. The files do not say how many experts looked at a summary "
                   f"(an expert who finds nothing leaves no annotation), so 'the majority of the experts' cannot be computed; unanimity of the "
                   f"annotators on record is used instead. The repository's FaithBench.csv, which the README does not describe, has a worst and "
                   f"a best label per summary (kept in meta.file_worst_label / file_best_label); in {dissent} of the {gold['no']} rows labelled "
                   f"no its best label is Consistent, i.e. another annotator found nothing, so these are 'unwanted' for the annotators on "
                   f"record and contested overall; yes rows with a different file label: "
                   f"{sum(it['gold'] == 'yes' and it['meta']['file_worst_label'] != 'Consistent' for it in items)}. LENGTH MATCHING: hallucinated summaries are "
                   f"longer (and come from longer sources); a plain balanced draw has best single length thresholds of {ref_cue['summary']:.3f} (summary) "
                   f"and {ref_cue['source']:.3f} (source). The rows were put in buckets of the summary length (100 characters) and the same number "
                   f"was drawn from both classes in every bucket (random.Random({SEED}); all matched pairs, so fewer than the {n_pool['yes']} + "
                   f"{n_pool['yes']} possible); thresholds in the sample: summary {cue['summary']:.3f}, source {cue['source']:.3f}; mean summary length "
                   f"{mean_len['yes']:.0f} (yes) and {mean_len['no']:.0f} (no) characters. Rows by summarising model (yes/no): "
                   + ", ".join(f"{m} {by_model[(m, 'yes')]}/{by_model[(m, 'no')]}" for m in models)
                   + ". The summaries were written by the ten LLMs (meta.summarizer), the labels by the human annotators; the samples were "
                     "chosen by the authors among instances on which popular hallucination detectors disagreed (abstract of arXiv:2410.13210), so "
                     "they are harder than random summaries, and the annotators often disagree (see the dropped groups). state = {source, summary} as in the files; meta.batch and meta.sample_id "
                     "identify the row in data_for_release/batch_<n>.json."}
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
                f"{tj['source']['url']}, {tj['source']['version']}.\n"
                + "".join(f"- File `{n}`: SHA-256 `{FILES[n]}`\n" for n in sorted(FILES, key=lambda n: (n == 'FaithBench.csv', len(n), n)))
                + f"- Licence: {tj['licence']}; {tj['redistribution']}.\n- Rows: {len(items)} ({gold['yes']} yes, {gold['no']} no), "
                f"length-matched on the summary; metric: accuracy (chance 0.5).\n- Rebuild: `python3 reference/build/build_{TASK}.py CACHE_DIR`\n\n"
                "Only summaries that are clearly faithful (no annotation) or clearly hallucinated (all annotators on record marked an unwanted "
                "span, at least two) are used; see `task.json` for the label rule, what was dropped and the caveats.\n")
    print(TASK, len(items), "rows;", dict(gold), "; pools", n_pool, "; dropped:", drop_txt, "; cue summary/source", round(cue["summary"], 3), round(cue["source"], 3),
          "(plain draw", round(ref_cue["summary"], 3), round(ref_cue["source"], 3), "); dissent in no rows", dissent)


if __name__ == "__main__":
    main()
