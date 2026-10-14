"""Score runs of DecisionPivot (releases 1.1 and 1.3).  The scorer of releases 1.0 to 1.3: every metric and interval is the same.  Release
1.3 removed from the reference tasks the items seen in the training data of the final StartLux-Decision-27B, so a task.json may name,
in accepts_items_sha256, earlier versions whose items are a SUPERSET of its own: a run made on such a version still counts (it is read
by id, and at least 99% of the items must have a line, as for every run).
Outputs of --all: headline tables over the generated families (T1 = the 13 DecisionPivot families; a task.json "family_set" other than
"decidebench" puts a family into a separate table T1b, and T1c covers all generated families), the family set on every per-family row
(tables/T2_core_per_family_long.csv), the share of items with a thought next to the tokens (T4), and tables that list only the systems
marked "table": true in systems.json (a run folder without an entry is scored in scores.json, report.md and MISSING_RUNS.md but is
not listed in the tables).
    python3 scoring/score.py [--root DIR] NAME=RUN_DIR [NAME=RUN_DIR ...] [--tasks T1,T2] [--out DIR] [--resamples 1000] [--subsample FILE]
    python3 scoring/score.py --all [--root DIR] [--runs DIR] [--systems FILE] [--out DIR] [--resamples 1000] [--jobs N]
                             [--headline-families auto|all|a,b,c] [--registered-only]
--root DIR: the benchmark folder that holds tasks/<task>/ (default: data/ of the repository, where the release is downloaded).
--subsample FILE: JSON {task: [item ids]}; every task is scored on these items only (reference rows that were run on a fixed
subsample; all systems named in the same call are scored on the same items).
--all: every folder of the runs folder (--runs DIR; default: runs/ inside the --root folder) on every task of tasks/, display names,
kinds and sizes from systems.json (--systems FILE; default: systems.json inside the --root folder; a system is listed in the tables T1..T4 only with "table": true); with
--out DIR (default: results/ of the repository) it writes scores.json, report.md, tables/T1..T4 (.csv and .tex) and MISSING_RUNS.md.
RUN_DIR holds one file per task, <task>.jsonl, one line per item: {"id", "answers": {"q": ANSWER}} where ANSWER is the answer
object of a typed-decision request (choice: {"type", "choice", "probabilities"}; score: {"type", "score", "probabilities" keyed
"0".."n-1"}; noul: {"type", "noul"}), or {"id", "p": {option: probability}}.  Lines with an "error" field and items without a
line count as unanswered; an unanswered item gets the uniform distribution and counts as wrong.  A run counts for a task only if
at least 99% of the task's items have a line (an answer or an error line) and, when runs_index.json records the version of the
items the run was made on, that version is the one in tasks/; otherwise the task is "not run on this version".

Per task (v0 definitions, unchanged):
  value     the task's own metric (accuracy, auroc, ndcg@10, pair_accuracy, or for mse_soft tasks the skill
            1 - mse / mse of the best constant, sampling noise of the label removed)
  lo, hi    percentile bootstrap interval of the value (seed 20261007); v1 resamples GROUPS when a task has groups, items otherwise
  score     value on a common scale: 0 = chance, 100 = perfect ((value - chance) / (1 - chance); skill as it is);
            negative values are kept in the table and counted as 0 in the means
  ece       calibration error of the top option, 15 equal-width bins (tasks with a gold option)
  brier     mean squared error of the option probabilities against the gold option (or the soft label)
  logscore  mean log probability of the gold option, floor 1e-6
  coverage  share of items answered; an unanswered item gets the uniform distribution and counts as wrong
Added in v1 (tasks with a gold option; intervals by the same bootstrap):
  accuracy          share of items whose top option is the gold option
  pair_accuracy     tasks with contrast groups: share of groups in which EVERY member is right
  pair_direction    yes/no contrast pairs: share of pairs in which P(yes) of the member whose truth is yes is larger than P(yes) of
                    the member whose truth is no (a tie does not count)
  auto_at_5/_1      largest share of the items that can be decided automatically while the error rate among the decided items
                    stays at or below 5% / 1%: items sorted by their top probability, highest first, items with equal
                    probability (after rounding to 12 decimals) enter together, the longest prefix that meets the target
  acc_at_090        accuracy among the items whose top probability is at least 0.90;  share_at_090 = their share of all items
  aurc              area under the risk-coverage curve: mean over items of the error rate of the prefix (sorted as above, ties
                    together) in which the item enters; 0 = perfect, (1 - accuracy) when the top probability says nothing
  trigger_recall_20 share of the system's errors that lie among the 20% of items with the lowest top probability (a tied group
                    that straddles the boundary counts in proportion)
  levels            accuracy and pair accuracy per difficulty level (1, 2, 3) of generated families; dials: the same per value of a
                    declared dial (families with two crossed dials)
Aggregates: core track (T1, T2) and reference track (T3: layer scores = mean of the floored task scores per layer, overall = mean
of the layer scores, as in v0)."""
import collections
import csv
import json
import math
import multiprocessing
import os
import random
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repository root (this file is scoring/score.py)
# the benchmark folder: HERE/tasks/<task>/ holds the items (default: data/ of the repository); --root DIR sets it.  main() passes it on
# in the environment so that worker processes (--jobs) started by spawn read the same folder.
HERE = os.path.abspath(os.environ.get("DECISIONPIVOT_ROOT") or os.path.join(REPO, "data"))
SYSTEMS_FILE = None        # --systems FILE (default: HERE/systems.json)
SEED = 20261007
MIN_PRESENT = 0.99          # share of a task's items that must have a line (answer or error) for a run to count
TAU = 0.90                  # acc_at_090 / share_at_090
TRIGGER = 0.20              # trigger_recall_20
LEVELS = (1, 2, 3)
BINS = 15
# runs whose files are not probabilities of the model but a published ranking (see runs/jev-1.13/README.md in v0): only the ranking metric is meaningful
RANKING_ONLY = {"jev-1.13": ("rerank_scifact", "rerank_nfcorpus")}


