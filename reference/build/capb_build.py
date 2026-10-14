"""Capability-boundary pilot for the decision-model benchmark (EVALUATION ONLY; nothing here is a training source).

Decision: "will this model answer this question correctly?" - the question a router or an abstention layer asks before
generation.  The truth is model-relative and is itself a probability: stored best-of-N runs hold 16 or 32 sampled
answers of five public chat models (Gemma 3 4B / 12B, Granite 3.3 2B, Phi-4-mini, Phi-4) on evaluation-only question
sets with gold answers (open-domain QA: NQ, PopQA, WebQuestions, TriviaQA; reasoning: BBH tasks, StrategyQA, FOLIO,
ProofWriter, DROP; arithmetic word problems: SVAMP, ASDiv, GSM-Hard, GSM-Plus, MAWPS), each sample marked correct or
not.  The success rate of a model on a question is the label.
    python3 reference/build/capb_build.py OUT_DIR --questions DIR --samples DIR [--per-domain 500] [--shots 8] [--seed 0]
--questions DIR holds the question files ext_qa.jsonl, ext_reason.jsonl and ext_math.jsonl (one question per line: "pid", "set",
"question", ...); --samples DIR holds the stored sampled answers, <tag>_<model>/gen/samples_s*.jsonl with tag bonq / bonr / bonx
(one sampled answer per line: "pid", "correct" = 1 or 0).  Neither input is part of this repository (see reference/README.md).
Writes OUT_DIR/capb_items.jsonl: one row per (question, model, form) with form "zero" (model card + question) or
"shot" (card + a track record of --shots other questions of the same domain with their results + question), and the
label fields {"n", "k", "rate"}; OUT_DIR/capb_stats.json."""
import collections
import glob
import json
import random
import sys

S = None   # --questions DIR
R = None   # --samples DIR
DOM = {"qa": ("ext_qa.jsonl", "bonq"), "reason": ("ext_reason.jsonl", "bonr"), "math": ("ext_math.jsonl", "bonx")}
CARD = {"granite2b": "Granite 3.3 2B Instruct, an open chat model with 2 billion parameters",
        "phi4mini": "Phi-4-mini Instruct, an open chat model with 3.8 billion parameters",
        "gemma4b": "Gemma 3 4B, an open chat model with 4 billion parameters",
        "gemma12b": "Gemma 3 12B, an open chat model with 12 billion parameters",
        "phi4": "Phi-4, an open chat model with 14 billion parameters"}
INS = "Will the answering model's final answer to this question be correct?"
CRIT = {"yes": "Its final answer will be correct.", "no": "Its final answer will be wrong."}


def main():
    global S, R
    if len(sys.argv) < 2 or sys.argv[1].startswith("--") or "--questions" not in sys.argv or "--samples" not in sys.argv:
        sys.exit("usage: capb_build.py OUT_DIR --questions DIR --samples DIR [--per-domain 500] [--shots 8] [--seed 0]")
    out = sys.argv[1]
    S = sys.argv[sys.argv.index("--questions") + 1]
    R = sys.argv[sys.argv.index("--samples") + 1]
    arg = lambda k, d: type(d)(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
    per, shots, seed = arg("--per-domain", 500), arg("--shots", 8), arg("--seed", 0)
    rng = random.Random(seed)
    items, stats = [], {}
    for dom, (qfile, tag) in DOM.items():
        qs = {}
        for l in open(f"{S}/{qfile}"):
            r = json.loads(l)
            qs[r["pid"]] = r
        rate = {}
        for m in CARD:
            agg = collections.defaultdict(lambda: [0, 0])
            for f in glob.glob(f"{R}/{tag}_{m}/gen/samples_s*.jsonl"):
                for l in open(f):
                    if not l.endswith("\n"):
                        continue
                    r = json.loads(l)
                    a = agg[r["pid"]]
                    a[0] += 1
                    a[1] += int(str(r.get("correct")) == "1")
            if agg:
                rate[m] = {p: (n, k) for p, (n, k) in agg.items() if p in qs and n >= 16}
        models = [m for m in CARD if m in rate and len(rate[m]) >= 0.9 * len(qs)]       # models with (nearly) every question
        common = sorted(p for p in qs if all(p in rate[m] for m in models))
        by_set = collections.defaultdict(list)
        for p in common:
            by_set[qs[p]["set"]].append(p)
        test = []
        for s in sorted(by_set):                                   # the same number of questions from every source set
            rng.shuffle(by_set[s])
            test += by_set[s][:max(1, per // len(by_set))]
        test = set(test[:per])
        rest = [p for p in common if p not in test]
        stats[dom] = {"questions": len(qs), "models": models, "common": len(common), "test": len(test),
                      "mean_rate": {m: round(sum(rate[m][p][1] / rate[m][p][0] for p in test) / len(test), 4) for m in models}}
        for m in models:
            # track record: questions outside the test set, half the model usually gets right, half it usually gets wrong
            hi = [p for p in rest if rate[m][p][1] / rate[m][p][0] >= 0.75]
            lo = [p for p in rest if rate[m][p][1] / rate[m][p][0] <= 0.25]
            rng.shuffle(hi)
            rng.shuffle(lo)
            prof = hi[:shots // 2] + lo[:shots - shots // 2]
            rng.shuffle(prof)
            record = [{"question": qs[p]["question"],
                       "result": f"correct in {rate[m][p][1]} of {rate[m][p][0]} attempts"} for p in prof]
            for p in sorted(test):
                n, k = rate[m][p]
                base = {"domain": dom, "set": qs[p]["set"], "pid": p, "model": m, "n": n, "k": k, "rate": round(k / n, 4),
                        "question_chars": len(qs[p]["question"])}
                items.append(dict(base, form="zero", id=f"{dom}:{m}:{p}:zero",
                                  state={"answering_model": CARD[m], "question": qs[p]["question"]},
                                  questions={"q": {"type": "choice", "instructions": INS, "criteria": CRIT}}))
                items.append(dict(base, form="shot", id=f"{dom}:{m}:{p}:shot",
                                  state={"answering_model": CARD[m], "track_record_on_other_questions": record,
                                         "question": qs[p]["question"]},
                                  questions={"q": {"type": "choice", "instructions": INS, "criteria": CRIT}}))
    with open(f"{out}/capb_items.jsonl", "w") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    stats["items"] = len(items)
    json.dump(stats, open(f"{out}/capb_stats.json", "w"), indent=1)
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
