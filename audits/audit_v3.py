"""Shortcut and variety audit of the generated families (numpy only).
    python3 audits/audit_v3.py [--root DIR] [TASK ...] [--json FILE]   (needs numpy; default: every directory under DIR/tasks/, DIR = generated/)

Per task (all cross-validation is 5-fold with the rows of a `group` kept in one fold, mean of 5 fold seeds):
  major      share of the most frequent gold key;  pos = share of the most frequent gold POSITION in the listed options
  ref        max(major, pos, chance): what a rule that never reads anything can reach
  bow_opt    bag-of-words logistic regression on the OPTIONS only (words, words tagged with the option position, keys)
  bow_qopt   the same with the words of the question added (still without the state)
  per_opt    one logistic regression over single options (words of the option, key, position -> is this the gold option?),
             the option with the highest score is the answer
             -> all three must stay <= ref + 0.03
  pos_dev    largest distance of a gold-position share from 1/k (items grouped by their number of options k) -> <= 0.03
  len, lines yes/no tasks only: accuracy of the best single threshold (found on all rows, as audit.py does) on the number of
             characters and on the number of lines of the state -> both within 0.50 +- 0.02
  vocab      yes/no and three-way tasks: number of words of frequency >= 20 whose rate in one class is more than twice
             the rate in the rest (must be 0) and the worst ratio
  dup        rows whose state is identical to the state of another row -> 0
  bow_state  information only: the same regression on the words of the STATE (a value far above ref means that surface
             statistics of the state give the answer away; flagged with ! above ref + 0.08)
  domains, skeletons   distinct meta.domain values; distinct lines of the states after masking numbers and identifiers
A task PASSES when every required check holds."""
import collections
import json
import os
import re
import sys

import numpy as np

np.seterr(all="ignore")          # the BLAS of some platforms raises spurious floating-point flags in matmul; results are asserted finite
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repository root (this file is audits/audit_v3.py)
HERE = os.path.join(REPO, "generated")                               # the folder that holds tasks/<task>/; --root DIR changes it
TOK = re.compile(r"[a-z0-9_]+")
SEEDS = (11, 23, 37, 41, 59)


def keys_of(it):
    c = it["questions"]["q"].get("criteria")
    return [str(i) for i in range(len(c))] if isinstance(c, list) else list(c)


def opt_texts(it):
    c = it["questions"]["q"].get("criteria")
    return [str(x) for x in c] if isinstance(c, list) else [str(c[k]) for k in c]


def state_text(it):
    s = it["state"]
    if isinstance(s, str):
        return s
    return "\n".join(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for v in s.values())


def fold_ids(groups, seed, k=5):
    ug = sorted(set(groups))
    perm = np.random.RandomState(seed).permutation(len(ug))
    f = {ug[j]: i % k for i, j in enumerate(perm)}
    return np.array([f[g] for g in groups])


def fit(X, y, n_cls, l2=1.0, steps=400):
    """multinomial logistic regression, full-batch gradient descent with the step 1 / (bound of the curvature)"""
    n, d = X.shape
    W, b, Y = np.zeros((d, n_cls)), np.zeros(n_cls), np.eye(n_cls)[y]
    lr = 1.0 / (0.5 * np.linalg.norm(X, 2) ** 2 / n + l2 / n + 1e-9)
    for _ in range(steps):
        Z = X @ W + b
        Z -= Z.max(1, keepdims=True)
        P = np.exp(Z)
        P /= P.sum(1, keepdims=True)
        G = (P - Y) / n
        W -= lr * (X.T @ G + l2 * W / n)
        b -= lr * G.sum(0)
    assert np.isfinite(W).all() and np.isfinite(b).all()
    return W, b


def vectorise(docs_train, docs_test, min_df=2):
    df = collections.Counter(t for d in docs_train for t in set(d))
    vocab = {t: i for i, t in enumerate(sorted(t for t, c in df.items() if c >= min_df))}

    def mat(docs):
        X = np.zeros((len(docs), max(1, len(vocab))))
        for r, d in enumerate(docs):
            for t in set(d):
                j = vocab.get(t)
                if j is not None:
                    X[r, j] = 1.0
        return X
    return mat(docs_train), mat(docs_test)


def cv_class(docs, y, groups, n_cls):
    """grouped 5-fold accuracy of a bag-of-words classifier, mean over the fold seeds"""
    y, accs = np.array(y), []
    for seed in SEEDS:
        f, hit = fold_ids(groups, seed), 0
        for k in range(5):
            tr, te = np.where(f != k)[0], np.where(f == k)[0]
            Xtr, Xte = vectorise([docs[i] for i in tr], [docs[i] for i in te])
            W, b = fit(Xtr, y[tr], n_cls)
            hit += int(((Xte @ W + b).argmax(1) == y[te]).sum())
        accs.append(hit / len(y))
    return float(np.mean(accs))