# --------------------------------------------------------------------------------------------- loading
def jload(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_path(item, dotted):
    cur = item
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def load_task(task, root=None):
    """-> (task.json, items); an item keeps id, questions, gold, soft, group and the scalar fields of meta, not the state"""
    d = f"{root or HERE}/tasks/{task}"
    tj = jload(f"{d}/task.json")
    items = []
    with open(f"{d}/items.jsonl", encoding="utf-8") as f:
        for l in f:
            it = json.loads(l)
            it["state"] = None
            m = it.get("meta") or {}
            it["meta"] = {k: v for k, v in m.items() if v is None or isinstance(v, (int, float, str, bool)) or k == "ideal_gains"}
            items.append(it)
    return tj, items


def keys_of(item):
    c = item["questions"]["q"].get("criteria")
    if item["questions"]["q"]["type"] == "noul":
        return ["yes", "no"]
    return [str(i) for i in range(len(c))] if isinstance(c, list) else list(c)


def probs_of(line, keys):
    """-> {key: p} normalised over the item's options, or None"""
    if not line or "error" in line:
        return None
    p = line.get("p")
    if p is None:
        a = ((line.get("answers") or {}).get("q")) or {}
        if a.get("type") == "noul" and a.get("noul") is not None:
            p = {"yes": float(a["noul"]), "no": 1 - float(a["noul"])}
        else:
            p = a.get("probabilities")
    if not p:
        return None
    try:
        v = {k: max(0.0, float(p.get(k, 0.0))) for k in keys}
    except (TypeError, ValueError):
        return None
    s = sum(v.values())
    return {k: x / s for k, x in v.items()} if s > 0 else None


def run_stamp(run_dir):
    """{task: items_sha256} that the runner of this folder wrote into _items.json (the version of the items the run was made on); {} if none"""
    p = f"{run_dir}/_items.json"
    try:
        return jload(p) if os.path.exists(p) else {}
    except Exception:
        return {}


def read_run(path):
    """-> (lines {id: line without error}, present {ids with any line}); a last line without newline is ignored"""
    lines, present = {}, set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for l in f:
                if l.endswith("\n"):
                    try:
                        x = json.loads(l)
                    except Exception:
                        continue
                    present.add(x.get("id"))
                    if "error" not in x:
                        lines[x["id"]] = x
    return lines, present


def level_of(item, tj):
    lf = tj.get("level_from")
    if lf:
        v = get_path(item, lf["field"])
        return lf["values"].get(str(v)) if v is not None else None
    lv = (item.get("meta") or {}).get("level")
    return lv if isinstance(lv, int) and not isinstance(lv, bool) and lv in LEVELS else None


# --------------------------------------------------------------------------------------------- v0 metrics
def auroc(score, label):
    pos = sum(label)
    neg = len(label) - pos
    if not pos or not neg:
        return float("nan")
    o = sorted(range(len(score)), key=lambda i: score[i])
    rank_sum, i = 0.0, 0
    while i < len(o):
        j = i
        while j < len(o) and score[o[j]] == score[o[i]]:
            j += 1
        r = (i + 1 + j) / 2
        rank_sum += r * sum(1 for x in o[i:j] if label[x])
        i = j
    return (rank_sum - pos * (pos + 1) / 2) / (pos * neg)


def ndcg10(rows, k=10):
    """rows of one query: (relevance score, doc id, graded gain, ideal gains)"""
    ranked = sorted(rows, key=lambda r: (-r[0], r[1]))[:k]
    dcg = sum(r[2] / math.log2(n + 1) for n, r in enumerate(ranked, 1))
    ideal = rows[0][3] if rows[0][3] else sorted((r[2] for r in rows), reverse=True)
    idcg = sum(g / math.log2(n + 1) for n, g in enumerate(ideal[:k], 1))
    return dcg / idcg if idcg > 0 else float("nan")


def unit_values(tj, items, probs):
    """-> (units, fn) where fn(list of units) -> metric value; a unit is what the bootstrap resamples.
    v1: an accuracy task with contrast groups resamples groups (a unit is (correct, size) of a group, the value is the ratio of sums)."""
    metric = tj["metric"]
    keyset = {i["id"]: keys_of(i) for i in items}
    top = {}
    for it in items:
        p = probs[it["id"]]
        ks = keyset[it["id"]]
        top[it["id"]] = max(ks, key=lambda k: p[k]) if p is not None else None        # first option wins ties
    if metric == "accuracy":
        if tj.get("group_kind") == "contrast" and any(i.get("group") for i in items):
            g = collections.defaultdict(lambda: [0, 0])
            for i in items:
                g[i["group"]][0] += top[i["id"]] == str(i["gold"])
                g[i["group"]][1] += 1
            u = [tuple(v) for _, v in sorted(g.items())]
            return u, lambda x: sum(a for a, _ in x) / sum(b for _, b in x)
        u = [float(top[i["id"]] == str(i["gold"])) for i in items]
        return u, lambda x: sum(x) / len(x)
    if metric == "auroc":
        u = [((probs[i["id"]] or {"yes": 0.5})["yes"], str(i["gold"]) == "yes") for i in items]
        return u, lambda x: auroc([a for a, _ in x], [b for _, b in x])
    if metric == "pair_accuracy":
        g = collections.defaultdict(list)
        for i in items:
            g[i["group"]].append(top[i["id"]] == str(i["gold"]))
        u = [float(all(v)) for _, v in sorted(g.items())]
        return u, lambda x: sum(x) / len(x)
    if metric == "ndcg@10":
        g = collections.defaultdict(list)
        for i in items:
            ks, p = keyset[i["id"]], probs[i["id"]]
            if p is None:
                rel = 0.0
            elif i["questions"]["q"]["type"] == "score":
                rel = sum(int(k) * p[k] for k in ks) / (len(ks) - 1)
            else:
                rel = p["yes"]
            m = i.get("meta") or {}
            g[i["group"]].append((rel, str(m.get("doc_id", i["id"])), float(m.get("relevance", 0)), m.get("ideal_gains")))
        u = [ndcg10(v) for _, v in sorted(g.items())]
        u = [x for x in u if x == x]
        return u, lambda x: sum(x) / len(x)
    if metric == "mse_soft":
        u = []
        for i in items:
            y = i["soft"]["yes"]
            n = (i.get("meta") or {}).get("n")
            noise = y * (1 - y) / (n - 1) if n and n > 1 else 0.0
            u.append(((probs[i["id"]] or {"yes": 0.5})["yes"], y, noise))

        def skill(x):
            my = sum(y for _, y, _ in x) / len(x)
            nz = sum(z for _, _, z in x) / len(x)
            mse = sum((p - y) ** 2 for p, y, _ in x) / len(x) - nz
            mse_c = sum((my - y) ** 2 for _, y, _ in x) / len(x) - nz
            return 1 - mse / mse_c if mse_c > 1e-9 else float("nan")
        return u, skill
    raise ValueError(metric)


def chance_of(tj, items):
    if tj["metric"] == "accuracy":
        return sum(1 / len(keys_of(i)) for i in items) / len(items)
    if tj["metric"] == "auroc":
        return 0.5
    if tj["metric"] == "pair_accuracy":
        g = collections.defaultdict(lambda: 1.0)
        for i in items:
            g[i["group"]] *= 1 / len(keys_of(i))
        return sum(g.values()) / len(g)
    if tj["metric"] == "ndcg@10":                       # expected value of a random order, 200 draws per query
        rng = random.Random(SEED)
        g = collections.defaultdict(list)
        for i in items:
            m = i.get("meta") or {}
            g[i["group"]].append((0.0, str(m.get("doc_id", i["id"])), float(m.get("relevance", 0)), m.get("ideal_gains")))
        tot = []
        for _, v in sorted(g.items()):
            acc = []
            for _ in range(200):
                acc.append(ndcg10([(rng.random(), r[1], r[2], r[3]) for r in v]))
            if acc[0] == acc[0]:
                tot.append(sum(acc) / len(acc))
        return sum(tot) / len(tot)
    return 0.0                                          # mse_soft: skill 0 = the best constant


def calibration(items, probs):
    """ece (top option, 15 bins), brier, logscore, auroc (binary), accuracy, mean top probability"""
    conf, hit, brier, logs, sc, lab = [], [], [], [], [], []
    for i in items:
        ks = keys_of(i)
        p = probs[i["id"]] or {k: 1 / len(ks) for k in ks}
        if i.get("gold") is not None:
            g = str(i["gold"])
            t = max(ks, key=lambda k: p[k])
            conf.append(p[t])
            hit.append(float(t == g and probs[i["id"]] is not None))
            brier.append(sum((p[k] - (k == g)) ** 2 for k in ks))
            logs.append(math.log(max(p[g], 1e-6)))
            if set(ks) == {"yes", "no"}:
                sc.append(p["yes"])
                lab.append(g == "yes")
        else:
            brier.append(sum((p[k] - i["soft"].get(k, 0.0)) ** 2 for k in ks))
            if set(ks) == {"yes", "no"}:
                sc.append(p["yes"])
                lab.append(i["soft"]["yes"] >= 0.5)
    out = {"brier": sum(brier) / len(brier)}
    if conf:
        bins = collections.defaultdict(list)
        for c, h in zip(conf, hit):
            bins[min(14, int(c * 15))].append((c, h))
        out["ece"] = sum(abs(sum(c for c, _ in b) - sum(h for _, h in b)) for b in bins.values()) / len(conf)
        out["logscore"] = sum(logs) / len(logs)
        out["accuracy"] = sum(hit) / len(hit)
        out["mean_top_p"] = sum(conf) / len(conf)
    if sc and 0 < sum(lab) < len(lab):
        out["auroc"] = auroc(sc, lab)
    return out


# --------------------------------------------------------------------------------------------- the new scores
def selective_scan(mult_o, err_o, end_o, hi_o, bin_o, conf_o, lv_o):
    """One pass over the items in order of falling top probability.  mult_o = multiplicity of each item (a resample), err_o = 1 for a
    wrong item, end_o = True at the last item of a group of equal top probabilities, hi_o = top probability >= TAU, bin_o / conf_o =
    calibration bin and top probability, lv_o = level (0 = none).  Returns a dict of counts and the sorted-prefix scores."""
    cum_n = cum_e = prev_n = prev_e = 0
    best5 = best1 = 0
    aurc_sum = 0.0
    hi_n = hi_c = 0
    bn = [0] * BINS
    bc = [0.0] * BINS
    bh = [0] * BINS
    ln = [0, 0, 0, 0]
    le = [0, 0, 0, 0]
    total_n = sum(mult_o)
    k_top = total_n * (1.0 - TRIGGER)          # items that stay outside the trigger set
    e_top = None
    for pos in range(len(mult_o)):
        m = mult_o[pos]
        if m:
            e = err_o[pos]
            cum_n += m
            cum_e += m * e
            lv = lv_o[pos]
            ln[lv] += m
            le[lv] += m * e
            b = bin_o[pos]
            bn[b] += m
            bc[b] += m * conf_o[pos]
            bh[b] += m * (1 - e)
            if hi_o[pos]:
                hi_n += m
                hi_c += m * (1 - e)
        if end_o[pos] and cum_n > prev_n:
            aurc_sum += (cum_n - prev_n) * (cum_e / cum_n)
            if cum_e * 20 <= cum_n:
                best5 = cum_n
            if cum_e * 100 <= cum_n:
                best1 = cum_n
            if e_top is None and cum_n >= k_top:
                e_top = prev_e + (k_top - prev_n) / (cum_n - prev_n) * (cum_e - prev_e)
            prev_n, prev_e = cum_n, cum_e
    out = {"n": cum_n, "errors": cum_e, "hi_n": hi_n, "hi_c": hi_c, "ln": ln, "le": le}
    if cum_n:
        out["auto_at_5"] = best5 / cum_n
        out["auto_at_1"] = best1 / cum_n
        out["aurc"] = aurc_sum / cum_n
        out["trigger_recall_20"] = (cum_e - (e_top if e_top is not None else cum_e)) / cum_e if cum_e else float("nan")
        out["ece"] = sum(abs(bc[b] - bh[b]) for b in range(BINS)) / cum_n
    return out


class TaskPrep(object):
    """Everything about a task that does not depend on the system."""

    def __init__(self, tj, items):
        self.tj, self.items = tj, items
        self.n = len(items)
        self.ids = [i["id"] for i in items]
        self.keys = [keys_of(i) for i in items]
        self.gold = [None if i.get("gold") is None else str(i["gold"]) for i in items]
        self.has_gold = all(g is not None for g in self.gold)
        grp = [i.get("group") for i in items]
        self.groups = bool(any(grp))
        self.kind = tj.get("group_kind") or (("ranking" if tj["metric"] == "ndcg@10" else "contrast") if self.groups else None)
        self.contrast = self.groups and self.kind == "contrast"
        if self.groups:
            gid = {g: n for n, g in enumerate(sorted({g for g in grp if g}))}
            self.unit_of_item = [gid[g] if g else None for g in grp]
            nxt = len(gid)
            for j, u in enumerate(self.unit_of_item):
                if u is None:                                   # an item without a group is a unit of its own
                    self.unit_of_item[j] = nxt
                    nxt += 1
            self.n_units = nxt
        else:
            self.unit_of_item = list(range(self.n))
            self.n_units = self.n
        self.members = [[] for _ in range(self.n_units)]
        for j, u in enumerate(self.unit_of_item):
            self.members[u].append(j)
        # strata: levels, declared dials; a unit belongs to a stratum value when all its members do
        self.level = [level_of(i, tj) or 0 for i in items]
        self.strata = {}
        lv_units = self._stratum(self.level, skip=0)
        if lv_units:
            self.strata["level"] = lv_units
        for name, field in (tj.get("dials") or {}).items():
            vals = [get_path(i, field) for i in items]
            st = self._stratum([str(v) if v is not None else None for v in vals], skip=None)
            if st:
                self.strata["dial:" + name] = st
        self.yesno = all(set(k) == {"yes", "no"} for k in self.keys)

    def _stratum(self, vals, skip):
        by = collections.defaultdict(list)
        for u, mem in enumerate(self.members):
            vs = {vals[j] for j in mem}
            if len(vs) == 1:
                v = next(iter(vs))
                if v != skip:
                    by[v].append(u)
        return {str(k): v for k, v in sorted(by.items(), key=lambda kv: str(kv[0]))} if by else None


class SystemArrays(object):
    """The answers of one system on one task, as arrays aligned with TaskPrep."""

    def __init__(self, P, probs):
        N = P.n
        self.tp = [0.0] * N
        self.err = [1] * N
        self.pyes = [0.5] * N
        for j in range(N):
            ks, p = P.keys[j], probs[P.ids[j]]
            if p is None:
                self.tp[j] = 1.0 / len(ks)
                continue
            t = max(ks, key=lambda k: p[k])
            self.tp[j] = p[t]
            self.err[j] = 0 if t == P.gold[j] else 1
            if "yes" in p:
                self.pyes[j] = p["yes"]
        U = P.n_units
        self.u_n = [len(m) for m in P.members]
        self.u_c = [sum(1 - self.err[j] for j in m) for m in P.members]
        self.u_all = [1 if all(self.err[j] == 0 for j in m) else 0 for m in P.members]
        self.u_dir = [None] * U                                         # pair direction, yes/no contrast pairs
        if P.contrast and P.yesno:
            for u, m in enumerate(P.members):
                if len(m) == 2 and {P.gold[m[0]], P.gold[m[1]]} == {"yes", "no"}:
                    y = m[0] if P.gold[m[0]] == "yes" else m[1]
                    n_ = m[1] if y == m[0] else m[0]
                    self.u_dir[u] = 1 if self.pyes[y] > self.pyes[n_] else 0
        tpr = [round(x, 12) for x in self.tp]
        self.order = sorted(range(N), key=lambda j: -tpr[j])
        o = self.order
        self.err_o = [self.err[j] for j in o]
        self.end_o = [pos == N - 1 or tpr[o[pos + 1]] != tpr[o[pos]] for pos in range(N)]
        self.hi_o = [tpr[j] >= TAU - 1e-9 for j in o]
        self.conf_o = [self.tp[j] for j in o]
        self.bin_o = [min(BINS - 1, int(self.tp[j] * BINS)) for j in o]
        self.lv_o = [P.level[j] for j in o]
        self.unit_o = [P.unit_of_item[j] for j in o]


def task_stats(P, A, cnt):
    """All scores of one system on one task for the units drawn `cnt` times (cnt = None: every unit once)."""
    U = P.n_units
    if cnt is None:
        mult_o = [1] * P.n
        cnt_u = None
    else:
        cnt_u = cnt
        mult_o = [cnt[u] for u in A.unit_o]
    s = selective_scan(mult_o, A.err_o, A.end_o, A.hi_o, A.bin_o, A.conf_o, A.lv_o)
    out = {}
    n = s["n"]
    if not n:
        return out
    out["accuracy"] = 1 - s["errors"] / n
    out["auto_at_5"], out["auto_at_1"], out["aurc"] = s["auto_at_5"], s["auto_at_1"], s["aurc"]
    out["trigger_recall_20"], out["ece"] = s["trigger_recall_20"], s["ece"]
    out["hi_n"], out["hi_c"], out["n_items"] = s["hi_n"], s["hi_c"], n
    out["share_at_090"] = s["hi_n"] / n
    out["acc_at_090"] = s["hi_c"] / s["hi_n"] if s["hi_n"] else float("nan")
    for lv in LEVELS:
        if s["ln"][lv]:
            out[f"level{lv}_accuracy"] = 1 - s["le"][lv] / s["ln"][lv]
    if P.contrast:
        if cnt_u is None:
            tot = U
            out["pair_accuracy"] = sum(A.u_all) / U
            de = [d for d in A.u_dir if d is not None]
            if de:
                out["pair_direction"] = sum(de) / len(de)
        else:
            tot = sum(cnt_u)
            out["pair_accuracy"] = sum(c * a for c, a in zip(cnt_u, A.u_all)) / tot if tot else float("nan")
            nd = sd = 0
            for u in range(U):
                c = cnt_u[u]
                if c and A.u_dir[u] is not None:
                    nd += c
                    sd += c * A.u_dir[u]
            if nd:
                out["pair_direction"] = sd / nd
        for name, st in P.strata.items():
            if name != "level":
                continue
            for v, us in st.items():
                if cnt_u is None:
                    out[f"level{v}_pair_accuracy"] = sum(A.u_all[u] for u in us) / len(us)
                else:
                    t = sum(cnt_u[u] for u in us)
                    if t:
                        out[f"level{v}_pair_accuracy"] = sum(cnt_u[u] * A.u_all[u] for u in us) / t
    return out


def dial_stats(P, A):
    """point estimates per value of each declared dial (families with two crossed dials)"""
    out = {}
    for name, st in P.strata.items():
        if not name.startswith("dial:"):
            continue
        d = {}
        for v, us in st.items():
            n = sum(A.u_n[u] for u in us)
            c = sum(A.u_c[u] for u in us)
            row = {"n": n, "accuracy": c / n if n else None}
            if P.contrast:
                row["pair_accuracy"] = sum(A.u_all[u] for u in us) / len(us)
            d[v] = row
        out[name[5:]] = d
    return out


# --------------------------------------------------------------------------------------------- bootstrap
def interval(draws):
    d = sorted(v for v in draws if v is not None and v == v)
    if not d:
        return float("nan"), float("nan")
    return d[int(0.025 * len(d))], d[min(len(d) - 1, int(0.975 * len(d)))]


def make_resamples(n_units, resamples):
    rng = random.Random(SEED)
    return [rng.choices(range(n_units), k=n_units) for _ in range(resamples)]


def clean(x):
    """NaN -> None, recursively; for JSON"""
    if isinstance(x, float):
        return None if x != x else x
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    return x


def score_task_arrays(task, tj, items, P, probs, resamples, boot_idx=None, value_idx=None):
    """-> (result dict, boot arrays) for one system on one task.  boot_idx = resample index lists over the units of P (shared by
    all systems of the task), value_idx = the same for the units of the metric (identical when the counts agree)."""
    units, fn = unit_values(tj, items, probs)
    value = fn(units)
    if value_idx is None:
        value_idx = make_resamples(len(units), resamples) if resamples else []
    vdraws = [fn([units[j] for j in idx]) for idx in value_idx]
    lo, hi = interval(vdraws)
    chance = chance_of(tj, items)
    scale = (lambda v: 100 * v) if tj["metric"] == "mse_soft" else (lambda v: 100 * (v - chance) / (1 - chance))
    answered = sum(p is not None for p in probs.values())
    r = {"task": task, "layer": tj["layer"], "track": tj.get("track"), "metric": tj["metric"], "rows": len(items), "units": len(units),
         "coverage": answered / len(items), "value": value, "lo": lo, "hi": hi, "chance": chance, "score": scale(value),
         "score_lo": scale(lo), "score_hi": scale(hi)}
    r.update(calibration(items, probs))
    boot = {"score": [scale(v) if v == v else float("nan") for v in vdraws]}
    if P.has_gold:
        A = SystemArrays(P, probs)
        point = task_stats(P, A, None)
        if boot_idx is None:
            boot_idx = make_resamples(P.n_units, resamples) if resamples else []
        draws = collections.defaultdict(list)
        for idx in boot_idx:
            cnt = [0] * P.n_units
            for j in idx:
                cnt[j] += 1
            st = task_stats(P, A, cnt)
            for k in point:
                draws[k].append(st.get(k, float("nan")))
        # ratio scores from the pooled counts
        for k in ("accuracy", "pair_accuracy", "pair_direction", "auto_at_5", "auto_at_1", "acc_at_090", "share_at_090", "aurc",
                  "trigger_recall_20"):
            if k in point:
                r[k] = point[k]
                r[k + "_lo"], r[k + "_hi"] = interval(draws[k]) if draws[k] else (float("nan"),) * 2
        r["hi_n"], r["hi_c"] = point["hi_n"], point["hi_c"]
        r["ece_lo"], r["ece_hi"] = interval(draws["ece"]) if draws["ece"] else (float("nan"),) * 2
        r["ece"] = point["ece"]
        lv = {}
        for L in LEVELS:
            row = {}
            if f"level{L}_accuracy" in point:
                row["n_items"] = sum(1 for j in range(P.n) if P.level[j] == L)
                for what in ("accuracy", "pair_accuracy"):
                    k = f"level{L}_{what}"
                    if k in point:
                        row[what] = point[k]
                        row[what + "_lo"], row[what + "_hi"] = interval(draws[k]) if draws[k] else (float("nan"),) * 2
            if row:
                lv[str(L)] = row
        if lv:
            r["levels"] = lv
        dl = dial_stats(P, A)
        if dl:
            r["dials"] = dl
        for k in ("accuracy", "pair_accuracy", "auto_at_5", "ece", "hi_n", "hi_c", "n_items", "level3_pair_accuracy", "level3_accuracy"):
            if k in draws:
                boot[k] = draws[k]
    return clean(r), boot


def task_worker(args):
    """one task for every system: -> (task, {name: result or {"not_run": reason}}, {name: boot arrays}, n_items)"""
    task, systems, resamples, subsample, index = args
    tj, items = load_task(task)
    if subsample is not None:
        keep = set(subsample.get(task, []))
        items = [i for i in items if i["id"] in keep]
        if not items:
            return task, {}, {}, 0
    P = TaskPrep(tj, items)
    boot_idx = make_resamples(P.n_units, resamples) if resamples else []
    value_idx = None
    res, boots = {}, {}
    for name, run_dir in systems:
        lines, present = read_run(f"{run_dir}/{task}.jsonl")
        ids = set(P.ids)
        share = len(ids & present) / len(ids)
        if share < MIN_PRESENT:
            res[name] = {"not_run": "no file" if not present else f"only {100 * share:.0f}% of the items have a line"}
            continue
        e = index.get(f"{os.path.relpath(run_dir, HERE + '/runs')}/{task}") if run_dir.startswith(HERE + "/runs/") else None
        declared = (e or {}).get("items_sha256") or run_stamp(run_dir).get(task)
        if declared and tj.get("items_sha256") and declared != tj["items_sha256"] and declared not in (tj.get("accepts_items_sha256") or []):
            res[name] = {"not_run": "the run was made on another version of the items"}
            continue
        probs = {j: probs_of(lines.get(j), k) for j, k in zip(P.ids, P.keys)}
        if not any(p is not None for p in probs.values()):
            res[name] = {"not_run": "no answer"}
            continue
        # the value draws are those of the metric's units; they are the same lists when the unit counts agree
        units, _ = unit_values(tj, items, probs) if value_idx is None else (None, None)
        if value_idx is None:
            value_idx = boot_idx if len(units) == P.n_units else make_resamples(len(units), resamples)
        r, b = score_task_arrays(task, tj, items, P, probs, resamples, boot_idx, value_idx)
        tk = [x["tokens"] for x in lines.values() if isinstance(x.get("tokens"), (int, float)) and x["id"] in ids]
        if len(tk) >= 0.9 * len(ids):
            r["tokens_mean"] = sum(tk) / len(tk)
        th = [bool(x["thought"]) for x in lines.values() if isinstance(x.get("thought"), bool) and x["id"] in ids]
        if len(th) >= 0.9 * len(ids):                   # v1.2: Auto-Think lines say whether the model thought on the item
            r["thought_share"] = sum(th) / len(th)
        res[name], boots[name] = r, b
    return task, res, boots, len(items)


# --------------------------------------------------------------------------------------------- systems, aggregates
def load_systems():
    p = SYSTEMS_FILE or f"{HERE}/systems.json"
    return jload(p) if os.path.exists(p) else {}


def load_index():
    """runs_index.json = {"runs": {"<system>/<task>": {..., "items_sha256": ...}}, "rejected": {...}}; returns the "runs" part"""
    p = f"{HERE}/runs_index.json"
    return jload(p).get("runs", {}) if os.path.exists(p) else {}


def mean(v):
    v = [x for x in v if x is not None and x == x]
    return sum(v) / len(v) if v else float("nan")


def run_scoring(specs, tasks, resamples, subsample, jobs, index):
    """specs [(name, run_dir)] -> results {name: {task: result}}, not_run {name: {task: reason}}, boots {name: {task: arrays}}"""
    args = [(t, specs, resamples, subsample, index) for t in tasks]
    results = collections.defaultdict(dict)
    not_run = collections.defaultdict(dict)
    boots = collections.defaultdict(dict)
    sizes = {}
    if jobs > 1:
        with multiprocessing.Pool(jobs) as pool:
            it = pool.imap_unordered(task_worker, args)
            out = list(it)
    else:
        out = [task_worker(a) for a in args]
    for task, res, bt, n in out:
        sizes[task] = n
        for name, r in res.items():
            if "not_run" in r:
                not_run[name][task] = r["not_run"]
            else:
                results[name][task] = r
                boots[name][task] = bt[name]
    for name, _ in specs:
        results.setdefault(name, {})
        not_run.setdefault(name, {})
        boots.setdefault(name, {})
    return results, not_run, boots


def layer_scores(res, tasks_by_layer):
    """layer = mean of floored task scores; only layers with every task answered; overall = mean over layers"""
    layers = {}
    for L, ts in tasks_by_layer.items():
        if ts and all(t in res for t in ts):
            layers[L] = mean([max(0.0, res[t]["score"]) if res[t]["score"] == res[t]["score"] else 0.0 for t in ts])
    return layers


def aggregate_reference(res, boot, ref_tasks, tj_of):
    by_layer = collections.defaultdict(list)
    for t in ref_tasks:
        by_layer[tj_of[t]["layer"]].append(t)
    layers = layer_scores(res, by_layer)
    out = {"layers": layers, "n_tasks": sum(1 for t in ref_tasks if t in res)}
    if len(layers) == len(by_layer) and layers:
        out["overall"] = mean(list(layers.values()))
        R = len(next(iter(boot.values()))["score"]) if boot else 0
        ldraws = {L: [] for L in layers}
        odraws = []
        for r in range(R):
            lv = {}
            for L, ts in by_layer.items():
                lv[L] = mean([max(0.0, boot[t]["score"][r]) if boot[t]["score"][r] == boot[t]["score"][r] else 0.0 for t in ts])
                ldraws[L].append(lv[L])
            odraws.append(mean(list(lv.values())))
        out["layers_ci"] = {L: interval(d) for L, d in ldraws.items()}
        out["overall_ci"] = interval(odraws)
    return out


def aggregate_core(res, boot, families, tj_of):
    """T1 numbers over the families (all must be in res): macro means, pooled counts for acc_at_090"""
    fam = [t for t in families if t in res]
    if len(fam) != len(families) or not fam:
        return None
    grouped = [t for t in fam if res[t].get("pair_accuracy") is not None]
    l3 = [t for t in grouped if (res[t].get("levels") or {}).get("3", {}).get("pair_accuracy") is not None]
    out = {"families": len(fam), "families_with_pairs": len(grouped), "families_with_level3_pairs": len(l3)}
    out["accuracy"] = mean([res[t]["accuracy"] for t in fam])
    out["pair_accuracy"] = mean([res[t]["pair_accuracy"] for t in grouped]) if grouped else None
    out["level3_pair_accuracy"] = mean([res[t]["levels"]["3"]["pair_accuracy"] for t in l3]) if l3 else None
    out["auto_at_5"] = mean([res[t]["auto_at_5"] for t in fam])
    hi_n, hi_c = sum(res[t]["hi_n"] for t in fam), sum(res[t]["hi_c"] for t in fam)
    n_all = sum(res[t]["rows"] for t in fam)
    out["acc_at_090"] = hi_c / hi_n if hi_n else None
    out["share_at_090"] = hi_n / n_all
    out["ece"] = mean([res[t]["ece"] for t in fam])
    out["tokens"] = mean([res[t]["tokens_mean"] for t in fam]) if all(res[t].get("tokens_mean") is not None for t in fam) else None
    out["thought_share"] = mean([res[t]["thought_share"] for t in fam]) if all(res[t].get("thought_share") is not None for t in fam) else None
    R = len(boot[fam[0]]["accuracy"]) if boot and "accuracy" in boot[fam[0]] else 0
    d = collections.defaultdict(list)
    for r in range(R):
        d["accuracy"].append(mean([boot[t]["accuracy"][r] for t in fam]))
        if grouped:
            d["pair_accuracy"].append(mean([boot[t]["pair_accuracy"][r] for t in grouped]))
        if l3:
            d["level3_pair_accuracy"].append(mean([boot[t]["level3_pair_accuracy"][r] for t in l3]))
        d["auto_at_5"].append(mean([boot[t]["auto_at_5"][r] for t in fam]))
        hn = sum(boot[t]["hi_n"][r] for t in fam)
        d["acc_at_090"].append(sum(boot[t]["hi_c"][r] for t in fam) / hn if hn else float("nan"))
        nn = sum(boot[t]["n_items"][r] for t in fam)
        d["share_at_090"].append(hn / nn if nn else float("nan"))
        d["ece"].append(mean([boot[t]["ece"][r] for t in fam]))
    out["ci"] = {k: interval(v) for k, v in d.items()}
    return out


# --------------------------------------------------------------------------------------------- output
def f1(x, scale=100.0):
    return "" if x is None or x != x else f"{scale * x:.1f}"


def tex_escape(s):
    for a, b in (("\\", "\\textbackslash{}"), ("&", "\\&"), ("%", "\\%"), ("#", "\\#"), ("_", "\\_"), ("$", "\\$")):
        s = s.replace(a, b)
    return s


def write_table(out_dir, name, header, rows, note, align=None):
    """CSV (plain numbers), LaTeX (booktabs, no vertical rules) and the Markdown text of one table; returns the Markdown"""
    os.makedirs(out_dir, exist_ok=True)
    with open(f"{out_dir}/{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)
    align = align or ("l" + "r" * (len(header) - 1))
    tex = [f"% {note}", f"\\begin{{tabular}}{{{align}}}", "\\toprule", " & ".join(tex_escape(h) for h in header) + " \\\\", "\\midrule"]
    for r in rows:
        tex.append(" & ".join(tex_escape(str(c)) if c != "" else "--" for c in r) + " \\\\")
    tex += ["\\bottomrule", "\\end{tabular}", ""]
    with open(f"{out_dir}/{name}.tex", "w", encoding="utf-8") as f:
        f.write("\n".join(tex))
    md = ["| " + " | ".join(header) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(header))) + "|"]
    for r in rows:
        md.append("| " + " | ".join(str(c) if c != "" else "–" for c in r) + " |")
    return "\n".join(md)


