"""Build the item file of the public reranking test (EVALUATION ONLY; never a training source).

Source: github.com/dchristopoulos/system1-rerank-bench (MIT), measured 2026-10-05: decision models in the reranker
slot on BEIR SciFact and NFCorpus, 100 test queries per data set, the same 50 hybrid-search candidates for every
model.  The repository publishes each arm's ranking per query; the candidates of a query are the documents of its
"hybrid" ranking.  Documents are the BEIR title and text joined with one space, as in the repository.
    python3 reference/build/rr_build.py REPO_DIR BEIR_DIR OUT.json
"""
import csv
import hashlib
import json
import sys

repo, beir, out = sys.argv[1:4]
manifest = json.load(open(f"{repo}/results/reranker-benchmark.json"))["datasets"]
res = {}
for name in ("scifact", "nfcorpus"):
    for f, h in manifest[name]["screen_manifest"]["inputs_sha256"].items():
        assert hashlib.sha256(open(f"{beir}/{name}/{f}", "rb").read()).hexdigest() == h, (name, f)
    corpus = {}
    for line in open(f"{beir}/{name}/corpus.jsonl", encoding="utf-8"):
        r = json.loads(line)
        corpus[r["_id"]] = (r.get("title", "") + " " + r["text"]).strip()
    qrels = {}
    for r in csv.DictReader(open(f"{beir}/{name}/qrels/test.tsv"), delimiter="\t"):
        if int(r["score"]) > 0:
            qrels.setdefault(r["query-id"], {})[r["corpus-id"]] = int(r["score"])
    queries = {}
    for line in open(f"{beir}/{name}/queries.jsonl", encoding="utf-8"):
        r = json.loads(line)
        queries[r["_id"]] = r["text"]
    arms = {}
    for line in open(f"{repo}/results/rankings/{name}.jsonl"):
        r = json.loads(line)
        arms.setdefault(r["arm"], {})[r["query_id"]] = r["ranking"]
    qids = sorted(arms["hybrid"])
    assert len(qids) == 100 and all(len(arms["hybrid"][q]) == 50 for q in qids)
    used = sorted({d for q in qids for d in arms["hybrid"][q]})
    res[name] = {"queries": {q: queries[q] for q in qids}, "candidates": {q: arms["hybrid"][q] for q in qids},
                 "corpus": {d: corpus[d] for d in used}, "qrels": {q: qrels[q] for q in qids},
                 "published": {a: v for a, v in arms.items()}}
    print(name, "queries", len(qids), "documents", len(used), "arms", sorted(arms))
json.dump(res, open(out, "w"), ensure_ascii=False)