def cv_per_option(items, gold_pos, groups):
    """every option is an example (its words, its key, its position); the answer is the option with the highest score"""
    docs, lab, owner = [], [], []
    for n, it in enumerate(items):
        for i, (k, t) in enumerate(zip(keys_of(it), opt_texts(it))):
            docs.append(TOK.findall(t.lower()) + [f"key={k.lower()}", f"pos={i}"])
            lab.append(int(i == gold_pos[n]))
            owner.append(n)
    lab, owner, accs = np.array(lab), np.array(owner), []
    for seed in SEEDS:
        f = fold_ids(groups, seed)
        fo, hit = f[owner], 0
        for k in range(5):
            tr, te = np.where(fo != k)[0], np.where(fo == k)[0]
            Xtr, Xte = vectorise([docs[i] for i in tr], [docs[i] for i in te])
            W, b = fit(Xtr, lab[tr], 2)
            s = (Xte @ W + b)
            s = s[:, 1] - s[:, 0]
            best = {}
            for j, e in enumerate(te):
                o = owner[e]
                if o not in best or s[j] > best[o][0]:
                    best[o] = (s[j], lab[e])
            hit += sum(v[1] for v in best.values())
        accs.append(hit / len(items))
    return float(np.mean(accs))


def best_threshold(xs, ys):
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


def vocab_offenders(states, gold, min_freq=20, max_ratio=2.0):
    classes = sorted(set(gold))
    sets = [set(re.findall(r"[a-z]+", s.lower())) for s in states]
    worst, bad = 1.0, []
    for c in classes:
        n1 = sum(g == c for g in gold)
        n0 = len(gold) - n1
        a, b = collections.Counter(), collections.Counter()
        for st, g in zip(sets, gold):
            (a if g == c else b).update(st)
        for t in set(a) | set(b):
            if a[t] + b[t] < min_freq:
                continue
            ra, rb = a[t] / n1, b[t] / n0
            ratio = max(ra, rb) / min(ra, rb) if min(ra, rb) > 0 else float("inf")
            worst = max(worst, ratio)
            if ratio > max_ratio:
                bad.append((t, c, a[t], b[t]))
    return sorted(set(bad)), worst


def skeleton(line):
    line = re.sub(r"\d", "0", line)
    return re.sub(r"\b\S*(?:[A-Z0-9_]|-\w)\S*\b", "X", line).strip()