def build_all(args):
    """--all: score every folder of runs/ and write scores.json, report.md, tables, MISSING_RUNS.md"""
    out_dir = args["out"] or os.path.join(REPO, "results")
    systems_meta = load_systems()
    runs_dir = os.path.abspath(args.get("runs") or f"{HERE}/runs")
    folders = sorted(d for d in os.listdir(runs_dir) if os.path.isdir(f"{runs_dir}/{d}")) if os.path.isdir(runs_dir) else []
    if args.get("registered_only"):                 # v1.2: only the run folders that systems.json names (others are being added elsewhere)
        folders = [d for d in folders if d in systems_meta]
    tasks = args["tasks"] or sorted(t for t in os.listdir(f"{HERE}/tasks") if os.path.isfile(f"{HERE}/tasks/{t}/task.json"))
    tj_of = {t: jload(f"{HERE}/tasks/{t}/task.json") for t in tasks}
    index = load_index()
    specs = [(d, f"{runs_dir}/{d}") for d in folders]
    t0 = time.time()
    results, not_run, boots = run_scoring(specs, tasks, args["resamples"], args["subsample"], args["jobs"], index)
    core = [t for t in tasks if tj_of[t].get("track") == "core"]
    ref = [t for t in tasks if tj_of[t].get("track") == "reference"]
    listed = [d for d in folders if (systems_meta.get(d) or {}).get("table", False)]
    # headline families: run by at least half of the listed systems (v1.1 rule), then split by family set (v1.2):
    # T1 = the DecisionPivot families (the 13 of v1.1), T1b = the Open Decision Bench families, T1c = both
    fset = {t: tj_of[t].get("family_set", "decidebench") for t in core}
    spec_h = args["headline"]
    if spec_h == "auto":
        cover = {t: sum(1 for d in listed if t in results[d]) for t in core}
        head_all = [t for t in core if listed and cover[t] >= 0.5 * len(listed)]
    elif spec_h == "all":
        head_all = list(core)
    else:
        head_all = [t for t in spec_h.split(",") if t in core]
    head = [t for t in head_all if fset[t] == "decidebench"]
    head_odb = [t for t in head_all if fset[t] == "odb"]
    S = {}
    for d in folders:
        meta = dict(systems_meta.get(d) or {})
        meta.setdefault("name", d)
        e = {"folder": d, "meta": meta, "tasks": results[d], "not_run": not_run[d]}
        e["core"] = aggregate_core(results[d], boots[d], head, tj_of) if head else None
        e["core_odb"] = aggregate_core(results[d], boots[d], head_odb, tj_of) if head_odb else None
        e["core_all"] = aggregate_core(results[d], boots[d], head_all, tj_of) if head_all else None
        e["reference"] = aggregate_reference(results[d], {t: boots[d][t] for t in ref if t in boots[d]}, ref, tj_of) if ref else None
        S[d] = e
    payload = {"meta": {"seed": SEED, "resamples": args["resamples"], "headline_families": head, "headline_families_odb": head_odb,
                        "headline_families_all": head_all, "core": core, "reference": ref,
                        "tasks": {t: {"track": tj_of[t].get("track"), "family_set": tj_of[t].get("family_set"), "layer": tj_of[t]["layer"], "metric": tj_of[t]["metric"],
                                      "rows": tj_of[t]["rows"], "groups": tj_of[t].get("groups"),
                                      "group_kind": tj_of[t].get("group_kind"), "items_sha256": tj_of[t].get("items_sha256")} for t in tasks}},
               "systems": S}
    os.makedirs(out_dir, exist_ok=True)
    with open(f"{out_dir}/scores.json", "w", encoding="utf-8") as f:
        json.dump(clean(payload), f, indent=1)
    write_outputs(out_dir, payload, listed, head, core, ref, tj_of, systems_meta, head_odb, head_all)
    print(f"scored {len(folders)} systems on {len(tasks)} tasks in {time.time() - t0:.0f} s; outputs in {out_dir}")


