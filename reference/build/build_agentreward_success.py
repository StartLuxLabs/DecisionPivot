"""Task agentreward_success (layer D, public test set): "did the agent's trajectory complete the user's task?"
Built from AgentRewardBench (official Hugging Face data set McGill-NLP/agent-reward-bench; no licence tag, card "Terms of Use"):
1,302 trajectories of four LLM agents on four web-agent benchmarks (WebArena, VisualWebArena, WorkArena, AssistantBench), each
annotated by expert reviewers (`data/annotations.csv`, column `trajectory_success`: Successful / Unsuccessful / Unsure; 106
trajectories have two annotations).
    python3 reference/build/build_agentreward_success.py CACHE_DIR      (the download cache, or its folder agentreward/)
The text form of a trajectory comes from the judge files of the data set (`judgments/<benchmark>/<agent>/<judge>/<task>.json`).
The files of one judge, `gpt-4o-mini-noscreen-noaxtree`, are used; each holds the goal of the task and the action history that
the benchmark's own code renders for that judge from the trajectory: for every step the URL, the action and the agent's own
reasoning, the last step carrying the final answer when the agent gave one ("The agent performed the following actions: ...").
Nothing else of the file is used: not the judge's reply that is stored in it (model-written), not the screenshots (none are in
these files), not the benchmark's automatic reward.  The full trajectory files under `cleaned/` (30 GB, with page observations)
are not used.  The files are fetched once from the pinned commit if missing; the checksum of annotations.csv and one checksum of
the sorted list of "path SHA-256" lines of all 1,302 judge files are verified, so the output is the same on every run.
Labels.  yes = every annotation of the trajectory says Successful, no = every annotation says Unsuccessful; trajectories with
disagreeing annotations or an Unsure are dropped (counted).  Trajectories whose action-history text is longer than 30,000
characters are dropped (counted).  The classes differ strongly in length (successful runs are short), so the rows are
length-matched: steps are put in buckets by the length of the JSON text of the `steps` list (100 characters below 2,000, 1,000
above) and the same number of rows is drawn from both classes in every bucket (random.Random(20261007), buckets in order), all
the matched pairs the data allow.  The final row order is shuffled with the same generator.  state = {task: the goal, steps: one
string per step ("Step: n", URL, action, reasoning), as rendered}."""
import collections
import csv
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "generated", "reference")   # writes HERE/tasks/<task>/
TASK, SOURCE, SEED, MAX_CHARS = "agentreward_success", "agentreward", 20261007, 30000
REPO = "McGill-NLP/agent-reward-bench"
COMMIT, COMMIT_DATE = "b6d17e646009d6cb63d5dd7be78807b680693f61", "2025-04-21"      # main, read on 2026-10-07
JUDGE = "gpt-4o-mini-noscreen-noaxtree"
ANN, ANN_SHA = "data/annotations.csv", "155be0e6530d190c14a056f0195aaafa081c2a45a36e8f72b922c9fdc6838367"
MANIFEST_SHA = "3b509abfb5b5fc6002a94c71de3e3228007adbe2fbd46463e89612220ace09f5"
HEAD = "The agent performed the following actions:\n-----\n"
TERMS = ["Restrictions: You agree not to use the Dataset in any way that is unlawful or would infringe upon the rights of others.",
         "Acknowledgment: By using the Dataset, you acknowledge that the Dataset may contain data derived from third-party sources, and "
         "you agree to abide by any additional terms and conditions that may apply to such third-party data.",
         "Fair Use Declaration: The Dataset may be used for research if it constitutes \"fair use\" under copyright laws within your "
         "jurisdiction. You are responsible for ensuring your use complies with applicable laws."]
QUESTION = {"type": "choice", "instructions": "Did the agent's trajectory complete the user's task?",
            "criteria": {"yes": "The agent completed the task.", "no": "The agent did not complete the task."}}


def fetch(cache, name):
    """Path of one source file in the cache (downloaded once from the pinned official URL, three tries)."""
    path = os.path.join(cache, name)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        url = f"https://huggingface.co/datasets/{REPO}/resolve/{COMMIT}/{urllib.parse.quote(name)}"
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=120) as r, open(path + ".part", "wb") as f:
                    f.write(r.read())
                os.replace(path + ".part", path)
                break
            except OSError:
                if attempt == 2:
                    raise
                time.sleep(5)
    return path


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


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


def split_steps(block):
    """The steps of the rendered action history, one string each; the pieces joined again give back the block."""
    assert block.startswith(HEAD) and block.endswith("-----")
    parts = re.split(r"-----\n(?=Step: \d+\nURL: )", block[len(HEAD):-5])
    assert [int(re.match(r"Step: (\d+)\n", p).group(1)) for p in parts] == list(range(1, len(parts) + 1))
    assert HEAD + "-----\n".join(parts) + "-----" == block
    return parts