def audit(task):
    d = f"{HERE}/tasks/{task}"
    tj = json.load(open(f"{d}/task.json"))
    items = [json.loads(l) for l in open(f"{d}/items.jsonl", encoding="utf-8")]
    n = len(items)
    keysets = [keys_of(it) for it in items]
    gold = [str(it["gold"]) for it in items]
    gpos = [ks.index(g) for ks, g in zip(keysets, gold)]
    groups = [it.get("group") or it["id"] for it in items]
    fixed = all(set(ks) == set(keysets[0]) for ks in keysets)
    chance = sum(1 / len(ks) for ks in keysets) / n
    major = collections.Counter(gold).most_common(1)[0][1] / n
    pos = collections.Counter(gpos).most_common(1)[0][1] / n
    ref = max(major, pos, chance)
    r = {"task": task, "layer": tj["layer"], "rows": n, "groups": len(set(groups)) if any(it.get("group") for it in items) else 0,
         "options": max(len(k) for k in keysets), "chance": chance, "major": major, "pos": pos, "ref": ref, "fixed_keys": fixed}
    # targets: the gold key when every row has the same keys, else the gold position
    if fixed:
        cls = sorted(set(keysets[0]))
        y, n_cls = [cls.index(g) for g in gold], len(cls)
    else:
        y, n_cls = gpos, max(len(k) for k in keysets)
    odocs, qdocs = [], []
    for it, ks in zip(items, keysets):
        doc = []
        for i, (k, t) in enumerate(zip(ks, opt_texts(it))):
            w = TOK.findall(t.lower())
            doc += w + [f"{x}@{i}" for x in w] + [f"key={k.lower()}@{i}"]
        odocs.append(doc)
        qdocs.append(doc + ["q:" + x for x in TOK.findall(it["questions"]["q"]["instructions"].lower())])
    r["bow_opt"] = cv_class(odocs, y, groups, n_cls)
    r["bow_qopt"] = cv_class(qdocs, y, groups, n_cls)
    r["per_opt"] = cv_per_option(items, gpos, groups)
    states = [state_text(it) for it in items]
    r["bow_state"] = cv_class([TOK.findall(s.lower()) for s in states], y, groups, n_cls)
    dev = 0.0
    by_k = collections.defaultdict(list)
    for ks, p in zip(keysets, gpos):
        by_k[len(ks)].append(p)
    for k, ps in by_k.items():
        if len(ps) >= 30:
            c = collections.Counter(ps)
            dev = max(dev, max(abs(c[i] / len(ps) - 1 / k) for i in range(k)))
    r["pos_dev"] = dev
    binary = fixed and set(keysets[0]) == {"yes", "no"}
    r["binary"] = binary
    if binary:
        ys = [g == "yes" for g in gold]
        r["len"] = best_threshold([len(s) for s in states], ys)
        r["lines"] = best_threshold([s.count("\n") + 1 for s in states], ys)
    if fixed and len(set(keysets[0])) <= 3:
        bad, worst = vocab_offenders(states, gold)
        r["vocab_bad"], r["vocab_worst"], r["vocab_examples"] = len(bad), worst, bad[:8]
    c = collections.Counter(states)
    r["dup"] = sum(v for v in c.values() if v > 1)
    r["domains"] = len({(it.get("meta") or {}).get("domain") for it in items} - {None})
    r["levels"] = dict(sorted(collections.Counter(str((it.get("meta") or {}).get("level")) for it in items).items()))
    r["instructions"] = len({it["questions"]["q"]["instructions"] for it in items})
    r["skeletons"] = len({skeleton(l) for s in states for l in s.split("\n") if l.strip()})
    lens = sorted(len(s) for s in states)
    r["chars"] = [lens[0], lens[n // 2], lens[-1]]
    fails = []
    for k in ("bow_opt", "bow_qopt", "per_opt"):
        if r[k] > ref + 0.03:
            fails.append(k)
    if dev > 0.03:
        fails.append("pos_dev")
    if binary and (abs(r["len"] - 0.5) > 0.02):
        fails.append("len")
    if binary and (abs(r["lines"] - 0.5) > 0.02):
        fails.append("lines")
    if r.get("vocab_bad"):
        fails.append("vocab")
    if r["dup"]:
        fails.append("dup")
    r["fails"], r["state_flag"] = fails, r["bow_state"] > ref + 0.08
    return r


def fmt(r):
    f3 = lambda k: f"{r[k]:6.3f}" if k in r else f"{'':6s}"
    voc = f"{r['vocab_bad']:d}/{r['vocab_worst']:.2f}" if "vocab_bad" in r else ""
    return (f"{r['layer']:2s} {r['task']:18s} {r['rows']:5d} {r['groups']:5d} {r['options']:3d} {r['chance']:6.3f} {r['major']:6.3f} {r['pos']:6.3f} | "
            f"{r['bow_opt']:6.3f} {r['bow_qopt']:6.3f} {r['per_opt']:6.3f} {r['pos_dev']:6.3f} {f3('len')} {f3('lines')} {voc:>8s} {r['dup']:4d} | "
            f"{r['bow_state']:6.3f}{'!' if r['state_flag'] else ' '} {r['domains']:3d} {r['skeletons']:5d} | "
            + ("PASS" if not r["fails"] else "FAIL " + ",".join(r["fails"])))


HEAD = (f"{'L':2s} {'task':18s} {'rows':>5s} {'grps':>5s} {'opt':>3s} {'chance':>6s} {'major':>6s} {'pos':>6s} | {'bowopt':>6s} {'bowqop':>6s} {'peropt':>6s} "
        f"{'posdev':>6s} {'len':>6s} {'lines':>6s} {'vocab':>8s} {'dup':>4s} | {'bowst':>6s}  {'dom':>3s} {'skel':>5s} | result")


def main():
    global HERE
    if "--root" in sys.argv:                                         # --root DIR: the folder that holds tasks/<task>/
        i = sys.argv.index("--root")
        HERE = os.path.abspath(sys.argv[i + 1])
        del sys.argv[i:i + 2]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
    if out:
        args.remove(out)
    tasks = args or sorted(t for t in os.listdir(f"{HERE}/tasks") if os.path.isfile(f"{HERE}/tasks/{t}/task.json"))
    print(HEAD)
    res = []
    for t in tasks:
        r = audit(t)
        res.append(r)
        print(fmt(r), flush=True)
        if r.get("vocab_examples"):
            print("      vocabulary offenders (word, class, in class, in rest):", r["vocab_examples"])
        print(f"      levels {r['levels']}  state characters min/median/max {r['chars']}  distinct instructions {r['instructions']}")
    if out:
        json.dump(res, open(out, "w"), indent=1)
    sys.exit(1 if any(r["fails"] for r in res) else 0)


if __name__ == "__main__":
    main()