def sort_key_core(e, key="core"):
    c = e[key]
    return (-(c["pair_accuracy"] if c and c["pair_accuracy"] is not None else -1), -(c["accuracy"] if c else -1))


def headline_table(tdir, S, listed, fams, tj_of, key, name, title_note):
    """one T1-style table (T1, T1b or T1c) over the families fams, aggregate S[d][key]; -> (Markdown, note)"""
    rows, order = [], sorted([d for d in listed if S[d].get(key)], key=lambda d: sort_key_core(S[d], key))
    rows_ci = []
    for d in order:
        c, m = S[d][key], S[d]["meta"]
        rows.append([m["name"], f1(c["accuracy"]), f1(c["pair_accuracy"]), f1(c["level3_pair_accuracy"]), f1(c["auto_at_5"]),
                     f1(c["acc_at_090"]) + (f" ({f1(c['share_at_090'])})" if c["acc_at_090"] is not None else ""), f1(c["ece"])])
        ci = c["ci"]
        row = [m["name"]]
        for k in ("accuracy", "pair_accuracy", "level3_pair_accuracy", "auto_at_5", "acc_at_090", "share_at_090", "ece"):
            v = c.get(k)
            lo, hi = ci.get(k, (None, None)) if v is not None else (None, None)
            row += [f1(v), f1(lo), f1(hi)]
        rows_ci.append(row)
    hdr = ["system", "accuracy", "pair accuracy", "level-3 pair accuracy", "auto_at_5", "acc_at_090 (share)", "calibration error"]
    pairs = [t for t in fams if tj_of[t].get("group_kind") == "contrast"]
    note = (f"{title_note} over {len(fams)} generated families ({', '.join(fams)}); macro means over families; pair accuracy over the "
            f"{len(pairs)} families with contrast groups; level-3 pair accuracy over those of them that have a level ladder; "
            f"acc_at_090 and its share pool all items; calibration error = 15-bin ECE; only systems with a valid run on every one of these "
            f"families. Intervals: tables/{name}_intervals.csv.")
    md = write_table(tdir, name, hdr, rows, note) if rows else "(no system has valid runs on every family of this table)"
    if not rows:
        write_table(tdir, name, hdr, [], note)
    hdr_ci = ["system"] + [f"{k}{x}" for k in ("accuracy", "pair_accuracy", "level3_pair_accuracy", "auto_at_5", "acc_at_090", "share_at_090", "ece")
                           for x in ("", "_lo", "_hi")]
    with open(f"{tdir}/{name}_intervals.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(hdr_ci)
        w.writerows(rows_ci)
    return md, note


def write_outputs(out_dir, payload, listed, head, core, ref, tj_of, systems_meta, head_odb=(), head_all=()):
    S = payload["systems"]
    tdir = f"{out_dir}/tables"
    os.makedirs(tdir, exist_ok=True)
    md = ["# Benchmark v1.3 (DecisionPivot) - scores", "",
          f"Seed {SEED}, {payload['meta']['resamples']} bootstrap resamples (groups are resampled where a task has groups). "
          "All values in points (x 100) with one decimal unless stated. The tables list the systems of the paper (`table: true` in `systems.json`); "
          "a system appears in a table only if it has a valid run on every task the table needs; the per-family and per-task sections below list every "
          "system with a run folder. `MISSING_RUNS.md` lists what is missing.", ""]
    # ---------------- T1, T1b, T1c
    for fams, key, name, title, note_head in ((head, "core", "T1_core_headline", "T1 Core track, headline (the 13 DecisionPivot families)", "T1 core headline"),
                                              (list(head_odb), "core_odb", "T1b_odb_headline", "T1b Generated families of Open Decision Bench", "T1b ODB headline"),
                                              (list(head_all), "core_all", "T1c_generated_headline", "T1c All generated families", "T1c generated headline")):
        if not fams:
            continue
        tmd, note = headline_table(tdir, S, listed, fams, tj_of, key, name, note_head)
        md += [f"## {title}", "", note, "", tmd, ""]
    # ---------------- T2
    shown = [t for t in core if any(t in S[d]["tasks"] for d in listed)]
    shown = [t for t in shown if tj_of[t].get("family_set", "decidebench") == "decidebench"] + \
        [t for t in shown if tj_of[t].get("family_set", "decidebench") != "decidebench"]
    unrun = [t for t in core if t not in shown]
    fam_cols = [f"{t} ({'pair' if tj_of[t].get('group_kind') == 'contrast' else 'acc.'}" +
                ("" if tj_of[t].get("family_set", "decidebench") == "decidebench" else f"; {tj_of[t]['family_set']}") + ")" for t in shown]
    rows2 = []
    for d in sorted([d for d in listed if any(t in S[d]["tasks"] for t in core)], key=lambda d: sort_key_core(S[d]) if S[d]["core"] else (1, 0)):
        row = [S[d]["meta"]["name"]]
        for t in shown:
            r = S[d]["tasks"].get(t)
            row.append("" if not r else f1(r["pair_accuracy"] if tj_of[t].get("group_kind") == "contrast" else r["accuracy"]))
        rows2.append(row)
    note2 = ("T2 generated families: pair accuracy (pair) where the family has contrast groups, accuracy (acc.) otherwise; the 13 DecisionPivot "
             "families first, then the families of another set (marked with the set, e.g. odb); empty = not run on this "
             "version of the items." + (f" Families that no listed system has been run on yet: {', '.join(unrun)}." if unrun else ""))
    md += ["## T2 Core track, per family", "", note2, "", write_table(tdir, "T2_core_per_family", ["system"] + fam_cols, rows2, note2), ""]
    with open(f"{tdir}/T2_core_per_family_long.csv", "w", newline="", encoding="utf-8") as f:     # v1.2: one row per system and family
        w = csv.writer(f)
        w.writerow(["system", "folder", "family", "family_set", "layer", "shown", "value", "accuracy", "pair_accuracy", "pair_direction",
                    "level3_accuracy", "level3_pair_accuracy", "auto_at_5", "ece"])
        for d in sorted([d for d in listed if any(t in S[d]["tasks"] for t in core)], key=lambda d: S[d]["meta"]["name"]):
            for t in core:
                r = S[d]["tasks"].get(t)
                if not r:
                    continue
                lv3 = (r.get("levels") or {}).get("3") or {}
                kind = "pair" if tj_of[t].get("group_kind") == "contrast" else "acc."
                w.writerow([S[d]["meta"]["name"], d, t, tj_of[t].get("family_set", "decidebench"), tj_of[t]["layer"], kind,
                            f1(r["pair_accuracy"] if kind == "pair" else r["accuracy"]), f1(r["accuracy"]), f1(r.get("pair_accuracy")),
                            f1(r.get("pair_direction")), f1(lv3.get("accuracy")), f1(lv3.get("pair_accuracy")), f1(r["auto_at_5"]), f1(r["ece"])])
    # ---------------- T3
    layers = sorted({tj_of[t]["layer"] for t in ref})
    rows3 = []
    for d in sorted([d for d in listed if S[d]["reference"] and S[d]["reference"].get("overall") is not None],
                    key=lambda d: -S[d]["reference"]["overall"]):
        r = S[d]["reference"]
        rows3.append([S[d]["meta"]["name"]] + [f1(r["layers"].get(L), 1.0) for L in layers] + [f1(r["overall"], 1.0)])
    note3 = ("T3 reference track: chance-corrected score (0 = chance, 100 = perfect) per layer, mean of the task scores floored at 0; total = "
             "mean of the layer scores; only systems with a valid run on every reference task.")
    md += ["## T3 Reference track, per layer and total", "", note3, "", write_table(tdir, "T3_reference_layers", ["system"] + layers + ["total"], rows3, note3), ""]
    # ---------------- T4
    rows4, pairs4 = [], []
    for d in sorted(S, key=lambda d: S[d]["meta"].get("name", d)):
        m = S[d]["meta"]
        if m.get("mode") == "with reasoning" and m.get("reasoning_of") in S and (m.get("table", False) or S[m["reasoning_of"]]["meta"].get("table", False)):
            pairs4.append((m["reasoning_of"], d))
    ref_names = set()
    for one, rs in pairs4:
        shared_ref = [t for t in ref if t in S[one]["tasks"] and t in S[rs]["tasks"]]
        ref_names.update(shared_ref)
        for dd, label in ((one, "one pass"), (rs, "with reasoning")):
            c = S[dd]["core"]
            if not c:
                continue
            rscore = mean([max(0.0, S[dd]["tasks"][t]["score"]) for t in shared_ref]) if shared_ref else None
            if label == "with reasoning" and "Auto-Think" in S[dd]["meta"].get("name", ""):
                label = "Auto-Think"
            rows4.append([S[dd]["meta"]["name"], label, f1(c["accuracy"]), f1(c["pair_accuracy"]), f1(c["level3_pair_accuracy"]), f1(c["auto_at_5"]),
                          f1(c["acc_at_090"]) + (f" ({f1(c['share_at_090'])})" if c["acc_at_090"] is not None else ""),
                          "" if c.get("tokens") is None else f"{c['tokens']:.0f}", f1(c.get("thought_share")),
                          "" if rscore is None else f1(rscore, 1.0)])
    note4 = ("T4 one pass against with reasoning, same model and same items: the one-pass read-out (p0) and the answer with reasoning from the same run. "
             "Auto-Think (v1.2) is the released default answer: the model writes a thought (limit 4,096 tokens) only when its top one-pass probability "
             "is below 0.90 and then answers 0.25 p0 + 0.75 p1 (p1 = read-out after the thought); a system named 'with reasoning' thinks on every item. "
             "Core columns as in T1 over the 13 DecisionPivot families; tokens per item = mean thought length per item, 0 for an item without a thought "
             "(macro mean over the families); thought share = share of the items with a thought; the last column is the mean chance-corrected score on "
             f"the reference tasks that both runs cover ({len(ref_names)} tasks). " + ("" if rows4 else "No system of the tables has both kinds of run."))
    hdr4 = ["system", "mode", "accuracy", "pair accuracy", "level-3 pair accuracy", "auto_at_5", "acc_at_090 (share)", "tokens per item",
            "thought share", "reference tasks score"]
    md += ["## T4 One pass against with reasoning", "", note4, "", write_table(tdir, "T4_one_pass_vs_reasoning", hdr4, rows4, note4), ""]
    md += per_system_detail(S, listed, core, ref, tj_of)
    with open(f"{out_dir}/report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    write_missing(out_dir, S, core, ref, tj_of, systems_meta)


def per_system_detail(S, listed, core, ref, tj_of):
    md = ["## Core track, every score per family", ""]
    cols = ["system", "acc.", "pair acc.", "pair dir.", "L1 pair", "L2 pair", "L3 pair", "auto_at_5", "auto_at_1", "acc_at_090 (share)", "aurc", "trigger_recall_20", "ece"]
    for t in core:
        md += [f"### `{t}`", ""]
        rows = []
        for d in listed:
            r = S[d]["tasks"].get(t)
            if not r or "accuracy" not in r:
                continue
            lv = r.get("levels") or {}
            rows.append([S[d]["meta"]["name"], f1(r["accuracy"]), f1(r.get("pair_accuracy")), f1(r.get("pair_direction"))]
                        + [f1((lv.get(str(L)) or {}).get("pair_accuracy") if r.get("pair_accuracy") is not None else (lv.get(str(L)) or {}).get("accuracy")) for L in LEVELS]
                        + [f1(r["auto_at_5"]), f1(r["auto_at_1"]), f1(r.get("acc_at_090")) + f" ({f1(r['share_at_090'])})" if r.get("acc_at_090") is not None else f"– ({f1(r['share_at_090'])})",
                           f1(r["aurc"]), f1(r.get("trigger_recall_20")), f1(r["ece"])])
        if rows:
            if tj_of[t].get("group_kind") != "contrast":
                md.append("(no contrast groups: the level columns show accuracy)")
                md.append("")
            md += ["| " + " | ".join(cols) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(cols))) + "|"]
            md += ["| " + " | ".join(c if c != "" else "–" for c in row) + " |" for row in rows]
            md.append("")
        dd = [(d, S[d]["tasks"][t]["dials"]) for d in listed if S[d]["tasks"].get(t, {}).get("dials")]
        if dd:
            md += [f"Per dial value (accuracy / pair accuracy, items): ", ""]
            names = sorted(next(iter(dd))[1])
            for nm in names:
                vals = sorted(next(iter(dd))[1][nm])
                md += ["| system | " + " | ".join(f"{nm} {v}" for v in vals) + " |", "|---|" + "---:|" * len(vals)]
                for d, dl in dd:
                    md.append("| " + S[d]["meta"]["name"] + " | " + " | ".join(
                        f"{f1(dl[nm][v]['accuracy'])} / {f1(dl[nm][v].get('pair_accuracy'))}" for v in vals) + " |")
                md.append("")
    md += ["## Reference track, every task", ""]
    cols = ["system", "task", "metric", "value [95% interval]", "score", "coverage", "ece", "auto_at_5", "acc_at_090 (share)"]
    for d in listed:
        rows = []
        for t in ref:
            r = S[d]["tasks"].get(t)
            if not r:
                continue
            if t in RANKING_ONLY.get(d, ()):                       # a published ranking written as relevance values: only the ranking metric means something
                rows.append([t, r["metric"], f"{r['value']:.3f} [{r['lo']:.3f}, {r['hi']:.3f}]", f"{r['score']:.1f}", f"{r['coverage']:.3f}", "", "", ""])
                continue
            rows.append([t, r["metric"], f"{r['value']:.3f} [{r['lo']:.3f}, {r['hi']:.3f}]", f"{r['score']:.1f}", f"{r['coverage']:.3f}",
                         "" if r.get("ece") is None else f"{r['ece']:.3f}", f1(r.get("auto_at_5")),
                         (f1(r.get("acc_at_090")) + f" ({f1(r.get('share_at_090'))})") if r.get("acc_at_090") is not None else ""])
        if rows:
            md += [f"### {S[d]['meta']['name']} (`{d}`)", "", "| " + " | ".join(cols[1:]) + " |", "|---|---|---|---:|---:|---:|---:|---:|"]
            md += ["| " + " | ".join(c if c != "" else "–" for c in row) + " |" for row in rows]
            md.append("")
    return md