def main():
    cache = os.path.abspath(sys.argv[1])
    cache = cache if os.path.basename(cache) == SOURCE else os.path.join(cache, SOURCE)
    ann_path = fetch(cache, ANN)
    if sha256(ann_path) != ANN_SHA:
        sys.exit(f"{ann_path}: checksum differs from the file this task was built from")
    ann = collections.defaultdict(list)
    for r in csv.DictReader(open(ann_path, encoding="utf-8")):
        ann[(r["benchmark"], r["model_name"], r["task_id"])].append(r)
    keys = sorted(ann)
    names = [f"judgments/{k[0]}/{k[1]}/{JUDGE}/{k[2]}.json" for k in keys]
    with ThreadPoolExecutor(max_workers=8) as ex:               # first run: the missing files are fetched eight at a time
        list(ex.map(lambda n: fetch(cache, n), [n for n in names if not os.path.exists(os.path.join(cache, n))]))
    lines = [f"{name} {sha256(os.path.join(cache, name))}" for name in names]
    if hashlib.sha256("\n".join(lines).encode()).hexdigest() != MANIFEST_SHA:
        sys.exit("the judge files differ from the files this task was built from (manifest checksum)")
    pool = {"yes": [], "no": []}
    drop = collections.Counter()
    for k in keys:
        marks = sorted({r["trajectory_success"] for r in ann[k]})
        d = json.load(open(os.path.join(cache, f"judgments/{k[0]}/{k[1]}/{JUDGE}/{k[2]}.json"), encoding="utf-8"))
        assert d["benchmark"] == k[0] and d["agent"] == k[1] and d["judge"] == JUDGE
        texts = [x["text"] for x in d["chat_messages"]["regular"][1]["content"] if x.get("type") == "text"]
        blocks = [t for t in texts if t.startswith("The agent performed the following actions")]
        assert len(blocks) == 1
        if marks == ["Successful"]:
            gold = "yes"
        elif marks == ["Unsuccessful"]:
            gold = "no"
        else:
            drop["disagreeing or unsure annotations"] += 1
            continue
        if len(blocks[0]) > MAX_CHARS:
            drop[f"action history longer than {MAX_CHARS:,} characters ({gold})"] += 1
            continue
        steps = split_steps(blocks[0])
        pool[gold].append({"key": k, "sid": "/".join(k), "goal": d["goal"], "steps": steps, "n": len(json.dumps(steps, ensure_ascii=False)),
                           "annotators": sorted(r["annotator_name"].strip() for r in ann[k]), "n_ann": len(ann[k])})
    for g in pool:
        pool[g].sort(key=lambda r: r["sid"])
    # reference: a plain balanced draw (not used) and how far a length rule gets on it
    ref_rng = random.Random(SEED)
    ref = [(r["n"], True) for r in pool["yes"]] + [(r["n"], False) for r in ref_rng.sample(pool["no"], len(pool["yes"]))]
    ref_acc = best_threshold([x for x, _ in ref], [y for _, y in ref])
    # length-matched draw: the same number from both classes in every bucket
    cells = {g: collections.defaultdict(list) for g in pool}
    for g in pool:
        for r in pool[g]:
            cells[g][bucket(r["n"])].append(r)
    rng = random.Random(SEED)
    rows = []
    for b in sorted(set(cells["yes"]) & set(cells["no"])):
        m = min(len(cells["yes"][b]), len(cells["no"][b]))
        for g in ("yes", "no"):
            rows += [(g, r) for r in rng.sample(cells[g][b], m)]
    rng.shuffle(rows)
    items = []
    for g, r in rows:
        items.append({"id": f"{TASK}:{r['sid']}", "state": {"task": r["goal"], "steps": r["steps"]}, "questions": {"q": QUESTION},
                      "gold": g, "soft": None, "group": None,
                      "meta": {"source_id": r["sid"], "benchmark": r["key"][0], "agent": r["key"][1], "task_id": r["key"][2],
                               "n_steps": len(r["steps"]), "n_annotations": r["n_ann"], "annotators": r["annotators"]}})
    gold = collections.Counter(it["gold"] for it in items)
    by_bench = collections.Counter((it["meta"]["benchmark"], it["gold"]) for it in items)
    by_agent = collections.Counter((it["meta"]["agent"].replace("GenericAgent-", ""), it["gold"]) for it in items)
    mean_steps = {g: sum(it["meta"]["n_steps"] for it in items if it["gold"] == g) / gold[g] for g in ("yes", "no")}
    n_all = len(keys)
    n_pool = {g: len(pool[g]) for g in pool}
    drop_txt = "; ".join(f"{n} ({k})" for k, n in sorted(drop.items()))
    benches = sorted({k[0] for k in by_bench})
    tj = {"task": TASK, "layer": "D", "title": "AgentRewardBench: did the web agent complete the task?",
          "decision": "whether a web agent's trajectory (task, then URL, action and reasoning of every step) completed the task, as annotated by expert reviewers",
          "source": {"name": "AgentRewardBench (AgentRewardBench: Evaluating Automatic Evaluations of Web Agent Trajectories, arXiv:2504.08942)",
                     "url": f"https://huggingface.co/datasets/{REPO}",
                     "files": [ANN, f"judgments/<benchmark>/<agent>/{JUDGE}/<task>.json (all {n_all:,} files)"],
                     "split": f"all {n_all:,} annotated trajectories (annotation file: {sum(len(v) for v in ann.values()):,} rows)",
                     "version": f"commit {COMMIT} (last modified {COMMIT_DATE}), downloaded 2026-10-07"},
          "licence": "no licence tag on the card; card 'Terms of Use': research use under fair use, third-party terms apply, derivatives must carry "
                     "the terms (see README.md of this task)",
          "redistribution": "rebuild script only", "labels": "human", "item_source": "public test set", "metric": "accuracy", "chance": 0.5,
          "rows": len(items), "groups": None, "question_type": "choice", "options": 2,
          "notes": f"{gold['yes']} yes + {gold['no']} no. Source trajectories: {n_all:,}; dropped before sampling: {drop_txt}; pools: {n_pool['yes']} yes, "
                   f"{n_pool['no']} no. Labels: the experts' `trajectory_success` (Successful = yes, Unsuccessful = no); a trajectory with two "
                   f"annotations is used only if both agree. LENGTH MATCHING: successful trajectories are much shorter than failed ones, so a "
                   f"plain balanced draw ({n_pool['yes']} + {n_pool['yes']}) has a best single length threshold of {ref_acc:.3f} (audit rule, chance 0.5); "
                   f"rows were put in buckets by the length of the JSON text of `steps` (100 characters below 2,000, 1,000 above) and the same "
                   f"number was drawn from both classes in every bucket (random.Random({SEED}), {len(set(cells['yes']) & set(cells['no']))} buckets "
                   f"shared by both classes); that gives all the matched pairs the data allow, {gold['yes']} + {gold['no']}, so the task is "
                   f"smaller than 1,000 rows. Mean number of steps in the sample: {mean_steps['yes']:.1f} (yes), {mean_steps['no']:.1f} (no). "
                   f"Rows by benchmark (yes/no): " + ", ".join(f"{b} {by_bench[(b, 'yes')]}/{by_bench[(b, 'no')]}" for b in benches)
                   + "; by agent (yes/no): " + ", ".join(f"{a} {by_agent[(a, 'yes')]}/{by_agent[(a, 'no')]}" for a in sorted({k[0] for k in by_agent}))
                   + ". The mix of benchmarks and agents differs between the classes (it is not matched). TEXT FORM: state.task = the goal, "
                   f"state.steps = the steps of the action history that the benchmark's own judge prompt renders (URL, action, the agent's "
                   f"reasoning; the final answer is the last action when the agent gave one), taken from the files of the {JUDGE} judge; the "
                   f"judge's reply in those files, the page observations and the screenshots are not used. The expert labels were made with the "
                   f"screenshots and the full trajectory, which this text does not contain, so a text-only decision can be wrong for reasons the "
                   f"text cannot show; VisualWebArena tasks can refer to images. Annotators: {len({a for it in items for a in it['meta']['annotators']})} "
                   f"reviewers named by letter in the annotation file (meta.annotators); "
                   f"{sum(it['meta']['n_annotations'] > 1 for it in items)} rows have two annotations that agree. Terms of use of the data set "
                   f"(derivatives must include them) are in README.md; only the rebuild script is redistributed, not the rows."}
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
                f"{tj['source']['url']}, {tj['source']['version']}.\n- Files: `{ANN}` (SHA-256 `{ANN_SHA}`) and the {n_all:,} judge files "
                f"`judgments/<benchmark>/<agent>/{JUDGE}/<task>.json` (digest of the sorted list of path and SHA-256: `{MANIFEST_SHA}`).\n"
                f"- Rows: {len(items)} ({gold['yes']} yes, {gold['no']} no), length-matched; metric: accuracy (chance 0.5).\n"
                f"- Rebuild: `python3 reference/build/build_{TASK}.py CACHE_DIR` (fetches the files if missing).\n\n"
                f"## Terms of use of the data set (the card says derivatives must include them)\n\n"
                + "".join(f"- {t}\n" for t in TERMS) + "\nThe card requires derivatives to include these terms. In this benchmark the rows of this task are not redistributed, "
                "only the rebuild script is. See `task.json` for the text form, the label rule and the length matching.\n")
    print(TASK, len(items), "rows;", dict(gold), "; dropped:", drop_txt, "; pools", n_pool, "; plain-draw length rule", round(ref_acc, 3))


if __name__ == "__main__":
    main()