def write_missing(out_dir, S, core, ref, tj_of, systems_meta):
    """MISSING_RUNS.md: per system the v1.1 tasks without a valid run, with the reason"""
    ip = f"{HERE}/runs_index.json"
    rejected = jload(ip).get("rejected", {}) if os.path.exists(ip) else {}
    all_tasks = core + ref
    md = ["# Missing runs", "",
          "For every system with a run folder in `runs/`, the v1.3 tasks that have no valid run, core tasks first (core = the generated families). A run is valid for a task when at least "
          "99% of the task's items have a line in the answer file (an answer or an error line) and the run was made on the items of this version "
          "(for generated families: the same `items_sha256`; a run made on an earlier version of a family does not count, even if its file is in `runs/`). "
          "Written by `score.py --all`; to fill a gap, produce the answer file as described in `runner/README.md`, put it in `runs/<system>/<task>.jsonl` and score again.", ""]
    rank = {"hosted": 0, "ours": 1, "open weights": 2}
    main = sorted([d for d in S if S[d]["meta"].get("table", False)], key=lambda d: (rank.get(S[d]["meta"].get("kind"), 3), d != "jev-1.13", S[d]["meta"].get("name", d)))
    other = sorted([d for d in S if not S[d]["meta"].get("table", False)], key=lambda d: S[d]["meta"].get("name", d))
    miss_of = {d: [t for t in all_tasks if t not in S[d]["tasks"]] for d in S}

    core_db = [t for t in core if tj_of[t].get("family_set", "decidebench") == "decidebench"]
    core_x = [t for t in core if t not in core_db]

    def summary(order, title):
        out = [f"## {title}", "", "| system | kind | DecisionPivot families without a run | ODB families without a run | reference tasks without a run |",
               "|---|---|---|---|---|"]
        for d in order:
            m = S[d]["meta"]
            mc = [t for t in miss_of[d] if t in core_db]
            mx = [t for t in miss_of[d] if t in core_x]
            mr = [t for t in miss_of[d] if tj_of[t].get("track") == "reference"]
            out.append(f"| {m['name']} (`{d}`) | {m.get('kind', '')} | {len(mc)} of {len(core_db)} | {len(mx)} of {len(core_x)} | {len(mr)} of {len(ref)} |")
        return out + [""]

    def detail(order):
        out = []
        for d in order:
            m = S[d]["meta"]
            miss = miss_of[d]
            out += [f"### {m['name']} (`{d}`)", ""]
            if m.get("kind") == "hosted":
                out += ["Hosted: a missing run is a set of API calls, not a GPU job.", ""]
            if not miss:
                out += ["Valid runs on all %d tasks." % len(all_tasks), ""]
                continue
            nr = S[d]["not_run"]
            groups = collections.OrderedDict()
            for t in miss:
                why = nr.get(t)
                if not why or why == "no file":
                    why = "no run recorded"
                    rj = rejected.get(f"{d}/{t}")
                    if rj:
                        if any(w in rj for w in ("not collected", "not run:", "stopped")):        # v1.2: a run that was not made, by decision
                            why = "not available (" + rj.split(": ", 1)[-1] + ")"
                        else:
                            why = "only a run on another version of the items exists, not counted (" + rj.split(": ", 1)[-1] + ")" if any(w in rj for w in ("version", "first", "differ", "tokens")) else "run refused (" + rj.split(": ", 1)[-1] + ")"
                groups.setdefault(why, []).append(t)
            for why, ts in groups.items():
                core_ts = [t for t in ts if tj_of[t].get("track") == "core"]
                ref_ts = [t for t in ts if tj_of[t].get("track") == "reference"]
                tail = ""
                if ref_ts:
                    tail = (f"{len(ref_ts)} reference tasks" + (" (" + ", ".join(f"`{t}`" for t in ref_ts) + ")" if len(ref_ts) <= 4 else ""))
                out.append(f"- {why}: " + ", ".join([f"`{t}`" for t in core_ts] + ([tail] if tail else [])))
            out.append("")
        return out

    md += summary(main, "Systems of the tables (the paper)") + ["## Per system", ""] + detail(main)
    if other:
        md += summary(other, "Systems that are not in the paper (data)") + [
            "These run folders are marked `table: false` in `systems.json` (v1.2: the other sizes of our final models, the released v1 models, research "
            "checkpoints, the Auto-Think one-pass read-outs, chat models with reasoning on a sample); they are listed so that nothing is hidden, not "
            "because anyone needs to queue them.", ""] + ["## Per system, not in the paper", ""] + detail(other)
    with open(f"{out_dir}/MISSING_RUNS.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")


# --------------------------------------------------------------------------------------------- v0-compatible single call
def score_task(task, run_dir, resamples, subsample=None):
    """one system on one task -> result dict, or None when the run does not count (v0 name kept)"""
    task_, res, _, _ = task_worker((task, [("x", run_dir)], resamples, subsample, {}))
    r = res.get("x")
    return r if r and "not_run" not in r else None


def main():
    global HERE, SYSTEMS_FILE
    argv = sys.argv[1:]
    opt = {}
    for flag in ("--tasks", "--out", "--resamples", "--subsample", "--jobs", "--headline-families", "--root", "--runs", "--systems"):
        if flag in argv:
            i = argv.index(flag)
            opt[flag] = argv[i + 1]
            del argv[i:i + 2]
    if "--root" in opt:
        HERE = os.path.abspath(opt["--root"])
        os.environ["DECISIONPIVOT_ROOT"] = HERE                   # worker processes read the same folder
    if "--systems" in opt:
        SYSTEMS_FILE = os.path.abspath(opt["--systems"])
    do_all = "--all" in argv
    registered_only = "--registered-only" in argv
    argv = [a for a in argv if a not in ("--all", "--registered-only")]
    resamples = int(opt.get("--resamples", 1000))
    jobs = int(opt.get("--jobs", 1))
    subsample = jload(opt["--subsample"]) if "--subsample" in opt else None
    tasks = opt["--tasks"].split(",") if "--tasks" in opt else None
    if do_all:
        build_all({"out": opt.get("--out"), "tasks": tasks, "resamples": resamples, "jobs": jobs, "subsample": subsample,
                   "headline": opt.get("--headline-families", "auto"), "registered_only": registered_only,
                   "runs": opt.get("--runs")})
        return
    specs = [tuple(a.split("=", 1)) for a in argv]
    tasks = tasks or sorted(t for t in os.listdir(f"{HERE}/tasks") if os.path.isfile(f"{HERE}/tasks/{t}/task.json"))
    tj_of = {t: jload(f"{HERE}/tasks/{t}/task.json") for t in tasks}
    specs = [(n, os.path.abspath(d)) for n, d in specs]
    results, not_run, boots = run_scoring(specs, tasks, resamples, subsample, jobs, load_index())
    allres, lines = {}, []
    for name, run_dir in specs:
        res = [results[name][t] for t in tasks if t in results[name]]
        allres[name] = res
        lines.append(f"== {name}  ({run_dir}; {len(res)} of {len(tasks)} tasks have a valid run)")
        lines.append(f"{'layer':5s} {'task':28s} {'metric':13s} {'value':>7s} {'95% interval':>17s} {'chance':>6s} {'score':>6s} {'cover':>6s} "
                     f"{'ece':>6s} {'brier':>6s} {'auroc':>6s} {'acc':>6s} {'pair':>6s} {'auto5':>6s} {'acc.90':>6s} {'share':>6s}")
        layers = collections.defaultdict(list)
        for r in sorted(res, key=lambda r: (r["layer"], r["task"])):
            layers[r["layer"]].append(max(0.0, r["score"]) if r["score"] == r["score"] else 0.0)

            def f3(k):
                return f"{r[k]:6.3f}" if r.get(k) is not None and r[k] == r[k] else f"{'':6s}"
            lines.append(f"{r['layer']:5s} {r['task']:28s} {r['metric']:13s} {r['value']:7.3f} [{r['lo']:6.3f}, {r['hi']:6.3f}] "
                         f"{r['chance']:6.3f} {r['score']:6.1f} {r['coverage']:6.3f} {f3('ece')} {f3('brier')} {f3('auroc')} {f3('accuracy')} "
                         f"{f3('pair_accuracy')} {f3('auto_at_5')} {f3('acc_at_090')} {f3('share_at_090')}")
        for t, why in sorted(not_run[name].items()):
            lines.append(f"{'':5s} {t:28s} not run on this version ({why})")
        if layers:
            ls = {k: sum(v) / len(v) for k, v in sorted(layers.items())}
            lines.append("   layer scores: " + "  ".join(f"{k} {v:.1f} ({len(layers[k])})" for k, v in ls.items())
                         + f"   overall {sum(ls.values()) / len(ls):.1f} over {len(ls)} layers")
            allres[name + "::layers"] = ls
    print("\n".join(lines))
    if "--out" in opt:
        os.makedirs(opt["--out"], exist_ok=True)
        with open(f"{opt['--out']}/scores.json", "w") as f:
            json.dump(clean(allres), f, indent=1)
        with open(f"{opt['--out']}/report.txt", "w") as f:
            f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
